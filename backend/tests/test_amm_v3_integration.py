"""
Integration tests for pool_manager's mint/swap orchestration against a real DB.

Unlike test_amm_v3.py (pure math, no DB), these exercise the async SQLAlchemy
orchestration in pool_manager.py directly. Requires a scratch Postgres DB.
"""
import asyncio
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.database import Base
from app.models.user import User, UserRole
from app.models import balance, token, pool, pool_v3, position, message, order, price, trade  # noqa: F401
from app.models.pool_v3 import PoolV3, TickData
from app.services.amm_v3.tick_math import get_sqrt_ratio_at_tick
from app.services.amm_v3.pool_manager import (
    create_pool, mint, swap, _get_or_create_balance, mint_below_price_usdt,
)

TEST_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/agent_metaverse_test"


async def _fresh_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    return engine, Session


async def _make_funded_user(db, username, currency, amount):
    user = User(username=username, role=UserRole.user)
    db.add(user)
    await db.flush()
    bal = await _get_or_create_balance(db, user.id, currency)
    bal.available = Decimal(amount)
    await db.flush()
    return user


async def _test_zero_liquidity_skips_tick_cross_async():
    engine, Session = await _fresh_session()
    async with Session() as db:
        lp = await _make_funded_user(db, "lp", "USDT", "999999999")
        (await _get_or_create_balance(db, lp.id, "AAA")).available = Decimal("999999999")
        trader = await _make_funded_user(db, "trader", "USDT", "999999999")

        pool = await create_pool(db, "AAA", "USDT", 3000, get_sqrt_ratio_at_tick(30))
        await db.commit()

        # Position A: active, in range [0, 60].
        await mint(db, pool.id, lp.id, 0, 60, Decimal("1000"))
        # Position B: out of range, above current price [120, 180].
        # Ticks (60, 120) are a deliberate liquidity-free gap between them.
        await mint(db, pool.id, lp.id, 120, 180, Decimal("2000"))
        await db.commit()

        # Buy enough to exhaust A (needs ~3.00 USDT) and continue through the
        # empty gap partway into B's range (B needs ~6.04 USDT to fully cross,
        # so 7 lands inside it without exiting the far side).
        await swap(db, trader.id, pool.id, False, Decimal("7"))
        await db.commit()

        refreshed = await db.get(PoolV3, pool.id)
        assert 120 <= refreshed.tick < 180, (
            f"expected the swap to land inside B's range [120,180), got tick={refreshed.tick}"
        )
        assert refreshed.liquidity == Decimal("2000"), (
            "crossing into position B's range must activate its liquidity — "
            f"got pool.liquidity={refreshed.liquidity} (bug: the zero-liquidity branch "
            "jumps to the next initialized tick without crossing it)"
        )
    await engine.dispose()
    print("  PASSED\n")


def test_zero_liquidity_skips_tick_cross():
    print("=== Test: zero-liquidity branch must cross the tick it jumps to ===")
    asyncio.run(_test_zero_liquidity_skips_tick_cross_async())


async def _test_swap_rejects_negative_liquidity_async():
    engine, Session = await _fresh_session()
    async with Session() as db:
        lp = await _make_funded_user(db, "lp2", "USDT", "999999999")
        (await _get_or_create_balance(db, lp.id, "BBB")).available = Decimal("999999999")
        trader = await _make_funded_user(db, "trader2", "USDT", "999999999")

        pool = await create_pool(db, "BBB", "USDT", 3000, get_sqrt_ratio_at_tick(60))
        await db.commit()

        await mint(db, pool.id, lp.id, 0, 120, Decimal("1000"))
        await db.commit()

        # Simulate a bookkeeping inconsistency: tick 120's liquidity_net should
        # be exactly -1000 (matching the one position minted above). Corrupt it
        # so crossing this tick drives pool liquidity negative. This tests the
        # invariant guard itself, independent of how such an inconsistency
        # could arise in production.
        result = await db.execute(
            select(TickData).where(TickData.pool_id == pool.id, TickData.tick_index == 120)
        )
        td = result.scalar_one()
        assert td.liquidity_net == Decimal("-1000"), f"test setup assumption broken: {td.liquidity_net}"
        td.liquidity_net = Decimal("-5000")
        await db.commit()

        raised = None
        try:
            await swap(db, trader.id, pool.id, False, Decimal("20"))
        except HTTPException as e:
            raised = e

        assert raised is not None, (
            "swap() must reject a negative-liquidity state with a clean error, "
            "not silently return a corrupted result"
        )
        assert raised.status_code == 500 and "liquidity went negative" in raised.detail.lower(), (
            f"expected a clean internal-invariant error, got {raised.status_code}: {raised.detail}"
        )
    await engine.dispose()
    print("  PASSED\n")


def test_swap_rejects_negative_liquidity():
    print("=== Test: swap must reject a negative-liquidity invariant violation ===")
    asyncio.run(_test_swap_rejects_negative_liquidity_async())


async def _test_mint_below_price_usdt_async():
    engine, Session = await _fresh_session()
    async with Session() as db:
        lp = await _make_funded_user(db, "lp3", "USDT", "999999999")

        pool = await create_pool(db, "CCC", "USDT", 3000, get_sqrt_ratio_at_tick(0))
        await db.commit()

        result = await mint_below_price_usdt(db, pool.id, lp.id, Decimal("1000"), -120, -60)
        await db.commit()

        assert Decimal(result["amount0"]) == 0, f"a below-price position must cost no CCC, got {result['amount0']}"
        deposited = Decimal(result["amount1"])
        assert abs(deposited - Decimal("1000")) < Decimal("0.01"), (
            f"expected ~1000 USDT deposited, got {deposited}"
        )

        raised = None
        try:
            await mint_below_price_usdt(db, pool.id, lp.id, Decimal("1000"), -60, 60)
        except HTTPException as e:
            raised = e
        assert raised is not None and raised.status_code == 400, (
            "a range straddling/above the current price isn't expressible in USDT alone "
            "and must be rejected with a clear error, not silently mis-costed"
        )
    await engine.dispose()
    print("  PASSED\n")


def test_mint_below_price_usdt():
    print("=== Test: mint_below_price_usdt derives liquidity from a USDT amount ===")
    asyncio.run(_test_mint_below_price_usdt_async())


async def _test_mint_below_price_usdt_auto_range_async():
    engine, Session = await _fresh_session()
    async with Session() as db:
        lp = await _make_funded_user(db, "lp4", "USDT", "999999999")

        # current tick -85201 with tick_spacing 60 -- the exact real-experiment
        # scenario where agents repeatedly picked tick_upper=-85200 (one
        # tick_spacing too high) and got rejected without ever correcting it.
        pool = await create_pool(db, "DDD", "USDT", 3000, get_sqrt_ratio_at_tick(-85201))
        await db.commit()
        assert pool.tick == -85201, f"test setup assumption broken: pool.tick={pool.tick}"

        result = await mint_below_price_usdt(db, pool.id, lp.id, Decimal("1000"))
        await db.commit()

        tick_upper = result["tick_upper"]
        tick_lower = result["tick_lower"]
        assert tick_upper <= pool.tick, (
            f"auto-computed tick_upper={tick_upper} must be at or below the current tick ({pool.tick})"
        )
        assert tick_upper % pool.tick_spacing == 0, f"tick_upper={tick_upper} must align to tick_spacing"
        assert tick_lower < tick_upper, f"tick_lower={tick_lower} must be below tick_upper={tick_upper}"
    await engine.dispose()
    print("  PASSED\n")


def test_mint_below_price_usdt_auto_range():
    print("=== Test: mint_below_price_usdt computes a safe tick range when none is given ===")
    asyncio.run(_test_mint_below_price_usdt_auto_range_async())


if __name__ == "__main__":
    test_zero_liquidity_skips_tick_cross()
    test_swap_rejects_negative_liquidity()
    test_mint_below_price_usdt()
    test_mint_below_price_usdt_auto_range()
    print("=" * 60)
    print("ALL INTEGRATION TESTS PASSED")
    print("=" * 60)
