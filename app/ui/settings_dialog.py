import json
import logging
from datetime import datetime, time, timezone
from pathlib import Path
from PyQt6.QtCore import QObject, QThread, Qt, QTime, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QDesktopServices


from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select
from app.database.connection import DATABASE_PATH, DATA_DIR, SessionLocal
from app.database.models.batch import Batch
from app.database.models.message import (
    Message,
    MessageTemplate,
    MessagingConfig,
    NotificationRule,
)
from app.services.backup_service import (
    create_database_backup,
    get_backup_directory,
    list_backups,
    restore_database_backup,
)
from app.services.batch_service import (
    create_batch,
    get_active_batches,
    update_batch,
    deactivate_batch,
    reactivate_batch,
    get_batch,
)
from app.services.coaching_helper_service import (
    check_for_updates,
    get_helper_status_file_path,
)
from app.services.messaging_service import (
    ensure_messaging_seed_data,
    get_messaging_config,
    get_whatsapp_provider_client,
    update_messaging_config,
)
from app.services.whatsapp_provider import (
    DEFAULT_GRAPH_API_VERSION,
    WhatsAppCloudProvider,
    get_access_token,
    mask_token,
    remove_access_token,
    save_access_token,
)
from app.ui.messaging_settings_widget import MessagingSettingsWidget, SendTestMessageDialog
from app.ui.table_utils import configure_table_ux



NAVY = "#012D54"
DARK_NAVY = "#04294D"
GOLD = "#D9B85F"
LIGHT_GOLD = "#E9DEBA"
CREAM = "#F8F6EA"
WHITE = "#FEFEFE"
TEXT = "#1F2937"
MUTED = "#615F4B"
class TAMSTimeEdit(QTimeEdit):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )

        self.setFixedHeight(42)

        self.up_button = QPushButton("▲", self)
        self.down_button = QPushButton("▼", self)

        self.up_button.setObjectName("timeArrowButton")
        self.down_button.setObjectName("timeArrowButton")

        self.up_button.clicked.connect(self.increase_time)
        self.down_button.clicked.connect(self.decrease_time)

        self.update_arrow_positions()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_arrow_positions()

    def update_arrow_positions(self):
        width = 24

        self.up_button.setGeometry(
            self.width() - width,
            2,
            width,
            (self.height() - 4) // 2,
        )

        self.down_button.setGeometry(
            self.width() - width,
            self.height() // 2,
            width,
            (self.height() - 4) // 2,
        )

    def increase_time(self):
        self.setTime(self.time().addSecs(15 * 60))

    def decrease_time(self):
        self.setTime(self.time().addSecs(-15 * 60))


# ─────────────────────────────────────────────────────────────────────────────
# BACKGROUND WORKER THREADS (QThread for non-blocking operations)
# ─────────────────────────────────────────────────────────────────────────────

class WhatsAppTestWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, config_kwargs: dict, parent=None):
        super().__init__(parent)
        self.config_kwargs = config_kwargs

    def run(self):
        try:
            with SessionLocal() as session:
                provider = get_whatsapp_provider_client(session)
                if self.config_kwargs.get("access_token"):
                    provider.config.access_token = self.config_kwargs["access_token"]
                if self.config_kwargs.get("phone_number_id"):
                    provider.config.phone_number_id = self.config_kwargs["phone_number_id"]
                if self.config_kwargs.get("api_version"):
                    provider.config.api_version = self.config_kwargs["api_version"]
                if self.config_kwargs.get("environment"):
                    provider.config.environment = self.config_kwargs["environment"]
                res = provider.test_connection()
        except Exception as e:
            res = {"success": False, "error": str(e)}
        self.finished.emit(res)


class BackupWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, custom_label: str | None, max_retention: int = 10, parent=None):
        super().__init__(parent)
        self.custom_label = custom_label
        self.max_retention = max_retention

    def run(self):
        try:
            res = create_database_backup(custom_label=self.custom_label, max_retention=self.max_retention)
        except Exception as e:
            res = {"success": False, "error": str(e)}
        self.finished.emit(res)


class RestoreWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, backup_file: Path | str, parent=None):
        super().__init__(parent)
        self.backup_file = backup_file

    def run(self):
        try:
            res = restore_database_backup(self.backup_file)
        except Exception as e:
            res = {"success": False, "error": str(e)}
        self.finished.emit(res)


class DbMaintenanceWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, action: str = "integrity_check", parent=None):
        super().__init__(parent)
        self.action = action

    def run(self):
        import sqlite3
        res = {"action": self.action, "success": True, "message": ""}
        try:
            conn = sqlite3.connect(str(DATABASE_PATH), timeout=30.0)
            cur = conn.cursor()
            if self.action == "integrity_check":
                cur.execute("PRAGMA integrity_check")
                row = cur.fetchone()
                msg = row[0] if row else "Unknown result"
                res["message"] = f"Integrity Check: {msg}"
                res["success"] = (msg == "ok")
            elif self.action == "vacuum":
                cur.execute("VACUUM")
                cur.execute("PRAGMA optimize")
                conn.commit()
                res["message"] = "Database vacuumed and index statistics optimized."
            conn.close()
        except Exception as e:
            res["success"] = False
            res["message"] = str(e)
        self.finished.emit(res)


class UpdateCheckWorker(QThread):
    finished = pyqtSignal(dict)

    def run(self):
        try:
            res = check_for_updates()
        except Exception as e:
            res = {"status": "error", "message": str(e)}
        self.finished.emit(res)


class SettingsDialog(QDialog):

    def __init__(self, parent=None, initial_tab: int = 0):
        super().__init__(parent)

        self.setWindowTitle("TAMS Settings")
        self.resize(950, 680)

        self.setup_ui()
        self.apply_styles()
        if initial_tab > 0 and initial_tab < self.settings_menu.count():
            self.settings_menu.setCurrentRow(initial_tab)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setObjectName("settingsHeader")

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 16, 20, 16)

        title = QLabel("Settings")
        title.setObjectName("settingsTitle")

        subtitle = QLabel("Manage your TAMS configuration")
        subtitle.setObjectName("settingsSubtitle")

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)

        close_button = QPushButton("×")
        close_button.setObjectName("closeButton")
        close_button.setFixedSize(38, 38)
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.clicked.connect(self.close)

        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        header_layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignVCenter)

        main_layout.addWidget(header)

        # Body
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("settingsSidebar")
        sidebar.setFixedWidth(220)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 20, 12, 20)
        sidebar_layout.setSpacing(6)

        self.settings_menu = QListWidget()
        self.settings_menu.setObjectName("settingsMenu")

        items = [
            ("⚙", "General"),
            ("▣", "Batches"),
            ("◈", "WhatsApp"),
            ("⚡", "Automation"),
            ("◫", "Backup"),
        ]

        for icon, name in items:
            item = QListWidgetItem(f"  {icon}    {name}")
            item.setSizeHint(item.sizeHint())
            self.settings_menu.addItem(item)

        self.settings_menu.setCurrentRow(0)

        sidebar_layout.addWidget(self.settings_menu)
        sidebar_layout.addStretch()

        body_layout.addWidget(sidebar)

        # Content
        self.pages = QStackedWidget()
        self.pages.setObjectName("settingsPages")

        self.pages.addWidget(self.create_general_page())
        self.pages.addWidget(self.create_batches_page())
        self.pages.addWidget(self.create_whatsapp_page())
        self.pages.addWidget(self.create_automation_page())
        self.pages.addWidget(self.create_backup_page())

        body_layout.addWidget(self.pages)

        self.settings_menu.currentRowChanged.connect(
            self.pages.setCurrentIndex
        )

        main_layout.addWidget(body)
        self.load_batches()
        self.load_whatsapp_settings()
        self.load_automation_settings()
        self.load_backup_page()

    def create_general_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(35, 30, 35, 30)
        layout.setSpacing(12)

        title = QLabel("General")
        title.setObjectName("pageTitle")

        description = QLabel(
            "Basic settings for your coaching management system."
        )
        description.setObjectName("pageDescription")

        layout.addWidget(title)
        layout.addWidget(description)

        card = QFrame()
        card.setObjectName("settingsCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)

        label = QLabel("Coaching details")
        label.setObjectName("cardTitle")

        info = QLabel(
            "Coaching name, address, academic year and other "
            "general information can be configured here."
        )
        info.setWordWrap(True)
        info.setObjectName("cardText")

        card_layout.addWidget(label)
        card_layout.addWidget(info)

        layout.addWidget(card)
        layout.addStretch()

        return page

    def create_batches_page(self):
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(35, 30, 35, 30)
        layout.setSpacing(12)

        title = QLabel("Batch Management")
        title.setObjectName("pageTitle")

        description = QLabel(
            "Create and manage the batches used by your coaching."
        )
        description.setObjectName("pageDescription")

        layout.addWidget(title)
        layout.addWidget(description)

        # Batch list card
        card = QFrame()
        card.setObjectName("settingsCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(12)

        header_layout = QHBoxLayout()

        label = QLabel("Your batches")
        label.setObjectName("cardTitle")

        header_layout.addWidget(label)
        header_layout.addStretch()

        add_button = QPushButton("+  Add Batch")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self.open_add_batch_dialog)

        header_layout.addWidget(add_button)

        card_layout.addLayout(header_layout)

        self.batch_list_container = QWidget()
        self.batch_list_layout = QVBoxLayout(self.batch_list_container)
        self.batch_list_layout.setContentsMargins(0, 5, 0, 5)
        self.batch_list_layout.setSpacing(10)
        self.batch_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMaximumHeight(350)
        scroll.setMinimumHeight(120)
        scroll.setWidget(self.batch_list_container)

        card_layout.addWidget(scroll)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }

        """

        )

        layout.addWidget(card, 1)
        inactive_card = QFrame()
        inactive_card.setObjectName("settingsCard")

        inactive_layout = QVBoxLayout(inactive_card)
        inactive_layout.setContentsMargins(20, 20, 20, 20)
        inactive_layout.setSpacing(12)

        inactive_header = QHBoxLayout()

        inactive_title = QLabel("Deactivated batches")
        inactive_title.setObjectName("cardTitle")

        inactive_header.addWidget(inactive_title)
        inactive_header.addStretch()

        inactive_layout.addLayout(inactive_header)

        self.inactive_batch_list_container = QWidget()

        self.inactive_batch_list_layout = QVBoxLayout(
            self.inactive_batch_list_container
        )
        self.inactive_batch_list_layout.setContentsMargins(0, 5, 0, 5)
        self.inactive_batch_list_layout.setSpacing(10)
        self.inactive_batch_list_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop
        )

        inactive_scroll = QScrollArea()
        inactive_scroll.setWidgetResizable(True)
        inactive_scroll.setFrameShape(QFrame.Shape.NoFrame)
        inactive_scroll.setMaximumHeight(250)
        inactive_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }

            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
        """)

        inactive_scroll.setWidget(
            self.inactive_batch_list_container
        )

        inactive_layout.addWidget(inactive_scroll)

        layout.addWidget(inactive_card)

        return page
    
    # ── TAB 2: WHATSAPP CLOUD API CONFIGURATION ─────────────────────────────
    def create_whatsapp_page(self):
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; } QScrollArea > QWidget > QWidget { background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(35, 30, 35, 30)
        layout.setSpacing(16)

        title = QLabel("WhatsApp Cloud API")
        title.setObjectName("pageTitle")
        description = QLabel("Configure Meta Cloud API credentials, test connections, and manage access tokens.")
        description.setObjectName("pageDescription")
        layout.addWidget(title)
        layout.addWidget(description)

        # 1. Environment Card
        env_card = QFrame()
        env_card.setObjectName("settingsCard")
        env_card_layout = QVBoxLayout(env_card)
        env_card_layout.setContentsMargins(20, 18, 20, 18)
        env_card_layout.setSpacing(10)

        env_header = QHBoxLayout()
        env_title = QLabel("Operating Environment & Mode")
        env_title.setObjectName("cardTitle")
        env_header.addWidget(env_title)
        env_header.addStretch()

        self.wa_env_badge = QLabel("DEVELOPMENT")
        self.wa_env_badge.setStyleSheet(
            "background-color: #FEF3C7; color: #B45309; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 11px;"
        )
        env_header.addWidget(self.wa_env_badge)
        env_card_layout.addLayout(env_header)

        env_row = QHBoxLayout()
        env_row.addWidget(QLabel("Current Mode:"))
        self.wa_env_combo = QComboBox()
        self.wa_env_combo.addItem("Development (Meta Test Sender Number)", "DEVELOPMENT")
        self.wa_env_combo.addItem("Production (Sir's Verified WhatsApp Number)", "PRODUCTION")
        self.wa_env_combo.currentIndexChanged.connect(self._on_whatsapp_env_changed)
        env_row.addWidget(self.wa_env_combo, 1)
        env_card_layout.addLayout(env_row)

        env_hint = QLabel("💡 In Development Mode, messages can only be delivered to phone numbers registered under 'To' in Meta WhatsApp dashboard.")
        env_hint.setWordWrap(True)
        env_hint.setObjectName("cardText")
        env_card_layout.addWidget(env_hint)
        layout.addWidget(env_card)

        # 2. Meta API Credentials Card
        cred_card = QFrame()
        cred_card.setObjectName("settingsCard")
        cred_layout = QVBoxLayout(cred_card)
        cred_layout.setContentsMargins(20, 18, 20, 18)
        cred_layout.setSpacing(12)

        cred_title = QLabel("Meta WhatsApp Cloud API Credentials")
        cred_title.setObjectName("cardTitle")
        cred_layout.addWidget(cred_title)

        form = QFormLayout()
        form.setSpacing(10)
        self.wa_phone_id_input = QLineEdit()
        self.wa_phone_id_input.setPlaceholderText("e.g. 104829104810294")
        form.addRow("Phone Number ID:", self.wa_phone_id_input)

        self.wa_waba_id_input = QLineEdit()
        self.wa_waba_id_input.setPlaceholderText("e.g. 192840192840192 (WABA ID)")
        form.addRow("Business Account ID (WABA):", self.wa_waba_id_input)

        self.wa_api_version_input = QLineEdit(DEFAULT_GRAPH_API_VERSION)
        form.addRow("Graph API Version:", self.wa_api_version_input)
        cred_layout.addLayout(form)
        layout.addWidget(cred_card)

        # 3. Security & Access Token Card
        token_card = QFrame()
        token_card.setObjectName("settingsCard")
        tok_layout = QVBoxLayout(token_card)
        tok_layout.setContentsMargins(20, 18, 20, 18)
        tok_layout.setSpacing(10)

        tok_title = QLabel("Security & Access Token")
        tok_title.setObjectName("cardTitle")
        tok_layout.addWidget(tok_title)

        tok_row = QHBoxLayout()
        tok_row.addWidget(QLabel("Stored Token:"))
        self.wa_token_display_lbl = QLabel("Not Configured")
        self.wa_token_display_lbl.setStyleSheet("font-family: monospace; font-size: 13px; color: #15803D; font-weight: 600;")
        tok_row.addWidget(self.wa_token_display_lbl, 1)

        self.wa_replace_token_btn = QPushButton("Replace Token")
        self.wa_replace_token_btn.clicked.connect(self._on_wa_replace_token)
        tok_row.addWidget(self.wa_replace_token_btn)

        self.wa_remove_token_btn = QPushButton("Remove")
        self.wa_remove_token_btn.setObjectName("dangerButton")
        self.wa_remove_token_btn.clicked.connect(self._on_wa_remove_token)
        tok_row.addWidget(self.wa_remove_token_btn)
        tok_layout.addLayout(tok_row)

        self.wa_new_token_input = QLineEdit()
        self.wa_new_token_input.setPlaceholderText("Paste Meta System User Access Token here (EAAB...)")
        self.wa_new_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.wa_new_token_input.setVisible(False)
        tok_layout.addWidget(self.wa_new_token_input)

        tok_hint = QLabel("🔒 Tokens are securely persisted in local OS storage with restricted permissions (0600) and never exported.")
        tok_hint.setObjectName("cardText")
        tok_layout.addWidget(tok_hint)
        layout.addWidget(token_card)

        # 4. Action Buttons
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(10)

        self.wa_test_conn_btn = QPushButton("🔌 Test Connection")
        self.wa_test_conn_btn.clicked.connect(self._on_wa_test_connection)
        btn_bar.addWidget(self.wa_test_conn_btn)

        self.wa_send_test_btn = QPushButton("📲 Send Test Message")
        self.wa_send_test_btn.clicked.connect(self._on_wa_send_test_message)
        btn_bar.addWidget(self.wa_send_test_btn)

        btn_bar.addStretch()

        self.wa_cancel_btn = QPushButton("Revert")
        self.wa_cancel_btn.clicked.connect(self.load_whatsapp_settings)
        btn_bar.addWidget(self.wa_cancel_btn)

        self.wa_save_btn = QPushButton("Save WhatsApp Settings")
        self.wa_save_btn.setObjectName("primaryButton")
        self.wa_save_btn.clicked.connect(self._on_save_whatsapp_settings)
        btn_bar.addWidget(self.wa_save_btn)

        layout.addLayout(btn_bar)
        layout.addStretch()

        scroll.setWidget(container)
        outer_layout = QVBoxLayout(page)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)
        return page

    def load_whatsapp_settings(self):
        with SessionLocal() as session:
            ensure_messaging_seed_data(session)
            cfg = get_messaging_config(session)

            env = cfg.get("whatsapp_environment", "DEVELOPMENT")
            idx = self.wa_env_combo.findData(env)
            if idx >= 0:
                self.wa_env_combo.setCurrentIndex(idx)
            self._on_whatsapp_env_changed()

            self.wa_phone_id_input.setText(cfg.get("whatsapp_phone_number_id", ""))
            self.wa_waba_id_input.setText(cfg.get("whatsapp_waba_id", ""))
            self.wa_api_version_input.setText(cfg.get("whatsapp_api_version", DEFAULT_GRAPH_API_VERSION))

            tok = get_access_token()
            self.wa_token_display_lbl.setText(mask_token(tok))
            self.wa_new_token_input.clear()
            self.wa_new_token_input.setVisible(False)

    def _on_whatsapp_env_changed(self):
        env = self.wa_env_combo.currentData()
        if env == "PRODUCTION":
            self.wa_env_badge.setText("PRODUCTION (LIVE NUMBER)")
            self.wa_env_badge.setStyleSheet(
                "background-color: #DCFCE7; color: #15803D; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 11px;"
            )
        else:
            self.wa_env_badge.setText("DEVELOPMENT (META TEST SENDER)")
            self.wa_env_badge.setStyleSheet(
                "background-color: #FEF3C7; color: #B45309; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 11px;"
            )

    def _on_wa_replace_token(self):
        self.wa_new_token_input.setVisible(True)
        self.wa_new_token_input.setFocus()

    def _on_wa_remove_token(self):
        res = QMessageBox.question(
            self,
            "Remove Access Token",
            "Are you sure you want to remove the stored Meta access token?\n"
            "WhatsApp messaging will be disabled until a new token is entered.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if res == QMessageBox.StandardButton.Yes:
            remove_access_token()
            self.wa_token_display_lbl.setText("Not Configured")
            self.wa_new_token_input.clear()
            self.wa_new_token_input.setVisible(False)
            QMessageBox.information(self, "Token Removed", "WhatsApp access token has been removed.")

    def _on_wa_test_connection(self):
        with SessionLocal() as session:
            provider = get_whatsapp_provider_client(session)
            new_tok = self.wa_new_token_input.text().strip()
            if new_tok:
                provider.config.access_token = new_tok
            if self.wa_phone_id_input.text().strip():
                provider.config.phone_number_id = self.wa_phone_id_input.text().strip()
            if self.wa_api_version_input.text().strip():
                provider.config.api_version = self.wa_api_version_input.text().strip()
            provider.config.environment = self.wa_env_combo.currentData()

            res = provider.test_connection()

        if res.get("success"):
            QMessageBox.information(
                self,
                "Connection Successful",
                f"✅ Meta WhatsApp Cloud API Connection Successful!\n\n"
                f"Verified Name: {res.get('verified_name')}\n"
                f"Display Phone: {res.get('display_phone_number')}\n"
                f"Quality Rating: {res.get('quality_rating')}\n"
                f"Environment: {res.get('environment')}",
            )
        else:
            QMessageBox.warning(
                self,
                "Connection Failed",
                f"❌ Meta WhatsApp Cloud API Test Failed:\n\n{res.get('error')}",
            )

    def _on_wa_send_test_message(self):
        dlg = SendTestMessageDialog(self)
        dlg.exec()

    def _on_save_whatsapp_settings(self):
        new_tok = self.wa_new_token_input.text().strip()
        if new_tok:
            save_access_token(new_tok)
            self.wa_token_display_lbl.setText(mask_token(new_tok))
            self.wa_new_token_input.clear()
            self.wa_new_token_input.setVisible(False)

        new_configs = {
            "whatsapp_environment": self.wa_env_combo.currentData(),
            "whatsapp_phone_number_id": self.wa_phone_id_input.text().strip(),
            "whatsapp_waba_id": self.wa_waba_id_input.text().strip(),
            "whatsapp_api_version": self.wa_api_version_input.text().strip() or DEFAULT_GRAPH_API_VERSION,
        }

        with SessionLocal() as session:
            update_messaging_config(session, new_configs)

        QMessageBox.information(self, "Saved", "WhatsApp settings saved successfully!")
        self.load_whatsapp_settings()

    # ── TAB 3: AUTOMATION & QUEUE SETTINGS ─────────────────────────────────────
    def create_automation_page(self):
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; } QScrollArea > QWidget > QWidget { background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(35, 30, 35, 30)
        layout.setSpacing(16)

        title = QLabel("Automation & Queue Policies")
        title.setObjectName("pageTitle")
        description = QLabel("Configure background queue processing, retry backoff, quiet hours, and event-based notification rules.")
        description.setObjectName("pageDescription")
        layout.addWidget(title)
        layout.addWidget(description)

        # 1. Queue & Retry Card
        q_card = QFrame()
        q_card.setObjectName("settingsCard")
        q_layout = QVBoxLayout(q_card)
        q_layout.setContentsMargins(20, 18, 20, 18)
        q_layout.setSpacing(12)

        q_title = QLabel("Background Queue & Retry Policies")
        q_title.setObjectName("cardTitle")
        q_layout.addWidget(q_title)

        form = QFormLayout()
        form.setSpacing(10)

        self.auto_queue_enabled_cb = QCheckBox("Enable background message queue processing")
        form.addRow("Queue Active:", self.auto_queue_enabled_cb)

        self.auto_retry_limit_spin = QSpinBox()
        self.auto_retry_limit_spin.setRange(1, 10)
        self.auto_retry_limit_spin.setValue(3)
        form.addRow("Max Retry Attempts:", self.auto_retry_limit_spin)

        self.auto_backoff_base_spin = QSpinBox()
        self.auto_backoff_base_spin.setRange(10, 600)
        self.auto_backoff_base_spin.setValue(60)
        self.auto_backoff_base_spin.setSuffix(" seconds")
        form.addRow("Exponential Backoff Base:", self.auto_backoff_base_spin)

        self.auto_polling_interval_spin = QSpinBox()
        self.auto_polling_interval_spin.setRange(5, 120)
        self.auto_polling_interval_spin.setValue(15)
        self.auto_polling_interval_spin.setSuffix(" seconds")
        form.addRow("Companion Polling Interval:", self.auto_polling_interval_spin)

        self.auto_max_bulk_spin = QSpinBox()
        self.auto_max_bulk_spin.setRange(10, 500)
        self.auto_max_bulk_spin.setValue(100)
        form.addRow("Max Bulk Batch Size:", self.auto_max_bulk_spin)
        q_layout.addLayout(form)
        layout.addWidget(q_card)

        # 2. Quiet Hours Card
        qh_card = QFrame()
        qh_card.setObjectName("settingsCard")
        qh_layout = QVBoxLayout(qh_card)
        qh_layout.setContentsMargins(20, 18, 20, 18)
        qh_layout.setSpacing(10)

        qh_title = QLabel("Quiet Hours (Nighttime Safety)")
        qh_title.setObjectName("cardTitle")
        qh_layout.addWidget(qh_title)

        qh_form = QFormLayout()
        qh_form.setSpacing(10)
        self.auto_quiet_hours_cb = QCheckBox("Pause message dispatching during quiet hours")
        qh_form.addRow("Quiet Hours Active:", self.auto_quiet_hours_cb)

        self.auto_quiet_start_edit = QTimeEdit(QTime(22, 0))
        qh_form.addRow("Start Time:", self.auto_quiet_start_edit)

        self.auto_quiet_end_edit = QTimeEdit(QTime(7, 0))
        qh_form.addRow("End Time:", self.auto_quiet_end_edit)
        qh_layout.addLayout(qh_form)

        qh_hint = QLabel("🌙 Outgoing messages queued during quiet hours will hold in the queue and automatically dispatch once quiet hours conclude.")
        qh_hint.setWordWrap(True)
        qh_hint.setObjectName("cardText")
        qh_layout.addWidget(qh_hint)
        layout.addWidget(qh_card)

        # 3. Notification Rules Card
        rules_card = QFrame()
        rules_card.setObjectName("settingsCard")
        r_layout = QVBoxLayout(rules_card)
        r_layout.setContentsMargins(20, 18, 20, 18)
        r_layout.setSpacing(10)

        r_title = QLabel("Event Notification Rules")
        r_title.setObjectName("cardTitle")
        r_layout.addWidget(r_title)

        r_hint = QLabel("Enable or disable automatic trigger notifications for attendance, fees, and test results.")
        r_hint.setObjectName("cardText")
        r_layout.addWidget(r_hint)

        self.auto_rules_table = QTableWidget()
        self.auto_rules_table.setColumnCount(5)
        self.auto_rules_table.setHorizontalHeaderLabels([
            "Rule Name", "Trigger Event", "Cooldown", "Enabled", "Template"
        ])
        configure_table_ux(
            self.auto_rules_table,
            column_widths=[220, 140, 100, 80, 180],
            stretch_column=0,
            default_row_height=38,
        )
        self.auto_rules_table.setMinimumHeight(180)
        r_layout.addWidget(self.auto_rules_table)
        layout.addWidget(rules_card)

        # Action Buttons
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()

        self.auto_cancel_btn = QPushButton("Revert")
        self.auto_cancel_btn.clicked.connect(self.load_automation_settings)
        btn_bar.addWidget(self.auto_cancel_btn)

        self.auto_save_btn = QPushButton("Save Automation Settings")
        self.auto_save_btn.setObjectName("primaryButton")
        self.auto_save_btn.clicked.connect(self._on_save_automation_settings)
        btn_bar.addWidget(self.auto_save_btn)

        layout.addLayout(btn_bar)
        layout.addStretch()

        scroll.setWidget(container)
        outer_layout = QVBoxLayout(page)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)
        return page

    def load_automation_settings(self):
        with SessionLocal() as session:
            ensure_messaging_seed_data(session)
            cfg = get_messaging_config(session)

            self.auto_queue_enabled_cb.setChecked(cfg.get("queue_enabled", "true").lower() == "true")
            self.auto_retry_limit_spin.setValue(int(cfg.get("retry_limit", "3")))
            self.auto_backoff_base_spin.setValue(int(cfg.get("retry_backoff_base", "60")))
            self.auto_polling_interval_spin.setValue(int(cfg.get("helper_polling_interval", "15")))
            self.auto_max_bulk_spin.setValue(int(cfg.get("max_bulk_batch_size", "100")))

            self.auto_quiet_hours_cb.setChecked(cfg.get("quiet_hours_enabled", "false").lower() == "true")
            st_parts = [int(p) for p in cfg.get("quiet_hours_start", "22:00").split(":")]
            end_parts = [int(p) for p in cfg.get("quiet_hours_end", "07:00").split(":")]
            self.auto_quiet_start_edit.setTime(QTime(st_parts[0], st_parts[1]))
            self.auto_quiet_end_edit.setTime(QTime(end_parts[0], end_parts[1]))

            # Load notification rules
            rules = session.scalars(select(NotificationRule).order_by(NotificationRule.name.asc())).all()
            tmpls = {t.id: t.name for t in session.scalars(select(MessageTemplate)).all()}
            self.auto_rules_table.setRowCount(len(rules))
            for row, r in enumerate(rules):
                name_item = QTableWidgetItem(r.name)
                name_item.setData(Qt.ItemDataRole.UserRole, r.id)
                self.auto_rules_table.setItem(row, 0, name_item)
                self.auto_rules_table.setItem(row, 1, QTableWidgetItem(r.trigger_event))
                self.auto_rules_table.setItem(row, 2, QTableWidgetItem(f"{r.cooldown_days} days"))

                cb = QCheckBox()
                cb.setChecked(bool(r.is_enabled))
                cb_container = QWidget()
                cb_layout = QHBoxLayout(cb_container)
                cb_layout.setContentsMargins(0, 0, 0, 0)
                cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cb_layout.addWidget(cb)
                self.auto_rules_table.setCellWidget(row, 3, cb_container)

                tmpl_name = tmpls.get(r.template_id, "—")
                self.auto_rules_table.setItem(row, 4, QTableWidgetItem(tmpl_name))

    def _on_save_automation_settings(self):
        new_configs = {
            "queue_enabled": "true" if self.auto_queue_enabled_cb.isChecked() else "false",
            "retry_limit": str(self.auto_retry_limit_spin.value()),
            "retry_backoff_base": str(self.auto_backoff_base_spin.value()),
            "helper_polling_interval": str(self.auto_polling_interval_spin.value()),
            "max_bulk_batch_size": str(self.auto_max_bulk_spin.value()),
            "quiet_hours_enabled": "true" if self.auto_quiet_hours_cb.isChecked() else "false",
            "quiet_hours_start": self.auto_quiet_start_edit.time().toString("HH:mm"),
            "quiet_hours_end": self.auto_quiet_end_edit.time().toString("HH:mm"),
        }

        with SessionLocal() as session:
            update_messaging_config(session, new_configs)

            for row in range(self.auto_rules_table.rowCount()):
                item = self.auto_rules_table.item(row, 0)
                if item:
                    rule_id = item.data(Qt.ItemDataRole.UserRole)
                    cb_container = self.auto_rules_table.cellWidget(row, 3)
                    cb = cb_container.findChild(QCheckBox) if cb_container else None
                    if rule_id and cb:
                        r = session.get(NotificationRule, rule_id)
                        if r:
                            r.is_enabled = cb.isChecked()
            session.commit()

        QMessageBox.information(self, "Saved", "Automation settings saved successfully!")
        self.load_automation_settings()

    # ── TAB 4: BACKUP & SYSTEM MAINTENANCE ─────────────────────────────────────
    def create_backup_page(self):
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; } QScrollArea > QWidget > QWidget { background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(35, 30, 35, 30)
        layout.setSpacing(16)

        title = QLabel("Backup & Maintenance")
        title.setObjectName("pageTitle")
        description = QLabel("Database backup snapshots, integrity verification, companion service health, and software updates.")
        description.setObjectName("pageDescription")
        layout.addWidget(title)
        layout.addWidget(description)

        # 1. Database & Companion Info Card
        info_card = QFrame()
        info_card.setObjectName("settingsCard")
        i_layout = QVBoxLayout(info_card)
        i_layout.setContentsMargins(20, 18, 20, 18)
        i_layout.setSpacing(10)

        i_title = QLabel("Database & Companion Service Status")
        i_title.setObjectName("cardTitle")
        i_layout.addWidget(i_title)

        form = QFormLayout()
        form.setSpacing(8)

        self.backup_db_path_lbl = QLabel(str(DATABASE_PATH))
        self.backup_db_path_lbl.setStyleSheet("font-family: monospace; font-size: 11px;")
        form.addRow("Database Path:", self.backup_db_path_lbl)

        self.backup_db_size_lbl = QLabel("—")
        form.addRow("Database Size:", self.backup_db_size_lbl)

        self.helper_status_lbl = QLabel("Checking...")
        self.helper_status_lbl.setStyleSheet("font-weight: 600; color: #15803D;")
        form.addRow("CoachingHelper Service:", self.helper_status_lbl)
        i_layout.addLayout(form)
        layout.addWidget(info_card)

        # 2. Create Backup Card
        create_card = QFrame()
        create_card.setObjectName("settingsCard")
        c_layout = QVBoxLayout(create_card)
        c_layout.setContentsMargins(20, 18, 20, 18)
        c_layout.setSpacing(10)

        c_title = QLabel("Create Database Backup")
        c_title.setObjectName("cardTitle")
        c_layout.addWidget(c_title)

        c_row = QHBoxLayout()
        self.backup_label_input = QLineEdit()
        self.backup_label_input.setPlaceholderText("Optional label, e.g. pre_exam_results or month_end")
        c_row.addWidget(self.backup_label_input, 1)

        self.create_backup_btn = QPushButton("💾 Create Backup Now")
        self.create_backup_btn.setObjectName("primaryButton")
        self.create_backup_btn.clicked.connect(self._on_create_backup_clicked)
        c_row.addWidget(self.create_backup_btn)
        c_layout.addLayout(c_row)

        c_hint = QLabel("🛡 Backups are generated using SQLite online backup API with transaction consistency and automatic integrity verification.")
        c_hint.setObjectName("cardText")
        c_layout.addWidget(c_hint)
        layout.addWidget(create_card)

        # 3. Existing Backups Card
        list_card = QFrame()
        list_card.setObjectName("settingsCard")
        l_layout = QVBoxLayout(list_card)
        l_layout.setContentsMargins(20, 18, 20, 18)
        l_layout.setSpacing(10)

        l_header = QHBoxLayout()
        l_title = QLabel("Existing Backups")
        l_title.setObjectName("cardTitle")
        l_header.addWidget(l_title)
        l_header.addStretch()

        self.open_backup_dir_btn = QPushButton("📂 Open Backups Folder")
        self.open_backup_dir_btn.clicked.connect(self._on_open_backup_dir)
        l_header.addWidget(self.open_backup_dir_btn)

        self.refresh_backups_btn = QPushButton("🔄 Refresh List")
        self.refresh_backups_btn.clicked.connect(self.load_backup_page)
        l_header.addWidget(self.refresh_backups_btn)
        l_layout.addLayout(l_header)

        self.backups_table = QTableWidget()
        self.backups_table.setColumnCount(4)
        self.backups_table.setHorizontalHeaderLabels([
            "Backup Filename", "Size", "Created At", "Actions"
        ])
        configure_table_ux(
            self.backups_table,
            column_widths=[260, 90, 160, 140],
            stretch_column=0,
            default_row_height=40,
        )
        self.backups_table.setMinimumHeight(200)
        l_layout.addWidget(self.backups_table)
        layout.addWidget(list_card)

        # 4. Updates & Maintenance Card
        maint_card = QFrame()
        maint_card.setObjectName("settingsCard")
        m_layout = QVBoxLayout(maint_card)
        m_layout.setContentsMargins(20, 18, 20, 18)
        m_layout.setSpacing(10)

        m_header = QHBoxLayout()
        m_title = QLabel("Application Updates & Maintenance")
        m_title.setObjectName("cardTitle")
        m_header.addWidget(m_title)
        m_header.addStretch()

        self.version_lbl = QLabel("TAMS v2.0.0")
        self.version_lbl.setStyleSheet("font-weight: 700; color: #012D54;")
        m_header.addWidget(self.version_lbl)

        self.check_updates_btn = QPushButton("🔄 Check for Updates")
        self.check_updates_btn.clicked.connect(self._on_check_updates_clicked)
        m_header.addWidget(self.check_updates_btn)
        m_layout.addLayout(m_header)
        layout.addWidget(maint_card)

        layout.addStretch()
        scroll.setWidget(container)

        outer_layout = QVBoxLayout(page)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)
        return page

    def load_backup_page(self):
        # 1. DB path and size
        db_path = Path(DATABASE_PATH)
        if db_path.exists():
            size = db_path.stat().st_size
            if size < 1024 * 1024:
                self.backup_db_size_lbl.setText(f"{size / 1024:.1f} KB")
            else:
                self.backup_db_size_lbl.setText(f"{size / (1024 * 1024):.2f} MB")
        else:
            self.backup_db_size_lbl.setText("Not found")

        # 2. Companion Status
        status_path = get_helper_status_file_path()
        if status_path.exists():
            try:
                with open(status_path, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
                state = s_data.get("state", "UNKNOWN")
                pid = s_data.get("pid", "—")
                self.helper_status_lbl.setText(f"🟢 Active (PID: {pid}, State: {state})")
                self.helper_status_lbl.setStyleSheet("font-weight: 600; color: #15803D;")
            except Exception:
                self.helper_status_lbl.setText("⚪ Idle / Not Running")
                self.helper_status_lbl.setStyleSheet("font-weight: 600; color: #615F4B;")
        else:
            self.helper_status_lbl.setText("⚪ Inactive (Main App Mode)")
            self.helper_status_lbl.setStyleSheet("font-weight: 600; color: #615F4B;")

        # 3. Populate Backups Table
        backups = list_backups()
        self.backups_table.setRowCount(len(backups))
        for row, b in enumerate(backups):
            self.backups_table.setItem(row, 0, QTableWidgetItem(b["filename"]))
            self.backups_table.setItem(row, 1, QTableWidgetItem(b["size_formatted"]))
            self.backups_table.setItem(row, 2, QTableWidgetItem(b["created_iso"]))

            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(4, 2, 4, 2)
            btn_layout.setSpacing(6)

            restore_btn = QPushButton("Restore")
            restore_btn.setStyleSheet(f"background-color: {CREAM}; color: {NAVY}; border: 1px solid {LIGHT_GOLD}; font-size: 11px; padding: 4px 8px; border-radius: 4px; font-weight: 600;")
            restore_btn.clicked.connect(lambda checked=False, p=b["path"]: self._on_restore_backup_clicked(p))
            btn_layout.addWidget(restore_btn)

            delete_btn = QPushButton("Delete")
            delete_btn.setStyleSheet("background-color: transparent; color: #DC2626; border: 1px solid #FECACA; font-size: 11px; padding: 4px 8px; border-radius: 4px; font-weight: 600;")
            delete_btn.clicked.connect(lambda checked=False, p=b["path"]: self._on_delete_backup_clicked(p))
            btn_layout.addWidget(delete_btn)

            self.backups_table.setCellWidget(row, 3, btn_widget)

    def _on_create_backup_clicked(self):
        label = self.backup_label_input.text().strip() or None
        res = create_database_backup(custom_label=label)
        if res.get("success"):
            self.backup_label_input.clear()
            QMessageBox.information(
                self,
                "Backup Created",
                f"✅ Database backup created successfully:\n\n"
                f"File: {Path(res['backup_path']).name}\n"
                f"Size: {res.get('size_bytes', 0) / 1024:.1f} KB\n"
                f"Integrity check: Passed",
            )
            self.load_backup_page()
        else:
            QMessageBox.critical(
                self,
                "Backup Failed",
                f"❌ Failed to create backup: {res.get('error')}",
            )

    def _on_restore_backup_clicked(self, backup_file: Path | str):
        b_path = Path(backup_file)
        confirm = QMessageBox.question(
            self,
            "Confirm Database Restore",
            f"Are you sure you want to restore the database from:\n{b_path.name}?\n\n"
            "A safety snapshot of your current database will be saved before restoring.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        result = restore_database_backup(b_path)
        if result.get("success"):
            QMessageBox.information(
                self,
                "Database Restored",
                f"✅ Database successfully restored from {b_path.name}.\n\n"
                f"Pre-restore safety snapshot created: {Path(result['safety_snapshot_path']).name}",
            )
            self.load_batches()
            self.load_backup_page()
        else:
            QMessageBox.critical(
                self,
                "Restore Failed",
                f"❌ Failed to restore database: {result.get('error')}",
            )

    def _on_delete_backup_clicked(self, backup_file: Path | str):
        b_path = Path(backup_file)
        confirm = QMessageBox.question(
            self,
            "Delete Backup",
            f"Delete backup file '{b_path.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                b_path.unlink(missing_ok=True)
                self.load_backup_page()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to delete backup file: {e}")

    def _on_check_updates_clicked(self):
        res = check_for_updates()
        QMessageBox.information(
            self,
            "Check for Updates",
            f"ℹ️ {res.get('message')}\n\n"
            f"Current Version: {res.get('current_version')}\n"
            f"Latest Version: {res.get('latest_version')}",
        )

    def _on_open_backup_dir(self):
        backup_dir = get_backup_directory()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(backup_dir)))


    def apply_styles(self):
        self.setStyleSheet(f"""
            QWidget {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }}

            /* ── Global ScrollBars ── */
            QScrollBar:vertical {{
                background: #F8F6EA;
                width: 9px;
                margin: 0px;
                border-radius: 4px;
            }}

            QScrollBar::handle:vertical {{
                background: #D9B85F;
                min-height: 24px;
                border-radius: 4px;
            }}

            QScrollBar::handle:vertical:hover {{
                background: #C5A64D;
            }}

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
                background: none;
                border: none;
            }}

            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}

            QScrollBar:horizontal {{
                background: #F8F6EA;
                height: 9px;
                margin: 0px;
                border-radius: 4px;
            }}

            QScrollBar::handle:horizontal {{
                background: #D9B85F;
                min-width: 24px;
                border-radius: 4px;
            }}

            QScrollBar::handle:horizontal:hover {{
                background: #C5A64D;
            }}

            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
                background: none;
                border: none;
            }}

            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: none;
            }}

            QMessageBox {{
                background: #FEFEFE;
            }}

            QMessageBox QLabel {{
                color: #012D54;
                font-size: 13px;
            }}

            QMessageBox QPushButton {{
                background: #FEFEFE;
                color: #012D54;
                border: 1px solid #E9DEBA;
                border-radius: 7px;
                padding: 8px 18px;
                min-width: 70px;
                font-weight: 600;
            }}

            QMessageBox QPushButton:hover {{
                background: #E9DEBA;
            }}

            QMessageBox QPushButton:pressed {{
                background: #D9B85F;
                color: #012D54;
            }}

            QDialog {{
                background: {CREAM};
            }}

            #settingsHeader {{
                background: {NAVY};
                border-bottom: 2px solid {GOLD};
            }}

            #settingsTitle {{
                color: {WHITE};
                font-size: 22px;
                font-weight: 700;
            }}

            #settingsSubtitle {{
                color: {LIGHT_GOLD};
                font-size: 12px;
            }}

            #closeButton {{
                color: {WHITE};
                background: transparent;
                border: none;
                font-size: 26px;
                border-radius: 19px;
            }}

            #closeButton:hover {{
                background: {DARK_NAVY};
            }}

            #settingsSidebar {{
                background: {WHITE};
                border-right: 1px solid {LIGHT_GOLD};
            }}

            #settingsMenu {{
                background: transparent;
                border: none;
                outline: none;
            }}

            #settingsMenu::item {{
                color: {TEXT};
                padding: 13px 12px;
                border-radius: 7px;
                margin-bottom: 3px;
                font-size: 14px;
            }}

            #settingsMenu::item:hover {{
                background: {LIGHT_GOLD};
            }}

            #settingsMenu::item:selected {{
                background: {GOLD};
                color: {NAVY};
                font-weight: 700;
            }}

            #settingsPages {{
                background: {CREAM};
            }}

            #pageTitle {{
                color: {NAVY};
                font-size: 24px;
                font-weight: 700;
            }}

            #pageDescription {{
                color: {MUTED};
                font-size: 13px;
                margin-bottom: 15px;
            }}

            #settingsCard {{
                background: {WHITE};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 10px;
            }}

            #cardTitle {{
                color: {NAVY};
                font-size: 16px;
                font-weight: 700;
            }}

            #cardText {{
                color: {MUTED};
                font-size: 13px;
            }}

            #primaryButton {{
                background: {NAVY};
                color: {WHITE};
                border: none;
                border-radius: 7px;
                padding: 10px 18px;
                font-weight: 600;
            }}

            #primaryButton:hover {{
                background: {DARK_NAVY};
            }}

            #dangerButton {{
                background: transparent;
                color: #A33A3A;
                border: 1px solid #D8A0A0;
                border-radius: 7px;
                padding: 10px 18px;
                font-weight: 600;
            }}

            #dangerButton:hover {{
                background: #F8EAEA;
            }}
            #batchItem {{
            background: {WHITE};
            border: 1px solid {LIGHT_GOLD};
            border-radius: 8px;
        }}

        #batchItem:hover {{
            border: 1px solid {GOLD};
        }}

        #batchName {{
            color: {NAVY};
            font-size: 15px;
            font-weight: 700;
        }}

        #batchInfo {{
            color: {MUTED};
            font-size: 12px;
        }}

        #batchStatus {{
            color: {NAVY};
            background: {LIGHT_GOLD};
            padding: 5px 9px;
            border-radius: 10px;
            font-size: 10px;
            font-weight: 700;
        }}

        #secondaryButton {{
            background: {WHITE};
            color: {NAVY};
            border: 1px solid {LIGHT_GOLD};
            border-radius: 7px;
            padding: 8px 14px;
            font-weight: 600;
        }}

        #secondaryButton:hover {{
            background: {LIGHT_GOLD};
        }}

        #emptyLabel {{
            color: {MUTED};
            padding: 40px;
            font-size: 13px;
        }}

        /* ── Inputs & Focus ── */
        QLineEdit, QTextEdit, QSpinBox, QTimeEdit, QComboBox {{
            background: {WHITE};
            color: {TEXT};
            border: 1px solid {GOLD};
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 13px;
        }}

        QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QTimeEdit:focus, QComboBox:focus {{
            border: 2px solid {NAVY};
        }}

        QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled, QTimeEdit:disabled, QComboBox:disabled {{
            background: {CREAM};
            color: {MUTED};
            border: 1px solid {LIGHT_GOLD};
        }}

        /* ── CheckBoxes & RadioButtons ── */
        QCheckBox, QRadioButton {{
            spacing: 8px;
            font-size: 13px;
            color: {TEXT};
        }}

        QCheckBox::indicator {{
            width: 17px;
            height: 17px;
            border: 1px solid {GOLD};
            border-radius: 4px;
            background: {WHITE};
        }}

        QCheckBox::indicator:hover {{
            border: 1px solid {NAVY};
            background: {CREAM};
        }}

        QCheckBox::indicator:checked {{
            background: {NAVY};
            border: 1px solid {NAVY};
        }}

        QCheckBox::indicator:disabled {{
            border: 1px solid {LIGHT_GOLD};
            background: {CREAM};
        }}

        /* ── Tables ── */
        QTableWidget {{
            background: {WHITE};
            border: 1px solid {LIGHT_GOLD};
            border-radius: 8px;
            gridline-color: #F1EBD3;
            color: {TEXT};
            font-size: 13px;
            selection-background-color: {LIGHT_GOLD};
            selection-color: {NAVY};
            outline: none;
        }}

        QTableWidget::item {{
            padding: 8px 10px;
            border-bottom: 1px solid #F1EBD3;
        }}

        QTableWidget::item:selected {{
            background-color: {LIGHT_GOLD};
            color: {NAVY};
        }}

        QHeaderView::section {{
            background: {NAVY};
            color: {WHITE};
            padding: 9px 10px;
            border: none;
            font-size: 12px;
            font-weight: 600;
        }}

        /* ── GroupBox & ToolTip ── */
        QGroupBox {{
            border: 1px solid {LIGHT_GOLD};
            border-radius: 8px;
            margin-top: 16px;
            padding-top: 14px;
            background: {WHITE};
            font-weight: 700;
            color: {NAVY};
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 12px;
            padding: 0 6px;
            color: {NAVY};
        }}

        QToolTip {{
            background: {NAVY};
            color: {WHITE};
            border: 1px solid {GOLD};
            border-radius: 5px;
            padding: 5px 8px;
            font-size: 12px;
        }}
        """)
    def load_batches(self):
        # Remove existing widgets
        while self.batch_list_layout.count():
            item = self.batch_list_layout.takeAt(0)

            if item.widget():
                item.widget().deleteLater()

        with SessionLocal() as session:
            batches = get_active_batches(session)

            if not batches:
                empty_label = QLabel(
                    "No active batches."
                )
                empty_label.setObjectName("emptyLabel")
                empty_label.setAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )
                self.batch_list_layout.addWidget(empty_label)
            else:
                for batch in batches:
                    self.add_batch_card(batch)

            self.load_inactive_batches()

            
            
    def add_batch_card(self, batch):
        card = QFrame()
        card.setObjectName("batchItem")
        card.setMaximumHeight(110)
        card.setMinimumHeight(100)
        card.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )

        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)

        # Batch information
        info_layout = QVBoxLayout()
        info_layout.setSpacing(3)

        name = QLabel(batch.name)
        name.setObjectName("batchName")

        start_str = batch.start_time.strftime("%I:%M %p") if batch.start_time else "—"
        end_str = batch.end_time.strftime("%I:%M %p") if batch.end_time else "—"
        days_str = batch.days or "Not scheduled"
        timing = QLabel(f"{start_str}  –  {end_str}\n{days_str}")
        timing.setObjectName("batchInfo")

        info_layout.addWidget(name)
        info_layout.addWidget(timing)

        layout.addLayout(info_layout)
        layout.addStretch()

        # Status
        status = QLabel("ACTIVE")
        status.setObjectName("batchStatus")
        layout.addWidget(status, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Edit
        edit_button = QPushButton("Edit")
        edit_button.setObjectName("secondaryButton")
        edit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_button.clicked.connect(
            lambda checked=False, b=batch: self.open_edit_batch_dialog(b)
        )
        layout.addWidget(edit_button, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Deactivate
        deactivate_button = QPushButton("Deactivate")
        deactivate_button.setObjectName("dangerButton")
        deactivate_button.setCursor(Qt.CursorShape.PointingHandCursor)
        deactivate_button.clicked.connect(
            lambda checked=False, b=batch: self.deactivate_batch(b)
        )
        layout.addWidget(deactivate_button, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.batch_list_layout.addWidget(card)
    def deactivate_batch(self, batch):
        result = QMessageBox.question(
            self,
            "Deactivate Batch",
            (
                f"Are you sure you want to deactivate "
                f"'{batch.name}'?\n\n"
                "The batch will no longer appear in the active "
                "batch selector.\n\n"
                "Existing student, attendance, fee and result "
                "history will be preserved."
            ),
            QMessageBox.StandardButton.Cancel
            | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )

        if result != QMessageBox.StandardButton.Yes:
            return

        with SessionLocal() as session:
            from app.services.batch_service import deactivate_batch

            deactivate_batch(session, batch.id)

        self.load_batches()
    def open_add_batch_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Add New Batch")
        dialog.setFixedSize(560, 500)

        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(0)

        # ── Header ─────────────────────────────────────

        header_layout = QHBoxLayout()

        title_layout = QVBoxLayout()
        title_layout.setSpacing(3)

        title = QLabel("Add New Batch")
        title.setObjectName("dialogTitle")

        subtitle = QLabel("Create a new teaching batch")
        subtitle.setObjectName("dialogSubtitle")

        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)

        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        close_button = QPushButton("×")
        close_button.setObjectName("dialogCloseButton")
        close_button.setFixedSize(34, 34)
        close_button.clicked.connect(dialog.reject)

        header_layout.addWidget(close_button)

        main_layout.addLayout(header_layout)

        # ── Separator ──────────────────────────────────

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName("dialogSeparator")

        main_layout.addWidget(separator)
        main_layout.addSpacing(22)

        # ── Batch name ─────────────────────────────────

        name_label = QLabel("BATCH NAME")
        name_label.setObjectName("formLabel")

        main_layout.addWidget(name_label)
        main_layout.addSpacing(6)

        name_input = QLineEdit()
        name_input.setPlaceholderText("e.g. Class 10 Maths")
        name_input.setMinimumHeight(42)

        main_layout.addWidget(name_input)

        main_layout.addSpacing(20)

        # ── Schedule ────────────────────────────────────

        schedule_label = QLabel("SCHEDULE")
        schedule_label.setObjectName("formLabel")

        main_layout.addWidget(schedule_label)
        main_layout.addSpacing(6)

        time_layout = QHBoxLayout()
        time_layout.setSpacing(14)

        # Start
        start_box = QVBoxLayout()
        start_box.setSpacing(5)

        start_caption = QLabel("Start Time")
        start_caption.setObjectName("smallLabel")

        start_input = TAMSTimeEdit()
        start_input.setDisplayFormat("hh:mm AP")
        start_input.setTime(time(17, 0))
        start_input.setMinimumHeight(42)

        start_box.addWidget(start_caption)
        start_box.addWidget(start_input)

        # End
        end_box = QVBoxLayout()
        end_box.setSpacing(5)

        end_caption = QLabel("End Time")
        end_caption.setObjectName("smallLabel")

        end_input = TAMSTimeEdit()
        end_input.setDisplayFormat("hh:mm AP")
        end_input.setTime(time(18, 0))
        end_input.setMinimumHeight(42)

        end_box.addWidget(end_caption)
        end_box.addWidget(end_input)

        time_layout.addLayout(start_box)
        time_layout.addLayout(end_box)

        main_layout.addLayout(time_layout)

        main_layout.addSpacing(20)

        # ── Days ────────────────────────────────────────

        days_label = QLabel("CLASS DAYS")
        days_label.setObjectName("formLabel")

        main_layout.addWidget(days_label)
        main_layout.addSpacing(8)

        days_layout = QHBoxLayout()
        days_layout.setSpacing(7)

        day_names = [
            ("Mon", "Monday"),
            ("Tue", "Tuesday"),
            ("Wed", "Wednesday"),
            ("Thu", "Thursday"),
            ("Fri", "Friday"),
            ("Sat", "Saturday"),
            ("Sun", "Sunday"),
        ]

        day_checkboxes = []

        for short_name, full_name in day_names:
            checkbox = QPushButton(short_name)
            checkbox.setCheckable(True)
            checkbox.setObjectName("dayButton")
            checkbox.setProperty("day_name", full_name)
            checkbox.setMinimumSize(60, 38)

            day_checkboxes.append(checkbox)
            days_layout.addWidget(checkbox)

        main_layout.addLayout(days_layout)

        main_layout.addStretch()

        # ── Bottom buttons ──────────────────────────────

        bottom_separator = QFrame()
        bottom_separator.setFrameShape(QFrame.Shape.HLine)
        bottom_separator.setObjectName("dialogSeparator")

        main_layout.addWidget(bottom_separator)
        main_layout.addSpacing(15)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("cancelButton")
        cancel_button.setMinimumSize(100, 40)
        cancel_button.clicked.connect(dialog.reject)

        create_button = QPushButton("Create Batch")
        create_button.setObjectName("createButton")
        create_button.setMinimumSize(125, 40)

        button_layout.addWidget(cancel_button)
        button_layout.addWidget(create_button)

        main_layout.addLayout(button_layout)

        # ── Save ────────────────────────────────────────

        def save_batch():
            name = name_input.text().strip()

            if not name:
                QMessageBox.warning(
                    dialog,
                    "Missing Batch Name",
                    "Please enter a batch name.",
                )
                return

            if start_input.time() >= end_input.time():
                QMessageBox.warning(
                    dialog,
                    "Invalid Time",
                    "End time must be later than start time.",
                )
                return

            selected_days = [
                button.property("day_name")
                for button in day_checkboxes
                if button.isChecked()
            ]

            if not selected_days:
                QMessageBox.warning(
                    dialog,
                    "No Days Selected",
                    "Please select at least one class day.",
                )
                return

            with SessionLocal() as session:
                create_batch(
                    session=session,
                    name=name,
                    start_time=start_input.time().toPyTime(),
                    end_time=end_input.time().toPyTime(),
                    days=", ".join(selected_days),
                )

            self.load_batches()

            dialog.accept()

        create_button.clicked.connect(save_batch)

        # ── Styling ─────────────────────────────────────

        dialog.setStyleSheet(f"""
            QDialog {{
                background: {CREAM};
            }}

            #dialogTitle {{
                color: {NAVY};
                font-size: 22px;
                font-weight: 700;
            }}

            #dialogSubtitle {{
                color: {MUTED};
                font-size: 12px;
            }}

            #dialogCloseButton {{
                background: transparent;
                color: {MUTED};
                border: none;
                font-size: 25px;
                border-radius: 17px;
            }}

            #dialogCloseButton:hover {{
                background: {LIGHT_GOLD};
                color: {NAVY};
            }}

            #dialogSeparator {{
                color: {LIGHT_GOLD};
                background: {LIGHT_GOLD};
                max-height: 1px;
            }}

            #formLabel {{
                color: {NAVY};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1px;
            }}

            #smallLabel {{
                color: {MUTED};
                font-size: 11px;
            }}

            QLineEdit,
            QTimeEdit {{
                background: {WHITE};
                color: {TEXT};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 7px;
                padding: 8px 10px;
                font-size: 13px;
            }}

            QLineEdit:focus,
            QTimeEdit:focus {{
                border: 1px solid {GOLD};
            }}
            QTimeEdit {{
                background: {WHITE};
                color: {TEXT};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 7px;
                padding: 8px 10px;
                font-size: 13px;
            }}

            QTimeEdit::up-button {{
                background: {LIGHT_GOLD};
                border: none;
                width: 22px;
            }}

            QTimeEdit::down-button {{
                background: {LIGHT_GOLD};
                border: none;
                width: 22px;
            }}

            QTimeEdit::up-button:hover,
            QTimeEdit::down-button:hover {{
                background: {GOLD};
            }}

            #dayButton {{
                background: {WHITE};
                color: {NAVY};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 7px;
                font-size: 11px;
                font-weight: 600;
            }}

            #dayButton:hover {{
                background: {LIGHT_GOLD};
            }}

            #dayButton:checked {{
                background: {GOLD};
                color: {NAVY};
                border: 1px solid {GOLD};
                font-weight: 700;
            }}

            #cancelButton {{
                background: {WHITE};
                color: {NAVY};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 7px;
                padding: 8px 16px;
                font-weight: 600;
            }}

            #cancelButton:hover {{
                background: {LIGHT_GOLD};
            }}

            #createButton {{
                background: {NAVY};
                color: {WHITE};
                border: none;
                border-radius: 7px;
                padding: 8px 16px;
                font-weight: 600;
            }}

            #createButton:hover {{
                background: {DARK_NAVY};
            }}
            #timeArrowButton {{
    background: {LIGHT_GOLD};
    color: {NAVY};
    border: none;
    font-size: 8px;
    padding: 0px;
}}

#timeArrowButton:hover {{
    background: {GOLD};
}}

#timeArrowButton:pressed {{
    background: {DARK_NAVY};
    color: {WHITE};
}}
        #inactiveBatchStatus {{
    color: #615F4B;
    background: #F0EFE8;
    padding: 5px 9px;
    border-radius: 10px;
    font-size: 10px;
    font-weight: 700;
}}
        """)

        dialog.exec()
    def open_edit_batch_dialog(self, batch):
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Batch")
        dialog.setFixedSize(560, 500)

        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(0)

        # Header
        header_layout = QHBoxLayout()

        title_layout = QVBoxLayout()
        title_layout.setSpacing(3)

        title = QLabel("Edit Batch")
        title.setObjectName("dialogTitle")

        subtitle = QLabel("Update the batch details")
        subtitle.setObjectName("dialogSubtitle")

        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)

        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        close_button = QPushButton("×")
        close_button.setObjectName("dialogCloseButton")
        close_button.setFixedSize(34, 34)
        close_button.clicked.connect(dialog.reject)

        header_layout.addWidget(close_button)

        main_layout.addLayout(header_layout)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName("dialogSeparator")

        main_layout.addWidget(separator)
        main_layout.addSpacing(22)

        # Batch name
        name_label = QLabel("BATCH NAME")
        name_label.setObjectName("formLabel")

        main_layout.addWidget(name_label)
        main_layout.addSpacing(6)

        name_input = QLineEdit()
        name_input.setText(batch.name)
        name_input.setMinimumHeight(42)

        main_layout.addWidget(name_input)

        main_layout.addSpacing(20)

        # Schedule
        schedule_label = QLabel("SCHEDULE")
        schedule_label.setObjectName("formLabel")

        main_layout.addWidget(schedule_label)
        main_layout.addSpacing(6)

        time_layout = QHBoxLayout()
        time_layout.setSpacing(14)

        start_box = QVBoxLayout()
        start_box.setSpacing(5)

        start_caption = QLabel("Start Time")
        start_caption.setObjectName("smallLabel")

        start_input = TAMSTimeEdit()
        start_input.setDisplayFormat("hh:mm AP")
        start_input.setTime(
            QTime(
                batch.start_time.hour,
                batch.start_time.minute,
            )
        )

        start_box.addWidget(start_caption)
        start_box.addWidget(start_input)

        end_box = QVBoxLayout()
        end_box.setSpacing(5)

        end_caption = QLabel("End Time")
        end_caption.setObjectName("smallLabel")

        end_input = TAMSTimeEdit()
        end_input.setDisplayFormat("hh:mm AP")
        end_input.setTime(
            QTime(
                batch.end_time.hour,
                batch.end_time.minute,
            )
        )

        end_box.addWidget(end_caption)
        end_box.addWidget(end_input)

        time_layout.addLayout(start_box)
        time_layout.addLayout(end_box)

        main_layout.addLayout(time_layout)

        main_layout.addSpacing(20)

        # Days
        days_label = QLabel("CLASS DAYS")
        days_label.setObjectName("formLabel")

        main_layout.addWidget(days_label)
        main_layout.addSpacing(8)

        days_layout = QHBoxLayout()
        days_layout.setSpacing(7)

        day_names = [
            ("Mon", "Monday"),
            ("Tue", "Tuesday"),
            ("Wed", "Wednesday"),
            ("Thu", "Thursday"),
            ("Fri", "Friday"),
            ("Sat", "Saturday"),
            ("Sun", "Sunday"),
        ]

        existing_days = {
            day.strip()
            for day in batch.days.split(",")
        }

        day_buttons = []

        for short_name, full_name in day_names:
            button = QPushButton(short_name)
            button.setCheckable(True)
            button.setObjectName("dayButton")
            button.setProperty("day_name", full_name)
            button.setMinimumSize(60, 38)

            if full_name in existing_days:
                button.setChecked(True)

            day_buttons.append(button)
            days_layout.addWidget(button)

        main_layout.addLayout(days_layout)

        main_layout.addStretch()

        # Bottom separator
        bottom_separator = QFrame()
        bottom_separator.setFrameShape(QFrame.Shape.HLine)
        bottom_separator.setObjectName("dialogSeparator")

        main_layout.addWidget(bottom_separator)
        main_layout.addSpacing(15)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("cancelButton")
        cancel_button.setMinimumSize(100, 40)
        cancel_button.clicked.connect(dialog.reject)

        save_button = QPushButton("Save Changes")
        save_button.setObjectName("createButton")
        save_button.setMinimumSize(125, 40)

        button_layout.addWidget(cancel_button)
        button_layout.addWidget(save_button)

        main_layout.addLayout(button_layout)

        # Save
        def save_changes():
            name = name_input.text().strip()

            if not name:
                QMessageBox.warning(
                    dialog,
                    "Missing Batch Name",
                    "Please enter a batch name.",
                )
                return

            if start_input.time() >= end_input.time():
                QMessageBox.warning(
                    dialog,
                    "Invalid Time",
                    "End time must be later than start time.",
                )
                return

            selected_days = [
                button.property("day_name")
                for button in day_buttons
                if button.isChecked()
            ]

            if not selected_days:
                QMessageBox.warning(
                    dialog,
                    "No Days Selected",
                    "Please select at least one class day.",
                )
                return

            with SessionLocal() as session:
                update_batch(
                    session,
                    batch.id,
                    name=name,
                    start_time=start_input.time().toPyTime(),
                    end_time=end_input.time().toPyTime(),
                    days=", ".join(selected_days),
                )

            self.load_batches()
            dialog.accept()

        save_button.clicked.connect(save_changes)

        # Same TAMS styling
        dialog.setStyleSheet(f"""
            QDialog {{
                background: {CREAM};
            }}

            #dialogTitle {{
                color: {NAVY};
                font-size: 22px;
                font-weight: 700;
            }}

            #dialogSubtitle {{
                color: {MUTED};
                font-size: 12px;
            }}

            #dialogCloseButton {{
                background: transparent;
                color: {MUTED};
                border: none;
                font-size: 25px;
                border-radius: 17px;
            }}

            #dialogCloseButton:hover {{
                background: {LIGHT_GOLD};
                color: {NAVY};
            }}

            #dialogSeparator {{
                color: {LIGHT_GOLD};
                background: {LIGHT_GOLD};
                max-height: 1px;
            }}

            #formLabel {{
                color: {NAVY};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1px;
            }}

            #smallLabel {{
                color: {MUTED};
                font-size: 11px;
            }}

            QLineEdit,
            QTimeEdit {{
                background: {WHITE};
                color: {TEXT};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 7px;
                padding: 8px 10px;
                font-size: 13px;
            }}

            QLineEdit:focus,
            QTimeEdit:focus {{
                border: 1px solid {GOLD};
            }}

            #timeArrowButton {{
                background: {LIGHT_GOLD};
                color: {NAVY};
                border: none;
                font-size: 8px;
                padding: 0px;
            }}

            #timeArrowButton:hover {{
                background: {GOLD};
            }}

            #timeArrowButton:pressed {{
                background: {DARK_NAVY};
                color: {WHITE};
            }}

            #dayButton {{
                background: {WHITE};
                color: {NAVY};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 7px;
                font-size: 11px;
                font-weight: 600;
            }}

            #dayButton:hover {{
                background: {LIGHT_GOLD};
            }}

            #dayButton:checked {{
                background: {GOLD};
                color: {NAVY};
                border: 1px solid {GOLD};
                font-weight: 700;
            }}

            #cancelButton {{
                background: {WHITE};
                color: {NAVY};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 7px;
                padding: 8px 16px;
                font-weight: 600;
            }}

            #cancelButton:hover {{
                background: {LIGHT_GOLD};
            }}

            #createButton {{
                background: {NAVY};
                color: {WHITE};
                border: none;
                border-radius: 7px;
                padding: 8px 16px;
                font-weight: 600;
            }}

            #createButton:hover {{
                background: {DARK_NAVY};
            }}
        """)

        dialog.exec()
    def get_inactive_batches(self):
        with SessionLocal() as session:
            from app.database.models.batch import Batch

            return (
                session.query(Batch)
                .filter(Batch.active.is_(False))
                .order_by(Batch.name)
                .all()
            )
    def reactivate_batch(self, batch):
        result = QMessageBox.question(
            self,
            "Reactivate Batch",
            (
                f"Reactivate '{batch.name}'?\n\n"
                "This batch will become active again and "
                "will appear in the main batch selector."
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )

        if result != QMessageBox.StandardButton.Yes:
            return

        with SessionLocal() as session:
            reactivate_batch(session, batch.id)

        self.load_batches()
    def load_inactive_batches(self):
        while self.inactive_batch_list_layout.count():
            item = self.inactive_batch_list_layout.takeAt(0)

            if item.widget():
                item.widget().deleteLater()

        with SessionLocal() as session:
            batches = (
                session.query(Batch)
                .filter(Batch.active.is_(False))
                .order_by(Batch.name)
                .all()
            )

            if not batches:
                empty_label = QLabel(
                    "No deactivated batches."
                )
                empty_label.setObjectName("emptyLabel")
                empty_label.setAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )

                self.inactive_batch_list_layout.addWidget(
                    empty_label
                )
                return

            for batch in batches:
                self.add_inactive_batch_card(batch)
    def add_inactive_batch_card(self, batch):
        card = QFrame()
        card.setObjectName("batchItem")
        card.setMinimumHeight(90)
        card.setMaximumHeight(100)

        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        layout = QHBoxLayout(card)
        layout.setContentsMargins(18, 12, 18, 12)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        name = QLabel(batch.name)
        name.setObjectName("batchName")

        start_str = batch.start_time.strftime("%I:%M %p") if batch.start_time else "—"
        end_str = batch.end_time.strftime("%I:%M %p") if batch.end_time else "—"
        days_str = batch.days or "Not scheduled"
        timing = QLabel(f"{start_str}  –  {end_str}\n{days_str}")
        timing.setObjectName("batchInfo")

        info_layout.addWidget(name)
        info_layout.addWidget(timing)

        layout.addLayout(info_layout)
        layout.addStretch()

        status = QLabel("INACTIVE")
        status.setObjectName("inactiveBatchStatus")
        layout.addWidget(status, alignment=Qt.AlignmentFlag.AlignVCenter)

        reactivate_button = QPushButton("Reactivate")
        reactivate_button.setObjectName("secondaryButton")
        reactivate_button.setCursor(Qt.CursorShape.PointingHandCursor)

        reactivate_button.clicked.connect(
            lambda checked=False, b=batch:
            self.reactivate_batch(b)
        )

        layout.addWidget(reactivate_button, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.inactive_batch_list_layout.addWidget(card)