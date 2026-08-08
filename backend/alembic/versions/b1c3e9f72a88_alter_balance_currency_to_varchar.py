"""alter balance currency to varchar

Revision ID: b1c3e9f72a88
Revises: 422999a4daed
Create Date: 2026-06-17 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b1c3e9f72a88'
down_revision: Union[str, None] = '422999a4daed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'balances',
        'currency',
        type_=sa.String(length=20),
        existing_type=sa.Enum('USDT', 'ETH', 'SOL', 'BTC', name='currency'),
        postgresql_using='currency::text',
    )
    op.execute('DROP TYPE IF EXISTS currency')


def downgrade() -> None:
    op.execute("CREATE TYPE currency AS ENUM ('USDT', 'ETH', 'SOL', 'BTC')")
    op.alter_column(
        'balances',
        'currency',
        type_=sa.Enum('USDT', 'ETH', 'SOL', 'BTC', name='currency'),
        existing_type=sa.String(length=20),
        postgresql_using='currency::currency',
    )
