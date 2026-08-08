from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.admin import (
    HardResetRequest,
    HardResetResponse,
    ReplayAdvanceRequest,
    ReplayAdvanceResponse,
)
from app.services.price_engine import replay_advance, reset_replay_source

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/hard-reset", response_model=HardResetResponse)
async def hard_reset(data: HardResetRequest, db: AsyncSession = Depends(get_db)):
    if not data.confirm:
        raise HTTPException(status_code=400, detail="Must set confirm=true to hard-reset the database")

    await db.execute(text(
        "TRUNCATE TABLE users, pools_v3, liquidity_pools, liquidity_provisions "
        "RESTART IDENTITY CASCADE"
    ))

    # In replay mode, a hard-reset should also restart the historical clock at
    # turn 0 and clear price_history — otherwise a fresh --world run inherits
    # a stale in-memory turn counter and leftover price rows from whatever ran
    # before it. No-op in live mode (price_history stays preserved there).
    await reset_replay_source()

    return HardResetResponse(
        status="ok",
        message=(
            "Wiped users, balances, spot_orders, positions, positions_v3, tokens, "
            "trades, messages, tick_data, tick_bitmap, pools_v3, liquidity_pools, "
            "liquidity_provisions. price_history preserved."
        ),
    )


@router.post("/replay/advance", response_model=ReplayAdvanceResponse)
async def advance_replay(data: ReplayAdvanceRequest):
    """Advance the historical replay price source by one hour.

    Response deliberately contains only a turn number and prices — never the
    world label, scenario name, or real historical date (see the design doc's
    leak checklist). Only callable when the backend was started with
    PRICE_MODE=replay.
    """
    if settings.price_mode != "replay":
        raise HTTPException(status_code=409, detail="Backend is not running in replay price mode")
    try:
        result = await replay_advance(data.turn)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ReplayAdvanceResponse(
        turn=result["turn"],
        prices={pair: str(price) for pair, price in result["prices"].items()},
    )
