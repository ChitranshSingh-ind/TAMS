from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)

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
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
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