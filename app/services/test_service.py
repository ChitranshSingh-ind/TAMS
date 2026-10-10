from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database.models.test import TestModel
from app.database.models.test_result import TestResult
from app.database.models.student import Student


def create_test(
    session: Session,
    *,
    batch_id: int,
    name: str,
    test_date: date,
    max_marks: int,
) -> TestModel:

    test = TestModel(
        batch_id=batch_id,
        name=name.strip(),
        test_date=test_date,
        max_marks=max_marks,
    )

    session.add(test)
    session.commit()
    session.refresh(test)

    return test


def get_upcoming_tests(
    session: Session,
    batch_id: int | None = None,
) -> list[TestModel]:

    statement = (
        select(TestModel)
        .where(TestModel.test_date >= date.today())
        .order_by(TestModel.test_date)
    )

    if batch_id is not None:
        statement = statement.where(
            TestModel.batch_id == batch_id
        )

    return list(session.scalars(statement).all())


def get_tests(
    session: Session,
    batch_id: int | None = None,
) -> list[TestModel]:
    statement = select(TestModel).order_by(
        TestModel.test_date.desc(),
        TestModel.id.desc(),
    )

    if batch_id is not None:
        statement = statement.where(TestModel.batch_id == batch_id)

    return list(session.scalars(statement).all())


def count_upcoming_tests(
    session: Session,
    batch_id: int | None = None,
) -> int:

    return len(
        get_upcoming_tests(
            session,
            batch_id=batch_id,
        )
    )
def save_test_results(
    session: Session,
    *,
    test_id: int,
    entries: list[dict],
) -> int:
    test = session.get(TestModel, test_id)
    if test is None:
        raise ValueError("The selected test no longer exists.")

    saved_count = 0

    for entry in entries:
        student_id = int(entry["student_id"])
        marks = int(entry["marks"])
        remarks = str(entry.get("remarks", "")).strip() or None

        if marks < 0 or marks > test.max_marks:
            raise ValueError(
                f"Marks must be between 0 and {test.max_marks}."
            )

        student = session.get(Student, student_id)
        if student is None or student.batch_id != test.batch_id:
            raise ValueError(
                "A selected student does not belong to this test's batch."
            )

        if student.status != "ACTIVE":
            raise ValueError(
                f"Results can only be entered or edited for active students. "
                f"{student.first_name} {student.last_name or ''} is "
                f"{student.status.lower()}."
            )

        existing = session.scalar(
            select(TestResult).where(
                TestResult.test_id == test_id,
                TestResult.student_id == student_id,
            )
        )

        if existing is None:
            existing = TestResult(
                test_id=test_id,
                student_id=student_id,
                marks=marks,
                remarks=remarks,
            )
            session.add(existing)
        else:
            existing.marks = marks
            existing.remarks = remarks

        saved_count += 1

    session.commit()
    return saved_count


def get_test_results(
    session: Session,
    test_id: int,
) -> list[TestResult]:
    statement = (
        select(TestResult)
        .where(TestResult.test_id == test_id)
        .order_by(TestResult.student_id)
    )
    return list(session.scalars(statement).all())


def get_student_results(
    session: Session,
    student_id: int,
):
    statement = (
        select(TestResult)
        .options(joinedload(TestResult.test))
        .join(TestModel, TestResult.test_id == TestModel.id)
        .where(TestResult.student_id == student_id)
        .order_by(TestModel.test_date.desc())
    )

    return list(session.scalars(statement).all())


def delete_test(
    session: Session,
    test_id: int,
) -> bool:
    test = session.get(TestModel, test_id)
    if test is None:
        return False

    results = session.scalars(
        select(TestResult).where(TestResult.test_id == test_id)
    ).all()
    for result in results:
        session.delete(result)

    session.delete(test)
    session.commit()
    return True