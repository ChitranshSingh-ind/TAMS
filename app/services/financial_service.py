"""
TAMS Financial & P&L Intelligence Service.

Computes comprehensive fiscal health analytics across student fees and operating expenses:
  - Cash-basis cash flow (actual money in vs. actual money out)
  - Accrual-basis profitability (fees billed vs. liabilities incurred)
  - Pending receivables and outstanding payables
  - Historical monthly financial trends and profit margins
"""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models.expense import Expense
from app.database.models.expense_payment import ExpensePayment
from app.database.models.fee import Fee
from app.database.models.fee_payment import FeePayment


def _to_decimal(val: Any) -> Decimal:
    """Helper to safely convert numeric or None values to 2-decimal-place Decimal."""
    if val is None:
        return Decimal("0.00")
    return Decimal(str(val)).quantize(Decimal("0.01"))


def get_financial_summary(
    session: Session,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Computes an aggregated financial summary comparing fee collections against expenses,
    covering both cash-basis and accrual-basis accounting.

    Args:
        session: Active database session.
        start_date: Optional start date filter.
        end_date: Optional end date filter.

    Returns:
        Dict containing fees_collected, expenses_paid, net_cash_flow,
        fees_billed, expenses_incurred, net_accrual_profit, and receivables/payables.
    """
    # ── 1. Cash-based metrics (Actual payments received vs actual payments made) ──
    fee_pay_stmt = select(func.coalesce(func.sum(FeePayment.amount), 0)).where(
        FeePayment.is_reversed.is_(False)
    )
    if start_date is not None:
        fee_pay_stmt = fee_pay_stmt.where(FeePayment.payment_date >= start_date)
    if end_date is not None:
        fee_pay_stmt = fee_pay_stmt.where(FeePayment.payment_date <= end_date)
    fees_collected = _to_decimal(session.scalar(fee_pay_stmt))

    exp_pay_stmt = select(func.coalesce(func.sum(ExpensePayment.amount), 0)).where(
        ExpensePayment.is_reversed.is_(False)
    )
    if start_date is not None:
        exp_pay_stmt = exp_pay_stmt.where(ExpensePayment.payment_date >= start_date)
    if end_date is not None:
        exp_pay_stmt = exp_pay_stmt.where(ExpensePayment.payment_date <= end_date)
    expenses_paid = _to_decimal(session.scalar(exp_pay_stmt))

    net_cash_flow = fees_collected - expenses_paid

    # ── 2. Accrual-based metrics (Incurred obligations & expenses) ───────────────
    fee_bill_stmt = select(func.coalesce(func.sum(Fee.final_amount_due), 0))
    if start_date is not None:
        fee_bill_stmt = fee_bill_stmt.where(Fee.due_date >= start_date)
    if end_date is not None:
        fee_bill_stmt = fee_bill_stmt.where(Fee.due_date <= end_date)
    fees_billed = _to_decimal(session.scalar(fee_bill_stmt))

    exp_incurred_stmt = select(func.coalesce(func.sum(Expense.amount), 0)).where(
        Expense.status != "VOID"
    )
    if start_date is not None:
        exp_incurred_stmt = exp_incurred_stmt.where(Expense.expense_date >= start_date)
    if end_date is not None:
        exp_incurred_stmt = exp_incurred_stmt.where(Expense.expense_date <= end_date)
    expenses_incurred = _to_decimal(session.scalar(exp_incurred_stmt))

    net_accrual_income = fees_billed - expenses_incurred

    # ── 3. Outstanding Balances / Liabilities (as of current date) ───────────────
    total_fee_due_all = _to_decimal(
        session.scalar(select(func.coalesce(func.sum(Fee.final_amount_due), 0)))
    )
    total_fee_paid_all = _to_decimal(
        session.scalar(
            select(func.coalesce(func.sum(FeePayment.amount), 0)).where(
                FeePayment.is_reversed.is_(False)
            )
        )
    )
    outstanding_student_fees = max(Decimal("0.00"), total_fee_due_all - total_fee_paid_all)

    total_exp_incurred_all = _to_decimal(
        session.scalar(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                Expense.status != "VOID"
            )
        )
    )
    total_exp_paid_all = _to_decimal(
        session.scalar(
            select(func.coalesce(func.sum(ExpensePayment.amount), 0)).where(
                ExpensePayment.is_reversed.is_(False)
            )
        )
    )
    outstanding_expenses = max(Decimal("0.00"), total_exp_incurred_all - total_exp_paid_all)

    return {
        "fees_collected": float(fees_collected),
        "expenses_paid": float(expenses_paid),
        "net_cash_flow": float(net_cash_flow),
        "fees_billed": float(fees_billed),
        "expenses_incurred": float(expenses_incurred),
        "net_accrual_income": float(net_accrual_income),
        "outstanding_student_fees": float(outstanding_student_fees),
        "outstanding_expenses": float(outstanding_expenses),
    }


def get_monthly_financial_comparison(
    session: Session,
    months_count: int = 6,
) -> list[dict[str, Any]]:
    """
    Computes a month-by-month comparative analysis of revenue and expenses
    for the last N months. Used for financial chart rendering.

    Args:
        session: Active database session.
        months_count: Number of historical months to include (default: 6).

    Returns:
        List of monthly records with fees_collected, expenses_paid, and profit margins.
    """
    today = date.today()
    results = []

    # Build sequence of (year, month) pairs for the last months_count months
    year, month = today.year, today.month
    months = []
    for _ in range(months_count):
        months.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1

    months.reverse()

    month_names = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
    ]

    for y, m in months:
        # Month start and end dates
        start = date(y, m, 1)
        if m == 12:
            end = date(y + 1, 1, 1)
        else:
            end = date(y, m + 1, 1)

        # Cash in: Fee payments in month
        fee_stmt = select(func.coalesce(func.sum(FeePayment.amount), 0)).where(
            FeePayment.is_reversed.is_(False),
            FeePayment.payment_date >= start,
            FeePayment.payment_date < end,
        )
        fees_cash = _to_decimal(session.scalar(fee_stmt))

        # Cash out: Expense payments in month
        exp_stmt = select(func.coalesce(func.sum(ExpensePayment.amount), 0)).where(
            ExpensePayment.is_reversed.is_(False),
            ExpensePayment.payment_date >= start,
            ExpensePayment.payment_date < end,
        )
        exp_cash = _to_decimal(session.scalar(exp_stmt))

        # Accrual: Expenses incurred in month
        incurred_stmt = select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.status != "VOID",
            Expense.expense_date >= start,
            Expense.expense_date < end,
        )
        exp_incurred = _to_decimal(session.scalar(incurred_stmt))

        # Accrual: Fees billed for fee_month m and academic_year
        billed_stmt = select(func.coalesce(func.sum(Fee.final_amount_due), 0)).where(
            Fee.fee_month == m
        )
        fees_billed = _to_decimal(session.scalar(billed_stmt))

        results.append({
            "year": y,
            "month": m,
            "label": f"{month_names[m - 1]} {y}",
            "month_name": f"{month_names[m - 1]} {y}",
            "fees_collected": float(fees_cash),
            "expenses_paid": float(exp_cash),
            "net_cash_flow": float(fees_cash - exp_cash),
            "fees_billed": float(fees_billed),
            "expenses_incurred": float(exp_incurred),
            "net_accrual_margin": float(fees_billed - exp_incurred),
        })

    return results
