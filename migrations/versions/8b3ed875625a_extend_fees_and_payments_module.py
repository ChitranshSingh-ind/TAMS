"""extend_fees_and_payments_module

Revision ID: 8b3ed875625a
Revises: bf1422c6d8e0
Create Date: 2026-10-10 15:40:00.016345

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b3ed875625a'
down_revision: Union[str, Sequence[str], None] = 'bf1422c6d8e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        'uq_fee_student_academic_month',
        'fees',
        ['student_id', 'academic_year', 'fee_month'],
        unique=True,
    )
    op.add_column(
        'fee_payments',
        sa.Column('is_reversed', sa.Boolean(), nullable=False, server_default=sa.text('0')),
    )
    op.add_column(
        'fee_payments',
        sa.Column('reversal_reason', sa.String(length=500), nullable=True),
    )
    op.add_column(
        'fee_payments',
        sa.Column('reversed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'students',
        sa.Column('monthly_fee', sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.add_column(
        'batches',
        sa.Column('monthly_fee', sa.Numeric(precision=10, scale=2), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('batches', 'monthly_fee')
    op.drop_column('students', 'monthly_fee')
    op.drop_column('fee_payments', 'reversed_at')
    op.drop_column('fee_payments', 'reversal_reason')
    op.drop_column('fee_payments', 'is_reversed')
    op.drop_index('uq_fee_student_academic_month', table_name='fees')
