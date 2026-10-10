import csv
from datetime import date, datetime, UTC
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database.models.expense import Expense
from app.database.models.expense_payment import ExpensePayment

DEFAULT_EXPENSE_CATEGORIES = [
    "Rent",
    "Utilities & Bills",
    "Salaries & Staff",
    "Printing & Stationery",
    "Software & Subscriptions",
    "Books & Study Material",
    "Maintenance & Repairs",
    "Marketing & Promotion",
    "Refreshments",
    "Taxes & Government",
    "Miscellaneous",
]

EXPENSE_PAYMENT_METHODS = ["Cash", "UPI", "Bank Transfer", "Card", "Cheque", "Other"]


def _to_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).quantize(Decimal("0.01"))


def create_expense(
    session: Session,
    description: str,
    category: str,
    amount: float | Decimal,
    expense_date: date,
    payee: str | None = None,
    due_date: date | None = None,
    notes: str | None = None,
    initial_payment: dict | None = None,
) -> Expense:
    desc = (description or "").strip()
    if not desc:
        raise ValueError("Expense description is required.")

    cat = (category or "").strip()
    if not cat:
        raise ValueError("Expense category is required.")

    amt_dec = _to_decimal(amount)
    if amt_dec <= Decimal("0.00"):
        raise ValueError("Expense amount must be greater than zero.")

    # Duplicate submission prevention: same description, payee, date and amount
    payee_clean = payee.strip() if payee else None
    existing = session.scalars(
        select(Expense).where(
            Expense.description == desc,
            Expense.expense_date == expense_date,
            Expense.amount == float(amt_dec),
            Expense.category == cat,
        )
    ).first()
    if existing is not None:
        raise ValueError(
            f"An identical expense ('{desc}' for ₹{float(amt_dec):,.2f} on {expense_date}) already exists."
        )

    expense = Expense(
        description=desc,
        category=cat,
        amount=float(amt_dec),
        expense_date=expense_date,
        payee=payee_clean,
        due_date=due_date,
        status="PENDING",
        notes=notes.strip() if notes else None,
    )
    session.add(expense)
    session.flush()

    if initial_payment:
        pay_amt = _to_decimal(initial_payment.get("amount", amt_dec))
        if pay_amt > amt_dec:
            raise ValueError("Initial payment cannot exceed the total expense amount.")
        if pay_amt > Decimal("0.00"):
            p_date = initial_payment.get("payment_date", expense_date)
            p_method = initial_payment.get("payment_method", "Cash")
            p_ref = initial_payment.get("reference_number")
            p_notes = initial_payment.get("notes")

            payment = ExpensePayment(
                expense_id=expense.id,
                amount=float(pay_amt),
                payment_date=p_date,
                payment_method=p_method,
                reference_number=p_ref.strip() if p_ref else None,
                notes=p_notes.strip() if p_notes else None,
            )
            session.add(payment)
            session.flush()

    session.refresh(expense)
    expense.status = expense.calculate_status()
    session.commit()
    session.refresh(expense)
    return expense


def update_expense(
    session: Session,
    expense_id: int,
    description: str,
    category: str,
    amount: float | Decimal,
    expense_date: date,
    payee: str | None = None,
    due_date: date | None = None,
    notes: str | None = None,
) -> Expense:
    expense = session.get(Expense, expense_id)
    if expense is None:
        raise ValueError("Expense not found.")

    desc = (description or "").strip()
    if not desc:
        raise ValueError("Expense description is required.")

    cat = (category or "").strip()
    if not cat:
        raise ValueError("Expense category is required.")

    amt_dec = _to_decimal(amount)
    if amt_dec <= Decimal("0.00"):
        raise ValueError("Expense amount must be greater than zero.")

    total_paid_dec = _to_decimal(expense.total_paid)
    if amt_dec < total_paid_dec:
        raise ValueError(
            f"New expense amount (₹{float(amt_dec):,.2f}) cannot be less than "
            f"already paid amount (₹{float(total_paid_dec):,.2f})."
        )

    expense.description = desc
    expense.category = cat
    expense.amount = float(amt_dec)
    expense.expense_date = expense_date
    expense.payee = payee.strip() if payee else None
    expense.due_date = due_date
    expense.notes = notes.strip() if notes else None

    expense.status = expense.calculate_status()
    session.commit()
    session.refresh(expense)
    return expense


def delete_expense(session: Session, expense_id: int) -> bool:
    expense = session.get(Expense, expense_id)
    if expense is None:
        return False

    valid_payments = [p for p in expense.payments if not p.is_reversed]
    if valid_payments:
        raise ValueError(
            "Cannot delete an expense with active payments. Reverse all payments first or mark the expense as void."
        )

    session.delete(expense)
    session.commit()
    return True


def get_expense(session: Session, expense_id: int) -> Expense | None:
    return session.scalar(
        select(Expense)
        .options(selectinload(Expense.payments))
        .where(Expense.id == expense_id)
    )


def get_expenses(
    session: Session,
    search: str | None = None,
    category: str | None = None,
    payment_status: str | None = None,
    payment_method: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    sort_by: str = "date_desc",
) -> list[Expense]:
    statement = (
        select(Expense)
        .options(selectinload(Expense.payments))
        .order_by(Expense.expense_date.desc(), Expense.id.desc())
    )

    if category and category != "ALL":
        statement = statement.where(Expense.category == category)

    if start_date is not None:
        statement = statement.where(Expense.expense_date >= start_date)

    if end_date is not None:
        statement = statement.where(Expense.expense_date <= end_date)

    if search:
        search_term = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                Expense.description.ilike(search_term),
                Expense.payee.ilike(search_term),
                Expense.notes.ilike(search_term),
            )
        )

    expenses = list(session.scalars(statement).all())

    # Post-filter by dynamically calculated status and payment method if requested
    if payment_status and payment_status != "ALL":
        expenses = [e for e in expenses if e.calculate_status() == payment_status]

    if payment_method and payment_method != "ALL":
        filtered = []
        for e in expenses:
            methods = {p.payment_method for p in e.payments if not p.is_reversed}
            if payment_method in methods:
                filtered.append(e)
        expenses = filtered

    if sort_by == "date_asc":
        expenses.sort(key=lambda e: (e.expense_date, e.id))
    elif sort_by == "amount_desc":
        expenses.sort(key=lambda e: e.amount, reverse=True)
    elif sort_by == "amount_asc":
        expenses.sort(key=lambda e: e.amount)

    return expenses


def get_expenses_summary(
    session: Session,
    start_date: date | None = None,
    end_date: date | None = None,
    category: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    expenses = get_expenses(
        session,
        search=search,
        category=category,
        start_date=start_date,
        end_date=end_date,
    )

    total_expenses = Decimal("0.00")
    total_paid = Decimal("0.00")
    total_outstanding = Decimal("0.00")
    current_month_total = Decimal("0.00")

    today = date.today()
    current_month = today.month
    current_year = today.year

    category_map: dict[str, Decimal] = {}
    method_map: dict[str, Decimal] = {}

    for e in expenses:
        if e.status == "VOID":
            continue
        amt = Decimal(str(e.amount))
        paid = Decimal(str(e.total_paid))
        bal = Decimal(str(e.outstanding_balance))

        total_expenses += amt
        total_paid += paid
        total_outstanding += bal

        if e.expense_date.year == current_year and e.expense_date.month == current_month:
            current_month_total += amt

        category_map[e.category] = category_map.get(e.category, Decimal("0.00")) + amt

        for p in e.payments:
            if not p.is_reversed:
                method_map[p.payment_method] = (
                    method_map.get(p.payment_method, Decimal("0.00")) + Decimal(str(p.amount))
                )

    cat_breakdown = [
        {"category": c, "amount": float(a)}
        for c, a in sorted(category_map.items(), key=lambda x: x[1], reverse=True)
    ]

    method_breakdown = [
        {"method": m, "amount": float(a)}
        for m, a in sorted(method_map.items(), key=lambda x: x[1], reverse=True)
    ]

    return {
        "total_expenses": float(total_expenses),
        "total_paid": float(total_paid),
        "total_outstanding": float(total_outstanding),
        "current_month_expenses": float(current_month_total),
        "count": len(expenses),
        "category_breakdown": cat_breakdown,
        "payment_method_breakdown": method_breakdown,
    }


def record_expense_payment(
    session: Session,
    expense_id: int,
    amount: float | Decimal,
    payment_date: date,
    payment_method: str,
    reference_number: str | None = None,
    notes: str | None = None,
) -> ExpensePayment:
    expense = session.get(Expense, expense_id)
    if expense is None:
        raise ValueError("Expense record not found.")

    if expense.status == "VOID":
        raise ValueError("Cannot record payment for a voided expense.")

    pay_amt = _to_decimal(amount)
    if pay_amt <= Decimal("0.00"):
        raise ValueError("Payment amount must be greater than zero.")

    outstanding = _to_decimal(expense.outstanding_balance)
    if pay_amt > outstanding:
        raise ValueError(
            f"Payment amount (₹{float(pay_amt):,.2f}) exceeds outstanding payable balance (₹{float(outstanding):,.2f})."
        )

    clean_method = (payment_method or "Cash").strip()
    if clean_method not in EXPENSE_PAYMENT_METHODS:
        clean_method = "Other"

    payment = ExpensePayment(
        expense_id=expense.id,
        amount=float(pay_amt),
        payment_date=payment_date,
        payment_method=clean_method,
        reference_number=reference_number.strip() if reference_number else None,
        notes=notes.strip() if notes else None,
    )
    session.add(payment)
    session.flush()

    session.refresh(expense)
    expense.status = expense.calculate_status()
    session.commit()
    session.refresh(payment)
    return payment


def reverse_expense_payment(
    session: Session,
    payment_id: int,
    reason: str,
) -> ExpensePayment:
    clean_reason = (reason or "").strip()
    if not clean_reason:
        raise ValueError("A reason is required to reverse an expense payment.")

    payment = session.get(ExpensePayment, payment_id)
    if payment is None:
        raise ValueError("Payment record not found.")

    if payment.is_reversed:
        raise ValueError("This payment has already been reversed.")

    payment.is_reversed = True
    payment.reversal_reason = clean_reason
    payment.reversed_at = datetime.now(UTC)

    expense = session.get(Expense, payment.expense_id)
    if expense:
        session.flush()
        expense.status = expense.calculate_status()

    session.commit()
    session.refresh(payment)
    return payment


def get_expense_payments(
    session: Session,
    expense_id: int | None = None,
    include_reversed: bool = False,
) -> list[ExpensePayment]:
    statement = (
        select(ExpensePayment)
        .options(joinedload(ExpensePayment.expense))
        .order_by(ExpensePayment.payment_date.desc(), ExpensePayment.id.desc())
    )
    if expense_id is not None:
        statement = statement.where(ExpensePayment.expense_id == expense_id)
    if not include_reversed:
        statement = statement.where(ExpensePayment.is_reversed.is_(False))

    return list(session.scalars(statement).all())


def export_expenses_csv(
    session: Session,
    filepath: str,
    search: str | None = None,
    category: str | None = None,
    payment_status: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> int:
    expenses = get_expenses(
        session,
        search=search,
        category=category,
        payment_status=payment_status,
        start_date=start_date,
        end_date=end_date,
    )

    with open(filepath, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "ID",
            "Date",
            "Description",
            "Category",
            "Payee / Vendor",
            "Total Amount (INR)",
            "Paid Amount (INR)",
            "Outstanding Balance (INR)",
            "Due Date",
            "Status",
            "Notes",
        ])

        for e in expenses:
            writer.writerow([
                e.id,
                e.expense_date.strftime("%Y-%m-%d"),
                e.description,
                e.category,
                e.payee or "",
                f"{e.amount:.2f}",
                f"{e.total_paid:.2f}",
                f"{e.outstanding_balance:.2f}",
                e.due_date.strftime("%Y-%m-%d") if e.due_date else "",
                e.calculate_status(),
                e.notes or "",
            ])

    return len(expenses)
