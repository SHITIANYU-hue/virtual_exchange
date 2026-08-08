import asyncio
import csv
import json
import logging
from decimal import Decimal
from pathlib import Path

import httpx
from sqlalchemy import delete

from app.config import settings
from app.database import async_session
from app.models.price import PriceHistory
from app.websocket.broadcaster import manager

logger = logging.getLogger(__name__)

TRADING_PAIRS = ["ETHUSDT", "SOLUSDT", "BTCUSDT"]

# Fallback seed prices when Binance API is unreachable. Also doubles as the
# common rebase anchor for historical replay mode (see ReplayPriceSource) so
# a replayed world starts at the same price scale every other experiment has
# used, rather than exposing the real historical absolute price.
SEED_PRICES: dict[str, Decimal] = {
    "ETHUSDT": Decimal("2800.00"),
    "SOLUSDT": Decimal("150.00"),
    "BTCUSDT": Decimal("95000.00"),
}

FORMAL_HOURS = 72
TOTAL_CANDLES = FORMAL_HOURS + 1  # + 1 pre-interval "previous hour" for Turn 1

# In-memory latest prices
current_prices: dict[str, Decimal] = {}


async def fetch_binance_prices() -> dict[str, Decimal]:
    prices = {}
    async with httpx.AsyncClient(trust_env=False, timeout=5.0) as client:
        for pair in TRADING_PAIRS:
            try:
                resp = await client.get(f"{settings.binance_base_url}/api/v3/ticker/price", params={"symbol": pair})
                resp.raise_for_status()
                data = resp.json()
                prices[pair] = Decimal(data["price"])
            except Exception as e:
                logger.error(f"Failed to fetch {pair}: {e}")
                if pair in current_prices:
                    prices[pair] = current_prices[pair]
                elif pair in SEED_PRICES:
                    prices[pair] = SEED_PRICES[pair]
                    logger.warning(f"Using seed price for {pair}: {SEED_PRICES[pair]}")
    return prices


async def save_prices(prices: dict[str, Decimal]):
    async with async_session() as db:
        for pair, price in prices.items():
            # No explicit timestamp: PriceHistory.timestamp defaults to the DB's
            # NOW() at insert time. This must stay real wall-clock time — never
            # the historical replay hour — or it would leak which era is being
            # replayed to anything that reads /api/prices/{pair}/history.
            db.add(PriceHistory(pair=pair, price=price))
        await db.commit()


class ReplayPriceSource:
    """Serves one historical world's hourly candles, rebased to a blind common
    start price, advancing one historical hour per explicit advance() call.

    Never exposes which world ("bull"/"bear") or which real dates are behind
    the "A"/"B" label it was constructed with — see docs/ARCHITECTURE.md
    section 12.
    """

    def __init__(self):
        mapping = json.loads(Path(settings.replay_mapping_path).read_text())
        if settings.replay_world not in mapping:
            raise RuntimeError(
                f"replay_world '{settings.replay_world}' not found in private mapping"
            )
        scenario = mapping[settings.replay_world]  # resolved once, never logged below
        data_dir = Path(settings.replay_data_dir) / scenario

        raw_closes: dict[str, list[Decimal]] = {}
        opens_by_pair: dict[str, list[int]] = {}
        for pair in TRADING_PAIRS:
            csv_path = data_dir / f"{pair}.csv"
            with open(csv_path, newline="") as f:
                rows = list(csv.DictReader(f))
            if len(rows) != TOTAL_CANDLES:
                raise RuntimeError(
                    f"replay data for {pair} has {len(rows)} candles, expected {TOTAL_CANDLES}"
                )
            raw_closes[pair] = [Decimal(r["close"]) for r in rows]
            opens_by_pair[pair] = [int(r["open_time_ms"]) for r in rows]

        reference_pair, reference_opens = next(iter(opens_by_pair.items()))
        for pair, opens in opens_by_pair.items():
            if opens != reference_opens:
                raise RuntimeError(
                    f"replay data misaligned: {pair}'s hourly grid does not match {reference_pair}'s"
                )

        # Rebase so candle 0 (the pre-interval "previous hour") equals the
        # project's normal seed price, then scale every later candle by the
        # real historical return from that anchor — preserves the true
        # up/down path without exposing the real absolute price level.
        self.candles: dict[str, list[Decimal]] = {}
        for pair in TRADING_PAIRS:
            anchor = raw_closes[pair][0]
            common_start = SEED_PRICES[pair]
            # Quantize to cents — an unrounded Decimal division carries ~28
            # significant digits, which is nonsense for a USDT-quoted price
            # and would look conspicuously synthetic in an agent's prompt.
            self.candles[pair] = [
                (common_start * c / anchor).quantize(Decimal("0.01")) for c in raw_closes[pair]
            ]

        self.turn = 0  # 0 = pre-interval hour (what Turn 1 sees); N = formal hour N
        logger.info(f"Replay price source loaded: {len(TRADING_PAIRS)} pairs, {TOTAL_CANDLES} candles each")

    def snapshot(self) -> dict[str, Decimal]:
        return {pair: self.candles[pair][self.turn] for pair in TRADING_PAIRS}

    def advance(self) -> dict[str, Decimal]:
        if self.turn < FORMAL_HOURS:
            self.turn += 1
        else:
            logger.warning(
                f"Replay price source: already at final candle (turn {FORMAL_HOURS}); holding last price"
            )
        return self.snapshot()


replay_source: ReplayPriceSource | None = None


async def reset_replay_source():
    """Reinitialize the replay clock to turn 0 and wipe price_history.

    Called from the hard-reset admin endpoint when price_mode == "replay", so
    that starting a fresh --hard-reset world run can't be contaminated by a
    previous run's (or manual testing's) leftover price_history rows leaking
    extra apparent volatility through GET /api/prices/{pair}/history, and so
    the in-memory turn counter — which a DB-only hard-reset can't touch — goes
    back to 0 in lockstep with the wiped DB state. No-op outside replay mode.
    """
    global replay_source
    if settings.price_mode != "replay":
        return
    replay_source = ReplayPriceSource()
    current_prices.update(replay_source.snapshot())
    async with async_session() as db:
        await db.execute(delete(PriceHistory))
        await db.commit()
    await save_prices(replay_source.snapshot())
    logger.info("Replay price source reset to turn 0 (price_history cleared)")


async def replay_advance(requested_turn: int) -> dict:
    """Advance the replay source to `requested_turn`, idempotently.

    `requested_turn` is the experiment runner's cycle number (1-indexed). A
    retried call for a turn already applied is a no-op that returns the
    current snapshot, rather than double-advancing the historical clock.
    """
    if replay_source is None:
        raise RuntimeError("replay_advance called but price_mode is not 'replay'")
    if requested_turn <= replay_source.turn:
        return {"turn": replay_source.turn, "prices": replay_source.snapshot()}
    if requested_turn != replay_source.turn + 1:
        raise RuntimeError(
            f"turn mismatch: requested {requested_turn}, replay source is at turn "
            f"{replay_source.turn} (expected {replay_source.turn + 1})"
        )
    prices = replay_source.advance()
    current_prices.update(prices)
    await save_prices(prices)
    await manager.broadcast("prices", {
        "type": "price_update",
        "data": {pair: str(price) for pair, price in prices.items()},
    })
    from app.services.liquidation import check_liquidations
    await check_liquidations()
    return {"turn": replay_source.turn, "prices": prices}


async def price_update_loop():
    if settings.price_mode == "replay":
        global replay_source
        replay_source = ReplayPriceSource()
        current_prices.update(replay_source.snapshot())
        await save_prices(replay_source.snapshot())
        # Live polling is fully disabled in replay mode — prices only move via
        # explicit POST /api/admin/replay/advance calls from the experiment runner.
        while True:
            await asyncio.sleep(3600)
        return

    while True:
        try:
            prices = await fetch_binance_prices()
            if prices:
                current_prices.update(prices)
                await save_prices(prices)
                await manager.broadcast("prices", {
                    "type": "price_update",
                    "data": {pair: str(price) for pair, price in prices.items()},
                })
                logger.info(f"Price update: {prices}")
                # Check for liquidations after price update
                from app.services.liquidation import check_liquidations
                await check_liquidations()
        except Exception as e:
            logger.error(f"Price update error: {e}")
        await asyncio.sleep(settings.price_update_interval)
