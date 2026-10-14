from datetime import date, datetime, UTC

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    batch_id: Mapped[int] = mapped_column(
        ForeignKey("batches.id", ondelete="RESTRICT"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    chapter: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    topic: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    planned_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    duration_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    sequence_order: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # PLANNED, IN_PROGRESS, COMPLETED, CANCELLED
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PLANNED",
    )

    notes: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    class_records: Mapped[list["ClassRecord"]] = relationship(
        "ClassRecord",
        back_populates="lesson",
        cascade="all, delete-orphan",
        lazy="select",
    )

    homeworks: Mapped[list["Homework"]] = relationship(
        "Homework",
        back_populates="lesson",
        cascade="all, delete-orphan",
        lazy="select",
    )

    batch: Mapped["Batch"] = relationship(  # type: ignore[name-defined]
        "Batch",
        foreign_keys=[batch_id],
        lazy="select",
    )


class ClassRecord(Base):
    """Records what was actually taught in a class session."""
    __tablename__ = "class_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    batch_id: Mapped[int] = mapped_column(
        ForeignKey("batches.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Optional link to a planned lesson
    lesson_id: Mapped[int | None] = mapped_column(
        ForeignKey("lessons.id", ondelete="SET NULL"),
        nullable=True,
    )

    class_date: Mapped[date] = mapped_column(Date, nullable=False)

    chapter: Mapped[str | None] = mapped_column(String(200), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(300), nullable=True)

    topics_completed: Mapped[str | None] = mapped_column(Text, nullable=True)
    topics_partial: Mapped[str | None] = mapped_column(Text, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Next session follow-up
    next_topic: Mapped[str | None] = mapped_column(String(300), nullable=True)

    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    lesson: Mapped["Lesson | None"] = relationship(
        "Lesson",
        back_populates="class_records",
    )

    homeworks: Mapped[list["Homework"]] = relationship(
        "Homework",
        back_populates="class_record",
        cascade="all, delete-orphan",
        lazy="select",
    )

    batch: Mapped["Batch"] = relationship(  # type: ignore[name-defined]
        "Batch",
        foreign_keys=[batch_id],
        lazy="select",
    )


class Homework(Base):
    """Homework or assignment given to students of a batch."""
    __tablename__ = "homeworks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    batch_id: Mapped[int] = mapped_column(
        ForeignKey("batches.id", ondelete="RESTRICT"),
        nullable=False,
    )

    lesson_id: Mapped[int | None] = mapped_column(
        ForeignKey("lessons.id", ondelete="SET NULL"),
        nullable=True,
    )

    class_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("class_records.id", ondelete="SET NULL"),
        nullable=True,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    assigned_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    lesson: Mapped["Lesson | None"] = relationship(
        "Lesson",
        back_populates="homeworks",
    )

    class_record: Mapped["ClassRecord | None"] = relationship(
        "ClassRecord",
        back_populates="homeworks",
    )

    batch: Mapped["Batch"] = relationship(  # type: ignore[name-defined]
        "Batch",
        foreign_keys=[batch_id],
        lazy="select",
    )