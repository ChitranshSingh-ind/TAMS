from sqlalchemy import select,func
from sqlalchemy.orm import Session

from app.database.models.fee import Fee
from app.database.models.fee_payment import FeePayment


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
    due_date=None,
    status: str = "PENDING",
    notes: str | None = None,
) -> Fee:

    if final_amount_due is None:
        final_amount_due = amount_due - discount

    fee = Fee(
        student_id=student_id,
        batch_id=batch_id,
        academic_year=academic_year,
        fee_month=fee_month,
        amount_due=amount_due,
        discount=discount,
        final_amount_due=final_amount_due,
        due_date=due_date,
        status=status,
        notes=notes,
    )

    session.add(fee)
    session.commit()
    session.refresh(fee)

    return fee


def get_fees_by_batch(
    session: Session,
    batch_id: int | None = None,
) -> list[Fee]:

    statement = (
        select(Fee)
        .order_by(Fee.due_date, Fee.student_id)
    )

    if batch_id is not None:
        statement = statement.where(
            Fee.batch_id == batch_id
        )

    return list(session.scalars(statement).all())
def get_outstanding_amount(
    session: Session,
    batch_id: int | None = None,
) -> float:

    statement = (
        select(
            func.coalesce(
                func.sum(Fee.final_amount_due),
                0,
            )
        )
    )

    if batch_id is not None:
        statement = statement.where(
            Fee.batch_id == batch_id
        )

    total_due = session.scalar(statement) or 0

    payment_statement = (
        select(
            func.coalesce(
                func.sum(FeePayment.amount),
                0,
            )
        )
        .join(
            Fee,
            Fee.id == FeePayment.fee_id,
        )
    )

    if batch_id is not None:
        payment_statement = payment_statement.where(
            Fee.batch_id == batch_id
        )

    total_paid = session.scalar(payment_statement) or 0

    return float(total_due - total_paid)
def get_student_fees(
    session: Session,
    student_id: int,
) -> list[Fee]:

    statement = (
        select(Fee)
        .where(Fee.student_id == student_id)
        .order_by(
            Fee.academic_year.desc(),
            Fee.fee_month.desc(),
        )
    )

    return list(session.scalars(statement).all())
def get_student_fee_summary(
    session: Session,
    student_id: int,
) -> dict[str, float]:

    total_due_statement = (
        select(
            func.coalesce(
                func.sum(Fee.final_amount_due),
                0,
            )
        )
        .where(Fee.student_id == student_id)
    )

    total_due = session.scalar(total_due_statement) or 0

    total_paid_statement = (
        select(
            func.coalesce(
                func.sum(FeePayment.amount),
                0,
            )
        )
        .join(
            Fee,
            Fee.id == FeePayment.fee_id,
        )
        .where(Fee.student_id == student_id)
    )

    total_paid = session.scalar(total_paid_statement) or 0

    outstanding = total_due - total_paid

    return {
        "total_due": float(total_due),
        "total_paid": float(total_paid),
        "outstanding": float(outstanding),
    }