"""
Tests for app.services.lesson_service (Teaching module).
"""
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.models.batch import Batch
from app.services.lesson_service import (
    LESSON_STATUSES,
    create_lesson,
    update_lesson,
    delete_lesson,
    get_lesson,
    get_lessons,
    get_upcoming_lessons,
    get_overdue_lessons,
    mark_lesson_completed,
    reschedule_lesson,
    get_teaching_summary,
    get_chapters_progress,
    create_class_record,
    update_class_record,
    delete_class_record,
    get_class_records,
    create_homework,
    update_homework,
    delete_homework,
    get_homeworks,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        yield session


@pytest.fixture
def batch(db_session):
    b = Batch(name="Test Batch", monthly_fee=1000)
    db_session.add(b)
    db_session.commit()
    db_session.refresh(b)
    return b


@pytest.fixture
def batch2(db_session):
    b = Batch(name="Other Batch", monthly_fee=1200)
    db_session.add(b)
    db_session.commit()
    db_session.refresh(b)
    return b


# ────────────────────────────────────────────────────────────────────────────
# Lesson CRUD + validation
# ────────────────────────────────────────────────────────────────────────────

def test_create_lesson_validation(db_session, batch):
    with pytest.raises(ValueError, match="title is required"):
        create_lesson(db_session, batch_id=batch.id, title="  ", planned_date=date.today())

    with pytest.raises(ValueError, match="Invalid status"):
        create_lesson(db_session, batch_id=batch.id, title="L1", planned_date=date.today(), status="BAD")


def test_create_lesson_success(db_session, batch):
    today = date.today()
    lesson = create_lesson(
        db_session,
        batch_id=batch.id,
        title="Quadratic Equations",
        planned_date=today,
        chapter="Algebra",
        topic="Factoring",
        duration_minutes=60,
        notes="Bring textbook",
    )
    assert lesson.id is not None
    assert lesson.title == "Quadratic Equations"
    assert lesson.chapter == "Algebra"
    assert lesson.status == "PLANNED"


def test_update_lesson(db_session, batch):
    lesson = create_lesson(db_session, batch_id=batch.id, title="Old Title", planned_date=date.today())
    updated = update_lesson(db_session, lesson.id, title="New Title", chapter="Ch 2", status="IN_PROGRESS")
    assert updated.title == "New Title"
    assert updated.chapter == "Ch 2"
    assert updated.status == "IN_PROGRESS"


def test_delete_lesson(db_session, batch):
    lesson = create_lesson(db_session, batch_id=batch.id, title="To Delete", planned_date=date.today())
    lid = lesson.id
    delete_lesson(db_session, lid)
    assert get_lesson(db_session, lid) is None


def test_get_lessons_batch_filter(db_session, batch, batch2):
    create_lesson(db_session, batch_id=batch.id,  title="Lesson A", planned_date=date.today())
    create_lesson(db_session, batch_id=batch2.id, title="Lesson B", planned_date=date.today())
    only_batch = get_lessons(db_session, batch_id=batch.id)
    assert all(l.batch_id == batch.id for l in only_batch)
    assert len(only_batch) == 1


def test_get_lessons_status_filter(db_session, batch):
    create_lesson(db_session, batch_id=batch.id, title="P1", planned_date=date.today(), status="PLANNED")
    create_lesson(db_session, batch_id=batch.id, title="C1", planned_date=date.today(), status="COMPLETED")
    planned = get_lessons(db_session, batch_id=batch.id, status="PLANNED")
    assert all(l.status == "PLANNED" for l in planned)


def test_get_lessons_search(db_session, batch):
    create_lesson(db_session, batch_id=batch.id, title="Trigonometry", planned_date=date.today(), chapter="Trig")
    create_lesson(db_session, batch_id=batch.id, title="Calculus", planned_date=date.today(), chapter="Calc")
    results = get_lessons(db_session, batch_id=batch.id, search="Trig")
    assert len(results) >= 1
    assert any("Trig" in (l.title + (l.chapter or "")) for l in results)


# ────────────────────────────────────────────────────────────────────────────
# Status transitions
# ────────────────────────────────────────────────────────────────────────────

def test_mark_lesson_completed(db_session, batch):
    lesson = create_lesson(db_session, batch_id=batch.id, title="Mark Done", planned_date=date.today())
    assert lesson.status == "PLANNED"
    mark_lesson_completed(db_session, lesson.id)
    refreshed = get_lesson(db_session, lesson.id)
    assert refreshed.status == "COMPLETED"


def test_reschedule_lesson(db_session, batch):
    lesson = create_lesson(db_session, batch_id=batch.id, title="Reschedule Me", planned_date=date.today())
    new_date = date.today() + timedelta(days=7)
    reschedule_lesson(db_session, lesson.id, new_date)
    refreshed = get_lesson(db_session, lesson.id)
    assert refreshed.planned_date == new_date


# ────────────────────────────────────────────────────────────────────────────
# Upcoming / overdue
# ────────────────────────────────────────────────────────────────────────────

def test_upcoming_and_overdue_lessons(db_session, batch):
    past_date   = date.today() - timedelta(days=3)
    future_date = date.today() + timedelta(days=3)
    create_lesson(db_session, batch_id=batch.id, title="Overdue L", planned_date=past_date)
    create_lesson(db_session, batch_id=batch.id, title="Future L",  planned_date=future_date)

    upcoming = get_upcoming_lessons(db_session, batch_id=batch.id, days=7)
    overdue  = get_overdue_lessons(db_session, batch_id=batch.id)

    assert any(l.title == "Future L"  for l in upcoming)
    assert any(l.title == "Overdue L" for l in overdue)


# ────────────────────────────────────────────────────────────────────────────
# Class records
# ────────────────────────────────────────────────────────────────────────────

def test_create_class_record(db_session, batch):
    lesson = create_lesson(db_session, batch_id=batch.id, title="Linked Lesson", planned_date=date.today())
    rec = create_class_record(
        db_session,
        batch_id=batch.id,
        class_date=date.today(),
        chapter="Ch 1",
        topic="Introduction",
        topics_completed="Intro done",
        notes="Good session",
        lesson_id=lesson.id,
    )
    assert rec.id is not None
    assert rec.lesson_id == lesson.id
    assert rec.chapter == "Ch 1"


def test_class_record_batch_filter(db_session, batch, batch2):
    create_class_record(db_session, batch_id=batch.id,  class_date=date.today())
    create_class_record(db_session, batch_id=batch2.id, class_date=date.today())
    records = get_class_records(db_session, batch_id=batch.id)
    assert all(r.batch_id == batch.id for r in records)
    assert len(records) == 1


def test_delete_class_record(db_session, batch):
    rec = create_class_record(db_session, batch_id=batch.id, class_date=date.today())
    rid = rec.id
    delete_class_record(db_session, rid)
    assert rid not in [r.id for r in get_class_records(db_session, batch_id=batch.id)]


def test_update_class_record(db_session, batch):
    rec = create_class_record(db_session, batch_id=batch.id, class_date=date.today(), chapter="Old Ch")
    updated = update_class_record(db_session, rec.id, chapter="New Ch", topic="New Topic")
    assert updated.chapter == "New Ch"
    assert updated.topic == "New Topic"


# ────────────────────────────────────────────────────────────────────────────
# Homework
# ────────────────────────────────────────────────────────────────────────────

def test_create_homework(db_session, batch):
    hw = create_homework(
        db_session,
        batch_id=batch.id,
        title="Exercise 1.2",
        description="Solve problems 1-10",
        assigned_date=date.today(),
        due_date=date.today() + timedelta(days=3),
    )
    assert hw.id is not None
    assert hw.title == "Exercise 1.2"


def test_homework_batch_filter(db_session, batch, batch2):
    create_homework(db_session, batch_id=batch.id,  title="HW for batch1", assigned_date=date.today())
    create_homework(db_session, batch_id=batch2.id, title="HW for batch2", assigned_date=date.today())
    hws = get_homeworks(db_session, batch_id=batch.id)
    assert all(h.batch_id == batch.id for h in hws)


def test_delete_homework(db_session, batch):
    hw = create_homework(db_session, batch_id=batch.id, title="Delete me", assigned_date=date.today())
    hid = hw.id
    delete_homework(db_session, hid)
    remaining = [h.id for h in get_homeworks(db_session, batch_id=batch.id)]
    assert hid not in remaining


def test_update_homework(db_session, batch):
    hw = create_homework(db_session, batch_id=batch.id, title="Old HW", assigned_date=date.today())
    updated = update_homework(db_session, hw.id, title="New HW", notes="Updated notes")
    assert updated.title == "New HW"


# ────────────────────────────────────────────────────────────────────────────
# Teaching summary
# ────────────────────────────────────────────────────────────────────────────

def test_get_teaching_summary(db_session, batch):
    today = date.today()
    create_lesson(db_session, batch_id=batch.id, title="P1", planned_date=today, status="PLANNED")
    create_lesson(db_session, batch_id=batch.id, title="C1", planned_date=today, status="COMPLETED")
    create_lesson(db_session, batch_id=batch.id, title="Ca1", planned_date=today, status="CANCELLED")
    create_homework(db_session, batch_id=batch.id, title="HW", assigned_date=today)

    summary = get_teaching_summary(db_session, batch_id=batch.id)
    assert summary["planned"] >= 1
    assert summary["completed"] >= 1
    assert summary["total_homework"] >= 1


def test_summary_cancelled_not_in_completion_pct(db_session, batch):
    """Cancelled lessons should not count toward completion percentage."""
    today = date.today()
    create_lesson(db_session, batch_id=batch.id, title="Done",      planned_date=today, status="COMPLETED")
    create_lesson(db_session, batch_id=batch.id, title="Cancelled", planned_date=today, status="CANCELLED")

    summary = get_teaching_summary(db_session, batch_id=batch.id)
    # completion_pct = completed / (total - cancelled)
    # 1 completed / 1 non-cancelled = 100%
    assert summary["completion_pct"] == 100.0


# ────────────────────────────────────────────────────────────────────────────
# Chapter progress
# ────────────────────────────────────────────────────────────────────────────

def test_get_chapters_progress(db_session, batch):
    today = date.today()
    create_lesson(db_session, batch_id=batch.id, title="L1", chapter="Ch A", planned_date=today, status="COMPLETED")
    create_lesson(db_session, batch_id=batch.id, title="L2", chapter="Ch A", planned_date=today, status="PLANNED")
    create_lesson(db_session, batch_id=batch.id, title="L3", chapter="Ch B", planned_date=today, status="COMPLETED")

    chapters = get_chapters_progress(db_session, batch_id=batch.id)
    ch_a = next((c for c in chapters if c["chapter"] == "Ch A"), None)
    ch_b = next((c for c in chapters if c["chapter"] == "Ch B"), None)

    assert ch_a is not None
    assert ch_a["total"] == 2
    assert ch_a["completed"] == 1
    assert ch_a["completion_pct"] == 50.0

    assert ch_b is not None
    assert ch_b["total"] == 1
    assert ch_b["completed"] == 1
    assert ch_b["completion_pct"] == 100.0
