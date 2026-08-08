from typing import Optional
from uuid import UUID

from pydantic import BaseModel


# Token Launchpad
class CreateTokenRequest(BaseModel):
    symbol: str
    name: str
    total_supply: float
    initial_price: float       # USDT per token
    initial_liquidity_usdt: float
    fee_tier: int = 3000       # 0.3% default


# V3 Pool Operations
class AddLiquidityRequest(BaseModel):
    pool_id: UUID
    # Required with `liquidity`. Optional with `amount_usdt` -- omit both to
    # get a safe range computed automatically below the current price.
    tick_lower: Optional[int] = None
    tick_upper: Optional[int] = None
    liquidity: Optional[float] = None
    amount_usdt: Optional[float] = None    # alternative to `liquidity`, for ranges below the current price


class RemoveLiquidityRequest(BaseModel):
    position_id: UUID
    liquidity: float


class CollectFeesRequest(BaseModel):
    position_id: UUID


class SwapV3Request(BaseModel):
    pool_id: UUID
    zero_for_one: bool
    amount: float              # positive = exactInput, negative = exactOutput
    sqrt_price_limit: Optional[float] = None


# Responses
class PoolV3Response(BaseModel):
    pool_id: str
    token0: str
    token1: str
    fee: int
    tick_spacing: int
    sqrt_price: str
    tick: int
    liquidity: str
    price: str                 # human-readable price (sqrt_price²)


class PositionV3Response(BaseModel):
    position_id: str
    pool_id: str
    owner_id: str
    tick_lower: int
    tick_upper: int
    liquidity: str
    tokens_owed_0: str
    tokens_owed_1: str


class TokenResponse(BaseModel):
    symbol: str
    name: str
    total_supply: str
    creator_id: str
