"""
TAMS Teaching & Syllabus Management Mixin.

Monitors curriculum progress across batches, covering:
  - Lessons and topics planning (Scheduled, Completed, Overdue, Cancelled)
  - Daily class records (teacher notes, topics taught, homework assigned)
  - Homework tracking and deadlines
  - Chapter-level completion progress bars
"""

from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
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
from app.services.batch_service import get_active_batches
from app.services.lesson_service import (
    delete_class_record,
    delete_homework,
    delete_lesson,
    get_chapters_progress,
    get_class_records,
    get_homeworks,
    get_lessons,
    get_teaching_summary,
    mark_lesson_completed,
)
from app.ui.table_utils import (
    TableSizingStrategy,
    auto_fit_columns,
    configure_table_ux,
)
from app.ui.teaching_dialogs import (
    HomeworkDialog,
    LessonDetailDialog,
    LessonDialog,
    RecordClassDialog,
)


class TeachingMixin:
    """
    Mixin providing Teaching UI: curriculum progress, lesson management tables,
    class logging dialogues, and homework assignments.
    """
    """Mixin providing Teaching page creation, syllabus lessons, class records, and homework."""

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
        configure_table_ux(
            self.lessons_table,
            column_widths=[120, 240, 170, 190, 110, 130, 150, 220],
            flexible_columns=[1, 3],
            strategy=TableSizingStrategy.WIDE_SCROLLABLE,
            default_row_height=48,
            alternating_colors=True,
        )
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
        configure_table_ux(
            self.class_records_table,
            column_widths=[120, 150, 170, 220, 180, 220, 140],
            flexible_columns=[2, 3, 5],
            strategy=TableSizingStrategy.WIDE_SCROLLABLE,
            default_row_height=48,
            alternating_colors=True,
        )
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
        configure_table_ux(
            self.homework_table,
            column_widths=[240, 150, 120, 120, 130, 140],
            flexible_columns=[0],
            strategy=TableSizingStrategy.BOUNDED_AND_FLEXIBLE,
            default_row_height=48,
            alternating_colors=True,
        )
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
        configure_table_ux(
            self.progress_table,
            column_widths=[260, 140, 130, 130, 150],
            flexible_columns=[0],
            strategy=TableSizingStrategy.BOUNDED_AND_FLEXIBLE,
            default_row_height=44,
            alternating_colors=True,
        )
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

        auto_fit_columns(self.lessons_table)
        auto_fit_columns(self.class_records_table)
        auto_fit_columns(self.homework_table)
        auto_fit_columns(self.progress_table)

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
        dlg = RecordClassDialog(default_lesson_id=lesson_id, parent=self)
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

