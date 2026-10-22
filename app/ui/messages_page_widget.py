"""
Complete Messages Workspace UI for TAMS Coaching Intelligence & Operations.
Implements Overview KPI Dashboard, Compose Message with live deduplication & preview,
Message History with advanced filters and CSV export, Queue & Retry management,
and integrated Messaging Settings & Automation Rules.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sqlalchemy import select

from app.database.connection import SessionLocal
from app.database.models.batch import Batch
from app.database.models.message import Message, MessageTemplate
from app.database.models.student import Student
from app.services.messaging_service import (
    cancel_pending_message,
    clear_completed_messages,
    export_message_history_csv,
    get_eligible_recipients,
    get_message_history_records,
    get_messaging_overview_stats,
    queue_bulk_messages,
    render_template_text,
    retry_failed_message,
)
from app.ui.chart_widgets import SegmentedDistributionWidget
from app.ui.messaging_settings_widget import MessagingSettingsWidget
from app.ui.table_utils import (
    configure_table_ux,
    TableSizingStrategy,
    auto_fit_columns,
)

# TAMS Palette
NAVY = "#012D54"
DARK_NAVY = "#04294D"
GOLD = "#D9B85F"
LIGHT_GOLD = "#E9DEBA"
CREAM = "#F8F6EA"
WHITE = "#FEFEFE"
TEXT = "#1F2937"
MUTED = "#615F4B"


# ─────────────────────────────────────────────────────────────────────────────
# 1. MESSAGE DETAILS DIALOG
# ─────────────────────────────────────────────────────────────────────────────

class MessageDetailsDialog(QDialog):
    """Inspects complete message record with full text, timestamps, provider IDs and delivery status."""

    def __init__(self, message_id: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.message_id = message_id
        self.setWindowTitle(f"Message Details — #{message_id}")
        self.resize(550, 520)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        with SessionLocal() as session:
            msg = session.get(Message, self.message_id)
            if not msg:
                layout.addWidget(QLabel("Message record not found."))
                return

            header = QLabel(f"Message #{msg.id} Details")
            header.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {NAVY};")
            layout.addWidget(header)

            form = QFormLayout()
            form.setSpacing(10)

            form.addRow("Status:", QLabel(f"<b>{msg.status}</b>"))
            form.addRow("Environment:", QLabel(msg.environment))
            form.addRow("Recipient Name:", QLabel(msg.recipient_name))
            form.addRow("Phone Number:", QLabel(msg.recipient_phone))
            form.addRow("Template:", QLabel(msg.template_name or "Free-form text"))
            form.addRow("Trigger Type:", QLabel(msg.trigger_type))
            form.addRow("Category:", QLabel(msg.category))
            form.addRow("Provider Message ID:", QLabel(msg.provider_message_id or "—"))
            form.addRow("Retry Count:", QLabel(f"{msg.retry_count} / {msg.max_retries}"))

            q_time = msg.queued_at.strftime("%Y-%m-%d %H:%M:%S UTC") if msg.queued_at else "—"
            s_time = msg.sent_at.strftime("%Y-%m-%d %H:%M:%S UTC") if msg.sent_at else "—"
            d_time = msg.delivered_at.strftime("%Y-%m-%d %H:%M:%S UTC") if msg.delivered_at else "—"
            r_time = msg.read_at.strftime("%Y-%m-%d %H:%M:%S UTC") if msg.read_at else "—"

            form.addRow("Queued At:", QLabel(q_time))
            form.addRow("Accepted At:", QLabel(s_time))
            form.addRow("Delivered At:", QLabel(d_time))
            form.addRow("Read At:", QLabel(r_time))

            if msg.error_message:
                err_lbl = QLabel(msg.error_message)
                err_lbl.setWordWrap(True)
                err_lbl.setStyleSheet("color: #DC2626; font-weight: 600;")
                form.addRow("Error Details:", err_lbl)

            layout.addLayout(form)

            body_lbl = QLabel("Message Body:")
            body_lbl.setStyleSheet(f"font-weight: 700; color: {NAVY}; margin-top: 6px;")
            layout.addWidget(body_lbl)

            body_text = QTextEdit()
            body_text.setReadOnly(True)
            body_text.setText(msg.message_body)
            body_text.setStyleSheet(f"background-color: {CREAM}; border: 1px solid {LIGHT_GOLD}; border-radius: 6px;")
            layout.addWidget(body_text)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)


# ─────────────────────────────────────────────────────────────────────────────
# 2. BULK SEND CONFIRMATION DIALOG
# ─────────────────────────────────────────────────────────────────────────────

class BulkSendConfirmationDialog(QDialog):
    """
    Shows total candidates, eligible recipients, skipped contacts with reasons,
    and requires explicit confirmation before queueing bulk messages.
    """

    def __init__(self, recipient_data: dict[str, Any], message_body: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.recipient_data = recipient_data
        self.message_body = message_body
        self.setWindowTitle("Confirm Bulk Message Dispatch")
        self.resize(650, 520)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        title = QLabel("Confirm Message Queueing")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {NAVY};")
        layout.addWidget(title)

        eligible = self.recipient_data.get("eligible", [])
        skipped = self.recipient_data.get("skipped", [])

        summary_box = QFrame()
        summary_box.setStyleSheet(f"background-color: {CREAM}; border: 1px solid {LIGHT_GOLD}; border-radius: 6px;")
        s_layout = QHBoxLayout(summary_box)
        s_layout.addWidget(QLabel(f"<b>Total Evaluated:</b> {self.recipient_data.get('total_candidates', 0)}"))
        s_layout.addWidget(QLabel(f"<b>Eligible to Receive:</b> <span style='color:#15803D;'>{len(eligible)}</span>"))
        s_layout.addWidget(QLabel(f"<b>Skipped:</b> <span style='color:#DC2626;'>{len(skipped)}</span>"))
        layout.addWidget(summary_box)

        # Tabs: Eligible vs Skipped
        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabBar::tab {{ padding: 6px 12px; }}
            QTabBar::tab:selected {{ background: {NAVY}; color: {WHITE}; }}
        """)

        # Eligible Table
        e_table = QTableWidget(len(eligible), 4)
        e_table.setHorizontalHeaderLabels(["Recipient", "Student", "Batch", "Phone Number"])
        configure_table_ux(
            e_table,
            column_widths=[140, 140, 120, 130],
            stretch_column=0,
            flexible_columns=[0, 1],
            strategy=TableSizingStrategy.BOUNDED_AND_FLEXIBLE,
        )
        for row, r in enumerate(eligible):
            e_table.setItem(row, 0, QTableWidgetItem(r.get("recipient_name", "")))
            e_table.setItem(row, 1, QTableWidgetItem(r.get("student_name", "")))
            e_table.setItem(row, 2, QTableWidgetItem(r.get("batch_name", "")))
            e_table.setItem(row, 3, QTableWidgetItem(r.get("masked_phone", "")))
        auto_fit_columns(e_table)
        tabs.addTab(e_table, f"Eligible Recipients ({len(eligible)})")

        # Skipped Table
        s_table = QTableWidget(len(skipped), 3)
        s_table.setHorizontalHeaderLabels(["Contact Name", "Student", "Reason for Skipping"])
        configure_table_ux(
            s_table,
            column_widths=[140, 140, 260],
            stretch_column=2,
            flexible_columns=[2],
            strategy=TableSizingStrategy.BOUNDED_AND_FLEXIBLE,
        )
        for row, s in enumerate(skipped):
            s_table.setItem(row, 0, QTableWidgetItem(s.get("name", "")))
            s_table.setItem(row, 1, QTableWidgetItem(s.get("student_name", "")))
            reason_item = QTableWidgetItem(s.get("reason", ""))
            reason_item.setForeground(QColor("#DC2626"))
            s_table.setItem(row, 2, reason_item)
        auto_fit_columns(s_table)
        tabs.addTab(s_table, f"Skipped ({len(skipped)})")

        layout.addWidget(tabs, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        confirm_btn = QPushButton(f"Queue {len(eligible)} Messages")
        confirm_btn.setStyleSheet(f"background-color: {NAVY}; color: {WHITE}; font-weight: 700; padding: 8px 18px; border-radius: 6px;")
        confirm_btn.clicked.connect(self.accept)
        btn_row.addWidget(confirm_btn)

        layout.addLayout(btn_row)


# ─────────────────────────────────────────────────────────────────────────────
# 3. COMPLETE MESSAGES PAGE WIDGET
# ─────────────────────────────────────────────────────────────────────────────

class MessagesPageWidget(QWidget):
    """
    Main workspace for the TAMS Messages section.
    Integrates Overview KPIs, Compose Message, Message History, Queue & Failed,
    and Central Settings & Automation Rules.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("messagesPage")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            QWidget#messagesPage {{
                background-color: {CREAM};
            }}
        """)
        self._selected_compose_student_ids: set[int] = set()
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 18, 20, 18)
        main_layout.setSpacing(14)

        # Header Title Row
        top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        page_title = QLabel("💬 Messages & WhatsApp Communications")
        page_title.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {NAVY};")
        subtitle = QLabel("Send WhatsApp notices, track message delivery, manage queue retries, and configure automation rules.")
        subtitle.setStyleSheet(f"font-size: 13px; color: {MUTED};")

        title_box.addWidget(page_title)
        title_box.addWidget(subtitle)
        top_bar.addLayout(title_box)
        top_bar.addStretch()

        self.env_indicator = QLabel("PRODUCTION SENDER")
        self.env_indicator.setStyleSheet(
            "background-color: #DCFCE7; color: #15803D; padding: 5px 12px; border-radius: 12px; font-weight: 700; font-size: 11px;"
        )
        top_bar.addWidget(self.env_indicator)

        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.setStyleSheet(f"background-color: {CREAM}; color: {NAVY}; border: 1px solid {LIGHT_GOLD}; font-weight: 700; padding: 6px 14px; border-radius: 6px;")
        self.refresh_btn.clicked.connect(self.load_messages_data)
        top_bar.addWidget(self.refresh_btn)

        main_layout.addLayout(top_bar)

        # Main Subsections Tab Bar
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {LIGHT_GOLD};
                background: {CREAM};
                border-radius: 6px;
            }}
            QTabBar::tab {{
                background: {CREAM};
                color: {TEXT};
                padding: 10px 20px;
                font-weight: 700;
                font-size: 13px;
                border: 1px solid {LIGHT_GOLD};
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
            }}
            QTabBar::tab:selected {{
                background: {NAVY};
                color: {WHITE};
            }}
        """)

        self.tabs.addTab(self._create_overview_tab(), "📊 Overview")
        self.tabs.addTab(self._create_compose_tab(), "✍ Compose Message")
        self.tabs.addTab(self._create_history_tab(), "📜 Message History")
        self.tabs.addTab(self._create_queue_tab(), "⏳ Queue & Failed")
        self.settings_tab_widget = MessagingSettingsWidget()
        self.tabs.addTab(self.settings_tab_widget, "⚙ Settings & Automation")

        self.tabs.currentChanged.connect(self._on_tab_changed)
        main_layout.addWidget(self.tabs, 1)

    # ─────────────────────────────────────────────────────────────────────────
    # SUBTAB 1: OVERVIEW
    # ─────────────────────────────────────────────────────────────────────────
    def _create_overview_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("overviewScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        if scroll.viewport():
            scroll.viewport().setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            scroll.viewport().setStyleSheet(f"background-color: {CREAM};")
        scroll.setStyleSheet(f"""
            QScrollArea#overviewScrollArea {{
                background-color: {CREAM};
                border: none;
            }}
            QScrollArea#overviewScrollArea > QWidget > QWidget {{
                background-color: {CREAM};
            }}
        """)

        container = QWidget()
        container.setObjectName("overviewContainer")
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        container.setStyleSheet(f"#overviewContainer {{ background-color: {CREAM}; }}")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # KPI Summary Cards Row
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)

        self.kpi_total_sent = self._create_kpi_card("Total Logged", "0", "#012D54")
        self.kpi_queued = self._create_kpi_card("Queued Locally", "0", "#2563EB")
        self.kpi_accepted = self._create_kpi_card("Accepted by Meta", "0", "#15803D")
        self.kpi_delivered = self._create_kpi_card("Delivered (Confirmed)", "0", "#059669")
        self.kpi_retry = self._create_kpi_card("Awaiting Retry", "0", "#D97706")
        self.kpi_failed = self._create_kpi_card("Failed", "0", "#DC2626")

        kpi_row.addWidget(self.kpi_total_sent)
        kpi_row.addWidget(self.kpi_queued)
        kpi_row.addWidget(self.kpi_accepted)
        kpi_row.addWidget(self.kpi_delivered)
        kpi_row.addWidget(self.kpi_retry)
        kpi_row.addWidget(self.kpi_failed)
        layout.addLayout(kpi_row)

        # Charts Row
        charts_row = QHBoxLayout()
        charts_row.setSpacing(14)

        self.overview_status_chart = SegmentedDistributionWidget("Message Delivery Outcomes")
        self.overview_status_chart.setMinimumHeight(180)
        charts_row.addWidget(self.overview_status_chart, 1)

        self.overview_category_chart = SegmentedDistributionWidget("Message Categories Distribution")
        self.overview_category_chart.setMinimumHeight(180)
        charts_row.addWidget(self.overview_category_chart, 1)

        layout.addLayout(charts_row)

        # Operational Status Notice
        self.overview_conn_banner = QLabel("")
        self.overview_conn_banner.setWordWrap(True)
        self.overview_conn_banner.setStyleSheet("padding: 12px; border-radius: 6px; font-size: 13px;")
        layout.addWidget(self.overview_conn_banner)

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    def _create_kpi_card(self, title: str, initial_val: str, color_hex: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"background-color: {WHITE}; border: 1px solid {LIGHT_GOLD}; border-radius: 8px;")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {MUTED};")

        v_lbl = QLabel(initial_val)
        v_lbl.setObjectName("valLabel")
        v_lbl.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {color_hex};")

        layout.addWidget(t_lbl)
        layout.addWidget(v_lbl)
        return card

    # ─────────────────────────────────────────────────────────────────────────
    # SUBTAB 2: COMPOSE MESSAGE
    # ─────────────────────────────────────────────────────────────────────────
    def _create_compose_tab(self) -> QWidget:
        widget = QWidget()
        widget.setObjectName("composeTabWidget")
        widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        widget.setStyleSheet(f"""
            #composeTabWidget {{
                background-color: {CREAM};
            }}
            #composeTabWidget QLabel {{
                color: {NAVY};
                font-weight: 600;
            }}
        """)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        # Left Column: Recipient Selection
        left_box = QGroupBox("1. Select Recipients")
        left_box.setStyleSheet(f"QGroupBox {{ font-weight: 700; color: {NAVY}; }}")
        left_layout = QVBoxLayout(left_box)
        left_layout.setSpacing(10)

        # Target Mode Combo
        mode_row = QHBoxLayout()
        mode_lbl = QLabel("Target Mode:")
        mode_lbl.setStyleSheet(f"color: {NAVY}; font-weight: 600; font-size: 13px;")
        mode_row.addWidget(mode_lbl)
        self.compose_mode_combo = QComboBox()
        self.compose_mode_combo.addItem("Select Batch", "BATCH")
        self.compose_mode_combo.addItem("Select Specific Students", "STUDENT")
        self.compose_mode_combo.addItem("Custom Contact / Phone", "CUSTOM_PHONE")
        self.compose_mode_combo.currentIndexChanged.connect(self._on_compose_mode_changed)
        mode_row.addWidget(self.compose_mode_combo, 1)
        left_layout.addLayout(mode_row)

        # Batch Selector
        self.compose_batch_box = QWidget()
        bb_layout = QHBoxLayout(self.compose_batch_box)
        bb_layout.setContentsMargins(0, 0, 0, 0)
        batch_lbl = QLabel("Batch:")
        batch_lbl.setStyleSheet(f"color: {NAVY}; font-weight: 600; font-size: 13px;")
        bb_layout.addWidget(batch_lbl)
        self.compose_batch_combo = QComboBox()
        self.compose_batch_combo.currentIndexChanged.connect(self._update_compose_recipients)
        bb_layout.addWidget(self.compose_batch_combo, 1)
        left_layout.addWidget(self.compose_batch_box)

        # Student Search & Multi-select Table
        self.compose_student_box = QWidget()
        sb_layout = QVBoxLayout(self.compose_student_box)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_lbl = QLabel("Select Students:")
        sb_lbl.setStyleSheet(f"color: {NAVY}; font-weight: 600; font-size: 13px;")
        sb_layout.addWidget(sb_lbl)
        self.compose_student_search = QLineEdit()
        self.compose_student_search.setPlaceholderText("Search students by name or admission number...")
        self.compose_student_search.textChanged.connect(self._filter_compose_students)
        sb_layout.addWidget(self.compose_student_search)

        self.compose_students_table = QTableWidget()
        self.compose_students_table.setColumnCount(3)
        self.compose_students_table.setHorizontalHeaderLabels(["Select", "Student Name", "Admission No."])
        configure_table_ux(
            self.compose_students_table,
            column_widths=[70, 200, 140],
            stretch_column=1,
            flexible_columns=[1],
            strategy=TableSizingStrategy.BOUNDED_AND_FLEXIBLE,
        )
        sb_layout.addWidget(self.compose_students_table, 1)
        self.compose_student_box.setVisible(False)
        left_layout.addWidget(self.compose_student_box, 1)

        # Custom Phone Box
        self.compose_custom_box = QWidget()
        cb_layout = QFormLayout(self.compose_custom_box)
        cb_layout.setContentsMargins(0, 0, 0, 0)
        self.compose_custom_phone = QLineEdit()
        self.compose_custom_phone.setPlaceholderText("+91 98765 43210")
        self.compose_custom_phone.textChanged.connect(self._update_compose_recipients)
        self.compose_custom_name = QLineEdit()
        self.compose_custom_name.setPlaceholderText("Parent / Contact Name")
        phone_lbl = QLabel("Phone:")
        phone_lbl.setStyleSheet(f"color: {NAVY}; font-weight: 600; font-size: 13px;")
        name_lbl = QLabel("Name:")
        name_lbl.setStyleSheet(f"color: {NAVY}; font-weight: 600; font-size: 13px;")
        cb_layout.addRow(phone_lbl, self.compose_custom_phone)
        cb_layout.addRow(name_lbl, self.compose_custom_name)
        self.compose_custom_box.setVisible(False)
        left_layout.addWidget(self.compose_custom_box)

        # Live Deduplication Summary Banner
        self.compose_recipient_summary_lbl = QLabel("0 recipients selected")
        self.compose_recipient_summary_lbl.setStyleSheet(
            f"background-color: {CREAM}; border: 1px solid {LIGHT_GOLD}; padding: 8px; border-radius: 6px; font-weight: 600; font-size: 12px; color: {NAVY};"
        )
        left_layout.addWidget(self.compose_recipient_summary_lbl)

        layout.addWidget(left_box, 1)

        # Right Column: Message Content & Preview
        right_box = QGroupBox("2. Message Content & Preview")
        right_box.setStyleSheet(f"QGroupBox {{ font-weight: 700; color: {NAVY}; }}")
        right_layout = QVBoxLayout(right_box)
        right_layout.setSpacing(10)

        tmpl_row = QHBoxLayout()
        tmpl_lbl = QLabel("Use Template:")
        tmpl_lbl.setStyleSheet(f"color: {NAVY}; font-weight: 600; font-size: 13px;")
        tmpl_row.addWidget(tmpl_lbl)
        self.compose_template_combo = QComboBox()
        self.compose_template_combo.currentIndexChanged.connect(self._on_compose_template_changed)
        tmpl_row.addWidget(self.compose_template_combo, 1)
        right_layout.addLayout(tmpl_row)

        body_lbl = QLabel("Message Text (supports {{student_name}}, {{batch_name}}):")
        body_lbl.setStyleSheet(f"color: {NAVY}; font-weight: 600; font-size: 13px;")
        right_layout.addWidget(body_lbl)
        self.compose_body_edit = QTextEdit()
        self.compose_body_edit.setPlaceholderText("Write custom message or select template...")
        self.compose_body_edit.textChanged.connect(self._update_compose_preview)
        right_layout.addWidget(self.compose_body_edit, 1)

        prev_lbl = QLabel("Live Interpolated Preview:")
        prev_lbl.setStyleSheet(f"color: {NAVY}; font-weight: 600; font-size: 13px;")
        right_layout.addWidget(prev_lbl)
        self.compose_preview_lbl = QTextEdit()
        self.compose_preview_lbl.setReadOnly(True)
        self.compose_preview_lbl.setFixedHeight(90)
        self.compose_preview_lbl.setStyleSheet(f"background-color: {CREAM}; border: 1px solid {LIGHT_GOLD}; border-radius: 6px;")
        right_layout.addWidget(self.compose_preview_lbl)

        # Dispatch Button Row
        btn_row = QHBoxLayout()
        self.compose_clear_btn = QPushButton("Clear")
        self.compose_clear_btn.clicked.connect(self._on_compose_clear)
        btn_row.addWidget(self.compose_clear_btn)

        btn_row.addStretch()

        self.compose_send_btn = QPushButton("Queue & Send Messages 🚀")
        self.compose_send_btn.setStyleSheet(f"background-color: {NAVY}; color: {WHITE}; font-weight: 700; padding: 10px 22px; border-radius: 6px;")
        self.compose_send_btn.clicked.connect(self._on_compose_send)
        btn_row.addWidget(self.compose_send_btn)

        right_layout.addLayout(btn_row)

        layout.addWidget(right_box, 1)
        return widget

    def _on_compose_mode_changed(self):
        mode = self.compose_mode_combo.currentData()
        self.compose_batch_box.setVisible(mode == "BATCH")
        self.compose_student_box.setVisible(mode == "STUDENT")
        self.compose_custom_box.setVisible(mode == "CUSTOM_PHONE")
        self._update_compose_recipients()

    def _update_compose_recipients(self):
        mode = self.compose_mode_combo.currentData()
        with SessionLocal() as session:
            target_ids = []
            custom_phone = None
            custom_name = None

            if mode == "BATCH":
                bid = self.compose_batch_combo.currentData()
                if bid:
                    target_ids = [bid]
            elif mode == "STUDENT":
                target_ids = list(self._selected_compose_student_ids)
            elif mode == "CUSTOM_PHONE":
                custom_phone = self.compose_custom_phone.text().strip()
                custom_name = self.compose_custom_name.text().strip()

            res = get_eligible_recipients(
                session,
                target_type=mode,
                target_ids=target_ids,
                custom_phone=custom_phone,
                custom_name=custom_name,
            )
            self._current_recipients_result = res

            eligible_cnt = res["eligible_count"]
            skipped_cnt = res["skipped_count"]
            self.compose_recipient_summary_lbl.setText(
                f"✅ <b>{eligible_cnt} eligible recipients</b> (Deduplicated) "
                f"| ⚠️ <b>{skipped_cnt} skipped</b>"
            )

        self._update_compose_preview()

    def _on_compose_template_changed(self):
        tid = self.compose_template_combo.currentData()
        if not tid:
            return
        with SessionLocal() as session:
            tmpl = session.get(MessageTemplate, tid)
            if tmpl:
                self.compose_body_edit.setText(tmpl.body)

    def _update_compose_preview(self):
        text = self.compose_body_edit.toPlainText().strip()
        sample_context = {
            "student_name": "Rohan Sharma",
            "batch_name": "Class 10 Science",
            "amount": "2,500",
            "due_date": "2026-10-15",
            "date": "2026-10-11",
            "test_date": "2026-10-11",
            "marks": "45",
            "max_marks": "50",
            "percentage": "90.0",
            "test_name": "Unit Test 1",
            "batch_avg": "72.4",
        }
        rendered = render_template_text(text, sample_context)
        self.compose_preview_lbl.setText(rendered)

    def _on_compose_clear(self):
        self._selected_compose_student_ids.clear()
        self.compose_body_edit.clear()
        self.compose_custom_phone.clear()
        self.compose_custom_name.clear()
        self._filter_compose_students()
        self._update_compose_recipients()

    def _on_compose_send(self):
        if not hasattr(self, "_current_recipients_result"):
            self._update_compose_recipients()

        res = self._current_recipients_result
        eligible = res.get("eligible", [])

        if not eligible:
            QMessageBox.warning(self, "No Recipients", "There are no eligible recipients to message.")
            return

        body_text = self.compose_body_edit.toPlainText().strip()
        if not body_text:
            QMessageBox.warning(self, "Empty Message", "Please enter message text or select a template.")
            return

        # Confirm bulk dispatch
        confirm_dlg = BulkSendConfirmationDialog(res, body_text, self)
        if not confirm_dlg.exec():
            return

        # Queue messages
        tid = self.compose_template_combo.currentData()
        with SessionLocal() as session:
            tmpl = session.get(MessageTemplate, tid) if tid else None
            count = queue_bulk_messages(
                session,
                recipients=eligible,
                message_body_template=body_text,
                template_id=tmpl.id if tmpl else None,
                template_name=tmpl.name if tmpl else None,
                category=tmpl.category if tmpl else "UTILITY",
                trigger_type="MANUAL",
                source_module="COMPOSE",
            )

        QMessageBox.information(
            self,
            "Messages Queued",
            f"✅ <b>{count} messages successfully queued!</b>\n\n"
            "The background worker will dispatch them according to rate limits and retry policies.",
        )
        self.load_messages_data()
        self.tabs.setCurrentIndex(3)  # Switch to Queue tab to see them

    # ─────────────────────────────────────────────────────────────────────────
    # SUBTAB 3: MESSAGE HISTORY
    # ─────────────────────────────────────────────────────────────────────────
    def _create_history_tab(self) -> QWidget:
        widget = QWidget()
        widget.setObjectName("historyTabWidget")
        widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        widget.setStyleSheet(f"""
            #historyTabWidget {{
                background-color: {CREAM};
            }}
            #historyTabWidget QLabel {{
                color: {NAVY};
                font-weight: 600;
            }}
        """)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Filters Bar
        filter_box = QGroupBox("Search & Filters")
        filter_box.setStyleSheet(f"QGroupBox {{ font-weight: 700; color: {NAVY}; }}")
        f_layout = QGridLayout(filter_box)
        f_layout.setSpacing(10)

        # Row 1: Search, Batch, Status
        self.history_search = QLineEdit()
        self.history_search.setPlaceholderText("Search recipient, student, or phone...")
        self.history_search.textChanged.connect(self._filter_history_table)
        search_lbl = QLabel("Search:")
        search_lbl.setStyleSheet(f"color: {NAVY}; font-weight: 600; font-size: 13px;")
        f_layout.addWidget(search_lbl, 0, 0)
        f_layout.addWidget(self.history_search, 0, 1)

        self.history_batch_filter = QComboBox()
        self.history_batch_filter.addItem("All Batches", None)
        self.history_batch_filter.currentIndexChanged.connect(self._filter_history_table)
        batch_lbl = QLabel("Batch:")
        batch_lbl.setStyleSheet(f"color: {NAVY}; font-weight: 600; font-size: 13px;")
        f_layout.addWidget(batch_lbl, 0, 2)
        f_layout.addWidget(self.history_batch_filter, 0, 3)

        self.history_status_filter = QComboBox()
        self.history_status_filter.addItems([
            "All Statuses", "QUEUED", "SENDING", "ACCEPTED", "DELIVERED", "READ", "FAILED", "RETRY_SCHEDULED", "CANCELLED"
        ])
        self.history_status_filter.currentIndexChanged.connect(self._filter_history_table)
        status_lbl = QLabel("Status:")
        status_lbl.setStyleSheet(f"color: {NAVY}; font-weight: 600; font-size: 13px;")
        f_layout.addWidget(status_lbl, 0, 4)
        f_layout.addWidget(self.history_status_filter, 0, 5)

        # Row 2: Category, Trigger, Export CSV
        self.history_cat_filter = QComboBox()
        self.history_cat_filter.addItems(["All Categories", "UTILITY", "MARKETING", "AUTHENTICATION"])
        self.history_cat_filter.currentIndexChanged.connect(self._filter_history_table)
        cat_lbl = QLabel("Category:")
        cat_lbl.setStyleSheet(f"color: {NAVY}; font-weight: 600; font-size: 13px;")
        f_layout.addWidget(cat_lbl, 1, 0)
        f_layout.addWidget(self.history_cat_filter, 1, 1)

        self.history_trigger_filter = QComboBox()
        self.history_trigger_filter.addItems(["All Triggers", "MANUAL", "AUTOMATED"])
        self.history_trigger_filter.currentIndexChanged.connect(self._filter_history_table)
        trig_lbl = QLabel("Trigger:")
        trig_lbl.setStyleSheet(f"color: {NAVY}; font-weight: 600; font-size: 13px;")
        f_layout.addWidget(trig_lbl, 1, 2)
        f_layout.addWidget(self.history_trigger_filter, 1, 3)

        self.export_csv_btn = QPushButton("📥 Export Filtered CSV")
        self.export_csv_btn.setStyleSheet(f"background-color: {CREAM}; color: {NAVY}; border: 1px solid {LIGHT_GOLD}; font-weight: 700; padding: 6px 12px; border-radius: 6px;")
        self.export_csv_btn.clicked.connect(self._on_export_csv)
        f_layout.addWidget(self.export_csv_btn, 1, 5)

        layout.addWidget(filter_box)

        # History Table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(10)
        self.history_table.setHorizontalHeaderLabels([
            "Timestamp", "Recipient", "Student", "Batch", "Phone", "Template", "Status", "Retries", "Provider ID", "Actions"
        ])
        configure_table_ux(
            self.history_table,
            column_widths=[140, 140, 140, 120, 120, 140, 100, 70, 150, 80],
            stretch_column=1,
            flexible_columns=[1, 2, 5],
            fixed_columns=[9],
            strategy=TableSizingStrategy.WIDE_SCROLLABLE,
        )
        layout.addWidget(self.history_table, 1)

        return widget

    def _filter_history_table(self):
        batch_id = self.history_batch_filter.currentData()
        status_f = self.history_status_filter.currentText()
        cat_f = self.history_cat_filter.currentText()
        trig_f = self.history_trigger_filter.currentText()
        query = self.history_search.text().strip()

        with SessionLocal() as session:
            records = get_message_history_records(
                session,
                batch_id=batch_id,
                status_filter=status_f,
                category_filter=cat_f,
                trigger_filter=trig_f,
                search_query=query,
                limit=150,
            )

        self.history_table.setRowCount(len(records))
        for row, r in enumerate(records):
            self.history_table.setItem(row, 0, QTableWidgetItem(r["date_time"]))
            self.history_table.setItem(row, 1, QTableWidgetItem(r["recipient_name"]))
            self.history_table.setItem(row, 2, QTableWidgetItem(r["student_name"]))
            self.history_table.setItem(row, 3, QTableWidgetItem(r["batch_name"]))
            self.history_table.setItem(row, 4, QTableWidgetItem(r["phone_masked"]))
            self.history_table.setItem(row, 5, QTableWidgetItem(r["template_name"]))

            # Status Badge
            st = r["status"]
            bg, fg = ("#DCFCE7", "#15803D") if st in ("ACCEPTED", "DELIVERED", "READ") else (
                ("#FEF3C7", "#B45309") if st in ("QUEUED", "SENDING", "RETRY_SCHEDULED") else ("#FEE2E2", "#B91C1C")
            )
            badge_item = QTableWidgetItem(st)
            badge_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.history_table.setItem(row, 6, badge_item)

            ret_item = QTableWidgetItem(str(r["retry_count"]))
            ret_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.history_table.setItem(row, 7, ret_item)

            self.history_table.setItem(row, 8, QTableWidgetItem(r["provider_message_id"]))

            view_btn = QPushButton("View")
            view_btn.setFixedSize(65, 26)
            view_btn.setStyleSheet(f"background-color: {CREAM}; color: {NAVY}; border: 1px solid {LIGHT_GOLD}; font-size: 11px; border-radius: 4px;")
            view_btn.clicked.connect(lambda checked=False, mid=r["id"]: self._inspect_message_details(mid))
            self.history_table.setCellWidget(row, 9, view_btn)

        auto_fit_columns(self.history_table)

    def _inspect_message_details(self, message_id: int):
        dlg = MessageDetailsDialog(message_id, self)
        dlg.exec()

    def _on_export_csv(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Message History CSV",
            f"TAMS_Message_History_{date.today().strftime('%Y%m%d')}.csv",
            "CSV Files (*.csv)",
        )
        if not file_path:
            return

        with SessionLocal() as session:
            csv_content = export_message_history_csv(
                session,
                batch_id=self.history_batch_filter.currentData(),
                status_filter=self.history_status_filter.currentText(),
            )

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(csv_content)

        QMessageBox.information(self, "Exported", f"Message history successfully exported to:\n{file_path}")

    # ─────────────────────────────────────────────────────────────────────────
    # SUBTAB 4: QUEUE & FAILED MESSAGES
    # ─────────────────────────────────────────────────────────────────────────
    def _create_queue_tab(self) -> QWidget:
        widget = QWidget()
        widget.setObjectName("queueTabWidget")
        widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        widget.setStyleSheet(f"#queueTabWidget {{ background-color: {CREAM}; }}")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Queue Actions Bar
        action_bar = QHBoxLayout()
        action_bar.setSpacing(10)

        self.queue_status_lbl = QLabel("Queue Status: Active")
        self.queue_status_lbl.setStyleSheet(f"font-weight: 700; color: {NAVY}; font-size: 13px;")
        action_bar.addWidget(self.queue_status_lbl)

        action_bar.addStretch()

        self.retry_all_failed_btn = QPushButton("🔄 Retry Eligible Failed")
        self.retry_all_failed_btn.setStyleSheet(f"background-color: {CREAM}; color: {NAVY}; border: 1px solid {LIGHT_GOLD}; font-weight: 700; padding: 6px 14px; border-radius: 6px;")
        self.retry_all_failed_btn.clicked.connect(self._on_retry_all_failed)
        action_bar.addWidget(self.retry_all_failed_btn)

        self.clear_completed_btn = QPushButton("🧹 Clear Old Completed")
        self.clear_completed_btn.clicked.connect(self._on_clear_completed)
        action_bar.addWidget(self.clear_completed_btn)

        layout.addLayout(action_bar)

        # Queue Table
        self.queue_table = QTableWidget()
        self.queue_table.setColumnCount(9)
        self.queue_table.setHorizontalHeaderLabels([
            "ID", "Queued At", "Recipient", "Phone", "Status", "Retries", "Next Retry", "Last Error", "Actions"
        ])
        configure_table_ux(
            self.queue_table,
            column_widths=[60, 140, 140, 120, 110, 70, 140, 200, 140],
            stretch_column=7,
            flexible_columns=[2, 7],
            fixed_columns=[8],
            strategy=TableSizingStrategy.WIDE_SCROLLABLE,
        )
        layout.addWidget(self.queue_table, 1)

        return widget

    def _load_queue_table(self):
        with SessionLocal() as session:
            q_stmt = select(Message).where(
                Message.status.in_(["QUEUED", "SENDING", "RETRY_SCHEDULED", "FAILED"])
            ).order_by(Message.queued_at.desc()).limit(150)
            items = list(session.scalars(q_stmt).all())

            self.queue_table.setRowCount(len(items))
            for row, m in enumerate(items):
                self.queue_table.setItem(row, 0, QTableWidgetItem(str(m.id)))
                self.queue_table.setItem(row, 1, QTableWidgetItem(m.queued_at.strftime("%d %b %H:%M")))
                self.queue_table.setItem(row, 2, QTableWidgetItem(m.recipient_name))
                self.queue_table.setItem(row, 3, QTableWidgetItem(m.recipient_phone))

                st_item = QTableWidgetItem(m.status)
                st_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.queue_table.setItem(row, 4, st_item)

                ret_item = QTableWidgetItem(f"{m.retry_count}/{m.max_retries}")
                ret_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.queue_table.setItem(row, 5, ret_item)

                next_ret = m.next_retry_at.strftime("%d %b %H:%M:%S") if m.next_retry_at else "—"
                self.queue_table.setItem(row, 6, QTableWidgetItem(next_ret))

                err_text = m.error_message or "—"
                self.queue_table.setItem(row, 7, QTableWidgetItem(err_text))

                # Actions Box (Retry / Cancel)
                act_widget = QWidget()
                act_layout = QHBoxLayout(act_widget)
                act_layout.setContentsMargins(0, 0, 0, 0)
                act_layout.setSpacing(4)

                if m.status in ("FAILED", "RETRY_SCHEDULED"):
                    r_btn = QPushButton("Retry")
                    r_btn.setFixedSize(55, 24)
                    r_btn.setStyleSheet(f"background-color: {CREAM}; color: {NAVY}; font-size: 11px; border: 1px solid {LIGHT_GOLD}; border-radius: 4px;")
                    r_btn.clicked.connect(lambda checked=False, mid=m.id: self._retry_single_message(mid))
                    act_layout.addWidget(r_btn)

                if m.status in ("QUEUED", "RETRY_SCHEDULED"):
                    c_btn = QPushButton("Cancel")
                    c_btn.setFixedSize(55, 24)
                    c_btn.setStyleSheet("color: #DC2626; font-size: 11px; border: 1px solid #FCA5A5; border-radius: 4px;")
                    c_btn.clicked.connect(lambda checked=False, mid=m.id: self._cancel_single_message(mid))
                    act_layout.addWidget(c_btn)

                self.queue_table.setCellWidget(row, 8, act_widget)

            auto_fit_columns(self.queue_table)

    def _retry_single_message(self, message_id: int):
        with SessionLocal() as session:
            retry_failed_message(session, message_id)
        self._load_queue_table()

    def _cancel_single_message(self, message_id: int):
        with SessionLocal() as session:
            cancel_pending_message(session, message_id)
        self._load_queue_table()

    def _on_retry_all_failed(self):
        with SessionLocal() as session:
            failed_msgs = session.scalars(select(Message).where(Message.status == "FAILED")).all()
            for m in failed_msgs:
                m.status = "QUEUED"
                m.next_retry_at = None
            session.commit()
            count = len(failed_msgs)

        QMessageBox.information(self, "Retried", f"{count} failed messages requeued for delivery.")
        self._load_queue_table()

    def _on_clear_completed(self):
        res = QMessageBox.question(
            self,
            "Clear Completed Messages",
            "Are you sure you want to purge delivered messages older than 30 days?\n(Audit logs for recent deliveries remain preserved).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if res == QMessageBox.StandardButton.Yes:
            with SessionLocal() as session:
                cnt = clear_completed_messages(session, days_old=30)
            QMessageBox.information(self, "Purged", f"{cnt} old records cleared from the active queue.")
            self._load_queue_table()

    # ─────────────────────────────────────────────────────────────────────────
    # DATA LOADING & TAB SYNCS
    # ─────────────────────────────────────────────────────────────────────────

    def load_messages_data(self):
        """Refreshes all message datasets, dropdowns, tables, and KPI metrics."""
        with SessionLocal() as session:
            stats = get_messaging_overview_stats(session)

            # Update KPI Cards
            st_counts = stats["status_counts"]
            self.kpi_total_sent.findChild(QLabel, "valLabel").setText(str(stats["total_messages"]))
            self.kpi_queued.findChild(QLabel, "valLabel").setText(str(st_counts.get("QUEUED", 0) + st_counts.get("SENDING", 0)))
            self.kpi_accepted.findChild(QLabel, "valLabel").setText(str(st_counts.get("ACCEPTED", 0)))
            self.kpi_delivered.findChild(QLabel, "valLabel").setText(str(st_counts.get("DELIVERED", 0) + st_counts.get("READ", 0)))
            self.kpi_retry.findChild(QLabel, "valLabel").setText(str(st_counts.get("RETRY_SCHEDULED", 0)))
            self.kpi_failed.findChild(QLabel, "valLabel").setText(str(st_counts.get("FAILED", 0)))

            # Update Status Outcomes Chart
            outcomes_data = [
                {"label": "Accepted / Sent", "count": st_counts.get("ACCEPTED", 0) + st_counts.get("DELIVERED", 0) + st_counts.get("READ", 0), "color": "#16A34A"},
                {"label": "Queued / Sending", "count": st_counts.get("QUEUED", 0) + st_counts.get("SENDING", 0), "color": "#2563EB"},
                {"label": "Awaiting Retry", "count": st_counts.get("RETRY_SCHEDULED", 0), "color": "#D97706"},
                {"label": "Failed", "count": st_counts.get("FAILED", 0), "color": "#DC2626"},
            ]
            self.overview_status_chart.set_data(outcomes_data)

            # Categories Distribution Chart
            cats_data = [
                {"label": cat, "count": cnt, "color": "#012D54" if cat == "UTILITY" else "#D9B85F"}
                for cat, cnt in stats["categories_count"].items()
            ]
            self.overview_category_chart.set_data(cats_data)

            # Environment Banner
            env = stats["environment"]
            self.env_indicator.setText(f"{env} SENDER")
            if env == "PRODUCTION":
                self.env_indicator.setStyleSheet("background-color: #DCFCE7; color: #15803D; padding: 5px 12px; border-radius: 12px; font-weight: 700; font-size: 11px;")
            else:
                self.env_indicator.setStyleSheet("background-color: #FEF3C7; color: #B45309; padding: 5px 12px; border-radius: 12px; font-weight: 700; font-size: 11px;")

            if stats["connection_status"] == "CONFIGURED":
                self.overview_conn_banner.setText("✅ <b>WhatsApp Cloud API Configured:</b> Outgoing message queue is operational.")
                self.overview_conn_banner.setStyleSheet("background-color: #DCFCE7; color: #15803D; padding: 10px; border-radius: 6px; font-size: 12px;")
            else:
                self.overview_conn_banner.setText("⚠️ <b>WhatsApp Credentials Missing:</b> Go to the Settings & Automation tab to enter your Phone Number ID and Access Token.")
                self.overview_conn_banner.setStyleSheet("background-color: #FEF3C7; color: #B45309; padding: 10px; border-radius: 6px; font-size: 12px;")

            # Populate Batch Dropdowns
            batches = session.scalars(select(Batch).where(Batch.active == True).order_by(Batch.name.asc())).all()
            self.compose_batch_combo.blockSignals(True)
            self.compose_batch_combo.clear()
            for b in batches:
                self.compose_batch_combo.addItem(b.name, b.id)
            self.compose_batch_combo.blockSignals(False)

            self.history_batch_filter.blockSignals(True)
            self.history_batch_filter.clear()
            self.history_batch_filter.addItem("All Batches", None)
            for b in batches:
                self.history_batch_filter.addItem(b.name, b.id)
            self.history_batch_filter.blockSignals(False)

            # Populate Templates in Compose Dropdown
            tmpls = session.scalars(select(MessageTemplate).where(MessageTemplate.is_active == True).order_by(MessageTemplate.name.asc())).all()
            self.compose_template_combo.blockSignals(True)
            self.compose_template_combo.clear()
            self.compose_template_combo.addItem("Select a Template...", None)
            for t in tmpls:
                self.compose_template_combo.addItem(f"{t.name} ({t.category})", t.id)
            self.compose_template_combo.blockSignals(False)

            # Load Compose Student Multi-select table
            students = session.scalars(select(Student).where(Student.status == "ACTIVE").order_by(Student.first_name.asc())).all()
            self._cached_compose_students = students
            self._filter_compose_students()

        self._filter_history_table()
        self._load_queue_table()
        self._update_compose_recipients()

    def _on_compose_student_toggled(self, student_id: int, checked: bool):
        if checked:
            self._selected_compose_student_ids.add(student_id)
        else:
            self._selected_compose_student_ids.discard(student_id)
        self._update_compose_recipients()

    def _filter_compose_students(self):
        if not hasattr(self, "_cached_compose_students"):
            return
        query = self.compose_student_search.text().strip().lower()
        filtered = [
            s for s in self._cached_compose_students
            if query in s.first_name.lower() or query in (s.last_name or "").lower() or query in (s.admission_number or "").lower()
        ]

        self.compose_students_table.setRowCount(len(filtered))
        for row, s in enumerate(filtered):
            cb = QCheckBox()
            cb.setChecked(s.id in self._selected_compose_student_ids)
            cb.toggled.connect(lambda checked, sid=s.id: self._on_compose_student_toggled(sid, checked))
            cb_container = QWidget()
            cb_l = QHBoxLayout(cb_container)
            cb_l.setContentsMargins(0, 0, 0, 0)
            cb_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb_l.addWidget(cb)
            self.compose_students_table.setCellWidget(row, 0, cb_container)

            name_item = QTableWidgetItem(f"{s.first_name} {s.last_name or ''}".strip())
            name_item.setData(Qt.ItemDataRole.UserRole, s.id)
            self.compose_students_table.setItem(row, 1, name_item)

            self.compose_students_table.setItem(row, 2, QTableWidgetItem(s.admission_number or "—"))

        auto_fit_columns(self.compose_students_table)

    def _on_tab_changed(self, index: int):
        if index == 0:
            self.load_messages_data()
        elif index == 2:
            self._filter_history_table()
        elif index == 3:
            self._load_queue_table()
        elif index == 4:
            self.settings_tab_widget.load_settings()
