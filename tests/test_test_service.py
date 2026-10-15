"""
Unit and Integration Tests for Examination & Test Results Service.

Covers:
  - Scheduling exams with float/decimal max_marks and validation (<= 0 rejection)
  - Querying tests and upcoming tests with eager-loaded batch relationships
  - Recording student scores:
      - Support for decimal marks and negative marks
      - Absent handling (is_absent=True, marks=0.0)
      - Enforcing marks <= max_marks
      - Inactive student validation: disallowing new results for inactive students,
        while allowing score updates for existing results
      - Foreign batch rejection
  - Duplicate result prevention (upsert behavior and unique constraint)
  - Cascade deletion of tests and associated test results
  - Querying student-specific historical results
"""

from datetime import date, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.models.batch import Batch
from app.database.models.student import Student
from app.database.models.test import TestModel
from app.database.models.test_result import TestResult
from app.services.test_service import (
    count_upcoming_tests,
    create_test,
    delete_test,
    get_student_results,
    get_test_results,
    get_tests,
    get_upcoming_tests,
    save_test_results,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        yield session
    engine.dispose()


def test_create_test_valid_and_invalid(db_session):
    batch = Batch(name="Mathematics Grade 10", days="Mon,Wed,Fri")
    db_session.add(batch)
    db_session.flush()

    # Valid test with integer max marks
    t1 = create_test(
        db_session,
        batch_id=batch.id,
        name="  Trigonometry Unit Test  ",
        test_date=date(2026, 11, 1),
        max_marks=100,
    )
    assert t1.id is not None
    assert t1.name == "Trigonometry Unit Test"
    assert t1.max_marks == 100.0

    # Valid test with float/decimal max marks
    t2 = create_test(
        db_session,
        batch_id=batch.id,
        name="Weekly Quiz 1",
        test_date=date(2026, 11, 8),
        max_marks=35.5,
    )
    assert t2.max_marks == 35.5

    # Invalid max marks <= 0
    with pytest.raises(ValueError, match="Maximum marks must be greater than zero."):
        create_test(
            db_session,
            batch_id=batch.id,
            name="Invalid Zero Marks",
            test_date=date(2026, 11, 15),
            max_marks=0,
        )

    with pytest.raises(ValueError, match="Maximum marks must be greater than zero."):
        create_test(
            db_session,
            batch_id=batch.id,
            name="Invalid Negative Marks",
            test_date=date(2026, 11, 15),
            max_marks=-10.0,
        )


def test_get_tests_and_eager_loading(db_session):
    b1 = Batch(name="Physics Alpha", days="Mon,Wed")
    b2 = Batch(name="Chemistry Beta", days="Tue,Thu")
    db_session.add_all([b1, b2])
    db_session.flush()

    today = date.today()
    past_date = today - timedelta(days=5)
    future_date = today + timedelta(days=5)

    t_past = create_test(db_session, batch_id=b1.id, name="Past Exam", test_date=past_date, max_marks=50)
    t_future = create_test(db_session, batch_id=b1.id, name="Future Exam", test_date=future_date, max_marks=50)
    t_other = create_test(db_session, batch_id=b2.id, name="Chem Exam", test_date=future_date, max_marks=100)

    # 1. get_tests ordering (newest date first)
    all_tests = get_tests(db_session)
    assert len(all_tests) == 3
    # Verify eager loading of batch
    assert all_tests[0].batch is not None
    assert all_tests[0].batch.name in ("Physics Alpha", "Chemistry Beta")

    # Filter by batch
    b1_tests = get_tests(db_session, batch_id=b1.id)
    assert len(b1_tests) == 2
    assert all(t.batch_id == b1.id for t in b1_tests)

    # 2. Upcoming tests filter (>= today)
    upcoming_b1 = get_upcoming_tests(db_session, batch_id=b1.id)
    assert len(upcoming_b1) == 1
    assert upcoming_b1[0].id == t_future.id

    assert count_upcoming_tests(db_session, batch_id=b1.id) == 1
    assert count_upcoming_tests(db_session) == 2


def test_save_test_results_decimal_and_negative_marks(db_session):
    batch = Batch(name="Competitive Math")
    db_session.add(batch)
    db_session.flush()

    s1 = Student(admission_number="ADM-TST-001", first_name="Aarav", batch_id=batch.id, status="ACTIVE")
    s2 = Student(admission_number="ADM-TST-002", first_name="Bhavna", batch_id=batch.id, status="ACTIVE")
    db_session.add_all([s1, s2])
    db_session.commit()

    test = create_test(db_session, batch_id=batch.id, name="Olympiad Prelims", test_date=date.today(), max_marks=100.0)

    # Decimal marks and negative marking (-1.25)
    saved_count = save_test_results(
        db_session,
        test_id=test.id,
        entries=[
            {"student_id": s1.id, "marks": 87.75, "remarks": "Excellent speed"},
            {"student_id": s2.id, "marks": -2.5, "remarks": "Penalty for negative questions"},
        ],
    )
    assert saved_count == 2

    results = get_test_results(db_session, test.id)
    assert len(results) == 2
    r_map = {r.student_id: r for r in results}

    assert r_map[s1.id].marks == 87.75
    assert r_map[s1.id].is_absent is False
    assert r_map[s1.id].remarks == "Excellent speed"

    assert r_map[s2.id].marks == -2.5
    assert r_map[s2.id].is_absent is False
    assert r_map[s2.id].remarks == "Penalty for negative questions"

    # Update existing score
    save_test_results(
        db_session,
        test_id=test.id,
        entries=[
            {"student_id": s2.id, "marks": 15.0, "remarks": "Re-evaluated after question cancellation"},
        ],
    )
    updated_results = get_test_results(db_session, test.id)
    assert len(updated_results) == 2
    u_map = {r.student_id: r for r in updated_results}
    assert u_map[s2.id].marks == 15.0
    assert u_map[s2.id].remarks == "Re-evaluated after question cancellation"


def test_save_test_results_absent_handling(db_session):
    batch = Batch(name="Biology Regular")
    db_session.add(batch)
    db_session.flush()

    s1 = Student(admission_number="ADM-TST-003", first_name="Chetan", batch_id=batch.id, status="ACTIVE")
    s2 = Student(admission_number="ADM-TST-004", first_name="Divya", batch_id=batch.id, status="ACTIVE")
    db_session.add_all([s1, s2])
    db_session.commit()

    test = create_test(db_session, batch_id=batch.id, name="Genetics Quiz", test_date=date.today(), max_marks=50.0)

    # s2 marked absent with non-zero marks passed in payload (should be forced to 0.0)
    save_test_results(
        db_session,
        test_id=test.id,
        entries=[
            {"student_id": s1.id, "marks": 42.0, "is_absent": False},
            {"student_id": s2.id, "marks": 999.0, "is_absent": True, "remarks": "Medical leave"},
        ],
    )

    results = get_test_results(db_session, test.id)
    r_map = {r.student_id: r for r in results}

    assert r_map[s1.id].marks == 42.0
    assert r_map[s1.id].is_absent is False

    assert r_map[s2.id].marks == 0.0
    assert r_map[s2.id].is_absent is True
    assert r_map[s2.id].remarks == "Medical leave"


def test_save_test_results_validations(db_session):
    b1 = Batch(name="Batch 1")
    b2 = Batch(name="Batch 2")
    db_session.add_all([b1, b2])
    db_session.flush()

    s1 = Student(admission_number="ADM-TST-005", first_name="Esha", batch_id=b1.id, status="ACTIVE")
    s_other = Student(admission_number="ADM-TST-006", first_name="Farhan", batch_id=b2.id, status="ACTIVE")
    db_session.add_all([s1, s_other])
    db_session.commit()

    test = create_test(db_session, batch_id=b1.id, name="Midterm Exam", test_date=date.today(), max_marks=50.0)

    # 1. Nonexistent test
    with pytest.raises(ValueError, match="The selected test no longer exists."):
        save_test_results(
            db_session,
            test_id=99999,
            entries=[{"student_id": s1.id, "marks": 40.0}],
        )

    # 2. Exceeding max marks
    with pytest.raises(ValueError, match=r"Marks must be at most 50\.0\."):
        save_test_results(
            db_session,
            test_id=test.id,
            entries=[{"student_id": s1.id, "marks": 50.5}],
        )

    # 3. Student from another batch
    with pytest.raises(ValueError, match="A selected student does not belong to this test's batch."):
        save_test_results(
            db_session,
            test_id=test.id,
            entries=[{"student_id": s_other.id, "marks": 40.0}],
        )


def test_save_test_results_inactive_student_behavior(db_session):
    batch = Batch(name="Batch Senior")
    db_session.add(batch)
    db_session.flush()

    s_active = Student(admission_number="ADM-TST-007", first_name="Gaurav", batch_id=batch.id, status="ACTIVE")
    s_inactive = Student(admission_number="ADM-TST-008", first_name="Hina", batch_id=batch.id, status="INACTIVE")
    db_session.add_all([s_active, s_inactive])
    db_session.commit()

    test = create_test(db_session, batch_id=batch.id, name="Final Evaluation", test_date=date.today(), max_marks=100.0)

    # 1. New result for active student succeeds
    save_test_results(
        db_session,
        test_id=test.id,
        entries=[{"student_id": s_active.id, "marks": 75.0}],
    )

    # 2. New result for inactive student fails
    with pytest.raises(ValueError, match="Results can only be entered for active students"):
        save_test_results(
            db_session,
            test_id=test.id,
            entries=[{"student_id": s_inactive.id, "marks": 60.0}],
        )

    # 3. Student who originally had results now becomes inactive
    s_active.status = "INACTIVE"
    db_session.commit()

    # Updating existing score for the now-inactive student should be allowed
    save_test_results(
        db_session,
        test_id=test.id,
        entries=[{"student_id": s_active.id, "marks": 80.0, "remarks": "Correction after review"}],
    )

    res = get_test_results(db_session, test.id)
    assert len(res) == 1
    assert res[0].student_id == s_active.id
    assert res[0].marks == 80.0
    assert res[0].remarks == "Correction after review"


def test_test_results_unique_constraint(db_session):
    batch = Batch(name="Batch Alpha")
    db_session.add(batch)
    db_session.flush()

    s = Student(admission_number="ADM-TST-009", first_name="Ishan", batch_id=batch.id, status="ACTIVE")
    db_session.add(s)
    db_session.commit()

    test = create_test(db_session, batch_id=batch.id, name="Unit 1", test_date=date.today(), max_marks=25.0)

    r1 = TestResult(test_id=test.id, student_id=s.id, marks=20.0)
    db_session.add(r1)
    db_session.commit()

    # Directly adding duplicate result for same (test_id, student_id) must trigger IntegrityError
    r2 = TestResult(test_id=test.id, student_id=s.id, marks=22.0)
    db_session.add(r2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_delete_test_cascades_results_and_student_results_query(db_session):
    batch = Batch(name="Batch Beta")
    db_session.add(batch)
    db_session.flush()

    s = Student(admission_number="ADM-TST-010", first_name="Juhi", batch_id=batch.id, status="ACTIVE")
    db_session.add(s)
    db_session.commit()

    t1 = create_test(db_session, batch_id=batch.id, name="Test 1", test_date=date(2026, 9, 1), max_marks=50.0)
    t2 = create_test(db_session, batch_id=batch.id, name="Test 2", test_date=date(2026, 9, 15), max_marks=50.0)

    save_test_results(db_session, test_id=t1.id, entries=[{"student_id": s.id, "marks": 40.0}])
    save_test_results(db_session, test_id=t2.id, entries=[{"student_id": s.id, "marks": 45.0}])

    # Query get_student_results
    student_results = get_student_results(db_session, s.id)
    assert len(student_results) == 2
    # Verify ordered newest test first
    assert student_results[0].test.name == "Test 2"
    assert student_results[1].test.name == "Test 1"

    # Delete t1
    deleted = delete_test(db_session, t1.id)
    assert deleted is True

    # Check t1 is deleted
    assert db_session.get(TestModel, t1.id) is None
    assert get_test_results(db_session, t1.id) == []

    # Check student results now only contains t2
    remaining_results = get_student_results(db_session, s.id)
    assert len(remaining_results) == 1
    assert remaining_results[0].test.name == "Test 2"

    # Deleting non-existent test returns False
    assert delete_test(db_session, 99999) is False
