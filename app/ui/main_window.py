"""
TAMS Desktop Application — Primary MainWindow Controller.

Coordinates the main application window, top bar, dynamic sidebar navigation,
batch filter selector, and page routing.

Modular Architecture:
Instead of maintaining a massive single-file UI, MainWindow composes specialized
page controller mixins from `app.ui.mixins`:
  - DashboardMixin   : Summary overview, today's classes, and active alerts
  - StudentsMixin    : Student registration, profiles, search, and directory
  - AttendanceMixin  : Daily batch attendance, bulk marking, and day overrides
  - ResultsMixin     : Exam creation, mark entry, and performance records
  - FeesMixin        : Fee generation, payments, history, and receipts
  - ExpensesMixin    : Operational costs, vendor tracking, and payments
  - TeachingMixin    : Syllabus completion, lessons, class records, and homework
  - AnalysisMixin    : Multi-tab coaching analytics, charts, and student risk tracking
  - MessagesPageWidget: Integrated Meta WhatsApp Cloud messaging control center
"""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.database.connection import SessionLocal
from app.services.batch_service import get_active_batches
from app.services.coaching_helper import CoachingHelper
from app.services.messaging_service import (
    ensure_messaging_seed_data,
    get_messaging_config,
)
from app.ui.messages_page_widget import MessagesPageWidget
from app.ui.mixins import (
    AnalysisMixin,
    AttendanceMixin,
    DashboardMixin,
    ExpensesMixin,
    FeesMixin,
    ResultsMixin,
    StudentsMixin,
    TeachingMixin,
)
from app.ui.settings_dialog import SettingsDialog
from app.ui.theme import (
    CHEVRON_DOWN_DISABLED_PATH,
    CHEVRON_DOWN_PATH,
    CREAM,
    DARK_NAVY,
    GOLD,
    LIGHT_GOLD,
    MUTED,
    NAVY,
    TEXT,
    WHITE,
)


class MainWindow(
    QMainWindow,
    DashboardMixin,
    StudentsMixin,
    AttendanceMixin,
    ResultsMixin,
    FeesMixin,
    ExpensesMixin,
    TeachingMixin,
    AnalysisMixin,
):
    """
    Main application window hosting the global top bar, navigation sidebar,
    and page container stack.
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle("TAMS - Coaching Management System")
        self.resize(1280, 800)

        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)

        # Top bar
        top_bar = QFrame()
        top_bar.setObjectName("topBar")

        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(24, 12, 24, 12)
        top_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        title = QLabel("Coaching Management System")
        title.setObjectName("appTitle")
        self.app_title_label = title

        settings_button = QPushButton("⚙")
        settings_button.setObjectName("settingButton")
        settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_button.clicked.connect(self.open_settings)

        top_layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignVCenter)
        top_layout.addStretch()
        top_layout.addWidget(settings_button, alignment=Qt.AlignmentFlag.AlignVCenter)

        main_layout.addWidget(top_bar)
        #  Main area
        content_widget = QWidget()
        content_widget.setObjectName("contentWidget")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        content_toolbar = QFrame()
        content_toolbar.setObjectName("contentToolbar")

        content_toolbar_layout = QHBoxLayout(content_toolbar)
        content_toolbar_layout.setContentsMargins(30, 8, 30, 8)
        content_toolbar_layout.setSpacing(10)
        content_toolbar_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        content_toolbar_layout.addStretch()

        batch_label = QLabel("Batch:")
        batch_label.setObjectName("batchLabel")

        self.batch_selector = QComboBox()
        self.batch_selector.setObjectName("batchSelector")
        self.batch_selector.setMinimumWidth(180)
        self.batch_selector.addItem("All Batches", None)

        content_toolbar_layout.addWidget(batch_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        content_toolbar_layout.addWidget(self.batch_selector, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.batch_selector.currentIndexChanged.connect(self.on_batch_changed)

        content_layout.addWidget(content_toolbar)

        workspace_layout = QHBoxLayout()
        workspace_layout.setContentsMargins(0,0,0,0)
        workspace_layout.setSpacing(0)

        


        

        

        # Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 15, 10, 15)
        sidebar_layout.setSpacing(5)

        self.pages = QStackedWidget()

        menu_items = [
            ("Dashboard", 0),
            ("Students", 1),
            ("Attendance", 2),
            ("Results", 3),
            ("Fees", 4),
            ("Expenses", 5),
            ("Teaching", 6),
            ("Analysis", 7),
            ("Messages", 8),
        ]
        workspace_layout.addWidget(sidebar)
        
        self.sidebar_buttons = []
        for name, index in menu_items:
            button = QPushButton(name)
            button.setCursor(Qt.CursorShape.PointingHandCursor)

            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            button.setFixedHeight(40)

            button.setProperty("page_index", index)
            button.setProperty("active", index == 0)

            button.clicked.connect(
                lambda checked=False, i=index: self.change_page(i)
            )

            sidebar_layout.addWidget(button)
            self.sidebar_buttons.append(button)

        sidebar_layout.addStretch()
        
        self.pages.addWidget(self.create_dashboard_page())

# Application pages
        for name, index in menu_items:
            if index == 0:
                continue

            if index == 1:
                self.pages.addWidget(self.create_students_page())
                continue
            if index == 2:
                self.pages.addWidget(self.create_attendance_page())
                continue

            if index == 3:
                self.pages.addWidget(self.create_results_page())
                continue

            if index == 4:
                self.pages.addWidget(self.create_fees_page())
                continue

            if index == 5:
                self.pages.addWidget(self.create_expenses_page())
                continue

            if index == 6:
                self.pages.addWidget(self.create_teaching_page())
                continue

            if index == 7:
                self.pages.addWidget(self.create_analysis_page())
                continue

            if index == 8:
                self.messages_page = MessagesPageWidget(self)
                self.pages.addWidget(self.messages_page)
                continue

            page = QWidget()
            layout = QVBoxLayout(page)

            label = QLabel(name)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("font-size: 28px;")

            layout.addWidget(label)
            self.pages.addWidget(page)
        workspace_layout.addWidget(self.pages)
        content_layout.addLayout(workspace_layout)

        main_layout.addWidget(content_widget)

        self.apply_styles()
        self.load_coaching_profile()
        self.load_batches()

        # Start CoachingHelper background worker thread
        self.coaching_helper = CoachingHelper(self)
        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(self.coaching_helper.stop)
        if not os.environ.get("PYTEST_CURRENT_TEST"):
            self.coaching_helper.start()

        # Check for system updates automatically on startup
        if not os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get("TAMS_DISABLE_AUTO_UPDATE"):
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1500, self.check_for_system_updates_on_startup)

    def check_for_system_updates_on_startup(self):
        """
        Automatically searches for system updates in the background on startup.
        If an update is available, prompts the user to download and install it.
        """
        if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("TAMS_DISABLE_AUTO_UPDATE"):
            return

        try:
            with SessionLocal() as session:
                cfg = get_messaging_config(session)
                if cfg.get("auto_check_updates_on_startup", "true").lower() != "true":
                    return
        except Exception:
            pass

        from app.ui.app_update_dialog import AppUpdateDialog, UpdateCheckWorker

        self._startup_update_worker = UpdateCheckWorker()

        def _on_startup_check_finished(res: dict):
            if not self.isVisible():
                return
            if res.get("status") == "update_available":
                dlg = AppUpdateDialog(res, parent=self)
                dlg.exec()

        self._startup_update_worker.finished.connect(_on_startup_check_finished)
        self._startup_update_worker.start()

    def load_coaching_profile(self):
        try:
            with SessionLocal() as session:
                ensure_messaging_seed_data(session)
                cfg = get_messaging_config(session)
                coaching_name = cfg.get("coaching_name", "TAMS Coaching Academy").strip() or "TAMS"
                tagline = cfg.get("coaching_tagline", "").strip()
                academic_session = cfg.get("academic_session", "").strip()

            self.setWindowTitle(f"TAMS - {coaching_name}" if coaching_name != "TAMS" else "TAMS - Coaching Management System")
            if hasattr(self, "app_title_label"):
                title_text = coaching_name
                if academic_session:
                    title_text += f" ({academic_session})"
                self.app_title_label.setText(title_text)

            if hasattr(self, "dashboard_subtitle_label"):
                if tagline:
                    self.dashboard_subtitle_label.setText(f"{tagline} • Here's what's happening with your coaching today.")
                else:
                    self.dashboard_subtitle_label.setText("Here's what's happening with your coaching today.")
        except Exception:
            pass

    def closeEvent(self, event):
        if hasattr(self, "_startup_update_worker") and self._startup_update_worker.isRunning():
            try:
                self._startup_update_worker.quit()
                self._startup_update_worker.wait(500)
            except Exception:
                pass
        if hasattr(self, "coaching_helper") and self.coaching_helper.isRunning():
            self.coaching_helper.stop()
        super().closeEvent(event)

    def open_settings(self, initial_tab: int = 0):
        dialog = SettingsDialog(self, initial_tab=initial_tab)
        dialog.exec()
        self.load_coaching_profile()
        self.load_batches()
        
    def apply_styles(self):
        self.setStyleSheet(f"""
            QWidget {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }}

            QMainWindow {{
                background: {LIGHT_GOLD};
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

            /* ── Top Bar ── */
            #topBar {{
                background: {NAVY};
                border-bottom: 2px solid {GOLD};
            }}

            #appTitle {{
                color: {WHITE};
                font-size: 22px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}

            #settingButton {{
                background: transparent;
                color: {WHITE};
                border: none;
                font-size: 20px;
                border-radius: 18px;
                padding: 4px;
            }}

            #settingButton:hover {{
                background: {DARK_NAVY};
            }}

            #contentToolbar {{
                background: {CREAM};
                border-bottom: 1px solid {LIGHT_GOLD};
            }}

            #batchLabel {{
                color: {NAVY};
                font-size: 13px;
                font-weight: 600;
            }}

            #batchSelector {{
                background-color: {WHITE};
                color: {NAVY};
                border: 1px solid {GOLD};
                border-radius: 7px;
                padding: 6px 28px 6px 12px;
                font-size: 13px;
                font-weight: 500;
            }}

            #batchSelector::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border: none;
            }}

            #batchSelector::down-arrow {{
                image: url("{CHEVRON_DOWN_PATH}");
                width: 12px;
                height: 12px;
                margin-right: 8px;
            }}

            #batchSelector::down-arrow:disabled {{
                image: url("{CHEVRON_DOWN_DISABLED_PATH}");
            }}

            #batchSelector QAbstractItemView {{
                background-color: {WHITE};
                color: {TEXT};
                border: 1px solid {GOLD};
                border-radius: 6px;
                selection-background-color: {NAVY};
                selection-color: {WHITE};
                padding: 4px;
            }}

            /* ── Sidebar ── */
            #sidebar {{
                background: {CREAM};
                border-right: 1px solid {LIGHT_GOLD};
            }}

            #sidebar QPushButton {{
                text-align: left;
                padding: 10px 16px;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 500;
                color: {NAVY};
                background: transparent;
            }}

            #sidebar QPushButton:hover {{
                background: {LIGHT_GOLD};
                color: {DARK_NAVY};
            }}

            #sidebar QPushButton[active="true"] {{
                background: {GOLD};
                color: {NAVY};
                font-weight: 700;
            }}

            /* ── General ComboBox ── */
            QComboBox {{
                padding: 7px 28px 7px 12px;
                border: 1px solid {GOLD};
                border-radius: 7px;
                background: {WHITE};
                color: {TEXT};
                font-size: 13px;
            }}

            QComboBox:focus {{
                border: 2px solid {NAVY};
            }}

            QComboBox:disabled {{
                background: {CREAM};
                color: {MUTED};
                border: 1px solid {LIGHT_GOLD};
            }}

            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border: none;
            }}

            QComboBox::down-arrow {{
                image: url("{CHEVRON_DOWN_PATH}");
                width: 12px;
                height: 12px;
                margin-right: 8px;
            }}

            QComboBox::down-arrow:disabled {{
                image: url("{CHEVRON_DOWN_DISABLED_PATH}");
            }}

            QComboBox QAbstractItemView {{
                background: {WHITE};
                color: {TEXT};
                border: 1px solid {LIGHT_GOLD};
                selection-background-color: {NAVY};
                selection-color: {WHITE};
                padding: 4px;
            }}

            /* ── Global Tables ── */
            QTableWidget {{
                background: {WHITE};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 10px;
                gridline-color: #F1EBD3;
                color: {TEXT};
                font-size: 13px;
                selection-background-color: {LIGHT_GOLD};
                selection-color: {NAVY};
                outline: none;
            }}

            QTableWidget::item {{
                padding: 8px 12px;
                border-bottom: 1px solid #F1EBD3;
            }}

            QTableWidget::item:hover {{
                background-color: #FAF8EE;
            }}

            QTableWidget::item:selected {{
                background-color: {LIGHT_GOLD};
                color: {NAVY};
            }}

            QHeaderView::section {{
                background: {NAVY};
                color: {WHITE};
                padding: 10px 12px;
                border: none;
                font-size: 12px;
                font-weight: 600;
                letter-spacing: 0.3px;
            }}

            QTableCornerButton::section {{
                background: {NAVY};
                border: none;
            }}

            /* ── Global Inputs & Focus Rings ── */
            QLineEdit, QTextEdit, QSpinBox, QTimeEdit, QDateEdit {{
                background: {WHITE};
                color: {TEXT};
                border: 1px solid {GOLD};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }}

            QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QTimeEdit:focus, QDateEdit:focus {{
                border: 2px solid {NAVY};
            }}

            QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled, QTimeEdit:disabled, QDateEdit:disabled {{
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

            QRadioButton::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {GOLD};
                border-radius: 9px;
                background: {WHITE};
            }}

            QRadioButton::indicator:hover {{
                border: 1px solid {NAVY};
                background: {CREAM};
            }}

            QRadioButton::indicator:checked {{
                background: {NAVY};
                border: 3px solid {WHITE};
            }}

            /* ── Menus & ToolTips ── */
            QMenu {{
                background-color: {WHITE};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 8px;
                padding: 6px;
                color: {TEXT};
            }}

            QMenu::item {{
                padding: 6px 20px 6px 14px;
                border-radius: 5px;
                font-size: 13px;
            }}

            QMenu::item:selected {{
                background-color: {LIGHT_GOLD};
                color: {NAVY};
                font-weight: 600;
            }}

            QMenu::separator {{
                height: 1px;
                background: {LIGHT_GOLD};
                margin: 4px 6px;
            }}

            QToolTip {{
                background-color: {NAVY};
                color: {WHITE};
                border: 1px solid {GOLD};
                border-radius: 5px;
                padding: 5px 8px;
                font-size: 12px;
            }}

            /* ── GroupBox, ProgressBar & Splitter ── */
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

            QProgressBar {{
                border: 1px solid {LIGHT_GOLD};
                border-radius: 6px;
                background: {CREAM};
                text-align: center;
                color: {NAVY};
                font-weight: 600;
                font-size: 11px;
                min-height: 16px;
            }}

            QProgressBar::chunk {{
                background: {GOLD};
                border-radius: 5px;
            }}

            QSplitter::handle {{
                background: {LIGHT_GOLD};
            }}


            /* ── Dashboard Page ── */
            #dashboardPage {{
                background: {CREAM};
            }}

            #dashboardGreeting {{
                color: {NAVY};
                font-size: 26px;
                font-weight: 700;
            }}

            #dashboardSubtitle {{
                color: {MUTED};
                font-size: 13px;
            }}

            #dashboardCard {{
                background: {WHITE};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 10px;
            }}

            #dashboardCard:hover {{
                border: 1px solid {GOLD};
            }}

            #dashboardCardTitle {{
                color: {MUTED};
                font-size: 12px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}

            #dashboardCardValue {{
                color: {NAVY};
                font-size: 28px;
                font-weight: 700;
            }}

            #dashboardCardDescription {{
                color: {MUTED};
                font-size: 12px;
            }}

            #dashboardSectionCard {{
                background: {WHITE};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 10px;
                min-height: 180px;
                max-height: 280px;
            }}

            #dashboardSectionTitle {{
                color: {NAVY};
                font-size: 16px;
                font-weight: 700;
            }}

            #dashboardSectionText {{
                color: {MUTED};
                font-size: 13px;
                line-height: 1.4;
            }}

            #dashboardScrollArea {{
                background: transparent;
                border: none;
            }}

            #dashboardScrollArea > QWidget > QWidget {{
                background: transparent;
            }}

            /* ── Students Page ── */
            #studentsPage {{
                background: {CREAM};
            }}

            #studentsPageTitle {{
                color: {NAVY};
                font-size: 26px;
                font-weight: 700;
            }}

            #studentsPageSubtitle {{
                color: {MUTED};
                font-size: 13px;
            }}

            #bulkActionsButton {{
                background: {CREAM};
                color: {NAVY};
                border: 1px solid {GOLD};
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 13px;
                font-weight: 600;
            }}

            #bulkActionsButton:hover {{
                background: {LIGHT_GOLD};
                border-color: {NAVY};
            }}

            #bulkActionsButton:pressed {{
                background: #D9B85F;
            }}

            #addStudentButton {{
                background: {NAVY};
                color: {WHITE};
                border: none;
                border-radius: 8px;
                padding: 10px 18px;
                font-size: 13px;
                font-weight: 600;
            }}

            #addStudentButton:hover {{
                background: {DARK_NAVY};
            }}

            #addStudentButton:pressed {{
                background: #001F3A;
            }}

            #studentsTableFrame {{
                background: {WHITE};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 12px;
            }}

            #studentsTablePlaceholder {{
                color: {MUTED};
                font-size: 14px;
            }}

            #studentsTable {{
                background: {WHITE};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 10px;
                gridline-color: #F1EBD3;
                color: {TEXT};
                font-size: 13px;
                selection-background-color: {LIGHT_GOLD};
                selection-color: {NAVY};
            }}

            #studentsTable::item {{
                padding: 8px;
                border-bottom: 1px solid #F1EBD3;
            }}

            #studentsTable QHeaderView::section {{
                background: {NAVY};
                color: {WHITE};
                padding: 10px 12px;
                border: none;
                font-size: 12px;
                font-weight: 600;
            }}

            #editStudentButton {{
                background: {LIGHT_GOLD};
                color: {NAVY};
                border: 1px solid {GOLD};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 700;
            }}

            #editStudentButton:hover {{
                background: {GOLD};
                color: {NAVY};
            }}

            #editStudentButton:pressed {{
                background: #C5A64D;
                color: {NAVY};
            }}

            /* ── Results Page ── */
            #resultsPage {{
                background: {CREAM};
            }}

            /* ── Attendance Page ── */
            #attendancePage {{
                background: {CREAM};
            }}

            #attendanceSummaryBadge {{
                background: {WHITE};
                color: {NAVY};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 600;
            }}

            /* ── Fees Page ── */
            #feesPage {{
                background: {CREAM};
            }}

            #feesPageTitle {{
                color: {NAVY};
                font-size: 26px;
                font-weight: 700;
            }}

            #feesPageSubtitle {{
                color: {MUTED};
                font-size: 13px;
            }}

            #feesTable {{
                background: {WHITE};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 10px;
                gridline-color: #F1EBD3;
                color: {TEXT};
                font-size: 13px;
                selection-background-color: {LIGHT_GOLD};
                selection-color: {NAVY};
            }}

            #feesTable::item {{
                padding: 8px 10px;
                border-bottom: 1px solid #F1EBD3;
            }}

            #feesTable QHeaderView::section {{
                background: {NAVY};
                color: {WHITE};
                padding: 10px 12px;
                border: none;
                font-size: 12px;
                font-weight: 600;
            }}

            /* ── Expenses Page ── */
            #expensesPage {{
                background: {CREAM};
            }}

            #expensesPageTitle {{
                color: {NAVY};
                font-size: 26px;
                font-weight: 700;
            }}

            #expensesPageSubtitle {{
                color: {MUTED};
                font-size: 13px;
            }}

            #expensesTable {{
                background: {WHITE};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 10px;
                gridline-color: #F1EBD3;
                color: {TEXT};
                font-size: 13px;
                selection-background-color: {LIGHT_GOLD};
                selection-color: {NAVY};
            }}

            #expensesTable::item {{
                padding: 8px 10px;
                border-bottom: 1px solid #F1EBD3;
            }}

            #expensesTable QHeaderView::section {{
                background: {NAVY};
                color: {WHITE};
                padding: 10px 12px;
                border: none;
                font-size: 12px;
                font-weight: 600;
            }}

            /* ── Financial Analysis Page ── */
            #analysisPage {{
                background: {CREAM};
            }}

            #analysisPageTitle {{
                color: {NAVY};
                font-size: 26px;
                font-weight: 700;
            }}

            #analysisPageSubtitle {{
                color: {MUTED};
                font-size: 13px;
            }}

            #analysisTable {{
                background: {WHITE};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 10px;
                gridline-color: #F1EBD3;
                color: {TEXT};
                font-size: 13px;
                selection-background-color: {LIGHT_GOLD};
                selection-color: {NAVY};
            }}

            #analysisTable::item {{
                padding: 8px 10px;
                border-bottom: 1px solid #F1EBD3;
            }}

            #analysisTable QHeaderView::section {{
                background: {NAVY};
                color: {WHITE};
                padding: 10px 12px;
                border: none;
                font-size: 12px;
                font-weight: 600;
            }}

            /* ── Teaching Page ── */
            #teachingPage, #messagesPage {{
                background: {CREAM};
            }}
            #teachingPageTitle {{
                color: {NAVY};
                font-size: 26px;
                font-weight: 700;
            }}
            #teachingPageSubtitle {{
                color: {MUTED};
                font-size: 13px;
            }}
            #lessonsTable, #classRecordsTable, #homeworkTable, #progressTable {{
                background: {WHITE};
                alternate-background-color: {CREAM};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 10px;
                gridline-color: #F1EBD3;
                color: {TEXT};
                font-size: 13px;
                selection-background-color: {LIGHT_GOLD};
                selection-color: {NAVY};
            }}
            #lessonsTable::item, #classRecordsTable::item, #homeworkTable::item, #progressTable::item {{
                padding: 8px 10px;
                border-bottom: 1px solid #F1EBD3;
            }}
            #lessonsTable QHeaderView::section, #classRecordsTable QHeaderView::section, #homeworkTable QHeaderView::section, #progressTable QHeaderView::section {{
                background: {NAVY};
                color: {WHITE};
                padding: 10px 12px;
                border: none;
                font-size: 12px;
                font-weight: 600;
            }}

            /* ── Dialogs & Forms ── */
            QDialog {{
                background: {CREAM};
            }}

            QDialog QLabel {{
                color: {NAVY};
                font-size: 13px;
            }}

            #addStudentTitle {{
                color: {NAVY};
                font-size: 22px;
                font-weight: 700;
            }}

            #addStudentSubtitle {{
                color: {MUTED};
                font-size: 13px;
            }}

            QDialog QLineEdit,
            QDialog QTextEdit,
            QDialog QDateEdit,
            QDialog QSpinBox,
            QDialog QDoubleSpinBox,
            QDialog QPlainTextEdit {{
                background: {WHITE};
                color: {TEXT};
                border: 1px solid {GOLD};
                border-radius: 7px;
                padding: 7px 11px;
                font-size: 13px;
            }}

            QDialog QComboBox {{
                background: {WHITE};
                color: {TEXT};
                border: 1px solid {GOLD};
                border-radius: 7px;
                padding: 7px 28px 7px 11px;
                font-size: 13px;
            }}

            QDialog QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border: none;
            }}

            QDialog QComboBox::down-arrow {{
                image: url("{CHEVRON_DOWN_PATH}");
                width: 12px;
                height: 12px;
                margin-right: 8px;
            }}

            QDialog QComboBox::down-arrow:disabled {{
                image: url("{CHEVRON_DOWN_DISABLED_PATH}");
            }}

            QDialog QLineEdit:focus,
            QDialog QTextEdit:focus,
            QDialog QComboBox:focus,
            QDialog QDateEdit:focus,
            QDialog QSpinBox:focus,
            QDialog QDoubleSpinBox:focus,
            QDialog QPlainTextEdit:focus {{
                border: 2px solid {NAVY};
            }}

            QSpinBox::up-button, QSpinBox::down-button,
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
                width: 18px;
                background: {LIGHT_GOLD};
                border: none;
            }}

            QSpinBox::up-button:hover, QSpinBox::down-button:hover,
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
                background: {GOLD};
            }}

            /* ── Dialog Buttons ── */
            #primaryDialogButton,
            QDialogButtonBox QPushButton:default {{
                background: {NAVY};
                color: {WHITE};
                border: 1px solid {NAVY};
                border-radius: 7px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 600;
            }}

            #primaryDialogButton:hover,
            QDialogButtonBox QPushButton:default:hover {{
                background: {DARK_NAVY};
                border-color: {DARK_NAVY};
            }}

            #primaryDialogButton:pressed,
            QDialogButtonBox QPushButton:default:pressed {{
                background: #001F3A;
            }}

            #primaryDialogButton:disabled,
            QDialogButtonBox QPushButton:default:disabled {{
                background: #CCCCCC;
                color: #888888;
                border-color: #CCCCCC;
            }}

            #secondaryDialogButton,
            QDialogButtonBox QPushButton {{
                background: {WHITE};
                color: {NAVY};
                border: 1px solid {GOLD};
                border-radius: 7px;
                padding: 8px 18px;
                font-size: 13px;
                font-weight: 600;
            }}

            #secondaryDialogButton:hover,
            QDialogButtonBox QPushButton:hover {{
                background: {LIGHT_GOLD};
            }}

            #secondaryDialogButton:pressed,
            QDialogButtonBox QPushButton:pressed {{
                background: {GOLD};
            }}

            /* ── Calendar Popup ── */
            QCalendarWidget {{
                background: {WHITE};
                border: 1px solid {GOLD};
                border-radius: 8px;
            }}

            QCalendarWidget QWidget#qt_calendar_navigationbar {{
                background-color: {NAVY};
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
                padding: 4px;
            }}

            QCalendarWidget QToolButton {{
                color: {WHITE};
                background-color: transparent;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: 600;
            }}

            QCalendarWidget QToolButton:hover {{
                background-color: {DARK_NAVY};
            }}

            QCalendarWidget QSpinBox {{
                background-color: {NAVY};
                color: {WHITE};
                border: none;
            }}

            QCalendarWidget QTableView {{
                background-color: {WHITE};
                selection-background-color: {NAVY};
                selection-color: {WHITE};
                alternate-background-color: {CREAM};
            }}
        """)
    def change_page(self, index):
        self.pages.setCurrentIndex(index)
        if index == 0:
            self.refresh_dashboard()
        elif index == 1:
            self.load_students()
        elif index == 2:
            self.load_attendance_students()
        elif index == 3:
            self.load_results_tests()
        elif index == 4:
            self.load_fees()
        elif index == 5:
            self.load_expenses()
        elif index == 6:
            self.load_teaching()
        elif index == 7:
            self.load_analysis()
        elif index == 8:
            if hasattr(self, "messages_page"):
                self.messages_page.load_messages_data()

        for button in self.sidebar_buttons:
            button.setProperty("active", button.property("page_index") == index)
            button.style().unpolish(button)
            button.style().polish(button)

    def on_batch_changed(self):
        self.refresh_dashboard()
        top_batch = self.batch_selector.currentData()
        if hasattr(self, "fee_batch_filter"):
            idx = self.fee_batch_filter.findData(top_batch)
            if idx >= 0:
                self.fee_batch_filter.blockSignals(True)
                self.fee_batch_filter.setCurrentIndex(idx)
                self.fee_batch_filter.blockSignals(False)
        if hasattr(self, "lesson_batch_filter"):
            idx = self.lesson_batch_filter.findData(top_batch)
            if idx >= 0:
                self.lesson_batch_filter.blockSignals(True)
                self.lesson_batch_filter.setCurrentIndex(idx)
                self.lesson_batch_filter.blockSignals(False)
        if hasattr(self, "analysis_batch_filter"):
            idx = self.analysis_batch_filter.findData(top_batch)
            if idx >= 0:
                self.analysis_batch_filter.blockSignals(True)
                self.analysis_batch_filter.setCurrentIndex(idx)
                self.analysis_batch_filter.blockSignals(False)
        current_index = self.pages.currentIndex()
        if current_index == 1:
            self.load_students()
        elif current_index == 2:
            self.load_attendance_students()
        elif current_index == 3:
            self.load_results_tests()
        elif current_index == 4:
            self.load_fees()
        elif current_index == 6:
            self.load_teaching()
        elif current_index == 7:
            self.load_analysis()

    def load_batches(self):
        current_selected_batch = self.batch_selector.currentData()

        self.batch_selector.blockSignals(True)
        self.batch_selector.clear()
        self.batch_selector.addItem("All Batches", None)

        with SessionLocal() as session:
            batches = get_active_batches(session)
            for batch in batches:
                self.batch_selector.addItem(
                    batch.name,
                    batch.id,
                )

        index = self.batch_selector.findData(current_selected_batch)
        if index >= 0:
            self.batch_selector.setCurrentIndex(index)
        else:
            self.batch_selector.setCurrentIndex(0)

        self.batch_selector.blockSignals(False)

        if hasattr(self, "fee_batch_filter"):
            curr_fee_batch = self.fee_batch_filter.currentData()
            self.fee_batch_filter.blockSignals(True)
            self.fee_batch_filter.clear()
            self.fee_batch_filter.addItem("All Batches", None)
            for batch in batches:
                self.fee_batch_filter.addItem(batch.name, batch.id)
            idx = self.fee_batch_filter.findData(curr_fee_batch)
            if idx >= 0:
                self.fee_batch_filter.setCurrentIndex(idx)
            self.fee_batch_filter.blockSignals(False)

        if hasattr(self, "lesson_batch_filter"):
            curr_lesson_batch = self.lesson_batch_filter.currentData()
            self.lesson_batch_filter.blockSignals(True)
            self.lesson_batch_filter.clear()
            self.lesson_batch_filter.addItem("All Batches", None)
            for batch in batches:
                self.lesson_batch_filter.addItem(batch.name, batch.id)
            idx = self.lesson_batch_filter.findData(curr_lesson_batch)
            if idx >= 0:
                self.lesson_batch_filter.setCurrentIndex(idx)
            self.lesson_batch_filter.blockSignals(False)

        if hasattr(self, "analysis_batch_filter"):
            curr_an_batch = self.analysis_batch_filter.currentData()
            self.analysis_batch_filter.blockSignals(True)
            self.analysis_batch_filter.clear()
            self.analysis_batch_filter.addItem("All Batches", None)
            for batch in batches:
                self.analysis_batch_filter.addItem(batch.name, batch.id)
            idx = self.analysis_batch_filter.findData(curr_an_batch)
            if idx >= 0:
                self.analysis_batch_filter.setCurrentIndex(idx)
            self.analysis_batch_filter.blockSignals(False)

        self.on_batch_changed()

