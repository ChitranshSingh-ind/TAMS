"""
Teaching service — Lesson CRUD, class records, homework, and progress.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import Session, selectinload

from app.database.models.lesson import Lesson, ClassRecord, Homework

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LESSON_STATUSES = ["PLANNED", "IN_PROGRESS", "COMPLETED", "CANCELLED"]


# ---------------------------------------------------------------------------
# Lesson helpers
# ---------------------------------------------------------------------------

def _load_lesson(session: Session, lesson_id: int) -> Lesson:
    lesson = session.get(Lesson, lesson_id, options=[
        selectinload(Lesson.class_records),
        selectinload(Lesson.homeworks),
    ])
    if lesson is None:
        raise ValueError(f"Lesson #{lesson_id} not found.")
    return lesson


# ---------------------------------------------------------------------------
# Lesson CRUD
# ---------------------------------------------------------------------------

def create_lesson(
    session: Session,
    *,
    batch_id: int,
    title: str,
    planned_date: date,
    chapter: str | None = None,
    topic: str | None = None,
    description: str | None = None,
    duration_minutes: int | None = None,
    sequence_order: int | None = None,
    status: str = "PLANNED",
    notes: str | None = None,
) -> Lesson:
    title = (title or "").strip()
    if not title:
        raise ValueError("Lesson title is required.")
    if status not in LESSON_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Use one of {LESSON_STATUSES}.")

    lesson = Lesson(
        batch_id=batch_id,
        title=title,
        chapter=chapter.strip() if chapter else None,
        topic=topic.strip() if topic else None,
        description=description.strip() if description else None,
        planned_date=planned_date,
        duration_minutes=duration_minutes,
        sequence_order=sequence_order,
        status=status,
        notes=notes.strip() if notes else None,
    )
    session.add(lesson)
    session.commit()
    session.refresh(lesson)
    return lesson


def update_lesson(
    session: Session,
    lesson_id: int,
    *,
    title: str | None = None,
    chapter: str | None = None,
    topic: str | None = None,
    description: str | None = None,
    planned_date: date | None = None,
    duration_minutes: int | None = None,
    sequence_order: int | None = None,
    status: str | None = None,
    notes: str | None = None,
) -> Lesson:
    lesson = _load_lesson(session, lesson_id)

    if title is not None:
        title = title.strip()
        if not title:
            raise ValueError("Lesson title cannot be empty.")
        lesson.title = title
    if chapter is not None:
        lesson.chapter = chapter.strip() or None
    if topic is not None:
        lesson.topic = topic.strip() or None
    if description is not None:
        lesson.description = description.strip() or None
    if planned_date is not None:
        lesson.planned_date = planned_date
    if duration_minutes is not None:
        lesson.duration_minutes = duration_minutes
    if sequence_order is not None:
        lesson.sequence_order = sequence_order
    if status is not None:
        if status not in LESSON_STATUSES:
            raise ValueError(f"Invalid status '{status}'.")
        lesson.status = status
    if notes is not None:
        lesson.notes = notes.strip() or None

    session.commit()
    session.refresh(lesson)
    return lesson


def delete_lesson(session: Session, lesson_id: int) -> bool:
    """Delete a lesson. Raises if it has linked class records."""
    lesson = session.get(Lesson, lesson_id)
    if lesson is None:
        return False
    # ClassRecord FK is SET NULL so we can safely delete
    session.delete(lesson)
    session.commit()
    return True


def get_lesson(session: Session, lesson_id: int) -> Lesson | None:
    return session.scalar(
        select(Lesson)
        .options(
            selectinload(Lesson.class_records),
            selectinload(Lesson.homeworks),
            selectinload(Lesson.batch),
        )
        .where(Lesson.id == lesson_id)
    )


def get_lessons(
    session: Session,
    batch_id: int | None = None,
    status: str | None = None,
    chapter: str | None = None,
    search: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[Lesson]:
    stmt = (
        select(Lesson)
        .options(
            selectinload(Lesson.class_records),
            selectinload(Lesson.homeworks),
            selectinload(Lesson.batch),
        )
        .order_by(Lesson.planned_date.desc(), Lesson.sequence_order.asc(), Lesson.id.desc())
    )
    if batch_id is not None:
        stmt = stmt.where(Lesson.batch_id == batch_id)
    if status and status != "ALL":
        stmt = stmt.where(Lesson.status == status)
    if chapter:
        stmt = stmt.where(Lesson.chapter.ilike(f"%{chapter}%"))
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Lesson.title.ilike(term),
                Lesson.chapter.ilike(term),
                Lesson.topic.ilike(term),
                Lesson.notes.ilike(term),
            )
        )
    if start_date:
        stmt = stmt.where(Lesson.planned_date >= start_date)
    if end_date:
        stmt = stmt.where(Lesson.planned_date <= end_date)
    return list(session.scalars(stmt).all())


def get_upcoming_lessons(
    session: Session,
    batch_id: int | None = None,
    days: int = 14,
) -> list[Lesson]:
    today = date.today()
    end = today + timedelta(days=days)
    stmt = (
        select(Lesson)
        .where(
            Lesson.status.in_(["PLANNED", "IN_PROGRESS"]),
            Lesson.planned_date >= today,
            Lesson.planned_date <= end,
        )
        .order_by(Lesson.planned_date.asc())
    )
    if batch_id is not None:
        stmt = stmt.where(Lesson.batch_id == batch_id)
    return list(session.scalars(stmt).all())


def get_overdue_lessons(
    session: Session,
    batch_id: int | None = None,
) -> list[Lesson]:
    today = date.today()
    stmt = (
        select(Lesson)
        .where(
            Lesson.status.in_(["PLANNED", "IN_PROGRESS"]),
            Lesson.planned_date < today,
        )
        .order_by(Lesson.planned_date.asc())
    )
    if batch_id is not None:
        stmt = stmt.where(Lesson.batch_id == batch_id)
    return list(session.scalars(stmt).all())


def mark_lesson_completed(session: Session, lesson_id: int) -> Lesson:
    lesson = _load_lesson(session, lesson_id)
    lesson.status = "COMPLETED"
    session.commit()
    session.refresh(lesson)
    return lesson


def reschedule_lesson(session: Session, lesson_id: int, new_date: date) -> Lesson:
    lesson = _load_lesson(session, lesson_id)
    lesson.planned_date = new_date
    if lesson.status == "CANCELLED":
        lesson.status = "PLANNED"
    session.commit()
    session.refresh(lesson)
    return lesson


# ---------------------------------------------------------------------------
# Teaching summary / progress
# ---------------------------------------------------------------------------

def get_teaching_summary(
    session: Session,
    batch_id: int | None = None,
) -> dict[str, Any]:
    today = date.today()

    def base_query(extra_filters=None):
        q = select(func.count(Lesson.id))
        if batch_id is not None:
            q = q.where(Lesson.batch_id == batch_id)
        if extra_filters:
            q = q.where(*extra_filters)
        return q

    total = session.scalar(base_query()) or 0
    planned = session.scalar(base_query([Lesson.status == "PLANNED"])) or 0
    in_prog = session.scalar(base_query([Lesson.status == "IN_PROGRESS"])) or 0
    completed = session.scalar(base_query([Lesson.status == "COMPLETED"])) or 0
    cancelled = session.scalar(base_query([Lesson.status == "CANCELLED"])) or 0
    upcoming = session.scalar(
        base_query([Lesson.status.in_(["PLANNED", "IN_PROGRESS"]), Lesson.planned_date >= today])
    ) or 0
    overdue = session.scalar(
        base_query([Lesson.status.in_(["PLANNED", "IN_PROGRESS"]), Lesson.planned_date < today])
    ) or 0

    active_total = total - cancelled
    pct = round(100 * completed / active_total) if active_total > 0 else 0

    cr_q = select(func.count(ClassRecord.id))
    if batch_id is not None:
        cr_q = cr_q.where(ClassRecord.batch_id == batch_id)
    total_classes_recorded = session.scalar(cr_q) or 0

    hw_q = select(func.count(Homework.id))
    if batch_id is not None:
        hw_q = hw_q.where(Homework.batch_id == batch_id)
    total_homework = session.scalar(hw_q) or 0

    overdue_hw = session.scalar(
        (hw_q if batch_id is None else hw_q).where(  # type: ignore[union-attr]
            Homework.due_date < today,
        )
    ) or 0
    # Re-build the HW query cleanly
    hw_base = select(func.count(Homework.id))
    if batch_id is not None:
        hw_base = hw_base.where(Homework.batch_id == batch_id)
    overdue_hw = session.scalar(hw_base.where(Homework.due_date < today)) or 0

    return {
        "total": total,
        "planned": planned,
        "in_progress": in_prog,
        "completed": completed,
        "cancelled": cancelled,
        "upcoming": upcoming,
        "overdue": overdue,
        "completion_pct": pct,
        "total_classes_recorded": total_classes_recorded,
        "total_homework": total_homework,
        "overdue_homework": overdue_hw,
    }


def get_chapters_progress(
    session: Session,
    batch_id: int | None = None,
) -> list[dict[str, Any]]:
    """Return per-chapter completion stats."""
    stmt = (
        select(Lesson.chapter, Lesson.status, func.count(Lesson.id))
        .where(Lesson.chapter.isnot(None))
        .group_by(Lesson.chapter, Lesson.status)
        .order_by(Lesson.chapter)
    )
    if batch_id is not None:
        stmt = stmt.where(Lesson.batch_id == batch_id)

    rows = session.execute(stmt).all()

    chapters: dict[str, dict] = {}
    for chapter, status, cnt in rows:
        if chapter not in chapters:
            chapters[chapter] = {"chapter": chapter, "total": 0, "completed": 0, "planned": 0,
                                  "cancelled": 0, "in_progress": 0}
        chapters[chapter]["total"] += cnt
        key = status.lower() if status.lower() in ("completed", "planned", "cancelled") else "in_progress"
        chapters[chapter][key] = chapters[chapter].get(key, 0) + cnt

    result = []
    for ch in chapters.values():
        active = ch["total"] - ch.get("cancelled", 0)
        ch["completion_pct"] = round(100 * ch["completed"] / active) if active > 0 else 0
        result.append(ch)
    return result


# ---------------------------------------------------------------------------
# Class Records (completed teaching sessions)
# ---------------------------------------------------------------------------

def create_class_record(
    session: Session,
    *,
    batch_id: int,
    class_date: date,
    chapter: str | None = None,
    topic: str | None = None,
    topics_completed: str | None = None,
    topics_partial: str | None = None,
    notes: str | None = None,
    next_topic: str | None = None,
    duration_minutes: int | None = None,
    lesson_id: int | None = None,
    auto_complete_lesson: bool = True,
) -> ClassRecord:
    if not class_date:
        raise ValueError("Class date is required.")

    record = ClassRecord(
        batch_id=batch_id,
        class_date=class_date,
        chapter=chapter.strip() if chapter else None,
        topic=topic.strip() if topic else None,
        topics_completed=topics_completed.strip() if topics_completed else None,
        topics_partial=topics_partial.strip() if topics_partial else None,
        notes=notes.strip() if notes else None,
        next_topic=next_topic.strip() if next_topic else None,
        duration_minutes=duration_minutes,
        lesson_id=lesson_id,
    )
    session.add(record)
    session.flush()

    # Optionally mark linked lesson as completed
    if lesson_id and auto_complete_lesson:
        lesson = session.get(Lesson, lesson_id)
        if lesson and lesson.status not in ("COMPLETED", "CANCELLED"):
            lesson.status = "COMPLETED"

    session.commit()
    session.refresh(record)
    return record


def update_class_record(
    session: Session,
    record_id: int,
    *,
    class_date: date | None = None,
    chapter: str | None = None,
    topic: str | None = None,
    topics_completed: str | None = None,
    topics_partial: str | None = None,
    notes: str | None = None,
    next_topic: str | None = None,
    duration_minutes: int | None = None,
    lesson_id: int | None = None,
) -> ClassRecord:
    record = session.get(ClassRecord, record_id)
    if record is None:
        raise ValueError(f"Class record #{record_id} not found.")

    if class_date is not None:
        record.class_date = class_date
    if chapter is not None:
        record.chapter = chapter.strip() or None
    if topic is not None:
        record.topic = topic.strip() or None
    if topics_completed is not None:
        record.topics_completed = topics_completed.strip() or None
    if topics_partial is not None:
        record.topics_partial = topics_partial.strip() or None
    if notes is not None:
        record.notes = notes.strip() or None
    if next_topic is not None:
        record.next_topic = next_topic.strip() or None
    if duration_minutes is not None:
        record.duration_minutes = duration_minutes
    if lesson_id is not None:
        record.lesson_id = lesson_id

    session.commit()
    session.refresh(record)
    return record


def get_class_records(
    session: Session,
    batch_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    search: str | None = None,
    limit: int | None = None,
) -> list[ClassRecord]:
    stmt = (
        select(ClassRecord)
        .options(
            selectinload(ClassRecord.homeworks),
            selectinload(ClassRecord.lesson),
            selectinload(ClassRecord.batch),
        )
        .order_by(ClassRecord.class_date.desc(), ClassRecord.id.desc())
    )
    if batch_id is not None:
        stmt = stmt.where(ClassRecord.batch_id == batch_id)
    if start_date:
        stmt = stmt.where(ClassRecord.class_date >= start_date)
    if end_date:
        stmt = stmt.where(ClassRecord.class_date <= end_date)
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                ClassRecord.chapter.ilike(term),
                ClassRecord.topic.ilike(term),
                ClassRecord.topics_completed.ilike(term),
                ClassRecord.notes.ilike(term),
            )
        )
    if limit:
        stmt = stmt.limit(limit)
    return list(session.scalars(stmt).all())


def delete_class_record(session: Session, record_id: int) -> bool:
    record = session.get(ClassRecord, record_id)
    if record is None:
        return False
    session.delete(record)
    session.commit()
    return True


# ---------------------------------------------------------------------------
# Homework
# ---------------------------------------------------------------------------

def create_homework(
    session: Session,
    *,
    batch_id: int,
    title: str,
    assigned_date: date,
    description: str | None = None,
    due_date: date | None = None,
    notes: str | None = None,
    lesson_id: int | None = None,
    class_record_id: int | None = None,
) -> Homework:
    title = (title or "").strip()
    if not title:
        raise ValueError("Homework title is required.")
    hw = Homework(
        batch_id=batch_id,
        title=title,
        description=description.strip() if description else None,
        assigned_date=assigned_date,
        due_date=due_date,
        notes=notes.strip() if notes else None,
        lesson_id=lesson_id,
        class_record_id=class_record_id,
    )
    session.add(hw)
    session.commit()
    session.refresh(hw)
    return hw


def update_homework(
    session: Session,
    hw_id: int,
    *,
    title: str | None = None,
    description: str | None = None,
    assigned_date: date | None = None,
    due_date: date | None = None,
    notes: str | None = None,
) -> Homework:
    hw = session.get(Homework, hw_id)
    if hw is None:
        raise ValueError(f"Homework #{hw_id} not found.")
    if title is not None:
        t = title.strip()
        if not t:
            raise ValueError("Homework title cannot be empty.")
        hw.title = t
    if description is not None:
        hw.description = description.strip() or None
    if assigned_date is not None:
        hw.assigned_date = assigned_date
    if due_date is not None:
        hw.due_date = due_date
    if notes is not None:
        hw.notes = notes.strip() or None
    session.commit()
    session.refresh(hw)
    return hw


def delete_homework(session: Session, hw_id: int) -> bool:
    hw = session.get(Homework, hw_id)
    if hw is None:
        return False
    session.delete(hw)
    session.commit()
    return True


def get_homeworks(
    session: Session,
    batch_id: int | None = None,
    upcoming_only: bool = False,
    overdue_only: bool = False,
    limit: int | None = None,
) -> list[Homework]:
    today = date.today()
    stmt = (
        select(Homework)
        .options(
            selectinload(Homework.lesson),
            selectinload(Homework.batch),
        )
        .order_by(Homework.due_date.asc(), Homework.assigned_date.desc())
    )
    if batch_id is not None:
        stmt = stmt.where(Homework.batch_id == batch_id)
    if upcoming_only:
        stmt = stmt.where(
            and_(Homework.due_date >= today, Homework.due_date.isnot(None))
        )
    if overdue_only:
        stmt = stmt.where(
            and_(Homework.due_date < today, Homework.due_date.isnot(None))
        )
    if limit:
        stmt = stmt.limit(limit)
    return list(session.scalars(stmt).all())


# ---------------------------------------------------------------------------
# Dashboard helpers
# ---------------------------------------------------------------------------

def get_today_lessons(session: Session, batch_id: int | None = None) -> list[Lesson]:
    return get_lessons_for_date(session, date.today(), batch_id=batch_id)


def get_lessons_for_date(
    session: Session,
    lesson_date: date,
    batch_id: int | None = None,
) -> list[Lesson]:
    stmt = (
        select(Lesson)
        .where(
            Lesson.planned_date == lesson_date,
            Lesson.status.in_(["PLANNED", "IN_PROGRESS"]),
        )
        .order_by(Lesson.id)
    )
    if batch_id is not None:
        stmt = stmt.where(Lesson.batch_id == batch_id)
    return list(session.scalars(stmt).all())