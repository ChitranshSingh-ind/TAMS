"""
TAMS Analysis & Institutional Reports Page Controller Mixin.

Renders multi-tab academic and financial intelligence:
  - At-Risk Student Early Warning System (attendance drops, failing tests)
  - Coaching KPI Overview & High-level metrics
  - Student Academic Performance Matrices (scores, trends, percentiles)
  - Cross-Batch Performance Comparisons
  - Attendance & Teaching Velocity Analytics
  - Financial Revenue vs. Operational Expense P&L
  - Visual Bar & Segmented Distribution Charts
  - CSV Report Export
"""

from datetime import date, datetime, timedelta

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.database.connection import SessionLocal
from app.services.analytics_service import (
    export_analytics_report_csv,
    get_attendance_analytics,
    get_batch_comparison_data,
    get_coaching_overview,
    get_student_improvement_analysis,
    get_student_performance_records,
    get_student_risk_analysis,
    get_teaching_analytics,
    get_tests_analytics,
)
from app.services.financial_service import (
    get_financial_summary,
    get_monthly_financial_comparison,
)
from app.ui.chart_widgets import (
    SegmentedDistributionWidget,
    SimpleBarChartWidget,
)
from app.ui.table_utils import (
    TableSizingStrategy,
    auto_fit_columns,
    configure_table_ux,
)


class AnalysisMixin:
    """
    Mixin providing the comprehensive Analysis & Reports page: tabbed diagnostic dashboards,
    trend charts, risk matrices, and multi-metric CSV reports.
    """
    """Mixin providing Analysis & Reports page creation, risk tracking, and trend charts."""

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
        self.analysis_risk_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        configure_table_ux(
            self.analysis_risk_table,
            column_widths=[220, 160, 140, 300, 130, 130, 300, 120],
            flexible_columns=[0, 3, 6],
            fixed_columns=[7],
            strategy=TableSizingStrategy.WIDE_SCROLLABLE,
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
        self.analysis_trajectory_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        configure_table_ux(
            self.analysis_trajectory_table,
            column_widths=[220, 160, 130, 150, 150, 140, 140, 120],
            flexible_columns=[0, 1],
            fixed_columns=[7],
            strategy=TableSizingStrategy.WIDE_SCROLLABLE,
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
        self.analysis_student_perf_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        configure_table_ux(
            self.analysis_student_perf_table,
            column_widths=[140, 240, 160, 130, 120, 120, 120, 120, 120, 130, 130, 130],
            flexible_columns=[1, 2],
            fixed_columns=[11],
            strategy=TableSizingStrategy.WIDE_SCROLLABLE,
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
        self.analysis_batch_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        configure_table_ux(
            self.analysis_batch_table,
            column_widths=[240, 150, 150, 160, 180, 160, 160],
            flexible_columns=[0],
            strategy=TableSizingStrategy.BOUNDED_AND_FLEXIBLE,
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
        self.analysis_tests_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        configure_table_ux(
            self.analysis_tests_table,
            column_widths=[260, 160, 130, 120, 180, 140, 120, 120, 170],
            flexible_columns=[0, 1],
            strategy=TableSizingStrategy.WIDE_SCROLLABLE,
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
        self.analysis_attendance_alert_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        configure_table_ux(
            self.analysis_attendance_alert_table,
            column_widths=[260, 170, 140, 130, 130, 180, 140],
            flexible_columns=[0, 1],
            fixed_columns=[6],
            strategy=TableSizingStrategy.BOUNDED_AND_FLEXIBLE,
            alternating_colors=True,
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
        self.analysis_syllabus_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        configure_table_ux(
            self.analysis_syllabus_table,
            column_widths=[320, 160, 150, 150, 170],
            flexible_columns=[0],
            strategy=TableSizingStrategy.BOUNDED_AND_FLEXIBLE,
            alternating_colors=True,
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
        self.analysis_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        configure_table_ux(
            self.analysis_table,
            column_widths=[160, 200, 200, 180, 180, 180, 180],
            stretch_column=None,
            flexible_columns=[0, 1, 2, 3, 4, 5, 6],
            strategy=TableSizingStrategy.WIDE_SCROLLABLE,
            alternating_colors=True,
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

        auto_fit_columns(self.analysis_table)

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

        auto_fit_columns(self.analysis_trajectory_table)

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

        auto_fit_columns(self.analysis_risk_table)

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

        auto_fit_columns(self.analysis_student_perf_table)

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

        auto_fit_columns(self.analysis_batch_table)

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

        auto_fit_columns(self.analysis_tests_table)

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

        auto_fit_columns(self.analysis_attendance_alert_table)
        auto_fit_columns(self.analysis_syllabus_table)

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

