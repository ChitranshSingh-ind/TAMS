from datetime import date, datetime, UTC

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class TestModel(Base):
    __test__ = False
    __tablename__ = "tests"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    batch_id: Mapped[int] = mapped_column(
        ForeignKey("batches.id", ondelete="RESTRICT"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    test_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    max_marks: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    results = relationship(
        "TestResult",
        back_populates="test",
        cascade="all, delete-orphan",
    )
    batch = relationship("Batch")