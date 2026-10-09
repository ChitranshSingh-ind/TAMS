from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

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
    statement = (
        select(Student)
        .options(
            joinedload(Student.parent),
            joinedload(Student.batch),
        )
        .where(Student.id == student_id)
    )
    return session.scalar(statement)


def get_students_by_batch(
    session: Session,
    batch_id: int | None = None,
    *,
    include_inactive: bool = False,
) -> list[Student]:

    statement = (
        select(Student)
        .options(
            joinedload(Student.parent),
            joinedload(Student.batch),
        )
    )

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

    return list(session.scalars(statement).unique().all())

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


def update_student_with_parent(
    session: Session,
    student_id: int,
    *,
    admission_number: str | None,
    first_name: str,
    last_name: str | None = None,
    parent_name: str | None = None,
    parent_phone: str | None = None,
    whatsapp_number: str | None = None,
    batch_id: int,
    date_of_birth=None,
    school_name: str | None = None,
    admission_date=None,
    status: str = "ACTIVE",
    notes: str | None = None,
) -> Student | None:
    student = session.get(Student, student_id)
    if student is None:
        return None

    # Check duplicate admission number if changing
    if admission_number and admission_number != student.admission_number:
        existing_student = session.scalar(
            select(Student).where(
                Student.admission_number == admission_number,
                Student.id != student_id,
            )
        )
        if existing_student:
            raise ValueError(
                "A student with this admission number already exists."
            )

    student.admission_number = admission_number.strip() if admission_number else None
    student.first_name = first_name.strip()
    student.last_name = last_name.strip() if last_name else None
    student.batch_id = batch_id
    student.date_of_birth = date_of_birth
    student.school_name = school_name.strip() if school_name else None
    student.admission_date = admission_date
    student.status = status
    student.notes = notes.strip() if notes else None

    # Update or create parent
    if parent_name:
        clean_parent_name = parent_name.strip()
        clean_phone = parent_phone.strip() if parent_phone else None
        clean_whatsapp = whatsapp_number.strip() if whatsapp_number else None

        if student.parent_id:
            parent = session.get(Parent, student.parent_id)
            if parent:
                parent.name = clean_parent_name
                parent.phone = clean_phone
                parent.whatsapp_number = clean_whatsapp
            else:
                parent = Parent(
                    name=clean_parent_name,
                    phone=clean_phone,
                    whatsapp_number=clean_whatsapp,
                )
                session.add(parent)
                session.flush()
                student.parent_id = parent.id
        else:
            parent = Parent(
                name=clean_parent_name,
                phone=clean_phone,
                whatsapp_number=clean_whatsapp,
            )
            session.add(parent)
            session.flush()
            student.parent_id = parent.id

    session.commit()
    session.refresh(student)
    return student