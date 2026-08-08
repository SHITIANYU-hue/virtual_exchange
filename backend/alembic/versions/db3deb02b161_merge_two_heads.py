"""merge two heads

Revision ID: db3deb02b161
Revises: 2628d089ba20, c4d7f2a19e35
Create Date: 2026-07-07 12:31:53.511989

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'db3deb02b161'
down_revision: Union[str, None] = ('2628d089ba20', 'c4d7f2a19e35')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
