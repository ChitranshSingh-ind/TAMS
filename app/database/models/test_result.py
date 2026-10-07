from datetime import datetime, UTC

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class TestResult(Base):
    __test__ = False
    __tablename__ = "test_results"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    test_id: Mapped[int] = mapped_column(
        ForeignKey("tests.id"),
        nullable=False,
    )

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        nullable=False,
    )

    marks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    remarks: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    test = relationship("TestModel")
    student = relationship("Student")