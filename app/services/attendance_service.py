from datetime import date

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
        attendance = Attendance(
            student_id=student_id,
            batch_id=batch_id,
            date=attendance_date,
            status=status,
            remarks=remarks,
        )
        session.add(attendance)
    else:
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
    Save or update attendance for all students in a batch in a single atomic transaction.
    attendance_records maps student_id -> status ('PRESENT', 'ABSENT', etc.).
    """
    if not attendance_records:
        return 0

    student_ids = list(attendance_records.keys())
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
        pass

    return saved_count


def get_attendance_by_date(
    session: Session,
    attendance_date: date,
    batch_id: int | None = None,
) -> list[Attendance]:

    statement = (
        select(Attendance)
        .where(Attendance.date == attendance_date)
        .order_by(Attendance.student_id)
    )

    if batch_id is not None:
        statement = statement.where(
            Attendance.batch_id == batch_id
        )

    return list(session.scalars(statement).all())

def get_student_attendance(
    session: Session,
    student_id: int,
) -> list[Attendance]:

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

    statement = (
        select(Attendance)
        .where(
            Attendance.date == attendance_date,
            Attendance.status == "PRESENT",
        )
    )

    if batch_id is not None:
        statement = statement.where(
            Attendance.batch_id == batch_id
        )

    return len(session.scalars(statement).all())
def get_student_attendance_summary(
    session: Session,
    student_id: int,
) -> dict[str, int | float]:
    attendance_records = get_student_attendance(
        session,
        student_id,
    )

    total = len(attendance_records)

    present = sum(
        1
        for record in attendance_records
        if record.status == "PRESENT"
    )

    absent = sum(
        1
        for record in attendance_records
        if record.status == "ABSENT"
    )

    late = sum(
        1
        for record in attendance_records
        if record.status == "LATE"
    )

    leave = sum(
        1
        for record in attendance_records
        if record.status == "LEAVE"
    )

    percentage = (
        (present / total) * 100
        if total > 0
        else 0.0
    )

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
    statement = (
        select(AttendanceOverride)
        .where(
            AttendanceOverride.batch_id == batch_id,
            AttendanceOverride.date == override_date,
        )
    )

    return session.scalar(statement)