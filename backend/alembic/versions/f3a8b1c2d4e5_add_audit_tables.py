"""add audit event and summary tables

Revision ID: f3a8b1c2d4e5
Revises: db3deb02b161
Create Date: 2026-07-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a8b1c2d4e5'
down_revision: Union[str, None] = 'db3deb02b161'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from sqlalchemy import inspect as sa_inspect

    conn = op.get_bind()
    if 'audit_events' in sa_inspect(conn).get_table_names():
        return  # already created

    op.create_table(
        'audit_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('experiment_id', sa.String(length=100), nullable=True),
        sa.Column('cycle_number', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.UUID(), nullable=False),
        sa.Column('agent_name', sa.String(length=50), nullable=False),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('action_details', sa.JSON(), nullable=True),
        sa.Column('verdict', sa.String(length=20), nullable=False),
        sa.Column('threat_score', sa.Float(), nullable=False),
        sa.Column('threat_category', sa.String(length=50), nullable=True),
        sa.Column('rule_score', sa.Float(), nullable=False),
        sa.Column('stat_score', sa.Float(), nullable=False),
        sa.Column('llm_score', sa.Float(), nullable=True),
        sa.Column('triggered_rules', sa.JSON(), nullable=True),
        sa.Column('anomalies', sa.JSON(), nullable=True),
        sa.Column('llm_reasoning', sa.Text(), nullable=True),
        sa.Column('agent_reasoning', sa.JSON(), nullable=True),
        sa.Column('market_state', sa.JSON(), nullable=True),
        sa.Column('cache_hit', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_audit_events_experiment_id', 'audit_events', ['experiment_id'])
    op.create_index('ix_audit_events_cycle_number', 'audit_events', ['cycle_number'])
    op.create_index('ix_audit_events_action_type', 'audit_events', ['action_type'])
    op.create_index('ix_audit_events_verdict', 'audit_events', ['verdict'])
    op.create_index('ix_audit_events_created_at', 'audit_events', ['created_at'])

    op.create_table(
        'audit_summaries',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('experiment_id', sa.String(length=100), nullable=False),
        sa.Column('agent_id', sa.UUID(), nullable=False),
        sa.Column('agent_name', sa.String(length=50), nullable=False),
        sa.Column('total_actions', sa.Integer(), nullable=True),
        sa.Column('flagged_count', sa.Integer(), nullable=True),
        sa.Column('blocked_count', sa.Integer(), nullable=True),
        sa.Column('avg_threat_score', sa.Float(), nullable=True),
        sa.Column('max_threat_score', sa.Float(), nullable=True),
        sa.Column('dominant_threat_category', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_audit_summaries_experiment_id', 'audit_summaries', ['experiment_id'])


def downgrade() -> None:
    op.drop_table('audit_summaries')
    op.drop_table('audit_events')
