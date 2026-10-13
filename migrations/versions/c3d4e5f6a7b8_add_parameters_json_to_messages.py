"""add_parameters_json_to_messages

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-12 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.add_column(sa.Column("parameters_json", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.drop_column("parameters_json")
