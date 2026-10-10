from datetime import date, datetime, UTC
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Fee(Base):
    __tablename__ = "fees"
    __table_args__ = (
        Index(
            "uq_fee_student_academic_month",
            "student_id",
            "academic_year",
            "fee_month",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
    )

    batch_id: Mapped[int] = mapped_column(
        ForeignKey("batches.id", ondelete="RESTRICT"),
        nullable=False,
    )

    academic_year: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    fee_month: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    amount_due: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    discount: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=0,
    )

    final_amount_due: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDING",
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

    student = relationship(
        "Student",
        back_populates="fees",
    )

    batch = relationship(
        "Batch",
        back_populates="fees",
    )

    payments = relationship(
        "FeePayment",
        back_populates="fee",
        cascade="all, delete-orphan",
        order_by="FeePayment.payment_date.desc(), FeePayment.id.desc()",
    )

    @property
    def total_paid(self) -> float:
        valid_payments = [p for p in self.payments if not p.is_reversed]
        return float(sum((Decimal(str(p.amount)) for p in valid_payments), Decimal("0.00")))

    @property
    def outstanding_balance(self) -> float:
        balance = Decimal(str(self.final_amount_due)) - Decimal(str(self.total_paid))
        return float(max(balance, Decimal("0.00")))

    def calculate_status(self, as_of_date: date | None = None) -> str:
        check_date = as_of_date or date.today()
        paid = Decimal(str(self.total_paid))
        due = Decimal(str(self.final_amount_due))

        if due <= Decimal("0.00") or paid >= due:
            return "PAID"
        if paid > Decimal("0.00"):
            return "PARTIALLY_PAID"
        if self.due_date and self.due_date < check_date:
            return "OVERDUE"
        return "UNPAID"