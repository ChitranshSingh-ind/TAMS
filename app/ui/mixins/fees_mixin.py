"""
TAMS Fees Page Controller Mixin.

Handles monthly fee generation, payment collection (full and partial),
payment history inspection, receipt issuance, and CSV export.
"""

import csv
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
from app.services.batch_service import get_active_batches
from app.services.fee_service import get_fees, get_fees_summary
from app.ui.fee_dialogs import (
    CreateFeeDialog,
    EditFeeDialog,
    GenerateFeesDialog,
    MONTH_NAMES,
    PaymentHistoryDialog,
    RecordPaymentDialog,
)
from app.ui.table_utils import (
    TableSizingStrategy,
    auto_fit_columns,
    configure_table_ux,
)


class FeesMixin:
    """
    Mixin providing Fees management UI: summary KPIs, student fee records table,
    search & status filters, and modal payment dialogues.
    """

    def create_fees_page(self) -> QWidget:
        """Constructs the complete Fees management page and associated toolbars."""
        page = QWidget()
        page.setObjectName("feesPage")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 28)
        layout.setSpacing(18)

        # ── Header ─────────────────────────────────────────
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        title = QLabel("Fees")
        title.setObjectName("feesPageTitle")
        subtitle = QLabel("Track student fees, record payments, and manage monthly obligations.")
        subtitle.setObjectName("feesPageSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        # Action Buttons
        generate_btn = QPushButton("＋ Generate Monthly Fees")
        generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        generate_btn.setFixedHeight(40)
        generate_btn.setStyleSheet("""
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
        generate_btn.clicked.connect(self.open_generate_fees_dialog)
        header_layout.addWidget(generate_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        add_fee_btn = QPushButton("＋ Add Fee")
        add_fee_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_fee_btn.setFixedHeight(40)
        add_fee_btn.setStyleSheet("""
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
        add_fee_btn.clicked.connect(self.open_create_fee_dialog)
        header_layout.addWidget(add_fee_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

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
        export_btn.clicked.connect(self.export_fees_csv)
        header_layout.addWidget(export_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        layout.addLayout(header_layout)

        # ── KPI Cards ──────────────────────────────────────
        kpi_layout = QGridLayout()
        kpi_layout.setHorizontalSpacing(15)
        kpi_layout.setVerticalSpacing(10)

        def make_fee_kpi_card(card_title, default_val, text_color="#012D54"):
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

        card1, self.fees_kpi_total_due = make_fee_kpi_card("Total Fees Due", "₹0.00", "#012D54")
        card2, self.fees_kpi_collected = make_fee_kpi_card("Total Collected", "₹0.00", "#16A34A")
        card3, self.fees_kpi_outstanding = make_fee_kpi_card("Total Outstanding", "₹0.00", "#D97706")
        card4, self.fees_kpi_overdue = make_fee_kpi_card("Total Overdue", "₹0.00", "#DC2626")

        kpi_layout.addWidget(card1, 0, 0)
        kpi_layout.addWidget(card2, 0, 1)
        kpi_layout.addWidget(card3, 0, 2)
        kpi_layout.addWidget(card4, 0, 3)

        layout.addLayout(kpi_layout)

        # ── Filters & Search Toolbar ───────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.fee_search_input = QLineEdit()
        self.fee_search_input.setPlaceholderText("Search by student name or admission no...")
        self.fee_search_input.setClearButtonEnabled(True)
        self.fee_search_input.setFixedHeight(36)
        self.fee_search_input.setStyleSheet("""
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
        self.fee_search_input.textChanged.connect(self.load_fees)
        toolbar.addWidget(self.fee_search_input, 2)

        # Batch filter
        self.fee_batch_filter = QComboBox()
        self.fee_batch_filter.setFixedHeight(36)
        self.fee_batch_filter.addItem("All Batches", None)
        with SessionLocal() as session:
            batches = get_active_batches(session)
            for b in batches:
                self.fee_batch_filter.addItem(b.name, b.id)
        self.fee_batch_filter.currentIndexChanged.connect(self.load_fees)
        toolbar.addWidget(self.fee_batch_filter, 1)

        # Month filter
        self.fee_month_filter = QComboBox()
        self.fee_month_filter.setFixedHeight(36)
        self.fee_month_filter.addItem("All Months", None)
        for i, m in enumerate(MONTH_NAMES, start=1):
            self.fee_month_filter.addItem(m, i)
        self.fee_month_filter.currentIndexChanged.connect(self.load_fees)
        toolbar.addWidget(self.fee_month_filter, 1)

        # Status filter
        self.fee_status_filter = QComboBox()
        self.fee_status_filter.setFixedHeight(36)
        self.fee_status_filter.addItem("All Statuses", "ALL")
        self.fee_status_filter.addItem("Unpaid / Pending", "PENDING")
        self.fee_status_filter.addItem("Partially Paid", "PARTIALLY_PAID")
        self.fee_status_filter.addItem("Paid", "PAID")
        self.fee_status_filter.addItem("Overdue", "OVERDUE")
        self.fee_status_filter.currentIndexChanged.connect(self.load_fees)
        toolbar.addWidget(self.fee_status_filter, 1)

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
        reset_btn.clicked.connect(self.reset_fee_filters)
        toolbar.addWidget(reset_btn)

        layout.addLayout(toolbar)

        # ── Fees Table ─────────────────────────────────────
        self.fees_table = QTableWidget()
        self.fees_table.setObjectName("feesTable")
        self.fees_table.setColumnCount(10)
        self.fees_table.setHorizontalHeaderLabels([
            "Admission No.",
            "Student Name",
            "Batch",
            "Fee Period",
            "Total Fee",
            "Paid",
            "Outstanding",
            "Due Date",
            "Status",
            "Actions",
        ])
        self.fees_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.fees_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.fees_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        configure_table_ux(
            self.fees_table,
            column_widths=[130, 180, 140, 120, 110, 110, 110, 110, 110, 180],
            stretch_column=1,
            flexible_columns=[1, 2],
            fixed_columns=[9],
            strategy=TableSizingStrategy.WIDE_SCROLLABLE,
        )

        layout.addWidget(self.fees_table, 1)

        # Empty state label
        self.fees_empty_label = QLabel(
            "No fee obligations match the current filters. Click '＋ Generate Monthly Fees' above to generate fees."
        )
        self.fees_empty_label.setStyleSheet("""
            QLabel {
                color: #615F4B;
                font-size: 13px;
                padding: 14px;
                background: #F8F6EA;
                border: 1px dashed #D9B85F;
                border-radius: 8px;
            }
        """)
        self.fees_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fees_empty_label.setVisible(False)
        layout.addWidget(self.fees_empty_label)

        return page

    def load_fees(self):
        if not hasattr(self, "fees_table"):
            return

        search = self.fee_search_input.text().strip() or None
        batch_id = self.fee_batch_filter.currentData()
        month = self.fee_month_filter.currentData()
        status = self.fee_status_filter.currentData()
        overdue_only = (status == "OVERDUE")

        with SessionLocal() as session:
            fees = get_fees(
                session,
                batch_id=batch_id,
                fee_month=month,
                status=status,
                search=search,
                overdue_only=overdue_only,
            )
            summary = get_fees_summary(
                session,
                batch_id=batch_id,
                fee_month=month,
                search=search,
            )

        # Update KPI Cards
        self.fees_kpi_total_due.setText(f"₹{summary['total_due']:,.2f}")
        self.fees_kpi_collected.setText(f"₹{summary['total_collected']:,.2f}")
        self.fees_kpi_outstanding.setText(f"₹{summary['total_outstanding']:,.2f}")
        self.fees_kpi_overdue.setText(f"₹{summary['total_overdue']:,.2f}")

        # Update table rows
        self.fees_table.setRowCount(len(fees))
        for row, fee in enumerate(fees):
            student_name = f"{fee.student.first_name} {fee.student.last_name or ''}".strip() if fee.student else "Unknown"
            adm_no = fee.student.admission_number if fee.student else "-"
            batch_name = fee.batch.name if fee.batch else "-"
            month_name = MONTH_NAMES[fee.fee_month - 1] if (1 <= fee.fee_month <= 12) else f"M{fee.fee_month}"
            period_str = f"{month_name} {fee.academic_year}"

            adm_item = QTableWidgetItem(adm_no)
            adm_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.fees_table.setItem(row, 0, adm_item)

            name_item = QTableWidgetItem(student_name)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.fees_table.setItem(row, 1, name_item)

            batch_item = QTableWidgetItem(batch_name)
            batch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.fees_table.setItem(row, 2, batch_item)

            period_item = QTableWidgetItem(period_str)
            period_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.fees_table.setItem(row, 3, period_item)

            due_item = QTableWidgetItem(f"₹{fee.final_amount_due:,.2f}")
            due_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.fees_table.setItem(row, 4, due_item)

            paid_item = QTableWidgetItem(f"₹{fee.total_paid:,.2f}")
            paid_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.fees_table.setItem(row, 5, paid_item)

            bal_val = fee.outstanding_balance
            bal_item = QTableWidgetItem(f"₹{bal_val:,.2f}")
            bal_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if bal_val > 0:
                bal_item.setForeground(Qt.GlobalColor.darkRed)
            self.fees_table.setItem(row, 6, bal_item)

            due_date_str = fee.due_date.strftime("%d %b %Y") if fee.due_date else "—"
            date_item = QTableWidgetItem(due_date_str)
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.fees_table.setItem(row, 7, date_item)

            # Status Badge Widget
            status_calc = fee.calculate_status()
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
            else:
                status_badge.setText("Unpaid")
                status_badge.setStyleSheet("background-color: #DBEAFE; color: #1D4ED8; font-size: 11px; font-weight: 700; padding: 4px 8px; border-radius: 4px;")

            status_layout.addWidget(status_badge)
            self.fees_table.setCellWidget(row, 8, status_widget)

            # Action Buttons Widget
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 2, 4, 2)
            action_layout.setSpacing(6)
            action_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            pay_btn = QPushButton("Pay")
            pay_btn.setFixedSize(52, 28)
            pay_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            pay_btn.setEnabled(bal_val > 0)
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
            pay_btn.clicked.connect(lambda ch, fid=fee.id: self.open_record_payment_dialog(fid))
            action_layout.addWidget(pay_btn)

            hist_btn = QPushButton("History")
            hist_btn.setFixedSize(60, 28)
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
            hist_btn.clicked.connect(lambda ch, fid=fee.id: self.open_payment_history_dialog(fid))
            action_layout.addWidget(hist_btn)

            edit_btn = QPushButton("Edit")
            edit_btn.setFixedSize(48, 28)
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
            edit_btn.clicked.connect(lambda ch, fid=fee.id: self.open_edit_fee_dialog(fid))
            action_layout.addWidget(edit_btn)

            self.fees_table.setCellWidget(row, 9, action_widget)

        self.fees_empty_label.setVisible(len(fees) == 0)
        auto_fit_columns(self.fees_table)

    def export_fees_csv(self):
        default_filename = f"fees_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Fees to CSV",
            default_filename,
            "CSV Files (*.csv)",
        )
        if not filepath:
            return

        search = self.fee_search_input.text().strip() or None
        batch_id = self.fee_batch_filter.currentData()
        month = self.fee_month_filter.currentData()
        status = self.fee_status_filter.currentData()
        overdue_only = (status == "OVERDUE")

        with SessionLocal() as session:
            fees = get_fees(
                session,
                batch_id=batch_id,
                fee_month=month,
                status=status,
                search=search,
                overdue_only=overdue_only,
            )

            try:
                with open(filepath, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "Admission No.",
                        "Student Name",
                        "Batch",
                        "Academic Year",
                        "Fee Month",
                        "Base Amount (INR)",
                        "Discount (INR)",
                        "Final Amount Due (INR)",
                        "Total Paid (INR)",
                        "Outstanding (INR)",
                        "Due Date",
                        "Status",
                        "Notes",
                    ])
                    for fee in fees:
                        student_name = f"{fee.student.first_name} {fee.student.last_name or ''}".strip() if fee.student else ""
                        month_name = MONTH_NAMES[fee.fee_month - 1] if (1 <= fee.fee_month <= 12) else str(fee.fee_month)
                        writer.writerow([
                            fee.student.admission_number if fee.student else "",
                            student_name,
                            fee.batch.name if fee.batch else "",
                            fee.academic_year,
                            month_name,
                            f"{fee.amount_due:.2f}",
                            f"{fee.discount:.2f}",
                            f"{fee.final_amount_due:.2f}",
                            f"{fee.total_paid:.2f}",
                            f"{fee.outstanding_balance:.2f}",
                            fee.due_date.strftime("%Y-%m-%d") if fee.due_date else "",
                            fee.calculate_status(),
                            fee.notes or "",
                        ])

                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Successfully exported {len(fees)} fee record(s) to:\n{filepath}",
                )
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Failed to export CSV: {e}")

    def reset_fee_filters(self):
        self.fee_search_input.blockSignals(True)
        self.fee_batch_filter.blockSignals(True)
        self.fee_month_filter.blockSignals(True)
        self.fee_status_filter.blockSignals(True)

        self.fee_search_input.clear()
        self.fee_batch_filter.setCurrentIndex(0)
        self.fee_month_filter.setCurrentIndex(0)
        self.fee_status_filter.setCurrentIndex(0)

        self.fee_search_input.blockSignals(False)
        self.fee_batch_filter.blockSignals(False)
        self.fee_month_filter.blockSignals(False)
        self.fee_status_filter.blockSignals(False)

        self.load_fees()

    def open_generate_fees_dialog(self):
        dialog = GenerateFeesDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_fees()
            self.refresh_dashboard()

    def open_create_fee_dialog(self):
        dialog = CreateFeeDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_fees()
            self.refresh_dashboard()

    def open_record_payment_dialog(self, fee_id: int):
        dialog = RecordPaymentDialog(fee_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_fees()
            self.refresh_dashboard()

    def open_payment_history_dialog(self, fee_id: int):
        dialog = PaymentHistoryDialog(fee_id, self)
        dialog.exec()
        self.load_fees()
        self.refresh_dashboard()

    def open_edit_fee_dialog(self, fee_id: int):
        dialog = EditFeeDialog(fee_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_fees()
            self.refresh_dashboard()

    # ═════════════════════════════════════════════════════════════════════════
    # ── EXPENSES MODULE ──────────────────────────────────────────────────────
    # ═════════════════════════════════════════════════════════════════════════

