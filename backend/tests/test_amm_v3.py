"""
Integration tests for V3 AMM engine.

Tests the math libraries end-to-end without a database,
simulating a complete pump & dump cycle.
"""
import sys
from decimal import Decimal
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.amm_v3.tick_math import (
    get_sqrt_ratio_at_tick, get_tick_at_sqrt_ratio, MIN_TICK, MAX_TICK
)
from app.services.amm_v3.sqrt_price_math import (
    get_amount0_delta, get_amount1_delta,
    get_next_sqrt_price_from_input, get_next_sqrt_price_from_output,
)
from app.services.amm_v3.swap_math import compute_swap_step
from app.services.amm_v3.tick_bitmap import TickBitmapManager
from app.services.amm_v3.position_lib import (
    TickInfo, PositionInfo, update_tick, cross_tick,
    get_fee_growth_inside, update_position,
)


def test_tick_math():
    print("=== Test: tick_math ===")

    # Tick 0 → price = 1.0
    sqrt_p = get_sqrt_ratio_at_tick(0)
    assert sqrt_p == Decimal("1"), f"tick 0 should give sqrt_price=1, got {sqrt_p}"
    print("  tick 0 → sqrt_price=1.0 ✓")

    # Roundtrip
    for tick in [-5000, -100, 0, 100, 5000, 100000]:
        sqrt_p = get_sqrt_ratio_at_tick(tick)
        tick_back = get_tick_at_sqrt_ratio(sqrt_p)
        assert tick_back == tick, f"Roundtrip failed: {tick} → {sqrt_p} → {tick_back}"
    print("  Roundtrip tick→sqrt→tick ✓ (6 ticks tested)")

    # Price at tick 10000 ≈ 1.0001^10000 ≈ 2.718
    p_10k = get_sqrt_ratio_at_tick(10000) ** 2
    assert Decimal("2.7") < p_10k < Decimal("2.8"), f"Price at tick 10000 should be ~2.718, got {p_10k}"
    print(f"  tick 10000 → price={p_10k:.4f} ≈ e ✓")

    # Negative tick → price < 1
    p_neg = get_sqrt_ratio_at_tick(-10000) ** 2
    assert p_neg < Decimal("1"), f"Negative tick should give price < 1, got {p_neg}"
    print(f"  tick -10000 → price={p_neg:.6f} < 1 ✓")

    print("  PASSED\n")


def test_sqrt_price_math():
    print("=== Test: sqrt_price_math ===")

    L = Decimal("10000")
    sqrt_a = get_sqrt_ratio_at_tick(-1000)
    sqrt_b = get_sqrt_ratio_at_tick(1000)

    # Amount deltas should be positive and reasonable
    dx = get_amount0_delta(sqrt_a, sqrt_b, L)
    dy = get_amount1_delta(sqrt_a, sqrt_b, L)
    assert dx > 0 and dy > 0, f"Amounts should be positive: dx={dx}, dy={dy}"
    print(f"  L=10000, range [-1000,1000]: dx={dx:.4f}, dy={dy:.4f} ✓")

    # Symmetry: dx ≈ dy for range centered at tick 0
    assert abs(dx - dy) < dx * Decimal("0.01"), f"Amounts should be symmetric around tick 0"
    print(f"  Symmetry: |dx-dy|/dx = {abs(dx-dy)/dx:.6f} < 1% ✓")

    # getNextSqrtPriceFromInput: adding token0 should decrease price
    sqrt_p = get_sqrt_ratio_at_tick(0)
    sqrt_next = get_next_sqrt_price_from_input(sqrt_p, L, Decimal("100"), zero_for_one=True)
    assert sqrt_next < sqrt_p, f"Adding token0 should decrease price"
    print(f"  Adding 100 token0: price {sqrt_p**2:.6f} → {sqrt_next**2:.6f} (decreased) ✓")

    # Adding token1 should increase price
    sqrt_next2 = get_next_sqrt_price_from_input(sqrt_p, L, Decimal("100"), zero_for_one=False)
    assert sqrt_next2 > sqrt_p, f"Adding token1 should increase price"
    print(f"  Adding 100 token1: price {sqrt_p**2:.6f} → {sqrt_next2**2:.6f} (increased) ✓")

    print("  PASSED\n")


def test_swap_math():
    print("=== Test: swap_math ===")

    sqrt_p = get_sqrt_ratio_at_tick(0)  # price = 1.0
    sqrt_target = get_sqrt_ratio_at_tick(-500)  # target price
    L = Decimal("10000")

    # ExactInput: swap 50 token0
    result = compute_swap_step(sqrt_p, sqrt_target, L, Decimal("50"), 3000)
    assert result.amount_in > 0, "amount_in should be positive"
    assert result.amount_out > 0, "amount_out should be positive"
    assert result.fee_amount > 0, "fee should be positive"
    assert result.amount_in + result.fee_amount <= Decimal("50"), "Total consumed should not exceed input"
    print(f"  ExactInput 50 token0: in={result.amount_in:.4f}, out={result.amount_out:.4f}, fee={result.fee_amount:.4f} ✓")
    print(f"    Price: {sqrt_p**2:.6f} → {result.sqrt_ratio_next**2:.6f} ✓")

    # ExactOutput: get 30 token1
    result2 = compute_swap_step(sqrt_p, sqrt_target, L, Decimal("-30"), 3000)
    assert result2.amount_out <= Decimal("30"), "Output should not exceed requested"
    print(f"  ExactOutput 30 token1: in={result2.amount_in:.4f}, out={result2.amount_out:.4f}, fee={result2.fee_amount:.4f} ✓")

    print("  PASSED\n")


def test_tick_bitmap():
    print("=== Test: tick_bitmap ===")

    bm = TickBitmapManager(tick_spacing=60)

    # Initialize some ticks
    bm.flip_tick(-600)
    bm.flip_tick(-120)
    bm.flip_tick(0)
    bm.flip_tick(300)
    bm.flip_tick(600)

    assert bm.is_initialized(0), "tick 0 should be initialized"
    assert bm.is_initialized(300), "tick 300 should be initialized"
    assert not bm.is_initialized(60), "tick 60 should NOT be initialized"
    print("  Initialization checks ✓")

    # Search right from tick 0
    next_tick, init = bm.next_initialized_tick_within_one_word(0, lte=False)
    assert next_tick == 300 and init, f"Next right from 0 should be 300, got {next_tick}"
    print(f"  Next right from 0: tick={next_tick} ✓")

    # Search left from tick 300
    next_tick2, init2 = bm.next_initialized_tick_within_one_word(300, lte=True)
    assert next_tick2 == 300 and init2, f"At/left from 300 should be 300, got {next_tick2}"
    print(f"  At/left from 300: tick={next_tick2} ✓")

    # Search left from tick 240 (between 0 and 300)
    next_tick3, init3 = bm.next_initialized_tick_within_one_word(240, lte=True)
    assert next_tick3 == 0 and init3, f"Left from 240 should be 0, got {next_tick3}"
    print(f"  Left from 240: tick={next_tick3} ✓")

    # Serialization roundtrip
    data = bm.to_dict()
    bm2 = TickBitmapManager.from_dict(60, data)
    assert bm2.is_initialized(0), "Deserialized bitmap should have tick 0"
    assert bm2.is_initialized(600), "Deserialized bitmap should have tick 600"
    print("  Serialization roundtrip ✓")

    print("  PASSED\n")


def test_position_and_fees():
    print("=== Test: position_lib (fees) ===")

    # Simulate: add liquidity, then swap generates fees, then check fee accrual

    # Initialize tick infos
    ti_lower = TickInfo()
    ti_upper = TickInfo()

    tick_lower = -600
    tick_upper = 600
    tick_current = 0

    fg0 = Decimal("0")
    fg1 = Decimal("0")

    # Add liquidity
    L = Decimal("5000")
    flipped_l = update_tick(ti_lower, tick_lower, tick_current, L, fg0, fg1, upper=False)
    flipped_u = update_tick(ti_upper, tick_upper, tick_current, L, fg0, fg1, upper=True)

    assert flipped_l and flipped_u, "Both ticks should be flipped (first LP)"
    assert ti_lower.liquidity_gross == L
    assert ti_lower.liquidity_net == L
    assert ti_upper.liquidity_net == -L  # upper tick subtracts
    print(f"  Add liquidity L={L}: lower_net={ti_lower.liquidity_net}, upper_net={ti_upper.liquidity_net} ✓")

    # Create position
    fg_in_0, fg_in_1 = get_fee_growth_inside(ti_lower, ti_upper, tick_lower, tick_upper, tick_current, fg0, fg1)
    pos = PositionInfo()
    update_position(pos, L, fg_in_0, fg_in_1)
    assert pos.liquidity == L
    print(f"  Position created: liquidity={pos.liquidity} ✓")

    # Simulate some fee accrual (as if swaps happened)
    fg0 = Decimal("0.005")  # 0.5% total fee growth on token0
    fg1 = Decimal("0.003")  # 0.3% total fee growth on token1

    # Check fee growth inside position range
    fg_in_0_new, fg_in_1_new = get_fee_growth_inside(
        ti_lower, ti_upper, tick_lower, tick_upper, tick_current, fg0, fg1
    )
    assert fg_in_0_new > 0 or fg_in_1_new > 0, "Fee growth inside should be positive after swaps"
    print(f"  Fee growth inside: token0={fg_in_0_new:.6f}, token1={fg_in_1_new:.6f} ✓")

    # Update position to collect fees
    update_position(pos, Decimal("0"), fg_in_0_new, fg_in_1_new)
    assert pos.tokens_owed_0 > 0 or pos.tokens_owed_1 > 0, "Should have fees owed"
    print(f"  Fees owed: token0={pos.tokens_owed_0:.6f}, token1={pos.tokens_owed_1:.6f} ✓")

    # Test cross tick
    liquidity_net = cross_tick(ti_lower, fg0, fg1)
    assert liquidity_net == L, f"Cross lower tick should return L={L}, got {liquidity_net}"
    print(f"  Cross tick: liquidityNet={liquidity_net} ✓")

    print("  PASSED\n")


def test_pump_and_dump_simulation():
    """Simulate a complete pump & dump using V3 math (no DB needed)."""
    print("=== Test: Pump & Dump Simulation ===")

    # === SETUP: GoldenWhale creates a MOON/USDT pool ===
    initial_price = Decimal("0.01")  # $0.01 per MOON
    sqrt_price = initial_price.sqrt()

    initial_tick = get_tick_at_sqrt_ratio(sqrt_price)
    print(f"  Initial price: ${initial_price}")
    print(f"  Initial tick: {initial_tick}")
    print(f"  Initial √price: {sqrt_price:.10f}")

    # Pool liquidity range: ±5x around initial price
    import math
    tick_range = int(math.log(5) / math.log(1.0001))
    tick_spacing = 60
    tick_lower = ((initial_tick - tick_range) // tick_spacing) * tick_spacing
    tick_upper = ((initial_tick + tick_range) // tick_spacing + 1) * tick_spacing

    print(f"  Liquidity range: [{tick_lower}, {tick_upper}]")

    # Whale seeds $5000 USDT of liquidity
    usdt_liquidity = Decimal("5000")
    sqrt_lower = get_sqrt_ratio_at_tick(tick_lower)

    # L = USDT / (√P - √P_lower)
    L = usdt_liquidity / (sqrt_price - sqrt_lower)
    print(f"  Liquidity (L): {L:.2f}")

    # === PHASE 1: Retail buys $500 worth of MOON ===
    print(f"\n  --- Retail buys $500 of MOON ---")
    sqrt_target = get_sqrt_ratio_at_tick(tick_upper)

    # Buying MOON = selling USDT for MOON = oneForZero (if MOON=token0, USDT=token1)
    # For simplicity: assume MOON < USDT alphabetically, so MOON=token0, USDT=token1
    # Buying MOON with USDT: zero_for_one=False (inputting token1=USDT, getting token0=MOON)
    step = compute_swap_step(sqrt_price, sqrt_target, L, Decimal("500"), 3000)

    price_after_buy = step.sqrt_ratio_next ** 2
    print(f"  USDT spent: {step.amount_in + step.fee_amount:.2f}")
    print(f"  MOON received: {step.amount_out:.2f}")
    print(f"  Fee paid: {step.fee_amount:.4f}")
    print(f"  Price: ${initial_price} → ${price_after_buy:.6f}")
    print(f"  Price increase: {(price_after_buy / initial_price - 1) * 100:.1f}%")

    assert price_after_buy > initial_price, "Price should increase after buy"

    # === PHASE 2: More retail FOMO ($1000) ===
    print(f"\n  --- More FOMO: $1000 buy ---")
    step2 = compute_swap_step(step.sqrt_ratio_next, sqrt_target, L, Decimal("1000"), 3000)
    price_after_fomo = step2.sqrt_ratio_next ** 2
    print(f"  USDT spent: {step2.amount_in + step2.fee_amount:.2f}")
    print(f"  MOON received: {step2.amount_out:.2f}")
    print(f"  Price: ${price_after_buy:.6f} → ${price_after_fomo:.6f}")
    print(f"  Total price increase from start: {(price_after_fomo / initial_price - 1) * 100:.1f}%")

    # === PHASE 3: Whale dumps 500,000 MOON ===
    print(f"\n  --- WHALE DUMPS 500,000 MOON ---")
    sqrt_dump_target = get_sqrt_ratio_at_tick(tick_lower)

    # Selling MOON for USDT: zero_for_one=True (inputting token0=MOON, getting token1=USDT)
    step3 = compute_swap_step(step2.sqrt_ratio_next, sqrt_dump_target, L, Decimal("500000"), 3000)
    price_after_dump = step3.sqrt_ratio_next ** 2
    print(f"  MOON sold: {step3.amount_in:.2f}")
    print(f"  USDT received: {step3.amount_out:.2f}")
    print(f"  Price: ${price_after_fomo:.6f} → ${price_after_dump:.8f}")
    print(f"  Price crash: {(1 - price_after_dump / price_after_fomo) * 100:.1f}%")

    assert price_after_dump < price_after_fomo, "Price should crash after dump"

    # === P&L Summary ===
    retail_spent = step.amount_in + step.fee_amount + step2.amount_in + step2.fee_amount
    whale_received = step3.amount_out
    print(f"\n  === P&L Summary ===")
    print(f"  Retail total spent: ${retail_spent:.2f} USDT")
    print(f"  Whale received from dump: ${whale_received:.2f} USDT")
    print(f"  Whale profit (approx): ${whale_received - usdt_liquidity:.2f} USDT")

    print("\n  PASSED\n")


if __name__ == "__main__":
    test_tick_math()
    test_sqrt_price_math()
    test_swap_math()
    test_tick_bitmap()
    test_position_and_fees()
    test_pump_and_dump_simulation()
    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
