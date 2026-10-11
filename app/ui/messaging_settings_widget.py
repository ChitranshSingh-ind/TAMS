"""
Dedicated Messaging Settings Widget & Dialogs for TAMS.
Provides centralized configuration for WhatsApp Cloud API, Meta developer test sender,
secure credential management, templates, automation rules, retry/queue policies,
opt-out preferences, and safe diagnostics.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from PyQt6.QtCore import Qt, QTime
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.database.models.batch import Batch
from app.database.models.message import (
    Message,
    MessageTemplate,
    MessagingConfig,
    NotificationRule,
    RecipientPreference,
)
from app.services.messaging_service import (
    ensure_messaging_seed_data,
    get_messaging_config,
    get_whatsapp_provider_client,
    update_messaging_config,
)
from app.services.whatsapp_provider import (
    DEFAULT_GRAPH_API_VERSION,
    get_access_token,
    mask_phone_number,
    mask_token,
    normalize_phone_number,
    remove_access_token,
    save_access_token,
)
from app.ui.table_utils import configure_table_ux

# TAMS Design Palette
NAVY = "#012D54"
DARK_NAVY = "#04294D"
GOLD = "#D9B85F"
LIGHT_GOLD = "#E9DEBA"
CREAM = "#F8F6EA"
WHITE = "#FEFEFE"
TEXT = "#1F2937"
MUTED = "#615F4B"


# ─────────────────────────────────────────────────────────────────────────────
# 1. SEND TEST MESSAGE DIALOG
# ─────────────────────────────────────────────────────────────────────────────

class SendTestMessageDialog(QDialog):
    """
    Explicit, deliberate dialog to send a real WhatsApp test message.
    Requires explicit phone entry, template selection (e.g. 'hello_world'),
    and a clear confirmation checkbox before dispatching.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Send WhatsApp Test Message")
        self.resize(520, 480)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        title = QLabel("📲 Send Test WhatsApp Message")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {NAVY};")
        layout.addWidget(title)

        banner = QLabel(
            "<b>Important:</b> In Meta Developer Test Mode, messages can only be delivered "
            "to phone numbers explicitly registered under <i>'To'</i> in the Meta WhatsApp Getting Started dashboard."
        )
        banner.setWordWrap(True)
        banner.setStyleSheet(
            "background-color: #FEF3C7; color: #92400E; padding: 10px; border-radius: 6px; font-size: 12px;"
        )
        layout.addWidget(banner)

        form = QFormLayout()
        form.setSpacing(12)

        self.recipient_input = QLineEdit()
        self.recipient_input.setPlaceholderText("+91 98765 43210 or 10-digit mobile")
        form.addRow("Recipient Phone:", self.recipient_input)

        self.template_combo = QComboBox()
        self.template_combo.addItem("hello_world (Meta pre-approved default)", "hello_world")
        self.template_combo.addItem("Free-form Text (only valid if within 24h window)", "__free_text__")

        # Load local active templates
        with SessionLocal() as session:
            templates = session.scalars(select(MessageTemplate).where(MessageTemplate.is_active == True)).all()
            for t in templates:
                if t.name != "hello_world":
                    self.template_combo.addItem(f"{t.name} ({t.meta_template_name})", t.name)

        self.template_combo.currentIndexChanged.connect(self._on_template_changed)
        form.addRow("Template:", self.template_combo)

        self.body_preview = QTextEdit()
        self.body_preview.setReadOnly(True)
        self.body_preview.setFixedHeight(90)
        self.body_preview.setStyleSheet(f"background-color: {CREAM}; border: 1px solid {LIGHT_GOLD}; border-radius: 6px;")
        form.addRow("Preview:", self.body_preview)

        layout.addLayout(form)

        self.confirm_cb = QCheckBox("I understand this will send a real WhatsApp message to the entered recipient")
        self.confirm_cb.setStyleSheet(f"color: {TEXT}; font-weight: 600; font-size: 12px;")
        layout.addWidget(self.confirm_cb)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        self.send_btn = QPushButton("Send Message")
        self.send_btn.setStyleSheet(f"background-color: {NAVY}; color: {WHITE}; font-weight: 700; padding: 8px 18px; border-radius: 6px;")
        self.send_btn.clicked.connect(self._on_send)
        btn_row.addWidget(self.send_btn)

        layout.addLayout(btn_row)
        self._on_template_changed()

    def _on_template_changed(self):
        data = self.template_combo.currentData()
        if data == "hello_world":
            self.body_preview.setText("Welcome and congratulations! This message confirms your WhatsApp connection with TAMS.")
            self.body_preview.setReadOnly(True)
        elif data == "__free_text__":
            self.body_preview.setReadOnly(False)
            self.body_preview.setText("Test message from TAMS Coaching Platform.")
        else:
            with SessionLocal() as session:
                tmpl = session.scalar(select(MessageTemplate).where(MessageTemplate.name == data))
                if tmpl:
                    self.body_preview.setText(tmpl.body)
                    self.body_preview.setReadOnly(True)

    def _on_send(self):
        phone = self.recipient_input.text().strip()
        if not phone:
            QMessageBox.warning(self, "Missing Phone", "Please enter a recipient phone number.")
            return

        is_valid, e164, reason = normalize_phone_number(phone)
        if not is_valid:
            QMessageBox.warning(self, "Invalid Phone", f"Phone number error: {reason}")
            return

        if not self.confirm_cb.isChecked():
            QMessageBox.warning(self, "Confirmation Required", "Please check the confirmation box before sending.")
            return

        tmpl_data = self.template_combo.currentData()
        with SessionLocal() as session:
            provider = get_whatsapp_provider_client(session)

            if tmpl_data == "hello_world":
                res = provider.send_template_message(
                    recipient_phone=e164,
                    template_name="hello_world",
                    language_code="en_US",
                )
            elif tmpl_data == "__free_text__":
                res = provider.send_text_message(
                    recipient_phone=e164,
                    message_body=self.body_preview.toPlainText().strip(),
                )
            else:
                tmpl = session.scalar(select(MessageTemplate).where(MessageTemplate.name == tmpl_data))
                res = provider.send_template_message(
                    recipient_phone=e164,
                    template_name=tmpl.meta_template_name if tmpl else tmpl_data,
                    language_code=tmpl.language if tmpl else "en",
                )

        if res.success:
            QMessageBox.information(
                self,
                "Message Accepted by Meta",
                f"✅ Test message accepted successfully by Meta WhatsApp Cloud API!\n\n"
                f"Provider Message ID: {res.provider_message_id}\n"
                f"Recipient: {e164}\n\n"
                f"Status: ACCEPTED (Waiting for delivery confirmation).",
            )
            self.accept()
        else:
            QMessageBox.critical(
                self,
                "Delivery Request Failed",
                f"❌ Meta API rejected the message:\n\n"
                f"Error Code: {res.error_code}\n"
                f"Details: {res.error_message}\n\n"
                f"Note: In test mode, verify that {e164} is added as a permitted test recipient in Meta Developer Portal.",
            )


# ─────────────────────────────────────────────────────────────────────────────
# 2. TEMPLATE EDIT DIALOG
# ─────────────────────────────────────────────────────────────────────────────

class TemplateEditDialog(QDialog):
    """Dialog to create or edit local message templates."""

    def __init__(self, template_id: int | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.template_id = template_id
        self.setWindowTitle("Edit Template" if template_id else "New Message Template")
        self.resize(500, 480)
        self.setup_ui()
        if template_id:
            self._load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        form.setSpacing(10)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. fee_due_reminder")
        form.addRow("Identifier:", self.name_input)

        self.meta_name_input = QLineEdit()
        self.meta_name_input.setPlaceholderText("e.g. fee_due_reminder (Meta exact name)")
        form.addRow("Meta Template Name:", self.meta_name_input)

        self.category_combo = QComboBox()
        self.category_combo.addItems(["UTILITY", "MARKETING", "AUTHENTICATION"])
        form.addRow("Category:", self.category_combo)

        self.language_input = QLineEdit("en")
        form.addRow("Language Code:", self.language_input)

        self.trigger_combo = QComboBox()
        self.trigger_combo.addItems(["MANUAL", "FEE_DUE", "FEE_OVERDUE", "PAYMENT_RECEIPT", "ABSENCE", "CONSECUTIVE_ABSENCE", "TEST_RESULT"])
        form.addRow("Trigger Event:", self.trigger_combo)

        self.body_input = QTextEdit()
        self.body_input.setPlaceholderText("Enter template text. Use {{student_name}}, {{amount}}, {{due_date}}, etc.")
        self.body_input.setFixedHeight(120)
        form.addRow("Message Body:", self.body_input)

        layout.addLayout(form)

        hint = QLabel("💡 <i>Note: Changing a local template does not alter the approved template in Meta WhatsApp Manager.</i>")
        hint.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save Template")
        save_btn.setStyleSheet(f"background-color: {NAVY}; color: {WHITE}; font-weight: 700; padding: 6px 16px; border-radius: 6px;")
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def _load_data(self):
        with SessionLocal() as session:
            tmpl = session.get(MessageTemplate, self.template_id)
            if tmpl:
                self.name_input.setText(tmpl.name)
                self.meta_name_input.setText(tmpl.meta_template_name)
                self.category_combo.setCurrentText(tmpl.category)
                self.language_input.setText(tmpl.language)
                self.body_input.setText(tmpl.body)
                if tmpl.associated_trigger:
                    self.trigger_combo.setCurrentText(tmpl.associated_trigger)

    def _on_save(self):
        name = self.name_input.text().strip()
        meta_name = self.meta_name_input.text().strip() or name
        body = self.body_input.toPlainText().strip()

        if not name or not body:
            QMessageBox.warning(self, "Incomplete", "Please provide a template identifier and message body.")
            return

        with SessionLocal() as session:
            if self.template_id:
                tmpl = session.get(MessageTemplate, self.template_id)
            else:
                tmpl = MessageTemplate(name=name, meta_template_name=meta_name, body=body)
                session.add(tmpl)

            tmpl.name = name
            tmpl.meta_template_name = meta_name
            tmpl.category = self.category_combo.currentText()
            tmpl.language = self.language_input.text().strip() or "en"
            tmpl.associated_trigger = self.trigger_combo.currentText()
            tmpl.body = body

            session.commit()

        self.accept()


# ─────────────────────────────────────────────────────────────────────────────
# 3. MAIN MESSAGING SETTINGS WIDGET (EMBEDDABLE IN SETTINGS & MESSAGES PAGE)
# ─────────────────────────────────────────────────────────────────────────────

class MessagingSettingsWidget(QWidget):
    """
    Comprehensive central settings workspace for Messaging and WhatsApp integration.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(14)

        # Header Title and Environment Badge
        top_row = QHBoxLayout()
        header_title = QLabel("⚙ Messaging & WhatsApp Configuration")
        header_title.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {NAVY};")
        top_row.addWidget(header_title)
        top_row.addStretch()

        self.env_badge = QLabel("DEVELOPMENT (TEST SENDER)")
        self.env_badge.setStyleSheet(
            "background-color: #FEF3C7; color: #B45309; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 11px;"
        )
        top_row.addWidget(self.env_badge)
        main_layout.addLayout(top_row)

        # Tabs for Subsections
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {LIGHT_GOLD};
                background: {WHITE};
                border-radius: 6px;
            }}
            QTabBar::tab {{
                background: {CREAM};
                color: {TEXT};
                padding: 8px 16px;
                font-weight: 600;
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

        self.tabs.addTab(self._create_provider_tab(), "Provider & Credentials")
        self.tabs.addTab(self._create_templates_tab(), "Templates")
        self.tabs.addTab(self._create_automation_tab(), "Automation Rules")
        self.tabs.addTab(self._create_queue_settings_tab(), "Queue & Limits")
        self.tabs.addTab(self._create_diagnostics_tab(), "Diagnostics & Health")

        main_layout.addWidget(self.tabs, 1)

        # Bottom Action Bar
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(10)

        self.test_conn_btn = QPushButton("🔌 Test Connection")
        self.test_conn_btn.setStyleSheet(f"background-color: {CREAM}; color: {NAVY}; border: 1px solid {LIGHT_GOLD}; font-weight: 700; padding: 8px 16px; border-radius: 6px;")
        self.test_conn_btn.clicked.connect(self._on_test_connection)
        bottom_bar.addWidget(self.test_conn_btn)

        self.send_test_btn = QPushButton("📲 Send Test Message")
        self.send_test_btn.setStyleSheet(f"background-color: {CREAM}; color: {NAVY}; border: 1px solid {LIGHT_GOLD}; font-weight: 700; padding: 8px 16px; border-radius: 6px;")
        self.send_test_btn.clicked.connect(self._on_send_test_message)
        bottom_bar.addWidget(self.send_test_btn)

        bottom_bar.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.load_settings)
        bottom_bar.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setStyleSheet(f"background-color: {NAVY}; color: {WHITE}; font-weight: 700; padding: 8px 20px; border-radius: 6px;")
        self.save_btn.clicked.connect(self._on_save_settings)
        bottom_bar.addWidget(self.save_btn)

        main_layout.addLayout(bottom_bar)

    # ── TAB 1: PROVIDER & CREDENTIALS ─────────────────────────────────────────
    def _create_provider_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Environment Selector Box
        env_box = QGroupBox("Environment & Mode")
        env_box.setStyleSheet(f"QGroupBox {{ font-weight: 700; color: {NAVY}; }}")
        env_layout = QHBoxLayout(env_box)

        self.env_combo = QComboBox()
        self.env_combo.addItem("Development (Meta Test Sender Number)", "DEVELOPMENT")
        self.env_combo.addItem("Production (Sir's Verified WhatsApp Number)", "PRODUCTION")
        self.env_combo.currentIndexChanged.connect(self._on_env_changed)
        env_layout.addWidget(QLabel("Operating Environment:"))
        env_layout.addWidget(self.env_combo, 1)

        layout.addWidget(env_box)

        # Meta Cloud API Details
        form_box = QGroupBox("Meta WhatsApp Cloud API Configuration")
        form_box.setStyleSheet(f"QGroupBox {{ font-weight: 700; color: {NAVY}; }}")
        form = QFormLayout(form_box)
        form.setSpacing(12)

        self.phone_id_input = QLineEdit()
        self.phone_id_input.setPlaceholderText("e.g. 104829104810294")
        form.addRow("Phone Number ID:", self.phone_id_input)

        self.waba_id_input = QLineEdit()
        self.waba_id_input.setPlaceholderText("e.g. 192840192840192 (WABA ID)")
        form.addRow("WhatsApp Business Account ID:", self.waba_id_input)

        self.api_version_input = QLineEdit(DEFAULT_GRAPH_API_VERSION)
        form.addRow("Graph API Version:", self.api_version_input)

        layout.addWidget(form_box)

        # Credentials Box (Masked token display + Replace/Remove)
        cred_box = QGroupBox("Security & Access Token")
        cred_box.setStyleSheet(f"QGroupBox {{ font-weight: 700; color: {NAVY}; }}")
        c_layout = QVBoxLayout(cred_box)
        c_layout.setSpacing(10)

        token_row = QHBoxLayout()
        self.token_display_lbl = QLabel("Not Configured")
        self.token_display_lbl.setStyleSheet("font-family: monospace; font-size: 13px; color: #15803D; font-weight: 600;")
        token_row.addWidget(QLabel("Active Token:"))
        token_row.addWidget(self.token_display_lbl, 1)

        self.replace_token_btn = QPushButton("Replace Token")
        self.replace_token_btn.clicked.connect(self._on_replace_token)
        token_row.addWidget(self.replace_token_btn)

        self.remove_token_btn = QPushButton("Remove")
        self.remove_token_btn.setStyleSheet("color: #DC2626;")
        self.remove_token_btn.clicked.connect(self._on_remove_token)
        token_row.addWidget(self.remove_token_btn)

        c_layout.addLayout(token_row)

        self.new_token_input = QLineEdit()
        self.new_token_input.setPlaceholderText("Paste new Meta Temporary or System User Access Token here (EAAB...)")
        self.new_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_token_input.setVisible(False)
        c_layout.addWidget(self.new_token_input)

        token_hint = QLabel(
            "🔒 <i>Tokens are securely persisted with restricted OS file permissions (0600). "
            "Never committed, never logged in full, and never included in exports.</i>"
        )
        token_hint.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        c_layout.addWidget(token_hint)

        layout.addWidget(cred_box)
        layout.addStretch()
        return widget

    # ── TAB 2: TEMPLATES ──────────────────────────────────────────────────────
    def _create_templates_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        top_bar = QHBoxLayout()
        search_lbl = QLabel("Search:")
        self.template_search = QLineEdit()
        self.template_search.setPlaceholderText("Filter templates by name or trigger...")
        self.template_search.textChanged.connect(self._filter_templates)
        top_bar.addWidget(search_lbl)
        top_bar.addWidget(self.template_search, 1)

        self.add_tmpl_btn = QPushButton("➕ Add Template")
        self.add_tmpl_btn.setStyleSheet(f"background-color: {NAVY}; color: {WHITE}; font-weight: 600; padding: 6px 14px; border-radius: 6px;")
        self.add_tmpl_btn.clicked.connect(self._on_add_template)
        top_bar.addWidget(self.add_tmpl_btn)

        layout.addLayout(top_bar)

        self.templates_table = QTableWidget()
        self.templates_table.setColumnCount(7)
        self.templates_table.setHorizontalHeaderLabels([
            "Template Name", "Meta Name", "Category", "Trigger", "Meta Status", "Active", "Actions"
        ])
        configure_table_ux(
            self.templates_table,
            column_widths=[160, 160, 100, 130, 110, 70, 90],
            stretch_column=0,
        )
        layout.addWidget(self.templates_table, 1)

        return widget

    # ── TAB 3: AUTOMATION RULES ───────────────────────────────────────────────
    def _create_automation_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        info_lbl = QLabel(
            "<b>Notification Rules:</b> Automatically queue WhatsApp notifications on student events. "
            "All rules are <b>disabled by default</b> until explicitly checked below. "
            "Built-in cooldowns prevent duplicate messages upon restarts or multiple actions."
        )
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet(f"background-color: {CREAM}; padding: 10px; border: 1px solid {LIGHT_GOLD}; border-radius: 6px; font-size: 12px;")
        layout.addWidget(info_lbl)

        self.rules_table = QTableWidget()
        self.rules_table.setColumnCount(6)
        self.rules_table.setHorizontalHeaderLabels([
            "Rule Name", "Trigger Event", "Offset / Days", "Cooldown", "Enabled", "Template"
        ])
        configure_table_ux(
            self.rules_table,
            column_widths=[220, 140, 100, 90, 80, 180],
            stretch_column=0,
        )
        layout.addWidget(self.rules_table, 1)

        return widget

    # ── TAB 4: QUEUE SETTINGS ─────────────────────────────────────────────────
    def _create_queue_settings_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        form_box = QGroupBox("Queue Processing & Retry Policies")
        form_box.setStyleSheet(f"QGroupBox {{ font-weight: 700; color: {NAVY}; }}")
        form = QFormLayout(form_box)
        form.setSpacing(12)

        self.queue_enabled_cb = QCheckBox("Enable background message queue processing")
        form.addRow("Queue Active:", self.queue_enabled_cb)

        self.retry_limit_spin = QSpinBox()
        self.retry_limit_spin.setRange(1, 10)
        self.retry_limit_spin.setValue(3)
        form.addRow("Max Retry Attempts:", self.retry_limit_spin)

        self.backoff_base_spin = QSpinBox()
        self.backoff_base_spin.setRange(10, 600)
        self.backoff_base_spin.setValue(60)
        self.backoff_base_spin.setSuffix(" seconds")
        form.addRow("Exponential Backoff Base:", self.backoff_base_spin)

        self.polling_interval_spin = QSpinBox()
        self.polling_interval_spin.setRange(5, 120)
        self.polling_interval_spin.setValue(15)
        self.polling_interval_spin.setSuffix(" seconds")
        form.addRow("Worker Polling Interval:", self.polling_interval_spin)

        self.max_bulk_spin = QSpinBox()
        self.max_bulk_spin.setRange(10, 500)
        self.max_bulk_spin.setValue(100)
        form.addRow("Max Bulk Send Size:", self.max_bulk_spin)

        layout.addWidget(form_box)

        # Quiet Hours
        quiet_box = QGroupBox("Quiet Hours (Prevent Nighttime Sends)")
        quiet_box.setStyleSheet(f"QGroupBox {{ font-weight: 700; color: {NAVY}; }}")
        q_layout = QFormLayout(quiet_box)
        q_layout.setSpacing(10)

        self.quiet_hours_cb = QCheckBox("Pause sending during quiet hours")
        q_layout.addRow("Quiet Hours:", self.quiet_hours_cb)

        self.quiet_start_edit = QTimeEdit(QTime(22, 0))
        q_layout.addRow("Start Time:", self.quiet_start_edit)

        self.quiet_end_edit = QTimeEdit(QTime(7, 0))
        q_layout.addRow("End Time:", self.quiet_end_edit)

        layout.addWidget(quiet_box)
        layout.addStretch()
        return widget

    # ── TAB 5: DIAGNOSTICS & HEALTH ───────────────────────────────────────────
    def _create_diagnostics_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        diag_box = QGroupBox("Connection & Queue Health Summary")
        diag_box.setStyleSheet(f"QGroupBox {{ font-weight: 700; color: {NAVY}; }}")
        d_layout = QVBoxLayout(diag_box)

        self.diag_text = QTextEdit()
        self.diag_text.setReadOnly(True)
        self.diag_text.setStyleSheet(f"background-color: {CREAM}; font-family: monospace; font-size: 12px; border: 1px solid {LIGHT_GOLD}; border-radius: 6px;")
        d_layout.addWidget(self.diag_text)

        action_row = QHBoxLayout()
        self.refresh_diag_btn = QPushButton("🔄 Refresh Diagnostics")
        self.refresh_diag_btn.clicked.connect(self._refresh_diagnostics)
        action_row.addWidget(self.refresh_diag_btn)

        self.copy_diag_btn = QPushButton("📋 Copy Redacted Report")
        self.copy_diag_btn.clicked.connect(self._copy_diagnostics)
        action_row.addWidget(self.copy_diag_btn)

        action_row.addStretch()
        d_layout.addLayout(action_row)

        layout.addWidget(diag_box)

        # Webhook Architecture Notice
        hook_notice = QLabel(
            "<b>Webhook Notice:</b> TAMS runs as a local offline-first desktop application. "
            "To receive real-time delivery receipts (Delivered/Read marks), incoming Meta Webhooks require "
            "a secure public HTTPS reverse-proxy or cloud relay. Outgoing messaging is fully operational without webhooks."
        )
        hook_notice.setWordWrap(True)
        hook_notice.setStyleSheet(f"background-color: #EFF6FF; color: #1E40AF; padding: 10px; border-radius: 6px; font-size: 11px;")
        layout.addWidget(hook_notice)

        return widget

    # ─────────────────────────────────────────────────────────────────────────
    # LOAD & SAVE LOGIC
    # ─────────────────────────────────────────────────────────────────────────

    def load_settings(self):
        with SessionLocal() as session:
            ensure_messaging_seed_data(session)
            cfg = get_messaging_config(session)

            env = cfg.get("whatsapp_environment", "DEVELOPMENT")
            idx = self.env_combo.findData(env)
            if idx >= 0:
                self.env_combo.setCurrentIndex(idx)
            self._update_env_badge(env)

            self.phone_id_input.setText(cfg.get("whatsapp_phone_number_id", ""))
            self.waba_id_input.setText(cfg.get("whatsapp_waba_id", ""))
            self.api_version_input.setText(cfg.get("whatsapp_api_version", DEFAULT_GRAPH_API_VERSION))

            # Token display
            tok = get_access_token()
            self.token_display_lbl.setText(mask_token(tok))
            self.new_token_input.clear()
            self.new_token_input.setVisible(False)

            # Queue configs
            self.queue_enabled_cb.setChecked(cfg.get("queue_enabled", "true").lower() == "true")
            self.retry_limit_spin.setValue(int(cfg.get("retry_limit", "3")))
            self.backoff_base_spin.setValue(int(cfg.get("retry_backoff_base", "60")))
            self.polling_interval_spin.setValue(int(cfg.get("helper_polling_interval", "15")))
            self.max_bulk_spin.setValue(int(cfg.get("max_bulk_batch_size", "100")))

            # Quiet hours
            self.quiet_hours_cb.setChecked(cfg.get("quiet_hours_enabled", "false").lower() == "true")
            st_parts = [int(p) for p in cfg.get("quiet_hours_start", "22:00").split(":")]
            end_parts = [int(p) for p in cfg.get("quiet_hours_end", "07:00").split(":")]
            self.quiet_start_edit.setTime(QTime(st_parts[0], st_parts[1]))
            self.quiet_end_edit.setTime(QTime(end_parts[0], end_parts[1]))

            self._load_templates_table(session)
            self._load_rules_table(session)
            self._refresh_diagnostics()

    def _on_env_changed(self):
        env = self.env_combo.currentData()
        self._update_env_badge(env)

    def _update_env_badge(self, env: str):
        if env == "PRODUCTION":
            self.env_badge.setText("PRODUCTION (SIR'S LIVE NUMBER)")
            self.env_badge.setStyleSheet(
                "background-color: #DCFCE7; color: #15803D; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 11px;"
            )
        else:
            self.env_badge.setText("DEVELOPMENT (META TEST SENDER)")
            self.env_badge.setStyleSheet(
                "background-color: #FEF3C7; color: #B45309; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 11px;"
            )

    def _on_replace_token(self):
        self.new_token_input.setVisible(True)
        self.new_token_input.setFocus()

    def _on_remove_token(self):
        res = QMessageBox.question(
            self,
            "Remove Access Token",
            "Are you sure you want to remove the saved Meta access token?\n"
            "Outgoing messages will not be processed until a new token is entered.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if res == QMessageBox.StandardButton.Yes:
            remove_access_token()
            self.token_display_lbl.setText("Not Configured")
            self.new_token_input.clear()
            self.new_token_input.setVisible(False)
            QMessageBox.information(self, "Token Removed", "The WhatsApp access token has been removed.")

    def _on_save_settings(self):
        # Save new token if entered
        new_tok = self.new_token_input.text().strip()
        if new_tok:
            save_access_token(new_tok)
            self.token_display_lbl.setText(mask_token(new_tok))
            self.new_token_input.clear()
            self.new_token_input.setVisible(False)

        new_configs = {
            "whatsapp_environment": self.env_combo.currentData(),
            "whatsapp_phone_number_id": self.phone_id_input.text().strip(),
            "whatsapp_waba_id": self.waba_id_input.text().strip(),
            "whatsapp_api_version": self.api_version_input.text().strip() or DEFAULT_GRAPH_API_VERSION,
            "queue_enabled": "true" if self.queue_enabled_cb.isChecked() else "false",
            "retry_limit": str(self.retry_limit_spin.value()),
            "retry_backoff_base": str(self.backoff_base_spin.value()),
            "helper_polling_interval": str(self.polling_interval_spin.value()),
            "max_bulk_batch_size": str(self.max_bulk_spin.value()),
            "quiet_hours_enabled": "true" if self.quiet_hours_cb.isChecked() else "false",
            "quiet_hours_start": self.quiet_start_edit.time().toString("HH:mm"),
            "quiet_hours_end": self.quiet_end_edit.time().toString("HH:mm"),
        }

        with SessionLocal() as session:
            update_messaging_config(session, new_configs)

            # Save rules toggles
            for row in range(self.rules_table.rowCount()):
                rule_id = self.rules_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                cb: QCheckBox = self.rules_table.cellWidget(row, 4)
                if rule_id and cb:
                    r = session.get(NotificationRule, rule_id)
                    if r:
                        r.is_enabled = cb.isChecked()
            session.commit()

        QMessageBox.information(self, "Saved", "Messaging settings saved successfully!")
        self.load_settings()

    def _on_test_connection(self):
        # Temporarily use entered values if unsaved
        with SessionLocal() as session:
            provider = get_whatsapp_provider_client(session)
            # Override with current input fields
            new_tok = self.new_token_input.text().strip()
            if new_tok:
                provider.config.access_token = new_tok
            if self.phone_id_input.text().strip():
                provider.config.phone_number_id = self.phone_id_input.text().strip()
            if self.api_version_input.text().strip():
                provider.config.api_version = self.api_version_input.text().strip()
            provider.config.environment = self.env_combo.currentData()

            res = provider.test_connection()

        if res["success"]:
            QMessageBox.information(
                self,
                "Connection Successful",
                f"✅ <b>Meta WhatsApp API Connection Successful!</b>\n\n"
                f"Verified Name: {res.get('verified_name')}\n"
                f"Display Phone: {res.get('display_phone_number')}\n"
                f"Quality Rating: {res.get('quality_rating')}\n"
                f"Environment: {res.get('environment')}\n"
                f"Tested At: {res.get('tested_at')}",
            )
        else:
            QMessageBox.warning(
                self,
                "Connection Failed",
                f"❌ <b>Meta WhatsApp API Connection Test Failed:</b>\n\n"
                f"{res.get('error')}",
            )

    def _on_send_test_message(self):
        dlg = SendTestMessageDialog(self)
        dlg.exec()

    # ── TEMPLATES TABLE ───────────────────────────────────────────────────────
    def _load_templates_table(self, session: Session):
        tmpls = session.scalars(select(MessageTemplate).order_by(MessageTemplate.name.asc())).all()
        self._cached_templates = tmpls
        self._filter_templates()

    def _filter_templates(self):
        if not hasattr(self, "_cached_templates"):
            return
        query = self.template_search.text().strip().lower()
        filtered = [
            t for t in self._cached_templates
            if query in t.name.lower() or query in (t.associated_trigger or "").lower()
        ]

        self.templates_table.setRowCount(len(filtered))
        for row, t in enumerate(filtered):
            name_item = QTableWidgetItem(t.name)
            name_item.setData(Qt.ItemDataRole.UserRole, t.id)
            self.templates_table.setItem(row, 0, name_item)

            self.templates_table.setItem(row, 1, QTableWidgetItem(t.meta_template_name))
            self.templates_table.setItem(row, 2, QTableWidgetItem(t.category))
            self.templates_table.setItem(row, 3, QTableWidgetItem(t.associated_trigger or "MANUAL"))
            self.templates_table.setItem(row, 4, QTableWidgetItem(t.meta_status))

            act_item = QTableWidgetItem("Yes" if t.is_active else "No")
            act_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.templates_table.setItem(row, 5, act_item)

            edit_btn = QPushButton("Edit")
            edit_btn.setFixedSize(65, 26)
            edit_btn.setStyleSheet(f"background-color: {CREAM}; color: {NAVY}; border: 1px solid {LIGHT_GOLD}; font-size: 11px; border-radius: 4px;")
            edit_btn.clicked.connect(lambda checked=False, tid=t.id: self._edit_template(tid))
            self.templates_table.setCellWidget(row, 6, edit_btn)

    def _on_add_template(self):
        dlg = TemplateEditDialog(None, self)
        if dlg.exec():
            with SessionLocal() as session:
                self._load_templates_table(session)

    def _edit_template(self, template_id: int):
        dlg = TemplateEditDialog(template_id, self)
        if dlg.exec():
            with SessionLocal() as session:
                self._load_templates_table(session)

    # ── RULES TABLE ───────────────────────────────────────────────────────────
    def _load_rules_table(self, session: Session):
        rules = session.scalars(select(NotificationRule).order_by(NotificationRule.name.asc())).all()
        tmpls = {t.id: t.name for t in session.scalars(select(MessageTemplate)).all()}

        self.rules_table.setRowCount(len(rules))
        for row, r in enumerate(rules):
            name_item = QTableWidgetItem(r.name)
            name_item.setData(Qt.ItemDataRole.UserRole, r.id)
            self.rules_table.setItem(row, 0, name_item)

            self.rules_table.setItem(row, 1, QTableWidgetItem(r.trigger_event))

            offset_text = f"{r.days_offset} days" if r.days_offset != 0 else "Immediate"
            self.rules_table.setItem(row, 2, QTableWidgetItem(offset_text))

            self.rules_table.setItem(row, 3, QTableWidgetItem(f"{r.cooldown_days} days"))

            cb = QCheckBox()
            cb.setChecked(r.is_enabled)
            cb_container = QWidget()
            cb_layout = QHBoxLayout(cb_container)
            cb_layout.setContentsMargins(0, 0, 0, 0)
            cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb_layout.addWidget(cb)
            self.rules_table.setCellWidget(row, 4, cb_container)

            tmpl_name = tmpls.get(r.template_id, "—")
            self.rules_table.setItem(row, 5, QTableWidgetItem(tmpl_name))

    # ── DIAGNOSTICS REFRESH ───────────────────────────────────────────────────
    def _refresh_diagnostics(self):
        with SessionLocal() as session:
            cfg = get_messaging_config(session)
            tok = get_access_token()

            total_msgs = session.scalar(select(func.count(Message.id))) or 0
            queued_msgs = session.scalar(select(func.count(Message.id)).where(Message.status == "QUEUED")) or 0
            failed_msgs = session.scalar(select(func.count(Message.id)).where(Message.status == "FAILED")) or 0
            retry_msgs = session.scalar(select(func.count(Message.id)).where(Message.status == "RETRY_SCHEDULED")) or 0

            latest_msg = session.scalar(select(Message).order_by(Message.queued_at.desc()))
            last_event = latest_msg.queued_at.strftime("%Y-%m-%d %H:%M:%S UTC") if latest_msg else "None recorded"

            report = (
                f"=== TAMS Messaging System Diagnostics ===\n"
                f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
                f"Environment:            {cfg.get('whatsapp_environment', 'DEVELOPMENT')}\n"
                f"Graph API Version:      {cfg.get('whatsapp_api_version', DEFAULT_GRAPH_API_VERSION)}\n"
                f"Phone Number ID:        {cfg.get('whatsapp_phone_number_id', 'Not Set')}\n"
                f"WABA ID:                {cfg.get('whatsapp_waba_id', 'Not Set')}\n"
                f"Access Token Status:    {'Configured (' + mask_token(tok) + ')' if tok else 'MISSING'}\n\n"
                f"Queue Status:           {'ACTIVE' if cfg.get('queue_enabled') == 'true' else 'PAUSED'}\n"
                f"Total Messages Logged:  {total_msgs}\n"
                f"Currently Queued:       {queued_msgs}\n"
                f"Awaiting Retry:         {retry_msgs}\n"
                f"Failed Messages:        {failed_msgs}\n"
                f"Last Message Event:     {last_event}\n"
            )
            self.diag_text.setText(report)

    def _copy_diagnostics(self):
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.diag_text.toPlainText())
            QMessageBox.information(self, "Copied", "Redacted diagnostic report copied to clipboard.")
