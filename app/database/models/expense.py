"""
Expense Database Model.

Represents an operating expenditure, bill, or vendor invoice incurred by the coaching institute.
Tracks expense category, bill amount, payments made, payment status ('PAID', 'PARTIALLY_PAID', 'PENDING'),
and links to granular ExpensePayment transactions.
"""

from datetime import date, datetime, UTC
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Expense(Base):
    """
    SQLAlchemy ORM model for institutional expenses and operational costs.
    """
    __tablename__ = "expenses"
    __table_args__ = (
        Index("ix_expenses_expense_date", "expense_date"),
        Index("ix_expenses_category", "category"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    description: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    amount: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    expense_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    payee: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
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

    payments = relationship(
        "ExpensePayment",
        back_populates="expense",
        cascade="all, delete-orphan",
        order_by="ExpensePayment.payment_date.desc(), ExpensePayment.id.desc()",
    )

    @property
    def total_paid(self) -> float:
        valid_payments = [p for p in self.payments if not p.is_reversed]
        return float(sum((Decimal(str(p.amount)) for p in valid_payments), Decimal("0.00")))

    @property
    def outstanding_balance(self) -> float:
        balance = Decimal(str(self.amount)) - Decimal(str(self.total_paid))
        return float(max(balance, Decimal("0.00")))

    def calculate_status(self, as_of_date: date | None = None) -> str:
        if self.status == "VOID":
            return "VOID"
        check_date = as_of_date or date.today()
        paid = Decimal(str(self.total_paid))
        total = Decimal(str(self.amount))

        if total <= Decimal("0.00") or paid >= total:
            return "PAID"
        if paid > Decimal("0.00"):
            return "PARTIALLY_PAID"
        if self.due_date and self.due_date < check_date:
            return "OVERDUE"
        return "PENDING"
