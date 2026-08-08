"""
Token Launchpad — Pump.fun style one-click token creation.

1. Create Token record
2. Mint total_supply to creator's balance
3. Create V3 pool (TOKEN/USDT)
4. Auto-add concentrated liquidity in a wide range around initial_price
5. Deduct USDT and tokens from creator
"""
import math
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token import Token
from app.models.balance import Balance

from .tick_math import get_sqrt_ratio_at_tick, get_tick_at_sqrt_ratio
from .pool_manager import create_pool, mint, _get_or_create_balance, _order_tokens

# Oracle-priced assets — reserved so a launchpad token can never share a
# balances.currency value with them (see 7c1a9e2b3f4d migration: that column
# is a free-text varchar, so a colliding symbol would let self-minted supply
# be cashed out at the real oracle price via spot trading).
RESERVED_SYMBOLS = {"USDT", "ETH", "BTC", "SOL"}


async def create_token(
    db: AsyncSession,
    creator_id: UUID,
    symbol: str,
    name: str,
    total_supply: Decimal,
    initial_price: Decimal,
    initial_liquidity_usdt: Decimal,
    fee_tier: int = 3000,
) -> dict:
    """
    One-click token launch (Pump.fun style).

    Args:
        symbol: token ticker (e.g. "MOON")
        name: full name (e.g. "Moon Coin")
        total_supply: total tokens to mint
        initial_price: starting price in USDT per token
        initial_liquidity_usdt: USDT to seed the pool
        fee_tier: V3 fee tier (default 0.3%)
    """
    symbol = symbol.upper()

    # Validate
    if symbol in RESERVED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Symbol {symbol} is reserved for oracle-priced assets")
    if total_supply <= 0:
        raise HTTPException(status_code=400, detail="total_supply must be positive")
    if initial_price <= 0:
        raise HTTPException(status_code=400, detail="initial_price must be positive")
    if initial_liquidity_usdt <= 0:
        raise HTTPException(status_code=400, detail="initial_liquidity_usdt must be positive")

    # Check symbol not taken
    existing = await db.execute(select(Token).where(Token.symbol == symbol))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Token {symbol} already exists")

    # Check creator has enough USDT
    usdt_bal = await _get_or_create_balance(db, creator_id, "USDT")
    if usdt_bal.available < initial_liquidity_usdt:
        raise HTTPException(status_code=400, detail=f"Insufficient USDT: need {initial_liquidity_usdt}, have {usdt_bal.available}")

    # 1. Create token record
    token = Token(
        symbol=symbol,
        name=name,
        total_supply=total_supply,
        creator_id=creator_id,
    )
    db.add(token)
    await db.flush()

    # 2. Mint tokens to creator's balance
    token_bal = await _get_or_create_balance(db, creator_id, symbol)
    token_bal.available += total_supply

    # 3. Calculate initial pool parameters
    # Order tokens alphabetically
    t0, t1 = _order_tokens(symbol, "USDT")

    # Calculate √price
    # If token0 = SYMBOL, token1 = USDT: price = USDT/SYMBOL = initial_price
    #   → √price = √(initial_price)
    # If token0 = USDT, token1 = SYMBOL: price = SYMBOL/USDT = 1/initial_price
    #   → √price = √(1/initial_price)
    if t0 == symbol:
        # token0 = SYMBOL, token1 = USDT
        # price = reserve1/reserve0 = USDT per SYMBOL
        sqrt_price = Decimal(str(math.sqrt(float(initial_price))))
    else:
        # token0 = USDT, token1 = SYMBOL
        # price = reserve1/reserve0 = SYMBOL per USDT = 1/initial_price
        sqrt_price = Decimal(str(math.sqrt(1.0 / float(initial_price))))

    # 4. Create the pool
    pool = await create_pool(db, t0, t1, fee_tier, sqrt_price)

    # 5. Calculate liquidity for initial seeding
    # Tokens to seed = initial_liquidity_usdt / initial_price
    tokens_for_liquidity = initial_liquidity_usdt / initial_price

    if tokens_for_liquidity > total_supply * Decimal("0.5"):
        tokens_for_liquidity = total_supply * Decimal("0.5")

    # Wide range: ±200% around initial price (covers most pump scenarios)
    initial_tick = get_tick_at_sqrt_ratio(sqrt_price)
    from .pool_manager import FEE_TIER_TO_TICK_SPACING
    tick_spacing = FEE_TIER_TO_TICK_SPACING[fee_tier]

    # Range: ~5x price range in each direction
    tick_range = int(math.log(5) / math.log(1.0001))  # ~16094 ticks ≈ 5x price
    tick_lower = ((initial_tick - tick_range) // tick_spacing) * tick_spacing
    tick_upper = ((initial_tick + tick_range) // tick_spacing + 1) * tick_spacing

    # Clamp
    tick_lower = max(-887272, tick_lower)
    tick_upper = min(887272, tick_upper)

    # Calculate liquidity from the token amounts we want to deploy
    # L = ΔY / (√p_current - √p_lower)  [from token1 side]
    sqrt_lower = get_sqrt_ratio_at_tick(tick_lower)
    sqrt_upper = get_sqrt_ratio_at_tick(tick_upper)

    # Use USDT amount to derive L
    if t0 == symbol:
        # token1 = USDT
        L = initial_liquidity_usdt / (sqrt_price - sqrt_lower)
    else:
        # token0 = USDT
        L = initial_liquidity_usdt / (Decimal("1") / sqrt_lower - Decimal("1") / sqrt_upper) / sqrt_price
        # Simplified: use token0 side
        L = initial_liquidity_usdt * sqrt_price * sqrt_lower / (sqrt_price - sqrt_lower)

    if L <= 0:
        raise HTTPException(status_code=400, detail="Cannot calculate valid liquidity amount")

    # 6. Add liquidity
    mint_result = await mint(db, pool.id, creator_id, tick_lower, tick_upper, L)

    return {
        "token": {
            "symbol": symbol,
            "name": name,
            "total_supply": str(total_supply),
            "creator_id": str(creator_id),
        },
        "pool": {
            "pool_id": str(pool.id),
            "token0": t0,
            "token1": t1,
            "fee": fee_tier,
            "initial_price": str(initial_price),
            "sqrt_price": str(sqrt_price),
            "tick": initial_tick,
        },
        "liquidity": mint_result,
    }
