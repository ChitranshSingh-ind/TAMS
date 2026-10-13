
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
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
)

from app.database.connection import SessionLocal
from app.services.expense_service import (
    DEFAULT_EXPENSE_CATEGORIES,
    EXPENSE_PAYMENT_METHODS,
    create_expense,
    get_expense,
    get_expense_payments,
    record_expense_payment,
    reverse_expense_payment,
    update_expense,
)
from app.services.financial_service import (
    get_financial_summary,
    get_monthly_financial_comparison,
)
from app.ui.table_utils import configure_table_ux, TableSizingStrategy, auto_fit_columns

NAVY = "#012D54"
DARK_NAVY = "#04294D"
GOLD = "#D9B85F"
LIGHT_GOLD = "#E9DEBA"
CREAM = "#F8F6EA"
WHITE = "#FEFEFE"
TEXT = "#1F2937"
MUTED = "#615F4B"


class AddExpenseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Expense")
        self.resize(540, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        title = QLabel("Add New Expense")
        title.setStyleSheet(f"color: {NAVY}; font-size: 18px; font-weight: 700;")
        subtitle = QLabel("Record an operating expense, vendor bill, or coaching cost.")
        subtitle.setStyleSheet(f"color: {MUTED}; font-size: 13px;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        form = QFormLayout()
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("e.g. October Center Rent, Xerox Paper")
        self.desc_input.setFixedHeight(36)

        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.addItems(DEFAULT_EXPENSE_CATEGORIES)
        self.category_combo.setFixedHeight(36)

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0.01, 10000000.0)
        self.amount_spin.setValue(1000.0)
        self.amount_spin.setPrefix("₹ ")
        self.amount_spin.setFixedHeight(36)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setFixedHeight(36)

        self.payee_input = QLineEdit()
        self.payee_input.setPlaceholderText("e.g. Landlord name, Vendor, Store")
        self.payee_input.setFixedHeight(36)

        self.has_due_date_cb = QCheckBox("Has Due Date (Unpaid Bill / Liability)")
        self.due_date_edit = QDateEdit()
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDate(QDate.currentDate().addDays(7))
        self.due_date_edit.setFixedHeight(36)
        self.due_date_edit.setEnabled(False)
        self.has_due_date_cb.toggled.connect(self.due_date_edit.setEnabled)

        due_date_container = QHBoxLayout()
        due_date_container.setSpacing(8)
        due_date_container.addWidget(self.has_due_date_cb)
        due_date_container.addWidget(self.due_date_edit)

        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("Optional notes or memo")
        self.notes_input.setFixedHeight(36)

        form.addRow("Description *:", self.desc_input)
        form.addRow("Category *:", self.category_combo)
        form.addRow("Total Amount *:", self.amount_spin)
        form.addRow("Expense Date *:", self.date_edit)
        form.addRow("Payee / Vendor:", self.payee_input)
        form.addRow("Payment Term:", due_date_container)
        form.addRow("Notes:", self.notes_input)

        layout.addLayout(form)

        # ── Payment Details Box ────────────────────────────
        payment_box = QFrame()
        payment_box.setStyleSheet(f"""
            QFrame {{
                background-color: {WHITE};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        p_layout = QVBoxLayout(payment_box)
        p_layout.setSpacing(8)

        self.pay_now_cb = QCheckBox("Record payment now (Mark as Paid)")
        self.pay_now_cb.setChecked(True)
        self.pay_now_cb.setStyleSheet(f"color: {NAVY}; font-weight: 600; font-size: 13px;")
        p_layout.addWidget(self.pay_now_cb)

        p_form = QFormLayout()
        p_form.setSpacing(8)
        p_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        p_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.pay_method_combo = QComboBox()
        self.pay_method_combo.addItems(EXPENSE_PAYMENT_METHODS)
        self.pay_method_combo.setFixedHeight(34)

        self.pay_amount_spin = QDoubleSpinBox()
        self.pay_amount_spin.setRange(0.01, 10000000.0)
        self.pay_amount_spin.setValue(self.amount_spin.value())
        self.pay_amount_spin.setPrefix("₹ ")
        self.pay_amount_spin.setFixedHeight(34)

        self.amount_spin.valueChanged.connect(self._sync_payment_amount)

        self.ref_input = QLineEdit()
        self.ref_input.setPlaceholderText("Optional receipt/ref/cheque number")
        self.ref_input.setFixedHeight(34)

        p_form.addRow("Paid Amount:", self.pay_amount_spin)
        p_form.addRow("Payment Method:", self.pay_method_combo)
        p_form.addRow("Reference No.:", self.ref_input)
        p_layout.addLayout(p_form)

        self.pay_now_cb.toggled.connect(payment_box.setEnabled)
        layout.addWidget(payment_box)

        # Buttons
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_btn = btns.button(QDialogButtonBox.StandardButton.Save)
        if save_btn:
            save_btn.setText("Save Expense")
            save_btn.setObjectName("primaryDialogButton")
            save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn = btns.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setObjectName("secondaryDialogButton")
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btns.accepted.connect(self.save_expense)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _sync_payment_amount(self, val):
        if self.pay_now_cb.isChecked():
            self.pay_amount_spin.setValue(val)

    def save_expense(self):
        desc = self.desc_input.text().strip()
        cat = self.category_combo.currentText().strip()
        amount = self.amount_spin.value()
        exp_date = self.date_edit.date().toPyDate()
        payee = self.payee_input.text().strip() or None
        due_date = self.due_date_edit.date().toPyDate() if self.has_due_date_cb.isChecked() else None
        notes = self.notes_input.text().strip() or None

        if not desc:
            QMessageBox.warning(self, "Required Field", "Please enter an expense description.")
            self.desc_input.setFocus()
            return

        if not cat:
            QMessageBox.warning(self, "Required Field", "Please choose or enter an expense category.")
            self.category_combo.setFocus()
            return

        initial_payment = None
        if self.pay_now_cb.isChecked():
            p_amt = self.pay_amount_spin.value()
            if p_amt > amount:
                QMessageBox.warning(
                    self,
                    "Invalid Payment Amount",
                    f"Paid amount (₹{p_amt:,.2f}) cannot exceed total expense amount (₹{amount:,.2f}).",
                )
                return
            initial_payment = {
                "amount": p_amt,
                "payment_date": exp_date,
                "payment_method": self.pay_method_combo.currentText(),
                "reference_number": self.ref_input.text().strip() or None,
            }

        try:
            with SessionLocal() as session:
                create_expense(
                    session,
                    description=desc,
                    category=cat,
                    amount=amount,
                    expense_date=exp_date,
                    payee=payee,
                    due_date=due_date,
                    notes=notes,
                    initial_payment=initial_payment,
                )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error Saving Expense", str(e))


class EditExpenseDialog(QDialog):
    def __init__(self, expense_id: int, parent=None):
        super().__init__(parent)
        self.expense_id = expense_id
        self.setWindowTitle("Edit Expense")
        self.resize(500, 480)

        with SessionLocal() as session:
            expense = get_expense(session, expense_id)
            if not expense:
                QMessageBox.critical(self, "Error", "Expense record not found.")
                self.reject()
                return
            self.description = expense.description
            self.category = expense.category
            self.amount = expense.amount
            self.total_paid = expense.total_paid
            self.expense_date = expense.expense_date
            self.payee = expense.payee or ""
            self.due_date = expense.due_date
            self.notes = expense.notes or ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        title = QLabel("Edit Expense")
        title.setStyleSheet(f"color: {NAVY}; font-size: 18px; font-weight: 700;")
        subtitle = QLabel(f"Already Paid: ₹{self.total_paid:,.2f}")
        subtitle.setStyleSheet(f"color: {MUTED}; font-size: 13px;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        form = QFormLayout()
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.desc_input = QLineEdit()
        self.desc_input.setText(self.description)
        self.desc_input.setFixedHeight(36)

        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.addItems(DEFAULT_EXPENSE_CATEGORIES)
        idx = self.category_combo.findText(self.category)
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        else:
            self.category_combo.setCurrentText(self.category)
        self.category_combo.setFixedHeight(36)

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(max(0.01, self.total_paid), 10000000.0)
        self.amount_spin.setValue(self.amount)
        self.amount_spin.setPrefix("₹ ")
        self.amount_spin.setFixedHeight(36)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate(self.expense_date.year, self.expense_date.month, self.expense_date.day))
        self.date_edit.setFixedHeight(36)

        self.payee_input = QLineEdit()
        self.payee_input.setText(self.payee)
        self.payee_input.setFixedHeight(36)

        self.due_date_edit = QDateEdit()
        self.due_date_edit.setCalendarPopup(True)
        if self.due_date:
            self.due_date_edit.setDate(QDate(self.due_date.year, self.due_date.month, self.due_date.day))
        else:
            self.due_date_edit.setDate(QDate.currentDate())
        self.due_date_edit.setFixedHeight(36)

        self.notes_input = QLineEdit()
        self.notes_input.setText(self.notes)
        self.notes_input.setFixedHeight(36)

        form.addRow("Description *:", self.desc_input)
        form.addRow("Category *:", self.category_combo)
        form.addRow("Amount Due *:", self.amount_spin)
        form.addRow("Expense Date *:", self.date_edit)
        form.addRow("Payee / Vendor:", self.payee_input)
        form.addRow("Due Date:", self.due_date_edit)
        form.addRow("Notes:", self.notes_input)

        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_btn = btns.button(QDialogButtonBox.StandardButton.Save)
        if save_btn:
            save_btn.setText("Update Expense")
            save_btn.setObjectName("primaryDialogButton")
            save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn = btns.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setObjectName("secondaryDialogButton")
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btns.accepted.connect(self.save_edit)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def save_edit(self):
        desc = self.desc_input.text().strip()
        cat = self.category_combo.currentText().strip()
        amount = self.amount_spin.value()
        exp_date = self.date_edit.date().toPyDate()
        payee = self.payee_input.text().strip() or None
        due_date = self.due_date_edit.date().toPyDate()
        notes = self.notes_input.text().strip() or None

        if not desc:
            QMessageBox.warning(self, "Required Field", "Please enter an expense description.")
            return

        try:
            with SessionLocal() as session:
                update_expense(
                    session,
                    expense_id=self.expense_id,
                    description=desc,
                    category=cat,
                    amount=amount,
                    expense_date=exp_date,
                    payee=payee,
                    due_date=due_date,
                    notes=notes,
                )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error Updating Expense", str(e))


class RecordExpensePaymentDialog(QDialog):
    def __init__(self, expense_id: int, parent=None):
        super().__init__(parent)
        self.expense_id = expense_id
        self.setWindowTitle("Record Expense Payment")
        self.resize(500, 480)

        with SessionLocal() as session:
            expense = get_expense(session, expense_id)
            if not expense:
                QMessageBox.critical(self, "Error", "Expense record not found.")
                self.reject()
                return
            self.description = expense.description
            self.category = expense.category
            self.payee = expense.payee or "—"
            self.amount = expense.amount
            self.total_paid = expense.total_paid
            self.outstanding = expense.outstanding_balance

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        title = QLabel("Record Expense Payment")
        title.setStyleSheet(f"color: {NAVY}; font-size: 18px; font-weight: 700;")
        layout.addWidget(title)

        # Info frame
        info_frame = QFrame()
        info_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {CREAM};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        info_layout = QFormLayout(info_frame)
        info_layout.setSpacing(6)
        info_layout.addRow("Expense:", QLabel(f"<b>{self.description}</b>"))
        info_layout.addRow("Category:", QLabel(self.category))
        info_layout.addRow("Payee:", QLabel(self.payee))
        info_layout.addRow("Total Cost:", QLabel(f"₹{self.amount:,.2f}"))
        info_layout.addRow("Already Paid:", QLabel(f"₹{self.total_paid:,.2f}"))

        bal_lbl = QLabel(f"<b>₹{self.outstanding:,.2f}</b>")
        bal_lbl.setStyleSheet("color: #DC2626; font-size: 14px;")
        info_layout.addRow("Outstanding Balance:", bal_lbl)
        layout.addWidget(info_frame)

        # Form
        form = QFormLayout()
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0.01, max(0.01, self.outstanding))
        self.amount_input.setValue(max(0.01, self.outstanding))
        self.amount_input.setPrefix("₹ ")
        self.amount_input.setFixedHeight(36)

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setFixedHeight(36)

        self.method_combo = QComboBox()
        self.method_combo.addItems(EXPENSE_PAYMENT_METHODS)
        self.method_combo.setFixedHeight(36)

        self.ref_input = QLineEdit()
        self.ref_input.setPlaceholderText("Optional receipt / transaction reference")
        self.ref_input.setFixedHeight(36)

        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("Optional notes")
        self.notes_input.setFixedHeight(36)

        form.addRow("Payment Amount *:", self.amount_input)
        form.addRow("Payment Date *:", self.date_input)
        form.addRow("Payment Method *:", self.method_combo)
        form.addRow("Reference No.:", self.ref_input)
        form.addRow("Notes:", self.notes_input)
        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_btn = btns.button(QDialogButtonBox.StandardButton.Save)
        if save_btn:
            save_btn.setText("Save Payment")
            save_btn.setObjectName("primaryDialogButton")
            save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn = btns.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setObjectName("secondaryDialogButton")
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btns.accepted.connect(self.save_payment)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def save_payment(self):
        amount = self.amount_input.value()
        p_date = self.date_input.date().toPyDate()
        method = self.method_combo.currentText()
        ref = self.ref_input.text().strip() or None
        notes = self.notes_input.text().strip() or None

        try:
            with SessionLocal() as session:
                record_expense_payment(
                    session,
                    expense_id=self.expense_id,
                    amount=amount,
                    payment_date=p_date,
                    payment_method=method,
                    reference_number=ref,
                    notes=notes,
                )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Payment Error", str(e))


class ExpensePaymentHistoryDialog(QDialog):
    def __init__(self, expense_id: int, parent=None):
        super().__init__(parent)
        self.expense_id = expense_id
        self.setWindowTitle("Expense Payment History")
        self.resize(650, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        title = QLabel("Payment & Transaction History")
        title.setStyleSheet(f"color: {NAVY}; font-size: 18px; font-weight: 700;")
        subtitle = QLabel("Audit trail of all payments recorded for this expense.")
        subtitle.setStyleSheet(f"color: {MUTED}; font-size: 13px;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Date", "Amount", "Method", "Reference", "Notes", "Status", "Action"
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        configure_table_ux(
            self.table,
            column_widths=[120, 120, 110, 130, 200, 110, 120],
            flexible_columns=[4],
            fixed_columns=[6],
            strategy=TableSizingStrategy.BOUNDED_AND_FLEXIBLE,
        )
        layout.addWidget(self.table, 1)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("primaryDialogButton")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

        self.load_payments()

    def load_payments(self):
        with SessionLocal() as session:
            payments = get_expense_payments(session, expense_id=self.expense_id, include_reversed=True)

        self.table.setRowCount(len(payments))
        for row, p in enumerate(payments):
            date_item = QTableWidgetItem(p.payment_date.strftime("%d %b %Y"))
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, date_item)

            amt_item = QTableWidgetItem(f"₹{p.amount:,.2f}")
            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, amt_item)

            method_item = QTableWidgetItem(p.payment_method)
            method_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, method_item)

            ref_item = QTableWidgetItem(p.reference_number or "-")
            ref_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, ref_item)

            note_text = p.notes or "-"
            if p.is_reversed and p.reversal_reason:
                note_text = f"Reversed: {p.reversal_reason} | {p.notes or ''}"
            notes_item = QTableWidgetItem(note_text)
            notes_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.table.setItem(row, 4, notes_item)

            status_item = QTableWidgetItem("Reversed" if p.is_reversed else "Valid")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if p.is_reversed:
                status_item.setForeground(Qt.GlobalColor.red)
            else:
                status_item.setForeground(Qt.GlobalColor.darkGreen)
            self.table.setItem(row, 5, status_item)

            if not p.is_reversed:
                rev_btn = QPushButton("Reverse")
                rev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                rev_btn.setFixedSize(65, 26)
                rev_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #FEFEFE;
                        color: #DC2626;
                        border: 1px solid #FECACA;
                        border-radius: 4px;
                        font-size: 11px;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background-color: #FEE2E2;
                    }
                """)
                rev_btn.clicked.connect(lambda ch, pid=p.id, amt=p.amount: self.confirm_reversal(pid, amt))
                self.table.setCellWidget(row, 6, rev_btn)
            else:
                lbl = QLabel("—")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setCellWidget(row, 6, lbl)

        auto_fit_columns(self.table)

    def confirm_reversal(self, payment_id: int, amount: float):
        reason_dialog = QDialog(self)
        reason_dialog.setWindowTitle("Reason for Payment Reversal")
        reason_dialog.resize(440, 190)
        r_layout = QVBoxLayout(reason_dialog)
        r_layout.setContentsMargins(18, 16, 18, 16)
        r_layout.setSpacing(12)

        lbl = QLabel(f"Please state the reason for reversing payment of ₹{amount:,.2f}:")
        lbl.setWordWrap(True)
        r_layout.addWidget(lbl)

        reason_input = QLineEdit()
        reason_input.setPlaceholderText("e.g. Duplicate entry / Incorrect account")
        reason_input.setFixedHeight(36)
        r_layout.addWidget(reason_input)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = btns.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setObjectName("primaryDialogButton")
            ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn = btns.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setObjectName("secondaryDialogButton")
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btns.accepted.connect(reason_dialog.accept)
        btns.rejected.connect(reason_dialog.reject)
        r_layout.addWidget(btns)

        if reason_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        reason = reason_input.text().strip()
        if not reason:
            QMessageBox.warning(self, "Reason Required", "Reversal reason cannot be empty.")
            return

        try:
            with SessionLocal() as session:
                reverse_expense_payment(session, payment_id=payment_id, reason=reason)
            QMessageBox.information(
                self,
                "Payment Reversed",
                f"Payment of ₹{amount:,.2f} has been reversed and audit record updated.",
            )
            self.load_payments()
        except Exception as e:
            QMessageBox.critical(self, "Reversal Failed", str(e))


class FinancialAnalysisDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Financial Overview & Cash Flow Analysis")
        self.resize(850, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(16)

        title = QLabel("Financial Analysis & Cash Flow")
        title.setStyleSheet(f"color: {NAVY}; font-size: 20px; font-weight: 700;")
        subtitle = QLabel("Shared comparison of student fee collections, operating expenses, and net cash flow.")
        subtitle.setStyleSheet(f"color: {MUTED}; font-size: 13px;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        with SessionLocal() as session:
            fin_summary = get_financial_summary(session)
            monthly_data = get_monthly_financial_comparison(session, months_count=6)

        # ── KPI Cards ──────────────────────────────────────
        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(12)

        def make_kpi(card_title, value_text, subtitle_text, color=NAVY):
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background: {WHITE};
                    border: 1px solid {LIGHT_GOLD};
                    border-radius: 8px;
                }}
            """)
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(14, 10, 14, 10)
            c_lay.setSpacing(2)
            t = QLabel(card_title)
            t.setStyleSheet(f"color: {MUTED}; font-size: 11px; font-weight: 600;")
            v = QLabel(value_text)
            v.setStyleSheet(f"color: {color}; font-size: 18px; font-weight: 700;")
            s = QLabel(subtitle_text)
            s.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
            c_lay.addWidget(t)
            c_lay.addWidget(v)
            c_lay.addWidget(s)
            return card

        net_flow = fin_summary["net_cash_flow"]
        flow_color = "#16A34A" if net_flow >= 0 else "#DC2626"
        flow_sign = "+" if net_flow >= 0 else ""

        kpi_grid.addWidget(make_kpi("Fees Collected (Cash)", f"₹{fin_summary['fees_collected']:,.2f}", "Total cash collected", "#16A34A"), 0, 0)
        kpi_grid.addWidget(make_kpi("Expenses Paid (Cash)", f"₹{fin_summary['expenses_paid']:,.2f}", "Total cash paid", "#DC2626"), 0, 1)
        kpi_grid.addWidget(make_kpi("Net Cash Flow", f"{flow_sign}₹{net_flow:,.2f}", "Cash In − Cash Out", flow_color), 0, 2)

        kpi_grid.addWidget(make_kpi("Outstanding Fees", f"₹{fin_summary['outstanding_student_fees']:,.2f}", "Uncollected student fees", "#D97706"), 1, 0)
        kpi_grid.addWidget(make_kpi("Outstanding Payables", f"₹{fin_summary['outstanding_expenses']:,.2f}", "Unpaid expense liabilities", "#D97706"), 1, 1)
        kpi_grid.addWidget(make_kpi("Net Accrual Margin", f"₹{fin_summary['net_accrual_income']:,.2f}", "Billed Fees − Incurred Costs", NAVY), 1, 2)

        layout.addLayout(kpi_grid)

        # ── Monthly Trend Table ─────────────────────────────
        trend_title = QLabel("Monthly Financial Comparison (Cash & Accrual)")
        trend_title.setStyleSheet(f"color: {NAVY}; font-size: 15px; font-weight: 700; margin-top: 6px;")
        layout.addWidget(trend_title)

        self.trend_table = QTableWidget()
        trend_table = self.trend_table
        self.trend_table.setColumnCount(6)
        self.trend_table.setHorizontalHeaderLabels([
            "Month", "Fees Collected (Cash)", "Expenses Paid (Cash)", "Net Cash Flow", "Fees Billed", "Costs Incurred"
        ])
        trend_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        trend_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        configure_table_ux(
            trend_table,
            column_widths=[140, 160, 160, 150, 140, 140],
            flexible_columns=[0, 1, 2, 3, 4, 5],
            strategy=TableSizingStrategy.WIDE_SCROLLABLE,
        )

        trend_table.setRowCount(len(monthly_data))
        for r, m in enumerate(monthly_data):
            lbl_item = QTableWidgetItem(m["label"])
            lbl_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            trend_table.setItem(r, 0, lbl_item)

            fc_item = QTableWidgetItem(f"₹{m['fees_collected']:,.2f}")
            fc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            trend_table.setItem(r, 1, fc_item)

            ep_item = QTableWidgetItem(f"₹{m['expenses_paid']:,.2f}")
            ep_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            trend_table.setItem(r, 2, ep_item)

            net_val = m["net_cash_flow"]
            net_item = QTableWidgetItem(f"{'+' if net_val >= 0 else ''}₹{net_val:,.2f}")
            net_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if net_val >= 0:
                net_item.setForeground(Qt.GlobalColor.darkGreen)
            else:
                net_item.setForeground(Qt.GlobalColor.red)
            trend_table.setItem(r, 3, net_item)

            fb_item = QTableWidgetItem(f"₹{m['fees_billed']:,.2f}")
            fb_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            trend_table.setItem(r, 4, fb_item)

            ei_item = QTableWidgetItem(f"₹{m['expenses_incurred']:,.2f}")
            ei_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            trend_table.setItem(r, 5, ei_item)

        auto_fit_columns(trend_table)
        layout.addWidget(trend_table, 1)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("primaryDialogButton")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
