"""Add indexes to refresh_tokens table for cleanup performance

Revision ID: 20261106_01
Revises: 20261105_01
Create Date: 2026-11-06

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20261106_01"
down_revision: str | None = "20261105_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade():
    op.create_index(
        'ix_refresh_tokens_expires_at',
        'refresh_tokens',
        ['expires_at']
    )
    op.create_index(
        'ix_refresh_tokens_is_revoked',
        'refresh_tokens',
        ['is_revoked']
    )


def downgrade():
    op.drop_index('ix_refresh_tokens_is_revoked', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_expires_at', table_name='refresh_tokens')
