"""
Unit test for ReplayPriceSource (backend/app/services/price_engine.py).

Pure logic, no DB/HTTP needed — loads the real downloaded scenario data and
the real private mapping, and checks the invariants the hourly bull/bear
replay design depends on (see docs/plans/2026-07-22-hourly-bull-bear-replay-design.md).

Run directly: python3 backend/tests/test_replay_price_source.py
Requires: experiments/scenarios/hourly_replay/{bull,bear}/*.csv and
experiments/.private_world_mapping.json to already exist (download_hourly_replay.py).
"""
import sys
from decimal import Decimal
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings  # noqa: E402
from app.services.price_engine import ReplayPriceSource, SEED_PRICES, TRADING_PAIRS  # noqa: E402

# Point settings at the real repo paths (not the /app/ paths used inside Docker).
settings.replay_mapping_path = str(REPO_ROOT / "experiments" / ".private_world_mapping.json")
settings.replay_data_dir = str(REPO_ROOT / "experiments" / "scenarios" / "hourly_replay")


def test_world(world_label: str):
    settings.replay_world = world_label
    src = ReplayPriceSource()
    formal_hours = src.formal_hours  # per-world now, not a fixed 72

    # Starts on the pre-interval candle, rebased to the project's normal seed prices.
    assert src.turn == 0
    snap0 = src.snapshot()
    for pair in TRADING_PAIRS:
        assert snap0[pair] == SEED_PRICES[pair], f"{world_label}/{pair}: turn-0 price != seed price"

    # `formal_hours` advances land exactly on the final candle, then hold.
    last = None
    for expected_turn in range(1, formal_hours + 1):
        last = src.advance()
        assert src.turn == expected_turn
    assert src.turn == formal_hours
    held = src.advance()
    assert src.turn == formal_hours, "advancing past the final candle should hold, not overrun"
    assert held == last, "holding past the final candle should return the same snapshot"

    # Real return direction/magnitude is preserved through the rebase (checked
    # structurally — this test never prints or asserts which world is which).
    btc_return = last["BTCUSDT"] / snap0["BTCUSDT"]
    assert Decimal("0.3") < btc_return < Decimal("3.0"), f"BTC return over {formal_hours}h should be a plausible move, not a rebase bug"
    print(f"World {world_label}: {formal_hours} formal hours, turn-0 == seed prices (OK), "
          f"{formal_hours} advances reach turn {formal_hours} and hold (OK), "
          f"BTC {formal_hours}h return = {btc_return:.4f} (plausible, not asserting direction)")


def test_bad_world_rejected():
    settings.replay_world = "Z"
    try:
        ReplayPriceSource()
    except RuntimeError as e:
        print(f"World 'Z' correctly rejected: {e}")
        return
    raise AssertionError("ReplayPriceSource should reject an unmapped world label")


if __name__ == "__main__":
    test_world("A")
    test_world("B")
    test_world("C")
    test_bad_world_rejected()
    print("\nAll ReplayPriceSource unit tests passed.")
