from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.test import TestModel


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