import os
import sys
from datetime import date
from decimal import Decimal
import pytest
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox
from PyQt6.QtCore import Qt

from app.database.connection import SessionLocal
from app.services.batch_service import create_batch
from app.services.student_service import create_student
from app.services.fee_service import create_fee, record_payment
from app.ui.fee_dialogs import (
    GenerateFeesDialog,
    RecordPaymentDialog,
    PaymentHistoryDialog,
    EditFeeDialog,
    CreateFeeDialog,
)
from app.ui.main_window import MainWindow
from app.ui.add_student_dialog import AddStudentDialog
from app.ui.bulk_student_dialog import BulkStudentDialog
from app.ui.settings_dialog import SettingsDialog


@pytest.fixture(scope="session")
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


import uuid

@pytest.fixture
def sample_data():
    unique_id = uuid.uuid4().hex[:8]
    with SessionLocal() as session:
        batch = create_batch(session, name=f"Batch {unique_id}")
        student = create_student(
            session,
            first_name="Audit",
            last_name="Student",
            batch_id=batch.id,
            admission_number=f"AUD_{unique_id}",
        )
        fee = create_fee(
            session,
            student_id=student.id,
            batch_id=batch.id,
            academic_year="2026-2027",
            fee_month=date.today().month,
            amount_due=2500.0,
            discount=200.0,
            due_date=date.today(),
        )
        payment = record_payment(
            session,
            fee_id=fee.id,
            amount=1000.0,
            payment_date=date.today(),
            payment_method="Cash",
        )
        yield {
            "batch_id": batch.id,
            "student_id": student.id,
            "fee_id": fee.id,
            "payment_id": payment.id,
        }


def test_navigation_and_dashboard(qapp, sample_data):
    win = MainWindow()
    win.show()

    # Initial state should be Dashboard (page 0)
    assert win.pages.currentIndex() == 0
    assert hasattr(win, "students_count_label")
    assert hasattr(win, "fees_pending_label")
    assert hasattr(win, "attendance_count_label")
    assert hasattr(win, "upcoming_tests_label")

    # Test dashboard card navigation
    win.change_page(1)
    assert win.pages.currentIndex() == 1

    win.change_page(2)
    assert win.pages.currentIndex() == 2

    win.change_page(3)
    assert win.pages.currentIndex() == 3

    win.change_page(4)
    assert win.pages.currentIndex() == 4

    win.change_page(0)
    assert win.pages.currentIndex() == 0


def test_students_page_and_profile_dialog(qapp, sample_data, monkeypatch):
    win = MainWindow()
    win.change_page(1)

    assert win.students_table.columnCount() == 7
    assert win.students_table.horizontalHeaderItem(0).text() == "Admission No."
    assert win.students_table.horizontalHeaderItem(1).text() == "Student Name"

    # Test AddStudentDialog with auto-generate and custom toggle
    add_dialog = AddStudentDialog(batches=[], parent=win, default_admission_number="ADM-2026-0001")
    assert add_dialog.admission_number_input is not None
    assert add_dialog.auto_generate_admission_cb.isChecked() is True
    assert add_dialog.admission_number_input.isReadOnly() is True
    assert add_dialog.admission_number_input.text() == "ADM-2026-0001"

    # Toggle to custom mode
    add_dialog.auto_generate_admission_cb.setChecked(False)
    assert add_dialog.admission_number_input.isReadOnly() is False
    add_dialog.admission_number_input.setText("CUSTOM-999")
    assert add_dialog.admission_number_input.text() == "CUSTOM-999"

    # Toggle back to auto-generate mode
    add_dialog.auto_generate_admission_cb.setChecked(True)
    assert add_dialog.admission_number_input.isReadOnly() is True
    assert add_dialog.admission_number_input.text() == "ADM-2026-0001"

    assert add_dialog.first_name_input is not None

    # Test student profile dialog (mocking exec to avoid blocking)
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    win.view_student(sample_data["student_id"])


def test_attendance_page(qapp, sample_data):
    win = MainWindow()
    win.change_page(2)

    assert win.attendance_table.columnCount() == 4
    assert win.attendance_table.horizontalHeaderItem(0).text() == "Admission No."
    assert win.attendance_table.horizontalHeaderItem(1).text() == "Student Name"
    assert win.attendance_table.horizontalHeaderItem(2).text() == "A"
    assert win.attendance_table.horizontalHeaderItem(3).text() == "P"
    assert hasattr(win, "attendance_date_picker")
    assert hasattr(win, "attendance_summary")


def test_results_page(qapp, sample_data):
    win = MainWindow()
    win.change_page(3)

    assert win.results_tests_table.columnCount() == 4
    assert win.results_tests_table.horizontalHeaderItem(0).text() == "Test Name"
    assert win.results_tests_table.horizontalHeaderItem(3).text() == "Maximum Marks"
    assert hasattr(win, "results_empty_label")


def test_fees_page_and_dialogs(qapp, sample_data, monkeypatch):
    win = MainWindow()
    win.change_page(4)

    # Fees table columns
    assert win.fees_table.columnCount() == 10
    headers = [win.fees_table.horizontalHeaderItem(i).text() for i in range(10)]
    assert "Admission No." in headers
    assert "Total Fee" in headers
    assert "Outstanding" in headers
    assert "Actions" in headers

    # KPI labels
    assert "₹" in win.fees_kpi_total_due.text()
    assert "₹" in win.fees_kpi_collected.text()
    assert "₹" in win.fees_kpi_outstanding.text()
    assert "₹" in win.fees_kpi_overdue.text()

    # Batch filter sync
    top_batch_id = sample_data["batch_id"]
    idx = win.batch_selector.findData(top_batch_id)
    if idx >= 0:
        win.batch_selector.setCurrentIndex(idx)
        assert win.fee_batch_filter.currentData() == top_batch_id

    # Test Fee Dialogs UI structures
    rec_dialog = RecordPaymentDialog(sample_data["fee_id"], parent=win)
    assert rec_dialog.amount_input.value() > 0

    hist_dialog = PaymentHistoryDialog(sample_data["fee_id"], parent=win)
    assert hist_dialog.table.columnCount() == 7

    edit_dialog = EditFeeDialog(sample_data["fee_id"], parent=win)
    assert edit_dialog.amt_spin.value() > 0


def test_settings_dialog(qapp):
    win = MainWindow()
    settings = SettingsDialog(parent=win)
    assert settings.settings_menu.count() >= 4


def test_bulk_student_dialog(qapp, sample_data, monkeypatch):
    win = MainWindow()
    win.change_page(1)
    assert hasattr(win, "bulk_actions_button")

    with SessionLocal() as session:
        from app.services.batch_service import get_active_batches
        batches = get_active_batches(session)

    dialog = BulkStudentDialog(batches=batches, initial_batch_id=sample_data["batch_id"], parent=win)
    assert dialog.table.columnCount() == 4
    assert dialog.table.rowCount() >= 1

    # Test selection
    dialog._select_all_visible()
    selected_ids = dialog._get_selected_student_ids()
    assert len(selected_ids) >= 1

    dialog._deselect_all()
    assert len(dialog._get_selected_student_ids()) == 0

    # Select all again
    dialog._select_all_visible()
    assert len(dialog._get_selected_student_ids()) >= 1

    # Test tab navigation
    assert dialog.tab_widget.count() == 2
    dialog.tab_widget.setCurrentIndex(0)
    assert "Promote" in dialog.tab_widget.tabText(0)
    dialog.tab_widget.setCurrentIndex(1)
    assert "Status" in dialog.tab_widget.tabText(1)

    # Test filtering
    dialog.search_input.setText("NonExistentStudentNameXYZ")
    assert dialog.table.isRowHidden(0) is True
    dialog.search_input.clear()
    assert dialog.table.isRowHidden(0) is False

    # Mock dialog exec and question prompts to test apply changes
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(QDialog, "accept", lambda self: None)

    # Test bulk status apply
    dialog.tab_widget.setCurrentIndex(1)
    dialog._on_apply_clicked()

