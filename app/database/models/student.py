"""
Student Database Model.

Represents an individual enrolled student in the coaching institute.
Tracks academic admission number, batch affiliation, contact links to Parent,
custom monthly fee rates, and status lifecycle ('ACTIVE', 'INACTIVE', 'ALUMNI').
"""

from datetime import date, datetime, UTC

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Student(Base):
    """
    SQLAlchemy ORM model for enrolled coaching students.
    """
    __tablename__ = "students"

    # Primary key identifier
    id: Mapped[int] = mapped_column(primary_key=True)

    # Unique institutional admission/roll number (e.g., 'ADM-2026-042')
    admission_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )

    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    last_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("parents.id", ondelete="RESTRICT"),
        nullable=True,
    )

    batch_id: Mapped[int] = mapped_column(
        ForeignKey("batches.id", ondelete="RESTRICT"),
        nullable=False,
    )

    date_of_birth: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    school_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    admission_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    monthly_fee: Mapped[float | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="ACTIVE",
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
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

    batch = relationship(
        "Batch",
        back_populates="students",
    )

    parent = relationship(
        "Parent",
        back_populates="students",
    )

    fees = relationship(
        "Fee",
        back_populates="student",
        order_by="Fee.academic_year.desc(), Fee.fee_month.desc()",
    )