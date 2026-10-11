"""create_messaging_system_tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-11 18:05:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. Create message_templates table ────────────────────────────────
    op.create_table(
        "message_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("meta_template_name", sa.String(100), nullable=False),
        sa.Column("category", sa.String(50), nullable=False, server_default="UTILITY"),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("parameters_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("meta_status", sa.String(50), nullable=False, server_default="LOCAL_ONLY"),
        sa.Column("associated_trigger", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── 2. Create messages table ──────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("recipient_phone", sa.String(30), nullable=False),
        sa.Column("recipient_name", sa.String(150), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="SET NULL"), nullable=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("parents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("batches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("message_templates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("template_name", sa.String(100), nullable=True),
        sa.Column("message_body", sa.Text(), nullable=False),
        sa.Column("category", sa.String(50), nullable=False, server_default="UTILITY"),
        sa.Column("trigger_type", sa.String(30), nullable=False, server_default="MANUAL"),
        sa.Column("source_module", sa.String(50), nullable=True),
        sa.Column("source_record_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="QUEUED"),
        sa.Column("provider", sa.String(50), nullable=False, server_default="WHATSAPP_CLOUD"),
        sa.Column("provider_message_id", sa.String(100), nullable=True),
        sa.Column("environment", sa.String(20), nullable=False, server_default="DEVELOPMENT"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("lease_holder", sa.String(100), nullable=True),
        sa.Column("leased_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_messages_status", "messages", ["status"])
    op.create_index("ix_messages_recipient_phone", "messages", ["recipient_phone"])
    op.create_index("ix_messages_queued_at", "messages", ["queued_at"])
    op.create_index("ix_messages_batch_id", "messages", ["batch_id"])
    op.create_index("ix_messages_student_id", "messages", ["student_id"])
    op.create_index("ix_messages_provider_msg_id", "messages", ["provider_message_id"])

    # ── 3. Create notification_rules table ────────────────────────────────
    op.create_table(
        "notification_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("trigger_event", sa.String(50), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("batches.id", ondelete="CASCADE"), nullable=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("message_templates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("days_offset", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cooldown_days", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("min_consecutive_days", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("custom_conditions_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notif_rules_trigger", "notification_rules", ["trigger_event"])

    # ── 4. Create recipient_preferences table ─────────────────────────────
    op.create_table(
        "recipient_preferences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("phone_number", sa.String(30), unique=True, nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="SET NULL"), nullable=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("parents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_opted_out", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("opt_out_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_source", sa.String(100), nullable=True, server_default="ADMISSION_RECORD"),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("preferred_language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("allowed_categories_json", sa.Text(), nullable=False, server_default='["ALL"]'),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_recipient_pref_phone", "recipient_preferences", ["phone_number"])

    # ── 5. Create messaging_configs table ─────────────────────────────────
    op.create_table(
        "messaging_configs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(100), unique=True, nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("messaging_configs")
    op.drop_table("recipient_preferences")
    op.drop_table("notification_rules")
    op.drop_table("messages")
    op.drop_table("message_templates")
