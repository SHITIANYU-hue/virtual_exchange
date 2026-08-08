"""
Position Library — manages LP positions and fee calculations.

Handles:
- Position update (add/remove liquidity)
- Fee growth tracking (feeGrowthInside)
- Tokens owed calculation

Corresponds to: Position.sol and parts of UniswapV3Pool._updatePosition
"""
from decimal import Decimal
from dataclasses import dataclass, field


@dataclass
class PositionInfo:
    """Corresponds to Position.Info in Solidity."""
    liquidity: Decimal = Decimal("0")
    fee_growth_inside_0_last: Decimal = Decimal("0")
    fee_growth_inside_1_last: Decimal = Decimal("0")
    tokens_owed_0: Decimal = Decimal("0")
    tokens_owed_1: Decimal = Decimal("0")


@dataclass
class TickInfo:
    """Corresponds to Tick.Info in Solidity."""
    liquidity_gross: Decimal = Decimal("0")
    liquidity_net: Decimal = Decimal("0")
    fee_growth_outside_0: Decimal = Decimal("0")
    fee_growth_outside_1: Decimal = Decimal("0")
    initialized: bool = False


def update_tick(
    tick_info: TickInfo,
    tick: int,
    tick_current: int,
    liquidity_delta: Decimal,
    fee_growth_global_0: Decimal,
    fee_growth_global_1: Decimal,
    upper: bool,
    max_liquidity: Decimal = Decimal("2") ** 128 - 1,
) -> bool:
    """
    Update tick state when liquidity is added/removed.

    Returns: flipped (whether the tick transitioned from initialized ↔ uninitialized)

    Corresponds to: Tick.update in Solidity.
    """
    liquidity_gross_before = tick_info.liquidity_gross
    liquidity_gross_after = liquidity_gross_before + liquidity_delta

    if liquidity_gross_after > max_liquidity:
        raise ValueError(f"Liquidity overflow at tick {tick}")
    if liquidity_gross_after < 0:
        raise ValueError(f"Liquidity underflow at tick {tick}")

    flipped = (liquidity_gross_after == 0) != (liquidity_gross_before == 0)

    # Initialize tick if first time
    if liquidity_gross_before == 0:
        if tick <= tick_current:
            tick_info.fee_growth_outside_0 = fee_growth_global_0
            tick_info.fee_growth_outside_1 = fee_growth_global_1
        tick_info.initialized = True

    tick_info.liquidity_gross = liquidity_gross_after

    # Update liquidityNet
    if upper:
        tick_info.liquidity_net -= liquidity_delta
    else:
        tick_info.liquidity_net += liquidity_delta

    if liquidity_gross_after == 0:
        tick_info.initialized = False

    return flipped


def cross_tick(
    tick_info: TickInfo,
    fee_growth_global_0: Decimal,
    fee_growth_global_1: Decimal,
) -> Decimal:
    """
    Handle crossing an initialized tick during a swap.

    Updates feeGrowthOutside and returns liquidityNet.

    Corresponds to: Tick.cross in Solidity.
    """
    # Flip fee growth outside: f_o = f_g - f_o
    tick_info.fee_growth_outside_0 = fee_growth_global_0 - tick_info.fee_growth_outside_0
    tick_info.fee_growth_outside_1 = fee_growth_global_1 - tick_info.fee_growth_outside_1

    return tick_info.liquidity_net


def get_fee_growth_inside(
    tick_lower_info: TickInfo,
    tick_upper_info: TickInfo,
    tick_lower: int,
    tick_upper: int,
    tick_current: int,
    fee_growth_global_0: Decimal,
    fee_growth_global_1: Decimal,
) -> tuple[Decimal, Decimal]:
    """
    Calculate fee growth inside a position's tick range.

    fee_growth_inside = f_g - f_below(tickLower) - f_above(tickUpper)

    Where:
      f_below(i) = f_o(i) if i_c >= i, else f_g - f_o(i)
      f_above(i) = f_o(i) if i_c < i, else f_g - f_o(i)

    Corresponds to: Tick.getFeeGrowthInside in Solidity.
    """
    # Calculate fee growth below tickLower
    if tick_current >= tick_lower:
        fee_growth_below_0 = tick_lower_info.fee_growth_outside_0
        fee_growth_below_1 = tick_lower_info.fee_growth_outside_1
    else:
        fee_growth_below_0 = fee_growth_global_0 - tick_lower_info.fee_growth_outside_0
        fee_growth_below_1 = fee_growth_global_1 - tick_lower_info.fee_growth_outside_1

    # Calculate fee growth above tickUpper
    if tick_current < tick_upper:
        fee_growth_above_0 = tick_upper_info.fee_growth_outside_0
        fee_growth_above_1 = tick_upper_info.fee_growth_outside_1
    else:
        fee_growth_above_0 = fee_growth_global_0 - tick_upper_info.fee_growth_outside_0
        fee_growth_above_1 = fee_growth_global_1 - tick_upper_info.fee_growth_outside_1

    # fee_growth_inside = f_g - f_below - f_above
    fee_growth_inside_0 = fee_growth_global_0 - fee_growth_below_0 - fee_growth_above_0
    fee_growth_inside_1 = fee_growth_global_1 - fee_growth_below_1 - fee_growth_above_1

    return fee_growth_inside_0, fee_growth_inside_1


def update_position(
    position: PositionInfo,
    liquidity_delta: Decimal,
    fee_growth_inside_0: Decimal,
    fee_growth_inside_1: Decimal,
):
    """
    Update a position's state (liquidity and accrued fees).

    Calculates tokens owed from fee growth, then updates position.

    Corresponds to: UniswapV3Pool._updatePosition
    """
    # Calculate accrued fees since last update
    tokens_owed_0 = (fee_growth_inside_0 - position.fee_growth_inside_0_last) * position.liquidity
    tokens_owed_1 = (fee_growth_inside_1 - position.fee_growth_inside_1_last) * position.liquidity

    # Update position
    position.liquidity += liquidity_delta
    position.fee_growth_inside_0_last = fee_growth_inside_0
    position.fee_growth_inside_1_last = fee_growth_inside_1
    position.tokens_owed_0 += tokens_owed_0
    position.tokens_owed_1 += tokens_owed_1

    if position.liquidity < 0:
        raise ValueError("Position liquidity cannot be negative")
