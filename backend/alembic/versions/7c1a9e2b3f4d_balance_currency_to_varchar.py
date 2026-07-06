"""balance currency column to varchar for dynamic tokens

Revision ID: 7c1a9e2b3f4d
Revises: 422999a4daed
Create Date: 2026-07-06 06:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c1a9e2b3f4d'
down_revision: Union[str, None] = '422999a4daed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'balances',
        'currency',
        existing_type=sa.Enum('USDT', 'ETH', 'SOL', 'BTC', name='currency'),
        type_=sa.String(length=20),
        postgresql_using='currency::text',
    )
    op.execute('DROP TYPE currency')


def downgrade() -> None:
    currency_enum = sa.Enum('USDT', 'ETH', 'SOL', 'BTC', name='currency')
    currency_enum.create(op.get_bind())
    op.alter_column(
        'balances',
        'currency',
        existing_type=sa.String(length=20),
        type_=currency_enum,
        postgresql_using='currency::currency',
    )
