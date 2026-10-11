"""
UI tests for the Teaching module — Teaching page components and dialogs.
"""
import os
import sys
import uuid

import pytest
from PyQt6.QtWidgets import QApplication, QDialog, QTabWidget, QTableWidget

from app.database.connection import SessionLocal
from app.database.models.batch import Batch
from app.services.lesson_service import create_lesson
from app.ui.main_window import MainWindow
from app.ui.teaching_dialogs import (
    HomeworkDialog,
    LessonDetailDialog,
    LessonDialog,
    RecordClassDialog,
)

from datetime import date


@pytest.fixture(scope="session")
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture(scope="session")
def main_window(qapp):
    w = MainWindow()
    return w


@pytest.fixture
def sample_lesson():
    """Create a lesson in the real DB (needs a real batch)."""
    uid = uuid.uuid4().hex[:6]
    with SessionLocal() as session:
        # Create a temporary batch
        b = Batch(name=f"TmpBatch-{uid}", monthly_fee=500)
        session.add(b)
        session.flush()
        lesson = create_lesson(
            session,
            batch_id=b.id,
            title=f"UI Test Lesson {uid}",
            planned_date=date.today(),
            chapter="Test Chapter",
            topic="Test Topic",
        )
        session.commit()
        yield lesson.id


# ─────────────────────────────────────────────────────────────────────────────
# Teaching page navigation
# ─────────────────────────────────────────────────────────────────────────────

def test_teaching_page_navigation(main_window):
    """Switching to page 6 loads the Teaching page without errors."""
    main_window.change_page(6)
    assert main_window.pages.currentIndex() == 6


def test_teaching_page_has_kpi_cards(main_window):
    """KPI label attributes exist after page creation."""
    assert hasattr(main_window, "teaching_kpi_planned")
    assert hasattr(main_window, "teaching_kpi_completed")
    assert hasattr(main_window, "teaching_kpi_upcoming")
    assert hasattr(main_window, "teaching_kpi_overdue")
    assert hasattr(main_window, "teaching_kpi_pct")


def test_teaching_page_has_tab_widget(main_window):
    """Tab widget exists with 4 tabs."""
    assert hasattr(main_window, "teaching_tabs")
    tabs = main_window.teaching_tabs
    assert isinstance(tabs, QTabWidget)
    assert tabs.count() == 4


def test_teaching_page_tab_labels(main_window):
    tabs = main_window.teaching_tabs
    labels = [tabs.tabText(i) for i in range(tabs.count())]
    assert "Lessons" in labels
    assert "Class History" in labels
    assert "Homework" in labels
    assert "Progress" in labels


def test_teaching_page_has_tables(main_window):
    """All four tables are present."""
    assert hasattr(main_window, "lessons_table")
    assert hasattr(main_window, "class_records_table")
    assert hasattr(main_window, "homework_table")
    assert hasattr(main_window, "progress_table")
    assert isinstance(main_window.lessons_table, QTableWidget)
    assert isinstance(main_window.class_records_table, QTableWidget)
    assert isinstance(main_window.homework_table, QTableWidget)
    assert isinstance(main_window.progress_table, QTableWidget)


def test_teaching_page_lessons_table_columns(main_window):
    assert main_window.lessons_table.columnCount() == 8


def test_teaching_page_class_records_table_columns(main_window):
    assert main_window.class_records_table.columnCount() == 7


def test_teaching_page_homework_table_columns(main_window):
    assert main_window.homework_table.columnCount() == 6


def test_teaching_page_progress_table_columns(main_window):
    assert main_window.progress_table.columnCount() == 5


def test_teaching_page_has_filter_controls(main_window):
    """Filter inputs are present."""
    assert hasattr(main_window, "lesson_search_input")
    assert hasattr(main_window, "lesson_batch_filter")
    assert hasattr(main_window, "lesson_status_filter")


def test_reset_teaching_filters(main_window):
    """reset_teaching_filters clears search and resets combos to index 0."""
    main_window.lesson_search_input.setText("something")
    main_window.lesson_status_filter.setCurrentIndex(2)
    main_window.reset_teaching_filters()
    assert main_window.lesson_search_input.text() == ""
    assert main_window.lesson_status_filter.currentIndex() == 0


# ─────────────────────────────────────────────────────────────────────────────
# load_teaching populates the table
# ─────────────────────────────────────────────────────────────────────────────

def test_load_teaching_runs_without_error(main_window):
    """load_teaching() completes without raising."""
    main_window.load_teaching()  # Should not raise


# ─────────────────────────────────────────────────────────────────────────────
# Dialog UI tests
# ─────────────────────────────────────────────────────────────────────────────

def test_lesson_dialog_add_mode(qapp):
    dlg = LessonDialog()
    assert dlg.windowTitle() == "Plan a Lesson"
    assert hasattr(dlg, "title_edit")
    assert hasattr(dlg, "batch_combo")
    assert hasattr(dlg, "date_edit")  # LessonDialog uses date_edit
    dlg.close()


def test_lesson_dialog_edit_mode(qapp, sample_lesson):
    dlg = LessonDialog(lesson_id=sample_lesson)
    assert dlg.windowTitle() == "Edit Lesson"
    assert dlg.title_edit.text() != ""  # populated from DB
    dlg.close()


def test_record_class_dialog_add_mode(qapp):
    dlg = RecordClassDialog()
    assert dlg.windowTitle() == "Record Completed Class"
    assert hasattr(dlg, "batch_combo")
    assert hasattr(dlg, "date_edit")
    assert hasattr(dlg, "chapter_edit")
    assert hasattr(dlg, "topic_edit")
    dlg.close()


def test_homework_dialog_add_mode(qapp):
    dlg = HomeworkDialog()
    assert dlg.windowTitle() == "Add Homework / Assignment"
    assert hasattr(dlg, "batch_combo")
    assert hasattr(dlg, "title_edit")
    assert hasattr(dlg, "assigned_edit")  # HomeworkDialog uses assigned_edit
    dlg.close()


def test_lesson_detail_dialog(qapp, sample_lesson):
    dlg = LessonDetailDialog(sample_lesson)
    # Just verify it opens without error
    dlg.close()


def test_load_teaching_with_empty_lessons_and_records(qapp):
    win = MainWindow()
    win.change_page(6)  # Teaching page
    # Filter by a search that yields 0 lessons
    win.lesson_search_input.setText("NonExistentLesson_XYZ_999")
    win.load_teaching()
    assert win.lessons_table.rowCount() == 0
    # Clear filter and reload
    win.lesson_search_input.clear()
    win.load_teaching()

