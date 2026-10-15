"""
Teaching dialogs — Lesson planning, class recording, homework management.
"""
from __future__ import annotations

from datetime import date, timedelta

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.database.connection import SessionLocal
from app.database.models.lesson import ClassRecord, Homework, Lesson
from app.services.batch_service import get_active_batches
from app.services.lesson_service import (
    LESSON_STATUSES,
    create_lesson,
    update_lesson,
    get_lesson,
    create_class_record,
    update_class_record,
    get_class_records,
    create_homework,
    update_homework,
    get_homeworks,
    get_lessons,
)

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


def _qdate(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


def _styled_btn(text: str, primary: bool = False) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFixedHeight(36)
    if primary:
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {NAVY}; color: {WHITE}; border: none;
                border-radius: 7px; padding: 6px 14px; font-weight: 600; font-size: 13px;
            }}
            QPushButton:hover {{ background: {DARK_NAVY}; }}
        """)
    else:
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {WHITE}; color: {NAVY}; border: 1px solid {LIGHT_GOLD};
                border-radius: 7px; padding: 6px 14px; font-weight: 600; font-size: 13px;
            }}
            QPushButton:hover {{ background: {LIGHT_GOLD}; }}
        """)
    return btn


def _dialog_style() -> str:
    return f"""
        QDialog {{ background: {CREAM}; }}
        QLabel {{ color: {NAVY}; font-size: 13px; }}
        QLineEdit, QTextEdit, QSpinBox, QDateEdit {{
            background: {WHITE}; border: 1px solid {LIGHT_GOLD};
            border-radius: 6px; padding: 6px 10px; font-size: 13px; color: {TEXT};
        }}
        QComboBox {{
            background: {WHITE}; border: 1px solid {LIGHT_GOLD};
            border-radius: 6px; padding: 6px 28px 6px 10px; font-size: 13px; color: {TEXT};
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
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {{
            border: 1.5px solid {NAVY};
        }}
    """


# ─────────────────────────────────────────────────────────────
# Lesson Dialog (create / edit)
# ─────────────────────────────────────────────────────────────

class LessonDialog(QDialog):
    def __init__(self, lesson_id: int | None = None, default_batch_id: int | None = None, parent=None):
        super().__init__(parent)
        self.lesson_id = lesson_id
        self.setWindowTitle("Edit Lesson" if lesson_id else "Plan a Lesson")
        self.resize(540, 600)
        self.setStyleSheet(_dialog_style())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        title_lbl = QLabel("Edit Lesson" if lesson_id else "Plan a New Lesson")
        title_lbl.setStyleSheet(f"color: {NAVY}; font-size: 18px; font-weight: 700;")
        layout.addWidget(title_lbl)

        form = QFormLayout()
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # Batch
        self.batch_combo = QComboBox()
        self.batch_combo.setFixedHeight(36)
        with SessionLocal() as s:
            batches = get_active_batches(s)
        self._batch_map: dict[str, int] = {}
        for b in batches:
            self.batch_combo.addItem(b.name, b.id)
            self._batch_map[b.name] = b.id
        if default_batch_id:
            idx = self.batch_combo.findData(default_batch_id)
            if idx >= 0:
                self.batch_combo.setCurrentIndex(idx)

        # Title
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("e.g. Introduction to Kinematics")
        self.title_edit.setFixedHeight(36)

        # Chapter
        self.chapter_edit = QLineEdit()
        self.chapter_edit.setPlaceholderText("e.g. Chapter 3 – Motion")
        self.chapter_edit.setFixedHeight(36)

        # Topic
        self.topic_edit = QLineEdit()
        self.topic_edit.setPlaceholderText("e.g. Velocity and acceleration")
        self.topic_edit.setFixedHeight(36)

        # Description
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("Learning objectives or detailed description…")
        self.desc_edit.setFixedHeight(90)

        # Planned date
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(_qdate(date.today()))
        self.date_edit.setFixedHeight(36)

        # Duration
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(0, 480)
        self.duration_spin.setValue(60)
        self.duration_spin.setSuffix(" min")
        self.duration_spin.setFixedHeight(36)
        self.duration_spin.setSpecialValueText("Not set")

        # Sequence order
        self.seq_spin = QSpinBox()
        self.seq_spin.setRange(0, 9999)
        self.seq_spin.setValue(0)
        self.seq_spin.setFixedHeight(36)
        self.seq_spin.setSpecialValueText("Auto")

        # Status
        self.status_combo = QComboBox()
        self.status_combo.setFixedHeight(36)
        for s in LESSON_STATUSES:
            self.status_combo.addItem(s.replace("_", " ").title(), s)

        # Notes
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Additional notes…")
        self.notes_edit.setFixedHeight(70)

        form.addRow("Batch *:", self.batch_combo)
        form.addRow("Title *:", self.title_edit)
        form.addRow("Chapter / Unit:", self.chapter_edit)
        form.addRow("Topic:", self.topic_edit)
        form.addRow("Description:", self.desc_edit)
        form.addRow("Planned Date *:", self.date_edit)
        form.addRow("Est. Duration:", self.duration_spin)
        form.addRow("Sequence No.:", self.seq_spin)
        form.addRow("Status:", self.status_combo)
        form.addRow("Notes:", self.notes_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Pre-fill if editing
        if lesson_id:
            self._populate(lesson_id)

    def _populate(self, lesson_id: int):
        with SessionLocal() as s:
            lesson = get_lesson(s, lesson_id)
        if not lesson:
            return
        idx = self.batch_combo.findData(lesson.batch_id)
        if idx >= 0:
            self.batch_combo.setCurrentIndex(idx)
        self.title_edit.setText(lesson.title)
        self.chapter_edit.setText(lesson.chapter or "")
        self.topic_edit.setText(lesson.topic or "")
        self.desc_edit.setPlainText(lesson.description or "")
        self.date_edit.setDate(_qdate(lesson.planned_date))
        self.duration_spin.setValue(lesson.duration_minutes or 0)
        self.seq_spin.setValue(lesson.sequence_order or 0)
        idx2 = self.status_combo.findData(lesson.status)
        if idx2 >= 0:
            self.status_combo.setCurrentIndex(idx2)
        self.notes_edit.setPlainText(lesson.notes or "")

    def _accept(self):
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Validation", "Lesson title is required.")
            return
        if self.batch_combo.currentData() is None:
            QMessageBox.warning(self, "Validation", "Please select a batch.")
            return

        batch_id = self.batch_combo.currentData()
        planned_date = self.date_edit.date().toPyDate()
        dur = self.duration_spin.value() or None
        seq = self.seq_spin.value() or None
        status = self.status_combo.currentData()

        try:
            with SessionLocal() as session:
                if self.lesson_id:
                    update_lesson(
                        session, self.lesson_id,
                        title=title,
                        chapter=self.chapter_edit.text() or None,
                        topic=self.topic_edit.text() or None,
                        description=self.desc_edit.toPlainText() or None,
                        planned_date=planned_date,
                        duration_minutes=dur,
                        sequence_order=seq,
                        status=status,
                        notes=self.notes_edit.toPlainText() or None,
                    )
                else:
                    create_lesson(
                        session,
                        batch_id=batch_id,
                        title=title,
                        chapter=self.chapter_edit.text() or None,
                        topic=self.topic_edit.text() or None,
                        description=self.desc_edit.toPlainText() or None,
                        planned_date=planned_date,
                        duration_minutes=dur,
                        sequence_order=seq,
                        status=status,
                        notes=self.notes_edit.toPlainText() or None,
                    )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))


# ─────────────────────────────────────────────────────────────
# Record Completed Class Dialog
# ─────────────────────────────────────────────────────────────

class RecordClassDialog(QDialog):
    def __init__(
        self,
        record_id: int | None = None,
        default_batch_id: int | None = None,
        default_lesson_id: int | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.record_id = record_id
        self.default_lesson_id = default_lesson_id
        self.setWindowTitle("Edit Class Record" if record_id else "Record Completed Class")
        self.resize(560, 640)
        self.setStyleSheet(_dialog_style())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        title_lbl = QLabel("Edit Class Record" if record_id else "Record a Completed Class")
        title_lbl.setStyleSheet(f"color: {NAVY}; font-size: 18px; font-weight: 700;")
        layout.addWidget(title_lbl)

        form = QFormLayout()
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.batch_combo = QComboBox()
        self.batch_combo.setFixedHeight(36)
        with SessionLocal() as s:
            batches = get_active_batches(s)
        for b in batches:
            self.batch_combo.addItem(b.name, b.id)
        if default_batch_id:
            idx = self.batch_combo.findData(default_batch_id)
            if idx >= 0:
                self.batch_combo.setCurrentIndex(idx)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(_qdate(date.today()))
        self.date_edit.setFixedHeight(36)

        # Optional link to a planned lesson
        self.lesson_combo = QComboBox()
        self.lesson_combo.setFixedHeight(36)
        self.lesson_combo.addItem("(No linked lesson — ad hoc)", None)
        self.batch_combo.currentIndexChanged.connect(self._reload_lessons)
        self._reload_lessons()

        self.chapter_edit = QLineEdit()
        self.chapter_edit.setPlaceholderText("Chapter or unit covered")
        self.chapter_edit.setFixedHeight(36)

        self.topic_edit = QLineEdit()
        self.topic_edit.setPlaceholderText("Main topic of the session")
        self.topic_edit.setFixedHeight(36)

        self.completed_edit = QTextEdit()
        self.completed_edit.setPlaceholderText("Topics fully completed…")
        self.completed_edit.setFixedHeight(75)

        self.partial_edit = QTextEdit()
        self.partial_edit.setPlaceholderText("Topics partially covered / left for next class…")
        self.partial_edit.setFixedHeight(60)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Session notes, student questions, observations…")
        self.notes_edit.setFixedHeight(75)

        self.next_topic_edit = QLineEdit()
        self.next_topic_edit.setPlaceholderText("What to teach next session")
        self.next_topic_edit.setFixedHeight(36)

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(0, 480)
        self.duration_spin.setValue(60)
        self.duration_spin.setSuffix(" min")
        self.duration_spin.setFixedHeight(36)
        self.duration_spin.setSpecialValueText("Not set")

        form.addRow("Batch *:", self.batch_combo)
        form.addRow("Class Date *:", self.date_edit)
        form.addRow("Linked Lesson:", self.lesson_combo)
        form.addRow("Chapter / Unit:", self.chapter_edit)
        form.addRow("Topic:", self.topic_edit)
        form.addRow("Completed Topics:", self.completed_edit)
        form.addRow("Partial / Next:", self.partial_edit)
        form.addRow("Session Notes:", self.notes_edit)
        form.addRow("Next Topic:", self.next_topic_edit)
        form.addRow("Duration:", self.duration_spin)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if record_id:
            self._populate(record_id)
        elif default_lesson_id:
            with SessionLocal() as s:
                lesson = s.get(Lesson, default_lesson_id)
            if lesson:
                idx = self.batch_combo.findData(lesson.batch_id)
                if idx >= 0:
                    self.batch_combo.setCurrentIndex(idx)
                self._reload_lessons()
                l_idx = self.lesson_combo.findData(lesson.id)
                if l_idx < 0:
                    label = f"{lesson.planned_date.strftime('%d %b')} — {lesson.title}"
                    self.lesson_combo.addItem(label, lesson.id)
                    l_idx = self.lesson_combo.findData(lesson.id)
                if l_idx >= 0:
                    self.lesson_combo.setCurrentIndex(l_idx)
                if lesson.chapter:
                    self.chapter_edit.setText(lesson.chapter)
                if lesson.topic:
                    self.topic_edit.setText(lesson.topic)

    def _reload_lessons(self):
        batch_id = self.batch_combo.currentData()
        self.lesson_combo.clear()
        self.lesson_combo.addItem("(No linked lesson — ad hoc)", None)
        if batch_id:
            with SessionLocal() as s:
                lessons = get_lessons(
                    s, batch_id=batch_id,
                    start_date=date.today() - timedelta(days=30),
                    end_date=date.today() + timedelta(days=7),
                )
            for lesson in reversed(lessons):
                label = f"{lesson.planned_date.strftime('%d %b')} — {lesson.title}"
                self.lesson_combo.addItem(label, lesson.id)

    def _populate(self, record_id: int):
        with SessionLocal() as s:
            rec = s.get(ClassRecord, record_id)
            if not rec:
                return
            idx = self.batch_combo.findData(rec.batch_id)
            if idx >= 0:
                self.batch_combo.setCurrentIndex(idx)
            self._reload_lessons()
            self.date_edit.setDate(_qdate(rec.class_date))
            self.chapter_edit.setText(rec.chapter or "")
            self.topic_edit.setText(rec.topic or "")
            self.completed_edit.setPlainText(rec.topics_completed or "")
            self.partial_edit.setPlainText(rec.topics_partial or "")
            self.notes_edit.setPlainText(rec.notes or "")
            self.next_topic_edit.setText(rec.next_topic or "")
            self.duration_spin.setValue(rec.duration_minutes or 0)
            if rec.lesson_id:
                l_idx = self.lesson_combo.findData(rec.lesson_id)
                if l_idx < 0:
                    linked_lesson = s.get(Lesson, rec.lesson_id)
                    if linked_lesson:
                        label = f"{linked_lesson.planned_date.strftime('%d %b')} — {linked_lesson.title}"
                        self.lesson_combo.addItem(label, linked_lesson.id)
                        l_idx = self.lesson_combo.findData(linked_lesson.id)
                if l_idx >= 0:
                    self.lesson_combo.setCurrentIndex(l_idx)

    def _accept(self):
        batch_id = self.batch_combo.currentData()
        if batch_id is None:
            QMessageBox.warning(self, "Validation", "Please select a batch.")
            return

        class_date = self.date_edit.date().toPyDate()
        lesson_id = self.lesson_combo.currentData()
        dur = self.duration_spin.value() or None

        try:
            with SessionLocal() as session:
                if self.record_id:
                    update_class_record(
                        session, self.record_id,
                        class_date=class_date,
                        chapter=self.chapter_edit.text() or None,
                        topic=self.topic_edit.text() or None,
                        topics_completed=self.completed_edit.toPlainText() or None,
                        topics_partial=self.partial_edit.toPlainText() or None,
                        notes=self.notes_edit.toPlainText() or None,
                        next_topic=self.next_topic_edit.text() or None,
                        duration_minutes=dur,
                        lesson_id=lesson_id,
                    )
                else:
                    create_class_record(
                        session,
                        batch_id=batch_id,
                        class_date=class_date,
                        chapter=self.chapter_edit.text() or None,
                        topic=self.topic_edit.text() or None,
                        topics_completed=self.completed_edit.toPlainText() or None,
                        topics_partial=self.partial_edit.toPlainText() or None,
                        notes=self.notes_edit.toPlainText() or None,
                        next_topic=self.next_topic_edit.text() or None,
                        duration_minutes=dur,
                        lesson_id=lesson_id,
                    )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))


# ─────────────────────────────────────────────────────────────
# Homework Dialog
# ─────────────────────────────────────────────────────────────

class HomeworkDialog(QDialog):
    def __init__(self, hw_id: int | None = None, default_batch_id: int | None = None, parent=None):
        super().__init__(parent)
        self.hw_id = hw_id
        self.setWindowTitle("Edit Homework" if hw_id else "Add Homework / Assignment")
        self.resize(500, 480)
        self.setStyleSheet(_dialog_style())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        title_lbl = QLabel("Edit Homework" if hw_id else "Add Homework / Assignment")
        title_lbl.setStyleSheet(f"color: {NAVY}; font-size: 18px; font-weight: 700;")
        layout.addWidget(title_lbl)

        form = QFormLayout()
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.batch_combo = QComboBox()
        self.batch_combo.setFixedHeight(36)
        with SessionLocal() as s:
            batches = get_active_batches(s)
        for b in batches:
            self.batch_combo.addItem(b.name, b.id)
        if default_batch_id:
            idx = self.batch_combo.findData(default_batch_id)
            if idx >= 0:
                self.batch_combo.setCurrentIndex(idx)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("e.g. Exercise 3.1 Q 1–10, Draw a ray diagram")
        self.title_edit.setFixedHeight(36)

        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("Detailed instructions or questions…")
        self.desc_edit.setFixedHeight(90)

        self.assigned_edit = QDateEdit()
        self.assigned_edit.setCalendarPopup(True)
        self.assigned_edit.setDate(_qdate(date.today()))
        self.assigned_edit.setFixedHeight(36)

        self.due_edit = QDateEdit()
        self.due_edit.setCalendarPopup(True)
        self.due_edit.setDate(_qdate(date.today() + timedelta(days=3)))
        self.due_edit.setFixedHeight(36)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Additional notes…")
        self.notes_edit.setFixedHeight(60)

        form.addRow("Batch *:", self.batch_combo)
        form.addRow("Title *:", self.title_edit)
        form.addRow("Instructions:", self.desc_edit)
        form.addRow("Assigned Date:", self.assigned_edit)
        form.addRow("Due Date:", self.due_edit)
        form.addRow("Notes:", self.notes_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if hw_id:
            self._populate(hw_id)

    def _populate(self, hw_id: int):
        with SessionLocal() as s:
            hw = s.get(Homework, hw_id)
        if not hw:
            return
        idx = self.batch_combo.findData(hw.batch_id)
        if idx >= 0:
            self.batch_combo.setCurrentIndex(idx)
        self.title_edit.setText(hw.title)
        self.desc_edit.setPlainText(hw.description or "")
        self.assigned_edit.setDate(_qdate(hw.assigned_date))
        if hw.due_date:
            self.due_edit.setDate(_qdate(hw.due_date))
        self.notes_edit.setPlainText(hw.notes or "")

    def _accept(self):
        batch_id = self.batch_combo.currentData()
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Validation", "Homework title is required.")
            return
        if batch_id is None:
            QMessageBox.warning(self, "Validation", "Please select a batch.")
            return

        try:
            with SessionLocal() as session:
                if self.hw_id:
                    update_homework(
                        session, self.hw_id,
                        title=title,
                        description=self.desc_edit.toPlainText() or None,
                        assigned_date=self.assigned_edit.date().toPyDate(),
                        due_date=self.due_edit.date().toPyDate(),
                        notes=self.notes_edit.toPlainText() or None,
                    )
                else:
                    create_homework(
                        session,
                        batch_id=batch_id,
                        title=title,
                        description=self.desc_edit.toPlainText() or None,
                        assigned_date=self.assigned_edit.date().toPyDate(),
                        due_date=self.due_edit.date().toPyDate(),
                        notes=self.notes_edit.toPlainText() or None,
                    )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))


# ─────────────────────────────────────────────────────────────
# Lesson Detail Dialog (view only)
# ─────────────────────────────────────────────────────────────

class LessonDetailDialog(QDialog):
    def __init__(self, lesson_id: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Lesson Details")
        self.resize(560, 500)
        self.setStyleSheet(_dialog_style())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)

        with SessionLocal() as s:
            lesson = get_lesson(s, lesson_id)

        if not lesson:
            layout.addWidget(QLabel("Lesson not found."))
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            buttons.rejected.connect(self.reject)
            layout.addWidget(buttons)
            return

        def row(lbl: str, val: str):
            w = QWidget()
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(10)
            l = QLabel(f"<b>{lbl}</b>")
            l.setMinimumWidth(130)
            l.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
            v = QLabel(val)
            v.setWordWrap(True)
            v.setStyleSheet(f"color: {TEXT}; font-size: 13px;")
            h.addWidget(l)
            h.addWidget(v, 1)
            return w

        heading = QLabel(lesson.title)
        heading.setStyleSheet(f"color: {NAVY}; font-size: 18px; font-weight: 700;")
        layout.addWidget(heading)

        status_colors = {
            "COMPLETED": ("#DCFCE7", "#15803D"),
            "PLANNED": ("#DBEAFE", "#1D4ED8"),
            "IN_PROGRESS": ("#FEF3C7", "#B45309"),
            "CANCELLED": ("#F3F4F6", "#6B7280"),
        }
        bg, fg = status_colors.get(lesson.status, ("#F3F4F6", "#6B7280"))
        status_badge = QLabel(lesson.status.replace("_", " ").title())
        status_badge.setStyleSheet(
            f"background: {bg}; color: {fg}; font-size: 11px; font-weight: 700;"
            f" padding: 4px 10px; border-radius: 4px;"
        )
        layout.addWidget(status_badge, alignment=Qt.AlignmentFlag.AlignLeft)

        frame = QFrame()
        frame.setStyleSheet(f"QFrame {{ background: {WHITE}; border: 1px solid {LIGHT_GOLD}; border-radius: 8px; }}")
        f_layout = QVBoxLayout(frame)
        f_layout.setContentsMargins(14, 12, 14, 12)
        f_layout.setSpacing(6)
        f_layout.addWidget(row("Planned Date:", lesson.planned_date.strftime("%d %b %Y")))
        f_layout.addWidget(row("Chapter / Unit:", lesson.chapter or "—"))
        f_layout.addWidget(row("Topic:", lesson.topic or "—"))
        if lesson.description:
            f_layout.addWidget(row("Description:", lesson.description))
        f_layout.addWidget(row("Duration:", f"{lesson.duration_minutes} min" if lesson.duration_minutes else "—"))
        f_layout.addWidget(row("Sequence:", str(lesson.sequence_order) if lesson.sequence_order else "—"))
        if lesson.notes:
            f_layout.addWidget(row("Notes:", lesson.notes))
        layout.addWidget(frame)

        # Linked class records
        if lesson.class_records:
            cr_lbl = QLabel(f"Class Records ({len(lesson.class_records)})")
            cr_lbl.setStyleSheet(f"color: {NAVY}; font-size: 14px; font-weight: 700;")
            layout.addWidget(cr_lbl)
            for cr in sorted(lesson.class_records, key=lambda r: r.class_date, reverse=True):
                cr_row = QFrame()
                cr_row.setStyleSheet(f"QFrame {{ background: {CREAM}; border: 1px solid {LIGHT_GOLD}; border-radius: 6px; }}")
                cr_lay = QVBoxLayout(cr_row)
                cr_lay.setContentsMargins(10, 8, 10, 8)
                cr_lay.setSpacing(2)
                cr_lay.addWidget(QLabel(f"<b>{cr.class_date.strftime('%d %b %Y')}</b> — {cr.topic or cr.chapter or 'Session'}"))
                if cr.topics_completed:
                    cr_lay.addWidget(QLabel(f"Covered: {cr.topics_completed[:120]}"))
                if cr.next_topic:
                    cr_lay.addWidget(QLabel(f"Next: {cr.next_topic}"))
                layout.addWidget(cr_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
