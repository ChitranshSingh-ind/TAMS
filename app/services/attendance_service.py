from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.attendance import Attendance


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