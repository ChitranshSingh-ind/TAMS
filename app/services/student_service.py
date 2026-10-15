import re
from datetime import date
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, joinedload

from app.database.models.batch import Batch
from app.database.models.parent import Parent
from app.database.models.student import Student


def generate_next_admission_number(session: Session, prefix: str = "ADM") -> str:
    """
    Generate the next unique, sequential admission number for a student.

    Looks up existing admission numbers in the database to find the highest
    sequence index for the current year or matching prefix, and increments it.
    If numbers exist with pattern {PREFIX}-{YYYY}-{INDEX:04d} or {PREFIX}{INDEX},
    it calculates the next unused number. Guarantees that the returned number
    does not collide with any existing record in the database.

    Args:
        session: Active SQLAlchemy database session.
        prefix: Institutional prefix for the admission number (defaults to 'ADM').

    Returns:
        A unique string admission number, e.g., 'ADM-2026-0001'.
    """
    current_year = date.today().year
    year_prefix = f"{prefix}-{current_year}-"

    # Query all non-empty admission numbers from the database
    existing_numbers = set(
        session.scalars(
            select(Student.admission_number).where(
                Student.admission_number.isnot(None)
            )
        ).all()
    )

    # First attempt: find highest numeric suffix matching {prefix}-{current_year}-XXXX
    max_seq = 0
    pattern_year = re.compile(rf"^{re.escape(prefix)}-{current_year}-(\d+)$", re.IGNORECASE)

    for adm in existing_numbers:
        match_year = pattern_year.match(adm)
        if match_year:
            try:
                seq = int(match_year.group(1))
                if seq > max_seq:
                    max_seq = seq
            except ValueError:
                pass

    # Increment and find the first non-colliding admission number (starts at 0001 if none in current year)
    candidate_seq = max_seq + 1
    while True:
        candidate = f"{year_prefix}{candidate_seq:04d}"
        if candidate not in existing_numbers:
            return candidate
        candidate_seq += 1



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
    monthly_fee: float | None = None,
) -> Student:
    # Check duplicate admission number
    if admission_number:
        clean_adm = admission_number.strip()
        existing_student = session.scalar(
            select(Student).where(
                Student.admission_number == clean_adm
            )
        )

        if existing_student:
            raise ValueError(
                "A student with this admission number already exists."
            )
        admission_number = clean_adm

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
        monthly_fee=monthly_fee,
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
    admission_number: str | None = None,
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
    monthly_fee: float | None = None,
) -> Student | None:
    student = session.get(Student, student_id)
    if student is None:
        return None

    # Check duplicate admission number if changing
    if admission_number is not None:
        clean_adm = admission_number.strip()
        if not clean_adm:
            raise ValueError("Admission number cannot be empty.")
        if clean_adm != student.admission_number:
            existing_student = session.scalar(
                select(Student).where(
                    Student.admission_number == clean_adm,
                    Student.id != student_id,
                )
            )
            if existing_student:
                raise ValueError(
                    "A student with this admission number already exists."
                )
        student.admission_number = clean_adm

    student.first_name = first_name.strip()
    student.last_name = last_name.strip() if last_name else None
    student.batch_id = batch_id
    student.date_of_birth = date_of_birth
    student.school_name = school_name.strip() if school_name else None
    student.admission_date = admission_date
    student.status = status
    student.notes = notes.strip() if notes else None
    if monthly_fee is not None:
        student.monthly_fee = monthly_fee

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


def bulk_update_student_batch(
    session: Session,
    student_ids: list[int],
    new_batch_id: int,
) -> int:
    """
    Update the enrolled batch for multiple students simultaneously.

    Transfers a group of students into a new batch while preserving their
    individual IDs, profile information, and historical records.

    Args:
        session: Active SQLAlchemy database session.
        student_ids: List of student primary key IDs to transfer.
        new_batch_id: Target batch primary key ID.

    Returns:
        The total count of student records updated.

    Raises:
        ValueError: If target batch does not exist.
    """
    if not student_ids:
        return 0

    target_batch = session.get(Batch, new_batch_id)
    if target_batch is None:
        raise ValueError(f"Target batch with ID {new_batch_id} does not exist.")

    statement = (
        update(Student)
        .where(Student.id.in_(student_ids))
        .values(batch_id=new_batch_id)
    )
    result = session.execute(statement)
    session.commit()
    return result.rowcount


def bulk_update_student_status(
    session: Session,
    student_ids: list[int],
    new_status: str,
) -> int:
    """
    Update the enrollment lifecycle status for multiple students simultaneously.

    Supports transitioning student cohorts between active study, temporary
    inactivity, or graduation alumni status.

    Args:
        session: Active SQLAlchemy database session.
        student_ids: List of student primary key IDs.
        new_status: Desired lifecycle status ('ACTIVE', 'INACTIVE', or 'ALUMNI').

    Returns:
        The total count of student records updated.

    Raises:
        ValueError: If new_status is not a recognized lifecycle status.
    """
    if not student_ids:
        return 0

    normalized_status = new_status.strip().upper()
    valid_statuses = {"ACTIVE", "INACTIVE", "ALUMNI", "LEFT"}
    if normalized_status not in valid_statuses:
        raise ValueError(
            f"Invalid status '{new_status}'. Allowed values are: {sorted(list(valid_statuses))}"
        )

    statement = (
        update(Student)
        .where(Student.id.in_(student_ids))
        .values(status=normalized_status)
    )
    result = session.execute(statement)
    session.commit()
    return result.rowcount


def bulk_update_students(
    session: Session,
    student_ids: list[int],
    *,
    new_batch_id: int | None = None,
    new_status: str | None = None,
) -> int:
    """
    Update both batch assignment and/or lifecycle status for multiple students in a single transaction.

    Args:
        session: Active SQLAlchemy database session.
        student_ids: List of student primary key IDs.
        new_batch_id: Optional new target batch primary key ID.
        new_status: Optional new lifecycle status ('ACTIVE', 'INACTIVE', 'ALUMNI', 'LEFT').

    Returns:
        The count of updated student records.
    """
    if not student_ids:
        return 0

    values_to_update = {}
    if new_batch_id is not None:
        target_batch = session.get(Batch, new_batch_id)
        if target_batch is None:
            raise ValueError(f"Target batch with ID {new_batch_id} does not exist.")
        values_to_update["batch_id"] = new_batch_id

    if new_status is not None:
        normalized_status = new_status.strip().upper()
        valid_statuses = {"ACTIVE", "INACTIVE", "ALUMNI", "LEFT"}
        if normalized_status not in valid_statuses:
            raise ValueError(
                f"Invalid status '{new_status}'. Allowed values are: {sorted(list(valid_statuses))}"
            )
        values_to_update["status"] = normalized_status

    if not values_to_update:
        return 0

    statement = (
        update(Student)
        .where(Student.id.in_(student_ids))
        .values(**values_to_update)
    )
    result = session.execute(statement)
    session.commit()
    return result.rowcount