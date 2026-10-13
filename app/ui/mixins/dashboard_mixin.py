"""
TAMS Dashboard Page Controller Mixin.

Renders the primary home screen of TAMS, featuring:
  - Dynamic time-aware greeting ('Good morning', 'Good afternoon', etc.)
  - High-level KPI summary cards (Total Students, Today's Attendance, Pending Fees, Scheduled Tests)
  - Interactive drill-down navigation (clicking cards jumps directly to relevant module pages)
  - Daily scheduled lessons breakdown with chapters and topics
  - Actionable coaching alerts (fee overdue alerts, attendance warnings, upcoming exams)
"""

from datetime import date, datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.database.connection import SessionLocal
from app.services.attendance_service import count_present_students
from app.services.dashboard_service import get_dashboard_alerts
from app.services.fee_service import get_outstanding_amount
from app.services.lesson_service import get_lessons_for_date
from app.services.student_service import count_students
from app.services.test_service import count_upcoming_tests


class DashboardMixin:
    """
    Mixin providing Dashboard page construction and live metrics synchronization.
    Composed into MainWindow.
    """

    def create_dashboard_page(self) -> QWidget:
        """
        Builds the Dashboard QWidget view hierarchy with KPI cards,
        today's class schedule container, and alert feed.
        """
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
        self.dashboard_subtitle_label = subtitle

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
