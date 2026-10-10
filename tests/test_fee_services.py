from datetime import date, timedelta
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.models.batch import Batch
from app.database.models.fee import Fee
from app.database.models.fee_payment import FeePayment
from app.database.models.student import Student
from app.services.batch_service import create_batch
from app.services.student_service import create_student
from app.services.fee_service import (
    create_fee,
    generate_monthly_fees,
    get_fee,
    get_fees,
    get_fees_summary,
    record_payment,
    reverse_payment,
    update_fee,
    get_student_fees,
    get_student_fee_summary,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        yield session


def test_create_fee_and_duplicate_prevention(db_session):
    batch = create_batch(db_session, "Class 10-A")
    student = create_student(
        db_session,
        admission_number="ADM001",
        first_name="Aarav",
        last_name="Sharma",
        batch_id=batch.id,
    )

    # 1. Successful creation
    fee = create_fee(
        db_session,
        student_id=student.id,
        batch_id=batch.id,
        academic_year="2026-2027",
        fee_month=10,
        amount_due=2500.0,
        discount=200.0,
        due_date=date(2026, 10, 15),
    )
    assert fee.id is not None
    assert fee.final_amount_due == 2300.0
    assert fee.outstanding_balance == 2300.0
    assert fee.total_paid == 0.0

    # 2. Duplicate obligation prevention
    with pytest.raises(ValueError, match="already exists"):
        create_fee(
            db_session,
            student_id=student.id,
            batch_id=batch.id,
            academic_year="2026-2027",
            fee_month=10,
            amount_due=2500.0,
        )

    # 3. Negative amount validation
    with pytest.raises(ValueError, match="negative"):
        create_fee(
            db_session,
            student_id=student.id,
            batch_id=batch.id,
            academic_year="2026-2027",
            fee_month=11,
            amount_due=-100.0,
        )


def test_monthly_fee_generation_and_preview(db_session):
    batch = create_batch(db_session, "Class 10-B")
    batch.monthly_fee = 1800.0
    db_session.commit()

    # Active student with custom fee
    s1 = create_student(
        db_session,
        admission_number="ADM101",
        first_name="Rohan",
        batch_id=batch.id,
    )
    s1.monthly_fee = 2200.0

    # Active student with default batch fee
    s2 = create_student(
        db_session,
        admission_number="ADM102",
        first_name="Priya",
        batch_id=batch.id,
    )

    # Inactive student (must NOT be charged)
    s3 = create_student(
        db_session,
        admission_number="ADM103",
        first_name="InactiveStudent",
        batch_id=batch.id,
    )
    s3.status = "INACTIVE"

    # Left student (must NOT be charged)
    s4 = create_student(
        db_session,
        admission_number="ADM104",
        first_name="LeftStudent",
        batch_id=batch.id,
    )
    s4.status = "LEFT"
    db_session.commit()

    # 1. Preview generation
    preview = generate_monthly_fees(
        db_session,
        academic_year="2026-2027",
        fee_month=11,
        batch_id=batch.id,
        default_amount=1500.0,
        due_date=date(2026, 11, 10),
        preview_only=True,
    )
    assert preview["eligible_count"] == 2
    assert preview["to_generate_count"] == 2
    # s1 gets 2200, s2 gets batch fee 1800 -> total 4000
    assert preview["total_amount_to_generate"] == 4000.0

    # 2. Actual generation
    result = generate_monthly_fees(
        db_session,
        academic_year="2026-2027",
        fee_month=11,
        batch_id=batch.id,
        default_amount=1500.0,
        due_date=date(2026, 11, 10),
        preview_only=False,
    )
    assert result["generated_count"] == 2
    assert result["total_amount_generated"] == 4000.0

    # 3. Idempotency: Running again skips existing
    result_retry = generate_monthly_fees(
        db_session,
        academic_year="2026-2027",
        fee_month=11,
        batch_id=batch.id,
        default_amount=1500.0,
        due_date=date(2026, 11, 10),
        preview_only=False,
    )
    assert result_retry["generated_count"] == 0
    assert result_retry["skipped_count"] == 2

    # 4. Historical integrity: When student leaves later, historical fee is preserved
    s1.status = "LEFT"
    db_session.commit()
    s1_fees = get_student_fees(db_session, s1.id)
    assert len(s1_fees) == 1
    assert s1_fees[0].final_amount_due == 2200.0


def test_full_and_partial_payments(db_session):
    batch = create_batch(db_session, "Class 9-A")
    student = create_student(
        db_session,
        admission_number="ADM201",
        first_name="Neha",
        batch_id=batch.id,
    )

    fee = create_fee(
        db_session,
        student_id=student.id,
        batch_id=batch.id,
        academic_year="2026-2027",
        fee_month=9,
        amount_due=3000.0,
        due_date=date(2026, 9, 10),
    )
    assert fee.status == "PENDING" or fee.status == "OVERDUE"
    assert fee.outstanding_balance == 3000.0

    # First partial payment: 1000
    p1 = record_payment(
        db_session,
        fee_id=fee.id,
        amount=1000.0,
        payment_date=date(2026, 9, 5),
        payment_method="UPI",
        receipt_number="REC-001",
    )
    assert p1.id is not None
    assert fee.total_paid == 1000.0
    assert fee.outstanding_balance == 2000.0
    assert fee.status == "PARTIALLY_PAID"

    # Second partial payment: 1200
    p2 = record_payment(
        db_session,
        fee_id=fee.id,
        amount=1200.0,
        payment_date=date(2026, 9, 15),
        payment_method="Cash",
    )
    assert fee.total_paid == 2200.0
    assert fee.outstanding_balance == 800.0
    assert fee.status == "PARTIALLY_PAID"

    # Final settlement: 800
    p3 = record_payment(
        db_session,
        fee_id=fee.id,
        amount=800.0,
        payment_date=date(2026, 9, 20),
        payment_method="Bank Transfer",
    )
    assert fee.total_paid == 3000.0
    assert fee.outstanding_balance == 0.0
    assert fee.status == "PAID"


def test_payment_validation_and_overpayment_prevention(db_session):
    batch = create_batch(db_session, "Class 11-Science")
    student = create_student(
        db_session,
        admission_number="ADM301",
        first_name="Aditya",
        batch_id=batch.id,
    )

    fee = create_fee(
        db_session,
        student_id=student.id,
        batch_id=batch.id,
        academic_year="2026-2027",
        fee_month=8,
        amount_due=1500.0,
    )

    # 1. Zero payment
    with pytest.raises(ValueError, match="greater than zero"):
        record_payment(
            db_session,
            fee_id=fee.id,
            amount=0.0,
            payment_date=date.today(),
            payment_method="Cash",
        )

    # 2. Negative payment
    with pytest.raises(ValueError, match="greater than zero"):
        record_payment(
            db_session,
            fee_id=fee.id,
            amount=-50.0,
            payment_date=date.today(),
            payment_method="Cash",
        )

    # 3. Overpayment rejection
    with pytest.raises(ValueError, match="cannot exceed current outstanding balance"):
        record_payment(
            db_session,
            fee_id=fee.id,
            amount=1600.0,
            payment_date=date.today(),
            payment_method="Cash",
        )

    # 4. Duplicate receipt number rejection
    record_payment(
        db_session,
        fee_id=fee.id,
        amount=500.0,
        payment_date=date.today(),
        payment_method="Cash",
        receipt_number="UNIQUE-REC-1",
    )
    with pytest.raises(ValueError, match="already exists"):
        record_payment(
            db_session,
            fee_id=fee.id,
            amount=500.0,
            payment_date=date.today(),
            payment_method="Cash",
            receipt_number="UNIQUE-REC-1",
        )


def test_payment_reversal_and_audit_trail(db_session):
    batch = create_batch(db_session, "Class 12-Commerce")
    student = create_student(
        db_session,
        admission_number="ADM401",
        first_name="Ananya",
        batch_id=batch.id,
    )

    fee = create_fee(
        db_session,
        student_id=student.id,
        batch_id=batch.id,
        academic_year="2026-2027",
        fee_month=7,
        amount_due=2000.0,
        due_date=date.today() - timedelta(days=5),
    )

    pmt = record_payment(
        db_session,
        fee_id=fee.id,
        amount=2000.0,
        payment_date=date.today(),
        payment_method="UPI",
    )
    assert fee.status == "PAID"
    assert fee.outstanding_balance == 0.0

    # 1. Reversal requires reason
    with pytest.raises(ValueError, match="reason must be provided"):
        reverse_payment(db_session, payment_id=pmt.id, reason="   ")

    # 2. Successful reversal
    rev = reverse_payment(
        db_session,
        payment_id=pmt.id,
        reason="Cheque bounced by bank",
    )
    assert rev.is_reversed is True
    assert rev.reversal_reason == "Cheque bounced by bank"
    assert rev.reversed_at is not None

    # Fee status and balance correctly reverted
    assert fee.total_paid == 0.0
    assert fee.outstanding_balance == 2000.0
    # Because due_date was 5 days ago, status is correctly OVERDUE
    assert fee.status == "OVERDUE"

    # 3. Cannot reverse already reversed payment
    with pytest.raises(ValueError, match="already been reversed"):
        reverse_payment(db_session, payment_id=pmt.id, reason="Try again")


def test_fee_adjustments_and_updates(db_session):
    batch = create_batch(db_session, "Class 10-C")
    student = create_student(
        db_session,
        admission_number="ADM501",
        first_name="Kabir",
        batch_id=batch.id,
    )

    fee = create_fee(
        db_session,
        student_id=student.id,
        batch_id=batch.id,
        academic_year="2026-2027",
        fee_month=6,
        amount_due=2000.0,
    )

    record_payment(
        db_session,
        fee_id=fee.id,
        amount=1000.0,
        payment_date=date.today(),
        payment_method="Cash",
    )

    # 1. Successful update: add waiver of 500
    updated = update_fee(
        db_session,
        fee_id=fee.id,
        discount=500.0,
        notes="Sibling discount applied",
    )
    assert updated.final_amount_due == 1500.0
    assert updated.outstanding_balance == 500.0
    assert updated.notes == "Sibling discount applied"

    # 2. Reject reducing fee below already collected amount (1000)
    with pytest.raises(ValueError, match="cannot be less than already collected"):
        update_fee(
            db_session,
            fee_id=fee.id,
            discount=1500.0,  # Net would be 500, but 1000 was collected!
        )


def test_fees_query_filters_and_summaries(db_session):
    b1 = create_batch(db_session, "Batch Alpha")
    b2 = create_batch(db_session, "Batch Beta")

    s1 = create_student(db_session, admission_number="A1", first_name="Dev", batch_id=b1.id)
    s2 = create_student(db_session, admission_number="A2", first_name="Karan", batch_id=b2.id)

    # Fee 1: Overdue
    f1 = create_fee(
        db_session,
        student_id=s1.id,
        batch_id=b1.id,
        academic_year="2026-2027",
        fee_month=1,
        amount_due=1000.0,
        due_date=date.today() - timedelta(days=10),
    )

    # Fee 2: Fully paid
    f2 = create_fee(
        db_session,
        student_id=s2.id,
        batch_id=b2.id,
        academic_year="2026-2027",
        fee_month=1,
        amount_due=2000.0,
        due_date=date.today() + timedelta(days=10),
    )
    record_payment(
        db_session,
        fee_id=f2.id,
        amount=2000.0,
        payment_date=date.today(),
        payment_method="UPI",
    )

    # Test summary
    summary = get_fees_summary(db_session)
    assert summary["total_due"] == 3000.0
    assert summary["total_collected"] == 2000.0
    assert summary["total_outstanding"] == 1000.0
    assert summary["total_overdue"] == 1000.0

    # Test search filter
    dev_fees = get_fees(db_session, search="Dev")
    assert len(dev_fees) == 1
    assert dev_fees[0].id == f1.id

    # Test batch filter
    b2_fees = get_fees(db_session, batch_id=b2.id)
    assert len(b2_fees) == 1
    assert b2_fees[0].id == f2.id

    # Test overdue only
    overdue_fees = get_fees(db_session, overdue_only=True)
    assert len(overdue_fees) == 1
    assert overdue_fees[0].id == f1.id


def test_student_fee_summary(db_session):
    batch = create_batch(db_session, "Class 10")
    student = create_student(db_session, admission_number="STU_SUM", first_name="Tara", batch_id=batch.id)

    create_fee(
        db_session,
        student_id=student.id,
        batch_id=batch.id,
        academic_year="2026-2027",
        fee_month=2,
        amount_due=1200.0,
        due_date=date.today() - timedelta(days=2),
    )
    f2 = create_fee(
        db_session,
        student_id=student.id,
        batch_id=batch.id,
        academic_year="2026-2027",
        fee_month=3,
        amount_due=1200.0,
        due_date=date.today() + timedelta(days=15),
    )
    record_payment(
        db_session,
        fee_id=f2.id,
        amount=600.0,
        payment_date=date.today(),
        payment_method="Cash",
    )

    summary = get_student_fee_summary(db_session, student.id)
    assert summary["total_due"] == 2400.0
    assert summary["total_paid"] == 600.0
    assert summary["outstanding"] == 1800.0
    assert summary["overdue"] == 1200.0
