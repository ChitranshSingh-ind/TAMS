from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
)


class AddStudentDialog(QDialog):
    def __init__(self, batches, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Add Student")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(18)

        # Header
        title = QLabel("Add Student")
        title.setObjectName("addStudentTitle")

        subtitle = QLabel(
            "Enter the student's personal and parent information."
        )
        subtitle.setObjectName("addStudentSubtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Form
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.admission_number_input = QLineEdit()
        self.admission_number_input.setPlaceholderText(
            "e.g. STU001"
        )

        self.first_name_input = QLineEdit()
        self.first_name_input.setPlaceholderText(
            "First name"
        )

        self.last_name_input = QLineEdit()
        self.last_name_input.setPlaceholderText(
            "Last name"
        )

        self.parent_name_input = QLineEdit()
        self.parent_name_input.setPlaceholderText(
            "Parent / guardian name"
        )

        self.parent_phone_input = QLineEdit()
        self.parent_phone_input.setPlaceholderText(
            "Phone number"
        )

        self.whatsapp_input = QLineEdit()
        self.whatsapp_input.setPlaceholderText(
            "WhatsApp number"
        )

        self.batch_input = QComboBox()

        for batch in batches:
            self.batch_input.addItem(
                batch.name,
                batch.id,
            )

        self.date_of_birth_input = QDateEdit()
        self.date_of_birth_input.setCalendarPopup(True)
        self.date_of_birth_input.setDisplayFormat("dd/MM/yyyy")
        self.date_of_birth_input.setSpecialValueText("Date of birth")
        self.date_of_birth_input.setMinimumDate(
            QDate(1900, 1, 1)
        )
        self.date_of_birth_input.setDate(
            self.date_of_birth_input.minimumDate()
        )

        self.school_input = QLineEdit()
        self.school_input.setPlaceholderText(
            "School name"
        )

        self.admission_date_input = QDateEdit()
        self.admission_date_input.setCalendarPopup(True)

        self.status_input = QComboBox()
        self.status_input.addItems([
            "ACTIVE",
            "INACTIVE",
            "LEFT",
        ])

        self.notes_input = QPlainTextEdit()
        self.notes_input.setPlaceholderText(
            "Additional notes..."
        )
        self.notes_input.setMaximumHeight(90)

        form.addRow("Admission No.", self.admission_number_input)
        form.addRow("First Name *", self.first_name_input)
        form.addRow("Last Name", self.last_name_input)
        form.addRow("Parent Name *", self.parent_name_input)
        form.addRow("Parent Phone", self.parent_phone_input)
        form.addRow("WhatsApp Number", self.whatsapp_input)
        form.addRow("Batch *", self.batch_input)
        form.addRow("Date of Birth", self.date_of_birth_input)
        form.addRow("School", self.school_input)
        form.addRow("Admission Date", self.admission_date_input)
        form.addRow("Status", self.status_input)
        form.addRow("Notes", self.notes_input)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Save
        )

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)