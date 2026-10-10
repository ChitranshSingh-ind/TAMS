import csv
from datetime import date, timedelta
from decimal import Decimal
import tempfile
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.models.expense import Expense
from app.database.models.expense_payment import ExpensePayment
from app.services.expense_service import (
    DEFAULT_EXPENSE_CATEGORIES,
    create_expense,
    update_expense,
    delete_expense,
    get_expense,
    get_expenses,
    get_expenses_summary,
    record_expense_payment,
    reverse_expense_payment,
    get_expense_payments,
    export_expenses_csv,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        yield session


def test_create_expense_validation_and_creation(db_session):
    # 1. Validation: Description required
    with pytest.raises(ValueError, match="Expense description is required"):
        create_expense(
            db_session,
            description="   ",
            category="Rent",
            amount=5000.0,
            expense_date=date(2026, 10, 1),
        )

    # 2. Validation: Category required
    with pytest.raises(ValueError, match="Expense category is required"):
        create_expense(
            db_session,
            description="October Rent",
            category="   ",
            amount=5000.0,
            expense_date=date(2026, 10, 1),
        )

    # 3. Validation: Amount > 0
    with pytest.raises(ValueError, match="Expense amount must be greater than zero"):
        create_expense(
            db_session,
            description="October Rent",
            category="Rent",
            amount=0.0,
            expense_date=date(2026, 10, 1),
        )

    with pytest.raises(ValueError, match="Expense amount must be greater than zero"):
        create_expense(
            db_session,
            description="October Rent",
            category="Rent",
            amount=-500.0,
            expense_date=date(2026, 10, 1),
        )

    # 4. Successful creation without initial payment
    exp = create_expense(
        db_session,
        description="Coaching Hall Rent",
        category="Rent",
        amount=15000.0,
        expense_date=date(2026, 10, 1),
        payee="City Commercial Hub",
        due_date=date(2026, 10, 10),
        notes="Rent for main hall",
    )
    assert exp.id is not None
    assert exp.amount == 15000.0
    assert exp.total_paid == 0.0
    assert exp.outstanding_balance == 15000.0
    assert exp.calculate_status() == "PENDING"
    assert len(exp.payments) == 0

    # 5. Duplicate submission prevention
    with pytest.raises(ValueError, match="An identical expense"):
        create_expense(
            db_session,
            description="Coaching Hall Rent",
            category="Rent",
            amount=15000.0,
            expense_date=date(2026, 10, 1),
            payee="City Commercial Hub",
        )


def test_create_expense_with_initial_payment(db_session):
    # 1. Full initial payment
    exp1 = create_expense(
        db_session,
        description="Electricity Bill",
        category="Utilities",
        amount=3200.0,
        expense_date=date(2026, 10, 5),
        payee="State Power Board",
        initial_payment={
            "amount": 3200.0,
            "payment_method": "UPI",
            "reference_number": "UPI-123456",
        },
    )
    assert exp1.total_paid == 3200.0
    assert exp1.outstanding_balance == 0.0
    assert exp1.calculate_status() == "PAID"
    assert len(exp1.payments) == 1
    p = exp1.payments[0]
    assert p.amount == 3200.0
    assert p.payment_method == "UPI"
    assert p.reference_number == "UPI-123456"

    # 2. Partial initial payment
    exp2 = create_expense(
        db_session,
        description="Annual Software License",
        category="Software & Subscriptions",
        amount=10000.0,
        expense_date=date(2026, 10, 2),
        payee="EdTech Cloud",
        initial_payment={
            "amount": 4000.0,
            "payment_method": "Bank Transfer",
        },
    )
    assert exp2.total_paid == 4000.0
    assert exp2.outstanding_balance == 6000.0
    assert exp2.calculate_status() == "PARTIALLY_PAID"

    # 3. Initial payment over amount raises ValueError
    with pytest.raises(ValueError, match="Initial payment cannot exceed the total expense amount"):
        create_expense(
            db_session,
            description="Paper Printing",
            category="Printing & Stationery",
            amount=500.0,
            expense_date=date(2026, 10, 2),
            initial_payment={"amount": 600.0},
        )


def test_update_expense(db_session):
    exp = create_expense(
        db_session,
        description="Highlighter Pens & Paper",
        category="Printing & Stationery",
        amount=1200.0,
        expense_date=date(2026, 10, 3),
        payee="Corner Book Store",
    )

    # 1. Successful update
    updated = update_expense(
        db_session,
        expense_id=exp.id,
        description="A4 Paper Boxes & Stationery",
        category="Printing & Stationery",
        amount=1500.0,
        expense_date=date(2026, 10, 4),
        payee="Wholesale Book Depot",
        due_date=date(2026, 10, 15),
        notes="Tax invoice attached",
    )
    assert updated.description == "A4 Paper Boxes & Stationery"
    assert updated.amount == 1500.0
    assert updated.payee == "Wholesale Book Depot"
    assert updated.due_date == date(2026, 10, 15)

    # 2. Update with active payment: cannot reduce amount below paid
    record_expense_payment(
        db_session,
        expense_id=exp.id,
        amount=1000.0,
        payment_date=date(2026, 10, 5),
        payment_method="Cash",
    )
    assert updated.total_paid == 1000.0

    with pytest.raises(ValueError, match="cannot be less than already paid amount"):
        update_expense(
            db_session,
            expense_id=exp.id,
            description="A4 Paper Boxes & Stationery",
            category="Printing & Stationery",
            amount=800.0,
            expense_date=date(2026, 10, 4),
        )


def test_delete_expense_protection(db_session):
    exp = create_expense(
        db_session,
        description="Whiteboard Markers",
        category="Printing & Stationery",
        amount=600.0,
        expense_date=date(2026, 10, 5),
    )

    # 1. Unpaid expense can be deleted
    assert delete_expense(db_session, exp.id) is True
    assert get_expense(db_session, exp.id) is None

    # 2. Expense with payments cannot be deleted
    exp2 = create_expense(
        db_session,
        description="Projector Bulb",
        category="Repairs & Maintenance",
        amount=2500.0,
        expense_date=date(2026, 10, 5),
    )
    pay = record_expense_payment(
        db_session,
        expense_id=exp2.id,
        amount=1500.0,
        payment_date=date(2026, 10, 6),
        payment_method="UPI",
    )
    with pytest.raises(ValueError, match="Cannot delete an expense with active payments"):
        delete_expense(db_session, exp2.id)

    # 3. If all payments are reversed, deletion succeeds
    reverse_expense_payment(
        db_session,
        payment_id=pay.id,
        reason="Wrong invoice recorded",
    )
    assert delete_expense(db_session, exp2.id) is True
    assert get_expense(db_session, exp2.id) is None


def test_expense_payments_and_reversals(db_session):
    exp = create_expense(
        db_session,
        description="Air Conditioner Service",
        category="Repairs & Maintenance",
        amount=4000.0,
        expense_date=date(2026, 10, 1),
        payee="Cool Air Technicians",
        due_date=date(2026, 10, 15),
    )

    # 1. Invalid payment amounts
    with pytest.raises(ValueError, match="Payment amount must be greater than zero"):
        record_expense_payment(
            db_session,
            expense_id=exp.id,
            amount=0.0,
            payment_date=date(2026, 10, 2),
            payment_method="Cash",
        )

    with pytest.raises(ValueError, match="exceeds outstanding payable balance"):
        record_expense_payment(
            db_session,
            expense_id=exp.id,
            amount=4500.0,
            payment_date=date(2026, 10, 2),
            payment_method="Cash",
        )

    # 2. Partial payment
    p1 = record_expense_payment(
        db_session,
        expense_id=exp.id,
        amount=2500.0,
        payment_date=date(2026, 10, 2),
        payment_method="Bank Transfer",
        reference_number="NEFT-9988",
        notes="Advance token",
    )
    assert exp.total_paid == 2500.0
    assert exp.outstanding_balance == 1500.0
    assert exp.calculate_status() == "PARTIALLY_PAID"

    # 3. Remaining payment
    p2 = record_expense_payment(
        db_session,
        expense_id=exp.id,
        amount=1500.0,
        payment_date=date(2026, 10, 10),
        payment_method="Cash",
    )
    assert exp.total_paid == 4000.0
    assert exp.outstanding_balance == 0.0
    assert exp.calculate_status() == "PAID"

    # 4. Reversal audit
    rev_p2 = reverse_expense_payment(
        db_session,
        payment_id=p2.id,
        reason="Duplicate entry submitted by mistake",
    )
    assert rev_p2.is_reversed is True
    assert rev_p2.reversal_reason == "Duplicate entry submitted by mistake"
    assert rev_p2.reversed_at is not None

    # Status and balances recalculated
    assert exp.total_paid == 2500.0
    assert exp.outstanding_balance == 1500.0
    assert exp.calculate_status() == "PARTIALLY_PAID"

    # Cannot reverse twice
    with pytest.raises(ValueError, match="already been reversed"):
        reverse_expense_payment(
            db_session,
            payment_id=p2.id,
            reason="Again",
        )


def test_get_expenses_filters_and_summaries(db_session):
    e1 = create_expense(
        db_session,
        description="Main Hall Rent",
        category="Rent",
        amount=20000.0,
        expense_date=date(2026, 9, 1),
        payee="Landlord ABC",
        initial_payment={
            "amount": 20000.0,
            "payment_method": "Bank Transfer",
        },
    )

    e2 = create_expense(
        db_session,
        description="Teacher Salary - Physics",
        category="Salaries & Stipends",
        amount=15000.0,
        expense_date=date(2026, 10, 1),
        payee="Dr. H. C. Verma",
        initial_payment={
            "amount": 10000.0,
            "payment_method": "UPI",
        },
    )

    e3 = create_expense(
        db_session,
        description="Electricity Bill September",
        category="Utilities",
        amount=4000.0,
        expense_date=date(2026, 10, 5),
        payee="Discom West",
        due_date=date(2026, 10, 8),
    )

    # 1. Search filter
    results = get_expenses(db_session, search="physics")
    assert len(results) == 1
    assert results[0].id == e2.id

    # 2. Category filter
    rent_results = get_expenses(db_session, category="Rent")
    assert len(rent_results) == 1
    assert rent_results[0].id == e1.id

    # 3. Status filter
    paid_results = get_expenses(db_session, payment_status="PAID")
    assert len(paid_results) == 1
    assert paid_results[0].id == e1.id

    partial_results = get_expenses(db_session, payment_status="PARTIALLY_PAID")
    assert len(partial_results) == 1
    assert partial_results[0].id == e2.id

    # 4. Payment method filter
    upi_results = get_expenses(db_session, payment_method="UPI")
    assert len(upi_results) == 1
    assert upi_results[0].id == e2.id

    # 5. Date range filter
    oct_results = get_expenses(
        db_session,
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 31),
    )
    assert len(oct_results) == 2

    # 6. Overall summary
    summary = get_expenses_summary(db_session)
    assert summary["total_expenses"] == 39000.0
    assert summary["total_paid"] == 30000.0
    assert summary["total_outstanding"] == 9000.0
    assert summary["count"] == 3


def test_export_expenses_csv(db_session):
    create_expense(
        db_session,
        description="Broadband Internet Fiber",
        category="Internet & Phone",
        amount=1500.0,
        expense_date=date(2026, 10, 1),
        payee="Airtel Fiber",
        initial_payment={
            "amount": 1500.0,
            "payment_method": "UPI",
        },
    )

    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".csv") as tmp:
        path = tmp.name

    count = export_expenses_csv(db_session, path)
    assert count == 1

    with open(path, "r", encoding="utf-8") as f:
        reader = list(csv.reader(f))
        assert reader[0][0] == "ID"
        assert reader[0][1] == "Date"
        assert reader[0][2] == "Description"
        assert len(reader) == 2
        assert "Broadband Internet Fiber" in reader[1]
        assert "1500.00" in reader[1]
