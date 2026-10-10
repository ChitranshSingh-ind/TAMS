import os
import sys
import uuid
from datetime import date
from decimal import Decimal
import pytest
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox
from PyQt6.QtCore import Qt

from app.database.connection import SessionLocal
from app.services.expense_service import (
    create_expense,
    record_expense_payment,
    get_expense,
)
from app.ui.expense_dialogs import (
    AddExpenseDialog,
    EditExpenseDialog,
    RecordExpensePaymentDialog,
    ExpensePaymentHistoryDialog,
    FinancialAnalysisDialog,
)
from app.ui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def sample_expense():
    uid = uuid.uuid4().hex[:6]
    with SessionLocal() as session:
        exp = create_expense(
            session,
            description=f"Test Expense {uid}",
            category="Utilities",
            amount=5000.0,
            expense_date=date.today(),
            payee="Utility Provider",
            due_date=date.today(),
            notes="Automated test note",
        )
        pay = record_expense_payment(
            session,
            expense_id=exp.id,
            amount=2000.0,
            payment_date=date.today(),
            payment_method="UPI",
            reference_number="UPI-TEST",
        )
        yield {
            "expense_id": exp.id,
            "payment_id": pay.id,
            "description": exp.description,
        }


def test_expenses_page_ui_components(qapp, sample_expense):
    win = MainWindow()
    win.change_page(5)  # Expenses page is at index 5

    assert win.pages.currentIndex() == 5
    assert hasattr(win, "expenses_table")
    assert win.expenses_table.columnCount() == 10
    assert hasattr(win, "expenses_kpi_total")
    assert hasattr(win, "expenses_kpi_paid")
    assert hasattr(win, "expenses_kpi_outstanding")
    assert hasattr(win, "expenses_kpi_month")
    assert hasattr(win, "expense_search_input")
    assert hasattr(win, "expense_category_filter")
    assert hasattr(win, "expense_status_filter")
    assert hasattr(win, "expense_method_filter")
    assert hasattr(win, "expenses_empty_label")

    # Table contains rows
    assert win.expenses_table.rowCount() >= 1

    # Filter interaction & Reset
    win.expense_search_input.setText("TestingSearchQuery")
    win.reset_expense_filters()
    assert win.expense_search_input.text() == ""
    assert win.expense_category_filter.currentIndex() == 0
    assert win.expense_status_filter.currentIndex() == 0
    assert win.expense_method_filter.currentIndex() == 0


def test_financial_analysis_page_ui_components(qapp):
    win = MainWindow()
    win.change_page(7)  # Analysis page is at index 7

    assert win.pages.currentIndex() == 7
    assert hasattr(win, "analysis_kpi_inflow")
    assert hasattr(win, "analysis_kpi_outflow")
    assert hasattr(win, "analysis_kpi_net_cash")
    assert hasattr(win, "analysis_kpi_receivables")
    assert hasattr(win, "analysis_kpi_payables")
    assert hasattr(win, "analysis_kpi_accrual")
    assert hasattr(win, "analysis_table")
    assert win.analysis_table.columnCount() == 7
    assert win.analysis_table.rowCount() == 6


def test_add_expense_dialog_ui(qapp, monkeypatch):
    win = MainWindow()
    dialog = AddExpenseDialog(win)

    assert dialog.desc_input.text() == ""
    assert dialog.category_combo.count() >= 5
    assert dialog.amount_spin.value() > 0
    assert dialog.pay_now_cb.isChecked() is True

    # Toggle Pay Now checkbox off and on
    dialog.pay_now_cb.setChecked(False)
    assert dialog.pay_amount_spin.isEnabled() is False
    dialog.pay_now_cb.setChecked(True)
    assert dialog.pay_amount_spin.isEnabled() is True
    assert dialog.pay_method_combo.isEnabled() is True


def test_edit_expense_dialog_ui(qapp, sample_expense):
    win = MainWindow()
    exp_id = sample_expense["expense_id"]
    dialog = EditExpenseDialog(exp_id, win)

    assert dialog.desc_input.text() == sample_expense["description"]
    assert dialog.amount_spin.value() == 5000.0
    assert dialog.category_combo.currentText() == "Utilities"
    assert dialog.payee_input.text() == "Utility Provider"


def test_record_expense_payment_dialog_ui(qapp, sample_expense):
    win = MainWindow()
    exp_id = sample_expense["expense_id"]
    dialog = RecordExpensePaymentDialog(exp_id, win)

    # Outstanding balance should be ₹3,000.00
    assert dialog.amount_input.maximum() == 3000.0
    assert dialog.amount_input.value() == 3000.0
    assert dialog.method_combo.count() >= 4


def test_expense_payment_history_dialog_ui(qapp, sample_expense):
    win = MainWindow()
    exp_id = sample_expense["expense_id"]
    dialog = ExpensePaymentHistoryDialog(exp_id, win)

    assert dialog.table.rowCount() >= 1
    # Check that payment amount is displayed
    assert "₹2,000.00" in dialog.table.item(0, 1).text()


def test_financial_analysis_dialog_ui(qapp):
    win = MainWindow()
    dialog = FinancialAnalysisDialog(win)

    assert hasattr(dialog, "trend_table")
    assert dialog.trend_table.columnCount() == 6
    assert dialog.trend_table.rowCount() == 6
