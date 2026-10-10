from PyQt6.QtCore import Qt
from datetime import time
from PyQt6.QtCore import QTime

from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
    QLineEdit,
    QCheckBox,
    QSizePolicy,
    QLineEdit,

)
from app.database.models.batch import Batch
from app.database.connection import SessionLocal
from app.services.batch_service import (
    create_batch,
    get_active_batches,
    update_batch,
    deactivate_batch,
    reactivate_batch,
    get_batch,
)


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


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("TAMS Settings")
        self.resize(900, 600)

        self.setup_ui()
        self.apply_styles()

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
            ("◫", "Backup")
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
        self.pages.addWidget(self.create_placeholder_page(
            "WhatsApp",
            "WhatsApp configuration will be available here."
        ))
        self.pages.addWidget(self.create_placeholder_page(
            "Backup & Maintenance",
            "Backup and application maintenance settings."
        ))
        

        body_layout.addWidget(self.pages)

        self.settings_menu.currentRowChanged.connect(
            self.pages.setCurrentIndex
        )

        main_layout.addWidget(body)
        self.load_batches()

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
    
    def create_placeholder_page(self, title_text, description_text):
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(35, 30, 35, 30)

        title = QLabel(title_text)
        title.setObjectName("pageTitle")

        description = QLabel(description_text)
        description.setObjectName("pageDescription")

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addStretch()

        return page

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

        timing = QLabel(
            f"{batch.start_time.strftime('%I:%M %p')}  –  "
            f"{batch.end_time.strftime('%I:%M %p')}\n"
            f"{batch.days}"
        )
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

        timing = QLabel(
            f"{batch.start_time.strftime('%I:%M %p')}  –  "
            f"{batch.end_time.strftime('%I:%M %p')}\n"
            f"{batch.days}"
        )
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