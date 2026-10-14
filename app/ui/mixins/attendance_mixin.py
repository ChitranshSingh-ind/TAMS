"""
TAMS Attendance Page Controller Mixin.

Manages attendance rosters, calendar date selections, scheduled batch days,
extra class schedule overrides, and bulk attendance marking (Present / Absent / Late).
"""

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database.connection import SessionLocal
from app.database.models.batch import Batch
from app.services.attendance_service import (
    create_attendance_override,
    get_attendance_by_date,
    get_attendance_override,
    save_batch_attendance,
)
from app.services.student_service import get_students_by_batch
from app.ui.table_utils import (
    TableSizingStrategy,
    auto_fit_columns,
    configure_table_ux,
)
from app.ui.theme import (
    CREAM,
    DARK_NAVY,
    GOLD,
    LIGHT_GOLD,
    MUTED,
    NAVY,
    TEXT,
    WHITE,
)


class AttendanceMixin:
    """
    Mixin providing Attendance tracking UI, student rosters, bulk marking actions,
    and unscheduled day override dialogs.
    """

    def create_attendance_page(self) -> QWidget:
        """Constructs the Attendance page container, date picker, and student roster table."""
        page = QWidget()
        page.setObjectName("attendancePage")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 28)
        layout.setSpacing(18)

        # Header
        title = QLabel("Attendance")
        title.setStyleSheet(f"""
            QLabel {{
                color: {NAVY};
                font-size: 26px;
                font-weight: 700;
                background: transparent;
            }}
        """)

        subtitle = QLabel(
            "Mark attendance for the selected batch."
        )
        subtitle.setStyleSheet(f"""
            QLabel {{
                color: {MUTED};
                font-size: 13px;
                background: transparent;
            }}
        """)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Date
        date_layout = QHBoxLayout()
        date_layout.setSpacing(10)
        date_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        date_label = QLabel("Date")
        date_label.setStyleSheet(f"""
            QLabel {{
                color: {NAVY};
                font-size: 13px;
                font-weight: 600;
            }}
        """)

        date_picker = QDateEdit()
        self.attendance_date_picker = date_picker
        
        date_picker.setDate(QDate.currentDate())
        date_picker.setCalendarPopup(True)
        date_picker.setFixedWidth(150)
        date_picker.setFixedHeight(38)

        date_picker.setStyleSheet(f"""
            QDateEdit {{
                background-color: {WHITE};
                color: {NAVY};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 13px;
            }}
        """)

        date_layout.addWidget(date_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        date_layout.addWidget(date_picker, alignment=Qt.AlignmentFlag.AlignVCenter)
        date_layout.addStretch()

        mark_all_present_btn = QPushButton("✓ Mark All Present")
        mark_all_present_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        mark_all_present_btn.setFixedHeight(38)
        mark_all_present_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {CREAM};
                color: {NAVY};
                border: 1px solid {GOLD};
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover:enabled {{
                background-color: {LIGHT_GOLD};
                border-color: {NAVY};
            }}
            QPushButton:disabled {{
                background-color: #F1EBD3;
                color: #8B887A;
                border-color: {LIGHT_GOLD};
            }}
        """)
        mark_all_present_btn.clicked.connect(lambda: self.set_all_attendance("PRESENT"))
        self.mark_all_present_btn = mark_all_present_btn
        date_layout.addWidget(mark_all_present_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        clear_all_btn = QPushButton("Clear All")
        clear_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_all_btn.setFixedHeight(38)
        clear_all_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {WHITE};
                color: {NAVY};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover:enabled {{
                background-color: {CREAM};
                border-color: {GOLD};
            }}
            QPushButton:disabled {{
                background-color: #F9F9F9;
                color: #BDBDBD;
                border-color: #E5E7EB;
            }}
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
            flexible_columns=[1],
            fixed_columns=[2, 3],
            strategy=TableSizingStrategy.BOUNDED_AND_FLEXIBLE,
            alternating_colors=True,
        )

        layout.addWidget(attendance_table)
                # Load students for selected batch
        # Save button
        save_button = QPushButton("Save Attendance")
        save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        save_button.setFixedHeight(40)

        save_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {NAVY};
                color: {WHITE};
                border: 1px solid {NAVY};
                border-radius: 8px;
                padding: 8px 22px;
                font-size: 13px;
                font-weight: 600;
            }}

            QPushButton:hover {{
                background-color: {DARK_NAVY};
            }}
        """)
        save_button.clicked.connect(self.save_attendance)
        override_button = QPushButton("Override Class Day")
        self.attendance_override_button = override_button

        override_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        override_button.setFixedHeight(40)

        override_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {CREAM};
                color: {NAVY};
                border: 1px solid {GOLD};
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 600;
            }}

            QPushButton:hover {{
                background-color: {LIGHT_GOLD};
                border-color: {NAVY};
            }}
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
        auto_fit_columns(self.attendance_table)

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