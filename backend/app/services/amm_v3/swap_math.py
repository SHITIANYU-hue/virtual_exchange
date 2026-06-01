"""
Swap Math — computeSwapStep for Uniswap V3.

This is the core per-step swap calculation. Each call computes the swap
result within a single liquidity range (between two initialized ticks).

Corresponds to: SwapMath.computeSwapStep in Solidity.
"""
from decimal import Decimal, ROUND_UP, ROUND_DOWN
from dataclasses import dataclass

from .sqrt_price_math import (
    get_amount0_delta,
    get_amount1_delta,
    get_next_sqrt_price_from_input,
    get_next_sqrt_price_from_output,
)


@dataclass
class SwapStepResult:
    sqrt_ratio_next: Decimal    # new √price after this step
    amount_in: Decimal          # tokens consumed as input
    amount_out: Decimal         # tokens produced as output
    fee_amount: Decimal         # fee charged on input


def compute_swap_step(
    sqrt_ratio_current: Decimal,
    sqrt_ratio_target: Decimal,
    liquidity: Decimal,
    amount_remaining: Decimal,
    fee_pips: int,
) -> SwapStepResult:
    """
    Compute a single swap step within one liquidity range.

    Args:
        sqrt_ratio_current: current √price
        sqrt_ratio_target: target √price (next tick or price limit)
        liquidity: available liquidity in this range
        amount_remaining: remaining amount to swap (positive = exactInput, negative = exactOutput)
        fee_pips: fee in hundredths of a bip (e.g. 3000 = 0.3%)

    Returns:
        SwapStepResult with new price, amounts in/out, and fee

    This is the direct Python equivalent of SwapMath.computeSwapStep in Solidity.
    """
    zero_for_one = sqrt_ratio_current >= sqrt_ratio_target
    exact_input = amount_remaining >= 0

    FEE_DENOMINATOR = Decimal("1000000")
    fee_rate = Decimal(fee_pips)

    if exact_input:
        # Remove fee from input amount for calculation
        amount_remaining_less_fee = amount_remaining * (FEE_DENOMINATOR - fee_rate) / FEE_DENOMINATOR

        # Calculate max amount needed to reach target price
        if zero_for_one:
            amount_in = get_amount0_delta(sqrt_ratio_target, sqrt_ratio_current, liquidity, True)
        else:
            amount_in = get_amount1_delta(sqrt_ratio_current, sqrt_ratio_target, liquidity, True)

        # Can we reach the target price?
        if amount_remaining_less_fee >= amount_in:
            sqrt_ratio_next = sqrt_ratio_target
        else:
            sqrt_ratio_next = get_next_sqrt_price_from_input(
                sqrt_ratio_current, liquidity, amount_remaining_less_fee, zero_for_one
            )
    else:
        # exactOutput mode: amount_remaining is negative
        if zero_for_one:
            amount_out = get_amount1_delta(sqrt_ratio_target, sqrt_ratio_current, liquidity, False)
        else:
            amount_out = get_amount0_delta(sqrt_ratio_current, sqrt_ratio_target, liquidity, False)

        if abs(amount_remaining) >= amount_out:
            sqrt_ratio_next = sqrt_ratio_target
        else:
            try:
                sqrt_ratio_next = get_next_sqrt_price_from_output(
                    sqrt_ratio_current, liquidity, abs(amount_remaining), zero_for_one
                )
            except ValueError:
                # Pool cannot safely fill this output — partial fill to target tick
                sqrt_ratio_next = sqrt_ratio_target

    # Price-impact guard: reject steps that move price more than 90% in one step
    MAX_PRICE_RATIO = Decimal("10")
    MIN_PRICE_RATIO = Decimal("0.1")
    if sqrt_ratio_current > 0:
        ratio = sqrt_ratio_next / sqrt_ratio_current
        if ratio > MAX_PRICE_RATIO or ratio < MIN_PRICE_RATIO:
            raise ValueError(
                f"Price impact too large: sqrt_ratio moved by {ratio:.4f}x "
                f"(current={sqrt_ratio_current}, next={sqrt_ratio_next})"
            )

    # Did we reach the target price?
    max_reached = sqrt_ratio_target == sqrt_ratio_next

    # Calculate actual input/output amounts
    if zero_for_one:
        if not (max_reached and exact_input):
            amount_in = get_amount0_delta(sqrt_ratio_next, sqrt_ratio_current, liquidity, True)
        if not (max_reached and not exact_input):
            amount_out = get_amount1_delta(sqrt_ratio_next, sqrt_ratio_current, liquidity, False)
    else:
        if not (max_reached and exact_input):
            amount_in = get_amount1_delta(sqrt_ratio_current, sqrt_ratio_next, liquidity, True)
        if not (max_reached and not exact_input):
            amount_out = get_amount0_delta(sqrt_ratio_current, sqrt_ratio_next, liquidity, False)

    # Cap output for exactOutput mode
    if not exact_input and amount_out > abs(amount_remaining):
        amount_out = abs(amount_remaining)

    # Calculate fee
    if exact_input and sqrt_ratio_next != sqrt_ratio_target:
        # Didn't reach target: remaining input is all fee
        fee_amount = amount_remaining - amount_in
    else:
        # feeAmount = amountIn * feePips / (1e6 - feePips)
        fee_amount = (amount_in * fee_rate / (FEE_DENOMINATOR - fee_rate)).quantize(
            Decimal("0.00000001"), rounding=ROUND_UP
        )

    return SwapStepResult(
        sqrt_ratio_next=sqrt_ratio_next,
        amount_in=amount_in,
        amount_out=amount_out,
        fee_amount=fee_amount,
    )
