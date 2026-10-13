"""
TAMS Dashboard Alerts Service.

Aggregates operational reminders and urgent notifications across coaching domains:
  - Daily unexcused absences
  - Overdue student tuition fee balances
  - Upcoming scheduled tests and diagnostic assessments
  - Unpaid operational expense liabilities
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models.attendance import Attendance
from app.database.models.student import Student
from app.database.models.test import TestModel
from app.services.fee_service import get_outstanding_amount


def get_dashboard_alerts(
    session: Session,
    batch_id: int | None = None,
) -> list[str]:
    """
    Evaluates system status and returns a formatted list of human-readable alert strings
    displayed in the Dashboard 'Alerts & Notifications' card.

    Args:
        session: Active database session.
        batch_id: Optional batch filter (if None, summarizes all batches).

    Returns:
        List of formatted alert messages (e.g. ['2 student(s) absent today.']).
    """

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
    outstanding = get_outstanding_amount(session, batch_id=batch_id)

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

    # ---------------------------------------------------------
    # 4. Outstanding expense payables
    # ---------------------------------------------------------
    if batch_id is None:
        try:
            from app.services.expense_service import get_expenses_summary
            exp_summary = get_expenses_summary(session)
            if exp_summary["total_outstanding"] > 0:
                alerts.append(
                    f"₹{exp_summary['total_outstanding']:,.0f} expense payables pending."
                )
        except Exception:
            pass

    return alerts