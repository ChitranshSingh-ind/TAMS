"""update test results and tests models

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-15 21:07:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('test_results', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_absent', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.alter_column('marks', existing_type=sa.Integer(), type_=sa.Float(), nullable=False)
        batch_op.create_unique_constraint('uq_test_results_test_student', ['test_id', 'student_id'])

    with op.batch_alter_table('tests', schema=None) as batch_op:
        batch_op.alter_column('max_marks', existing_type=sa.Integer(), type_=sa.Float(), nullable=False)


def downgrade():
    with op.batch_alter_table('tests', schema=None) as batch_op:
        batch_op.alter_column('max_marks', existing_type=sa.Float(), type_=sa.Integer(), nullable=False)

    with op.batch_alter_table('test_results', schema=None) as batch_op:
        batch_op.drop_constraint('uq_test_results_test_student', type_='unique')
        batch_op.alter_column('marks', existing_type=sa.Float(), type_=sa.Integer(), nullable=False)
        batch_op.drop_column('is_absent')
