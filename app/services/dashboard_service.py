from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models.attendance import Attendance
from app.database.models.fee import Fee
from app.database.models.fee_payment import FeePayment
from app.database.models.student import Student
from app.database.models.test import TestModel


def get_dashboard_alerts(
    session: Session,
    batch_id: int | None = None,
) -> list[str]:

    alerts = []

    # ---------------------------------------------------------
    # 1. Students absent today
    # ---------------------------------------------------------
    absent_statement = (
        select(func.count(Attendance.id))
        .join(
            Student,
            Student.id == Attendance.student_id,
        )
        .where(
            Attendance.date == date.today(),
            Attendance.status == "ABSENT",
            Student.status == "ACTIVE",
        )
    )

    if batch_id is not None:
        absent_statement = absent_statement.where(
            Attendance.batch_id == batch_id
        )

    absent_count = session.scalar(absent_statement) or 0

    if absent_count:
        alerts.append(
            f"{absent_count} student(s) absent today."
        )

    # ---------------------------------------------------------
    # 2. Outstanding fees
    # ---------------------------------------------------------
    fee_statement = (
        select(
            func.coalesce(
                func.sum(Fee.final_amount_due),
                0,
            )
        )
    )

    if batch_id is not None:
        fee_statement = fee_statement.where(
            Fee.batch_id == batch_id
        )

    total_due = session.scalar(fee_statement) or 0

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

    outstanding = float(total_due - total_paid)

    if outstanding > 0:
        alerts.append(
            f"₹{outstanding:,.0f} fees outstanding."
        )

    # ---------------------------------------------------------
    # 3. Upcoming tests
    # ---------------------------------------------------------
    test_statement = (
        select(func.count(TestModel.id))
        .where(
            TestModel.test_date >= date.today()
        )
    )

    if batch_id is not None:
        test_statement = test_statement.where(
            TestModel.batch_id == batch_id
        )

    upcoming_tests = session.scalar(test_statement) or 0

    if upcoming_tests:
        alerts.append(
            f"{upcoming_tests} upcoming test(s) scheduled."
        )

    return alerts