import uuid
from decimal import Decimal

from sqlalchemy import String, Numeric, Integer, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# Fee tier configuration (same as Uniswap V3)
FEE_TIER_TO_TICK_SPACING = {
    500: 10,     # 0.05%
    3000: 60,    # 0.30%
    10000: 200,  # 1.00%
}


class PoolV3(Base):
    """Uniswap V3 concentrated liquidity pool."""
    __tablename__ = "pools_v3"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token0: Mapped[str] = mapped_column(String(20), nullable=False)  # base token (alphabetically first)
    token1: Mapped[str] = mapped_column(String(20), nullable=False)  # quote token
    fee: Mapped[int] = mapped_column(Integer, nullable=False)         # e.g. 3000 = 0.3%
    tick_spacing: Mapped[int] = mapped_column(Integer, nullable=False)

    # Current pool state (Slot0 equivalent)
    sqrt_price: Mapped[Decimal] = mapped_column(Numeric(40, 20), nullable=False)  # current √price
    tick: Mapped[int] = mapped_column(Integer, nullable=False)                      # current tick
    liquidity: Mapped[Decimal] = mapped_column(Numeric(40, 8), default=Decimal("0"))  # active liquidity (L)

    # Global fee accumulators (per unit of liquidity)
    fee_growth_global_0: Mapped[Decimal] = mapped_column(Numeric(40, 20), default=Decimal("0"))
    fee_growth_global_1: Mapped[Decimal] = mapped_column(Numeric(40, 20), default=Decimal("0"))

    __table_args__ = (
        UniqueConstraint("token0", "token1", "fee", name="uq_pool_v3_pair_fee"),
    )


class TickData(Base):
    """Per-tick state for a V3 pool."""
    __tablename__ = "tick_data"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pool_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pools_v3.id"), nullable=False)
    tick_index: Mapped[int] = mapped_column(Integer, nullable=False)

    liquidity_gross: Mapped[Decimal] = mapped_column(Numeric(40, 8), default=Decimal("0"))
    liquidity_net: Mapped[Decimal] = mapped_column(Numeric(40, 8), default=Decimal("0"))
    fee_growth_outside_0: Mapped[Decimal] = mapped_column(Numeric(40, 20), default=Decimal("0"))
    fee_growth_outside_1: Mapped[Decimal] = mapped_column(Numeric(40, 20), default=Decimal("0"))
    initialized: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("pool_id", "tick_index", name="uq_tick_data_pool_tick"),
    )


class TickBitmapWord(Base):
    """256-bit bitmap word for efficient tick search."""
    __tablename__ = "tick_bitmap"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pool_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pools_v3.id"), nullable=False)
    word_pos: Mapped[int] = mapped_column(Integer, nullable=False)
    bitmap: Mapped[str] = mapped_column(String(66), default="0x0")  # 256-bit as hex string

    __table_args__ = (
        UniqueConstraint("pool_id", "word_pos", name="uq_tick_bitmap_pool_word"),
    )


class PositionV3(Base):
    """LP position with concentrated liquidity range."""
    __tablename__ = "positions_v3"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pool_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pools_v3.id"), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    tick_lower: Mapped[int] = mapped_column(Integer, nullable=False)
    tick_upper: Mapped[int] = mapped_column(Integer, nullable=False)

    liquidity: Mapped[Decimal] = mapped_column(Numeric(40, 8), default=Decimal("0"))
    fee_growth_inside_0_last: Mapped[Decimal] = mapped_column(Numeric(40, 20), default=Decimal("0"))
    fee_growth_inside_1_last: Mapped[Decimal] = mapped_column(Numeric(40, 20), default=Decimal("0"))
    tokens_owed_0: Mapped[Decimal] = mapped_column(Numeric(30, 8), default=Decimal("0"))
    tokens_owed_1: Mapped[Decimal] = mapped_column(Numeric(30, 8), default=Decimal("0"))

    __table_args__ = (
        UniqueConstraint("pool_id", "owner_id", "tick_lower", "tick_upper", name="uq_position_v3"),
    )
