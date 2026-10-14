"""
TAMS Students Page Controller Mixin.

Manages student registration, live keyword search, batch membership, parent contact details,
and modal dialogs for comprehensive student 360 profiles (attendance histories, exam score trends,
and fee payment ledgers).
"""

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.database.connection import SessionLocal
from app.services.attendance_service import get_student_attendance
from app.services.batch_service import get_active_batches
from app.services.fee_service import get_student_fee_summary, get_student_fees
from app.services.student_service import (
    create_student_with_parent,
    generate_next_admission_number,
    get_student,
    get_students_by_batch,
    update_student_with_parent,
)
from app.services.test_service import get_student_results
from app.ui.add_student_dialog import AddStudentDialog
from app.ui.bulk_student_dialog import BulkStudentDialog
from app.ui.fee_dialogs import MONTH_NAMES
from app.ui.table_utils import (
    TableSizingStrategy,
    auto_fit_columns,
    configure_table_ux,
)
from app.ui.theme import (
    BADGE_AMBER_BG,
    BADGE_AMBER_FG,
    BADGE_GRAY_BG,
    BADGE_GRAY_FG,
    BADGE_GREEN_BG,
    BADGE_GREEN_FG,
)


class StudentsMixin:
    """
    Mixin providing Students management UI: student roster tables, registration forms,
    interactive filters, and detailed student profile inspector views.
    """
    """Mixin providing Students page, student registration, search, and student profile dialogs."""

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

        # Bulk actions button
        self.bulk_actions_button = QPushButton("👥 Bulk Actions")
        self.bulk_actions_button.setObjectName("bulkActionsButton")
        self.bulk_actions_button.setFixedHeight(38)
        self.bulk_actions_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.bulk_actions_button.clicked.connect(self.open_bulk_student_dialog)
        header_layout.addWidget(self.bulk_actions_button, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Add student button
        add_student_button = QPushButton("+ Add Student")
        add_student_button.setObjectName("addStudentButton")
        add_student_button.setFixedHeight(38)
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
            column_widths=[130, 200, 170, 130, 140, 100, 160],
            stretch_column=1,
            flexible_columns=[1, 2],
            fixed_columns=[6],
            strategy=TableSizingStrategy.BOUNDED_AND_FLEXIBLE,
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

                # Status pill badge widget
                status_widget = QWidget()
                status_layout = QHBoxLayout(status_widget)
                status_layout.setContentsMargins(0, 0, 0, 0)
                status_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

                status_badge = QLabel()
                status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
                norm_status = (student.status or "ACTIVE").upper()
                if norm_status == "ACTIVE":
                    status_badge.setText("Active")
                    status_badge.setStyleSheet(
                        f"background-color: {BADGE_GREEN_BG}; color: {BADGE_GREEN_FG}; "
                        "font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 5px;"
                    )
                elif norm_status == "ALUMNI":
                    status_badge.setText("Alumni")
                    status_badge.setStyleSheet(
                        f"background-color: {BADGE_AMBER_BG}; color: {BADGE_AMBER_FG}; "
                        "font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 5px;"
                    )
                else:
                    status_badge.setText("Inactive")
                    status_badge.setStyleSheet(
                        f"background-color: {BADGE_GRAY_BG}; color: {BADGE_GRAY_FG}; "
                        "font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 5px;"
                    )

                status_layout.addWidget(status_badge)
                self.students_table.setCellWidget(row, 5, status_widget)

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

        auto_fit_columns(self.students_table)

    def open_bulk_student_dialog(self):
        """
        Open the modal dialog for bulk student operations (batch promotion and status update).
        """
        with SessionLocal() as session:
            batches = get_active_batches(session)

        current_batch_id = (
            self.batch_selector.currentData()
            if hasattr(self, "batch_selector")
            else None
        )

        dialog = BulkStudentDialog(
            batches=batches,
            initial_batch_id=current_batch_id,
            parent=self,
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Refresh students roster and dashboard metrics
            self.load_students()
            if hasattr(self, "refresh_dashboard"):
                self.refresh_dashboard()

    def open_add_student_dialog(self):
        """
        Open the student registration modal dialog.
        
        Fetches active batches and autogenerates the next sequential admission
        number to suggest by default, while allowing custom overrides.
        """
        with SessionLocal() as session:
            batches = get_active_batches(session)
            suggested_admission_no = generate_next_admission_number(session)

        dialog = AddStudentDialog(
            batches=batches,
            parent=self,
            default_admission_number=suggested_admission_no,
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
            flexible_columns=[0, 4],
            strategy=TableSizingStrategy.BOUNDED_AND_FLEXIBLE,
            alternating_colors=True,
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
            flexible_columns=[0, 1],
            strategy=TableSizingStrategy.BOUNDED_AND_FLEXIBLE,
            alternating_colors=True,
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
            column_widths=[140, 110, 110, 110, 110, 110, 140],
            stretch_column=0,
            flexible_columns=[0],
            fixed_columns=[6],
            strategy=TableSizingStrategy.BOUNDED_AND_FLEXIBLE,
            alternating_colors=True,
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

        auto_fit_columns(attendance_table)

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

        auto_fit_columns(results_table)
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

            auto_fit_columns(table)
