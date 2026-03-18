"""
Pool Manager — orchestrates all V3 pool operations.

This is the equivalent of UniswapV3Pool.sol, adapted for our
async SQLAlchemy backend. Coordinates:
  - create_pool: initialize a new V3 pool
  - mint: add concentrated liquidity [tickLower, tickUpper]
  - burn: remove liquidity from a position
  - collect: claim accrued fees
  - swap: execute a swap with full cross-tick loop
"""
import math
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.balance import Balance
from app.models.pool_v3 import PoolV3, TickData, TickBitmapWord, PositionV3, FEE_TIER_TO_TICK_SPACING
from app.models.trade import Trade, TradeType

from .tick_math import get_sqrt_ratio_at_tick, get_tick_at_sqrt_ratio, MIN_TICK, MAX_TICK
from .sqrt_price_math import get_amount0_delta, get_amount1_delta
from .swap_math import compute_swap_step
from .tick_bitmap import TickBitmapManager
from .position_lib import TickInfo, PositionInfo, update_tick, cross_tick, get_fee_growth_inside, update_position


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _order_tokens(token_a: str, token_b: str) -> tuple[str, str]:
    """Alphabetically order tokens (V3 convention: token0 < token1)."""
    return (token_a, token_b) if token_a < token_b else (token_b, token_a)


async def _get_or_create_balance(db: AsyncSession, user_id: UUID, currency: str) -> Balance:
    result = await db.execute(
        select(Balance).where(Balance.user_id == user_id, Balance.currency == currency)
    )
    bal = result.scalar_one_or_none()
    if not bal:
        bal = Balance(user_id=user_id, currency=currency, available=Decimal("0"), locked=Decimal("0"))
        db.add(bal)
        await db.flush()
    return bal


async def _get_pool_by_id_or_pair(db: AsyncSession, pool_identifier: str, fee_tier: int = 3000) -> PoolV3:
    """
    Look up a pool by either UUID or token pair name.

    Args:
        pool_identifier: Either a UUID string or a pair like "MOON/USDT" or "ETHUSDT"
        fee_tier: Fee tier to use when looking up by pair name (default 3000 = 0.3%)

    Returns:
        PoolV3 object

    Raises:
        HTTPException 400 if identifier format is invalid
        HTTPException 404 if pool not found
    """
    # Try parsing as UUID first
    try:
        pool_id = UUID(pool_identifier)
        pool = await db.get(PoolV3, pool_id)
        if not pool:
            raise HTTPException(status_code=404, detail=f"Pool with ID {pool_id} not found")
        return pool
    except ValueError:
        # Not a valid UUID, try parsing as token pair
        pass

    # Parse as token pair (e.g., "MOON/USDT" or "ETHUSDT")
    if "/" in pool_identifier:
        tokens = pool_identifier.split("/")
        if len(tokens) != 2:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid pool identifier: '{pool_identifier}'. Expected UUID or 'TOKEN0/TOKEN1' format"
            )
        token_a, token_b = tokens[0].strip(), tokens[1].strip()
    else:
        # Try to split concatenated pair like "ETHUSDT"
        # Common base currencies
        bases = ["USDT", "USDC", "ETH", "BTC", "SOL"]
        token_a, token_b = None, None
        for base in bases:
            if pool_identifier.endswith(base):
                token_a = pool_identifier[:-len(base)]
                token_b = base
                break

        if not token_a or not token_b:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid pool identifier: '{pool_identifier}'. Expected UUID or 'TOKEN0/TOKEN1' format"
            )

    # Order tokens alphabetically (V3 convention)
    token0, token1 = _order_tokens(token_a, token_b)

    # Look up pool by token pair and fee tier
    result = await db.execute(
        select(PoolV3).where(
            PoolV3.token0 == token0,
            PoolV3.token1 == token1,
            PoolV3.fee == fee_tier
        )
    )
    pool = result.scalar_one_or_none()

    if not pool:
        raise HTTPException(
            status_code=404,
            detail=f"Pool {token0}/{token1} with fee tier {fee_tier} not found"
        )

    return pool


async def _get_tick_info(db: AsyncSession, pool_id: UUID, tick_index: int) -> tuple[TickData, TickInfo]:
    """Load tick from DB or create empty TickInfo."""
    result = await db.execute(
        select(TickData).where(TickData.pool_id == pool_id, TickData.tick_index == tick_index)
    )
    td = result.scalar_one_or_none()
    if td:
        ti = TickInfo(
            liquidity_gross=td.liquidity_gross,
            liquidity_net=td.liquidity_net,
            fee_growth_outside_0=td.fee_growth_outside_0,
            fee_growth_outside_1=td.fee_growth_outside_1,
            initialized=td.initialized,
        )
        return td, ti
    else:
        td = TickData(pool_id=pool_id, tick_index=tick_index)
        db.add(td)
        await db.flush()
        return td, TickInfo()


def _save_tick_info(td: TickData, ti: TickInfo):
    """Write TickInfo back to TickData model."""
    td.liquidity_gross = ti.liquidity_gross
    td.liquidity_net = ti.liquidity_net
    td.fee_growth_outside_0 = ti.fee_growth_outside_0
    td.fee_growth_outside_1 = ti.fee_growth_outside_1
    td.initialized = ti.initialized


async def _load_tick_bitmap(db: AsyncSession, pool_id: UUID, tick_spacing: int) -> TickBitmapManager:
    """Load full tick bitmap from DB."""
    result = await db.execute(
        select(TickBitmapWord).where(TickBitmapWord.pool_id == pool_id)
    )
    rows = result.scalars().all()
    data = {row.word_pos: row.bitmap for row in rows}
    return TickBitmapManager.from_dict(tick_spacing, data)


async def _save_tick_bitmap(db: AsyncSession, pool_id: UUID, bm: TickBitmapManager):
    """Persist tick bitmap changes to DB."""
    serialized = bm.to_dict()
    for word_pos, bitmap_hex in serialized.items():
        result = await db.execute(
            select(TickBitmapWord).where(
                TickBitmapWord.pool_id == pool_id,
                TickBitmapWord.word_pos == word_pos,
            )
        )
        row = result.scalar_one_or_none()
        if row:
            row.bitmap = bitmap_hex
        else:
            db.add(TickBitmapWord(pool_id=pool_id, word_pos=word_pos, bitmap=bitmap_hex))


# ---------------------------------------------------------------------------
# create_pool
# ---------------------------------------------------------------------------

async def create_pool(
    db: AsyncSession,
    token0: str,
    token1: str,
    fee: int,
    initial_sqrt_price: Decimal,
) -> PoolV3:
    """
    Create a new V3 pool.

    Args:
        token0, token1: token symbols (will be reordered alphabetically)
        fee: fee tier (500, 3000, or 10000)
        initial_sqrt_price: starting √price

    Corresponds to: UniswapV3Factory.createPool + pool.initialize
    """
    if fee not in FEE_TIER_TO_TICK_SPACING:
        raise HTTPException(status_code=400, detail=f"Invalid fee tier: {fee}. Must be one of {list(FEE_TIER_TO_TICK_SPACING.keys())}")

    t0, t1 = _order_tokens(token0, token1)
    tick_spacing = FEE_TIER_TO_TICK_SPACING[fee]
    initial_tick = get_tick_at_sqrt_ratio(initial_sqrt_price)

    # Check pool doesn't already exist
    existing = await db.execute(
        select(PoolV3).where(PoolV3.token0 == t0, PoolV3.token1 == t1, PoolV3.fee == fee)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Pool {t0}/{t1} fee={fee} already exists")

    pool = PoolV3(
        token0=t0,
        token1=t1,
        fee=fee,
        tick_spacing=tick_spacing,
        sqrt_price=initial_sqrt_price,
        tick=initial_tick,
        liquidity=Decimal("0"),
    )
    db.add(pool)
    await db.flush()
    return pool


# ---------------------------------------------------------------------------
# mint (add liquidity)
# ---------------------------------------------------------------------------

async def mint(
    db: AsyncSession,
    pool_id: UUID | str,
    owner_id: UUID,
    tick_lower: int,
    tick_upper: int,
    liquidity_amount: Decimal,
) -> dict:
    """
    Add concentrated liquidity to a position.

    Corresponds to: UniswapV3Pool.mint
    """
    # Support both UUID and token pair identifiers (e.g., "MOON/USDT" or "ETHUSDT")
    pool = await _get_pool_by_id_or_pair(db, str(pool_id) if isinstance(pool_id, UUID) else pool_id)

    if tick_lower >= tick_upper:
        raise HTTPException(status_code=400, detail="tickLower must be < tickUpper")
    if tick_lower < MIN_TICK or tick_upper > MAX_TICK:
        raise HTTPException(status_code=400, detail="Tick out of range")
    if tick_lower % pool.tick_spacing != 0 or tick_upper % pool.tick_spacing != 0:
        raise HTTPException(status_code=400, detail=f"Ticks must be aligned to tickSpacing={pool.tick_spacing}")
    if liquidity_amount <= 0:
        raise HTTPException(status_code=400, detail="Liquidity must be positive")

    # Calculate token amounts needed
    sqrt_price_lower = get_sqrt_ratio_at_tick(tick_lower)
    sqrt_price_upper = get_sqrt_ratio_at_tick(tick_upper)

    amount0 = Decimal("0")
    amount1 = Decimal("0")

    if pool.tick < tick_lower:
        # Current price below range: only token0 needed
        amount0 = get_amount0_delta(sqrt_price_lower, sqrt_price_upper, liquidity_amount, True)
    elif pool.tick < tick_upper:
        # Current price in range: both tokens needed
        amount0 = get_amount0_delta(pool.sqrt_price, sqrt_price_upper, liquidity_amount, True)
        amount1 = get_amount1_delta(sqrt_price_lower, pool.sqrt_price, liquidity_amount, True)
        # Update pool liquidity (position is in range)
        pool.liquidity += liquidity_amount
    else:
        # Current price above range: only token1 needed
        amount1 = get_amount1_delta(sqrt_price_lower, sqrt_price_upper, liquidity_amount, True)

    # Deduct tokens from owner
    if amount0 > 0:
        bal0 = await _get_or_create_balance(db, owner_id, pool.token0)
        if bal0.available < amount0:
            raise HTTPException(status_code=400, detail=f"Insufficient {pool.token0}: need {amount0}, have {bal0.available}")
        bal0.available -= amount0

    if amount1 > 0:
        bal1 = await _get_or_create_balance(db, owner_id, pool.token1)
        if bal1.available < amount1:
            raise HTTPException(status_code=400, detail=f"Insufficient {pool.token1}: need {amount1}, have {bal1.available}")
        bal1.available -= amount1

    # Update ticks
    bm = await _load_tick_bitmap(db, pool.id, pool.tick_spacing)

    td_lower, ti_lower = await _get_tick_info(db, pool.id, tick_lower)
    flipped_lower = update_tick(
        ti_lower, tick_lower, pool.tick, liquidity_amount,
        pool.fee_growth_global_0, pool.fee_growth_global_1, upper=False,
    )
    _save_tick_info(td_lower, ti_lower)
    if flipped_lower:
        bm.flip_tick(tick_lower)

    td_upper, ti_upper = await _get_tick_info(db, pool.id, tick_upper)
    flipped_upper = update_tick(
        ti_upper, tick_upper, pool.tick, liquidity_amount,
        pool.fee_growth_global_0, pool.fee_growth_global_1, upper=True,
    )
    _save_tick_info(td_upper, ti_upper)
    if flipped_upper:
        bm.flip_tick(tick_upper)

    await _save_tick_bitmap(db, pool.id, bm)

    # Update or create position
    result = await db.execute(
        select(PositionV3).where(
            PositionV3.pool_id == pool.id,
            PositionV3.owner_id == owner_id,
            PositionV3.tick_lower == tick_lower,
            PositionV3.tick_upper == tick_upper,
        )
    )
    pos = result.scalar_one_or_none()

    fee_growth_inside_0, fee_growth_inside_1 = get_fee_growth_inside(
        ti_lower, ti_upper, tick_lower, tick_upper, pool.tick,
        pool.fee_growth_global_0, pool.fee_growth_global_1,
    )

    if pos:
        # Update existing position
        pi = PositionInfo(
            liquidity=pos.liquidity,
            fee_growth_inside_0_last=pos.fee_growth_inside_0_last,
            fee_growth_inside_1_last=pos.fee_growth_inside_1_last,
            tokens_owed_0=pos.tokens_owed_0,
            tokens_owed_1=pos.tokens_owed_1,
        )
        update_position(pi, liquidity_amount, fee_growth_inside_0, fee_growth_inside_1)
        pos.liquidity = pi.liquidity
        pos.fee_growth_inside_0_last = pi.fee_growth_inside_0_last
        pos.fee_growth_inside_1_last = pi.fee_growth_inside_1_last
        pos.tokens_owed_0 = pi.tokens_owed_0
        pos.tokens_owed_1 = pi.tokens_owed_1
    else:
        pos = PositionV3(
            pool_id=pool.id,
            owner_id=owner_id,
            tick_lower=tick_lower,
            tick_upper=tick_upper,
            liquidity=liquidity_amount,
            fee_growth_inside_0_last=fee_growth_inside_0,
            fee_growth_inside_1_last=fee_growth_inside_1,
        )
        db.add(pos)

    return {
        "position_id": str(pos.id) if pos.id else "new",
        "amount0": str(amount0),
        "amount1": str(amount1),
        "liquidity": str(liquidity_amount),
        "tick_lower": tick_lower,
        "tick_upper": tick_upper,
    }


# ---------------------------------------------------------------------------
# burn (remove liquidity)
# ---------------------------------------------------------------------------

async def burn(
    db: AsyncSession,
    position_id: UUID,
    liquidity_amount: Decimal,
) -> dict:
    """
    Remove liquidity from a position.

    Corresponds to: UniswapV3Pool.burn
    """
    pos = await db.get(PositionV3, position_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
    if liquidity_amount > pos.liquidity:
        raise HTTPException(status_code=400, detail="Cannot burn more than position liquidity")

    pool = await db.get(PoolV3, pos.pool_id)

    # Calculate token amounts to return
    sqrt_price_lower = get_sqrt_ratio_at_tick(pos.tick_lower)
    sqrt_price_upper = get_sqrt_ratio_at_tick(pos.tick_upper)

    amount0 = Decimal("0")
    amount1 = Decimal("0")

    if pool.tick < pos.tick_lower:
        amount0 = get_amount0_delta(sqrt_price_lower, sqrt_price_upper, liquidity_amount, False)
    elif pool.tick < pos.tick_upper:
        amount0 = get_amount0_delta(pool.sqrt_price, sqrt_price_upper, liquidity_amount, False)
        amount1 = get_amount1_delta(sqrt_price_lower, pool.sqrt_price, liquidity_amount, False)
        pool.liquidity -= liquidity_amount
    else:
        amount1 = get_amount1_delta(sqrt_price_lower, sqrt_price_upper, liquidity_amount, False)

    # Update ticks
    bm = await _load_tick_bitmap(db, pos.pool_id, pool.tick_spacing)
    neg_liq = -liquidity_amount

    td_lower, ti_lower = await _get_tick_info(db, pos.pool_id, pos.tick_lower)
    flipped_lower = update_tick(
        ti_lower, pos.tick_lower, pool.tick, neg_liq,
        pool.fee_growth_global_0, pool.fee_growth_global_1, upper=False,
    )
    _save_tick_info(td_lower, ti_lower)
    if flipped_lower:
        bm.flip_tick(pos.tick_lower)

    td_upper, ti_upper = await _get_tick_info(db, pos.pool_id, pos.tick_upper)
    flipped_upper = update_tick(
        ti_upper, pos.tick_upper, pool.tick, neg_liq,
        pool.fee_growth_global_0, pool.fee_growth_global_1, upper=True,
    )
    _save_tick_info(td_upper, ti_upper)
    if flipped_upper:
        bm.flip_tick(pos.tick_upper)

    await _save_tick_bitmap(db, pos.pool_id, bm)

    # Update position fees
    fee_growth_inside_0, fee_growth_inside_1 = get_fee_growth_inside(
        ti_lower, ti_upper, pos.tick_lower, pos.tick_upper, pool.tick,
        pool.fee_growth_global_0, pool.fee_growth_global_1,
    )

    pi = PositionInfo(
        liquidity=pos.liquidity,
        fee_growth_inside_0_last=pos.fee_growth_inside_0_last,
        fee_growth_inside_1_last=pos.fee_growth_inside_1_last,
        tokens_owed_0=pos.tokens_owed_0,
        tokens_owed_1=pos.tokens_owed_1,
    )
    update_position(pi, neg_liq, fee_growth_inside_0, fee_growth_inside_1)

    # Add burned amounts to tokens owed
    pi.tokens_owed_0 += amount0
    pi.tokens_owed_1 += amount1

    pos.liquidity = pi.liquidity
    pos.fee_growth_inside_0_last = pi.fee_growth_inside_0_last
    pos.fee_growth_inside_1_last = pi.fee_growth_inside_1_last
    pos.tokens_owed_0 = pi.tokens_owed_0
    pos.tokens_owed_1 = pi.tokens_owed_1

    return {"amount0": str(amount0), "amount1": str(amount1), "liquidity_burned": str(liquidity_amount)}


# ---------------------------------------------------------------------------
# collect (claim fees + burned tokens)
# ---------------------------------------------------------------------------

async def collect(db: AsyncSession, position_id: UUID, owner_id: UUID) -> dict:
    """
    Collect accrued fees and burned token amounts.

    Corresponds to: UniswapV3Pool.collect
    """
    pos = await db.get(PositionV3, position_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
    if pos.owner_id != owner_id:
        raise HTTPException(status_code=403, detail="Not position owner")

    pool = await db.get(PoolV3, pos.pool_id)

    amount0 = pos.tokens_owed_0
    amount1 = pos.tokens_owed_1

    if amount0 > 0:
        pos.tokens_owed_0 = Decimal("0")
        bal0 = await _get_or_create_balance(db, owner_id, pool.token0)
        bal0.available += amount0

    if amount1 > 0:
        pos.tokens_owed_1 = Decimal("0")
        bal1 = await _get_or_create_balance(db, owner_id, pool.token1)
        bal1.available += amount1

    return {"amount0_collected": str(amount0), "amount1_collected": str(amount1)}


# ---------------------------------------------------------------------------
# swap
# ---------------------------------------------------------------------------

async def swap(
    db: AsyncSession,
    user_id: UUID,
    pool_id: UUID | str,
    zero_for_one: bool,
    amount_specified: Decimal,
    sqrt_price_limit: Decimal | None = None,
) -> dict:
    """
    Execute a V3 swap with full cross-tick loop.

    Args:
        zero_for_one: True = sell token0 for token1, False = sell token1 for token0
        amount_specified: positive = exactInput, negative = exactOutput
        sqrt_price_limit: price limit for slippage control (optional)

    Corresponds to: UniswapV3Pool.swap
    """
    # Support both UUID and token pair identifiers (e.g., "MOON/USDT" or "ETHUSDT")
    pool = await _get_pool_by_id_or_pair(db, str(pool_id) if isinstance(pool_id, UUID) else pool_id)

    # Validate and set price limit
    if sqrt_price_limit is None or sqrt_price_limit == Decimal("0"):
        if zero_for_one:
            sqrt_price_limit = get_sqrt_ratio_at_tick(MIN_TICK + 1)
        else:
            sqrt_price_limit = get_sqrt_ratio_at_tick(MAX_TICK - 1)

    if zero_for_one:
        if sqrt_price_limit >= pool.sqrt_price or sqrt_price_limit <= get_sqrt_ratio_at_tick(MIN_TICK):
            raise HTTPException(status_code=400, detail="Invalid sqrtPriceLimit for zeroForOne")
    else:
        if sqrt_price_limit <= pool.sqrt_price or sqrt_price_limit >= get_sqrt_ratio_at_tick(MAX_TICK):
            raise HTTPException(status_code=400, detail="Invalid sqrtPriceLimit for oneForZero")

    exact_input = amount_specified > 0

    # Load tick bitmap
    bm = await _load_tick_bitmap(db, pool.id, pool.tick_spacing)

    # Initialize swap state
    amount_remaining = amount_specified
    amount_calculated = Decimal("0")
    sqrt_price = pool.sqrt_price
    tick = pool.tick
    liquidity = pool.liquidity
    fee_growth_global = pool.fee_growth_global_0 if zero_for_one else pool.fee_growth_global_1

    # Swap loop
    MAX_ITERATIONS = 100  # safety limit
    iterations = 0

    while amount_remaining != 0 and sqrt_price != sqrt_price_limit:
        iterations += 1
        if iterations > MAX_ITERATIONS:
            break

        # Find next initialized tick
        step_tick_next, step_initialized = bm.next_initialized_tick_within_one_word(
            tick, lte=zero_for_one
        )

        # Clamp to valid range
        step_tick_next = max(MIN_TICK, min(MAX_TICK, step_tick_next))

        # Get √price at next tick
        sqrt_price_next = get_sqrt_ratio_at_tick(step_tick_next)

        # Determine target price for this step
        if zero_for_one:
            sqrt_ratio_target = max(sqrt_price_next, sqrt_price_limit)
        else:
            sqrt_ratio_target = min(sqrt_price_next, sqrt_price_limit)

        # Compute swap step
        if liquidity == 0:
            # No liquidity — skip to next tick
            sqrt_price = sqrt_ratio_target
            if sqrt_price_next == sqrt_ratio_target:
                tick = step_tick_next - 1 if zero_for_one else step_tick_next
            else:
                tick = get_tick_at_sqrt_ratio(sqrt_price)
            continue

        step = compute_swap_step(sqrt_price, sqrt_ratio_target, liquidity, amount_remaining, pool.fee)

        # Update state
        sqrt_price = step.sqrt_ratio_next

        if exact_input:
            amount_remaining -= (step.amount_in + step.fee_amount)
            amount_calculated -= step.amount_out
        else:
            amount_remaining += step.amount_out
            amount_calculated += (step.amount_in + step.fee_amount)

        # Update fee growth global
        if liquidity > 0:
            fee_growth_global += step.fee_amount / liquidity

        # Cross tick if we reached it
        if sqrt_price == sqrt_price_next:
            if step_initialized:
                # Load tick and cross it
                td, ti = await _get_tick_info(db, pool.id, step_tick_next)
                liquidity_net = cross_tick(ti,
                    fee_growth_global if zero_for_one else pool.fee_growth_global_0,
                    pool.fee_growth_global_1 if zero_for_one else fee_growth_global,
                )
                _save_tick_info(td, ti)

                if zero_for_one:
                    liquidity_net = -liquidity_net
                liquidity += liquidity_net

            tick = step_tick_next - 1 if zero_for_one else step_tick_next
        else:
            tick = get_tick_at_sqrt_ratio(sqrt_price)

    # Calculate final amounts
    if zero_for_one == exact_input:
        amount0 = amount_specified - amount_remaining
        amount1 = amount_calculated
    else:
        amount0 = amount_calculated
        amount1 = amount_specified - amount_remaining

    # amount0 > 0 means user pays token0, < 0 means user receives token0
    # For zeroForOne exactInput: amount0 > 0 (user pays), amount1 < 0 (user receives)

    # Execute transfers
    input_token = pool.token0 if zero_for_one else pool.token1
    output_token = pool.token1 if zero_for_one else pool.token0
    input_amount = abs(amount0 if zero_for_one else amount1)
    output_amount = abs(amount1 if zero_for_one else amount0)

    # Deduct input
    input_bal = await _get_or_create_balance(db, user_id, input_token)
    if input_bal.available < input_amount:
        raise HTTPException(status_code=400, detail=f"Insufficient {input_token}: need {input_amount}, have {input_bal.available}")
    input_bal.available -= input_amount

    # Credit output
    output_bal = await _get_or_create_balance(db, user_id, output_token)
    output_bal.available += output_amount

    # Update pool state
    pool.sqrt_price = sqrt_price
    pool.tick = tick
    pool.liquidity = liquidity
    if zero_for_one:
        pool.fee_growth_global_0 = fee_growth_global
    else:
        pool.fee_growth_global_1 = fee_growth_global

    # Record trade
    price = output_amount / input_amount if input_amount > 0 else Decimal("0")
    trade = Trade(
        buyer_id=user_id,
        pair=f"{pool.token0}{pool.token1}",
        price=price,
        quantity=output_amount,
        trade_type=TradeType.amm_swap,
    )
    db.add(trade)

    return {
        "pool": f"{pool.token0}/{pool.token1}",
        "input_token": input_token,
        "output_token": output_token,
        "amount_in": str(input_amount),
        "amount_out": str(output_amount),
        "fee": str(input_amount * Decimal(pool.fee) / Decimal("1000000")),
        "sqrt_price_after": str(pool.sqrt_price),
        "tick_after": pool.tick,
        "price_after": str(pool.sqrt_price ** 2),
    }
