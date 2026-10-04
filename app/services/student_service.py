from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database.models.student import Student
from app.database.models.parent import Parent


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
    batch_id: int | None = None,
    *,
    include_inactive: bool = False,
) -> list[Student]:

    statement = select(Student)

    if batch_id is not None:
        statement = statement.where(
            Student.batch_id == batch_id
        )

    if not include_inactive:
        statement = statement.where(
            Student.status == "ACTIVE"
        )

    statement = statement.order_by(
        Student.first_name,
        Student.last_name,
    )

    return list(session.scalars(statement).all())

def count_students(session: Session, batch_id: int | None = None) -> int:
    statement = (select(func.count(Student.id)).where(Student.status == "ACTIVE"))
    if batch_id is not None:
        statement = statement.where(Student.batch_id == batch_id)
    return session.scalar(statement) or 0


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
def create_student_with_parent(
    session: Session,
    admission_number: str | None,
    first_name: str,
    last_name: str | None,
    parent_name: str,
    parent_phone: str | None,
    whatsapp_number: str | None,
    batch_id: int,
    date_of_birth,
    school_name: str | None,
    admission_date,
    status: str,
    notes: str | None,
) -> Student:
    # Check duplicate admission number
    if admission_number:
        existing_student = session.scalar(
            select(Student).where(
                Student.admission_number == admission_number
            )
        )

        if existing_student:
            raise ValueError(
                "A student with this admission number already exists."
            )

    # Create parent
    parent = Parent(
        name=parent_name,
        phone=parent_phone,
        whatsapp_number=whatsapp_number,
    )

    session.add(parent)
    session.flush()

    # Create student
    student = Student(
        admission_number=admission_number,
        first_name=first_name,
        last_name=last_name,
        parent_id=parent.id,
        batch_id=batch_id,
        date_of_birth=date_of_birth,
        school_name=school_name,
        admission_date=admission_date,
        status=status,
        notes=notes,
    )

    session.add(student)
    session.commit()
    session.refresh(student)

    return student