import os
from datetime import date, datetime, timedelta
from app.ui.settings_dialog import SettingsDialog
from app.ui.add_student_dialog import AddStudentDialog
from PyQt6.QtCore import Qt, QDate
from app.database.connection import SessionLocal
from app.services.batch_service import get_active_batches
from app.services.student_service import (
    count_students,
    get_students_by_batch,
    create_student_with_parent,
    get_student,
    update_student,
    update_student_with_parent,
)
import csv
from app.services.fee_service import (
    get_fees,
    get_fees_summary,
    get_fee,
    record_payment,
    get_fee_payments,
    reverse_payment,
    update_fee,
    get_student_fees,
    get_student_fee_summary,
    get_outstanding_amount,
)
from app.ui.fee_dialogs import (
    GenerateFeesDialog,
    RecordPaymentDialog,
    PaymentHistoryDialog,
    EditFeeDialog,
    CreateFeeDialog,
    MONTH_NAMES,
)
from app.services.expense_service import (
    get_expenses,
    get_expenses_summary,
    delete_expense,
    export_expenses_csv,
    DEFAULT_EXPENSE_CATEGORIES,
    EXPENSE_PAYMENT_METHODS,
)
from app.services.financial_service import (
    get_financial_summary,
    get_monthly_financial_comparison,
)
from app.ui.expense_dialogs import (
    AddExpenseDialog,
    EditExpenseDialog,
    RecordExpensePaymentDialog,
    ExpensePaymentHistoryDialog,
    FinancialAnalysisDialog,
)
from app.services.test_service import (
    count_upcoming_tests,
    get_student_results,
    create_test,
    get_tests,
    get_test_results,
    save_test_results,
    delete_test,
)
from app.services.lesson_service import (
    get_lessons_for_date,
    get_lessons,
    get_upcoming_lessons,
    get_overdue_lessons,
    get_teaching_summary,
    get_chapters_progress,
    get_class_records,
    get_homeworks,
    create_lesson,
    update_lesson,
    delete_lesson,
    mark_lesson_completed,
    reschedule_lesson,
    delete_class_record,
    delete_homework,
    LESSON_STATUSES,
)
from app.ui.teaching_dialogs import (
    LessonDialog,
    RecordClassDialog,
    HomeworkDialog,
    LessonDetailDialog,
)
from app.services.dashboard_service import get_dashboard_alerts
from app.services.attendance_service import (
    count_present_students,
    get_student_attendance,
    mark_attendance,
    get_attendance_by_date,
    get_student_attendance_summary,
    create_attendance_override,
    get_attendance_override,
    save_batch_attendance,
)
from app.database.models.batch import Batch
from app.database.models.test import TestModel
from app.services.analytics_service import (
    get_coaching_overview,
    get_student_performance_records,
    get_batch_comparison_data,
    get_attendance_analytics,
    get_tests_analytics,
    get_student_risk_analysis,
    get_student_improvement_analysis,
    get_teaching_analytics,
    get_retention_analytics,
    export_analytics_report_csv,
)
from app.ui.chart_widgets import (
    SimpleBarChartWidget,
    SegmentedDistributionWidget,
    TrendLineChartWidget,
)
from app.ui.messages_page_widget import MessagesPageWidget
from app.services.coaching_helper import CoachingHelper
from app.ui.table_utils import configure_table_ux, save_table_state, restore_table_state, TAMSItemDelegate
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
    QGridLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QDialog,
    QMessageBox,
    QTabWidget,
    QDateEdit,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QDialogButtonBox,
    QFileDialog,
    QScrollArea,
    QMenu,
)

NAVY = "#012D54"
DARK_NAVY = "#04294D"
GOLD = "#D9B85F"
LIGHT_GOLD = "#E9DEBA"
CREAM = "#F8F6EA"
WHITE = "#FEFEFE"
TEXT = "#1F2937"
MUTED = "#615F4B"
class MainWindow(QMainWindow):
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
        self.load_batches()

        # Start CoachingHelper background worker thread
        self.coaching_helper = CoachingHelper(self)
        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(self.coaching_helper.stop)
        if not os.environ.get("PYTEST_CURRENT_TEST"):
            self.coaching_helper.start()

    def closeEvent(self, event):
        if hasattr(self, "coaching_helper") and self.coaching_helper.isRunning():
            self.coaching_helper.stop()
        super().closeEvent(event)

    def open_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec()
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
                padding: 6px 12px;
                font-size: 13px;
                font-weight: 500;
            }}

            #batchSelector::drop-down {{
                border: none;
                width: 0px;
            }}

            #batchSelector::down-arrow {{
                image: none;
                width: 0px;
                height: 0px;
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
                padding: 7px 12px;
                border: 1px solid {GOLD};
                border-radius: 7px;
                background: {WHITE};
                color: {TEXT};
                font-size: 13px;
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
            #teachingPage {{
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
            QDialog QComboBox,
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

            QDialog QLineEdit:focus,
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

    def create_dashboard_page(self):
        page = QWidget()
        page.setObjectName("dashboardPage")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 28)
        layout.setSpacing(22)

        # ── Header ──────────────────────────────────────
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)

        hour = datetime.now().hour
        if hour < 12:
            greeting_text = "Good morning 👋"
        elif hour < 17:
            greeting_text = "Good afternoon 👋"
        else:
            greeting_text = "Good evening 👋"

        greeting = QLabel(greeting_text)
        greeting.setObjectName("dashboardGreeting")

        subtitle = QLabel(
            "Here's what's happening with your coaching today."
        )
        subtitle.setObjectName("dashboardSubtitle")

        header_layout.addWidget(greeting)
        header_layout.addWidget(subtitle)

        layout.addLayout(header_layout)

        # ── Summary Cards ───────────────────────────────
        cards_layout = QGridLayout()
        cards_layout.setSpacing(15)

        cards = [
            ("Students", "0", "Total students"),
            ("Attendance", "—", "Today's attendance"),
            ("Fees Pending", "₹0", "Outstanding amount"),
            ("Upcoming Tests", "0", "Tests scheduled"),
        ]

        for column, (title, value, description) in enumerate(cards):
            card = QFrame()
            card.setObjectName("dashboardCard")
            card.setMinimumHeight(125)
            card.setCursor(Qt.CursorShape.PointingHandCursor)

            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(20, 18, 20, 18)
            card_layout.setSpacing(5)

            title_label = QLabel(title)
            title_label.setObjectName("dashboardCardTitle")

            value_label = QLabel(value)
            value_label.setObjectName("dashboardCardValue")
            if title == "Students":
                self.students_count_label = value_label
                card.mousePressEvent = lambda e: self.change_page(1)
            elif title == "Attendance":
                self.attendance_count_label = value_label
                card.mousePressEvent = lambda e: self.change_page(2)
            elif title == "Fees Pending":
                self.fees_pending_label = value_label
                card.mousePressEvent = lambda e: self.change_page(4)
            elif title == "Upcoming Tests":
                self.upcoming_tests_label = value_label
                card.mousePressEvent = lambda e: self.change_page(3)

            description_label = QLabel(description)
            description_label.setObjectName(
                "dashboardCardDescription"
            )

            card_layout.addWidget(title_label)
            card_layout.addWidget(value_label)
            card_layout.addWidget(description_label)
            card_layout.addStretch()

            cards_layout.addWidget(card, 0, column)

        layout.addLayout(cards_layout)

        # ── Lower Section ───────────────────────────────
        lower_layout = QHBoxLayout()
        lower_layout.setSpacing(15)

        today_card = QFrame()
        today_card.setObjectName("dashboardSectionCard")

        today_layout = QVBoxLayout(today_card)
        today_layout.setContentsMargins(20, 18, 20, 18)
        today_layout.setSpacing(10)

        today_title = QLabel("Today's Classes")
        today_title.setObjectName("dashboardSectionTitle")
        today_layout.addWidget(today_title)

        today_scroll = QScrollArea()
        today_scroll.setObjectName("dashboardScrollArea")
        today_scroll.setWidgetResizable(True)
        today_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        today_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        today_scroll.setFrameShape(QFrame.Shape.NoFrame)
        today_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        today_info = QLabel()
        today_info.setWordWrap(True)
        today_info.setObjectName("dashboardSectionText")
        today_info.setStyleSheet("background: transparent;")
        today_scroll.setWidget(today_info)

        self.today_classes_label = today_info
        today_layout.addWidget(today_scroll, 1)

        alerts_card = QFrame()
        alerts_card.setObjectName("dashboardSectionCard")

        alerts_layout = QVBoxLayout(alerts_card)
        alerts_layout.setContentsMargins(20, 18, 20, 18)
        alerts_layout.setSpacing(10)

        alerts_title = QLabel("Alerts & Notifications")
        alerts_title.setObjectName("dashboardSectionTitle")
        alerts_layout.addWidget(alerts_title)

        alerts_scroll = QScrollArea()
        alerts_scroll.setObjectName("dashboardScrollArea")
        alerts_scroll.setWidgetResizable(True)
        alerts_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        alerts_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        alerts_scroll.setFrameShape(QFrame.Shape.NoFrame)
        alerts_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        alerts_info = QLabel()
        alerts_info.setWordWrap(True)
        alerts_info.setObjectName("dashboardSectionText")
        alerts_info.setStyleSheet("background: transparent;")
        alerts_scroll.setWidget(alerts_info)

        self.alerts_label = alerts_info
        alerts_layout.addWidget(alerts_scroll, 1)

        lower_layout.addWidget(today_card, 1)
        lower_layout.addWidget(alerts_card, 1)

        layout.addLayout(lower_layout)

        return page

    def create_results_page(self):
        page = QWidget()
        page.setObjectName("resultsPage")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 28)
        layout.setSpacing(18)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        heading_layout = QVBoxLayout()
        heading_layout.setSpacing(4)

        title = QLabel("Results")
        title.setStyleSheet("""
            QLabel {
                color: #012D54;
                font-size: 26px;
                font-weight: 700;
            }
        """)

        subtitle = QLabel(
            "Create tests and track student performance."
        )
        subtitle.setStyleSheet("""
            QLabel {
                color: #615F4B;
                font-size: 13px;
            }
        """)

        heading_layout.addWidget(title)
        heading_layout.addWidget(subtitle)
        header_layout.addLayout(heading_layout)
        header_layout.addStretch()

        create_button = QPushButton("＋ Create Test")
        create_button.setCursor(Qt.CursorShape.PointingHandCursor)
        create_button.setFixedHeight(42)
        create_button.setStyleSheet("""
            QPushButton {
                background: #012D54;
                color: #FEFEFE;
                border: none;
                border-radius: 8px;
                padding: 10px 18px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #04294D;
            }
        """)
        create_button.clicked.connect(self.create_test_dialog)
        header_layout.addWidget(create_button, alignment=Qt.AlignmentFlag.AlignVCenter)

        check_results_button = QPushButton("Check Results")
        check_results_button.setCursor(Qt.CursorShape.PointingHandCursor)
        check_results_button.setFixedHeight(42)
        check_results_button.setEnabled(False)
        check_results_button.setStyleSheet("""
            QPushButton {
                background: #E9DEBA;
                color: #012D54;
                border: 1px solid #D9B85F;
                border-radius: 8px;
                padding: 10px 18px;
                font-weight: 600;
            }
            QPushButton:hover:enabled {
                background: #D9B85F;
            }
            QPushButton:disabled {
                color: #8B887A;
                background: #F1EBD3;
                border-color: #E9DEBA;
            }
        """)
        check_results_button.clicked.connect(self.check_selected_test_results)
        header_layout.addWidget(check_results_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.check_results_button = check_results_button

        edit_results_button = QPushButton("Edit Results")
        edit_results_button.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_results_button.setFixedHeight(42)
        edit_results_button.setEnabled(False)
        edit_results_button.setStyleSheet("""
            QPushButton {
                background: #FEFEFE;
                color: #012D54;
                border: 1px solid #D9B85F;
                border-radius: 8px;
                padding: 10px 18px;
                font-weight: 600;
            }
            QPushButton:hover:enabled {
                background: #E9DEBA;
            }
            QPushButton:disabled {
                color: #8B887A;
                background: #F1EBD3;
                border-color: #E9DEBA;
            }
        """)
        edit_results_button.clicked.connect(self.edit_selected_test_results)
        header_layout.addWidget(edit_results_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.edit_results_button = edit_results_button

        delete_test_button = QPushButton("Delete Test")
        delete_test_button.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_test_button.setFixedHeight(42)
        delete_test_button.setEnabled(False)
        delete_test_button.setStyleSheet("""
            QPushButton {
                background: #FEFEFE;
                color: #DC2626;
                border: 1px solid #FECACA;
                border-radius: 8px;
                padding: 10px 18px;
                font-weight: 600;
            }
            QPushButton:hover:enabled {
                background: #FEE2E2;
                border-color: #DC2626;
            }
            QPushButton:disabled {
                color: #BDBDBD;
                background: #F9F9F9;
                border-color: #E5E7EB;
            }
        """)
        delete_test_button.clicked.connect(self.delete_selected_test)
        header_layout.addWidget(delete_test_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.delete_test_button = delete_test_button

        layout.addLayout(header_layout)

        self.results_tests_table = QTableWidget()
        self.results_tests_table.setObjectName("resultsTestsTable")
        self.results_tests_table.setColumnCount(4)
        self.results_tests_table.setHorizontalHeaderLabels(
            ["Test Name", "Batch", "Test Date", "Maximum Marks"]
        )
        self.results_tests_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.results_tests_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.results_tests_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.results_tests_table.itemSelectionChanged.connect(
            self.update_check_results_button
        )
        configure_table_ux(
            self.results_tests_table,
            column_widths=[240, 160, 140, 130],
            stretch_column=0,
        )

        layout.addWidget(self.results_tests_table)

        self.results_empty_label = QLabel(
            "No tests found for the selected batch. Click '＋ Create Test' above to add one."
        )
        self.results_empty_label.setStyleSheet("""
            QLabel {
                color: #615F4B;
                font-size: 13px;
                padding: 14px;
                background: #F8F6EA;
                border: 1px dashed #D9B85F;
                border-radius: 8px;
            }
        """)
        self.results_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.results_empty_label.setVisible(False)
        layout.addWidget(self.results_empty_label)

        return page

    def load_results_tests(self):
        if not hasattr(self, "results_tests_table"):
            return

        selected_batch_id = self.batch_selector.currentData()

        with SessionLocal() as session:
            tests = get_tests(
                session,
                batch_id=selected_batch_id,
            )
            rows = []
            for test in tests:
                batch = session.get(Batch, test.batch_id)
                rows.append((
                    test.name,
                    batch.name if batch is not None else "Unknown batch",
                    test.test_date.strftime("%d %b %Y"),
                    str(test.max_marks),
                ))

        self.results_tests_table.setRowCount(len(rows))
        for row_index, values in enumerate(rows):
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, tests[row_index].id)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.results_tests_table.setItem(
                    row_index,
                    column_index,
                    item,
                )

        if hasattr(self, "results_empty_label"):
            self.results_empty_label.setVisible(len(rows) == 0)

        self.update_check_results_button()

    def update_check_results_button(self):
        has_selection = self.results_tests_table.currentRow() >= 0
        self.check_results_button.setEnabled(has_selection)
        self.edit_results_button.setEnabled(has_selection)
        if hasattr(self, "delete_test_button"):
            self.delete_test_button.setEnabled(has_selection)

    def delete_selected_test(self):
        selected_row = self.results_tests_table.currentRow()
        if selected_row < 0:
            QMessageBox.information(
                self,
                "Select a Test",
                "Select a test from the table first.",
            )
            return

        test_item = self.results_tests_table.item(selected_row, 0)
        test_id = test_item.data(Qt.ItemDataRole.UserRole)
        test_name = test_item.text()

        confirm = QMessageBox.question(
            self,
            "Confirm Delete Test",
            f"Are you sure you want to delete test '{test_name}'?\n\nThis will permanently delete the test and all student marks recorded for it.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        with SessionLocal() as session:
            delete_test(session, int(test_id))

        self.load_results_tests()
        self.refresh_dashboard()

        QMessageBox.information(
            self,
            "Test Deleted",
            f"Test '{test_name}' and its results have been deleted.",
        )

    def check_selected_test_results(self):
        selected_row = self.results_tests_table.currentRow()
        if selected_row < 0:
            QMessageBox.information(
                self,
                "Select a Test",
                "Select a test from the table first.",
            )
            return

        test_item = self.results_tests_table.item(selected_row, 0)
        test_id = test_item.data(Qt.ItemDataRole.UserRole)
        test_name = test_item.text()

        with SessionLocal() as session:
            results = get_test_results(session, int(test_id))
            rows = []
            for result in results:
                student = result.student
                student_name = (
                    f"{student.first_name} {student.last_name or ''}"
                ).strip() if student is not None else "Unknown student"
                percentage = (
                    result.marks / result.test.max_marks * 100
                    if result.test.max_marks
                    else 0
                )
                rows.append((
                    student.admission_number if student is not None else "-",
                    student_name,
                    str(result.marks),
                    f"{percentage:.1f}%",
                    result.remarks or "—",
                ))

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Results — {test_name}")
        dialog.resize(760, 460)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        heading = QLabel(f"Recorded results: {test_name}")
        heading.setStyleSheet(
            "color: #012D54; font-size: 18px; font-weight: 700;"
        )
        layout.addWidget(heading)

        results_table = QTableWidget()
        results_table.setColumnCount(5)
        results_table.setHorizontalHeaderLabels(
            ["Admission No.", "Student", "Marks", "Percentage", "Remarks"]
        )
        results_table.setRowCount(len(rows))
        results_table.verticalHeader().setVisible(False)
        results_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        results_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        for row_index, values in enumerate(rows):
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column_index in (0, 2, 3):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                results_table.setItem(
                    row_index,
                    column_index,
                    item,
                )

        layout.addWidget(results_table)

        if not rows:
            empty_label = QLabel(
                "No marks have been recorded for this test yet."
            )
            empty_label.setStyleSheet("color: #615F4B;")
            layout.addWidget(empty_label)

        close_button = QPushButton("Close")
        close_button.setObjectName("primaryDialogButton")
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.setFixedWidth(100)
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(
            close_button,
            alignment=Qt.AlignmentFlag.AlignRight,
        )

        dialog.exec()

    def edit_selected_test_results(self):
        selected_row = self.results_tests_table.currentRow()
        if selected_row < 0:
            QMessageBox.information(
                self,
                "Select a Test",
                "Select a test from the table first.",
            )
            return

        test_item = self.results_tests_table.item(selected_row, 0)
        test_id = int(test_item.data(Qt.ItemDataRole.UserRole))
        test_name = test_item.text()

        with SessionLocal() as session:
            test = session.get(
                TestModel,
                test_id,
            )
            if test is None:
                QMessageBox.warning(
                    self,
                    "Test Not Found",
                    "This test could not be found. Refresh the Results page and try again.",
                )
                return

            batch_id = test.batch_id
            max_marks = test.max_marks
            students = get_students_by_batch(
                session,
                batch_id=batch_id,
                include_inactive=True,
            )
            existing_results = get_test_results(session, test_id)
            existing_by_student = {
                result.student_id: result
                for result in existing_results
            }

            student_rows = [
                (
                    student.id,
                    student.admission_number or "-",
                    f"{student.first_name} {student.last_name or ''}".strip(),
                    student.status,
                    str(existing_by_student[student.id].marks)
                    if student.id in existing_by_student else "",
                    existing_by_student[student.id].remarks or ""
                    if student.id in existing_by_student else "",
                )
                for student in students
            ]

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Results — {test_name}")
        dialog.resize(850, 520)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        heading = QLabel(
            f"Enter or edit marks for {test_name} (maximum {max_marks})."
        )
        heading.setStyleSheet(
            "color: #012D54; font-size: 17px; font-weight: 700;"
        )
        layout.addWidget(heading)

        note = QLabel(
            "Leave Marks blank to keep a student unchanged or skip a new result. "
            "Enter 0 for a score of zero."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #615F4B; font-size: 12px;")
        layout.addWidget(note)

        results_table = QTableWidget()
        results_table.setColumnCount(5)
        results_table.setHorizontalHeaderLabels(
            ["Admission No.", "Student", "Status", "Marks", "Remarks"]
        )
        results_table.setRowCount(len(student_rows))
        results_table.verticalHeader().setVisible(False)
        results_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        for row_index, values in enumerate(student_rows):
            (
                student_id,
                admission_number,
                student_name,
                student_status,
                marks,
                remarks,
            ) = values
            admission_item = QTableWidgetItem(admission_number)
            admission_item.setFlags(
                admission_item.flags() & ~Qt.ItemFlag.ItemIsEditable
            )
            admission_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            name_item = QTableWidgetItem(student_name)
            name_item.setFlags(
                name_item.flags() & ~Qt.ItemFlag.ItemIsEditable
            )
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            name_item.setData(Qt.ItemDataRole.UserRole, student_id)

            status_item = QTableWidgetItem(student_status.title())
            status_item.setFlags(
                status_item.flags() & ~Qt.ItemFlag.ItemIsEditable
            )
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            marks_item = QTableWidgetItem(marks)
            marks_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            remarks_item = QTableWidgetItem(remarks)
            remarks_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

            if student_status != "ACTIVE":
                marks_item.setFlags(
                    marks_item.flags() & ~Qt.ItemFlag.ItemIsEditable
                )
                remarks_item.setFlags(
                    remarks_item.flags() & ~Qt.ItemFlag.ItemIsEditable
                )
                status_item.setToolTip(
                    "Only active students can have results entered or edited."
                )
                marks_item.setToolTip(
                    "Results for inactive or left students are read-only."
                )
                remarks_item.setToolTip(
                    "Results for inactive or left students are read-only."
                )

            results_table.setItem(row_index, 0, admission_item)
            results_table.setItem(row_index, 1, name_item)
            results_table.setItem(row_index, 2, status_item)
            results_table.setItem(row_index, 3, marks_item)
            results_table.setItem(row_index, 4, remarks_item)

        layout.addWidget(results_table)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if save_btn:
            save_btn.setObjectName("primaryDialogButton")
            save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if cancel_btn:
            cancel_btn.setObjectName("secondaryDialogButton")
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        entries = []
        for row_index in range(results_table.rowCount()):
            student_status = results_table.item(row_index, 2).text().strip().upper()
            if student_status != "ACTIVE":
                continue

            student_id = results_table.item(
                row_index, 1
            ).data(Qt.ItemDataRole.UserRole)
            marks_text = results_table.item(row_index, 3).text().strip()
            remarks = results_table.item(row_index, 4).text().strip()

            if not marks_text:
                continue

            try:
                marks = int(marks_text)
            except ValueError:
                QMessageBox.warning(
                    self,
                    "Invalid Marks",
                    f"Enter a whole number for {results_table.item(row_index, 1).text()}.",
                )
                return

            if marks < 0 or marks > max_marks:
                QMessageBox.warning(
                    self,
                    "Marks Out of Range",
                    f"Marks must be between 0 and {max_marks}.",
                )
                return

            entries.append({
                "student_id": student_id,
                "marks": marks,
                "remarks": remarks,
            })

        if not entries:
            QMessageBox.information(
                self,
                "No Marks Entered",
                "Enter marks for at least one student before saving.",
            )
            return

        try:
            with SessionLocal() as session:
                saved_count = save_test_results(
                    session,
                    test_id=test_id,
                    entries=entries,
                )
        except ValueError as error:
            QMessageBox.warning(self, "Could Not Save Results", str(error))
            return

        self.load_results_tests()
        QMessageBox.information(
            self,
            "Results Saved",
            f"Results saved for {saved_count} student(s).",
        )

    def create_test_dialog(self):
        with SessionLocal() as session:
            batches = get_active_batches(session)

        if not batches:
            QMessageBox.warning(
                self,
                "No Active Batches",
                "Create or reactivate a batch before creating a test.",
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Create Test")
        dialog.setMinimumWidth(440)

        form = QFormLayout(dialog)
        form.setContentsMargins(24, 20, 24, 20)
        form.setSpacing(14)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

        batch_input = QComboBox()
        for batch in batches:
            batch_input.addItem(batch.name, batch.id)

        current_batch_id = self.batch_selector.currentData()
        if current_batch_id is not None:
            batch_index = batch_input.findData(current_batch_id)
            if batch_index >= 0:
                batch_input.setCurrentIndex(batch_index)

        name_input = QLineEdit()
        name_input.setPlaceholderText("e.g. Chapter 1 Test")

        date_input = QDateEdit()
        date_input.setCalendarPopup(True)
        date_input.setDisplayFormat("dd MMM yyyy")
        date_input.setDate(QDate.currentDate())

        max_marks_input = QSpinBox()
        max_marks_input.setRange(1, 100000)
        max_marks_input.setValue(100)

        form.addRow("Batch", batch_input)
        form.addRow("Test name", name_input)
        form.addRow("Test date", date_input)
        form.addRow("Maximum marks", max_marks_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if save_btn:
            save_btn.setObjectName("primaryDialogButton")
            save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if cancel_btn:
            cancel_btn.setObjectName("secondaryDialogButton")
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        test_name = name_input.text().strip()
        if not test_name:
            QMessageBox.warning(
                self,
                "Test Name Required",
                "Please enter a name for this test.",
            )
            return

        with SessionLocal() as session:
            create_test(
                session,
                batch_id=int(batch_input.currentData()),
                name=test_name,
                test_date=date_input.date().toPyDate(),
                max_marks=max_marks_input.value(),
            )

        self.load_results_tests()
        QMessageBox.information(
            self,
            "Test Created",
            f'"{test_name}" has been created successfully.',
        )

    def create_fees_page(self):
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
            column_widths=[120, 170, 130, 120, 110, 110, 110, 110, 100, 120],
            stretch_column=1,
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
        if batch_id is None and self.batch_selector.currentData() is not None:
            batch_id = self.batch_selector.currentData()

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
        if batch_id is None and self.batch_selector.currentData() is not None:
            batch_id = self.batch_selector.currentData()
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

    def create_expenses_page(self):
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
            column_widths=[110, 200, 130, 150, 110, 110, 110, 110, 100, 120],
            stretch_column=1,
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

    def create_analysis_page(self):
        page = QWidget()
        page.setObjectName("analysisPage")

        main_layout = QVBoxLayout(page)
        main_layout.setContentsMargins(30, 24, 30, 24)
        main_layout.setSpacing(16)

        # ── Global Header & Controls ─────────────────────────────────────────
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        title = QLabel("Coaching Intelligence & Performance Analysis")
        title.setObjectName("analysisPageTitle")
        title.setStyleSheet("color: #012D54; font-size: 22px; font-weight: 800;")
        subtitle = QLabel("Student risk diagnostics, academic trajectory tracking, batch comparisons, and coaching operations.")
        subtitle.setObjectName("analysisPageSubtitle")
        subtitle.setStyleSheet("color: #615F4B; font-size: 13px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        # Batch filter
        self.analysis_batch_filter = QComboBox()
        self.analysis_batch_filter.setFixedHeight(38)
        self.analysis_batch_filter.setMinimumWidth(140)
        self.analysis_batch_filter.addItem("All Batches", None)
        self.analysis_batch_filter.setStyleSheet("""
            QComboBox {
                background: #FEFEFE;
                color: #012D54;
                border: 1px solid #E9DEBA;
                border-radius: 6px;
                padding: 4px 10px;
                font-weight: 600;
                font-size: 12px;
            }
        """)
        self.analysis_batch_filter.currentIndexChanged.connect(self.load_analysis)
        header_layout.addWidget(self.analysis_batch_filter)

        # Date / Period filter
        self.analysis_period_filter = QComboBox()
        self.analysis_period_filter.setFixedHeight(38)
        self.analysis_period_filter.setMinimumWidth(140)
        self.analysis_period_filter.addItem("All Time", "ALL")
        self.analysis_period_filter.addItem("Last 30 Days", "30D")
        self.analysis_period_filter.addItem("Last 90 Days", "90D")
        self.analysis_period_filter.addItem("Academic Year", "YEAR")
        self.analysis_period_filter.setStyleSheet("""
            QComboBox {
                background: #FEFEFE;
                color: #012D54;
                border: 1px solid #E9DEBA;
                border-radius: 6px;
                padding: 4px 10px;
                font-weight: 600;
                font-size: 12px;
            }
        """)
        self.analysis_period_filter.currentIndexChanged.connect(self.load_analysis)
        header_layout.addWidget(self.analysis_period_filter)

        # Export Report Dropdown Menu
        self.analysis_export_btn = QPushButton("📥 Export Report ▼")
        self.analysis_export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.analysis_export_btn.setFixedHeight(38)
        self.analysis_export_btn.setStyleSheet("""
            QPushButton {
                background: #E9DEBA;
                color: #012D54;
                border: 1px solid #D9B85F;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #D9B85F;
            }
        """)
        export_menu = QMenu(self)
        export_menu.setStyleSheet("""
            QMenu {
                background-color: #FEFEFE;
                border: 1px solid #E9DEBA;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 16px;
                color: #012D54;
                font-size: 12px;
                font-weight: 500;
            }
            QMenu::item:selected {
                background-color: #F8F6EA;
                color: #012D54;
                font-weight: 600;
            }
        """)
        act_risk = export_menu.addAction("🚨 Export Student Risk & Action Plan (CSV)")
        act_risk.triggered.connect(lambda: self.export_analysis_report("risk"))
        act_perf = export_menu.addAction("🎓 Export Student Performance Records (CSV)")
        act_perf.triggered.connect(lambda: self.export_analysis_report("performance"))
        act_batch = export_menu.addAction("📈 Export Batch Comparison (CSV)")
        act_batch.triggered.connect(lambda: self.export_analysis_report("batches"))
        act_syll = export_menu.addAction("📚 Export Syllabus Progress (CSV)")
        act_syll.triggered.connect(lambda: self.export_analysis_report("syllabus"))
        self.analysis_export_btn.setMenu(export_menu)
        header_layout.addWidget(self.analysis_export_btn)

        # Refresh Button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setFixedHeight(38)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: #012D54;
                color: #FEFEFE;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #04294D;
            }
        """)
        refresh_btn.clicked.connect(self.load_analysis)
        header_layout.addWidget(refresh_btn)

        main_layout.addLayout(header_layout)

        # ── Intelligence Tab Widget ──────────────────────────────────────────
        self.analysis_tabs = QTabWidget()
        self.analysis_tabs.setObjectName("analysisTabs")
        self.analysis_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #E9DEBA;
                background: #FEFEFE;
                border-radius: 8px;
                top: -1px;
            }
            QTabBar::tab {
                background: #F8F6EA;
                color: #012D54;
                font-weight: 600;
                font-size: 12px;
                padding: 10px 16px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border: 1px solid #E9DEBA;
                border-bottom: none;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background: #FEFEFE;
                color: #012D54;
                font-weight: 700;
                border-bottom: 2px solid #D9B85F;
            }
            QTabBar::tab:hover:!selected {
                background: #F1EBD3;
            }
        """)

        # Add tabs
        self.analysis_tabs.addTab(self._init_analysis_risk_tab(), "🚨 Student Risk & Improvement")
        self.analysis_tabs.addTab(self._init_analysis_overview_tab(), "📊 Coaching Overview")
        self.analysis_tabs.addTab(self._init_analysis_student_perf_tab(), "🎓 Student Performance")
        self.analysis_tabs.addTab(self._init_analysis_batches_tab(), "📈 Batches & Assessments")
        self.analysis_tabs.addTab(self._init_analysis_attendance_tab(), "📅 Attendance & Teaching")
        self.analysis_tabs.addTab(self._init_analysis_financial_tab(), "💰 Fees & Finances")

        main_layout.addWidget(self.analysis_tabs, 1)
        return page

    # ─────────────────────────────────────────────────────────────────────────
    # ── TAB 1: STUDENT RISK & IMPROVEMENT (CENTREPIECE) ──────────────────────
    # ─────────────────────────────────────────────────────────────────────────

    def _init_analysis_risk_tab(self):
        container = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Risk Summary Cards (4 Cards)
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)

        def _make_stat_card(title, def_val, color):
            card = QFrame()
            card.setStyleSheet("background-color: #FEFEFE; border: 1px solid #E9DEBA; border-radius: 8px;")
            l = QVBoxLayout(card)
            l.setContentsMargins(14, 12, 14, 12)
            l.setSpacing(2)
            t = QLabel(title)
            t.setStyleSheet("color: #615F4B; font-size: 11px; font-weight: 600;")
            v = QLabel(def_val)
            v.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: 800;")
            l.addWidget(t)
            l.addWidget(v)
            return card, v

        c1, self.risk_kpi_high = _make_stat_card("High Attention Required", "0", "#DC2626")
        c2, self.risk_kpi_moderate = _make_stat_card("Needs Attention", "0", "#D97706")
        c3, self.risk_kpi_improving = _make_stat_card("Improving Trajectory", "0", "#16A34A")
        c4, self.risk_kpi_declining = _make_stat_card("Declining Trajectory", "0", "#991B1B")

        kpi_row.addWidget(c1)
        kpi_row.addWidget(c2)
        kpi_row.addWidget(c3)
        kpi_row.addWidget(c4)
        layout.addLayout(kpi_row)

        # Section 1: At-Risk Students & Targeted Interventions
        sec_header = QHBoxLayout()
        sec_title = QLabel("Action Required: At-Risk Students & Next Teacher Steps")
        sec_title.setStyleSheet("color: #012D54; font-size: 15px; font-weight: 700;")
        sec_header.addWidget(sec_title)
        sec_header.addStretch()

        self.analysis_risk_filter = QComboBox()
        self.analysis_risk_filter.setFixedHeight(32)
        self.analysis_risk_filter.addItems(["All At-Risk Students", "High Attention Only", "Needs Attention Only", "All Assessed Students"])
        self.analysis_risk_filter.setStyleSheet("background: #FEFEFE; border: 1px solid #E9DEBA; border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 600;")
        self.analysis_risk_filter.currentIndexChanged.connect(self._filter_risk_table)
        sec_header.addWidget(self.analysis_risk_filter)

        self.analysis_risk_search = QLineEdit()
        self.analysis_risk_search.setPlaceholderText("Filter student...")
        self.analysis_risk_search.setFixedHeight(32)
        self.analysis_risk_search.setFixedWidth(160)
        self.analysis_risk_search.setStyleSheet("background: #FEFEFE; border: 1px solid #E9DEBA; border-radius: 4px; padding: 2px 8px; font-size: 11px;")
        self.analysis_risk_search.textChanged.connect(self._filter_risk_table)
        sec_header.addWidget(self.analysis_risk_search)

        layout.addLayout(sec_header)

        # Risk Table
        self.analysis_risk_table = QTableWidget()
        self.analysis_risk_table.setObjectName("analysisRiskTable")
        self.analysis_risk_table.setColumnCount(8)
        self.analysis_risk_table.setHorizontalHeaderLabels([
            "Student",
            "Batch",
            "Risk Level",
            "Observed Warning Signals",
            "Attendance %",
            "Avg Score %",
            "Suggested Next Action",
            "Action",
        ])
        self.analysis_risk_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.analysis_risk_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.analysis_risk_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.analysis_risk_table.setMinimumHeight(240)
        configure_table_ux(
            self.analysis_risk_table,
            column_widths=[160, 130, 120, 220, 110, 110, 220, 100],
            stretch_column=3,
        )
        layout.addWidget(self.analysis_risk_table)

        # Section 2: Progress Dynamics & Trajectory Table
        traj_title = QLabel("Performance Trajectory (Score Progress Deltas)")
        traj_title.setStyleSheet("color: #012D54; font-size: 15px; font-weight: 700; margin-top: 10px;")
        layout.addWidget(traj_title)

        self.analysis_trajectory_table = QTableWidget()
        self.analysis_trajectory_table.setObjectName("analysisTrajectoryTable")
        self.analysis_trajectory_table.setColumnCount(8)
        self.analysis_trajectory_table.setHorizontalHeaderLabels([
            "Student",
            "Batch",
            "Tests Taken",
            "Baseline Avg %",
            "Recent Avg %",
            "Delta (% Pts)",
            "Trajectory",
            "Action",
        ])
        self.analysis_trajectory_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.analysis_trajectory_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.analysis_trajectory_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.analysis_trajectory_table.setMinimumHeight(200)
        configure_table_ux(
            self.analysis_trajectory_table,
            column_widths=[160, 130, 110, 120, 120, 120, 120, 100],
            stretch_column=0,
        )
        layout.addWidget(self.analysis_trajectory_table)

        scroll.setWidget(inner)
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.addWidget(scroll)
        return container

    # ─────────────────────────────────────────────────────────────────────────
    # ── TAB 2: COACHING OVERVIEW ─────────────────────────────────────────────
    # ─────────────────────────────────────────────────────────────────────────

    def _init_analysis_overview_tab(self):
        container = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # High-level KPIs Row (5 cards)
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)

        def _make_overview_card(title, def_val):
            card = QFrame()
            card.setStyleSheet("background-color: #FEFEFE; border: 1px solid #E9DEBA; border-radius: 8px;")
            l = QVBoxLayout(card)
            l.setContentsMargins(14, 12, 14, 12)
            l.setSpacing(2)
            t = QLabel(title)
            t.setStyleSheet("color: #615F4B; font-size: 11px; font-weight: 600;")
            v = QLabel(def_val)
            v.setStyleSheet("color: #012D54; font-size: 20px; font-weight: 800;")
            l.addWidget(t)
            l.addWidget(v)
            return card, v

        c1, self.overview_kpi_active_students = _make_overview_card("Active Students", "0")
        c2, self.overview_kpi_tested_students = _make_overview_card("Students Tested", "0")
        c3, self.overview_kpi_avg_score = _make_overview_card("Avg Test Score", "0.0%")
        c4, self.overview_kpi_avg_attendance = _make_overview_card("Avg Attendance", "0.0%")
        c5, self.overview_kpi_syllabus_progress = _make_overview_card("Syllabus Covered", "0.0%")

        kpi_row.addWidget(c1)
        kpi_row.addWidget(c2)
        kpi_row.addWidget(c3)
        kpi_row.addWidget(c4)
        kpi_row.addWidget(c5)
        layout.addLayout(kpi_row)

        # Charts Row (Side-by-side)
        charts_row = QHBoxLayout()
        charts_row.setSpacing(14)

        self.overview_batch_score_chart = SimpleBarChartWidget("Batch Average Test Scores (%)", "%")
        self.overview_batch_score_chart.setMinimumHeight(240)
        charts_row.addWidget(self.overview_batch_score_chart, 1)

        self.overview_score_band_chart = SegmentedDistributionWidget("Overall Assessment Grade Distribution")
        self.overview_score_band_chart.setMinimumHeight(240)
        charts_row.addWidget(self.overview_score_band_chart, 1)

        layout.addLayout(charts_row)

        # Action Priorities Summary Card
        priorities_card = QFrame()
        priorities_card.setStyleSheet("background-color: #FEFEFE; border: 1px solid #E9DEBA; border-radius: 8px;")
        p_layout = QVBoxLayout(priorities_card)
        p_layout.setContentsMargins(18, 16, 18, 16)
        p_layout.setSpacing(8)

        p_title = QLabel("⚡ Key Coaching Priorities & Action Items")
        p_title.setStyleSheet("color: #012D54; font-size: 14px; font-weight: 700;")
        p_layout.addWidget(p_title)

        self.overview_action_priorities_label = QLabel("Loading coaching intelligence...")
        self.overview_action_priorities_label.setStyleSheet("color: #1F2937; font-size: 13px; line-height: 1.5;")
        self.overview_action_priorities_label.setWordWrap(True)
        p_layout.addWidget(self.overview_action_priorities_label)

        layout.addWidget(priorities_card)

        scroll.setWidget(inner)
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.addWidget(scroll)
        return container

    # ─────────────────────────────────────────────────────────────────────────
    # ── TAB 3: STUDENT PERFORMANCE ───────────────────────────────────────────
    # ─────────────────────────────────────────────────────────────────────────

    def _init_analysis_student_perf_tab(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Filter bar
        filt_row = QHBoxLayout()
        filt_row.setSpacing(10)

        self.student_perf_search = QLineEdit()
        self.student_perf_search.setPlaceholderText("Search by student name or admission number...")
        self.student_perf_search.setFixedHeight(34)
        self.student_perf_search.setStyleSheet("background: #FEFEFE; border: 1px solid #E9DEBA; border-radius: 6px; padding: 4px 10px; font-size: 12px;")
        self.student_perf_search.textChanged.connect(self._filter_student_perf_table)
        filt_row.addWidget(self.student_perf_search, 2)

        self.student_perf_trend_filter = QComboBox()
        self.student_perf_trend_filter.setFixedHeight(34)
        self.student_perf_trend_filter.addItems(["All Trends", "Improving", "Declining", "Stable", "Provisional"])
        self.student_perf_trend_filter.setStyleSheet("background: #FEFEFE; border: 1px solid #E9DEBA; border-radius: 6px; padding: 4px 10px; font-size: 12px; font-weight: 600;")
        self.student_perf_trend_filter.currentIndexChanged.connect(self._filter_student_perf_table)
        filt_row.addWidget(self.student_perf_trend_filter, 1)

        layout.addLayout(filt_row)

        # Performance Table
        self.analysis_student_perf_table = QTableWidget()
        self.analysis_student_perf_table.setObjectName("analysisStudentPerfTable")
        self.analysis_student_perf_table.setColumnCount(12)
        self.analysis_student_perf_table.setHorizontalHeaderLabels([
            "Adm No",
            "Student Name",
            "Batch",
            "Tests Taken",
            "Latest %",
            "Average %",
            "Highest %",
            "Lowest %",
            "vs Batch",
            "Attendance %",
            "Trend",
            "Action",
        ])
        self.analysis_student_perf_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.analysis_student_perf_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.analysis_student_perf_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        configure_table_ux(
            self.analysis_student_perf_table,
            column_widths=[110, 160, 120, 90, 80, 80, 80, 80, 80, 90, 90, 90],
            stretch_column=1,
        )

        layout.addWidget(self.analysis_student_perf_table, 1)
        return container

    # ─────────────────────────────────────────────────────────────────────────
    # ── TAB 4: BATCHES & ASSESSMENTS ─────────────────────────────────────────
    # ─────────────────────────────────────────────────────────────────────────

    def _init_analysis_batches_tab(self):
        container = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Batch Comparison Section
        b_title = QLabel("Cross-Batch Academic & Operational Comparison")
        b_title.setStyleSheet("color: #012D54; font-size: 15px; font-weight: 700;")
        layout.addWidget(b_title)

        self.analysis_batch_table = QTableWidget()
        self.analysis_batch_table.setObjectName("analysisBatchTable")
        self.analysis_batch_table.setColumnCount(7)
        self.analysis_batch_table.setHorizontalHeaderLabels([
            "Batch Name",
            "Active Students",
            "Tests Conducted",
            "Batch Avg Score %",
            "Batch Avg Attendance %",
            "Syllabus Covered %",
            "Sample Reliability",
        ])
        self.analysis_batch_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.analysis_batch_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.analysis_batch_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.analysis_batch_table.setMinimumHeight(180)
        configure_table_ux(
            self.analysis_batch_table,
            column_widths=[180, 120, 120, 130, 140, 130, 130],
            stretch_column=0,
        )
        layout.addWidget(self.analysis_batch_table)

        # Assessments Section
        t_title = QLabel("Assessment Results & Score Distributions")
        t_title.setStyleSheet("color: #012D54; font-size: 15px; font-weight: 700; margin-top: 10px;")
        layout.addWidget(t_title)

        self.analysis_tests_table = QTableWidget()
        self.analysis_tests_table.setObjectName("analysisTestsTable")
        self.analysis_tests_table.setColumnCount(9)
        self.analysis_tests_table.setHorizontalHeaderLabels([
            "Test Title",
            "Batch",
            "Date",
            "Max Marks",
            "Participation",
            "Batch Avg %",
            "Highest %",
            "Lowest %",
            "Performance Level",
        ])
        self.analysis_tests_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.analysis_tests_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.analysis_tests_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.analysis_tests_table.setMinimumHeight(220)
        configure_table_ux(
            self.analysis_tests_table,
            column_widths=[180, 130, 110, 100, 140, 110, 90, 90, 130],
            stretch_column=0,
        )
        layout.addWidget(self.analysis_tests_table)

        scroll.setWidget(inner)
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.addWidget(scroll)
        return container

    # ─────────────────────────────────────────────────────────────────────────
    # ── TAB 5: ATTENDANCE & TEACHING ─────────────────────────────────────────
    # ─────────────────────────────────────────────────────────────────────────

    def _init_analysis_attendance_tab(self):
        container = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Charts Row
        charts_row = QHBoxLayout()
        charts_row.setSpacing(14)

        self.attendance_band_chart = SegmentedDistributionWidget("Attendance Health Bands")
        self.attendance_band_chart.setMinimumHeight(220)
        charts_row.addWidget(self.attendance_band_chart, 1)

        self.teaching_status_chart = SegmentedDistributionWidget("Lesson Progress Breakdown")
        self.teaching_status_chart.setMinimumHeight(220)
        charts_row.addWidget(self.teaching_status_chart, 1)

        layout.addLayout(charts_row)

        # Attendance Alerts Table
        att_title = QLabel("Attendance Alerts (Students Below 75% or Consecutive Absences)")
        att_title.setStyleSheet("color: #012D54; font-size: 15px; font-weight: 700; margin-top: 6px;")
        layout.addWidget(att_title)

        self.analysis_attendance_alert_table = QTableWidget()
        self.analysis_attendance_alert_table.setObjectName("analysisAttendanceAlertTable")
        self.analysis_attendance_alert_table.setColumnCount(7)
        self.analysis_attendance_alert_table.setHorizontalHeaderLabels([
            "Student Name",
            "Batch",
            "Attendance %",
            "Total Classes",
            "Missed Classes",
            "Consecutive Absences",
            "Action",
        ])
        self.analysis_attendance_alert_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.analysis_attendance_alert_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.analysis_attendance_alert_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.analysis_attendance_alert_table.verticalHeader().setVisible(False)
        self.analysis_attendance_alert_table.verticalHeader().setDefaultSectionSize(40)
        configure_table_ux(
            self.analysis_attendance_alert_table,
            column_widths=[200, 140, 120, 100, 100, 150, 120],
            stretch_column=0,
            alternating_colors=True
        )
        layout.addWidget(self.analysis_attendance_alert_table)

        # Syllabus / Chapter Progress Table
        syll_title = QLabel("Chapter Syllabus Completion Progress")
        syll_title.setStyleSheet("color: #012D54; font-size: 15px; font-weight: 700; margin-top: 10px;")
        layout.addWidget(syll_title)

        self.analysis_syllabus_table = QTableWidget()
        self.analysis_syllabus_table.setObjectName("analysisSyllabusTable")
        self.analysis_syllabus_table.setColumnCount(5)
        self.analysis_syllabus_table.setHorizontalHeaderLabels([
            "Chapter / Unit",
            "Total Lessons",
            "Completed",
            "Remaining",
            "Completion %",
        ])
        self.analysis_syllabus_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.analysis_syllabus_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.analysis_syllabus_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.analysis_syllabus_table.verticalHeader().setVisible(False)
        self.analysis_syllabus_table.verticalHeader().setDefaultSectionSize(40)
        self.analysis_syllabus_table.setMinimumHeight(180)
        configure_table_ux(
            self.analysis_syllabus_table,
            column_widths=[260, 130, 130, 130, 140],
            stretch_column=0,
            alternating_colors=True
        )
        layout.addWidget(self.analysis_syllabus_table)

        scroll.setWidget(inner)
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.addWidget(scroll)
        return container

    # ─────────────────────────────────────────────────────────────────────────
    # ── TAB 6: FEES & FINANCES (PRESERVED) ───────────────────────────────────
    # ─────────────────────────────────────────────────────────────────────────

    def _init_analysis_financial_tab(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header with Deep-Dive button
        top_row = QHBoxLayout()
        f_title = QLabel("Financial Performance & Integrated Cash Flow")
        f_title.setStyleSheet("color: #012D54; font-size: 15px; font-weight: 700;")
        top_row.addWidget(f_title)
        top_row.addStretch()

        modal_btn = QPushButton("📊 Deep-Dive Report")
        modal_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        modal_btn.setFixedHeight(34)
        modal_btn.setStyleSheet("""
            QPushButton {
                background: #E9DEBA;
                color: #012D54;
                border: 1px solid #D9B85F;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #D9B85F;
            }
        """)
        modal_btn.clicked.connect(self.open_financial_analysis_dialog)
        top_row.addWidget(modal_btn)
        layout.addLayout(top_row)

        # 6 KPI Cards Grid
        kpi_grid = QGridLayout()
        kpi_grid.setHorizontalSpacing(14)
        kpi_grid.setVerticalSpacing(10)

        def make_analysis_kpi_card(card_title, default_val, text_color="#012D54"):
            card = QFrame()
            card.setStyleSheet("background-color: #FEFEFE; border: 1px solid #E9DEBA; border-radius: 8px;")
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(16, 12, 16, 12)
            c_layout.setSpacing(4)
            c_title = QLabel(card_title)
            c_title.setStyleSheet("color: #615F4B; font-size: 11px; font-weight: 600;")
            c_val = QLabel(default_val)
            c_val.setStyleSheet(f"color: {text_color}; font-size: 20px; font-weight: 700;")
            c_layout.addWidget(c_title)
            c_layout.addWidget(c_val)
            return card, c_val

        c_inflow, self.analysis_kpi_inflow = make_analysis_kpi_card("Cash Received (Fee Inflow)", "₹0.00", "#16A34A")
        c_outflow, self.analysis_kpi_outflow = make_analysis_kpi_card("Cash Paid (Expense Outflow)", "₹0.00", "#DC2626")
        c_netcash, self.analysis_kpi_net_cash = make_analysis_kpi_card("Net Cash Flow", "₹0.00", "#012D54")
        c_receivables, self.analysis_kpi_receivables = make_analysis_kpi_card("Student Fees Receivable", "₹0.00", "#D97706")
        c_payables, self.analysis_kpi_payables = make_analysis_kpi_card("Vendor Payables Due", "₹0.00", "#DC2626")
        c_accrual, self.analysis_kpi_accrual = make_analysis_kpi_card("Net Accrual Margin", "₹0.00", "#2563EB")

        kpi_grid.addWidget(c_inflow, 0, 0)
        kpi_grid.addWidget(c_outflow, 0, 1)
        kpi_grid.addWidget(c_netcash, 0, 2)
        kpi_grid.addWidget(c_receivables, 1, 0)
        kpi_grid.addWidget(c_payables, 1, 1)
        kpi_grid.addWidget(c_accrual, 1, 2)
        layout.addLayout(kpi_grid)

        # Monthly Comparison Table
        tbl_label = QLabel("Monthly Performance Trend (Fees vs. Expenses)")
        tbl_label.setStyleSheet("color: #012D54; font-size: 15px; font-weight: 700; margin-top: 8px;")
        layout.addWidget(tbl_label)

        self.analysis_table = QTableWidget()
        self.analysis_table.setObjectName("analysisTable")
        self.analysis_table.setColumnCount(7)
        self.analysis_table.setHorizontalHeaderLabels([
            "Month",
            "Fees Collected (Cash)",
            "Expenses Paid (Cash)",
            "Net Cash Flow",
            "Fees Billed",
            "Expenses Incurred",
            "Accrual Margin",
        ])
        self.analysis_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.analysis_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.analysis_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.analysis_table.verticalHeader().setVisible(False)
        self.analysis_table.verticalHeader().setDefaultSectionSize(42)

        configure_table_ux(
            self.analysis_table,
            column_widths=[140, 160, 160, 150, 150, 150, 150],
            stretch_column=None,
            alternating_colors=True
        )

        layout.addWidget(self.analysis_table, 1)
        return container

    # ─────────────────────────────────────────────────────────────────────────
    # ── DATA LOADING & REFRESH ───────────────────────────────────────────────
    # ─────────────────────────────────────────────────────────────────────────

    def load_analysis(self):
        if not hasattr(self, "analysis_table"):
            return

        batch_id = self.analysis_batch_filter.currentData() if hasattr(self, "analysis_batch_filter") else None
        period_key = self.analysis_period_filter.currentData() if hasattr(self, "analysis_period_filter") else "ALL"

        today = date.today()
        start_date = None
        end_date = None

        if period_key == "30D":
            start_date = today - timedelta(days=30)
            end_date = today
        elif period_key == "90D":
            start_date = today - timedelta(days=90)
            end_date = today
        elif period_key == "YEAR":
            ay_year = today.year if today.month >= 4 else today.year - 1
            start_date = date(ay_year, 4, 1)
            end_date = today

        with SessionLocal() as session:
            financial_summary = get_financial_summary(session)
            monthly_data = get_monthly_financial_comparison(session)
            overview_data = get_coaching_overview(session, batch_id=batch_id, start_date=start_date, end_date=end_date)
            risk_data = get_student_risk_analysis(session, batch_id=batch_id, start_date=start_date, end_date=end_date)
            trajectory_data = get_student_improvement_analysis(session, batch_id=batch_id, start_date=start_date, end_date=end_date)
            perf_data = get_student_performance_records(session, batch_id=batch_id, start_date=start_date, end_date=end_date)
            batches_data = get_batch_comparison_data(session)
            tests_data = get_tests_analytics(session, batch_id=batch_id, start_date=start_date, end_date=end_date)
            attendance_data = get_attendance_analytics(session, batch_id=batch_id, start_date=start_date, end_date=end_date)
            teaching_data = get_teaching_analytics(session, batch_id=batch_id)

        # Cache data for instant in-page search / filtering
        self._cached_risk_data = risk_data
        self._cached_trajectory_data = trajectory_data
        self._cached_perf_data = perf_data

        # Populate all tabs
        self._load_analysis_financial(financial_summary, monthly_data)
        self._load_analysis_risk(risk_data, trajectory_data)
        self._load_analysis_overview(overview_data, batches_data, tests_data)
        self._load_analysis_student_perf(perf_data)
        self._load_analysis_batches_tests(batches_data, tests_data)
        self._load_analysis_attendance_teaching(attendance_data, teaching_data)

    def _load_analysis_financial(self, summary, monthly_data):
        self.analysis_kpi_inflow.setText(f"₹{summary['fees_collected']:,.2f}")
        self.analysis_kpi_outflow.setText(f"₹{summary['expenses_paid']:,.2f}")

        net_cash = summary["net_cash_flow"]
        self.analysis_kpi_net_cash.setText(f"₹{net_cash:,.2f}")
        self.analysis_kpi_net_cash.setStyleSheet(
            "color: #16A34A; font-size: 20px; font-weight: 700;" if net_cash >= 0
            else "color: #DC2626; font-size: 20px; font-weight: 700;"
        )

        self.analysis_kpi_receivables.setText(f"₹{summary['outstanding_student_fees']:,.2f}")
        self.analysis_kpi_payables.setText(f"₹{summary['outstanding_expenses']:,.2f}")

        net_accrual = summary["net_accrual_income"]
        self.analysis_kpi_accrual.setText(f"₹{net_accrual:,.2f}")
        self.analysis_kpi_accrual.setStyleSheet(
            "color: #2563EB; font-size: 20px; font-weight: 700;" if net_accrual >= 0
            else "color: #DC2626; font-size: 20px; font-weight: 700;"
        )

        self.analysis_table.setRowCount(len(monthly_data))
        for row, item in enumerate(monthly_data):
            m_item = QTableWidgetItem(item["month_name"])
            m_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_table.setItem(row, 0, m_item)

            fc_item = QTableWidgetItem(f"₹{item['fees_collected']:,.2f}")
            fc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_table.setItem(row, 1, fc_item)

            ep_item = QTableWidgetItem(f"₹{item['expenses_paid']:,.2f}")
            ep_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_table.setItem(row, 2, ep_item)

            ncf = item["net_cash_flow"]
            ncf_item = QTableWidgetItem(f"₹{ncf:,.2f}")
            ncf_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            ncf_item.setForeground(Qt.GlobalColor.darkGreen if ncf >= 0 else Qt.GlobalColor.darkRed)
            self.analysis_table.setItem(row, 3, ncf_item)

            fb_item = QTableWidgetItem(f"₹{item['fees_billed']:,.2f}")
            fb_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_table.setItem(row, 4, fb_item)

            ei_item = QTableWidgetItem(f"₹{item['expenses_incurred']:,.2f}")
            ei_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_table.setItem(row, 5, ei_item)

            nam = item["net_accrual_margin"]
            nam_item = QTableWidgetItem(f"₹{nam:,.2f}")
            nam_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            nam_item.setForeground(Qt.GlobalColor.blue if nam >= 0 else Qt.GlobalColor.darkRed)
            self.analysis_table.setItem(row, 6, nam_item)

    def _load_analysis_risk(self, risk_data, trajectory_data):
        high_cnt = sum(1 for r in risk_data if r["risk_level"] == "High Attention")
        mod_cnt = sum(1 for r in risk_data if r["risk_level"] == "Needs Attention")
        imp_cnt = sum(1 for t in trajectory_data if t["trend"] == "Improving")
        dec_cnt = sum(1 for t in trajectory_data if t["trend"] == "Declining")

        self.risk_kpi_high.setText(str(high_cnt))
        self.risk_kpi_moderate.setText(str(mod_cnt))
        self.risk_kpi_improving.setText(str(imp_cnt))
        self.risk_kpi_declining.setText(str(dec_cnt))

        self._filter_risk_table()

        # Populate Trajectory Table
        self.analysis_trajectory_table.setRowCount(len(trajectory_data))
        for row, t in enumerate(trajectory_data):
            s_item = QTableWidgetItem(t["name"])
            self.analysis_trajectory_table.setItem(row, 0, s_item)

            b_item = QTableWidgetItem(t["batch_name"])
            b_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_trajectory_table.setItem(row, 1, b_item)

            tc_item = QTableWidgetItem(str(t["tests_count"]))
            tc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_trajectory_table.setItem(row, 2, tc_item)

            init_item = QTableWidgetItem(f"{t['initial_avg']:.1f}%" if t['initial_avg'] is not None else "—")
            init_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_trajectory_table.setItem(row, 3, init_item)

            rec_item = QTableWidgetItem(f"{t['recent_avg']:.1f}%" if t['recent_avg'] is not None else "—")
            rec_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_trajectory_table.setItem(row, 4, rec_item)

            d = t["delta"]
            delta_str = f"{d:+.1f}%" if d is not None else "—"
            delta_item = QTableWidgetItem(delta_str)
            delta_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if d is not None:
                delta_item.setForeground(Qt.GlobalColor.darkGreen if d > 0 else (Qt.GlobalColor.darkRed if d < 0 else Qt.GlobalColor.black))
            self.analysis_trajectory_table.setItem(row, 5, delta_item)

            trend_name = t["trend"]
            bg, fg = ("#DCFCE7", "#15803D") if trend_name == "Improving" else (
                ("#FEE2E2", "#B91C1C") if trend_name == "Declining" else (
                    ("#DBEAFE", "#1D4ED8") if trend_name == "Stable" else ("#F3F4F6", "#6B7280")
                )
            )
            self.analysis_trajectory_table.setCellWidget(row, 6, self._create_badge_widget(trend_name, bg, fg))
            self.analysis_trajectory_table.setCellWidget(row, 7, self._create_action_btn_widget(t["student_id"]))

    def _filter_risk_table(self):
        if not hasattr(self, "_cached_risk_data"):
            return

        mode = self.analysis_risk_filter.currentText()
        query = self.analysis_risk_search.text().strip().lower()

        filtered = []
        for r in self._cached_risk_data:
            if mode == "High Attention Only" and r["risk_level"] != "High Attention":
                continue
            if mode == "Needs Attention Only" and r["risk_level"] != "Needs Attention":
                continue
            if mode == "All At-Risk Students" and r["risk_level"] not in ("High Attention", "Needs Attention"):
                continue

            if query:
                s_name = r["student_name"].lower()
                adm = (r["admission_number"] or "").lower()
                b_name = (r["batch_name"] or "").lower()
                if query not in s_name and query not in adm and query not in b_name:
                    continue

            filtered.append(r)

        self.analysis_risk_table.setRowCount(len(filtered))
        for row, r in enumerate(filtered):
            name_text = f"{r['student_name']} ({r['admission_number']})" if r["admission_number"] else r["student_name"]
            n_item = QTableWidgetItem(name_text)
            self.analysis_risk_table.setItem(row, 0, n_item)

            b_item = QTableWidgetItem(r["batch_name"])
            b_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_risk_table.setItem(row, 1, b_item)

            lvl = r["risk_level"]
            lbl_text = lvl.upper()
            bg, fg = ("#FEE2E2", "#B91C1C") if lvl == "High Attention" else (
                ("#FEF3C7", "#B45309") if lvl == "Needs Attention" else (
                    ("#DCFCE7", "#15803D") if lvl == "On Track" else ("#F3F4F6", "#6B7280")
                )
            )
            self.analysis_risk_table.setCellWidget(row, 2, self._create_badge_widget(lbl_text, bg, fg))

            reasons_str = "; ".join(r["reasons"]) if r["reasons"] else "No critical flags"
            r_item = QTableWidgetItem(reasons_str)
            r_item.setToolTip(reasons_str)
            self.analysis_risk_table.setItem(row, 3, r_item)

            att_str = f"{r['attendance_pct']:.1f}%" if r["attendance_pct"] is not None else "—"
            att_item = QTableWidgetItem(att_str)
            att_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_risk_table.setItem(row, 4, att_item)

            sc_str = f"{r['avg_score_pct']:.1f}%" if r["avg_score_pct"] is not None else "—"
            sc_item = QTableWidgetItem(sc_str)
            sc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_risk_table.setItem(row, 5, sc_item)

            rec_item = QTableWidgetItem(r["recommendation"])
            rec_item.setToolTip(r["recommendation"])
            self.analysis_risk_table.setItem(row, 6, rec_item)

            self.analysis_risk_table.setCellWidget(row, 7, self._create_action_btn_widget(r["student_id"]))

    def _load_analysis_overview(self, overview_data, batches_data, tests_data=None):
        self.overview_kpi_active_students.setText(str(overview_data.get("active_students", 0)))
        tested_cnt = overview_data.get("students_tested", 0)
        tot_cnt = overview_data.get("active_students", 0)
        t_pct = (tested_cnt / tot_cnt * 100.0) if tot_cnt > 0 else 0.0
        self.overview_kpi_tested_students.setText(f"{tested_cnt} ({t_pct:.0f}%)")

        self.overview_kpi_avg_score.setText(f"{overview_data.get('avg_score_pct', 0.0):.1f}%")
        self.overview_kpi_avg_attendance.setText(f"{overview_data.get('avg_attendance_pct', 0.0):.1f}%")
        self.overview_kpi_syllabus_progress.setText(f"{overview_data.get('syllabus_completion_pct', 0.0):.1f}%")

        # Assessment Scores Chart (Batch comparison when All Batches, or test-wise when a batch is selected)
        batch_id = self.analysis_batch_filter.currentData() if hasattr(self, "analysis_batch_filter") else None

        if batch_id is not None and tests_data:
            selected_name = self.analysis_batch_filter.currentText()
            self.overview_batch_score_chart.set_title(f"Test Scores — {selected_name} (%)")
            t_items = []
            test_list = tests_data.get("tests", [])
            for t in test_list:
                sc = float(t.get("avg_pct", 0.0))
                appeared = t.get("students_appeared", 0)
                expected = t.get("expected_students", 0)
                color = "#16A34A" if sc >= 75 else ("#D9B85F" if sc >= 50 else "#DC2626")
                sublabel = f"{appeared}/{expected} appeared · Max {t.get('max_marks', 100)}"
                t_items.append({
                    "label": t.get("test_name", "Test"),
                    "value": sc,
                    "color": color,
                    "sublabel": sublabel,
                })
            self.overview_batch_score_chart.set_data(t_items)
        else:
            self.overview_batch_score_chart.set_title("Batch Average Test Scores (%)")
            tested_batches = [b for b in batches_data if b.get("tests_conducted", 0) > 0]
            if tested_batches:
                tested_batches.sort(
                    key=lambda b: (b.get("avg_score_pct", 0.0), b.get("tests_conducted", 0), b.get("active_students", 0)),
                    reverse=True,
                )
                display_batches = tested_batches[:8]
            else:
                active_batches = [b for b in batches_data if b.get("active_students", 0) > 0]
                active_batches.sort(key=lambda b: b.get("active_students", 0), reverse=True)
                display_batches = active_batches[:8]

            b_items = []
            for b in display_batches:
                sc = float(b.get("avg_score_pct", 0.0))
                t_count = b.get("tests_conducted", 0)
                s_count = b.get("active_students", 0)
                if t_count > 0:
                    color = "#16A34A" if sc >= 75 else ("#D9B85F" if sc >= 50 else "#DC2626")
                    sublabel = f"{s_count} student{'s' if s_count != 1 else ''} · {t_count} test{'s' if t_count != 1 else ''}"
                    val_text = f"{sc:.1f}%"
                else:
                    color = "#9CA3AF"
                    sublabel = f"{s_count} student{'s' if s_count != 1 else ''} · No tests yet"
                    val_text = "No tests"

                b_items.append({
                    "label": b.get("batch_name", "Batch"),
                    "value": sc,
                    "color": color,
                    "sublabel": sublabel,
                    "val_text": val_text,
                })
            self.overview_batch_score_chart.set_data(b_items)

        # Score distribution chips
        bands_data = [
            {"label": "Distinction (≥80%)", "count": overview_data.get("score_bands", {}).get("Distinction (>=80%)", 0), "color": "#16A34A"},
            {"label": "Merit (60-79%)", "count": overview_data.get("score_bands", {}).get("Merit (60-79%)", 0), "color": "#2563EB"},
            {"label": "Pass (40-59%)", "count": overview_data.get("score_bands", {}).get("Pass (40-59%)", 0), "color": "#D97706"},
            {"label": "Needs Help (<40%)", "count": overview_data.get("score_bands", {}).get("Needs Help (<40%)", 0), "color": "#DC2626"},
        ]
        self.overview_score_band_chart.set_data(bands_data)

        # Action Priorities
        items = overview_data.get("action_items", [])
        if items:
            bullet_html = "<ul style='margin: 4px 0; padding-left: 20px;'>"
            for it in items:
                bullet_html += f"<li style='margin-bottom: 6px;'><b>{it['name']} ({it['batch_name']}):</b> {it['level']} — {it['reason']}. <i>Action: {it['action']}</i></li>"
            bullet_html += "</ul>"
            self.overview_action_priorities_label.setText(bullet_html)
        else:
            self.overview_action_priorities_label.setText("✅ <b>All systems operational!</b> No high-risk academic or attendance anomalies detected.")

    def _load_analysis_student_perf(self, perf_data):
        self._filter_student_perf_table()

    def _filter_student_perf_table(self):
        if not hasattr(self, "_cached_perf_data"):
            return

        query = self.student_perf_search.text().strip().lower()
        trend_mode = self.student_perf_trend_filter.currentText()

        filtered = []
        for p in self._cached_perf_data:
            if trend_mode != "All Trends" and p["trend"] != trend_mode:
                continue

            if query:
                s_name = p["name"].lower()
                adm = (p["admission_number"] or "").lower()
                b_name = (p["batch_name"] or "").lower()
                if query not in s_name and query not in adm and query not in b_name:
                    continue

            filtered.append(p)

        self.analysis_student_perf_table.setRowCount(len(filtered))
        for row, p in enumerate(filtered):
            adm_item = QTableWidgetItem(p["admission_number"] or "—")
            adm_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_student_perf_table.setItem(row, 0, adm_item)

            name_item = QTableWidgetItem(p["name"])
            self.analysis_student_perf_table.setItem(row, 1, name_item)

            b_item = QTableWidgetItem(p["batch_name"])
            b_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_student_perf_table.setItem(row, 2, b_item)

            t_item = QTableWidgetItem(str(p["tests_taken"]))
            t_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_student_perf_table.setItem(row, 3, t_item)

            lat_str = f"{p['latest_pct']:.1f}%" if p["latest_pct"] is not None else "—"
            lat_item = QTableWidgetItem(lat_str)
            lat_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_student_perf_table.setItem(row, 4, lat_item)

            avg_str = f"{p['avg_pct']:.1f}%" if p["avg_pct"] is not None else "—"
            avg_item = QTableWidgetItem(avg_str)
            avg_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_student_perf_table.setItem(row, 5, avg_item)

            h_str = f"{p['high_pct']:.1f}%" if p["high_pct"] is not None else "—"
            h_item = QTableWidgetItem(h_str)
            h_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_student_perf_table.setItem(row, 6, h_item)

            l_str = f"{p['low_pct']:.1f}%" if p["low_pct"] is not None else "—"
            l_item = QTableWidgetItem(l_str)
            l_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_student_perf_table.setItem(row, 7, l_item)

            diff = p["diff_from_batch"]
            diff_str = f"{diff:+.1f}%" if diff is not None else "—"
            diff_item = QTableWidgetItem(diff_str)
            diff_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if diff is not None:
                diff_item.setForeground(Qt.GlobalColor.darkGreen if diff >= 0 else Qt.GlobalColor.darkRed)
            self.analysis_student_perf_table.setItem(row, 8, diff_item)

            att_str = f"{p['attendance_pct']:.1f}%" if p["attendance_pct"] is not None else "—"
            att_item = QTableWidgetItem(att_str)
            att_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_student_perf_table.setItem(row, 9, att_item)

            tr = p["trend"]
            bg, fg = ("#DCFCE7", "#15803D") if tr == "Improving" else (
                ("#FEE2E2", "#B91C1C") if tr == "Declining" else (
                    ("#DBEAFE", "#1D4ED8") if tr == "Stable" else ("#F3F4F6", "#6B7280")
                )
            )
            self.analysis_student_perf_table.setCellWidget(row, 10, self._create_badge_widget(tr, bg, fg))
            self.analysis_student_perf_table.setCellWidget(row, 11, self._create_action_btn_widget(p["student_id"]))

    def _load_analysis_batches_tests(self, batches_data, tests_data):
        # Batch Comparison Table
        self.analysis_batch_table.setRowCount(len(batches_data))
        for row, b in enumerate(batches_data):
            self.analysis_batch_table.setItem(row, 0, QTableWidgetItem(b["batch_name"]))

            act_item = QTableWidgetItem(str(b["active_students"]))
            act_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_batch_table.setItem(row, 1, act_item)

            tc_item = QTableWidgetItem(str(b["tests_conducted"]))
            tc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_batch_table.setItem(row, 2, tc_item)

            sc_item = QTableWidgetItem(f"{b['avg_score_pct']:.1f}%")
            sc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_batch_table.setItem(row, 3, sc_item)

            att_item = QTableWidgetItem(f"{b['attendance_pct']:.1f}%")
            att_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_batch_table.setItem(row, 4, att_item)

            syll_item = QTableWidgetItem(f"{b['syllabus_pct']:.1f}%")
            syll_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_batch_table.setItem(row, 5, syll_item)

            rel_text = "Adequate Data" if b["reliable_sample"] else "Low Data Sample"
            rel_bg, rel_fg = ("#DCFCE7", "#15803D") if b["reliable_sample"] else ("#FEF3C7", "#B45309")
            self.analysis_batch_table.setCellWidget(row, 6, self._create_badge_widget(rel_text, rel_bg, rel_fg))

        # Tests Table
        test_list = tests_data.get("tests", [])
        self.analysis_tests_table.setRowCount(len(test_list))
        for row, t in enumerate(test_list):
            self.analysis_tests_table.setItem(row, 0, QTableWidgetItem(t["test_name"]))

            b_item = QTableWidgetItem(t["batch_name"])
            b_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_tests_table.setItem(row, 1, b_item)

            d_item = QTableWidgetItem(t["test_date"])
            d_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_tests_table.setItem(row, 2, d_item)

            tm_item = QTableWidgetItem(str(t["max_marks"]))
            tm_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_tests_table.setItem(row, 3, tm_item)

            part_item = QTableWidgetItem(f"{t['students_appeared']} / {t['expected_students']} ({t['participation_pct']:.0f}%)")
            part_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_tests_table.setItem(row, 4, part_item)

            avg_item = QTableWidgetItem(f"{t['avg_pct']:.1f}%")
            avg_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_tests_table.setItem(row, 5, avg_item)

            h_item = QTableWidgetItem(f"{t['high_pct']:.1f}%")
            h_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            h_item.setForeground(Qt.GlobalColor.darkGreen)
            self.analysis_tests_table.setItem(row, 6, h_item)

            l_item = QTableWidgetItem(f"{t['low_pct']:.1f}%")
            l_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if t['low_pct'] < 40:
                l_item.setForeground(Qt.GlobalColor.darkRed)
            self.analysis_tests_table.setItem(row, 7, l_item)

            st_badge = "Strong (≥65%)" if t["avg_pct"] >= 65 else ("Satisfactory (50-64%)" if t["avg_pct"] >= 50 else "Needs Review (<50%)")
            st_bg, st_fg = ("#DCFCE7", "#15803D") if t["avg_pct"] >= 65 else (("#DBEAFE", "#1D4ED8") if t["avg_pct"] >= 50 else ("#FEE2E2", "#B91C1C"))
            self.analysis_tests_table.setCellWidget(row, 8, self._create_badge_widget(st_badge, st_bg, st_fg))

    def _load_analysis_attendance_teaching(self, att_data, teach_data):
        # Attendance bands
        a_bands = [
            {"label": "Excellent (>90%)", "count": att_data.get("distribution_bands", {}).get("Excellent (>90%)", 0), "color": "#16A34A"},
            {"label": "Good (75-90%)", "count": att_data.get("distribution_bands", {}).get("Good (75-90%)", 0), "color": "#2563EB"},
            {"label": "Moderate (60-75%)", "count": att_data.get("distribution_bands", {}).get("Moderate (60-75%)", 0), "color": "#D97706"},
            {"label": "Critical (<60%)", "count": att_data.get("distribution_bands", {}).get("Critical (<60%)", 0), "color": "#DC2626"},
        ]
        self.attendance_band_chart.set_data(a_bands)

        # Teaching status bands
        t_bands = [
            {"label": "Completed", "count": teach_data.get("completed_lessons", 0), "color": "#16A34A"},
            {"label": "Planned", "count": teach_data.get("planned_lessons", 0), "color": "#2563EB"},
            {"label": "In Progress", "count": teach_data.get("in_progress_lessons", 0), "color": "#D97706"},
            {"label": "Cancelled", "count": teach_data.get("cancelled_lessons", 0), "color": "#6B7280"},
        ]
        self.teaching_status_chart.set_data(t_bands)

        # Attendance Alerts Table
        low_students = att_data.get("low_attendance_students", [])
        self.analysis_attendance_alert_table.setRowCount(len(low_students))
        for row, s in enumerate(low_students):
            n_text = f"{s['name']} ({s['admission_number']})" if s.get("admission_number") else s["name"]
            self.analysis_attendance_alert_table.setItem(row, 0, QTableWidgetItem(n_text))

            b_item = QTableWidgetItem(s["batch_name"])
            b_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_attendance_alert_table.setItem(row, 1, b_item)

            att_item = QTableWidgetItem(f"{s['attendance_pct']:.1f}%")
            att_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            att_item.setForeground(Qt.GlobalColor.darkRed if s["attendance_pct"] < 60 else Qt.GlobalColor.darkYellow)
            self.analysis_attendance_alert_table.setItem(row, 2, att_item)

            tot_item = QTableWidgetItem(str(s["total_classes"]))
            tot_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_attendance_alert_table.setItem(row, 3, tot_item)

            mis_item = QTableWidgetItem(str(s["classes_missed"]))
            mis_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_attendance_alert_table.setItem(row, 4, mis_item)

            con_item = QTableWidgetItem(str(s["consecutive_absent"]))
            con_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if s["consecutive_absent"] >= 3:
                con_item.setForeground(Qt.GlobalColor.darkRed)
            self.analysis_attendance_alert_table.setItem(row, 5, con_item)

            self.analysis_attendance_alert_table.setCellWidget(row, 6, self._create_action_btn_widget(s["student_id"]))

        # Syllabus / Chapter Progress Table
        chapters = teach_data.get("chapters", [])
        self.analysis_syllabus_table.setRowCount(len(chapters))
        for row, ch in enumerate(chapters):
            self.analysis_syllabus_table.setItem(row, 0, QTableWidgetItem(ch["chapter"]))

            tot_item = QTableWidgetItem(str(ch["total"]))
            tot_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_syllabus_table.setItem(row, 1, tot_item)

            comp_item = QTableWidgetItem(str(ch["completed"]))
            comp_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_syllabus_table.setItem(row, 2, comp_item)

            rem_item = QTableWidgetItem(str(ch["remaining"]))
            rem_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.analysis_syllabus_table.setItem(row, 3, rem_item)

            cp = ch["completion_pct"]
            pct_item = QTableWidgetItem(f"{cp:.1f}%")
            pct_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            pct_item.setForeground(Qt.GlobalColor.darkGreen if cp >= 100 else (Qt.GlobalColor.blue if cp >= 50 else Qt.GlobalColor.black))
            self.analysis_syllabus_table.setItem(row, 4, pct_item)

    # ─────────────────────────────────────────────────────────────────────────
    # ── UI HELPERS & EXPORT ──────────────────────────────────────────────────
    # ─────────────────────────────────────────────────────────────────────────

    def _create_badge_widget(self, text: str, bg_color: str, text_color: str) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"""
            background-color: {bg_color};
            color: {text_color};
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 4px;
        """)
        lay.addWidget(lbl)
        return w

    def _create_action_btn_widget(self, student_id: int, label: str = "View Profile") -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn = QPushButton(label)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(26)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #E9DEBA;
                color: #012D54;
                border: 1px solid #D9B85F;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 2px 8px;
            }
            QPushButton:hover {
                background-color: #D9B85F;
            }
        """)
        btn.clicked.connect(lambda ch, sid=student_id: self.view_student(sid))
        lay.addWidget(btn)
        return w

    def export_analysis_report(self, report_type="risk"):
        batch_id = self.analysis_batch_filter.currentData() if hasattr(self, "analysis_batch_filter") else None
        with SessionLocal() as session:
            csv_content = export_analytics_report_csv(session, report_type=report_type, batch_id=batch_id)

        default_filename = f"tams_{report_type}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            f"Export {report_type.title()} Report to CSV",
            default_filename,
            "CSV Files (*.csv)",
        )
        if not filepath:
            return

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                f.write(csv_content)
            QMessageBox.information(
                self,
                "Export Complete",
                f"Report exported successfully to:\n{filepath}",
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export report: {e}",
            )

    # ═════════════════════════════════════════════════════════════════════════
    # ── TEACHING MODULE ──────────────────────────────────────────────────────
    # ═════════════════════════════════════════════════════════════════════════

    def create_teaching_page(self):
        page = QWidget()
        page.setObjectName("teachingPage")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 28)
        layout.setSpacing(18)

        # ── Header ────────────────────────────────────────────────────────
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        title_lbl = QLabel("Teaching")
        title_lbl.setObjectName("teachingPageTitle")
        subtitle_lbl = QLabel("Plan lessons, record classes, track homework and syllabus progress.")
        subtitle_lbl.setObjectName("teachingPageSubtitle")
        title_box.addWidget(title_lbl)
        title_box.addWidget(subtitle_lbl)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        def _nav_btn(text, primary=True):
            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(40)
            if primary:
                btn.setStyleSheet("""
                    QPushButton {
                        background: #012D54;
                        color: #FEFEFE;
                        border: none;
                        border-radius: 8px;
                        padding: 8px 16px;
                        font-weight: 600;
                        font-size: 13px;
                    }
                    QPushButton:hover { background: #04294D; }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background: #E9DEBA;
                        color: #012D54;
                        border: 1px solid #D9B85F;
                        border-radius: 8px;
                        padding: 8px 16px;
                        font-weight: 600;
                        font-size: 13px;
                    }
                    QPushButton:hover { background: #D9B85F; }
                """)
            return btn

        plan_btn = _nav_btn("＋ Plan Lesson")
        plan_btn.clicked.connect(self.open_add_lesson_dialog)
        header_layout.addWidget(plan_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        record_btn = _nav_btn("📝 Record Class", primary=False)
        record_btn.clicked.connect(lambda: self.open_record_class_dialog())
        header_layout.addWidget(record_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        hw_btn = _nav_btn("＋ Add Homework", primary=False)
        hw_btn.clicked.connect(self.open_add_homework_dialog)
        header_layout.addWidget(hw_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        layout.addLayout(header_layout)

        # ── KPI Cards ─────────────────────────────────────────────────────
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(14)

        def make_teaching_kpi_card(card_title, default_val, text_color="#012D54"):
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

        card1, self.teaching_kpi_planned   = make_teaching_kpi_card("Lessons Planned",    "0", "#012D54")
        card2, self.teaching_kpi_completed = make_teaching_kpi_card("Lessons Completed",  "0", "#16A34A")
        card3, self.teaching_kpi_upcoming  = make_teaching_kpi_card("Upcoming (7 days)",  "0", "#2563EB")
        card4, self.teaching_kpi_overdue   = make_teaching_kpi_card("Overdue Lessons",    "0", "#DC2626")
        card5, self.teaching_kpi_pct       = make_teaching_kpi_card("Syllabus Progress",  "0%", "#D97706")

        for c in (card1, card2, card3, card4, card5):
            kpi_layout.addWidget(c, 1)
        layout.addLayout(kpi_layout)

        # ── Filters Toolbar ───────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.lesson_search_input = QLineEdit()
        self.lesson_search_input.setPlaceholderText("Search by title, chapter, or topic…")
        self.lesson_search_input.setClearButtonEnabled(True)
        self.lesson_search_input.setFixedHeight(36)
        self.lesson_search_input.setStyleSheet("""
            QLineEdit {
                background-color: #FEFEFE;
                color: #012D54;
                border: 1px solid #E9DEBA;
                border-radius: 7px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QLineEdit:focus { border: 1.5px solid #012D54; }
        """)
        self.lesson_search_input.textChanged.connect(self.load_teaching)
        toolbar.addWidget(self.lesson_search_input, 2)

        self.lesson_batch_filter = QComboBox()
        self.lesson_batch_filter.setFixedHeight(36)
        self.lesson_batch_filter.addItem("All Batches", None)
        with SessionLocal() as session:
            _batches = get_active_batches(session)
            for _b in _batches:
                self.lesson_batch_filter.addItem(_b.name, _b.id)
        self.lesson_batch_filter.currentIndexChanged.connect(self.load_teaching)
        toolbar.addWidget(self.lesson_batch_filter, 1)

        self.lesson_status_filter = QComboBox()
        self.lesson_status_filter.setFixedHeight(36)
        self.lesson_status_filter.addItem("All Statuses", None)
        self.lesson_status_filter.addItem("Planned",     "PLANNED")
        self.lesson_status_filter.addItem("In Progress", "IN_PROGRESS")
        self.lesson_status_filter.addItem("Completed",   "COMPLETED")
        self.lesson_status_filter.addItem("Cancelled",   "CANCELLED")
        self.lesson_status_filter.currentIndexChanged.connect(self.load_teaching)
        toolbar.addWidget(self.lesson_status_filter, 1)

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
            QPushButton:hover { background-color: #E9DEBA; color: #012D54; }
        """)
        reset_btn.clicked.connect(self.reset_teaching_filters)
        toolbar.addWidget(reset_btn)
        layout.addLayout(toolbar)

        # ── Tab Widget ────────────────────────────────────────────────────
        self.teaching_tabs = QTabWidget()
        self.teaching_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #E9DEBA;
                border-radius: 8px;
                background: #FEFEFE;
            }
            QTabBar::tab {
                background: #F8F6EA;
                color: #615F4B;
                border: 1px solid #E9DEBA;
                border-bottom: none;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 500;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 3px;
            }
            QTabBar::tab:selected {
                background: #012D54;
                color: #FEFEFE;
                font-weight: 600;
            }
            QTabBar::tab:hover:!selected { background: #E9DEBA; color: #012D54; }
        """)

        # ── Tab 0: Lessons ───────────────────────────────────────────────
        tab_lessons = QWidget()
        tab_lessons_layout = QVBoxLayout(tab_lessons)
        tab_lessons_layout.setContentsMargins(0, 0, 0, 0)
        tab_lessons_layout.setSpacing(0)

        self.lessons_table = QTableWidget()
        self.lessons_table.setObjectName("lessonsTable")
        self.lessons_table.setColumnCount(8)
        self.lessons_table.setHorizontalHeaderLabels([
            "Date", "Title", "Chapter", "Topic", "Duration", "Status", "Batch", "Actions",
        ])
        self.lessons_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.lessons_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.lessons_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.lessons_table.verticalHeader().setVisible(False)
        self.lessons_table.verticalHeader().setDefaultSectionSize(48)
        self.lessons_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.lessons_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.lessons_table.setAlternatingRowColors(True)
        self.lessons_table.setStyleSheet("""
            QTableWidget {
                background: #FEFEFE;
                alternate-background-color: #F8F6EA;
                border: none;
                gridline-color: #F1EBD3;
                font-size: 13px;
                color: #1F2937;
                selection-background-color: #E9DEBA;
                selection-color: #012D54;
            }
            QTableWidget::item { padding: 6px 8px; border-bottom: 1px solid #F1EBD3; }
            QHeaderView::section {
                background: #012D54;
                color: #FEFEFE;
                padding: 9px 8px;
                border: none;
                font-weight: 600;
                font-size: 12px;
            }
        """)
        h = self.lessons_table.horizontalHeader()
        h.setStretchLastSection(False)
        for c in range(8):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
        self.lessons_table.setColumnWidth(0, 120)  # Date
        self.lessons_table.setColumnWidth(1, 240)  # Title
        self.lessons_table.setColumnWidth(2, 170)  # Chapter
        self.lessons_table.setColumnWidth(3, 190)  # Topic
        self.lessons_table.setColumnWidth(4, 110)  # Duration
        self.lessons_table.setColumnWidth(5, 130)  # Status
        self.lessons_table.setColumnWidth(6, 150)  # Batch
        self.lessons_table.setColumnWidth(7, 230)  # Actions
        self.lessons_table.setItemDelegate(TAMSItemDelegate(self.lessons_table))

        tab_lessons_layout.addWidget(self.lessons_table)

        self.lessons_empty_label = QLabel("No lessons match the current filters. Click '＋ Plan Lesson' to create one.")
        self.lessons_empty_label.setStyleSheet("""
            QLabel {
                color: #615F4B; font-size: 13px; padding: 24px;
                background: #F8F6EA; border: 1px dashed #D9B85F; border-radius: 8px;
                margin: 10px;
            }
        """)
        self.lessons_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lessons_empty_label.setVisible(False)
        tab_lessons_layout.addWidget(self.lessons_empty_label)

        self.teaching_tabs.addTab(tab_lessons, "Lessons")

        # ── Tab 1: Class History ─────────────────────────────────────────
        tab_history = QWidget()
        tab_history_layout = QVBoxLayout(tab_history)
        tab_history_layout.setContentsMargins(0, 0, 0, 0)
        tab_history_layout.setSpacing(0)

        self.class_records_table = QTableWidget()
        self.class_records_table.setObjectName("classRecordsTable")
        self.class_records_table.setColumnCount(7)
        self.class_records_table.setHorizontalHeaderLabels([
            "Date", "Batch", "Chapter", "Topic Taught", "Topics Completed", "Notes", "Actions",
        ])
        self.class_records_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.class_records_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.class_records_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.class_records_table.verticalHeader().setVisible(False)
        self.class_records_table.verticalHeader().setDefaultSectionSize(48)
        self.class_records_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.class_records_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.class_records_table.setAlternatingRowColors(True)
        self.class_records_table.setStyleSheet("""
            QTableWidget {
                background: #FEFEFE;
                alternate-background-color: #F8F6EA;
                border: none;
                gridline-color: #F1EBD3;
                font-size: 13px;
                color: #1F2937;
                selection-background-color: #E9DEBA;
                selection-color: #012D54;
            }
            QTableWidget::item { padding: 6px 8px; border-bottom: 1px solid #F1EBD3; }
            QHeaderView::section {
                background: #012D54;
                color: #FEFEFE;
                padding: 9px 8px;
                border: none;
                font-weight: 600;
                font-size: 12px;
            }
        """)
        h2 = self.class_records_table.horizontalHeader()
        h2.setStretchLastSection(False)
        for c in range(7):
            h2.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
        self.class_records_table.setColumnWidth(0, 120)  # Date
        self.class_records_table.setColumnWidth(1, 150)  # Batch
        self.class_records_table.setColumnWidth(2, 170)  # Chapter
        self.class_records_table.setColumnWidth(3, 220)  # Topic Taught
        self.class_records_table.setColumnWidth(4, 200)  # Topics Completed
        self.class_records_table.setColumnWidth(5, 230)  # Notes
        self.class_records_table.setColumnWidth(6, 120)  # Actions
        self.class_records_table.setItemDelegate(TAMSItemDelegate(self.class_records_table))

        tab_history_layout.addWidget(self.class_records_table)

        self.class_records_empty_label = QLabel("No class sessions recorded yet. Click '📝 Record Class' to add one.")
        self.class_records_empty_label.setStyleSheet("""
            QLabel {
                color: #615F4B; font-size: 13px; padding: 24px;
                background: #F8F6EA; border: 1px dashed #D9B85F; border-radius: 8px;
                margin: 10px;
            }
        """)
        self.class_records_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.class_records_empty_label.setVisible(False)
        tab_history_layout.addWidget(self.class_records_empty_label)

        self.teaching_tabs.addTab(tab_history, "Class History")

        # ── Tab 2: Homework ──────────────────────────────────────────────
        tab_hw = QWidget()
        tab_hw_layout = QVBoxLayout(tab_hw)
        tab_hw_layout.setContentsMargins(0, 0, 0, 0)
        tab_hw_layout.setSpacing(0)

        self.homework_table = QTableWidget()
        self.homework_table.setObjectName("homeworkTable")
        self.homework_table.setColumnCount(6)
        self.homework_table.setHorizontalHeaderLabels([
            "Title", "Batch", "Assigned", "Due", "Status", "Actions",
        ])
        self.homework_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.homework_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.homework_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.homework_table.verticalHeader().setVisible(False)
        self.homework_table.verticalHeader().setDefaultSectionSize(48)
        self.homework_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.homework_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.homework_table.setAlternatingRowColors(True)
        self.homework_table.setStyleSheet("""
            QTableWidget {
                background: #FEFEFE;
                alternate-background-color: #F8F6EA;
                border: none;
                gridline-color: #F1EBD3;
                font-size: 13px;
                color: #1F2937;
                selection-background-color: #E9DEBA;
                selection-color: #012D54;
            }
            QTableWidget::item { padding: 6px 8px; border-bottom: 1px solid #F1EBD3; }
            QHeaderView::section {
                background: #012D54;
                color: #FEFEFE;
                padding: 9px 8px;
                border: none;
                font-weight: 600;
                font-size: 12px;
            }
        """)
        h3 = self.homework_table.horizontalHeader()
        h3.setStretchLastSection(False)
        for c in range(6):
            h3.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
        self.homework_table.setColumnWidth(0, 240)  # Title
        self.homework_table.setColumnWidth(1, 150)  # Batch
        self.homework_table.setColumnWidth(2, 120)  # Assigned
        self.homework_table.setColumnWidth(3, 120)  # Due
        self.homework_table.setColumnWidth(4, 130)  # Status
        self.homework_table.setColumnWidth(5, 120)  # Actions
        self.homework_table.setItemDelegate(TAMSItemDelegate(self.homework_table))

        tab_hw_layout.addWidget(self.homework_table)

        self.homework_empty_label = QLabel("No homework assigned yet. Click '＋ Add Homework' to create one.")
        self.homework_empty_label.setStyleSheet("""
            QLabel {
                color: #615F4B; font-size: 13px; padding: 24px;
                background: #F8F6EA; border: 1px dashed #D9B85F; border-radius: 8px;
                margin: 10px;
            }
        """)
        self.homework_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.homework_empty_label.setVisible(False)
        tab_hw_layout.addWidget(self.homework_empty_label)

        self.teaching_tabs.addTab(tab_hw, "Homework")

        # ── Tab 3: Progress ──────────────────────────────────────────────
        tab_progress = QWidget()
        tab_progress_layout = QVBoxLayout(tab_progress)
        tab_progress_layout.setContentsMargins(0, 0, 0, 0)
        tab_progress_layout.setSpacing(0)

        self.progress_table = QTableWidget()
        self.progress_table.setObjectName("progressTable")
        self.progress_table.setColumnCount(5)
        self.progress_table.setHorizontalHeaderLabels([
            "Chapter", "Total Lessons", "Completed", "Cancelled", "Progress",
        ])
        self.progress_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.progress_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.progress_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.progress_table.verticalHeader().setVisible(False)
        self.progress_table.verticalHeader().setDefaultSectionSize(44)
        self.progress_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.progress_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.progress_table.setAlternatingRowColors(True)
        self.progress_table.setStyleSheet("""
            QTableWidget {
                background: #FEFEFE;
                alternate-background-color: #F8F6EA;
                border: none;
                gridline-color: #F1EBD3;
                font-size: 13px;
                color: #1F2937;
                selection-background-color: #E9DEBA;
                selection-color: #012D54;
            }
            QTableWidget::item { padding: 6px 8px; border-bottom: 1px solid #F1EBD3; }
            QHeaderView::section {
                background: #012D54;
                color: #FEFEFE;
                padding: 9px 8px;
                border: none;
                font-weight: 600;
                font-size: 12px;
            }
        """)
        h4 = self.progress_table.horizontalHeader()
        h4.setStretchLastSection(False)
        for c in range(5):
            h4.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
        self.progress_table.setColumnWidth(0, 260)  # Chapter
        self.progress_table.setColumnWidth(1, 140)  # Total Lessons
        self.progress_table.setColumnWidth(2, 130)  # Completed
        self.progress_table.setColumnWidth(3, 130)  # Cancelled
        self.progress_table.setColumnWidth(4, 140)  # Progress
        self.progress_table.setItemDelegate(TAMSItemDelegate(self.progress_table))

        tab_progress_layout.addWidget(self.progress_table)

        self.progress_empty_label = QLabel("No chapter data. Plan lessons with chapter names to see progress.")
        self.progress_empty_label.setStyleSheet("""
            QLabel {
                color: #615F4B; font-size: 13px; padding: 24px;
                background: #F8F6EA; border: 1px dashed #D9B85F; border-radius: 8px;
                margin: 10px;
            }
        """)
        self.progress_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_empty_label.setVisible(False)
        tab_progress_layout.addWidget(self.progress_empty_label)

        self.teaching_tabs.addTab(tab_progress, "Progress")

        layout.addWidget(self.teaching_tabs, 1)
        return page

    # ── load_teaching ─────────────────────────────────────────────────────

    def load_teaching(self):
        if not hasattr(self, "lessons_table"):
            return

        def _small_btn(label, color, hover, text_color="#FEFEFE", border=None):
            b = QPushButton(label)
            b.setFixedHeight(26)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            border_css = f"border: 1px solid {border};" if border else "border: none;"
            b.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: {text_color};
                    {border_css}
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 0 6px;
                }}
                QPushButton:hover {{ background-color: {hover}; }}
            """)
            return b

        batch_id = self.lesson_batch_filter.currentData()
        if batch_id is None:
            batch_id = self.batch_selector.currentData()
        search = self.lesson_search_input.text().strip() or None
        status = self.lesson_status_filter.currentData()

        with SessionLocal() as session:
            lessons  = get_lessons(session, batch_id=batch_id, status=status, search=search)
            summary  = get_teaching_summary(session, batch_id=batch_id)
            records  = get_class_records(session, batch_id=batch_id)
            homeworks = get_homeworks(session, batch_id=batch_id)
            chapters = get_chapters_progress(session, batch_id=batch_id)

        # KPI cards
        self.teaching_kpi_planned.setText(str(summary.get("planned", 0)))
        self.teaching_kpi_completed.setText(str(summary.get("completed", 0)))
        self.teaching_kpi_upcoming.setText(str(summary.get("upcoming", 0)))
        self.teaching_kpi_overdue.setText(str(summary.get("overdue", 0)))
        pct = summary.get("completion_pct", 0)
        self.teaching_kpi_pct.setText(f"{pct:.0f}%")

        # ── Lessons table ────────────────────────────────────────────────
        STATUS_COLORS = {
            "PLANNED":     ("#DBEAFE", "#1D4ED8"),
            "IN_PROGRESS": ("#FEF3C7", "#B45309"),
            "COMPLETED":   ("#DCFCE7", "#15803D"),
            "CANCELLED":   ("#F3F4F6", "#6B7280"),
        }

        self.lessons_table.setRowCount(len(lessons))
        for row, lesson in enumerate(lessons):
            from app.database.models.batch import Batch as _Batch  # local import avoids circularity

            date_str  = lesson.planned_date.strftime("%d %b %Y") if lesson.planned_date else "—"
            dur_str   = f"{lesson.duration_minutes} min" if lesson.duration_minutes else "—"
            batch_name = lesson.batch.name if lesson.batch else "—"

            for col, (val, align) in enumerate([
                (date_str,             Qt.AlignmentFlag.AlignCenter),
                (lesson.title,         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                (lesson.chapter or "—", Qt.AlignmentFlag.AlignCenter),
                (lesson.topic or "—",  Qt.AlignmentFlag.AlignCenter),
                (dur_str,              Qt.AlignmentFlag.AlignCenter),
            ]):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(align)
                self.lessons_table.setItem(row, col, item)

            # Status badge
            st = lesson.status
            bg, fg = STATUS_COLORS.get(st, ("#F3F4F6", "#6B7280"))
            status_widget = QWidget()
            sl = QHBoxLayout(status_widget)
            sl.setContentsMargins(0, 0, 0, 0)
            sl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge = QLabel(st.replace("_", " ").title())
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(f"background-color:{bg}; color:{fg}; font-size:11px; font-weight:700; padding:4px 8px; border-radius:4px;")
            sl.addWidget(badge)
            self.lessons_table.setCellWidget(row, 5, status_widget)

            batch_item = QTableWidgetItem(batch_name)
            batch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lessons_table.setItem(row, 6, batch_item)

            # Action buttons
            action_w = QWidget()
            action_l = QHBoxLayout(action_w)
            action_l.setContentsMargins(4, 2, 4, 2)
            action_l.setSpacing(4)
            action_l.setAlignment(Qt.AlignmentFlag.AlignCenter)

            detail_btn = _small_btn("Detail", "#E9DEBA", "#D9B85F", "#012D54", "#D9B85F")
            detail_btn.clicked.connect(lambda _, lid=lesson.id: self.open_lesson_detail_dialog(lid))
            action_l.addWidget(detail_btn)

            rec_btn = _small_btn("Record", "#012D54", "#04294D")
            rec_btn.clicked.connect(lambda _, lid=lesson.id: self.open_record_class_dialog(lid))
            action_l.addWidget(rec_btn)

            edit_btn = _small_btn("Edit", "#FEFEFE", "#F1EBD3", "#012D54", "#E9DEBA")
            edit_btn.clicked.connect(lambda _, lid=lesson.id: self.open_edit_lesson_dialog(lid))
            action_l.addWidget(edit_btn)

            if st not in ("COMPLETED", "CANCELLED"):
                done_btn = _small_btn("✓", "#16A34A", "#15803D")
                done_btn.setToolTip("Mark as Completed")
                done_btn.clicked.connect(lambda _, lid=lesson.id: self.mark_lesson_done(lid))
                action_l.addWidget(done_btn)

            del_btn = _small_btn("✕", "#FEE2E2", "#FCA5A5", "#B91C1C", "#FCA5A5")
            del_btn.setToolTip("Delete lesson")
            del_btn.clicked.connect(lambda _, lid=lesson.id: self.confirm_delete_lesson(lid))
            action_l.addWidget(del_btn)

            self.lessons_table.setCellWidget(row, 7, action_w)

        self.lessons_empty_label.setVisible(len(lessons) == 0)
        self.lessons_table.setVisible(len(lessons) > 0)

        # ── Class Records table ──────────────────────────────────────────
        self.class_records_table.setRowCount(len(records))
        for row, rec in enumerate(records):
            date_str = rec.class_date.strftime("%d %b %Y") if rec.class_date else "—"
            batch_name = rec.batch.name if rec.batch else "—"
            completed_str = rec.topics_completed or "—"
            notes_str = (rec.notes or "").strip() or "—"

            for col, (val, align) in enumerate([
                (date_str,              Qt.AlignmentFlag.AlignCenter),
                (batch_name,            Qt.AlignmentFlag.AlignCenter),
                (rec.chapter or "—",    Qt.AlignmentFlag.AlignCenter),
                (rec.topic or "—",      Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                (completed_str,         Qt.AlignmentFlag.AlignCenter),
                (notes_str,             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            ]):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(align)
                self.class_records_table.setItem(row, col, item)

            action_w2 = QWidget()
            action_l2 = QHBoxLayout(action_w2)
            action_l2.setContentsMargins(4, 2, 4, 2)
            action_l2.setSpacing(4)
            action_l2.setAlignment(Qt.AlignmentFlag.AlignCenter)

            edit2 = _small_btn("Edit", "#E9DEBA", "#D9B85F", "#012D54", "#D9B85F")
            edit2.clicked.connect(lambda _, rid=rec.id: self.open_edit_class_record_dialog(rid))
            action_l2.addWidget(edit2)

            del2 = _small_btn("✕", "#FEE2E2", "#FCA5A5", "#B91C1C", "#FCA5A5")
            del2.clicked.connect(lambda _, rid=rec.id: self.confirm_delete_class_record(rid))
            action_l2.addWidget(del2)

            self.class_records_table.setCellWidget(row, 6, action_w2)

        self.class_records_empty_label.setVisible(len(records) == 0)
        self.class_records_table.setVisible(len(records) > 0)

        # ── Homework table ───────────────────────────────────────────────
        today = date.today()
        self.homework_table.setRowCount(len(homeworks))
        for row, hw in enumerate(homeworks):
            assigned_str = hw.assigned_date.strftime("%d %b %Y") if hw.assigned_date else "—"
            due_str      = hw.due_date.strftime("%d %b %Y")      if hw.due_date else "—"
            batch_name   = hw.batch.name if hw.batch else "—"

            for col, (val, align) in enumerate([
                (hw.title,   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                (batch_name, Qt.AlignmentFlag.AlignCenter),
                (assigned_str, Qt.AlignmentFlag.AlignCenter),
                (due_str,    Qt.AlignmentFlag.AlignCenter),
            ]):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(align)
                self.homework_table.setItem(row, col, item)

            # Status badge
            hw_status_w = QWidget()
            hw_sl = QHBoxLayout(hw_status_w)
            hw_sl.setContentsMargins(0, 0, 0, 0)
            hw_sl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hw_badge = QLabel()
            hw_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if hw.due_date and hw.due_date < today:
                hw_badge.setText("Overdue")
                hw_badge.setStyleSheet("background-color:#FEE2E2; color:#B91C1C; font-size:11px; font-weight:700; padding:4px 8px; border-radius:4px;")
            elif hw.due_date:
                hw_badge.setText("Upcoming")
                hw_badge.setStyleSheet("background-color:#DBEAFE; color:#1D4ED8; font-size:11px; font-weight:700; padding:4px 8px; border-radius:4px;")
            else:
                hw_badge.setText("No Due Date")
                hw_badge.setStyleSheet("background-color:#F3F4F6; color:#6B7280; font-size:11px; font-weight:700; padding:4px 8px; border-radius:4px;")
            hw_sl.addWidget(hw_badge)
            self.homework_table.setCellWidget(row, 4, hw_status_w)

            action_w3 = QWidget()
            action_l3 = QHBoxLayout(action_w3)
            action_l3.setContentsMargins(4, 2, 4, 2)
            action_l3.setSpacing(4)
            action_l3.setAlignment(Qt.AlignmentFlag.AlignCenter)

            edit3 = _small_btn("Edit", "#E9DEBA", "#D9B85F", "#012D54", "#D9B85F")
            edit3.clicked.connect(lambda _, hid=hw.id: self.open_edit_homework_dialog(hid))
            action_l3.addWidget(edit3)

            del3 = _small_btn("✕", "#FEE2E2", "#FCA5A5", "#B91C1C", "#FCA5A5")
            del3.clicked.connect(lambda _, hid=hw.id: self.confirm_delete_homework(hid))
            action_l3.addWidget(del3)

            self.homework_table.setCellWidget(row, 5, action_w3)

        self.homework_empty_label.setVisible(len(homeworks) == 0)
        self.homework_table.setVisible(len(homeworks) > 0)

        # ── Progress table ───────────────────────────────────────────────
        self.progress_table.setRowCount(len(chapters))
        for row, ch in enumerate(chapters):
            ch_name = ch.get("chapter") or "(No Chapter)"
            total   = ch.get("total", 0)
            done    = ch.get("completed", 0)
            canc    = ch.get("cancelled", 0)
            pct_ch  = ch.get("completion_pct", 0.0)

            ch_item = QTableWidgetItem(ch_name)
            ch_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.progress_table.setItem(row, 0, ch_item)

            for col, val in [(1, total), (2, done), (3, canc)]:
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.progress_table.setItem(row, col, item)

            pct_item = QTableWidgetItem(f"{pct_ch:.0f}%")
            pct_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if pct_ch >= 80:
                pct_item.setForeground(Qt.GlobalColor.darkGreen)
            elif pct_ch >= 40:
                pct_item.setForeground(Qt.GlobalColor.darkYellow)
            else:
                pct_item.setForeground(Qt.GlobalColor.darkRed)
            self.progress_table.setItem(row, 4, pct_item)

        self.progress_empty_label.setVisible(len(chapters) == 0)
        self.progress_table.setVisible(len(chapters) > 0)

    # ── Filter reset ──────────────────────────────────────────────────────

    def reset_teaching_filters(self):
        self.lesson_search_input.blockSignals(True)
        self.lesson_batch_filter.blockSignals(True)
        self.lesson_status_filter.blockSignals(True)

        self.lesson_search_input.clear()
        self.lesson_batch_filter.setCurrentIndex(0)
        self.lesson_status_filter.setCurrentIndex(0)

        self.lesson_search_input.blockSignals(False)
        self.lesson_batch_filter.blockSignals(False)
        self.lesson_status_filter.blockSignals(False)

        self.load_teaching()

    # ── Lesson action handlers ────────────────────────────────────────────

    def open_add_lesson_dialog(self):
        dlg = LessonDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_teaching()

    def open_edit_lesson_dialog(self, lesson_id: int):
        dlg = LessonDialog(lesson_id=lesson_id, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_teaching()

    def open_lesson_detail_dialog(self, lesson_id: int):
        dlg = LessonDetailDialog(lesson_id, self)
        dlg.exec()

    def open_record_class_dialog(self, lesson_id: int | None = None):
        # RecordClassDialog doesn't take lesson_id; user selects from combo inside
        dlg = RecordClassDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_teaching()

    def open_edit_class_record_dialog(self, record_id: int):
        dlg = RecordClassDialog(record_id=record_id, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_teaching()

    def open_add_homework_dialog(self):
        dlg = HomeworkDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_teaching()

    def open_edit_homework_dialog(self, hw_id: int):
        dlg = HomeworkDialog(hw_id=hw_id, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_teaching()

    def confirm_delete_lesson(self, lesson_id: int):
        result = QMessageBox.question(
            self,
            "Delete Lesson",
            "Are you sure you want to delete this lesson? This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if result == QMessageBox.StandardButton.Yes:
            try:
                with SessionLocal() as session:
                    delete_lesson(session, lesson_id)
                self.load_teaching()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete lesson: {e}")

    def confirm_delete_class_record(self, record_id: int):
        result = QMessageBox.question(
            self,
            "Delete Class Record",
            "Delete this class session record?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if result == QMessageBox.StandardButton.Yes:
            try:
                with SessionLocal() as session:
                    delete_class_record(session, record_id)
                self.load_teaching()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete class record: {e}")

    def confirm_delete_homework(self, hw_id: int):
        result = QMessageBox.question(
            self,
            "Delete Homework",
            "Delete this homework assignment?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if result == QMessageBox.StandardButton.Yes:
            try:
                with SessionLocal() as session:
                    delete_homework(session, hw_id)
                self.load_teaching()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete homework: {e}")

    def mark_lesson_done(self, lesson_id: int):
        try:
            with SessionLocal() as session:
                mark_lesson_completed(session, lesson_id)
            self.load_teaching()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to mark lesson complete: {e}")

    def create_students_page(self):

        page = QWidget()
        page.setObjectName("studentsPage")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 28)
        layout.setSpacing(18)

        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(4)

        title = QLabel("Students")
        title.setObjectName("studentsPageTitle")

        subtitle = QLabel(
            "Manage your students and their information."
        )
        subtitle.setObjectName("studentsPageSubtitle")

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        header_layout.addLayout(title_box)
        header_layout.addStretch()

        # Add student button
        add_student_button = QPushButton("+ Add Student")
        add_student_button.setObjectName("addStudentButton")
        add_student_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        add_student_button.clicked.connect(self.open_add_student_dialog)

        header_layout.addWidget(add_student_button, alignment=Qt.AlignmentFlag.AlignVCenter)

        layout.addLayout(header_layout)

        # Search and filter toolbar
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(12)

        self.student_search_input = QLineEdit()
        self.student_search_input.setPlaceholderText("Search by name, admission no, parent, or phone...")
        self.student_search_input.setClearButtonEnabled(True)
        self.student_search_input.setFixedHeight(38)
        self.student_search_input.setStyleSheet("""
            QLineEdit {
                background-color: #FEFEFE;
                color: #012D54;
                border: 1px solid #E9DEBA;
                border-radius: 7px;
                padding: 6px 14px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1.5px solid #012D54;
            }
        """)
        self.student_search_input.textChanged.connect(self.filter_students_table)
        filter_layout.addWidget(self.student_search_input, 1)

        self.student_count_badge = QLabel("Total: 0 students")
        self.student_count_badge.setStyleSheet("""
            QLabel {
                color: #012D54;
                font-size: 12px;
                font-weight: 600;
                background-color: #E9DEBA;
                padding: 6px 14px;
                border-radius: 6px;
            }
        """)
        filter_layout.addWidget(self.student_count_badge, alignment=Qt.AlignmentFlag.AlignVCenter)

        layout.addLayout(filter_layout)

        # Students table
        self.students_table = QTableWidget()
        self.students_table.setObjectName("studentsTable")
        self.students_table.setVerticalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAsNeeded
    )

        self.students_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.students_table.setMinimumHeight(300)
        self.students_table.verticalHeader().setDefaultSectionSize(55)

        self.students_table.setColumnCount(7)
        self.students_table.setHorizontalHeaderLabels([
            "Admission No.",
            "Student Name",
            "Parent",
            "Phone",
            "Batch",
            "Status",
            "Action",
        ])

        self.students_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.students_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.students_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        configure_table_ux(
            self.students_table,
            column_widths=[120, 170, 150, 130, 140, 100, 110],
            stretch_column=1,
        )

        self.students_table.setRowCount(0)
        layout.addWidget(self.students_table, 1)

        return page
    def load_students(self):
        batch_id = self.batch_selector.currentData()

        with SessionLocal() as session:
            students = get_students_by_batch(
                session,
                batch_id=batch_id,
            )

            self.students_table.setRowCount(len(students))

            for row, student in enumerate(students):
                parent_name = ""
                parent_phone = ""

                if student.parent:
                    parent_name = student.parent.name or ""
                    parent_phone = (
                        student.parent.whatsapp_number
                        or student.parent.phone
                        or ""
                    )

                batch_name = ""
                if student.batch:
                    batch_name = student.batch.name

                adm_item = QTableWidgetItem(student.admission_number or "")
                adm_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.students_table.setItem(row, 0, adm_item)

                name_item = QTableWidgetItem(
                    f"{student.first_name} {student.last_name or ''}".strip()
                )
                name_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                self.students_table.setItem(row, 1, name_item)

                parent_item = QTableWidgetItem(parent_name)
                parent_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                self.students_table.setItem(row, 2, parent_item)

                phone_item = QTableWidgetItem(parent_phone)
                phone_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.students_table.setItem(row, 3, phone_item)

                batch_item = QTableWidgetItem(batch_name)
                batch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.students_table.setItem(row, 4, batch_item)

                status_item = QTableWidgetItem(student.status)
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.students_table.setItem(row, 5, status_item)

                # Action buttons
                action_widget = QWidget()
                action_layout = QHBoxLayout(action_widget)
                action_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                action_layout.setContentsMargins(6, 4, 6, 4)
                action_layout.setSpacing(8)

                # View button
                view_button = QPushButton("View")
                view_button.setFixedSize(65, 28)
                view_button.setCursor(
                    Qt.CursorShape.PointingHandCursor
                )

                view_button.setStyleSheet("""
                    QPushButton {
                        background-color: #012D54;
                        color: #FEFEFE;
                        border: 1px solid #012D54;
                        border-radius: 6px;
                        font-size: 12px;
                        font-weight: bold;
                    }

                    QPushButton:hover {
                        background-color: #04294D;
                    }

                    QPushButton:pressed {
                        background-color: #001F3A;
                    }
                """)

                view_button.clicked.connect(
                    lambda checked=False, student_id=student.id:
                        self.view_student(student_id)
                )

                # Edit button
                edit_button = QPushButton("Edit")
                edit_button.setFixedSize(65, 28)
                edit_button.setCursor(
                    Qt.CursorShape.PointingHandCursor
                )

                edit_button.setStyleSheet("""
                    QPushButton {
                        background-color: #E9DEBA;
                        color: #012D54;
                        border: 1px solid #D9B85F;
                        border-radius: 6px;
                        font-size: 12px;
                        font-weight: bold;
                    }

                    QPushButton:hover {
                        background-color: #D9B85F;
                        color: #012D54;
                    }

                    QPushButton:pressed {
                        background-color: #C5A64D;
                        color: #012D54;
                    }
                """)

                edit_button.clicked.connect(
                    lambda checked=False, student_id=student.id:
                        self.edit_student(student_id)
                )

                action_layout.addWidget(view_button)
                action_layout.addWidget(edit_button)

                self.students_table.setCellWidget(
                    row,
                    6,
                    action_widget,
                )

        if hasattr(self, "filter_students_table"):
            self.filter_students_table()

    def filter_students_table(self):
        if not hasattr(self, "student_search_input") or not hasattr(self, "students_table"):
            return

        query = self.student_search_input.text().strip().lower()
        total_rows = self.students_table.rowCount()
        visible_count = 0

        for row in range(total_rows):
            adm_item = self.students_table.item(row, 0)
            name_item = self.students_table.item(row, 1)
            parent_item = self.students_table.item(row, 2)
            phone_item = self.students_table.item(row, 3)

            adm = adm_item.text().lower() if adm_item else ""
            name = name_item.text().lower() if name_item else ""
            parent = parent_item.text().lower() if parent_item else ""
            phone = phone_item.text().lower() if phone_item else ""

            matches = (
                not query
                or (query in adm)
                or (query in name)
                or (query in parent)
                or (query in phone)
            )

            self.students_table.setRowHidden(row, not matches)
            if matches:
                visible_count += 1

        if hasattr(self, "student_count_badge"):
            if not query:
                self.student_count_badge.setText(
                    f"Total: {total_rows} student{'s' if total_rows != 1 else ''}"
                )
            elif visible_count == 0:
                self.student_count_badge.setText(f"0 of {total_rows} match")
            else:
                self.student_count_badge.setText(
                    f"Showing {visible_count} of {total_rows} students"
                )

    def refresh_dashboard(self):
        batch_id = self.batch_selector.currentData()

        with SessionLocal() as session:
            student_count = count_students(
                session,
                batch_id=batch_id,
            )
            present_count = count_present_students(
                session,
                attendance_date=date.today(),
                batch_id=batch_id
                )
            outstanding_amount = get_outstanding_amount(
                            session,
                            batch_id=batch_id
                        )
            upcoming_test_count = count_upcoming_tests(
                session,
                batch_id = batch_id,
                    )
            today_lessons = get_lessons_for_date(
                session,
                lesson_date=date.today(),
                batch_id=batch_id,
            )
            dashboard_alerts = get_dashboard_alerts(
                session,
                batch_id=batch_id
            )
            

            if student_count == 0:
                self.attendance_count_label.setText("-")
            else:
                self.attendance_count_label.setText(f"{present_count}/{student_count}")

            self.fees_pending_label.setText(f"₹{outstanding_amount:,.0f}")
            self.upcoming_tests_label.setText(str(upcoming_test_count))
            if not today_lessons:
                self.today_classes_label.setText(
                    "No classes scheduled for today."
                )
            else:
                class_lines = []

                for lesson in today_lessons:
                    line = lesson.title

                    if lesson.chapter:
                        line += f"\nChapter: {lesson.chapter}"

                    if lesson.topic:
                        line += f"\nTopic: {lesson.topic}"

                    class_lines.append(line)

                self.today_classes_label.setText(
                    "\n\n".join(class_lines)
                )
            if not dashboard_alerts:
                self.alerts_label.setText(
                    "No alerts at the moment."
                )
            else:
                self.alerts_label.setText(
                    "\n".join(
                        f"• {alert}"
                        for alert in dashboard_alerts
                    )
                )
                        
                        

            self.students_count_label.setText(str(student_count))
    def open_add_student_dialog(self):
        with SessionLocal() as session:
            batches = get_active_batches(session)

        dialog = AddStudentDialog(
            batches=batches,
            parent=self,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        admission_number = (
            dialog.admission_number_input.text().strip()
            or None
        )

        first_name = (
            dialog.first_name_input.text().strip()
        )

        last_name = (
            dialog.last_name_input.text().strip()
            or None
        )

        parent_name = (
            dialog.parent_name_input.text().strip()
        )

        parent_phone = (
            dialog.parent_phone_input.text().strip()
            or None
        )

        whatsapp_number = (
            dialog.whatsapp_input.text().strip()
            or None
        )

        batch_id = dialog.batch_input.currentData()

        school_name = (
            dialog.school_input.text().strip()
            or None
        )

        status = dialog.status_input.currentText()

        notes = (
            dialog.notes_input.toPlainText().strip()
            or None
        )

        dob = dialog.date_of_birth_input.date()

        if dob == dialog.date_of_birth_input.minimumDate():
            date_of_birth = None
        else:
            date_of_birth = dob.toPyDate()
        admission_date = (
            dialog.admission_date_input.date().toPyDate()
        )

        if not first_name:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Please enter the student's first name.",
            )
            return

        if not parent_name:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Please enter the parent's name.",
            )
            return

        if batch_id is None:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Please select a batch.",
            )
            return

        try:
            with SessionLocal() as session:
                create_student_with_parent(
                    session=session,
                    admission_number=admission_number,
                    first_name=first_name,
                    last_name=last_name,
                    parent_name=parent_name,
                    parent_phone=parent_phone,
                    whatsapp_number=whatsapp_number,
                    batch_id=batch_id,
                    date_of_birth=date_of_birth,
                    school_name=school_name,
                    admission_date=admission_date,
                    status=status,
                    notes=notes,
                )

            self.load_students()
            self.refresh_dashboard()

            QMessageBox.information(
                self,
                "Student Added",
                "Student has been added successfully.",
            )

        except ValueError as error:
            QMessageBox.warning(
                self,
                "Could Not Add Student",
                str(error),
            )
    def edit_student(self, student_id):
        with SessionLocal() as session:
            student = get_student(session, student_id)

            if student is None:
                QMessageBox.warning(
                    self,
                    "Student Not Found",
                    "The selected student could not be found.",
                )
                return

            batches = get_active_batches(session)

            admission_number = student.admission_number or ""
            first_name = student.first_name or ""
            last_name = student.last_name or ""
            parent_name = student.parent.name if student.parent else ""
            parent_phone = student.parent.phone if student.parent else ""
            whatsapp_number = student.parent.whatsapp_number if student.parent else ""
            batch_id = student.batch_id
            date_of_birth = student.date_of_birth
            school_name = student.school_name or ""
            admission_date = student.admission_date
            status = student.status or "ACTIVE"
            notes = student.notes or ""

        dialog = AddStudentDialog(
            batches=batches,
            parent=self,
        )
        dialog.setWindowTitle("Edit Student")
        dialog.title_label.setText("Edit Student")
        dialog.subtitle_label.setText(
            "Update the student's personal and parent information."
        )

        dialog.admission_number_input.setText(admission_number)
        dialog.first_name_input.setText(first_name)
        dialog.last_name_input.setText(last_name)
        dialog.parent_name_input.setText(parent_name)
        dialog.parent_phone_input.setText(parent_phone)
        dialog.whatsapp_input.setText(whatsapp_number)

        if batch_id is not None:
            batch_index = dialog.batch_input.findData(batch_id)
            if batch_index >= 0:
                dialog.batch_input.setCurrentIndex(batch_index)

        if date_of_birth:
            dialog.date_of_birth_input.setDate(
                QDate(
                    date_of_birth.year,
                    date_of_birth.month,
                    date_of_birth.day,
                )
            )

        dialog.school_input.setText(school_name)

        if admission_date:
            dialog.admission_date_input.setDate(
                QDate(
                    admission_date.year,
                    admission_date.month,
                    admission_date.day,
                )
            )

        status_index = dialog.status_input.findText(status)
        if status_index >= 0:
            dialog.status_input.setCurrentIndex(status_index)

        dialog.notes_input.setPlainText(notes)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_admission_number = dialog.admission_number_input.text().strip() or None
        new_first_name = dialog.first_name_input.text().strip()
        new_last_name = dialog.last_name_input.text().strip() or None
        new_parent_name = dialog.parent_name_input.text().strip()
        new_parent_phone = dialog.parent_phone_input.text().strip() or None
        new_whatsapp_number = dialog.whatsapp_input.text().strip() or None
        new_batch_id = dialog.batch_input.currentData()

        dob = dialog.date_of_birth_input.date()
        if dob == dialog.date_of_birth_input.minimumDate():
            new_date_of_birth = None
        else:
            new_date_of_birth = dob.toPyDate()

        new_school_name = dialog.school_input.text().strip() or None
        new_admission_date = dialog.admission_date_input.date().toPyDate()
        new_status = dialog.status_input.currentText()
        new_notes = dialog.notes_input.toPlainText().strip() or None

        if not new_first_name:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Please enter the student's first name.",
            )
            return

        if not new_parent_name:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Please enter the parent's name.",
            )
            return

        if new_batch_id is None:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Please select a batch.",
            )
            return

        try:
            with SessionLocal() as session:
                update_student_with_parent(
                    session=session,
                    student_id=student_id,
                    admission_number=new_admission_number,
                    first_name=new_first_name,
                    last_name=new_last_name,
                    parent_name=new_parent_name,
                    parent_phone=new_parent_phone,
                    whatsapp_number=new_whatsapp_number,
                    batch_id=new_batch_id,
                    date_of_birth=new_date_of_birth,
                    school_name=new_school_name,
                    admission_date=new_admission_date,
                    status=new_status,
                    notes=new_notes,
                )

            self.load_students()
            self.refresh_dashboard()

            QMessageBox.information(
                self,
                "Student Updated",
                "Student details have been updated successfully.",
            )

        except ValueError as e:
            QMessageBox.warning(
                self,
                "Update Failed",
                str(e),
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Update Failed",
                f"Could not update the student.\n\n{e}",
            )
    def view_student(self, student_id):
        with SessionLocal() as session:
            student = get_student(session, student_id)

            if student is None:
                QMessageBox.warning(
                    self,
                    "Student Not Found",
                    "The selected student could not be found.",
                )
                return

            # Student information
            student_name = (
                f"{student.first_name} {student.last_name or ''}"
            ).strip()

            admission_number = student.admission_number or "Not provided"
            school_name = student.school_name or "Not provided"
            status = student.status or "Not provided"
            notes = student.notes or "No notes"

            # Batch
            batch_name = "Not assigned"
            if student.batch:
                batch_name = student.batch.name

            # Parent information
            parent_name = "Not provided"
            parent_phone = "Not provided"
            whatsapp_number = "Not provided"

            if student.parent:
                parent_name = student.parent.name or "Not provided"
                parent_phone = student.parent.phone or "Not provided"
                whatsapp_number = (
                    student.parent.whatsapp_number
                    or "Not provided"
                )

            # Dates
            date_of_birth = "Not provided"
            if student.date_of_birth:
                date_of_birth = student.date_of_birth.strftime(
                    "%d/%m/%Y"
                )

            admission_date = "Not provided"
            if student.admission_date:
                admission_date = student.admission_date.strftime(
                    "%d/%m/%Y"
                )

        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Student Profile")
        dialog.resize(780, 600)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)

        # Title
        title = QLabel(student_name)
        title.setObjectName("studentProfileTitle")

        subtitle = QLabel(
            f"Admission No. • {admission_number}"
        )
        subtitle.setObjectName("studentProfileSubtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Student details
        details = QLabel(
            f"""
            <b>Student Information</b><br><br>

            <b>School:</b> {school_name}<br>
            <b>Batch:</b> {batch_name}<br>
            <b>Status:</b> {status}<br>
            <b>Date of Birth:</b> {date_of_birth}<br>
            <b>Admission Date:</b> {admission_date}<br><br>

            <b>Parent / Guardian</b><br><br>

            <b>Name:</b> {parent_name}<br>
            <b>Phone:</b> {parent_phone}<br>
            <b>WhatsApp:</b> {whatsapp_number}<br><br>

            <b>Notes</b><br><br>
            {notes}
            """
        )

        details.setWordWrap(True)
        details.setTextFormat(
            Qt.TextFormat.RichText
        )

                    # Student profile tabs
        
                    # Student profile tabs
        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        # ---------------- OVERVIEW TAB ----------------
        overview_tab = QWidget()
        overview_tab.setStyleSheet("""
            QWidget {
                background-color: #F8F6EA;
            }
        """)

        overview_layout = QVBoxLayout(overview_tab)
        overview_layout.setContentsMargins(10, 10, 10, 10)
        overview_layout.setSpacing(10)

        details.setStyleSheet("""
            QLabel {
                background-color: #FEFEFE;
                color: #012D54;
                border: 1px solid #E9DEBA;
                border-radius: 8px;
                padding: 15px;
                font-size: 13px;
            }
        """)

        overview_layout.addWidget(details)
        overview_layout.addStretch()

        tabs.addTab(overview_tab, "Overview")



        # ---------------- ATTENDANCE TAB ----------------
        attendance_tab = QWidget()
        attendance_tab.setStyleSheet("""
            QWidget {
                background-color: #F8F6EA;
            }
        """)

        attendance_layout = QVBoxLayout(attendance_tab)
        attendance_layout.setContentsMargins(10, 10, 10, 10)
        attendance_layout.setSpacing(12)

        attendance_title = QLabel("Attendance History")
        attendance_title.setStyleSheet("""
            QLabel {
                color: #012D54;
                background: transparent;
                font-size: 18px;
                font-weight: 700;
            }
        """)
        attendance_summary_layout = QHBoxLayout()
        attendance_summary_layout.setSpacing(10)

        total_label = QLabel("0")
        present_label = QLabel("0")
        absent_label = QLabel("0")
        late_label = QLabel("0")
        percentage_label = QLabel("0.0%")

        # -------------test_result tab-------------------------------

        results_tab = QWidget()
        results_tab.setStyleSheet("""
            QWidget {
                background-color: #F8F6EA;
            }
        """)

        results_layout = QVBoxLayout(results_tab)
        results_layout.setContentsMargins(10, 10, 10, 10)
        results_layout.setSpacing(12)

        results_title = QLabel("Test Results")
        results_title.setStyleSheet("""
            QLabel {
                color: #012D54;
                background: transparent;
                font-size: 18px;
                font-weight: 700;
            }
        """)

        results_layout.addWidget(results_title)
        test_summary_layout = QHBoxLayout()
        test_summary_layout.setSpacing(10)

        tests_label = QLabel("0")
        average_label = QLabel("0.0%")
        highest_label = QLabel("0.0%")
        lowest_label = QLabel("0.0%")


        def create_result_summary_card(title, value_label):
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background-color: #FEFEFE;
                    border: 1px solid #E9DEBA;
                    border-radius: 8px;
                }
            """)

            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 10, 12, 10)
            card_layout.setSpacing(3)

            title_label = QLabel(title)
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_label.setStyleSheet("""
                QLabel {
                    color: #615F4B;
                    background: transparent;
                    font-size: 11px;
                    font-weight: 600;
                }
            """)

            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value_label.setStyleSheet("""
                QLabel {
                    color: #012D54;
                    background: transparent;
                    font-size: 20px;
                    font-weight: 700;
                }
            """)

            card_layout.addWidget(title_label)
            card_layout.addWidget(value_label)

            return card


        test_summary_layout.addWidget(
            create_result_summary_card(
                "Tests Taken",
                tests_label,
            )
        )

        test_summary_layout.addWidget(
            create_result_summary_card(
                "Average",
                average_label,
            )
        )

        test_summary_layout.addWidget(
            create_result_summary_card(
                "Highest",
                highest_label,
            )
        )

        test_summary_layout.addWidget(
            create_result_summary_card(
                "Lowest",
                lowest_label,
            )
        )

        results_layout.addLayout(test_summary_layout)
        results_table = QTableWidget()
        results_table.setColumnCount(5)
        results_table.setHorizontalHeaderLabels([
            "Test",
            "Date",
            "Marks",
            "Percentage",
            "Remarks",
        ])

        results_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        results_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        results_table.verticalHeader().setVisible(False)
        results_table.verticalHeader().setDefaultSectionSize(40)
        configure_table_ux(
            results_table,
            column_widths=[200, 120, 120, 120, 200],
            stretch_column=0,
            alternating_colors=True
        )

        results_layout.addWidget(results_table)

        tabs.addTab(results_tab, "Results")
        self.load_student_results(
            student_id,
            results_table,
            tests_label,
            average_label,
            highest_label,
            lowest_label,
        )


        def create_summary_card(title, value_label):
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background-color: #FEFEFE;
                    border: 1px solid #E9DEBA;
                    border-radius: 8px;
                }
            """)

            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 10, 12, 10)
            card_layout.setSpacing(3)

            title_label = QLabel(title)
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_label.setStyleSheet("""
                color: #615F4B;
                background: transparent;
                font-size: 11px;
                font-weight: 600;
            """)

            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value_label.setStyleSheet("""
                color: #012D54;
                background: transparent;
                font-size: 20px;
                font-weight: 700;
            """)

            card_layout.addWidget(title_label)
            card_layout.addWidget(value_label)

            return card


        attendance_summary_layout.addWidget(
            create_summary_card("Total Days", total_label)
        )
        attendance_summary_layout.addWidget(
            create_summary_card("Present", present_label)
        )
        attendance_summary_layout.addWidget(
            create_summary_card("Absent", absent_label)
        )
        attendance_summary_layout.addWidget(
            create_summary_card("Late", late_label)
        )
        attendance_summary_layout.addWidget(
            create_summary_card("Attendance", percentage_label)
        )

        attendance_layout.addLayout(attendance_summary_layout)
        

        attendance_layout.addWidget(attendance_title)

        attendance_table = QTableWidget()
        
        attendance_table.setColumnCount(2)

        attendance_table.setHorizontalHeaderLabels([
            "Date",
            "Status",
        ])

        attendance_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        attendance_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        attendance_table.verticalHeader().setVisible(False)
        attendance_table.verticalHeader().setDefaultSectionSize(40)
        configure_table_ux(
            attendance_table,
            column_widths=[180, 180],
            stretch_column=0,
            alternating_colors=True
        )

        attendance_layout.addWidget(attendance_table)
        self.load_student_attendance(
            student_id,
            attendance_table,
            total_label,
            present_label,
            absent_label,
            late_label,
            percentage_label,
        )

        tabs.addTab(attendance_tab, "Attendance")
        # Fees Tab
        fees_tab = QWidget()
        fees_tab.setStyleSheet("""
            QWidget {
                background-color: #F8F6EA;
            }
        """)

        fees_layout = QVBoxLayout(fees_tab)
        fees_layout.setContentsMargins(10, 10, 10, 10)
        fees_layout.setSpacing(12)

        fees_title = QLabel("Fee Summary")
        fees_title.setStyleSheet("""
            QLabel {
                color: #012D54;
                background: transparent;
                font-size: 18px;
                font-weight: 700;
            }
        """)

        fees_layout.addWidget(fees_title)

        fees_summary_layout = QHBoxLayout()
        fees_summary_layout.setSpacing(10)

        total_due_label = QLabel("₹0.00")
        total_paid_label = QLabel("₹0.00")
        outstanding_label = QLabel("₹0.00")


        def create_fee_summary_card(title, value_label):
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background-color: #FEFEFE;
                    border: 1px solid #E9DEBA;
                    border-radius: 8px;
                }
            """)

            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 10, 12, 10)
            card_layout.setSpacing(3)

            title_label = QLabel(title)
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_label.setStyleSheet("""
                QLabel {
                    color: #615F4B;
                    background: transparent;
                    font-size: 11px;
                    font-weight: 600;
                }
            """)

            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value_label.setStyleSheet("""
                QLabel {
                    color: #012D54;
                    background: transparent;
                    font-size: 20px;
                    font-weight: 700;
                }
            """)

            card_layout.addWidget(title_label)
            card_layout.addWidget(value_label)

            return card


        overdue_label = QLabel("₹0.00")

        fees_summary_layout.addWidget(
            create_fee_summary_card(
                "Total Due",
                total_due_label,
            )
        )

        fees_summary_layout.addWidget(
            create_fee_summary_card(
                "Total Paid",
                total_paid_label,
            )
        )

        fees_summary_layout.addWidget(
            create_fee_summary_card(
                "Outstanding",
                outstanding_label,
            )
        )

        fees_summary_layout.addWidget(
            create_fee_summary_card(
                "Overdue",
                overdue_label,
            )
        )

        fees_layout.addLayout(fees_summary_layout)

        student_fees_table = QTableWidget()
        student_fees_table.setColumnCount(7)
        student_fees_table.setHorizontalHeaderLabels([
            "Period", "Total Due", "Paid", "Outstanding", "Due Date", "Status", "Actions"
        ])
        student_fees_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        student_fees_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        student_fees_table.verticalHeader().setVisible(False)
        configure_table_ux(
            student_fees_table,
            column_widths=[140, 110, 110, 110, 110, 110, 120],
            stretch_column=0,
            alternating_colors=True
        )
        fees_layout.addWidget(student_fees_table, 1)

        tabs.addTab(fees_tab, "Fees")
        self.load_student_fee_summary(
            student_id,
            total_due_label,
            total_paid_label,
            outstanding_label,
            overdue_label,
            student_fees_table,
        )


        # ---------------- TAB WIDGET STYLE ----------------
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #E9DEBA;
                border-radius: 8px;
                background-color: #F8F6EA;
                top: -1px;
            }

            QTabBar::tab {
                background-color: #E9DEBA;
                color: #012D54;
                padding: 8px 18px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }

            QTabBar::tab:selected {
                background-color: #012D54;
                color: #FEFEFE;
            }

            QTabBar::tab:hover {
                background-color: #D9B85F;
                color: #012D54;
            }
        """)

        layout.addWidget(tabs)
        layout.addStretch()
        layout.addStretch()
        # Close button
        close_button = QPushButton("Close")
        close_button.setFixedWidth(100)
        close_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        close_button.clicked.connect(dialog.accept)

        layout.addWidget(
            close_button,
            alignment=Qt.AlignmentFlag.AlignRight,
        )

        dialog.setStyleSheet("""
            QWidget {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }

            QDialog {
                background: #F8F6EA;
            }

            #studentProfileTitle {
                color: #012D54;
                font-size: 24px;
                font-weight: 700;
            }

            #studentProfileSubtitle {
                color: #615F4B;
                font-size: 13px;
            }

            QLabel {
                color: #1F2937;
                font-size: 13px;
            }

            QPushButton {
                background: #012D54;
                color: #FEFEFE;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: 600;
            }

            QPushButton:hover {
                background: #04294D;
            }

            QPushButton:pressed {
                background: #001F3A;
            }
        """)

        dialog.exec()
    def load_student_attendance(
        self,
        student_id,
        attendance_table,
        total_label,
        present_label,
        absent_label,
        late_label,
        percentage_label,
    ):
        attendance_table.setRowCount(0)

        with SessionLocal() as session:
            records = get_student_attendance(
                session,
                student_id=student_id,
            )

        total_days = len(records)
        present_days = sum(
            1 for record in records
            if record.status == "PRESENT"
        )
        absent_days = sum(
            1 for record in records
            if record.status == "ABSENT"
        )
        late_days = sum(
            1 for record in records
            if record.status == "LATE"
        )

        if total_days > 0:
            attendance_percentage = (
                present_days / total_days
            ) * 100
        else:
            attendance_percentage = 0

        total_label.setText(str(total_days))
        present_label.setText(str(present_days))
        absent_label.setText(str(absent_days))
        late_label.setText(str(late_days))
        percentage_label.setText(
            f"{attendance_percentage:.1f}%"
        )

        attendance_table.setRowCount(len(records))

        for row, record in enumerate(records):
            d_item = QTableWidgetItem(record.date.strftime("%d/%m/%Y"))
            d_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            attendance_table.setItem(row, 0, d_item)

            s_item = QTableWidgetItem(record.status)
            s_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            attendance_table.setItem(row, 1, s_item)
    def load_student_results(
        self,
        student_id,
        results_table,
        tests_label,
        average_label,
        highest_label,
        lowest_label,
    ):
        results_table.setRowCount(0)

        with SessionLocal() as session:
            results = get_student_results(
                session,
                student_id=student_id,
            )

        percentages = []

        for result in results:
            test = result.test

            if test.max_marks:
                percentage = (
                    result.marks / test.max_marks
                ) * 100
                percentages.append(percentage)

        tests_taken = len(results)

        if percentages:
            average_percentage = sum(percentages) / len(percentages)
            highest_percentage = max(percentages)
            lowest_percentage = min(percentages)
        else:
            average_percentage = 0
            highest_percentage = 0
            lowest_percentage = 0

        tests_label.setText(str(tests_taken))
        average_label.setText(f"{average_percentage:.1f}%")
        highest_label.setText(f"{highest_percentage:.1f}%")
        lowest_label.setText(f"{lowest_percentage:.1f}%")

        results_table.setRowCount(len(results))

        for row, result in enumerate(results):
            test = result.test

            percentage = (
                result.marks / test.max_marks * 100
                if test.max_marks
                else 0
            )

            name_item = QTableWidgetItem(test.name)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            results_table.setItem(row, 0, name_item)

            date_item = QTableWidgetItem(test.test_date.strftime("%d/%m/%Y"))
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            results_table.setItem(row, 1, date_item)

            marks_item = QTableWidgetItem(f"{result.marks} / {test.max_marks}")
            marks_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            results_table.setItem(row, 2, marks_item)

            pct_item = QTableWidgetItem(f"{percentage:.1f}%")
            pct_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            results_table.setItem(row, 3, pct_item)

            rem_item = QTableWidgetItem(result.remarks or "")
            rem_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            results_table.setItem(row, 4, rem_item)
    def load_student_fee_summary(
        self,
        student_id,
        total_due_label,
        total_paid_label,
        outstanding_label,
        overdue_label=None,
        table=None,
    ):
        with SessionLocal() as session:
            summary = get_student_fee_summary(
                session,
                student_id=student_id,
            )
            fees = get_student_fees(session, student_id=student_id)

        total_due_label.setText(
            f"₹{summary['total_due']:,.2f}"
        )

        total_paid_label.setText(
            f"₹{summary['total_paid']:,.2f}"
        )

        outstanding_label.setText(
            f"₹{summary['outstanding']:,.2f}"
        )

        if overdue_label is not None:
            overdue_label.setText(
                f"₹{summary.get('overdue', 0.0):,.2f}"
            )

        if table is not None:
            table.setRowCount(len(fees))
            for row, fee in enumerate(fees):
                m_name = MONTH_NAMES[fee.fee_month - 1] if (1 <= fee.fee_month <= 12) else str(fee.fee_month)
                period_item = QTableWidgetItem(f"{m_name} {fee.academic_year}")
                period_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 0, period_item)

                due_item = QTableWidgetItem(f"₹{fee.final_amount_due:,.2f}")
                due_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 1, due_item)

                paid_item = QTableWidgetItem(f"₹{fee.total_paid:,.2f}")
                paid_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 2, paid_item)

                bal_val = fee.outstanding_balance
                bal_item = QTableWidgetItem(f"₹{bal_val:,.2f}")
                bal_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if bal_val > 0:
                    bal_item.setForeground(Qt.GlobalColor.darkRed)
                table.setItem(row, 3, bal_item)

                due_date_str = fee.due_date.strftime("%d/%m/%Y") if fee.due_date else "—"
                d_item = QTableWidgetItem(due_date_str)
                d_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 4, d_item)

                status_calc = fee.calculate_status()
                status_item = QTableWidgetItem(status_calc.replace("_", " ").title())
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if status_calc == "PAID":
                    status_item.setForeground(Qt.GlobalColor.darkGreen)
                elif status_calc == "OVERDUE":
                    status_item.setForeground(Qt.GlobalColor.red)
                table.setItem(row, 5, status_item)

                act_w = QWidget()
                act_l = QHBoxLayout(act_w)
                act_l.setContentsMargins(4, 2, 4, 2)
                act_l.setSpacing(6)
                act_l.setAlignment(Qt.AlignmentFlag.AlignCenter)

                pay_b = QPushButton("Pay")
                pay_b.setFixedSize(50, 26)
                pay_b.setEnabled(bal_val > 0)
                pay_b.setCursor(Qt.CursorShape.PointingHandCursor)
                pay_b.setStyleSheet("""
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
                pay_b.clicked.connect(lambda ch, fid=fee.id: (self.open_record_payment_dialog(fid), self.load_student_fee_summary(student_id, total_due_label, total_paid_label, outstanding_label, overdue_label, table)))
                act_l.addWidget(pay_b)

                hist_b = QPushButton("History")
                hist_b.setFixedSize(58, 26)
                hist_b.setCursor(Qt.CursorShape.PointingHandCursor)
                hist_b.setStyleSheet("""
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
                hist_b.clicked.connect(lambda ch, fid=fee.id: (self.open_payment_history_dialog(fid), self.load_student_fee_summary(student_id, total_due_label, total_paid_label, outstanding_label, overdue_label, table)))
                act_l.addWidget(hist_b)

                table.setCellWidget(row, 6, act_w)
    def create_attendance_page(self):
        page = QWidget()
        page.setObjectName("attendancePage")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 28)
        layout.setSpacing(18)

        # Header
        title = QLabel("Attendance")
        title.setStyleSheet("""
            QLabel {
                color: #012D54;
                font-size: 26px;
                font-weight: 700;
                background: transparent;
            }
        """)

        subtitle = QLabel(
            "Mark attendance for the selected batch."
        )
        subtitle.setStyleSheet("""
            QLabel {
                color: #615F4B;
                font-size: 13px;
                background: transparent;
            }
        """)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Date
        date_layout = QHBoxLayout()
        date_layout.setSpacing(10)
        date_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        date_label = QLabel("Date")
        date_label.setStyleSheet("""
            QLabel {
                color: #012D54;
                font-size: 13px;
                font-weight: 600;
            }
        """)

        date_picker = QDateEdit()
        self.attendance_date_picker = date_picker
        
        date_picker.setDate(QDate.currentDate())
        date_picker.setCalendarPopup(True)
        date_picker.setFixedWidth(150)

        date_picker.setStyleSheet("""
            QDateEdit {
                background-color: #FEFEFE;
                color: #012D54;
                border: 1px solid #E9DEBA;
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 13px;
            }
        """)

        date_layout.addWidget(date_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        date_layout.addWidget(date_picker, alignment=Qt.AlignmentFlag.AlignVCenter)
        date_layout.addStretch()

        mark_all_present_btn = QPushButton("✓ Mark All Present")
        mark_all_present_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        mark_all_present_btn.setFixedHeight(34)
        mark_all_present_btn.setStyleSheet("""
            QPushButton {
                background-color: #E9DEBA;
                color: #012D54;
                border: 1px solid #D9B85F;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover:enabled {
                background-color: #D9B85F;
            }
            QPushButton:disabled {
                background-color: #F1EBD3;
                color: #8B887A;
                border-color: #E9DEBA;
            }
        """)
        mark_all_present_btn.clicked.connect(lambda: self.set_all_attendance("PRESENT"))
        self.mark_all_present_btn = mark_all_present_btn
        date_layout.addWidget(mark_all_present_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        clear_all_btn = QPushButton("Clear All")
        clear_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_all_btn.setFixedHeight(34)
        clear_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #FEFEFE;
                color: #012D54;
                border: 1px solid #E9DEBA;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover:enabled {
                background-color: #F1EBD3;
            }
            QPushButton:disabled {
                background-color: #F9F9F9;
                color: #BDBDBD;
                border-color: #E5E7EB;
            }
        """)
        clear_all_btn.clicked.connect(lambda: self.set_all_attendance(None))
        self.clear_all_attendance_btn = clear_all_btn
        date_layout.addWidget(clear_all_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        layout.addLayout(date_layout)

        attendance_summary = QLabel("Present: 0  |  Absent: 0  |  Total: 0")
        attendance_summary.setObjectName("attendanceSummaryBadge")
        self.attendance_summary = attendance_summary

        layout.addWidget(attendance_summary)

        # Attendance table
        attendance_table = QTableWidget()
        self.attendance_table = attendance_table
        attendance_table.setColumnCount(4)
        self.attendance_date_picker.dateChanged.connect(
                    self.load_attendance_students
                )
        attendance_table.setHorizontalHeaderLabels([
            "Admission No.",
            "Student Name",
            "A",
            "P",
        ])

        attendance_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        attendance_table.setSelectionMode(
            QTableWidget.SelectionMode.NoSelection
        )

        attendance_table.verticalHeader().setVisible(False)
        attendance_table.verticalHeader().setDefaultSectionSize(48)

        configure_table_ux(
            attendance_table,
            column_widths=[140, 260, 70, 70],
            stretch_column=1,
            alternating_colors=True
        )

        layout.addWidget(attendance_table)
                # Load students for selected batch
        # Save button
        save_button = QPushButton("Save Attendance")
        save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        save_button.setFixedHeight(42)

        save_button.setStyleSheet("""
            QPushButton {
                background-color: #012D54;
                color: #FEFEFE;
                border: none;
                border-radius: 7px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 600;
            }

            QPushButton:hover {
                background-color: #04294D;
            }
        """)
        save_button.clicked.connect(self.save_attendance)
        override_button = QPushButton("Override Class Day")
        self.attendance_override_button = override_button

        override_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        override_button.setFixedHeight(42)

        override_button.setStyleSheet("""
            QPushButton {
                background-color: #E9DEBA;
                color: #012D54;
                border: 1px solid #D9B85F;
                border-radius: 7px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 600;
            }

            QPushButton:hover {
                background-color: #D9B85F;
            }
        """)

        override_button.clicked.connect(
            self.override_attendance_day
        )

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        button_layout.addWidget(
            override_button
        )

        button_layout.addWidget(
            save_button
        )

        layout.addLayout(button_layout)

        return page
    def is_batch_class_day(self, batch, selected_date):
        if not batch or not batch.days:
            return False

        full_day = selected_date.strftime("%A").lower()
        short_day = selected_date.strftime("%a").lower()

        class_days = [
            day.strip().lower()
            for day in batch.days.split(",")
            if day.strip()
        ]

        return full_day in class_days or short_day in class_days

    def load_attendance_students(self):
        selected_batch_id = self.batch_selector.currentData()
        selected_date = (
            self.attendance_date_picker.date().toPyDate()
        )

        with SessionLocal() as session:
            students = get_students_by_batch(
                session,
                batch_id=selected_batch_id,
            )

            existing_attendance = get_attendance_by_date(
                session,
                selected_date,
                batch_id=selected_batch_id,
            )

            selected_batch = None
            attendance_override = None

            if selected_batch_id is not None:
                selected_batch = session.get(
                    Batch,
                    selected_batch_id,
                )
                attendance_override = get_attendance_override(
                    session,
                    batch_id=selected_batch_id,
                    override_date=selected_date,
                )

            if (
                selected_batch is not None
                and not self.is_batch_class_day(
                    selected_batch,
                    selected_date,
                )
                and attendance_override is None
            ):
                self.attendance_table.setRowCount(0)
                self.attendance_status = {}
                self.attendance_row_callbacks = {}
                if hasattr(self, "mark_all_present_btn"):
                    self.mark_all_present_btn.setEnabled(False)
                    self.clear_all_attendance_btn.setEnabled(False)

                self.attendance_summary.setText(
                    "Attendance unavailable — "
                    f"{selected_date.strftime('%A')} is not a class day."
                )

                return

        self.attendance_table.setRowCount(0)

        existing_status = {
            attendance.student_id: attendance.status
            for attendance in existing_attendance
        }

        self.attendance_status = {}
        self.attendance_row_callbacks = {}

        for row, student in enumerate(students):
            self.attendance_table.insertRow(row)
            self.attendance_status[student.id] = existing_status.get(
                student.id
            )

            admission_item = QTableWidgetItem(
                student.admission_number or "-"
            )
            admission_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            name_item = QTableWidgetItem(
                f"{student.first_name} {student.last_name or ''}".strip()
            )
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

            self.attendance_table.setItem(
                row,
                0,
                admission_item
            )

            self.attendance_table.setItem(
                row,
                1,
                name_item
            )

            # -----------------------------
            # Absent button
            # -----------------------------
            absent_button = QPushButton("A")
            absent_button.setCursor(
                Qt.CursorShape.PointingHandCursor
            )
            absent_button.setFixedSize(42, 32)

            # -----------------------------
            # Present button
            # -----------------------------
            present_button = QPushButton("P")
            present_button.setCursor(
                Qt.CursorShape.PointingHandCursor
            )
            present_button.setFixedSize(42, 32)

            def update_attendance_buttons(
                selected_status,
                absent_button=absent_button,
                present_button=present_button,
            ):
                normal_style = """
                    QPushButton {
                        background-color: #FEFEFE;
                        color: #012D54;
                        border: 1px solid #E9DEBA;
                        border-radius: 6px;
                        font-weight: 700;
                    }

                    QPushButton:hover {
                        background-color: #E9DEBA;
                    }
                """

                absent_style = """
                    QPushButton {
                        background-color: #DC2626;
                        color: #FEFEFE;
                        border: 1px solid #DC2626;
                        border-radius: 6px;
                        font-weight: 700;
                    }
                """

                present_style = """
                    QPushButton {
                        background-color: #16A34A;
                        color: #FEFEFE;
                        border: 1px solid #16A34A;
                        border-radius: 6px;
                        font-weight: 700;
                    }
                """

                absent_button.setStyleSheet(
                    absent_style
                    if selected_status == "ABSENT"
                    else normal_style
                )

                present_button.setStyleSheet(
                    present_style
                    if selected_status == "PRESENT"
                    else normal_style
                )

                present_count = sum(
                    1
                    for status in self.attendance_status.values()
                    if status == "PRESENT"
                )

                absent_count = sum(
                    1
                    for status in self.attendance_status.values()
                    if status == "ABSENT"
                )

                total_count = len(self.attendance_status)

                self.attendance_summary.setText(
                    f"Present: {present_count}  |  "
                    f"Absent: {absent_count}  |  "
                    f"Total: {total_count}"
)

            absent_button.clicked.connect(
                lambda checked=False,
                    student_id=student.id,
                    update_buttons=update_attendance_buttons:
                    (
                        self.attendance_status.__setitem__(
                            student_id,
                            "ABSENT"
                        ),
                        update_buttons("ABSENT")
                    )
            )

            present_button.clicked.connect(
                lambda checked=False,
                    student_id=student.id,
                    update_buttons=update_attendance_buttons:
                    (
                        self.attendance_status.__setitem__(
                            student_id,
                            "PRESENT"
                        ),
                        update_buttons("PRESENT")
                    )
            )
            self.attendance_row_callbacks[student.id] = update_attendance_buttons

            if self.attendance_status[student.id] is not None:
                update_attendance_buttons(
                    self.attendance_status[student.id]
                )

            # A button container
            absent_widget = QWidget()
            absent_layout = QHBoxLayout(absent_widget)
            absent_layout.setContentsMargins(0, 0, 0, 0)
            absent_layout.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )
            absent_layout.addWidget(absent_button)

            # P button container
            present_widget = QWidget()
            present_layout = QHBoxLayout(present_widget)
            present_layout.setContentsMargins(0, 0, 0, 0)
            present_layout.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )
            present_layout.addWidget(present_button)

            self.attendance_table.setCellWidget(
                row,
                2,
                absent_widget
            )

            self.attendance_table.setCellWidget(
                row,
                3,
                present_widget
            )

        has_students = len(students) > 0
        if hasattr(self, "mark_all_present_btn"):
            self.mark_all_present_btn.setEnabled(has_students)
            self.clear_all_attendance_btn.setEnabled(has_students)

        present_count = sum(
            1
            for status in self.attendance_status.values()
            if status == "PRESENT"
        )

        absent_count = sum(
            1
            for status in self.attendance_status.values()
            if status == "ABSENT"
        )

        total_count = len(self.attendance_status)

        self.attendance_summary.setText(
            f"Present: {present_count}  |  "
            f"Absent: {absent_count}  |  "
            f"Total: {total_count}"
        )

    def set_all_attendance(self, status):
        if not hasattr(self, "attendance_row_callbacks") or not self.attendance_row_callbacks:
            return

        for student_id, update_callback in self.attendance_row_callbacks.items():
            self.attendance_status[student_id] = status
            update_callback(status)

    def save_attendance(self):
        batch_id = self.batch_selector.currentData()

        if batch_id is None:
            QMessageBox.warning(
                self,
                "Select Batch",
                "Please select a specific batch before saving attendance."
            )
            return

        attendance_date = (
            self.attendance_date_picker.date().toPyDate()
        )

        with SessionLocal() as session:
            selected_batch = session.get(
                Batch,
                batch_id,
            )

            if selected_batch is None:
                QMessageBox.warning(
                    self,
                    "Batch Not Found",
                    "The selected batch could not be found."
                )
                return

            attendance_override = get_attendance_override(
                session,
                batch_id=batch_id,
                override_date=attendance_date,
            )

            if (
                not self.is_batch_class_day(
                    selected_batch,
                    attendance_date,
                )
                and attendance_override is None
            ):
                QMessageBox.warning(
                    self,
                    "No Class Today",
                    (
                        f"{selected_batch.name} does not have a class "
                        f"on {attendance_date.strftime('%A')}."
                    ),
                )
                return

        if not hasattr(self, "attendance_status") or not self.attendance_status:
            QMessageBox.warning(
                self,
                "Attendance",
                "Attendance data is not ready."
            )
            return

        unmarked_students = [
            student_id
            for student_id, status in self.attendance_status.items()
            if status is None
        ]

        if unmarked_students:
            QMessageBox.warning(
                self,
                "Incomplete Attendance",
                "Please mark attendance for all students before saving."
            )
            return

        with SessionLocal() as session:
            saved_count = save_batch_attendance(
                session,
                batch_id=batch_id,
                attendance_date=attendance_date,
                attendance_records=self.attendance_status,
            )

        QMessageBox.information(
            self,
            "Attendance Saved",
            f"Attendance for {attendance_date.strftime('%d %B %Y')} "
            f"has been saved successfully ({saved_count} student{'s' if saved_count != 1 else ''})."
        )

        self.refresh_dashboard()

    def override_attendance_day(self):
        batch_id = self.batch_selector.currentData()

        if batch_id is None:
            QMessageBox.warning(
                self,
                "Select Batch",
                "Please select a specific batch before overriding the class day."
            )
            return

        override_date = (
            self.attendance_date_picker.date().toPyDate()
        )

        with SessionLocal() as session:
            batch = session.get(
                Batch,
                batch_id,
            )

            if batch is None:
                QMessageBox.warning(
                    self,
                    "Batch Not Found",
                    "The selected batch could not be found."
                )
                return

            batch_name = batch.name

            existing_override = get_attendance_override(
                session,
                batch_id=batch_id,
                override_date=override_date,
            )

            if existing_override is not None:
                QMessageBox.information(
                    self,
                    "Already Overridden",
                    (
                        f"{override_date.strftime('%A, %d %B %Y')} "
                        "is already marked as an extra class day."
                    ),
                )
                return

        result = QMessageBox.question(
            self,
            "Override Class Day",
            (
                f"{override_date.strftime('%A, %d %B %Y')} "
                f"is not a scheduled class day for {batch_name}.\n\n"
                "Do you want to mark this date as an extra class day?"
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )

        if result != QMessageBox.StandardButton.Yes:
            return

        with SessionLocal() as session:
            create_attendance_override(
                session,
                batch_id=batch_id,
                override_date=override_date,
                reason="Extra class",
            )

        self.load_attendance_students()