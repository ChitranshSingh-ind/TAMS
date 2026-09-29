from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.student import Student


def create_student(
    session: Session,
    *,
    admission_number: str,
    first_name: str,
    last_name: str | None = None,
    parent_id: int | None = None,
    batch_id: int,
    date_of_birth=None,
    school_name: str | None = None,
    admission_date=None,
    notes: str | None = None,
) -> Student:

    student = Student(
        admission_number=admission_number.strip(),
        first_name=first_name.strip(),
        last_name=last_name.strip() if last_name else None,
        parent_id=parent_id,
        batch_id=batch_id,
        date_of_birth=date_of_birth,
        school_name=school_name,
        admission_date=admission_date,
        notes=notes,
        status="ACTIVE",
    )

    session.add(student)
    session.commit()
    session.refresh(student)

    return student


def get_student(
    session: Session,
    student_id: int,
) -> Student | None:
    return session.get(Student, student_id)


def get_students_by_batch(
    session: Session,
    batch_id: int,
    *,
    include_inactive: bool = False,
) -> list[Student]:

    statement = (
        select(Student)
        .where(Student.batch_id == batch_id)
        .order_by(Student.first_name, Student.last_name)
    )

    if not include_inactive:
        statement = statement.where(Student.status == "ACTIVE")

    return list(session.scalars(statement).all())


def update_student(
    session: Session,
    student_id: int,
    **changes,
) -> Student | None:

    student = session.get(Student, student_id)

    if student is None:
        return None

    allowed_fields = {
        "admission_number",
        "first_name",
        "last_name",
        "parent_id",
        "batch_id",
        "date_of_birth",
        "school_name",
        "admission_date",
        "status",
        "notes",
    }

    for field, value in changes.items():
        if field in allowed_fields:
            if isinstance(value, str):
                value = value.strip()

            setattr(student, field, value)

    session.commit()
    session.refresh(student)

    return student


def archive_student(
    session: Session,
    student_id: int,
) -> Student | None:

    student = session.get(Student, student_id)

    if student is None:
        return None

    student.status = "INACTIVE"

    session.commit()
    session.refresh(student)

    return student