from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.models.batch import Batch
from app.database.models.student import Student
from app.services.batch_service import create_batch
from app.services.student_service import create_student
from app.services.fee_service import create_fee, record_payment, reverse_payment
from app.services.expense_service import (
    create_expense,
    record_expense_payment,
    reverse_expense_payment,
)
from app.services.financial_service import (
    get_financial_summary,
    get_monthly_financial_comparison,
)
from app.services.dashboard_service import get_dashboard_alerts


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        yield session


def test_shared_financial_summary_cash_and_accrual(db_session):
    # Setup batch and students
    batch = create_batch(db_session, "Class 12-PCM")
    s1 = create_student(
        db_session,
        admission_number="ADM-101",
        first_name="Rohan",
        last_name="Verma",
        batch_id=batch.id,
    )
    s2 = create_student(
        db_session,
        admission_number="ADM-102",
        first_name="Priya",
        last_name="Nair",
        batch_id=batch.id,
    )

    # 1. Fees:
    # Fee 1: ₹5,000 billed, ₹3,000 paid via UPI
    f1 = create_fee(
        db_session,
        student_id=s1.id,
        batch_id=batch.id,
        academic_year="2026-2027",
        fee_month=10,
        amount_due=5000.0,
        due_date=date(2026, 10, 10),
    )
    p_fee1 = record_payment(
        db_session,
        fee_id=f1.id,
        amount=3000.0,
        payment_date=date(2026, 10, 5),
        payment_method="UPI",
    )

    # Fee 2: ₹4,000 billed, ₹4,000 paid via Cash
    f2 = create_fee(
        db_session,
        student_id=s2.id,
        batch_id=batch.id,
        academic_year="2026-2027",
        fee_month=10,
        amount_due=4000.0,
        due_date=date(2026, 10, 10),
    )
    p_fee2 = record_payment(
        db_session,
        fee_id=f2.id,
        amount=4000.0,
        payment_date=date(2026, 10, 6),
        payment_method="Cash",
    )

    # 2. Expenses:
    # Expense 1: Coaching Rent ₹6,000 incurred, ₹6,000 paid via Bank Transfer
    e1 = create_expense(
        db_session,
        description="Premises Rent October",
        category="Rent",
        amount=6000.0,
        expense_date=date(2026, 10, 1),
        initial_payment={
            "amount": 6000.0,
            "payment_method": "Bank Transfer",
            "payment_date": date(2026, 10, 1),
        },
    )

    # Expense 2: Study Material Printing ₹2,500 incurred, ₹1,000 paid via UPI (₹1,500 payable)
    e2 = create_expense(
        db_session,
        description="Booklet Printing",
        category="Printing & Stationery",
        amount=2500.0,
        expense_date=date(2026, 10, 3),
        initial_payment={
            "amount": 1000.0,
            "payment_method": "UPI",
            "payment_date": date(2026, 10, 3),
        },
    )

    # 3. Financial Summary Verification
    summary = get_financial_summary(db_session)

    # Cash Inflow: Fee payments = ₹3,000 + ₹4,000 = ₹7,000
    assert summary["fees_collected"] == 7000.0

    # Cash Outflow: Expense payments = ₹6,000 + ₹1,000 = ₹7,000
    assert summary["expenses_paid"] == 7000.0

    # Net Cash Flow = ₹7,000 - ₹7,000 = ₹0.00
    assert summary["net_cash_flow"] == 0.0

    # Accrual Billed: Fees billed = ₹5,000 + ₹4,000 = ₹9,000
    assert summary["fees_billed"] == 9000.0

    # Accrual Incurred: Expenses incurred = ₹6,000 + ₹2,500 = ₹8,500
    assert summary["expenses_incurred"] == 8500.0

    # Net Accrual Operating Margin = ₹9,000 - ₹8,500 = ₹500.00
    assert summary["net_accrual_income"] == 500.0

    # Receivables (Student Outstanding Fees): f1 has ₹2,000 balance, f2 has ₹0 balance
    assert summary["outstanding_student_fees"] == 2000.0

    # Payables (Vendor Outstanding Expenses): e1 has ₹0 balance, e2 has ₹1,500 balance
    assert summary["outstanding_expenses"] == 1500.0


def test_payment_reversal_impact_on_financials(db_session):
    batch = create_batch(db_session, "Class 11")
    s = create_student(db_session, admission_number="ADM-201", first_name="Ananya", batch_id=batch.id)

    f = create_fee(
        db_session,
        student_id=s.id,
        batch_id=batch.id,
        academic_year="2026-2027",
        fee_month=10,
        amount_due=3000.0,
        due_date=date(2026, 10, 15),
    )
    p_fee = record_payment(
        db_session,
        fee_id=f.id,
        amount=3000.0,
        payment_date=date(2026, 10, 5),
        payment_method="UPI",
    )

    exp = create_expense(
        db_session,
        description="Electricity",
        category="Utilities",
        amount=1200.0,
        expense_date=date(2026, 10, 5),
    )
    p_exp = record_expense_payment(
        db_session,
        expense_id=exp.id,
        amount=1200.0,
        payment_date=date(2026, 10, 6),
        payment_method="UPI",
    )

    s_before = get_financial_summary(db_session)
    assert s_before["fees_collected"] == 3000.0
    assert s_before["expenses_paid"] == 1200.0
    assert s_before["net_cash_flow"] == 1800.0

    # Reverse fee payment
    reverse_payment(db_session, payment_id=p_fee.id, reason="Cheque bounced")
    s_mid = get_financial_summary(db_session)
    assert s_mid["fees_collected"] == 0.0
    assert s_mid["expenses_paid"] == 1200.0
    assert s_mid["net_cash_flow"] == -1200.0
    assert s_mid["outstanding_student_fees"] == 3000.0

    # Reverse expense payment
    reverse_expense_payment(db_session, payment_id=p_exp.id, reason="Refunded by utility")
    s_after = get_financial_summary(db_session)
    assert s_after["fees_collected"] == 0.0
    assert s_after["expenses_paid"] == 0.0
    assert s_after["net_cash_flow"] == 0.0
    assert s_after["outstanding_expenses"] == 1200.0


def test_monthly_financial_comparison(db_session):
    batch = create_batch(db_session, "Class 9")
    s = create_student(db_session, admission_number="ADM-301", first_name="Kavya", batch_id=batch.id)

    # August Fee & Payment
    f_aug = create_fee(
        db_session,
        student_id=s.id,
        batch_id=batch.id,
        academic_year="2026-2027",
        fee_month=8,
        amount_due=5000.0,
        due_date=date(2026, 8, 10),
    )
    record_payment(
        db_session,
        fee_id=f_aug.id,
        amount=5000.0,
        payment_date=date(2026, 8, 5),
        payment_method="Cash",
    )

    # August Expense & Payment
    create_expense(
        db_session,
        description="August Cleaning",
        category="Repairs & Maintenance",
        amount=1500.0,
        expense_date=date(2026, 8, 2),
        initial_payment={
            "amount": 1500.0,
            "payment_method": "Cash",
            "payment_date": date(2026, 8, 2),
        },
    )

    # Monthly comparison
    monthly = get_monthly_financial_comparison(db_session)
    aug_data = next((m for m in monthly if "Aug" in m["month_name"]), None)
    assert aug_data is not None
    assert aug_data["fees_collected"] == 5000.0
    assert aug_data["expenses_paid"] == 1500.0
    assert aug_data["net_cash_flow"] == 3500.0
    assert aug_data["fees_billed"] == 5000.0
    assert aug_data["expenses_incurred"] == 1500.0
    assert aug_data["net_accrual_margin"] == 3500.0


def test_dashboard_alerts_include_payables(db_session):
    # When no expense payables exist
    alerts = get_dashboard_alerts(db_session, batch_id=None)
    assert not any("expense payables" in a for a in alerts)

    # Create an unpaid expense
    create_expense(
        db_session,
        description="Office Water Dispenser Refill",
        category="Utilities",
        amount=850.0,
        expense_date=date(2026, 10, 5),
    )

    # Alert should now notify about pending payables
    alerts_after = get_dashboard_alerts(db_session, batch_id=None)
    assert any("₹850 expense payables pending." in a for a in alerts_after)
