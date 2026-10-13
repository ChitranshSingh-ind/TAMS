"""
TAMS Attendance Service Layer.

Provides business logic for tracking student attendance:
  - Marking single and batch attendance (atomic multi-student updates)
  - Automatic notification triggers for absent students (WhatsApp integration)
  - Querying daily attendance rosters and individual student history
  - Calculating student attendance percentages and metric summaries (Present, Absent, Late, Leave)
  - Handling unscheduled class date overrides (extra classes outside default batch days)
"""

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.attendance import Attendance
from app.database.models.attendance_override import AttendanceOverride


def mark_attendance(
    session: Session,
    *,
    student_id: int,
    batch_id: int,
    attendance_date: date,
    status: str,
    remarks: str | None = None,
) -> Attendance:
    """
    Records or updates attendance status for an individual student on a specific date.

    Args:
        session: Active database session.
        student_id: ID of the student.
        batch_id: ID of the batch.
        attendance_date: Calendar date of attendance.
        status: Attendance status ('PRESENT', 'ABSENT', 'LATE', 'LEAVE').
        remarks: Optional teacher notes or explanation.

    Returns:
        The created or updated Attendance record.
    """
    # Check if an attendance record already exists for this student on this date
    statement = (
        select(Attendance)
        .where(
            Attendance.student_id == student_id,
            Attendance.batch_id == batch_id,
            Attendance.date == attendance_date,
        )
    )
    attendance = session.scalar(statement)

    if attendance is None:
        # Create a new record if none exists
        attendance = Attendance(
            student_id=student_id,
            batch_id=batch_id,
            date=attendance_date,
            status=status,
            remarks=remarks,
        )
        session.add(attendance)
    else:
        # Update existing record
        attendance.status = status
        attendance.remarks = remarks

    session.commit()
    session.refresh(attendance)

    return attendance


def save_batch_attendance(
    session: Session,
    *,
    batch_id: int,
    attendance_date: date,
    attendance_records: dict[int, str],
) -> int:
    """
    Saves or updates attendance for all students in a batch within a single atomic transaction.
    Also dispatches automated WhatsApp absence alerts to parents when enabled.

    Args:
        session: Active database session.
        batch_id: Target batch ID.
        attendance_date: Date being recorded.
        attendance_records: Mapping of student_id -> status ('PRESENT', 'ABSENT', etc.).

    Returns:
        The total count of student records updated/inserted.
    """
    if not attendance_records:
        return 0

    student_ids = list(attendance_records.keys())

    # Pre-fetch existing records for this batch/date to avoid N+1 individual queries
    existing_statement = (
        select(Attendance)
        .where(
            Attendance.batch_id == batch_id,
            Attendance.date == attendance_date,
            Attendance.student_id.in_(student_ids),
        )
    )
    existing_records = {
        record.student_id: record
        for record in session.scalars(existing_statement).all()
    }

    saved_count = 0
    # Process each student status in batch
    for student_id, status in attendance_records.items():
        if status is None:
            continue

        record = existing_records.get(student_id)
        if record is None:
            record = Attendance(
                student_id=student_id,
                batch_id=batch_id,
                date=attendance_date,
                status=status,
            )
            session.add(record)
        else:
            record.status = status
        saved_count += 1

    session.commit()

    # Trigger automated WhatsApp absence notifications if configured
    try:
        from app.services.messaging_service import trigger_automation_event
        for student_id, status in attendance_records.items():
            if status == "ABSENT":
                trigger_automation_event(
                    session,
                    event_type="ABSENCE",
                    event_data={"date": attendance_date.strftime("%d %b %Y")},
                    batch_id=batch_id,
                    student_id=student_id,
                )
    except Exception:
        # Non-blocking: background messaging failure should never roll back attendance
        pass

    return saved_count


def get_attendance_by_date(
    session: Session,
    attendance_date: date,
    batch_id: int | None = None,
) -> list[Attendance]:
    """
    Retrieves all attendance records for a specific date, optionally filtered by batch.

    Args:
        session: Active database session.
        attendance_date: Target calendar date.
        batch_id: Optional batch filter.

    Returns:
        List of matching Attendance entries.
    """
    statement = (
        select(Attendance)
        .where(Attendance.date == attendance_date)
        .order_by(Attendance.student_id)
    )

    if batch_id is not None:
        statement = statement.where(Attendance.batch_id == batch_id)

    return list(session.scalars(statement).all())


def get_student_attendance(
    session: Session,
    student_id: int,
) -> list[Attendance]:
    """
    Retrieves the complete historical attendance trail for a student, ordered newest first.

    Args:
        session: Active database session.
        student_id: Target student ID.

    Returns:
        Chronological list of Attendance records.
    """
    statement = (
        select(Attendance)
        .where(Attendance.student_id == student_id)
        .order_by(Attendance.date.desc())
    )

    return list(session.scalars(statement).all())


def count_present_students(
    session: Session,
    attendance_date: date,
    batch_id: int | None = None,
) -> int:
    """
    Counts the number of students marked 'PRESENT' on a specific date.
    Used for live Dashboard KPI card calculations.

    Args:
        session: Active database session.
        attendance_date: Date to inspect.
        batch_id: Optional batch filter.

    Returns:
        Integer count of present students.
    """
    statement = (
        select(Attendance)
        .where(
            Attendance.date == attendance_date,
            Attendance.status == "PRESENT",
        )
    )

    if batch_id is not None:
        statement = statement.where(Attendance.batch_id == batch_id)

    return len(session.scalars(statement).all())


def get_student_attendance_summary(
    session: Session,
    student_id: int,
) -> dict[str, Any]:
    """
    Computes aggregated attendance metrics for a student:
    total classes, counts for each status, and attendance percentage.

    Args:
        session: Active database session.
        student_id: Target student ID.

    Returns:
        Dict with total, present, absent, late, leave counts and rounded percentage.
    """
    attendance_records = get_student_attendance(session, student_id)

    total = len(attendance_records)
    present = sum(1 for r in attendance_records if r.status == "PRESENT")
    absent = sum(1 for r in attendance_records if r.status == "ABSENT")
    late = sum(1 for r in attendance_records if r.status == "LATE")
    leave = sum(1 for r in attendance_records if r.status == "LEAVE")

    percentage = ((present / total) * 100) if total > 0 else 0.0

    return {
        "total": total,
        "present": present,
        "absent": absent,
        "late": late,
        "leave": leave,
        "percentage": round(percentage, 1),
    }


def create_attendance_override(
    session: Session,
    *,
    batch_id: int,
    override_date: date,
    reason: str | None = None,
) -> AttendanceOverride:
    """
    Registers an extra class date override for a batch, allowing attendance to be taken
    on days outside the batch's regular weekly schedule.

    Args:
        session: Active database session.
        batch_id: Target batch ID.
        override_date: Date to permit attendance taking.
        reason: Optional description (e.g. 'Exam Revision Class').

    Returns:
        The created AttendanceOverride instance.
    """
    override = AttendanceOverride(
        batch_id=batch_id,
        date=override_date,
        reason=reason,
    )

    session.add(override)
    session.commit()
    session.refresh(override)

    return override


def get_attendance_override(
    session: Session,
    *,
    batch_id: int,
    override_date: date,
) -> AttendanceOverride | None:
    """
    Checks if a given calendar date has an active class day override for the batch.

    Args:
        session: Active database session.
        batch_id: Target batch ID.
        override_date: Calendar date to check.

    Returns:
        The AttendanceOverride record if one exists, otherwise None.
    """
    statement = (
        select(AttendanceOverride)
        .where(
            AttendanceOverride.batch_id == batch_id,
            AttendanceOverride.date == override_date,
        )
    )

    return session.scalar(statement)