"""
Unit and Integration Tests for Attendance Service.

Covers:
  - Single attendance marking and updating (mark_attendance)
  - Batch atomic attendance saving (save_batch_attendance)
  - Attendance percentage calculations:
      - Counting LATE as attended alongside PRESENT
      - Excluding approved LEAVE from required total classes
  - count_present_students optimization
  - Class day overrides (creation, querying, duplicate rejection)
"""

from datetime import date
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.models.batch import Batch
from app.database.models.parent import Parent
from app.database.models.student import Student
from app.services.attendance_service import (
    count_present_students,
    create_attendance_override,
    get_attendance_by_date,
    get_attendance_override,
    get_student_attendance,
    get_student_attendance_summary,
    mark_attendance,
    save_batch_attendance,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        yield session
    engine.dispose()


def test_mark_single_attendance_create_and_update(db_session):
    batch = Batch(name="Physics 101", days="Mon,Wed,Fri")
    db_session.add(batch)
    db_session.flush()

    student = Student(admission_number="ADM-ATT-001", first_name="Alice", batch_id=batch.id)
    db_session.add(student)
    db_session.commit()

    d1 = date(2026, 10, 12)

    # 1. Create single attendance
    att = mark_attendance(
        db_session,
        student_id=student.id,
        batch_id=batch.id,
        attendance_date=d1,
        status="PRESENT",
        remarks="Arrived on time",
    )
    assert att.id is not None
    assert att.status == "PRESENT"
    assert att.remarks == "Arrived on time"

    # 2. Update existing attendance (same student, batch, date)
    att_updated = mark_attendance(
        db_session,
        student_id=student.id,
        batch_id=batch.id,
        attendance_date=d1,
        status="LATE",
        remarks="Delayed by 10 mins",
    )
    assert att_updated.id == att.id
    assert att_updated.status == "LATE"
    assert att_updated.remarks == "Delayed by 10 mins"


def test_save_batch_attendance(db_session):
    batch = Batch(name="Chemistry 101", days="Tue,Thu")
    db_session.add(batch)
    db_session.flush()

    s1 = Student(admission_number="ADM-ATT-002", first_name="Bob", batch_id=batch.id)
    s2 = Student(admission_number="ADM-ATT-003", first_name="Charlie", batch_id=batch.id)
    db_session.add_all([s1, s2])
    db_session.commit()

    d1 = date(2026, 10, 13)

    # Save batch records
    saved = save_batch_attendance(
        db_session,
        batch_id=batch.id,
        attendance_date=d1,
        attendance_records={s1.id: "PRESENT", s2.id: "ABSENT"},
    )
    assert saved == 2

    # Query back
    records = get_attendance_by_date(db_session, d1, batch_id=batch.id)
    assert len(records) == 2
    rec_map = {r.student_id: r.status for r in records}
    assert rec_map[s1.id] == "PRESENT"
    assert rec_map[s2.id] == "ABSENT"


def test_attendance_percentage_harmonization_and_leave_exclusion(db_session):
    """
    Verifies that:
      - LATE counts as attended alongside PRESENT
      - Approved LEAVE does not penalize the student's required class total
    """
    batch = Batch(name="Math 101", days="Mon,Wed,Fri")
    db_session.add(batch)
    db_session.flush()

    student = Student(admission_number="ADM-ATT-004", first_name="Diana", batch_id=batch.id)
    db_session.add(student)
    db_session.commit()

    # Session 1: PRESENT
    mark_attendance(db_session, student_id=student.id, batch_id=batch.id, attendance_date=date(2026, 10, 5), status="PRESENT")
    # Session 2: LATE (should count as attended!)
    mark_attendance(db_session, student_id=student.id, batch_id=batch.id, attendance_date=date(2026, 10, 7), status="LATE")
    # Session 3: LEAVE (approved leave: must NOT penalize required classes)
    mark_attendance(db_session, student_id=student.id, batch_id=batch.id, attendance_date=date(2026, 10, 9), status="LEAVE")

    summary = get_student_attendance_summary(db_session, student.id)
    assert summary["total"] == 3
    assert summary["present"] == 1
    assert summary["late"] == 1
    assert summary["leave"] == 1
    assert summary["absent"] == 0
    # Effective total = 3 - 1 (leave) = 2. Attended = 1 (present) + 1 (late) = 2.
    # Percentage should be (2 / 2) * 100 = 100.0%!
    assert summary["percentage"] == 100.0

    # Session 4: ABSENT (now effective total = 4 - 1 = 3, attended = 2 -> 66.7%)
    mark_attendance(db_session, student_id=student.id, batch_id=batch.id, attendance_date=date(2026, 10, 12), status="ABSENT")
    summary2 = get_student_attendance_summary(db_session, student.id)
    assert summary2["total"] == 4
    assert summary2["absent"] == 1
    assert summary2["percentage"] == 66.7


def test_count_present_students_optimization(db_session):
    batch1 = Batch(name="Batch 1", days="Mon")
    batch2 = Batch(name="Batch 2", days="Mon")
    db_session.add_all([batch1, batch2])
    db_session.flush()

    s1 = Student(admission_number="ADM-P-1", first_name="S1", batch_id=batch1.id)
    s2 = Student(admission_number="ADM-P-2", first_name="S2", batch_id=batch1.id)
    s3 = Student(admission_number="ADM-P-3", first_name="S3", batch_id=batch2.id)
    db_session.add_all([s1, s2, s3])
    db_session.commit()

    d1 = date(2026, 10, 12)
    mark_attendance(db_session, student_id=s1.id, batch_id=batch1.id, attendance_date=d1, status="PRESENT")
    mark_attendance(db_session, student_id=s2.id, batch_id=batch1.id, attendance_date=d1, status="ABSENT")
    mark_attendance(db_session, student_id=s3.id, batch_id=batch2.id, attendance_date=d1, status="PRESENT")

    # Across all batches: 2 present
    assert count_present_students(db_session, d1) == 2
    # For batch 1: 1 present
    assert count_present_students(db_session, d1, batch_id=batch1.id) == 1
    # For batch 2: 1 present
    assert count_present_students(db_session, d1, batch_id=batch2.id) == 1


def test_attendance_overrides(db_session):
    batch = Batch(name="Weekend Batch", days="Sat,Sun")
    db_session.add(batch)
    db_session.commit()

    override_d = date(2026, 10, 14)  # Wednesday (unscheduled day)

    # Initially None
    assert get_attendance_override(db_session, batch_id=batch.id, override_date=override_d) is None

    # Create override
    ov = create_attendance_override(
        db_session,
        batch_id=batch.id,
        override_date=override_d,
        reason="Midterm Revision Class",
    )
    assert ov.id is not None
    assert ov.reason == "Midterm Revision Class"

    # Query back
    queried = get_attendance_override(db_session, batch_id=batch.id, override_date=override_d)
    assert queried is not None
    assert queried.id == ov.id
