"""
TAMS Examination & Test Results Service.

Encapsulates all business logic for academic evaluations:
  - Scheduling exams with assigned maximum marks
  - Querying upcoming and historical tests by batch
  - Recording student scores with validation against maximum marks
  - Automated WhatsApp dispatch for test score announcements
  - Cascade deletion of tests and associated score sheets
"""

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database.models.student import Student
from app.database.models.test import TestModel
from app.database.models.test_result import TestResult


def create_test(
    session: Session,
    *,
    batch_id: int,
    name: str,
    test_date: date,
    max_marks: float | int,
) -> TestModel:
    """
    Creates and persists a new academic test record for a batch.

    Args:
        session: Active database session.
        batch_id: Target batch ID.
        name: Name/topic of the test (e.g. 'Quadratic Equations Midterm').
        test_date: Date the test is administered.
        max_marks: Total possible marks (must be greater than 0).

    Returns:
        The newly created TestModel instance.
    """
    if max_marks <= 0:
        raise ValueError("Maximum marks must be greater than zero.")

    test = TestModel(
        batch_id=batch_id,
        name=name.strip(),
        test_date=test_date,
        max_marks=float(max_marks),
    )

    session.add(test)
    session.commit()
    session.refresh(test)

    return test


def get_upcoming_tests(
    session: Session,
    batch_id: int | None = None,
) -> list[TestModel]:
    """
    Retrieves tests scheduled for today or later, ordered chronologically.

    Args:
        session: Active database session.
        batch_id: Optional batch filter.

    Returns:
        List of upcoming TestModel instances.
    """
    statement = (
        select(TestModel)
        .options(joinedload(TestModel.batch))
        .where(TestModel.test_date >= date.today())
        .order_by(TestModel.test_date)
    )

    if batch_id is not None:
        statement = statement.where(TestModel.batch_id == batch_id)

    return list(session.scalars(statement).all())


def get_tests(
    session: Session,
    batch_id: int | None = None,
) -> list[TestModel]:
    """
    Retrieves all tests ordered newest first, optionally filtered by batch.
    Eagerly loads the batch relationship to eliminate N+1 queries.

    Args:
        session: Active database session.
        batch_id: Optional batch filter.

    Returns:
        List of TestModel records.
    """
    statement = (
        select(TestModel)
        .options(joinedload(TestModel.batch))
        .order_by(
            TestModel.test_date.desc(),
            TestModel.id.desc(),
        )
    )

    if batch_id is not None:
        statement = statement.where(TestModel.batch_id == batch_id)

    return list(session.scalars(statement).all())


def count_upcoming_tests(
    session: Session,
    batch_id: int | None = None,
) -> int:
    """
    Counts the number of tests scheduled on or after today for KPI badges.

    Args:
        session: Active database session.
        batch_id: Optional batch filter.

    Returns:
        Integer count of upcoming tests.
    """
    return len(get_upcoming_tests(session, batch_id=batch_id))


def save_test_results(
    session: Session,
    *,
    test_id: int,
    entries: list[dict[str, Any]],
) -> int:
    """
    Validates, records, and updates student exam scores for a given test.
    Automatically triggers WhatsApp result notification events if configured.

    Args:
        session: Active database session.
        test_id: Target test primary key.
        entries: List of dicts with 'student_id', 'marks', and optional 'remarks'.

    Returns:
        The number of results recorded.

    Raises:
        ValueError: If marks exceed max_marks, if student does not belong to batch,
                    or if the student is not active.
    """
    test = session.get(TestModel, test_id)
    if test is None:
        raise ValueError("The selected test no longer exists.")

    saved_count = 0

    for entry in entries:
        student_id = int(entry["student_id"])
        is_absent = bool(entry.get("is_absent", False))
        marks = float(entry.get("marks", 0.0))
        remarks = str(entry.get("remarks", "")).strip() or None

        # Validate mark range (support negative scoring, ensure <= max_marks)
        if not is_absent and marks > test.max_marks:
            raise ValueError(f"Marks must be at most {test.max_marks}.")

        student = session.get(Student, student_id)
        if student is None or student.batch_id != test.batch_id:
            raise ValueError("A selected student does not belong to this test's batch.")

        # Check for existing result entry
        existing = session.scalar(
            select(TestResult).where(
                TestResult.test_id == test_id,
                TestResult.student_id == student_id,
            )
        )

        if existing is None and student.status != "ACTIVE":
            raise ValueError(
                f"Results can only be entered for active students. "
                f"{student.first_name} {student.last_name or ''} is {student.status.lower()}."
            )

        if existing is None:
            existing = TestResult(
                test_id=test_id,
                student_id=student_id,
                marks=marks if not is_absent else 0.0,
                is_absent=is_absent,
                remarks=remarks,
            )
            session.add(existing)
        else:
            existing.marks = marks if not is_absent else 0.0
            existing.is_absent = is_absent
            existing.remarks = remarks

        saved_count += 1

    session.commit()

    # Trigger automated WhatsApp test score dispatch to parents
    try:
        from app.services.messaging_service import trigger_automation_event
        # Calculate batch average excluding absent students
        valid_entries = [e for e in entries if not e.get("is_absent", False)]
        batch_avg_str = "—"
        if valid_entries:
            b_avg = sum(float(e.get("marks", 0.0)) for e in valid_entries) / len(valid_entries)
            batch_avg_str = f"{b_avg:.1f}"

        for entry in entries:
            if entry.get("is_absent", False):
                continue
            s_id = int(entry["student_id"])
            m_val = float(entry.get("marks", 0.0))
            pct = (m_val / test.max_marks * 100.0) if test.max_marks > 0 else 0.0
            trigger_automation_event(
                session,
                event_type="TEST_RESULT",
                event_data={
                    "marks": f"{m_val:g}",
                    "max_marks": f"{test.max_marks:g}",
                    "percentage": f"{pct:.1f}",
                    "test_name": test.name,
                    "test_date": test.test_date.strftime("%d %b %Y"),
                    "batch_avg": batch_avg_str,
                },
                batch_id=test.batch_id,
                student_id=s_id,
            )
    except Exception:
        # Non-blocking notification dispatch
        pass

    return saved_count


def get_test_results(
    session: Session,
    test_id: int,
) -> list[TestResult]:
    """
    Retrieves all student results for a specific test.

    Args:
        session: Active database session.
        test_id: Primary key of the test.

    Returns:
        List of TestResult records ordered by student ID.
    """
    statement = (
        select(TestResult)
        .options(joinedload(TestResult.student), joinedload(TestResult.test))
        .where(TestResult.test_id == test_id)
        .order_by(TestResult.student_id)
    )
    return list(session.scalars(statement).all())


def get_student_results(
    session: Session,
    student_id: int,
) -> list[TestResult]:
    """
    Retrieves all exam scores for a single student, eagerly loading associated TestModel.

    Args:
        session: Active database session.
        student_id: Primary key of the student.

    Returns:
        List of TestResult entities ordered newest test first.
    """
    statement = (
        select(TestResult)
        .options(joinedload(TestResult.test))
        .join(TestModel, TestResult.test_id == TestModel.id)
        .where(TestResult.student_id == student_id)
        .order_by(TestModel.test_date.desc())
    )

    return list(session.scalars(statement).all())


def delete_test(
    session: Session,
    test_id: int,
) -> bool:
    """
    Cascades and deletes a test and all student results recorded under it.

    Args:
        session: Active database session.
        test_id: Primary key of the test to remove.

    Returns:
        True if deleted successfully, False if test was not found.
    """
    test = session.get(TestModel, test_id)
    if test is None:
        return False

    session.delete(test)
    session.commit()
    return True