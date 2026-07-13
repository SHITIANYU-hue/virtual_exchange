from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.admin import HardResetRequest, HardResetResponse

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/hard-reset", response_model=HardResetResponse)
async def hard_reset(data: HardResetRequest, db: AsyncSession = Depends(get_db)):
    if not data.confirm:
        raise HTTPException(status_code=400, detail="Must set confirm=true to hard-reset the database")

    await db.execute(text(
        "TRUNCATE TABLE users, pools_v3, liquidity_pools, liquidity_provisions "
        "RESTART IDENTITY CASCADE"
    ))

    return HardResetResponse(
        status="ok",
        message=(
            "Wiped users, balances, spot_orders, positions, positions_v3, tokens, "
            "trades, messages, tick_data, tick_bitmap, pools_v3, liquidity_pools, "
            "liquidity_provisions. price_history preserved."
        ),
    )
