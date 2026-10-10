import os
import sys
from datetime import date
from decimal import Decimal
import pytest
from PyQt6.QtWidgets import QApplication

from app.ui.fee_dialogs import (
    GenerateFeesDialog,
    CreateFeeDialog,
    MONTH_NAMES,
)


@pytest.fixture(scope="session")
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_fees_page_ui_components(qapp):
    from app.ui.main_window import MainWindow

    win = MainWindow()
    win.change_page(4)

    assert win.pages.currentIndex() == 4
    assert hasattr(win, "fees_table")
    assert win.fees_table.columnCount() == 10
    assert hasattr(win, "fees_kpi_total_due")
    assert hasattr(win, "fees_kpi_collected")
    assert hasattr(win, "fees_kpi_outstanding")
    assert hasattr(win, "fees_kpi_overdue")
    assert hasattr(win, "fee_search_input")
    assert hasattr(win, "fee_batch_filter")
    assert hasattr(win, "fee_month_filter")
    assert hasattr(win, "fee_status_filter")
    assert hasattr(win, "fees_empty_label")

    # Filter reset test
    win.fee_search_input.setText("TestingSearchQuery")
    win.reset_fee_filters()
    assert win.fee_search_input.text() == ""
    assert win.fee_batch_filter.currentIndex() == 0
    assert win.fee_month_filter.currentIndex() == 0
    assert win.fee_status_filter.currentIndex() == 0


def test_generate_fees_dialog_ui(qapp):
    from app.ui.main_window import MainWindow

    win = MainWindow()
    dialog = GenerateFeesDialog(win)

    assert dialog.year_combo.count() >= 2
    assert dialog.month_combo.count() == 12
    assert dialog.amount_spin.value() > 0
    assert dialog.table.columnCount() == 5
    assert dialog.table.horizontalHeaderItem(0).text() == "Admission No."
    assert dialog.table.horizontalHeaderItem(4).text() == "Status"


def test_create_fee_dialog_ui(qapp):
    from app.ui.main_window import MainWindow

    win = MainWindow()
    dialog = CreateFeeDialog(win)

    assert hasattr(dialog, "student_combo")
    assert hasattr(dialog, "year_combo")
    assert hasattr(dialog, "month_combo")
    assert hasattr(dialog, "amt_spin")
    assert hasattr(dialog, "disc_spin")
    assert hasattr(dialog, "due_date_edit")
