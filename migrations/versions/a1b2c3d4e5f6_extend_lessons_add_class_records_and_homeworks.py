"""extend_lessons_add_class_records_and_homeworks

Revision ID: a1b2c3d4e5f6
Revises: e512e3adff1c
Create Date: 2026-10-10 18:15:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "e512e3adff1c"
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. Extend lessons table with new columns ──────────────────────────
    with op.batch_alter_table("lessons") as batch_op:
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("duration_minutes", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("sequence_order", sa.Integer(), nullable=True))

    # ── 2. Create class_records table ─────────────────────────────────────
    op.create_table(
        "class_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("batches.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True),
        sa.Column("class_date", sa.Date(), nullable=False),
        sa.Column("chapter", sa.String(200), nullable=True),
        sa.Column("topic", sa.String(300), nullable=True),
        sa.Column("topics_completed", sa.Text(), nullable=True),
        sa.Column("topics_partial", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("next_topic", sa.String(300), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── 3. Create homeworks table ─────────────────────────────────────────
    op.create_table(
        "homeworks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("batches.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True),
        sa.Column("class_record_id", sa.Integer(), sa.ForeignKey("class_records.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("assigned_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("homeworks")
    op.drop_table("class_records")
    with op.batch_alter_table("lessons") as batch_op:
        batch_op.drop_column("sequence_order")
        batch_op.drop_column("duration_minutes")
        batch_op.drop_column("description")
