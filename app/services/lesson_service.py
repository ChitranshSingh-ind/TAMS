from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.lesson import Lesson


def create_lesson(
    session: Session,
    *,
    batch_id: int,
    title: str,
    planned_date: date,
    chapter: str | None = None,
    topic: str | None = None,
    status: str = "PLANNED",
    notes: str | None = None,
) -> Lesson:

    lesson = Lesson(
        batch_id=batch_id,
        title=title.strip(),
        chapter=chapter.strip() if chapter else None,
        topic=topic.strip() if topic else None,
        planned_date=planned_date,
        status=status,
        notes=notes,
    )

    session.add(lesson)
    session.commit()
    session.refresh(lesson)

    return lesson


def get_lessons_for_date(
    session: Session,
    lesson_date: date,
    batch_id: int | None = None,
) -> list[Lesson]:

    statement = (
        select(Lesson)
        .where(
            Lesson.planned_date == lesson_date,
            Lesson.status == "PLANNED",
        )
        .order_by(Lesson.id)
    )

    if batch_id is not None:
        statement = statement.where(
            Lesson.batch_id == batch_id
        )

    return list(session.scalars(statement).all())