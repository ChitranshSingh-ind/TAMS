from datetime import date
from app.ui.settings_dialog import SettingsDialog
from app.ui.add_student_dialog import AddStudentDialog
from PyQt6.QtCore import Qt, QDate
from app.database.connection import SessionLocal
from app.services.batch_service import get_active_batches
from app.services.student_service import count_students,  get_students_by_batch, create_student_with_parent, get_student, update_student
from app.services.fee_service import get_outstanding_amount
from app.services.test_service import count_upcoming_tests
from app.services.lesson_service import get_lessons_for_date
from app.services.dashboard_service import get_dashboard_alerts
from PyQt6.QtWidgets import (
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
    
)
from app.services.attendance_service import count_present_students
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
        top_layout.setContentsMargins(20, 12, 20, 12)

        title = QLabel("Coaching Management System")
        title.setObjectName("appTitle")

        

        settings_button = QPushButton("⚙")
        settings_button.setObjectName("settingButton")
        settings_button.clicked.connect(self.open_settings)

        top_layout.addWidget(title)
     
        top_layout.addStretch()
        
        top_layout.addWidget(settings_button)

        main_layout.addWidget(top_bar)
        #  Main area
        content_widget = QWidget()
        content_widget.setObjectName("contentWidget")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0,0,0,0)
        content_layout.setSpacing(0)
        

        content_toolbar = QFrame()
        content_toolbar.setObjectName("contentToolbar")

        content_toolbar_layout = QHBoxLayout(content_toolbar)
        content_toolbar_layout.setContentsMargins(20,12,20,12)

        content_toolbar_layout.addStretch()

        batch_label = QLabel("Batch:")
        batch_label.setObjectName("batchLabel")

        self.batch_selector = QComboBox()
        self.batch_selector.setObjectName("batchSelector")
        self.batch_selector.setMinimumWidth(180)
        self.batch_selector.addItem("All Batches", None)

        content_toolbar_layout.addWidget(batch_label)
        content_toolbar_layout.addWidget(self.batch_selector)

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
    def open_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec()
        self.load_batches()
        
    def apply_styles(self):
        self.setStyleSheet(f"""
            QMainWindow {{
                background: {LIGHT_GOLD};
            }}
    
            #topBar {{
                background: {NAVY};
                border-bottom: 2px solid {GOLD};
            }}
    
            #appTitle {{
                color: {WHITE};
                font-size: 24px;
                font-weight: bold;
            }}
    
            #batchLabel {{
                color: {NAVY};
                font-weight: 600;
            }}
    
            #sidebar {{
                background: {CREAM};
                border-right: 1px solid {LIGHT_GOLD};
            }}
    
            #batchSelector {{
                background-color: {WHITE};
                color: {NAVY};
                border: 1px solid {GOLD};
                border-radius: 6px;
                padding: 7px 10px;
            }}
    
            #batchSelector QAbstractItemView {{
                background-color: {WHITE};
                color: {TEXT};
                selection-background-color: {NAVY};
                selection-color: {WHITE};
            }}
    
            #sidebar QPushButton {{
                text-align: left;
                padding: 10px 14px;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                color: {NAVY};
                background: transparent;
            }}
    
            #sidebar QPushButton:hover {{
                background: {LIGHT_GOLD};
                color: {DARK_NAVY};
            }}
    
            #contentToolbar {{
                background: {CREAM};
                border-bottom: 1px solid {LIGHT_GOLD};
            }}
    
            QComboBox {{
                padding: 7px 10px;
                border: 1px solid {GOLD};
                border-radius: 10px;
                background: {WHITE};
            }}
    
            #settingButton {{
                background: transparent;
                color: {WHITE};
                border: none;
                font-size: 18px;
            }}
    
            #settingButton:hover {{
                background: {DARK_NAVY};
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
            #sidebar QPushButton[active="true"] {{
                background: {GOLD};
                color: {NAVY};
                font-weight: 700;
            }}
            #dashboardPage {{
        background: #F8F6EA;
    }}

    #dashboardGreeting {{
        color: #012D54;
        font-size: 26px;
        font-weight: 700;
    }}

    #dashboardSubtitle {{
        color: #615F4B;
        font-size: 13px;
    }}

    #dashboardCard {{
        background: #FEFEFE;
        border: 1px solid #E9DEBA;
        border-radius: 10px;
    }}

    #dashboardCard:hover {{
        border: 1px solid #D9B85F;
    }}

    #dashboardCardTitle {{
        color: #615F4B;
        font-size: 12px;
        font-weight: 600;
    }}

    #dashboardCardValue {{
        color: #012D54;
        font-size: 28px;
        font-weight: 700;
    }}

    #dashboardCardDescription {{
        color: #615F4B;
        font-size: 11px;
    }}

    #dashboardSectionCard {{
        background: #FEFEFE;
        border: 1px solid #E9DEBA;
        border-radius: 10px;
        min-height: 180px;
    }}

    #dashboardSectionTitle {{
        color: #012D54;
        font-size: 16px;
        font-weight: 700;
    }}

    #dashboardSectionText {{
        color: #615F4B;
        font-size: 13px;
    }}
    #studentsPage {{
    background: #F8F6EA;
}}

#studentsPageTitle {{
    color: #012D54;
    font-size: 26px;
    font-weight: 700;
}}

#studentsPageSubtitle {{
    color: #615F4B;
    font-size: 13px;
}}
#studentsPage {{
    background: #F8F6EA;
}}

#studentsPageTitle {{
    color: #012D54;
    font-size: 26px;
    font-weight: 700;
}}

#studentsPageSubtitle {{
    color: #615F4B;
    font-size: 13px;
}}

#addStudentButton {{
    background: #012D54;
    color: #FEFEFE;
    border: none;
    border-radius: 8px;
    padding: 10px 18px;
    font-size: 13px;
    font-weight: 600;
}}

#addStudentButton:hover {{
    background: #04294D;
}}

#addStudentButton:pressed {{
    background: #001F3A;
}}

#studentsTableFrame {{
    background: #FEFEFE;
    border: 1px solid #E9DEBA;
    border-radius: 12px;
}}

#studentsTablePlaceholder {{
    color: #615F4B;
    font-size: 14px;
}}
#studentsTable {{
    background: #FEFEFE;
    border: 1px solid #E9DEBA;
    border-radius: 10px;
    gridline-color: #E9DEBA;
    color: #1F2937;
    font-size: 13px;
    selection-background-color: #E9DEBA;
    selection-color: #012D54;
}}

#studentsTable::item {{
    padding: 8px;
    border-bottom: 1px solid #F1EBD3;
}}

#studentsTable QHeaderView::section {{
    background: #012D54;
    color: #FEFEFE;
    padding: 10px;
    border: none;
    font-size: 12px;
    font-weight: 600;
}}

#studentsTable QTableCornerButton::section {{
    background: #012D54;
    border: none;
}}
#addStudentTitle {{
    color: {NAVY};
    font-size: 22px;
    font-weight: 700;
}}

#addStudentSubtitle {{
    color: {DARK_NAVY};
    font-size: 13px;
}}

QDialog {{
    background: #F8F6EA;
}}

QDialog QLineEdit,
QDialog QComboBox,
QDialog QDateEdit,
QDialog QPlainTextEdit {{
    background: #FEFEFE;
    color: #1F2937;
    border: 1px solid #D9B85F;
    border-radius: 6px;
    padding: 7px 9px;
}}

QDialog QLineEdit:focus,
QDialog QComboBox:focus,
QDialog QDateEdit:focus,
QDialog QPlainTextEdit:focus {{
    border: 2px solid #012D54;
}}

QDialog QDialogButtonBox QPushButton {{
    background: #012D54;
    color: #FEFEFE;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: 600;
}}

QDialog QDialogButtonBox QPushButton:hover {{
    background: #04294D;
}}
QDialog QLabel{{
    color: {NAVY};
}}
#editStudentButton {{
    background: #E9DEBA;
    color: #012D54;
    border: 1px solid #D9B85F;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 700;
}}

#editStudentButton:hover {{
    background: #D9B85F;
    color: #012D54;
}}

#editStudentButton:pressed {{
    background: #C5A64D;
    color: #012D54;
}}
        """)
    def change_page(self,index):
        self.pages.setCurrentIndex(index)
        if index == 1:
            self.load_students()

        for button in self.sidebar_buttons:
            button.setProperty("active", button.property("page_index") == index)
            button.style().unpolish(button)
            button.style().polish(button)
    def load_batches(self):
        self.batch_selector.clear()

        self.batch_selector.addItem("All Batches", None)
        self.batch_selector.currentIndexChanged.connect(self.refresh_dashboard)
        self.batch_selector.currentIndexChanged.connect(self.load_students)
        with SessionLocal() as session:
            batches = get_active_batches(session)
            for batch in batches:
                self.batch_selector.addItem(
                    batch.name, 
                    batch.id
                )

                
        self.pages.setCurrentIndex(0)
        self.refresh_dashboard()

    def create_dashboard_page(self):
        page = QWidget()
        page.setObjectName("dashboardPage")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(20)

        # ── Header ──────────────────────────────────────
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)

        greeting = QLabel("Good afternoon 👋")
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

            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(20, 18, 20, 18)
            card_layout.setSpacing(5)

            title_label = QLabel(title)
            title_label.setObjectName("dashboardCardTitle")

            value_label = QLabel(value)
            value_label.setObjectName("dashboardCardValue")
            if title == "Students":
                self.students_count_label = value_label
            if title == "Attendance":
                self.attendance_count_label = value_label
            if title == "Fees Pending":
                self.fees_pending_label = value_label
            if title == "Upcoming Tests":
                self.upcoming_tests_label = value_label
            

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

        today_title = QLabel("Today's Classes")
        today_title.setObjectName("dashboardSectionTitle")

        today_info = QLabel()
        today_info.setWordWrap(True)
        today_info.setObjectName("dashboardSectionText")

        self.today_classes_label = today_info

        today_layout.addWidget(today_title)
        today_layout.addSpacing(10)
        today_layout.addWidget(today_info)
        today_layout.addStretch()

        alerts_card = QFrame()
        alerts_card.setObjectName("dashboardSectionCard")

        alerts_layout = QVBoxLayout(alerts_card)
        alerts_layout.setContentsMargins(20, 18, 20, 18)

        alerts_title = QLabel("Alerts & Notifications")
        alerts_title.setObjectName("dashboardSectionTitle")

        alerts_info = QLabel()
        alerts_info.setWordWrap(True)
        alerts_info.setObjectName("dashboardSectionText")

        self.alerts_label = alerts_info

        alerts_layout.addWidget(alerts_title)
        alerts_layout.addSpacing(10)
        alerts_layout.addWidget(alerts_info)
        alerts_layout.addStretch()

        

        lower_layout.addWidget(today_card, 1)
        lower_layout.addWidget(alerts_card, 1)

        layout.addLayout(lower_layout)

        return page
    def create_students_page(self):
        page = QWidget()
        page.setObjectName("studentsPage")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 30)
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

        header_layout.addWidget(add_student_button)

        layout.addLayout(header_layout)

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

        self.students_table.verticalHeader().setVisible(False)

        header = self.students_table.horizontalHeader()

        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents
        )

        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch
        )

        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch
        )

        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.ResizeToContents
        )

        header.setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.ResizeToContents
        )

        header.setSectionResizeMode(
            5,
            QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(
            6,
            QHeaderView.ResizeMode.ResizeToContents
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

                self.students_table.setItem(
                    row,
                    0,
                    QTableWidgetItem(
                        student.admission_number or ""
                    ),
                )

                self.students_table.setItem(
                    row,
                    1,
                    QTableWidgetItem(
                        f"{student.first_name} {student.last_name or ''}".strip()
                    ),
                )

                self.students_table.setItem(
                    row,
                    2,
                    QTableWidgetItem(parent_name),
                )

                self.students_table.setItem(
                    row,
                    3,
                    QTableWidgetItem(parent_phone),
                )

                self.students_table.setItem(
                    row,
                    4,
                    QTableWidgetItem(batch_name),
                )

                self.students_table.setItem(
                    row,
                    5,
                    QTableWidgetItem(student.status),
                )
                # Action buttons
                action_widget = QWidget()
                action_layout = QHBoxLayout(action_widget)

                action_layout.setContentsMargins(4, 2, 4, 2)
                action_layout.setSpacing(5)

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


                self.fees_pending_label.setText(f"{outstanding_amount:,.0f}")
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

            # Load active batches
            batches = get_active_batches(session)

            dialog = AddStudentDialog(
                batches=batches,
                parent=self,
            )

            # -----------------------------
            # Fill existing student data
            # -----------------------------

            dialog.admission_number_input.setText(
                student.admission_number or ""
            )

            dialog.first_name_input.setText(
                student.first_name or ""
            )

            dialog.last_name_input.setText(
                student.last_name or ""
            )

            if student.parent:
                dialog.parent_name_input.setText(
                    student.parent.name or ""
                )

                dialog.parent_phone_input.setText(
                    student.parent.phone or ""
                )

                dialog.whatsapp_input.setText(
                    student.parent.whatsapp_number or ""
                )

            # Select student's batch
            if student.batch_id is not None:
                batch_index = dialog.batch_input.findData(
                    student.batch_id
                )

                if batch_index >= 0:
                    dialog.batch_input.setCurrentIndex(
                        batch_index
                    )

            # DOB
            if student.date_of_birth:
                dialog.date_of_birth_input.setDate(
                    QDate(
                        student.date_of_birth.year,
                        student.date_of_birth.month,
                        student.date_of_birth.day,
                    )
                )

            # School
            dialog.school_input.setText(
                student.school_name or ""
            )

            # Admission date
            if student.admission_date:
                dialog.admission_date_input.setDate(
                    QDate(
                        student.admission_date.year,
                        student.admission_date.month,
                        student.admission_date.day,
                    )
                )

            # Status
            status_index = dialog.status_input.findText(
                student.status
            )

            if status_index >= 0:
                dialog.status_input.setCurrentIndex(
                    status_index
                )

            # Notes
            dialog.notes_input.setPlainText(
                student.notes or ""
            )

            # -----------------------------
            # Show dialog
            # -----------------------------

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

        # Read updated values
            admission_number = dialog.admission_number_input.text().strip() or None
            first_name = dialog.first_name_input.text().strip()
            last_name = dialog.last_name_input.text().strip()
            parent_name = dialog.parent_name_input.text().strip()
            parent_phone = dialog.parent_phone_input.text().strip()
            whatsapp_number = dialog.whatsapp_input.text().strip()

            batch_id = dialog.batch_input.currentData()

            dob = dialog.date_of_birth_input.date()
            if dob == dialog.date_of_birth_input.minimumDate():
                date_of_birth = None
            else:
                date_of_birth = dob.toPyDate()

            school_name = dialog.school_input.text().strip()

            admission_date = dialog.admission_date_input.date().toPyDate()

            status = dialog.status_input.currentText()

            notes = dialog.notes_input.toPlainText().strip()

            # Basic validation
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

            with SessionLocal() as session:
                try:
                    update_student(
                        session,
                        student_id,
                        admission_number=admission_number,
                        first_name=first_name,
                        last_name=last_name,
                        batch_id=batch_id,
                        date_of_birth=date_of_birth,
                        school_name=school_name,
                        admission_date=admission_date,
                        status=status,
                        notes=notes,
                    )

                    # Update parent details
                    student = get_student(session, student_id)

                    if student and student.parent:
                        student.parent.name = parent_name
                        student.parent.phone = parent_phone or None
                        student.parent.whatsapp_number = whatsapp_number or None
                        session.commit()

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
                    session.rollback()
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
            dialog.resize(600, 550)

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

            layout.addWidget(details)
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
                                            