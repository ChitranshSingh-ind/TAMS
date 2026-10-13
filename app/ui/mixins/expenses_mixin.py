"""
TAMS Expenses Page Controller Mixin.

Tracks operational costs, coaching expenditures, recurring bills (Rent, Utilities, Supplies),
partial/full expense payments, category analytics, and data export.
"""

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database.connection import SessionLocal
from app.services.expense_service import (
    DEFAULT_EXPENSE_CATEGORIES,
    EXPENSE_PAYMENT_METHODS,
    delete_expense,
    export_expenses_csv,
    get_expenses,
    get_expenses_summary,
)
from app.ui.expense_dialogs import (
    AddExpenseDialog,
    EditExpenseDialog,
    ExpensePaymentHistoryDialog,
    FinancialAnalysisDialog,
    RecordExpensePaymentDialog,
)
from app.ui.table_utils import (
    TableSizingStrategy,
    auto_fit_columns,
    configure_table_ux,
)


class ExpensesMixin:
    """
    Mixin providing Expenses UI: financial expense tables, payment dialogues,
    status filters, and CSV export utilities.
    """

    def create_expenses_page(self) -> QWidget:
        """Constructs the Expenses page layout with KPI summaries and payment logs."""
        page = QWidget()
        page.setObjectName("expensesPage")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 28)
        layout.setSpacing(18)

        # ── Header ─────────────────────────────────────────
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        title = QLabel("Expenses")
        title.setObjectName("expensesPageTitle")
        subtitle = QLabel("Track coaching expenses, manage vendor liabilities, and control operating cash flow.")
        subtitle.setObjectName("expensesPageSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        # Action Buttons
        add_exp_btn = QPushButton("＋ Add Expense")
        add_exp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_exp_btn.setFixedHeight(40)
        add_exp_btn.setStyleSheet("""
            QPushButton {
                background: #012D54;
                color: #FEFEFE;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #04294D;
            }
        """)
        add_exp_btn.clicked.connect(self.open_add_expense_dialog)
        header_layout.addWidget(add_exp_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        overview_btn = QPushButton("📊 Financial Overview")
        overview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        overview_btn.setFixedHeight(40)
        overview_btn.setStyleSheet("""
            QPushButton {
                background: #E9DEBA;
                color: #012D54;
                border: 1px solid #D9B85F;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #D9B85F;
            }
        """)
        overview_btn.clicked.connect(self.open_financial_analysis_dialog)
        header_layout.addWidget(overview_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        export_btn = QPushButton("📥 Export CSV")
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.setFixedHeight(40)
        export_btn.setStyleSheet("""
            QPushButton {
                background: #FEFEFE;
                color: #012D54;
                border: 1px solid #D9B85F;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #E9DEBA;
            }
        """)
        export_btn.clicked.connect(self.export_expenses_csv)
        header_layout.addWidget(export_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        layout.addLayout(header_layout)

        # ── KPI Cards ──────────────────────────────────────
        kpi_layout = QGridLayout()
        kpi_layout.setHorizontalSpacing(15)
        kpi_layout.setVerticalSpacing(10)

        def make_expense_kpi_card(card_title, default_val, text_color="#012D54"):
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background-color: #FEFEFE;
                    border: 1px solid #E9DEBA;
                    border-radius: 10px;
                }
            """)
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(18, 14, 18, 14)
            c_layout.setSpacing(4)
            c_title = QLabel(card_title)
            c_title.setStyleSheet("color: #615F4B; font-size: 12px; font-weight: 600;")
            c_val = QLabel(default_val)
            c_val.setStyleSheet(f"color: {text_color}; font-size: 22px; font-weight: 700;")
            c_layout.addWidget(c_title)
            c_layout.addWidget(c_val)
            return card, c_val

        c1, self.expenses_kpi_total = make_expense_kpi_card("Total Expenses Incurred", "₹0.00", "#012D54")
        c2, self.expenses_kpi_paid = make_expense_kpi_card("Total Paid Out", "₹0.00", "#16A34A")
        c3, self.expenses_kpi_outstanding = make_expense_kpi_card("Outstanding Payables", "₹0.00", "#D97706")
        c4, self.expenses_kpi_month = make_expense_kpi_card("This Month Expenses", "₹0.00", "#2563EB")

        kpi_layout.addWidget(c1, 0, 0)
        kpi_layout.addWidget(c2, 0, 1)
        kpi_layout.addWidget(c3, 0, 2)
        kpi_layout.addWidget(c4, 0, 3)

        layout.addLayout(kpi_layout)

        # ── Filters & Search Toolbar ───────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.expense_search_input = QLineEdit()
        self.expense_search_input.setPlaceholderText("Search by description, vendor, payee...")
        self.expense_search_input.setClearButtonEnabled(True)
        self.expense_search_input.setFixedHeight(36)
        self.expense_search_input.setStyleSheet("""
            QLineEdit {
                background-color: #FEFEFE;
                color: #012D54;
                border: 1px solid #E9DEBA;
                border-radius: 7px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1.5px solid #012D54;
            }
        """)
        self.expense_search_input.textChanged.connect(self.load_expenses)
        toolbar.addWidget(self.expense_search_input, 2)

        # Category filter
        self.expense_category_filter = QComboBox()
        self.expense_category_filter.setFixedHeight(36)
        self.expense_category_filter.addItem("All Categories", None)
        for cat in DEFAULT_EXPENSE_CATEGORIES:
            self.expense_category_filter.addItem(cat, cat)
        self.expense_category_filter.currentIndexChanged.connect(self.load_expenses)
        toolbar.addWidget(self.expense_category_filter, 1)

        # Status filter
        self.expense_status_filter = QComboBox()
        self.expense_status_filter.setFixedHeight(36)
        self.expense_status_filter.addItem("All Statuses", "ALL")
        self.expense_status_filter.addItem("Unpaid / Pending", "PENDING")
        self.expense_status_filter.addItem("Partially Paid", "PARTIALLY_PAID")
        self.expense_status_filter.addItem("Paid", "PAID")
        self.expense_status_filter.addItem("Overdue", "OVERDUE")
        self.expense_status_filter.currentIndexChanged.connect(self.load_expenses)
        toolbar.addWidget(self.expense_status_filter, 1)

        # Payment Method filter
        self.expense_method_filter = QComboBox()
        self.expense_method_filter.setFixedHeight(36)
        self.expense_method_filter.addItem("All Payment Methods", "ALL")
        for m in EXPENSE_PAYMENT_METHODS:
            self.expense_method_filter.addItem(m, m)
        self.expense_method_filter.currentIndexChanged.connect(self.load_expenses)
        toolbar.addWidget(self.expense_method_filter, 1)

        # Reset button
        reset_btn = QPushButton("Reset")
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.setFixedHeight(36)
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #FEFEFE;
                color: #615F4B;
                border: 1px solid #E9DEBA;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #E9DEBA;
                color: #012D54;
            }
        """)
        reset_btn.clicked.connect(self.reset_expense_filters)
        toolbar.addWidget(reset_btn)

        layout.addLayout(toolbar)

        # ── Expenses Table ─────────────────────────────────
        self.expenses_table = QTableWidget()
        self.expenses_table.setObjectName("expensesTable")
        self.expenses_table.setColumnCount(10)
        self.expenses_table.setHorizontalHeaderLabels([
            "Date",
            "Description",
            "Category",
            "Payee / Vendor",
            "Total Amount",
            "Paid",
            "Outstanding",
            "Due Date",
            "Status",
            "Actions",
        ])
        self.expenses_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.expenses_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.expenses_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        configure_table_ux(
            self.expenses_table,
            column_widths=[120, 240, 140, 160, 110, 110, 110, 110, 110, 235],
            stretch_column=1,
            flexible_columns=[1, 3],
            fixed_columns=[9],
            strategy=TableSizingStrategy.WIDE_SCROLLABLE,
        )

        layout.addWidget(self.expenses_table, 1)

        # Empty state label
        self.expenses_empty_label = QLabel(
            "No expenses match the current filters. Click '＋ Add Expense' above to record a new coaching expense."
        )
        self.expenses_empty_label.setStyleSheet("""
            QLabel {
                color: #615F4B;
                font-size: 13px;
                padding: 14px;
                background: #F8F6EA;
                border: 1px dashed #D9B85F;
                border-radius: 8px;
            }
        """)
        self.expenses_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.expenses_empty_label.setVisible(False)
        layout.addWidget(self.expenses_empty_label)

        return page

    def load_expenses(self):
        if not hasattr(self, "expenses_table"):
            return

        search = self.expense_search_input.text().strip() or None
        category = self.expense_category_filter.currentData()
        status = self.expense_status_filter.currentData()
        method = self.expense_method_filter.currentData()

        with SessionLocal() as session:
            expenses = get_expenses(
                session,
                search=search,
                category=category,
                payment_status=status,
                payment_method=method,
            )
            summary = get_expenses_summary(
                session,
                search=search,
                category=category,
            )

        # Update KPI Cards
        self.expenses_kpi_total.setText(f"₹{summary['total_expenses']:,.2f}")
        self.expenses_kpi_paid.setText(f"₹{summary['total_paid']:,.2f}")
        self.expenses_kpi_outstanding.setText(f"₹{summary['total_outstanding']:,.2f}")
        self.expenses_kpi_month.setText(f"₹{summary['current_month_expenses']:,.2f}")

        # Update table rows
        self.expenses_table.setRowCount(len(expenses))
        for row, exp in enumerate(expenses):
            date_str = exp.expense_date.strftime("%d %b %Y") if exp.expense_date else "—"
            date_item = QTableWidgetItem(date_str)
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.expenses_table.setItem(row, 0, date_item)

            desc_item = QTableWidgetItem(exp.description)
            desc_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.expenses_table.setItem(row, 1, desc_item)

            cat_item = QTableWidgetItem(exp.category)
            cat_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.expenses_table.setItem(row, 2, cat_item)

            payee_item = QTableWidgetItem(exp.payee or "—")
            payee_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.expenses_table.setItem(row, 3, payee_item)

            amt_item = QTableWidgetItem(f"₹{exp.amount:,.2f}")
            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.expenses_table.setItem(row, 4, amt_item)

            paid_item = QTableWidgetItem(f"₹{exp.total_paid:,.2f}")
            paid_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.expenses_table.setItem(row, 5, paid_item)

            bal_val = exp.outstanding_balance
            bal_item = QTableWidgetItem(f"₹{bal_val:,.2f}")
            bal_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if bal_val > 0:
                bal_item.setForeground(Qt.GlobalColor.darkRed)
            self.expenses_table.setItem(row, 6, bal_item)

            due_date_str = exp.due_date.strftime("%d %b %Y") if exp.due_date else "—"
            due_item = QTableWidgetItem(due_date_str)
            due_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.expenses_table.setItem(row, 7, due_item)

            # Status Badge Widget
            status_calc = exp.calculate_status()
            status_widget = QWidget()
            status_layout = QHBoxLayout(status_widget)
            status_layout.setContentsMargins(0, 0, 0, 0)
            status_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            status_badge = QLabel()
            status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if status_calc == "PAID":
                status_badge.setText("Paid")
                status_badge.setStyleSheet("background-color: #DCFCE7; color: #15803D; font-size: 11px; font-weight: 700; padding: 4px 8px; border-radius: 4px;")
            elif status_calc == "PARTIALLY_PAID":
                status_badge.setText("Partial")
                status_badge.setStyleSheet("background-color: #FEF3C7; color: #B45309; font-size: 11px; font-weight: 700; padding: 4px 8px; border-radius: 4px;")
            elif status_calc == "OVERDUE":
                status_badge.setText("Overdue")
                status_badge.setStyleSheet("background-color: #FEE2E2; color: #B91C1C; font-size: 11px; font-weight: 700; padding: 4px 8px; border-radius: 4px;")
            elif status_calc == "VOID":
                status_badge.setText("Void")
                status_badge.setStyleSheet("background-color: #F3F4F6; color: #6B7280; font-size: 11px; font-weight: 700; padding: 4px 8px; border-radius: 4px;")
            else:
                status_badge.setText("Unpaid")
                status_badge.setStyleSheet("background-color: #DBEAFE; color: #1D4ED8; font-size: 11px; font-weight: 700; padding: 4px 8px; border-radius: 4px;")

            status_layout.addWidget(status_badge)
            self.expenses_table.setCellWidget(row, 8, status_widget)

            # Action Buttons Widget
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 2, 4, 2)
            action_layout.setSpacing(6)
            action_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            pay_btn = QPushButton("Pay")
            pay_btn.setFixedSize(50, 28)
            pay_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            pay_btn.setEnabled(bal_val > 0 and status_calc != "VOID")
            pay_btn.setStyleSheet("""
                QPushButton {
                    background-color: #012D54;
                    color: #FEFEFE;
                    border: none;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover:enabled {
                    background-color: #04294D;
                }
                QPushButton:disabled {
                    background-color: #E5E7EB;
                    color: #9CA3AF;
                }
            """)
            pay_btn.clicked.connect(lambda ch, eid=exp.id: self.open_record_expense_payment_dialog(eid))
            action_layout.addWidget(pay_btn)

            hist_btn = QPushButton("History")
            hist_btn.setFixedSize(58, 28)
            hist_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            hist_btn.setStyleSheet("""
                QPushButton {
                    background-color: #E9DEBA;
                    color: #012D54;
                    border: 1px solid #D9B85F;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #D9B85F;
                }
            """)
            hist_btn.clicked.connect(lambda ch, eid=exp.id: self.open_expense_payment_history_dialog(eid))
            action_layout.addWidget(hist_btn)

            edit_btn = QPushButton("Edit")
            edit_btn.setFixedSize(46, 28)
            edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_btn.setStyleSheet("""
                QPushButton {
                    background-color: #FEFEFE;
                    color: #012D54;
                    border: 1px solid #E9DEBA;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #F1EBD3;
                }
            """)
            edit_btn.clicked.connect(lambda ch, eid=exp.id: self.open_edit_expense_dialog(eid))
            action_layout.addWidget(edit_btn)

            del_btn = QPushButton("Delete")
            del_btn.setFixedSize(54, 28)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setStyleSheet("""
                QPushButton {
                    background-color: #FEE2E2;
                    color: #B91C1C;
                    border: 1px solid #FCA5A5;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #FECACA;
                }
            """)
            del_btn.clicked.connect(lambda ch, eid=exp.id: self.confirm_delete_expense(eid))
            action_layout.addWidget(del_btn)

            self.expenses_table.setCellWidget(row, 9, action_widget)

        self.expenses_empty_label.setVisible(len(expenses) == 0)
        auto_fit_columns(self.expenses_table)

    def reset_expense_filters(self):
        if not hasattr(self, "expense_search_input"):
            return
        self.expense_search_input.blockSignals(True)
        self.expense_category_filter.blockSignals(True)
        self.expense_status_filter.blockSignals(True)
        self.expense_method_filter.blockSignals(True)

        self.expense_search_input.clear()
        self.expense_category_filter.setCurrentIndex(0)
        self.expense_status_filter.setCurrentIndex(0)
        self.expense_method_filter.setCurrentIndex(0)

        self.expense_search_input.blockSignals(False)
        self.expense_category_filter.blockSignals(False)
        self.expense_status_filter.blockSignals(False)
        self.expense_method_filter.blockSignals(False)

        self.load_expenses()

    def export_expenses_csv(self):
        default_filename = f"expenses_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Expenses to CSV",
            default_filename,
            "CSV Files (*.csv)",
        )
        if not filepath:
            return

        search = self.expense_search_input.text().strip() or None
        cat = self.expense_category_filter.currentData()
        status = self.expense_status_filter.currentData()

        with SessionLocal() as session:
            try:
                count = export_expenses_csv(
                    session,
                    filepath,
                    search=search,
                    category=cat,
                    payment_status=status,
                )
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Successfully exported {count} expense record(s) to:\n{filepath}",
                )
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Failed to export CSV: {e}")

    def open_add_expense_dialog(self):
        dialog = AddExpenseDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_expenses()
            self.refresh_dashboard()

    def open_edit_expense_dialog(self, expense_id: int):
        dialog = EditExpenseDialog(expense_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_expenses()
            self.refresh_dashboard()

    def open_record_expense_payment_dialog(self, expense_id: int):
        dialog = RecordExpensePaymentDialog(expense_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_expenses()
            self.refresh_dashboard()

    def open_expense_payment_history_dialog(self, expense_id: int):
        dialog = ExpensePaymentHistoryDialog(expense_id, self)
        dialog.exec()
        self.load_expenses()
        self.refresh_dashboard()

    def confirm_delete_expense(self, expense_id: int):
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Are you sure you want to delete this expense record?\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            with SessionLocal() as session:
                try:
                    deleted = delete_expense(session, expense_id)
                    if deleted:
                        QMessageBox.information(self, "Deleted", "Expense record deleted successfully.")
                        self.load_expenses()
                        self.refresh_dashboard()
                except ValueError as ve:
                    QMessageBox.warning(self, "Cannot Delete", str(ve))
                except Exception as ex:
                    QMessageBox.critical(self, "Error", f"Failed to delete expense: {ex}")

    def open_financial_analysis_dialog(self):
        dialog = FinancialAnalysisDialog(self)
        dialog.exec()

    # ═════════════════════════════════════════════════════════════════════════
    # ── FINANCIAL ANALYSIS PAGE (PAGE 7) ────────────────────────────────────
    # ═════════════════════════════════════════════════════════════════════════

