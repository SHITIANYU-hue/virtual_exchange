import uuid
import enum
from decimal import Decimal

from sqlalchemy import String, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# Keep Currency enum for backwards compatibility with existing code
# But Balance.currency is now a free-form String to support dynamic tokens
class Currency(str, enum.Enum):
    USDT = "USDT"
    ETH = "ETH"
    SOL = "SOL"
    BTC = "BTC"

# Default currencies created for new users
DEFAULT_CURRENCIES = [Currency.USDT, Currency.ETH, Currency.SOL, Currency.BTC]


class Balance(Base):
    __tablename__ = "balances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    currency: Mapped[str] = mapped_column(String(20), nullable=False)  # was Enum, now String for dynamic tokens
    available: Mapped[Decimal] = mapped_column(Numeric(30, 8), default=Decimal("0"))
    locked: Mapped[Decimal] = mapped_column(Numeric(30, 8), default=Decimal("0"))

    user = relationship("User", back_populates="balances")

    __table_args__ = (
        UniqueConstraint("user_id", "currency", name="uq_balance_user_currency"),
    )
