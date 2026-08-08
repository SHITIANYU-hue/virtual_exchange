"""add discovered_patterns and discovery_runs tables

Revision ID: b7e4c1f9a2d3
Revises: f3a8b1c2d4e5
Create Date: 2026-07-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7e4c1f9a2d3'
down_revision: Union[str, None] = 'f3a8b1c2d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from sqlalchemy import inspect as sa_inspect

    conn = op.get_bind()
    if 'discovered_patterns' in sa_inspect(conn).get_table_names():
        return

    op.create_table(
        'discovered_patterns',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('experiment_id', sa.String(length=100), nullable=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('mechanism', sa.Text(), nullable=True),
        sa.Column('involved_agents', sa.JSON(), nullable=True),
        sa.Column('evidence', sa.JSON(), nullable=True),
        sa.Column('is_novel', sa.Boolean(), nullable=True),
        sa.Column('known_category', sa.String(length=50), nullable=True),
        sa.Column('occurrence_count', sa.Integer(), nullable=True),
        sa.Column('first_seen_cycle', sa.Integer(), nullable=True),
        sa.Column('proposed_rule', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_discovered_patterns_experiment_id', 'discovered_patterns', ['experiment_id'])

    op.create_table(
        'discovery_runs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('experiment_id', sa.String(length=100), nullable=True),
        sa.Column('cycle', sa.Integer(), nullable=False),
        sa.Column('window_start_cycle', sa.Integer(), nullable=False),
        sa.Column('patterns_found', sa.Integer(), nullable=True),
        sa.Column('novel_count', sa.Integer(), nullable=True),
        sa.Column('llm_reasoning', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_discovery_runs_experiment_id', 'discovery_runs', ['experiment_id'])


def downgrade() -> None:
    op.drop_table('discovery_runs')
    op.drop_table('discovered_patterns')
