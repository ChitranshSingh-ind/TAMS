from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class MessageTemplate(Base):
    """
    Templates for WhatsApp and SMS notifications.
    Supports local TAMS variable interpolation and Meta WhatsApp pre-approved templates.
    """
    __tablename__ = "message_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    meta_template_name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="UTILITY")  # UTILITY, MARKETING, AUTHENTICATION
    language: Mapped[str] = mapped_column(String(10), default="en")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    parameters_json: Mapped[str] = mapped_column(Text, default="[]")  # JSON list of required param names
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    meta_status: Mapped[str] = mapped_column(String(50), default="LOCAL_ONLY")  # APPROVED, PENDING, REJECTED, LOCAL_ONLY
    associated_trigger: Mapped[str | None] = mapped_column(String(50), nullable=True)  # FEE_DUE, ABSENCE, etc.

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    messages: Mapped[list[Message]] = relationship("Message", back_populates="template")


class Message(Base):
    """
    Audit log, queue record, and delivery history for all outgoing messages.
    Supports safe lease locking for SQLite concurrent background processors.
    """
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipient_phone: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    recipient_name: Mapped[str] = mapped_column(String(150), nullable=False)

    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("parents.id", ondelete="SET NULL"),
        nullable=True,
    )
    batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("message_templates.id", ondelete="SET NULL"),
        nullable=True,
    )

    template_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parameters_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_body: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="UTILITY")
    trigger_type: Mapped[str] = mapped_column(String(30), default="MANUAL")  # MANUAL, AUTOMATED
    source_module: Mapped[str | None] = mapped_column(String(50), nullable=True)  # FEES, ATTENDANCE, RESULTS, GENERAL
    source_record_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Lifecycle: QUEUED -> SENDING -> ACCEPTED -> DELIVERED / READ / FAILED / RETRY_SCHEDULED / CANCELLED
    status: Mapped[str] = mapped_column(String(30), default="QUEUED", index=True)
    provider: Mapped[str] = mapped_column(String(50), default="WHATSAPP_CLOUD")
    provider_message_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    environment: Mapped[str] = mapped_column(String(20), default="PRODUCTION")  # DEVELOPMENT, PRODUCTION

    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Claim/Lease locking mechanism to prevent race conditions in background processing
    lease_holder: Mapped[str | None] = mapped_column(String(100), nullable=True)
    leased_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_messages_provider_msg_id", "provider_message_id"),
    )

    template: Mapped[MessageTemplate | None] = relationship("MessageTemplate", back_populates="messages")


class NotificationRule(Base):
    """
    Configurable rules triggering automatic notifications on TAMS events.
    Disabled by default until explicitly enabled by user.
    """
    __tablename__ = "notification_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    trigger_event: Mapped[str] = mapped_column(String(50), nullable=False)
    # Events: FEE_DUE, FEE_OVERDUE, PAYMENT_RECEIPT, ABSENCE, CONSECUTIVE_ABSENCE, TEST_RESULT
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)  # MUST BE FALSE BY DEFAULT

    batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("batches.id", ondelete="CASCADE"),
        nullable=True,
    )
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("message_templates.id", ondelete="SET NULL"),
        nullable=True,
    )

    days_offset: Mapped[int] = mapped_column(Integer, default=0)
    cooldown_days: Mapped[int] = mapped_column(Integer, default=0)
    min_consecutive_days: Mapped[int] = mapped_column(Integer, default=2)
    custom_conditions_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_notif_rules_trigger", "trigger_event"),
    )


class RecipientPreference(Base):
    """
    Consent, verification, and opt-out preferences per contact phone number.
    """
    __tablename__ = "recipient_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True,
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("parents.id", ondelete="SET NULL"),
        nullable=True,
    )

    is_opted_out: Mapped[bool] = mapped_column(Boolean, default=False)
    opt_out_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_source: Mapped[str | None] = mapped_column(String(100), default="ADMISSION_RECORD")
    verified: Mapped[bool] = mapped_column(Boolean, default=True)
    preferred_language: Mapped[str] = mapped_column(String(10), default="en")
    allowed_categories_json: Mapped[str] = mapped_column(Text, default='["ALL"]')

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_recipient_pref_phone", "phone_number"),
    )


class MessagingConfig(Base):
    """
    Key-value persistence for messaging system preferences, provider settings, and limits.
    (Non-secret configs; secrets stored via secure credential store / encrypted fallback).
    """
    __tablename__ = "messaging_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
