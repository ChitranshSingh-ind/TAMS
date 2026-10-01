from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.models.batch import Batch
from app.database.models.parent import Parent
from app.database.models.student import Student
from app.services.batch_service import create_batch, get_active_batches
from app.services.student_service import (
    create_student,
    get_students_by_batch,
    count_students,
)


def test_batch_and_student_creation():
    engine = create_engine("sqlite:///:memory:")

    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)

    with Session() as session:
        batch = create_batch(
            session,
            "Morning Batch",
            days="Mon,Wed,Fri",
        )

        assert batch.id is not None
        assert batch.name == "Morning Batch"

        parent = Parent(
            name="Test Parent",
            whatsapp_number="9999999999",
        )

        session.add(parent)
        session.commit()

        student = create_student(
            session,
            admission_number="T001",
            first_name="Test",
            last_name="Student",
            parent_id=parent.id,
            batch_id=batch.id,
        )

        assert student.id is not None

        students = get_students_by_batch(
            session,
            batch.id,
        )

        assert len(students) == 1
        assert students[0].first_name == "Test"

        batches = get_active_batches(session)

        assert len(batches) == 1