"""Add recurrence fields to transactions table

Revision ID: 20261105_01
Revises: 20261019_02
Create Date: 2026-11-05

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20261105_01"
down_revision: str | None = "20261019_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade():
    op.add_column('transactions', sa.Column('recurrence_type', sa.String(20), nullable=True))
    op.add_column('transactions', sa.Column('recurrence_interval', sa.BigInteger(), nullable=True))
    op.add_column('transactions', sa.Column('recurrence_count', sa.BigInteger(), nullable=True))
    op.add_column('transactions', sa.Column('recurrence_end_date', sa.Date(), nullable=True))
    op.add_column('transactions', sa.Column('parent_transaction_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_transactions_parent_transaction_id',
        'transactions',
        'transactions',
        ['parent_transaction_id'],
        ['id'],
        ondelete='CASCADE'
    )
    op.add_column('transactions', sa.Column('installment_number', sa.BigInteger(), nullable=True))
    op.add_column('transactions', sa.Column('total_installments', sa.BigInteger(), nullable=True))


def downgrade():
    op.drop_column('transactions', 'total_installments')
    op.drop_column('transactions', 'installment_number')
    op.drop_constraint('fk_transactions_parent_transaction_id', 'transactions', type_='foreignkey')
    op.drop_column('transactions', 'parent_transaction_id')
    op.drop_column('transactions', 'recurrence_end_date')
    op.drop_column('transactions', 'recurrence_count')
    op.drop_column('transactions', 'recurrence_interval')
    op.drop_column('transactions', 'recurrence_type')
