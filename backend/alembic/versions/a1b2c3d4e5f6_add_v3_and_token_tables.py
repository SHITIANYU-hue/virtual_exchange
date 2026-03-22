"""add v3 and token tables

Revision ID: a1b2c3d4e5f6
Revises: 422999a4daed
Create Date: 2026-03-20 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '422999a4daed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Alter balances.currency from enum to VARCHAR(20) for dynamic tokens
    op.execute("ALTER TABLE balances ALTER COLUMN currency TYPE VARCHAR(20) USING currency::text")
    op.execute("DROP TYPE IF EXISTS currency")

    # Add unique constraint if it doesn't already exist
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE balances ADD CONSTRAINT uq_balance_user_currency UNIQUE (user_id, currency);
        EXCEPTION WHEN duplicate_table THEN NULL;
        END $$;
    """)

    # 2. Widen trades.pair from VARCHAR(20) to VARCHAR(40) for custom token pairs
    op.alter_column('trades', 'pair', type_=sa.String(length=40))

    # 3. Create tokens table
    op.create_table('tokens',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('total_supply', sa.Numeric(precision=30, scale=8), nullable=False),
        sa.Column('creator_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['creator_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('symbol'),
    )

    # 4. Create pools_v3 table
    op.create_table('pools_v3',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('token0', sa.String(length=20), nullable=False),
        sa.Column('token1', sa.String(length=20), nullable=False),
        sa.Column('fee', sa.Integer(), nullable=False),
        sa.Column('tick_spacing', sa.Integer(), nullable=False),
        sa.Column('sqrt_price', sa.Numeric(precision=40, scale=20), nullable=False),
        sa.Column('tick', sa.Integer(), nullable=False),
        sa.Column('liquidity', sa.Numeric(precision=40, scale=8), nullable=True),
        sa.Column('fee_growth_global_0', sa.Numeric(precision=40, scale=20), nullable=True),
        sa.Column('fee_growth_global_1', sa.Numeric(precision=40, scale=20), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token0', 'token1', 'fee', name='uq_pool_v3_pair_fee'),
    )

    # 5. Create tick_data table
    op.create_table('tick_data',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('pool_id', sa.UUID(), nullable=False),
        sa.Column('tick_index', sa.Integer(), nullable=False),
        sa.Column('liquidity_gross', sa.Numeric(precision=40, scale=8), nullable=True),
        sa.Column('liquidity_net', sa.Numeric(precision=40, scale=8), nullable=True),
        sa.Column('fee_growth_outside_0', sa.Numeric(precision=40, scale=20), nullable=True),
        sa.Column('fee_growth_outside_1', sa.Numeric(precision=40, scale=20), nullable=True),
        sa.Column('initialized', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['pool_id'], ['pools_v3.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pool_id', 'tick_index', name='uq_tick_data_pool_tick'),
    )

    # 6. Create tick_bitmap table
    op.create_table('tick_bitmap',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('pool_id', sa.UUID(), nullable=False),
        sa.Column('word_pos', sa.Integer(), nullable=False),
        sa.Column('bitmap', sa.String(length=66), nullable=True),
        sa.ForeignKeyConstraint(['pool_id'], ['pools_v3.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pool_id', 'word_pos', name='uq_tick_bitmap_pool_word'),
    )

    # 7. Create positions_v3 table
    op.create_table('positions_v3',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('pool_id', sa.UUID(), nullable=False),
        sa.Column('owner_id', sa.UUID(), nullable=False),
        sa.Column('tick_lower', sa.Integer(), nullable=False),
        sa.Column('tick_upper', sa.Integer(), nullable=False),
        sa.Column('liquidity', sa.Numeric(precision=40, scale=8), nullable=True),
        sa.Column('fee_growth_inside_0_last', sa.Numeric(precision=40, scale=20), nullable=True),
        sa.Column('fee_growth_inside_1_last', sa.Numeric(precision=40, scale=20), nullable=True),
        sa.Column('tokens_owed_0', sa.Numeric(precision=30, scale=8), nullable=True),
        sa.Column('tokens_owed_1', sa.Numeric(precision=30, scale=8), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id']),
        sa.ForeignKeyConstraint(['pool_id'], ['pools_v3.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pool_id', 'owner_id', 'tick_lower', 'tick_upper', name='uq_position_v3'),
    )


def downgrade() -> None:
    op.drop_table('positions_v3')
    op.drop_table('tick_bitmap')
    op.drop_table('tick_data')
    op.drop_table('pools_v3')
    op.drop_table('tokens')

    op.alter_column('trades', 'pair', type_=sa.String(length=20))

    op.execute("CREATE TYPE currency AS ENUM ('USDT', 'ETH', 'SOL', 'BTC')")
    op.execute("ALTER TABLE balances ALTER COLUMN currency TYPE currency USING currency::currency")
