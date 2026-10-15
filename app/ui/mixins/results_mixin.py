"""
TAMS Results & Examination Page Controller Mixin.

Enables examination planning and score entry, including:
  - Test creation (total marks, test date, topic/title)
  - Student score evaluation table with instant percentage calculation
  - Test result modification and test deletion
  - Performance rank badges and grade distribution
"""

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database.connection import SessionLocal
from app.database.models.batch import Batch
from app.database.models.test import TestModel
from app.services.batch_service import get_active_batches
from app.services.student_service import get_students_by_batch
from app.services.test_service import (
    create_test,
    delete_test,
    get_test_results,
    get_tests,
    save_test_results,
)
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


class ResultsMixin:
    """
    Mixin providing Results management UI: examination lists, test score grids,
    interactive result checks, and grade calculations.
    """

    def create_results_page(self) -> QWidget:
        """Constructs the Results page container, test dropdown filter, and examination grid."""
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
        title.setStyleSheet(f"""
            QLabel {{
                color: {NAVY};
                font-size: 26px;
                font-weight: 700;
            }}
        """)

        subtitle = QLabel(
            "Create tests and track student performance."
        )
        subtitle.setStyleSheet(f"""
            QLabel {{
                color: {MUTED};
                font-size: 13px;
            }}
        """)

        heading_layout.addWidget(title)
        heading_layout.addWidget(subtitle)
        header_layout.addLayout(heading_layout)
        header_layout.addStretch()

        create_button = QPushButton("＋ Create Test")
        create_button.setCursor(Qt.CursorShape.PointingHandCursor)
        create_button.setFixedHeight(38)
        create_button.setStyleSheet(f"""
            QPushButton {{
                background: {NAVY};
                color: {WHITE};
                border: 1px solid {NAVY};
                border-radius: 8px;
                padding: 8px 18px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {DARK_NAVY};
            }}
        """)
        create_button.clicked.connect(self.create_test_dialog)
        header_layout.addWidget(create_button, alignment=Qt.AlignmentFlag.AlignVCenter)

        check_results_button = QPushButton("Check Results")
        check_results_button.setCursor(Qt.CursorShape.PointingHandCursor)
        check_results_button.setFixedHeight(38)
        check_results_button.setEnabled(False)
        check_results_button.setStyleSheet(f"""
            QPushButton {{
                background: {CREAM};
                color: {NAVY};
                border: 1px solid {GOLD};
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover:enabled {{
                background: {LIGHT_GOLD};
                border-color: {NAVY};
            }}
            QPushButton:disabled {{
                color: #8B887A;
                background: #F1EBD3;
                border-color: {LIGHT_GOLD};
            }}
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
            flexible_columns=[0],
            strategy=TableSizingStrategy.BOUNDED_AND_FLEXIBLE,
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
                batch_name = test.batch.name if test.batch is not None else "Unknown batch"
                rows.append((
                    test.name,
                    batch_name,
                    test.test_date.strftime("%d %b %Y"),
                    f"{test.max_marks:g}",
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

        auto_fit_columns(self.results_tests_table)
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
        configure_table_ux(
            results_table,
            column_widths=[140, 200, 100, 120, 220],
            flexible_columns=[1, 4],
            strategy=TableSizingStrategy.BOUNDED_AND_FLEXIBLE,
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

        auto_fit_columns(results_table)
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
                    f"{existing_by_student[student.id].marks:g}"
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
        configure_table_ux(
            results_table,
            column_widths=[140, 200, 110, 110, 220],
            flexible_columns=[1, 4],
            strategy=TableSizingStrategy.BOUNDED_AND_FLEXIBLE,
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

        auto_fit_columns(results_table)
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
                marks = float(marks_text)
            except ValueError:
                QMessageBox.warning(
                    self,
                    "Invalid Marks",
                    f"Enter a valid number for {results_table.item(row_index, 1).text()}.",
                )
                return

            if marks > max_marks:
                QMessageBox.warning(
                    self,
                    "Marks Out of Range",
                    f"Marks must be at most {max_marks}.",
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

