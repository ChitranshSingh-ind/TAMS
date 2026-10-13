"""
Batch Database Model.

Represents an academic cohort or class (e.g. 'Class 10 Mathematics', 'Droppers NEET Biology').
Batches define weekly class days, schedules, default fee structures, and link to enrolled students.
"""

from datetime import datetime, UTC

from sqlalchemy import Boolean, DateTime, Numeric, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Batch(Base):
    """
    SQLAlchemy ORM model for coaching batches.
    Stores schedule timings, active status flag, and relationships to students and fees.
    """
    __tablename__ = "batches"

    # Primary key identifier
    id: Mapped[int] = mapped_column(primary_key=True)

    # Unique batch name (e.g., 'Class 12 Physics')
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    start_time: Mapped[Time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[Time | None] = mapped_column(Time, nullable=True)

    days: Mapped[str | None] = mapped_column(String(100), nullable=True)

    monthly_fee: Mapped[float | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    students = relationship(
        "Student",
        back_populates="batch",
    )

    fees = relationship(
        "Fee",
        back_populates="batch",
    )