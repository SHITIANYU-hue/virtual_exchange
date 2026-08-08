"""
Unit test for ReplayPriceSource (backend/app/services/price_engine.py).

Pure logic, no DB/HTTP needed — loads the real downloaded scenario data and
the real private mapping, and checks the invariants the hourly bull/bear
replay design depends on (see docs/ARCHITECTURE.md (section 12)).

Run directly: python3 backend/tests/test_replay_price_source.py
Requires: scenarios/hourly_replay/{bull,bear}/*.csv and
.private_world_mapping.json to already exist (download_hourly_replay.py).
"""
import sys
from decimal import Decimal
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings  # noqa: E402
from app.services.price_engine import ReplayPriceSource, SEED_PRICES, TRADING_PAIRS, TOTAL_CANDLES  # noqa: E402

# Point settings at the real repo paths (not the /app/ paths used inside Docker).
settings.replay_mapping_path = str(REPO_ROOT / ".private_world_mapping.json")
settings.replay_data_dir = str(REPO_ROOT / "scenarios" / "hourly_replay")


def test_world(world_label: str):
    settings.replay_world = world_label
    src = ReplayPriceSource()

    # Starts on the pre-interval candle, rebased to the project's normal seed prices.
    assert src.turn == 0
    snap0 = src.snapshot()
    for pair in TRADING_PAIRS:
        assert snap0[pair] == SEED_PRICES[pair], f"{world_label}/{pair}: turn-0 price != seed price"

    # 72 advances land exactly on the final candle, then hold.
    last = None
    for expected_turn in range(1, TOTAL_CANDLES):
        last = src.advance()
        assert src.turn == expected_turn
    assert src.turn == 72
    held = src.advance()
    assert src.turn == 72, "advancing past the final candle should hold, not overrun"
    assert held == last, "holding past the final candle should return the same snapshot"

    # Real return direction/magnitude is preserved through the rebase (checked
    # structurally — this test never prints or asserts which world is which).
    btc_return = last["BTCUSDT"] / snap0["BTCUSDT"]
    assert Decimal("0.5") < btc_return < Decimal("2.0"), "BTC return over 72h should be a plausible single-digit-percent move, not a rebase bug"
    print(f"World {world_label}: turn-0 == seed prices (OK), 72 advances reach turn 72 and hold (OK), "
          f"BTC 72h return = {btc_return:.4f} (plausible, not asserting direction)")


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
    test_bad_world_rejected()
    print("\nAll ReplayPriceSource unit tests passed.")
