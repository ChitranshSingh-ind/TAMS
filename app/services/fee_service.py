from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.fee import Fee


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