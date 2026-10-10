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


def test_update_student_with_parent():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        batch1 = create_batch(session, "Batch 1")
        batch2 = create_batch(session, "Batch 2")

        parent = Parent(name="Original Parent", phone="1111111111")
        session.add(parent)
        session.commit()

        student = create_student(
            session,
            admission_number="ADM001",
            first_name="Alice",
            parent_id=parent.id,
            batch_id=batch1.id,
        )

        # Update student details and existing parent
        from app.services.student_service import update_student_with_parent, get_student

        updated = update_student_with_parent(
            session,
            student.id,
            admission_number="ADM001-UPDATED",
            first_name="Alice Updated",
            last_name="Smith",
            parent_name="Parent Updated",
            parent_phone="2222222222",
            whatsapp_number="3333333333",
            batch_id=batch2.id,
            notes="Updated notes",
        )

        assert updated is not None
        assert updated.admission_number == "ADM001-UPDATED"
        assert updated.first_name == "Alice Updated"
        assert updated.last_name == "Smith"
        assert updated.batch_id == batch2.id
        assert updated.parent.name == "Parent Updated"
        assert updated.parent.phone == "2222222222"
        assert updated.parent.whatsapp_number == "3333333333"


def test_update_student_creates_parent_if_none_existed():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        batch = create_batch(session, "Batch 1")

        student = create_student(
            session,
            admission_number="ADM002",
            first_name="Bob",
            parent_id=None,
            batch_id=batch.id,
        )
        assert student.parent_id is None

        from app.services.student_service import update_student_with_parent

        updated = update_student_with_parent(
            session,
            student.id,
            admission_number="ADM002",
            first_name="Bob",
            parent_name="New Parent",
            parent_phone="4444444444",
            whatsapp_number="5555555555",
            batch_id=batch.id,
        )

        assert updated is not None
        assert updated.parent_id is not None
        assert updated.parent.name == "New Parent"
        assert updated.parent.phone == "4444444444"


def test_update_student_rejects_duplicate_admission_number():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        batch = create_batch(session, "Batch 1")

        create_student(
            session,
            admission_number="ADM100",
            first_name="Charlie",
            batch_id=batch.id,
        )
        student2 = create_student(
            session,
            admission_number="ADM101",
            first_name="David",
            batch_id=batch.id,
        )

        from app.services.student_service import update_student_with_parent
        import pytest

        with pytest.raises(ValueError, match="already exists"):
            update_student_with_parent(
                session,
                student2.id,
                admission_number="ADM100",
                first_name="David",
                batch_id=batch.id,
            )


def test_eager_loading_in_student_queries():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        batch = create_batch(session, "Batch Alpha")
        batch_id = batch.id
        parent = Parent(name="Alpha Parent", phone="123")
        session.add(parent)
        session.commit()

        create_student(
            session,
            admission_number="STU_EAGER",
            first_name="Eve",
            parent_id=parent.id,
            batch_id=batch_id,
        )

    # In a new session, fetch and then close the session to verify parent and batch remain accessible
    from app.services.student_service import get_students_by_batch, get_student

    with Session() as session:
        students = get_students_by_batch(session, batch_id)
        single_student = get_student(session, students[0].id)

    # Session is now closed! Check that parent and batch are already loaded in memory:
    assert students[0].parent.name == "Alpha Parent"
    assert students[0].batch.name == "Batch Alpha"
    assert single_student.parent.name == "Alpha Parent"
    assert single_student.batch.name == "Batch Alpha"


def test_save_batch_attendance_and_overrides():
    from datetime import date
    from app.services.attendance_service import (
        save_batch_attendance,
        get_attendance_by_date,
        create_attendance_override,
        get_attendance_override,
    )

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        batch = create_batch(session, "Class 10", days="Mon,Wed,Fri")
        s1 = create_student(session, admission_number="A1", first_name="A1", batch_id=batch.id)
        s2 = create_student(session, admission_number="A2", first_name="A2", batch_id=batch.id)

        test_date = date(2026, 10, 12)  # A Monday

        # Batch save attendance
        saved = save_batch_attendance(
            session,
            batch_id=batch.id,
            attendance_date=test_date,
            attendance_records={s1.id: "PRESENT", s2.id: "ABSENT"},
        )
        assert saved == 2

        records = get_attendance_by_date(session, test_date, batch_id=batch.id)
        assert len(records) == 2
        record_map = {r.student_id: r.status for r in records}
        assert record_map[s1.id] == "PRESENT"
        assert record_map[s2.id] == "ABSENT"

        # Update attendance (upsert)
        save_batch_attendance(
            session,
            batch_id=batch.id,
            attendance_date=test_date,
            attendance_records={s1.id: "ABSENT", s2.id: "PRESENT"},
        )
        records_after = get_attendance_by_date(session, test_date, batch_id=batch.id)
        assert len(records_after) == 2
        record_map_after = {r.student_id: r.status for r in records_after}
        assert record_map_after[s1.id] == "ABSENT"
        assert record_map_after[s2.id] == "PRESENT"

        # Test attendance override
        tuesday = date(2026, 10, 13)
        override = create_attendance_override(session, batch_id=batch.id, override_date=tuesday, reason="Extra class")
        assert override.id is not None

        queried = get_attendance_override(session, batch_id=batch.id, override_date=tuesday)
        assert queried is not None
        assert queried.reason == "Extra class"


def test_create_and_delete_test():
    from datetime import date
    from app.services.test_service import create_test, delete_test, get_tests, save_test_results, get_test_results

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        batch = create_batch(session, "Class 10-A")
        student = create_student(session, admission_number="STU_T1", first_name="Tom", batch_id=batch.id)

        test = create_test(
            session,
            batch_id=batch.id,
            name="Unit Test 1",
            test_date=date(2026, 10, 15),
            max_marks=50,
        )
        assert test.id is not None
        assert len(get_tests(session, batch_id=batch.id)) == 1

        # Save result
        save_test_results(session, test_id=test.id, entries=[{"student_id": student.id, "marks": 45, "remarks": "Good"}])
        assert len(get_test_results(session, test.id)) == 1

        # Delete test
        success = delete_test(session, test.id)
        assert success is True
        assert len(get_tests(session, batch_id=batch.id)) == 0
        assert len(get_test_results(session, test.id)) == 0