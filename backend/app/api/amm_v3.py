"""V3 AMM + Token Launchpad API routes."""
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.token import Token
from app.models.pool_v3 import PoolV3, PositionV3
from app.schemas.amm_v3 import (
    CreateTokenRequest, AddLiquidityRequest, RemoveLiquidityRequest,
    CollectFeesRequest, SwapV3Request,
    PoolV3Response, PositionV3Response, TokenResponse,
)
from app.services.amm_v3.token_launchpad import create_token
from app.services.amm_v3.pool_manager import mint, burn, collect, swap

router = APIRouter(tags=["v3"])


# ---------------------------------------------------------------------------
# Token Launchpad
# ---------------------------------------------------------------------------

@router.post("/api/token/create")
async def create_token_endpoint(
    data: CreateTokenRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await create_token(
        db, user.id, data.symbol, data.name,
        Decimal(str(data.total_supply)),
        Decimal(str(data.initial_price)),
        Decimal(str(data.initial_liquidity_usdt)),
        data.fee_tier,
    )
    return result


@router.get("/api/token/list", response_model=list[TokenResponse])
async def list_tokens(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Token))
    tokens = result.scalars().all()
    return [TokenResponse(
        symbol=t.symbol, name=t.name,
        total_supply=str(t.total_supply), creator_id=str(t.creator_id),
    ) for t in tokens]


# ---------------------------------------------------------------------------
# V3 Pool Operations
# ---------------------------------------------------------------------------

@router.post("/api/v3/add-liquidity")
async def add_liquidity(
    data: AddLiquidityRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await mint(
        db, data.pool_id, user.id,
        data.tick_lower, data.tick_upper,
        Decimal(str(data.liquidity)),
    )
    return result


@router.post("/api/v3/remove-liquidity")
async def remove_liquidity(
    data: RemoveLiquidityRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await burn(db, data.position_id, Decimal(str(data.liquidity)), owner_id=user.id)


@router.post("/api/v3/collect-fees")
async def collect_fees(
    data: CollectFeesRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await collect(db, data.position_id, user.id)


@router.post("/api/v3/swap")
async def swap_v3(
    data: SwapV3Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sqrt_limit = Decimal(str(data.sqrt_price_limit)) if data.sqrt_price_limit else None
    return await swap(
        db, user.id, data.pool_id,
        data.zero_for_one,
        Decimal(str(data.amount)),
        sqrt_limit,
    )


@router.get("/api/v3/pools", response_model=list[PoolV3Response])
async def list_pools(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PoolV3))
    pools = result.scalars().all()
    return [PoolV3Response(
        pool_id=str(p.id), token0=p.token0, token1=p.token1,
        fee=p.fee, tick_spacing=p.tick_spacing,
        sqrt_price=str(p.sqrt_price), tick=p.tick,
        liquidity=str(p.liquidity),
        price=str(p.sqrt_price ** 2),
    ) for p in pools]


@router.get("/api/v3/pools/{pool_id}", response_model=PoolV3Response)
async def get_pool(pool_id: str, db: AsyncSession = Depends(get_db)):
    pool = await db.get(PoolV3, pool_id)
    if not pool:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Pool not found")
    return PoolV3Response(
        pool_id=str(pool.id), token0=pool.token0, token1=pool.token1,
        fee=pool.fee, tick_spacing=pool.tick_spacing,
        sqrt_price=str(pool.sqrt_price), tick=pool.tick,
        liquidity=str(pool.liquidity),
        price=str(pool.sqrt_price ** 2),
    )


@router.get("/api/v3/positions", response_model=list[PositionV3Response])
async def list_positions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PositionV3).where(PositionV3.owner_id == user.id)
    )
    positions = result.scalars().all()
    return [PositionV3Response(
        position_id=str(p.id), pool_id=str(p.pool_id), owner_id=str(p.owner_id),
        tick_lower=p.tick_lower, tick_upper=p.tick_upper,
        liquidity=str(p.liquidity),
        tokens_owed_0=str(p.tokens_owed_0), tokens_owed_1=str(p.tokens_owed_1),
    ) for p in positions]
