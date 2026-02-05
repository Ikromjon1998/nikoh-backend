"""Add reports table

Revision ID: 002
Revises: 001
Create Date: 2026-02-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reported_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reporter_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reason', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['reported_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reporter_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for common queries
    op.create_index('ix_reports_status', 'reports', ['status'])
    op.create_index('ix_reports_reported_user_id', 'reports', ['reported_user_id'])
    op.create_index('ix_reports_reporter_user_id', 'reports', ['reporter_user_id'])
    op.create_index('ix_reports_created_at', 'reports', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_reports_created_at', table_name='reports')
    op.drop_index('ix_reports_reporter_user_id', table_name='reports')
    op.drop_index('ix_reports_reported_user_id', table_name='reports')
    op.drop_index('ix_reports_status', table_name='reports')
    op.drop_table('reports')
