from datetime import date, datetime, UTC
from decimal import Decimal
import uuid
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database.models.batch import Batch
from app.database.models.fee import Fee
from app.database.models.fee_payment import FeePayment
from app.database.models.student import Student


def _to_decimal(val: float | int | Decimal | None) -> Decimal:
    if val is None:
        return Decimal("0.00")
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def generate_receipt_number() -> str:
    now_str = datetime.now(UTC).strftime("%Y%m%d")
    short_uuid = uuid.uuid4().hex[:6].upper()
    return f"REC-{now_str}-{short_uuid}"


def create_fee(
    session: Session,
    *,
    student_id: int,
    batch_id: int,
    academic_year: str,
    fee_month: int,
    amount_due: float,
    discount: float = 0,
    final_amount_due: float | None = None,
    due_date: date | None = None,
    status: str | None = None,
    notes: str | None = None,
) -> Fee:
    # Check if student exists
    student = session.get(Student, student_id)
    if student is None:
        raise ValueError(f"Student with ID {student_id} does not exist.")

    # Check for duplicate obligation for same student, year, month
    existing = session.scalars(
        select(Fee).where(
            Fee.student_id == student_id,
            Fee.academic_year == academic_year,
            Fee.fee_month == fee_month,
        )
    ).first()
    if existing is not None:
        raise ValueError(
            f"A fee obligation already exists for student ID {student_id} in {academic_year} month {fee_month}."
        )

    amt_dec = _to_decimal(amount_due)
    disc_dec = _to_decimal(discount)
    if disc_dec < Decimal("0.00"):
        raise ValueError("Discount cannot be negative.")
    if amt_dec < Decimal("0.00"):
        raise ValueError("Amount due cannot be negative.")

    if final_amount_due is None:
        final_dec = max(Decimal("0.00"), amt_dec - disc_dec)
    else:
        final_dec = max(Decimal("0.00"), _to_decimal(final_amount_due))

    computed_status = status
    if not computed_status:
        if final_dec <= Decimal("0.00"):
            computed_status = "PAID"
        elif due_date and due_date < date.today():
            computed_status = "OVERDUE"
        else:
            computed_status = "PENDING"

    fee = Fee(
        student_id=student_id,
        batch_id=batch_id,
        academic_year=academic_year,
        fee_month=fee_month,
        amount_due=float(amt_dec),
        discount=float(disc_dec),
        final_amount_due=float(final_dec),
        due_date=due_date,
        status=computed_status,
        notes=notes,
    )

    session.add(fee)
    session.commit()
    session.refresh(fee)
    return fee


def get_fee(session: Session, fee_id: int) -> Fee | None:
    statement = (
        select(Fee)
        .options(
            joinedload(Fee.student),
            joinedload(Fee.batch),
            selectinload(Fee.payments),
        )
        .where(Fee.id == fee_id)
    )
    return session.scalars(statement).first()


def get_fees_by_batch(
    session: Session,
    batch_id: int | None = None,
) -> list[Fee]:
    statement = (
        select(Fee)
        .options(
            joinedload(Fee.student),
            joinedload(Fee.batch),
            selectinload(Fee.payments),
        )
        .order_by(Fee.due_date.desc(), Fee.student_id)
    )

    if batch_id is not None:
        statement = statement.where(Fee.batch_id == batch_id)

    return list(session.scalars(statement).all())


def get_fees(
    session: Session,
    *,
    batch_id: int | None = None,
    fee_month: int | None = None,
    academic_year: str | None = None,
    status: str | None = None,
    search: str | None = None,
    overdue_only: bool = False,
) -> list[Fee]:
    statement = (
        select(Fee)
        .join(Student, Student.id == Fee.student_id)
        .join(Batch, Batch.id == Fee.batch_id)
        .options(
            joinedload(Fee.student),
            joinedload(Fee.batch),
            selectinload(Fee.payments),
        )
    )

    if batch_id is not None:
        statement = statement.where(Fee.batch_id == batch_id)

    if fee_month is not None:
        statement = statement.where(Fee.fee_month == fee_month)

    if academic_year is not None:
        statement = statement.where(Fee.academic_year == academic_year)

    if search:
        search_term = f"%{search.strip().lower()}%"
        statement = statement.where(
            func.lower(Student.first_name).like(search_term)
            | func.lower(Student.last_name).like(search_term)
            | func.lower(Student.admission_number).like(search_term)
        )

    statement = statement.order_by(
        Fee.academic_year.desc(),
        Fee.fee_month.desc(),
        Student.first_name.asc(),
    )

    fees = list(session.scalars(statement).all())

    today = date.today()
    results = []
    for fee in fees:
        calc_status = fee.calculate_status(today)
        # Update status in object if it changed
        if fee.status != calc_status:
            fee.status = calc_status

        if overdue_only and calc_status != "OVERDUE":
            continue

        if status and status != "ALL":
            if status == "OVERDUE" and calc_status != "OVERDUE":
                continue
            elif status == "PAID" and calc_status != "PAID":
                continue
            elif status == "PARTIALLY_PAID" and calc_status != "PARTIALLY_PAID":
                continue
            elif status in ("PENDING", "UNPAID") and calc_status not in ("PENDING", "UNPAID"):
                continue

        results.append(fee)

    return results


def get_fees_summary(
    session: Session,
    *,
    batch_id: int | None = None,
    fee_month: int | None = None,
    academic_year: str | None = None,
    search: str | None = None,
) -> dict[str, float]:
    fees = get_fees(
        session,
        batch_id=batch_id,
        fee_month=fee_month,
        academic_year=academic_year,
        search=search,
    )

    total_due = Decimal("0.00")
    total_collected = Decimal("0.00")
    total_outstanding = Decimal("0.00")
    total_overdue = Decimal("0.00")
    today = date.today()

    for fee in fees:
        final_due = _to_decimal(fee.final_amount_due)
        paid = _to_decimal(fee.total_paid)
        balance = max(Decimal("0.00"), final_due - paid)

        total_due += final_due
        total_collected += paid
        total_outstanding += balance

        if fee.due_date and fee.due_date < today and balance > Decimal("0.00"):
            total_overdue += balance

    return {
        "total_due": float(total_due),
        "total_collected": float(total_collected),
        "total_outstanding": float(total_outstanding),
        "total_overdue": float(total_overdue),
    }


def get_outstanding_amount(
    session: Session,
    batch_id: int | None = None,
) -> float:
    summary = get_fees_summary(session, batch_id=batch_id)
    return summary["total_outstanding"]


def get_student_fees(
    session: Session,
    student_id: int,
) -> list[Fee]:
    statement = (
        select(Fee)
        .options(
            joinedload(Fee.student),
            joinedload(Fee.batch),
            selectinload(Fee.payments),
        )
        .where(Fee.student_id == student_id)
        .order_by(
            Fee.academic_year.desc(),
            Fee.fee_month.desc(),
        )
    )
    fees = list(session.scalars(statement).all())
    today = date.today()
    for fee in fees:
        calc_status = fee.calculate_status(today)
        if fee.status != calc_status:
            fee.status = calc_status
    return fees


def get_student_fee_summary(
    session: Session,
    student_id: int,
) -> dict[str, float]:
    fees = get_student_fees(session, student_id)
    total_due = Decimal("0.00")
    total_paid = Decimal("0.00")
    outstanding = Decimal("0.00")
    overdue = Decimal("0.00")
    today = date.today()

    for fee in fees:
        f_due = _to_decimal(fee.final_amount_due)
        f_paid = _to_decimal(fee.total_paid)
        bal = max(Decimal("0.00"), f_due - f_paid)

        total_due += f_due
        total_paid += f_paid
        outstanding += bal

        if fee.due_date and fee.due_date < today and bal > Decimal("0.00"):
            overdue += bal

    return {
        "total_due": float(total_due),
        "total_paid": float(total_paid),
        "outstanding": float(outstanding),
        "overdue": float(overdue),
    }


def generate_monthly_fees(
    session: Session,
    *,
    academic_year: str,
    fee_month: int,
    batch_id: int | None = None,
    default_amount: float,
    due_date: date | None = None,
    preview_only: bool = False,
) -> dict:
    if default_amount < 0:
        raise ValueError("Default fee amount cannot be negative.")

    # Fetch active students
    student_query = (
        select(Student)
        .join(Batch, Batch.id == Student.batch_id)
        .options(joinedload(Student.batch))
        .where(Student.status == "ACTIVE")
    )
    if batch_id is not None:
        student_query = student_query.where(Student.batch_id == batch_id)

    student_query = student_query.order_by(Student.first_name, Student.last_name)
    students = list(session.scalars(student_query).all())

    # Fetch existing fees for this year and month for active students in scope
    student_ids = [s.id for s in students]
    existing_student_ids: set[int] = set()
    if student_ids:
        existing_fees_query = (
            select(Fee.student_id)
            .where(
                Fee.academic_year == academic_year,
                Fee.fee_month == fee_month,
                Fee.student_id.in_(student_ids),
            )
        )
        existing_student_ids = set(session.scalars(existing_fees_query).all())

    preview_items = []
    eligible_students = []
    total_amount_to_generate = Decimal("0.00")

    for student in students:
        batch_fee = student.batch.monthly_fee if (student.batch and student.batch.monthly_fee) else None
        student_fee = student.monthly_fee if student.monthly_fee else None

        applicable_amount = Decimal(str(default_amount))
        if student_fee is not None and student_fee > 0:
            applicable_amount = Decimal(str(student_fee))
        elif batch_fee is not None and batch_fee > 0:
            applicable_amount = Decimal(str(batch_fee))

        already_exists = student.id in existing_student_ids
        status_label = "ALREADY_EXISTS" if already_exists else "READY"

        if not already_exists:
            total_amount_to_generate += applicable_amount
            eligible_students.append((student, applicable_amount))

        student_name = f"{student.first_name} {student.last_name or ''}".strip()
        preview_items.append({
            "student_id": student.id,
            "student_name": student_name,
            "admission_number": student.admission_number,
            "batch_name": student.batch.name if student.batch else "No Batch",
            "amount": float(applicable_amount),
            "due_date": due_date,
            "status": status_label,
        })

    if preview_only:
        return {
            "eligible_count": len(students),
            "already_generated_count": len(existing_student_ids),
            "to_generate_count": len(eligible_students),
            "total_amount_to_generate": float(total_amount_to_generate),
            "preview_items": preview_items,
        }

    # Perform transactional generation
    generated_fees = []
    for student, applicable_amount in eligible_students:
        initial_status = "PENDING"
        if applicable_amount <= Decimal("0.00"):
            initial_status = "PAID"
        elif due_date and due_date < date.today():
            initial_status = "OVERDUE"

        fee = Fee(
            student_id=student.id,
            batch_id=student.batch_id,
            academic_year=academic_year,
            fee_month=fee_month,
            amount_due=float(applicable_amount),
            discount=0.0,
            final_amount_due=float(applicable_amount),
            due_date=due_date,
            status=initial_status,
            notes=None,
        )
        session.add(fee)
        generated_fees.append(fee)

    session.commit()
    for fee in generated_fees:
        session.refresh(fee)

    return {
        "generated_count": len(generated_fees),
        "skipped_count": len(existing_student_ids),
        "total_amount_generated": float(total_amount_to_generate),
        "fee_ids": [f.id for f in generated_fees],
    }


def record_payment(
    session: Session,
    *,
    fee_id: int,
    amount: float,
    payment_date: date,
    payment_method: str,
    receipt_number: str | None = None,
    notes: str | None = None,
) -> FeePayment:
    amt_dec = _to_decimal(amount)
    if amt_dec <= Decimal("0.00"):
        raise ValueError("Payment amount must be greater than zero.")

    fee = get_fee(session, fee_id)
    if fee is None:
        raise ValueError(f"Fee with ID {fee_id} does not exist.")

    current_outstanding = _to_decimal(fee.outstanding_balance)
    if amt_dec > current_outstanding:
        raise ValueError(
            f"Payment amount (₹{amt_dec:,.2f}) cannot exceed current outstanding balance (₹{current_outstanding:,.2f})."
        )

    clean_receipt = receipt_number.strip() if receipt_number else None
    if not clean_receipt:
        clean_receipt = generate_receipt_number()
    else:
        # Check uniqueness of receipt number
        existing_receipt = session.scalars(
            select(FeePayment).where(FeePayment.receipt_number == clean_receipt)
        ).first()
        if existing_receipt is not None:
            raise ValueError(f"Receipt number '{clean_receipt}' already exists. Please provide a unique receipt number.")

    payment = FeePayment(
        fee_id=fee_id,
        amount=float(amt_dec),
        payment_date=payment_date,
        payment_method=payment_method,
        receipt_number=clean_receipt,
        notes=notes.strip() if notes else None,
        is_reversed=False,
    )
    session.add(payment)

    # Calculate resulting status
    new_outstanding = current_outstanding - amt_dec
    if new_outstanding <= Decimal("0.00"):
        fee.status = "PAID"
    else:
        fee.status = "PARTIALLY_PAID"

    session.commit()
    session.refresh(payment)
    session.refresh(fee)

    try:
        from app.services.messaging_service import trigger_automation_event
        trigger_automation_event(
            session,
            event_type="PAYMENT_RECEIPT",
            event_data={
                "amount": f"{amount:,.2f}",
                "payment_mode": payment_method,
                "receipt_no": clean_receipt,
            },
            batch_id=fee.batch_id,
            student_id=fee.student_id,
            source_record_id=payment.id,
        )
    except Exception:
        pass

    return payment


def reverse_payment(
    session: Session,
    *,
    payment_id: int,
    reason: str,
) -> FeePayment:
    if not reason or not reason.strip():
        raise ValueError("A reason must be provided to reverse a payment.")

    payment = session.get(FeePayment, payment_id)
    if payment is None:
        raise ValueError(f"Payment with ID {payment_id} does not exist.")

    if payment.is_reversed:
        raise ValueError(f"Payment with ID {payment_id} has already been reversed.")

    fee = get_fee(session, payment.fee_id)
    if fee is None:
        raise ValueError(f"Associated Fee record with ID {payment.fee_id} not found.")

    payment.is_reversed = True
    payment.reversal_reason = reason.strip()
    payment.reversed_at = datetime.now(UTC)

    # Recalculate status
    fee.status = fee.calculate_status()

    session.commit()
    session.refresh(payment)
    session.refresh(fee)
    return payment


def get_fee_payments(
    session: Session,
    *,
    fee_id: int | None = None,
    student_id: int | None = None,
    batch_id: int | None = None,
    include_reversed: bool = True,
) -> list[FeePayment]:
    statement = (
        select(FeePayment)
        .join(Fee, Fee.id == FeePayment.fee_id)
        .join(Student, Student.id == Fee.student_id)
        .options(
            joinedload(FeePayment.fee).joinedload(Fee.student),
            joinedload(FeePayment.fee).joinedload(Fee.batch),
        )
    )

    if fee_id is not None:
        statement = statement.where(FeePayment.fee_id == fee_id)
    if student_id is not None:
        statement = statement.where(Fee.student_id == student_id)
    if batch_id is not None:
        statement = statement.where(Fee.batch_id == batch_id)
    if not include_reversed:
        statement = statement.where(FeePayment.is_reversed.is_(False))

    statement = statement.order_by(
        FeePayment.payment_date.desc(),
        FeePayment.id.desc(),
    )
    return list(session.scalars(statement).all())


def update_fee(
    session: Session,
    *,
    fee_id: int,
    amount_due: float | None = None,
    discount: float | None = None,
    due_date: date | None = None,
    notes: str | None = None,
) -> Fee:
    fee = get_fee(session, fee_id)
    if fee is None:
        raise ValueError(f"Fee with ID {fee_id} does not exist.")

    amt_dec = _to_decimal(amount_due if amount_due is not None else fee.amount_due)
    disc_dec = _to_decimal(discount if discount is not None else fee.discount)

    if amt_dec < Decimal("0.00"):
        raise ValueError("Amount due cannot be negative.")
    if disc_dec < Decimal("0.00"):
        raise ValueError("Discount cannot be negative.")

    final_dec = max(Decimal("0.00"), amt_dec - disc_dec)
    total_paid_dec = _to_decimal(fee.total_paid)

    if final_dec < total_paid_dec:
        raise ValueError(
            f"Updated fee amount (₹{final_dec:,.2f}) cannot be less than already collected payments (₹{total_paid_dec:,.2f})."
        )

    fee.amount_due = float(amt_dec)
    fee.discount = float(disc_dec)
    fee.final_amount_due = float(final_dec)
    if due_date is not None:
        fee.due_date = due_date
    if notes is not None:
        fee.notes = notes

    fee.status = fee.calculate_status()

    session.commit()
    session.refresh(fee)
    return fee