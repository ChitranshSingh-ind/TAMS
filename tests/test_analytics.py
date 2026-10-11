import os
import sys
import uuid
import tempfile
from datetime import date, timedelta
import pytest
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox
from PyQt6.QtCore import Qt

from app.database.connection import SessionLocal
from app.services.batch_service import create_batch
from app.services.student_service import create_student
from app.database.models.test import TestModel
from app.database.models.test_result import TestResult
from app.database.models.attendance import Attendance
from app.database.models.lesson import Lesson, ClassRecord
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
from app.ui.main_window import MainWindow
from app.ui.chart_widgets import (
    SimpleBarChartWidget,
    SegmentedDistributionWidget,
    TrendLineChartWidget,
)


@pytest.fixture(scope="session")
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def analytics_test_data():
    unique_id = uuid.uuid4().hex[:8]
    today = date.today()

    with SessionLocal() as session:
        # Create batch
        batch = create_batch(session, name=f"Batch_{unique_id}")

        # Create students:
        # Student 1: High risk (low attendance, failing tests, dropping trend)
        s_risk = create_student(
            session,
            first_name="Risk",
            last_name="Student",
            batch_id=batch.id,
            admission_number=f"RISK_{unique_id}",
        )
        # Student 2: Improving student (started lower, scoring higher)
        s_imp = create_student(
            session,
            first_name="Improving",
            last_name="Student",
            batch_id=batch.id,
            admission_number=f"IMP_{unique_id}",
        )
        # Student 3: Consistent star student
        s_star = create_student(
            session,
            first_name="Star",
            last_name="Student",
            batch_id=batch.id,
            admission_number=f"STAR_{unique_id}",
        )

        # Create tests
        t1 = TestModel(
            name="Diagnostic Test",
            batch_id=batch.id,
            test_date=today - timedelta(days=20),
            max_marks=100.0,
        )
        t2 = TestModel(
            name="Mid-Term Test",
            batch_id=batch.id,
            test_date=today - timedelta(days=5),
            max_marks=100.0,
        )
        session.add_all([t1, t2])
        session.commit()

        # Add test results:
        # s_risk: 40 -> 25 (declining, low score)
        # s_imp: 50 -> 85 (improving)
        # s_star: 90 -> 95 (stable high)
        r1_risk = TestResult(test_id=t1.id, student_id=s_risk.id, marks=40.0)
        r2_risk = TestResult(test_id=t2.id, student_id=s_risk.id, marks=25.0)

        r1_imp = TestResult(test_id=t1.id, student_id=s_imp.id, marks=50.0)
        r2_imp = TestResult(test_id=t2.id, student_id=s_imp.id, marks=85.0)

        r1_star = TestResult(test_id=t1.id, student_id=s_star.id, marks=90.0)
        r2_star = TestResult(test_id=t2.id, student_id=s_star.id, marks=95.0)

        session.add_all([r1_risk, r2_risk, r1_imp, r2_imp, r1_star, r2_star])

        # Add attendance:
        # s_risk has low attendance + consecutive absences
        session.add(Attendance(student_id=s_risk.id, batch_id=batch.id, date=today - timedelta(days=4), status="ABSENT"))
        session.add(Attendance(student_id=s_risk.id, batch_id=batch.id, date=today - timedelta(days=3), status="ABSENT"))
        session.add(Attendance(student_id=s_risk.id, batch_id=batch.id, date=today - timedelta(days=2), status="ABSENT"))
        session.add(Attendance(student_id=s_risk.id, batch_id=batch.id, date=today - timedelta(days=1), status="PRESENT"))

        # s_imp has 100% attendance
        session.add(Attendance(student_id=s_imp.id, batch_id=batch.id, date=today - timedelta(days=2), status="PRESENT"))
        session.add(Attendance(student_id=s_imp.id, batch_id=batch.id, date=today - timedelta(days=1), status="PRESENT"))

        # s_star has 100% attendance
        session.add(Attendance(student_id=s_star.id, batch_id=batch.id, date=today - timedelta(days=2), status="PRESENT"))
        session.add(Attendance(student_id=s_star.id, batch_id=batch.id, date=today - timedelta(days=1), status="PRESENT"))

        # Add lessons & chapter progress
        l1 = Lesson(batch_id=batch.id, title="Kinematics 101", chapter="Mechanics", topic="Kinematics", planned_date=today - timedelta(days=10), status="COMPLETED")
        l2 = Lesson(batch_id=batch.id, title="Dynamics 101", chapter="Mechanics", topic="Dynamics", planned_date=today - timedelta(days=5), status="COMPLETED")
        l3 = Lesson(batch_id=batch.id, title="Heat Transfer 101", chapter="Thermodynamics", topic="Heat Transfer", planned_date=today + timedelta(days=2), status="PLANNED")
        session.add_all([l1, l2, l3])

        session.commit()

        return {
            "batch_id": batch.id,
            "student_risk_id": s_risk.id,
            "student_imp_id": s_imp.id,
            "student_star_id": s_star.id,
        }


def test_coaching_overview_service(analytics_test_data):
    batch_id = analytics_test_data["batch_id"]
    with SessionLocal() as session:
        overview = get_coaching_overview(session, batch_id=batch_id)

        assert overview["active_students"] == 3
        assert overview["students_tested"] == 3
        assert overview["avg_score_pct"] > 0
        assert overview["high_risk_count"] >= 1
        assert overview["improving_count"] >= 1
        assert "score_bands" in overview
        assert overview["score_bands"]["Distinction (>=80%)"] >= 1
        assert len(overview["action_items"]) > 0


def test_student_risk_analysis_service(analytics_test_data):
    batch_id = analytics_test_data["batch_id"]
    with SessionLocal() as session:
        risks = get_student_risk_analysis(session, batch_id=batch_id)
        assert len(risks) == 3

        # First student in priority order should be High Attention
        high_risk = risks[0]
        assert high_risk["risk_level"] == "High Attention"
        assert len(high_risk["reasons"]) >= 2
        assert high_risk["student_id"] == analytics_test_data["student_risk_id"]
        assert "parent call" in high_risk["recommendation"] or "revision" in high_risk["recommendation"]


def test_student_improvement_analysis_service(analytics_test_data):
    batch_id = analytics_test_data["batch_id"]
    with SessionLocal() as session:
        improvements = get_student_improvement_analysis(session, batch_id=batch_id)
        assert len(improvements) == 3

        # Check improving student
        imp_stu = next(s for s in improvements if s["student_id"] == analytics_test_data["student_imp_id"])
        assert imp_stu["trend"] == "Improving"
        assert imp_stu["delta"] > 0

        # Check declining student
        dec_stu = next(s for s in improvements if s["student_id"] == analytics_test_data["student_risk_id"])
        assert dec_stu["trend"] == "Declining"
        assert dec_stu["delta"] < 0


def test_student_performance_records_service(analytics_test_data):
    batch_id = analytics_test_data["batch_id"]
    with SessionLocal() as session:
        records = get_student_performance_records(session, batch_id=batch_id)
        assert len(records) == 3

        star_record = next(r for r in records if r["student_id"] == analytics_test_data["student_star_id"])
        assert star_record["avg_pct"] >= 90.0
        assert star_record["diff_from_batch"] > 0
        assert star_record["trend"] in ("Improving", "Stable")


def test_attendance_and_teaching_analytics_services(analytics_test_data):
    batch_id = analytics_test_data["batch_id"]
    with SessionLocal() as session:
        att = get_attendance_analytics(session, batch_id=batch_id)
        assert "overall_attendance_pct" in att
        assert "distribution_bands" in att
        assert len(att["low_attendance_students"]) >= 1

        teach = get_teaching_analytics(session, batch_id=batch_id)
        assert teach["total_lessons"] == 3
        assert teach["completed_lessons"] == 2
        assert teach["completion_rate_pct"] > 60.0
        assert len(teach["chapters"]) == 2


def test_export_analytics_reports_csv(analytics_test_data):
    batch_id = analytics_test_data["batch_id"]
    with SessionLocal() as session:
        for r_type in ["risk", "performance", "batches", "syllabus"]:
            csv_str = export_analytics_report_csv(session, report_type=r_type, batch_id=batch_id)
            assert len(csv_str) > 20
            lines = csv_str.strip().split("\r\n") if "\r\n" in csv_str else csv_str.strip().split("\n")
            assert len(lines) >= 2


def test_analysis_page_ui_full_integration(qapp, analytics_test_data):
    win = MainWindow()
    win.change_page(7)  # Analysis section

    assert win.pages.currentIndex() == 7
    assert hasattr(win, "analysis_tabs")
    assert win.analysis_tabs.count() == 6

    # Verify tab names
    expected_tab_names = [
        "Student Risk & Improvement",
        "Coaching Overview",
        "Student Performance",
        "Batches & Assessments",
        "Attendance & Teaching",
        "Fees & Finances",
    ]
    for idx, expected in enumerate(expected_tab_names):
        assert expected in win.analysis_tabs.tabText(idx)

    # Verify Centrepiece: Student Risk tab
    assert hasattr(win, "risk_kpi_high")
    assert hasattr(win, "risk_kpi_moderate")
    assert hasattr(win, "risk_kpi_improving")
    assert hasattr(win, "risk_kpi_declining")
    assert hasattr(win, "analysis_risk_table")
    assert hasattr(win, "analysis_trajectory_table")
    assert win.analysis_risk_table.columnCount() == 8
    assert win.analysis_trajectory_table.columnCount() == 8

    # Verify Coaching Overview tab
    assert hasattr(win, "overview_kpi_active_students")
    assert hasattr(win, "overview_batch_score_chart")
    assert hasattr(win, "overview_score_band_chart")

    # Verify Student Performance tab
    assert hasattr(win, "analysis_student_perf_table")
    assert win.analysis_student_perf_table.columnCount() == 12

    # Verify Batches & Assessments tab
    assert hasattr(win, "analysis_batch_table")
    assert hasattr(win, "analysis_tests_table")
    assert win.analysis_batch_table.columnCount() == 7
    assert win.analysis_tests_table.columnCount() == 9

    # Verify Attendance & Teaching tab
    assert hasattr(win, "attendance_band_chart")
    assert hasattr(win, "teaching_status_chart")
    assert hasattr(win, "analysis_attendance_alert_table")
    assert hasattr(win, "analysis_syllabus_table")
    assert win.analysis_attendance_alert_table.columnCount() == 7
    assert win.analysis_syllabus_table.columnCount() == 5

    # Verify Preserved Financials tab
    assert hasattr(win, "analysis_kpi_inflow")
    assert hasattr(win, "analysis_kpi_outflow")
    assert hasattr(win, "analysis_kpi_net_cash")
    assert hasattr(win, "analysis_kpi_receivables")
    assert hasattr(win, "analysis_kpi_payables")
    assert hasattr(win, "analysis_kpi_accrual")
    assert hasattr(win, "analysis_table")
    assert win.analysis_table.columnCount() == 7
    assert win.analysis_table.rowCount() == 6


def test_analysis_ui_search_and_filters(qapp, analytics_test_data):
    win = MainWindow()
    win.change_page(7)

    # Test risk search
    win.analysis_risk_search.setText("Risk")
    assert win.analysis_risk_table.rowCount() >= 1

    win.analysis_risk_search.setText("NonExistentStudentName123")
    assert win.analysis_risk_table.rowCount() == 0

    win.analysis_risk_search.clear()

    # Test risk severity dropdown
    win.analysis_risk_filter.setCurrentText("High Attention Only")
    # All displayed rows must have HIGH ATTENTION badge
    for r in range(win.analysis_risk_table.rowCount()):
        cell_widget = win.analysis_risk_table.cellWidget(r, 2)
        assert cell_widget is not None

    # Test student perf search
    win.student_perf_search.setText("Star")
    assert win.analysis_student_perf_table.rowCount() >= 1

    win.student_perf_search.clear()


def test_analysis_ui_export_action(qapp, monkeypatch, analytics_test_data):
    win = MainWindow()
    win.change_page(7)

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        temp_path = f.name

    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (temp_path, "CSV Files (*.csv)"),
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args, **kwargs: None,
    )

    win.export_analysis_report("risk")

    assert os.path.exists(temp_path)
    with open(temp_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Student ID" in content
    assert "Risk Level" in content

    os.remove(temp_path)


def test_chart_widgets_rendering_and_painting(qapp, analytics_test_data):
    from PyQt6.QtGui import QPixmap, QPainter

    # 1. Test MainWindow actual UI render & paint of all analysis tabs
    win = MainWindow()
    win.change_page(7)
    pix = QPixmap(1000, 800)
    for i in range(win.analysis_tabs.count()):
        win.analysis_tabs.setCurrentIndex(i)
        win.render(pix)

    # 2. Test SegmentedDistributionWidget with dicts, tuples, and empty
    seg = SegmentedDistributionWidget("Test Distribution")
    seg.resize(400, 150)
    # Tuples
    seg.set_data([("Band A", 5, "#16A34A"), ("Band B", 10, "#DC2626")])
    seg.render(QPixmap(400, 150))
    # Dicts
    seg.set_data([{"label": "Band C", "count": 2, "color": "#012D54"}])
    seg.render(QPixmap(400, 150))
    # Empty
    seg.set_data([])
    seg.render(QPixmap(400, 150))

    # 3. Test SimpleBarChartWidget with dicts, tuples, and empty
    bar = SimpleBarChartWidget("Test Bars")
    bar.resize(400, 200)
    bar.set_title("Updated Batch Title")
    assert bar.title == "Updated Batch Title"
    # Tuples
    bar.set_data([("Batch 1", 75.0, "#D9B85F"), ("Batch 2", 40.0, "#DC2626")])
    bar.render(QPixmap(400, 200))
    # Dicts with sublabel & val_text
    bar.set_data([{"label": "Batch 3", "value": 85.0, "color": "#16A34A", "sublabel": "10 students", "val_text": "85.0%"}])
    bar.render(QPixmap(400, 200))
    # Empty
    bar.set_data([])
    bar.render(QPixmap(400, 200))

    # 4. Test TrendLineChartWidget with points and empty
    trend = TrendLineChartWidget("Test Trend")
    trend.resize(400, 200)
    trend.set_data([("Test 1", 50.0), ("Test 2", 75.0), ("Test 3", 90.0)])
    trend.render(QPixmap(400, 200))
    trend.set_data([])
    trend.render(QPixmap(400, 200))

    # 5. Verify batch filter switching updates overview_batch_score_chart
    # Select first batch if available
    if win.analysis_batch_filter.count() > 1:
        win.analysis_batch_filter.setCurrentIndex(1)
        win.load_analysis()
        assert "Test Scores — " in win.overview_batch_score_chart.title
        # Switch back to All Batches
        win.analysis_batch_filter.setCurrentIndex(0)
        win.load_analysis()
        assert win.overview_batch_score_chart.title == "Batch Average Test Scores (%)"

