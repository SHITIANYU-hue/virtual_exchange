"""
Tests for agents/run.py's portfolio valuation, specifically V3 LP position value.

Run directly: python3 agents/test_run.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.run import _calculate_portfolio_value, _estimate_v3_position_value


def _pool(pool_id, token0, token1, tick, price):
    return {
        "pool_id": pool_id, "token0": token0, "token1": token1,
        "tick": tick, "price": str(price), "liquidity": "999999",
    }


def test_v3_position_value_below_range_is_pure_quote_token():
    # tick_upper <= current tick: position holds only token1. When token1 is USDT
    # itself, the amount needs no further price conversion.
    pool = _pool("p1", "MOON", "USDT", tick=0, price=1.0)
    position = {"pool_id": "p1", "tick_lower": -1200, "tick_upper": -600, "liquidity": "100000"}
    value = _estimate_v3_position_value(position, pool)
    expected = 2867.9630427111747
    assert abs(value - expected) < 0.01, f"expected ~{expected}, got {value}"
    print(f"  below-range position (pure USDT): {value:.4f} ✓")


def test_v3_position_value_above_range_is_pure_base_token():
    # tick_lower > current tick: position holds only token0, converted at the
    # pool's price (USDT per token0) -- must multiply, not divide.
    pool = _pool("p1", "MOON", "USDT", tick=0, price=3.0)
    position = {"pool_id": "p1", "tick_lower": 600, "tick_upper": 1200, "liquidity": "100000"}
    value = _estimate_v3_position_value(position, pool)
    expected = 8603.889128133524
    assert abs(value - expected) < 0.01, f"expected ~{expected}, got {value}"
    print(f"  above-range position (pure base token x price): {value:.4f} ✓")


def test_v3_position_value_in_range_is_mixed():
    pool = _pool("p1", "MOON", "USDT", tick=0, price=3.0)
    position = {"pool_id": "p1", "tick_lower": -600, "tick_upper": 600, "liquidity": "100000"}
    value = _estimate_v3_position_value(position, pool)
    expected = 11821.204351653558
    assert abs(value - expected) < 0.01, f"expected ~{expected}, got {value}"
    print(f"  in-range position (mixed, both legs valued): {value:.4f} ✓")


def test_v3_position_value_zero_liquidity_is_zero():
    pool = _pool("p1", "MOON", "USDT", tick=0, price=1.0)
    position = {"pool_id": "p1", "tick_lower": -600, "tick_upper": 600, "liquidity": "0"}
    value = _estimate_v3_position_value(position, pool)
    assert value == 0.0, f"expected 0, got {value}"
    print("  zero-liquidity position: 0 ✓ (matches every already-withdrawn historical position)")


def test_v3_position_value_handles_token0_is_usdt_ordering():
    # token0=USDT, token1=ZENITH (alphabetical U < Z). Below range -> pure token1
    # (ZENITH), which must be converted by DIVIDING by price (ZENITH per USDT),
    # not multiplying -- price=2.0 here makes a multiply/divide mixup fail loudly
    # (divide gives ~1434, multiply would give ~5736).
    pool = _pool("p2", "USDT", "ZENITH", tick=0, price=2.0)
    position = {"pool_id": "p2", "tick_lower": -1200, "tick_upper": -600, "liquidity": "100000"}
    value = _estimate_v3_position_value(position, pool)
    expected = 1433.9815213555873
    assert abs(value - expected) < 0.01, f"expected ~{expected}, got {value}"
    print(f"  token0=USDT ordering handled correctly (divide, not multiply): {value:.4f} ✓")


def test_calculate_portfolio_value_includes_v3_position_value():
    state = {
        "balances": [{"currency": "USDT", "available": "1000", "locked": "0"}],
        "positions": [],
        "v3_pools": [_pool("p1", "MOON", "USDT", tick=0, price=1.0)],
        "v3_positions": [
            {"pool_id": "p1", "tick_lower": -1200, "tick_upper": -600, "liquidity": "100000"},
        ],
        "tokens": [],
        "prices": {},
    }
    total = _calculate_portfolio_value(state)
    expected = 1000 + 2867.9630427111747
    assert abs(total - expected) < 0.01, f"expected ~{expected}, got {total}"
    print(f"  portfolio total now includes locked LP value: {total:.4f} ✓")


def test_calculate_portfolio_value_unchanged_when_no_v3_positions():
    state = {
        "balances": [{"currency": "USDT", "available": "1000", "locked": "0"}],
        "positions": [],
        "v3_pools": [],
        "v3_positions": [],
        "tokens": [],
        "prices": {},
    }
    total = _calculate_portfolio_value(state)
    assert total == 1000.0, f"expected 1000, got {total}"
    print("  no v3_positions key/empty list: total unchanged ✓ (no regression for old callers)")


if __name__ == "__main__":
    test_v3_position_value_below_range_is_pure_quote_token()
    test_v3_position_value_above_range_is_pure_base_token()
    test_v3_position_value_in_range_is_mixed()
    test_v3_position_value_zero_liquidity_is_zero()
    test_v3_position_value_handles_token0_is_usdt_ordering()
    test_calculate_portfolio_value_includes_v3_position_value()
    test_calculate_portfolio_value_unchanged_when_no_v3_positions()
    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
