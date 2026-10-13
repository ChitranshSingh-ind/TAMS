from datetime import date
from decimal import Decimal

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from sqlalchemy import select

from app.ui.table_utils import configure_table_ux, TableSizingStrategy, auto_fit_columns

from app.database.connection import SessionLocal
from app.database.models.student import Student
from app.services.batch_service import get_active_batches
from app.services.fee_service import (
    create_fee,
    generate_monthly_fees,
    get_fee,
    get_fee_payments,
    record_payment,
    reverse_payment,
    update_fee,
)

NAVY = "#012D54"
DARK_NAVY = "#04294D"
GOLD = "#D9B85F"
LIGHT_GOLD = "#E9DEBA"
CREAM = "#F8F6EA"
WHITE = "#FEFEFE"
TEXT = "#1F2937"
MUTED = "#615F4B"

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]


class GenerateFeesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generate Monthly Fees")
        self.resize(780, 580)
        self.preview_data = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(16)

        # Header
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        title = QLabel("Monthly Fee Generation")
        title.setStyleSheet(f"color: {NAVY}; font-size: 20px; font-weight: 700;")
        subtitle = QLabel("Generate fee obligations for all active students in the selected month.")
        subtitle.setStyleSheet(f"color: {MUTED}; font-size: 13px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box)

        # Form controls
        controls_frame = QFrame()
        controls_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {WHITE};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 8px;
            }}
        """)
        form = QFormLayout(controls_frame)
        form.setContentsMargins(16, 14, 16, 14)
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # Academic Year
        self.year_combo = QComboBox()
        self.year_combo.setFixedHeight(36)
        curr_year = date.today().year
        self.year_combo.addItems([
            f"{curr_year-1}-{curr_year}",
            f"{curr_year}-{curr_year+1}",
            f"{curr_year+1}-{curr_year+2}",
        ])
        self.year_combo.setCurrentIndex(1)

        # Month
        self.month_combo = QComboBox()
        self.month_combo.setFixedHeight(36)
        for i, m in enumerate(MONTH_NAMES, start=1):
            self.month_combo.addItem(m, i)
        self.month_combo.setCurrentIndex(date.today().month - 1)

        # Batch
        self.batch_combo = QComboBox()
        self.batch_combo.setFixedHeight(36)
        self.batch_combo.addItem("All Batches", None)
        with SessionLocal() as session:
            batches = get_active_batches(session)
            for b in batches:
                self.batch_combo.addItem(b.name, b.id)

        # Default fee amount
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setFixedHeight(36)
        self.amount_spin.setRange(0, 1000000)
        self.amount_spin.setSingleStep(100)
        self.amount_spin.setValue(2000.0)
        self.amount_spin.setPrefix("₹ ")

        # Due Date
        self.due_date_edit = QDateEdit()
        self.due_date_edit.setFixedHeight(36)
        self.due_date_edit.setCalendarPopup(True)
        today = date.today()
        # Default to 10th of selected month
        default_due = QDate(today.year, today.month, min(10, 28))
        self.due_date_edit.setDate(default_due)

        form.addRow("Academic Year:", self.year_combo)
        form.addRow("Fee Month:", self.month_combo)
        form.addRow("Target Batch:", self.batch_combo)
        form.addRow("Default Amount:", self.amount_spin)
        form.addRow("Due Date:", self.due_date_edit)

        layout.addWidget(controls_frame)

        # Preview toolbar & Summary
        preview_bar = QHBoxLayout()
        preview_bar.setSpacing(10)

        preview_btn = QPushButton("🔍 Preview Eligible Students")
        preview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        preview_btn.setFixedHeight(34)
        preview_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {LIGHT_GOLD};
                color: {NAVY};
                border: 1px solid {GOLD};
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {GOLD};
            }}
        """)
        preview_btn.clicked.connect(self.run_preview)
        preview_bar.addWidget(preview_btn)

        self.summary_badge = QLabel("Click 'Preview' to check eligible students.")
        self.summary_badge.setStyleSheet(f"color: {MUTED}; font-size: 12px; font-weight: 500;")
        preview_bar.addWidget(self.summary_badge)
        preview_bar.addStretch()

        layout.addLayout(preview_bar)

        # Preview table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Admission No.", "Student Name", "Batch", "Fee Amount", "Status"
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        configure_table_ux(
            self.table,
            column_widths=[140, 200, 140, 130, 120],
            flexible_columns=[1, 2],
            strategy=TableSizingStrategy.BOUNDED_AND_FLEXIBLE,
        )
        layout.addWidget(self.table, 1)

        # Dialog buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)
        btn_box.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryDialogButton")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setFixedHeight(38)
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        self.generate_btn = QPushButton("Confirm & Generate Fees")
        self.generate_btn.setObjectName("primaryDialogButton")
        self.generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generate_btn.setFixedHeight(38)
        self.generate_btn.setEnabled(False)
        self.generate_btn.clicked.connect(self.confirm_generation)
        btn_box.addWidget(self.generate_btn)

        layout.addLayout(btn_box)

        # Automatically run preview on first show
        self.run_preview()

    def run_preview(self):
        academic_year = self.year_combo.currentText()
        fee_month = self.month_combo.currentData()
        batch_id = self.batch_combo.currentData()
        default_amt = self.amount_spin.value()
        due_date = self.due_date_edit.date().toPyDate()

        with SessionLocal() as session:
            preview = generate_monthly_fees(
                session,
                academic_year=academic_year,
                fee_month=fee_month,
                batch_id=batch_id,
                default_amount=default_amt,
                due_date=due_date,
                preview_only=True,
            )

        self.preview_data = preview
        items = preview["preview_items"]
        self.table.setRowCount(len(items))

        for row, item in enumerate(items):
            adm_item = QTableWidgetItem(item["admission_number"] or "-")
            adm_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, adm_item)

            name_item = QTableWidgetItem(item["student_name"])
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.table.setItem(row, 1, name_item)

            batch_item = QTableWidgetItem(item["batch_name"])
            batch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, batch_item)

            amt_item = QTableWidgetItem(f"₹{item['amount']:,.2f}")
            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, amt_item)

            status_str = "Ready to generate" if item["status"] == "READY" else "Already generated"
            status_item = QTableWidgetItem(status_str)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if item["status"] == "READY":
                status_item.setForeground(Qt.GlobalColor.darkGreen)
            else:
                status_item.setForeground(Qt.GlobalColor.gray)
            self.table.setItem(row, 4, status_item)

        to_gen = preview["to_generate_count"]
        already = preview["already_generated_count"]
        total_amt = preview["total_amount_to_generate"]

        self.summary_badge.setText(
            f"Eligible: {preview['eligible_count']}  |  "
            f"To Generate: {to_gen} (₹{total_amt:,.2f})  |  "
            f"Already Exists: {already}"
        )
        self.generate_btn.setEnabled(to_gen > 0)
        auto_fit_columns(self.table)

    def confirm_generation(self):
        academic_year = self.year_combo.currentText()
        fee_month = self.month_combo.currentData()
        batch_id = self.batch_combo.currentData()
        default_amt = self.amount_spin.value()
        due_date = self.due_date_edit.date().toPyDate()
        to_gen = self.preview_data["to_generate_count"] if self.preview_data else 0

        confirm = QMessageBox.question(
            self,
            "Confirm Fee Generation",
            f"Are you sure you want to generate fee obligations for {to_gen} students for "
            f"{MONTH_NAMES[fee_month-1]} {academic_year}?\n\nThis will record new obligations in the system.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        with SessionLocal() as session:
            result = generate_monthly_fees(
                session,
                academic_year=academic_year,
                fee_month=fee_month,
                batch_id=batch_id,
                default_amount=default_amt,
                due_date=due_date,
                preview_only=False,
            )

        QMessageBox.information(
            self,
            "Fees Generated",
            f"Successfully generated {result['generated_count']} fee obligation(s) "
            f"totalling ₹{result['total_amount_generated']:,.2f}.",
        )
        self.accept()


class RecordPaymentDialog(QDialog):
    def __init__(self, fee_id: int, parent=None):
        super().__init__(parent)
        self.fee_id = fee_id
        self.setWindowTitle("Record Payment")
        self.resize(520, 500)

        with SessionLocal() as session:
            fee = get_fee(session, fee_id)
            if not fee:
                QMessageBox.critical(self, "Error", "Fee record not found.")
                self.reject()
                return

            self.student_name = f"{fee.student.first_name} {fee.student.last_name or ''}".strip()
            self.admission_no = fee.student.admission_number or "-"
            self.batch_name = fee.batch.name if fee.batch else "-"
            self.period_name = f"{MONTH_NAMES[fee.fee_month - 1]} {fee.academic_year}"
            self.final_due = fee.final_amount_due
            self.total_paid = fee.total_paid
            self.outstanding = fee.outstanding_balance

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(16)

        # Header
        title = QLabel("Record Payment")
        title.setStyleSheet(f"color: {NAVY}; font-size: 20px; font-weight: 700;")
        layout.addWidget(title)

        # Info card
        info_frame = QFrame()
        info_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {CREAM};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        info_layout = QFormLayout(info_frame)
        info_layout.setSpacing(6)
        info_layout.addRow("Student:", QLabel(f"<b>{self.student_name}</b> ({self.admission_no})"))
        info_layout.addRow("Batch:", QLabel(self.batch_name))
        info_layout.addRow("Fee Period:", QLabel(self.period_name))
        info_layout.addRow("Total Due:", QLabel(f"₹{self.final_due:,.2f}"))
        info_layout.addRow("Already Paid:", QLabel(f"₹{self.total_paid:,.2f}"))

        outstanding_label = QLabel(f"<b>₹{self.outstanding:,.2f}</b>")
        outstanding_label.setStyleSheet("color: #DC2626; font-size: 15px;")
        info_layout.addRow("Outstanding Balance:", outstanding_label)

        layout.addWidget(info_frame)

        # Payment Form
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
        self.method_combo.addItems(["Cash", "UPI", "Bank Transfer", "Card", "Other"])
        self.method_combo.setFixedHeight(36)

        self.receipt_input = QLineEdit()
        self.receipt_input.setPlaceholderText("Optional (auto-generated if empty)")
        self.receipt_input.setFixedHeight(36)

        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("Optional payment notes")
        self.notes_input.setFixedHeight(36)

        form.addRow("Payment Amount *:", self.amount_input)
        form.addRow("Payment Date *:", self.date_input)
        form.addRow("Payment Method *:", self.method_combo)
        form.addRow("Receipt / Ref No.:", self.receipt_input)
        form.addRow("Notes:", self.notes_input)

        layout.addLayout(form)

        # Buttons
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
        payment_date = self.date_input.date().toPyDate()
        method = self.method_combo.currentText()
        receipt = self.receipt_input.text().strip() or None
        notes = self.notes_input.text().strip() or None

        if amount <= 0:
            QMessageBox.warning(self, "Invalid Amount", "Payment amount must be greater than zero.")
            return

        if Decimal(str(amount)) > Decimal(str(self.outstanding)):
            QMessageBox.warning(
                self,
                "Overpayment Disallowed",
                f"Amount (₹{amount:,.2f}) cannot exceed outstanding balance (₹{self.outstanding:,.2f}).",
            )
            return

        try:
            with SessionLocal() as session:
                pmt = record_payment(
                    session,
                    fee_id=self.fee_id,
                    amount=amount,
                    payment_date=payment_date,
                    payment_method=method,
                    receipt_number=receipt,
                    notes=notes,
                )
                receipt_used = pmt.receipt_number

            QMessageBox.information(
                self,
                "Payment Recorded",
                f"Payment of ₹{amount:,.2f} recorded successfully.\nReceipt No: {receipt_used}",
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Payment Error", str(e))


class PaymentHistoryDialog(QDialog):
    def __init__(self, fee_id: int, parent=None):
        super().__init__(parent)
        self.fee_id = fee_id
        self.setWindowTitle("Payment History")
        self.resize(760, 480)

        with SessionLocal() as session:
            fee = get_fee(session, fee_id)
            if not fee:
                QMessageBox.critical(self, "Error", "Fee record not found.")
                self.reject()
                return

            self.student_name = f"{fee.student.first_name} {fee.student.last_name or ''}".strip()
            self.period_name = f"{MONTH_NAMES[fee.fee_month - 1]} {fee.academic_year}"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel(f"Payment History — {self.student_name}")
        title.setStyleSheet(f"color: {NAVY}; font-size: 18px; font-weight: 700;")
        subtitle = QLabel(f"Fee Period: {self.period_name}")
        subtitle.setStyleSheet(f"color: {MUTED}; font-size: 13px;")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Date", "Receipt No.", "Amount", "Method", "Notes", "Status", "Action"
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        configure_table_ux(
            self.table,
            column_widths=[120, 150, 120, 110, 200, 110, 120],
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
            payments = get_fee_payments(session, fee_id=self.fee_id, include_reversed=True)

        self.table.setRowCount(len(payments))
        for row, p in enumerate(payments):
            date_item = QTableWidgetItem(p.payment_date.strftime("%d %b %Y"))
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, date_item)

            receipt_item = QTableWidgetItem(p.receipt_number or "-")
            receipt_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, receipt_item)

            amt_item = QTableWidgetItem(f"₹{p.amount:,.2f}")
            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, amt_item)

            method_item = QTableWidgetItem(p.payment_method)
            method_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, method_item)

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
        reason_dialog.setWindowTitle("Reason for Reversal")
        reason_dialog.resize(440, 190)
        r_layout = QVBoxLayout(reason_dialog)
        r_layout.setContentsMargins(18, 16, 18, 16)
        r_layout.setSpacing(12)

        lbl = QLabel(f"Please state the reason for reversing payment of ₹{amount:,.2f}:")
        lbl.setWordWrap(True)
        r_layout.addWidget(lbl)

        reason_input = QLineEdit()
        reason_input.setPlaceholderText("e.g. Bank bounced / Entered in error")
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
                reverse_payment(session, payment_id=payment_id, reason=reason)

            QMessageBox.information(
                self,
                "Payment Reversed",
                f"Payment of ₹{amount:,.2f} has been reversed and audit record updated.",
            )
            self.load_payments()
        except Exception as e:
            QMessageBox.critical(self, "Reversal Failed", str(e))


class EditFeeDialog(QDialog):
    def __init__(self, fee_id: int, parent=None):
        super().__init__(parent)
        self.fee_id = fee_id
        self.setWindowTitle("Edit Fee Obligation")
        self.resize(480, 420)

        with SessionLocal() as session:
            fee = get_fee(session, fee_id)
            if not fee:
                QMessageBox.critical(self, "Error", "Fee record not found.")
                self.reject()
                return

            self.student_name = f"{fee.student.first_name} {fee.student.last_name or ''}".strip()
            self.period_name = f"{MONTH_NAMES[fee.fee_month - 1]} {fee.academic_year}"
            self.current_amt = fee.amount_due
            self.current_discount = fee.discount
            self.total_paid = fee.total_paid
            self.due_date = fee.due_date
            self.notes = fee.notes or ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(16)

        title = QLabel(f"Edit Fee — {self.student_name}")
        title.setStyleSheet(f"color: {NAVY}; font-size: 18px; font-weight: 700;")
        subtitle = QLabel(f"Period: {self.period_name}  |  Already Paid: ₹{self.total_paid:,.2f}")
        subtitle.setStyleSheet(f"color: {MUTED}; font-size: 13px;")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        form = QFormLayout()
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.amt_spin = QDoubleSpinBox()
        self.amt_spin.setRange(0, 1000000)
        self.amt_spin.setValue(self.current_amt)
        self.amt_spin.setPrefix("₹ ")
        self.amt_spin.setFixedHeight(36)

        self.disc_spin = QDoubleSpinBox()
        self.disc_spin.setRange(0, 1000000)
        self.disc_spin.setValue(self.current_discount)
        self.disc_spin.setPrefix("₹ ")
        self.disc_spin.setFixedHeight(36)

        self.net_label = QLabel("₹0.00")
        self.net_label.setStyleSheet(f"color: {NAVY}; font-size: 14px; font-weight: 700;")

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

        form.addRow("Base Fee:", self.amt_spin)
        form.addRow("Discount / Waiver:", self.disc_spin)
        form.addRow("Final Due:", self.net_label)
        form.addRow("Due Date:", self.due_date_edit)
        form.addRow("Notes:", self.notes_input)

        layout.addLayout(form)

        self.amt_spin.valueChanged.connect(self.update_net)
        self.disc_spin.valueChanged.connect(self.update_net)
        self.update_net()

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_btn = btns.button(QDialogButtonBox.StandardButton.Save)
        if save_btn:
            save_btn.setObjectName("primaryDialogButton")
            save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn = btns.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setObjectName("secondaryDialogButton")
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btns.accepted.connect(self.save_edit)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def update_net(self):
        base = self.amt_spin.value()
        disc = self.disc_spin.value()
        net = max(0.0, base - disc)
        self.net_label.setText(f"₹{net:,.2f}")

    def save_edit(self):
        base = self.amt_spin.value()
        disc = self.disc_spin.value()
        net = max(0.0, base - disc)

        if net < self.total_paid:
            QMessageBox.warning(
                self,
                "Invalid Amount",
                f"Final fee (₹{net:,.2f}) cannot be less than already collected amount (₹{self.total_paid:,.2f}).",
            )
            return

        try:
            with SessionLocal() as session:
                update_fee(
                    session,
                    fee_id=self.fee_id,
                    amount_due=base,
                    discount=disc,
                    due_date=self.due_date_edit.date().toPyDate(),
                    notes=self.notes_input.text().strip() or None,
                )
            QMessageBox.information(self, "Fee Updated", "Fee obligation updated successfully.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Update Error", str(e))


class CreateFeeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Fee Obligation")
        self.resize(500, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(16)

        title = QLabel("Create Single Fee Obligation")
        title.setStyleSheet(f"color: {NAVY}; font-size: 18px; font-weight: 700;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.student_combo = QComboBox()
        self.student_combo.setFixedHeight(36)
        with SessionLocal() as session:
            students = session.scalars(
                select(Student).order_by(Student.first_name, Student.last_name)
            ).all()
            for s in students:
                name = f"{s.first_name} {s.last_name or ''}".strip()
                adm = s.admission_number or ""
                self.student_combo.addItem(f"{name} ({adm})", (s.id, s.batch_id))

        curr_year = date.today().year
        self.year_combo = QComboBox()
        self.year_combo.addItems([
            f"{curr_year-1}-{curr_year}",
            f"{curr_year}-{curr_year+1}",
            f"{curr_year+1}-{curr_year+2}",
        ])
        self.year_combo.setCurrentIndex(1)
        self.year_combo.setFixedHeight(36)

        self.month_combo = QComboBox()
        for i, m in enumerate(MONTH_NAMES, start=1):
            self.month_combo.addItem(m, i)
        self.month_combo.setCurrentIndex(date.today().month - 1)
        self.month_combo.setFixedHeight(36)

        self.amt_spin = QDoubleSpinBox()
        self.amt_spin.setRange(0, 1000000)
        self.amt_spin.setValue(2000.0)
        self.amt_spin.setPrefix("₹ ")
        self.amt_spin.setFixedHeight(36)

        self.disc_spin = QDoubleSpinBox()
        self.disc_spin.setRange(0, 1000000)
        self.disc_spin.setValue(0.0)
        self.disc_spin.setPrefix("₹ ")
        self.disc_spin.setFixedHeight(36)

        self.due_date_edit = QDateEdit()
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDate(QDate.currentDate())
        self.due_date_edit.setFixedHeight(36)

        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("Optional notes")
        self.notes_input.setFixedHeight(36)

        form.addRow("Student *:", self.student_combo)
        form.addRow("Academic Year *:", self.year_combo)
        form.addRow("Fee Month *:", self.month_combo)
        form.addRow("Amount Due *:", self.amt_spin)
        form.addRow("Discount / Waiver:", self.disc_spin)
        form.addRow("Due Date:", self.due_date_edit)
        form.addRow("Notes:", self.notes_input)

        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_btn = btns.button(QDialogButtonBox.StandardButton.Save)
        if save_btn:
            save_btn.setObjectName("primaryDialogButton")
            save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn = btns.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setObjectName("secondaryDialogButton")
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btns.accepted.connect(self.save_fee)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def save_fee(self):
        student_data = self.student_combo.currentData()
        if not student_data:
            QMessageBox.warning(self, "Required", "Please select a student.")
            return

        student_id, batch_id = student_data
        year = self.year_combo.currentText()
        month = self.month_combo.currentData()
        amt = self.amt_spin.value()
        disc = self.disc_spin.value()
        due_date = self.due_date_edit.date().toPyDate()
        notes = self.notes_input.text().strip() or None

        try:
            with SessionLocal() as session:
                create_fee(
                    session,
                    student_id=student_id,
                    batch_id=batch_id,
                    academic_year=year,
                    fee_month=month,
                    amount_due=amt,
                    discount=disc,
                    due_date=due_date,
                    notes=notes,
                )
            QMessageBox.information(self, "Success", "Fee obligation created successfully.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Creation Failed", str(e))
