"""
Analytics Service — Coaching Intelligence Suite.

Aggregates real database records across:
- Student performance & test trends
- Batch comparisons
- Attendance & engagement
- Test & assessment metrics
- Explainable student risk detection & recommendations
- Student improvement & decline comparisons
- Teaching & lesson completion effectiveness
- Syllabus chapter progress
- Student retention & enrollment
- CSV report generators
"""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Any

from sqlalchemy import func, select, case
from sqlalchemy.orm import Session

from app.database.models.student import Student
from app.database.models.batch import Batch
from app.database.models.test import TestModel
from app.database.models.test_result import TestResult
from app.database.models.attendance import Attendance
from app.database.models.lesson import Lesson, ClassRecord


# ─────────────────────────────────────────────────────────────────────────────
# 1. OVERVIEW & INTELLIGENCE SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def get_coaching_overview(
    session: Session,
    *,
    batch_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Returns high-level KPI counts and intervention action items for the teacher overview.
    """
    # Active students query
    student_stmt = select(Student).where(Student.status == "ACTIVE")
    if batch_id is not None:
        student_stmt = student_stmt.where(Student.batch_id == batch_id)
    active_students = list(session.scalars(student_stmt).all())
    total_active_students = len(active_students)

    # All tests in scope
    test_stmt = select(TestModel).order_by(TestModel.test_date.asc())
    if batch_id is not None:
        test_stmt = test_stmt.where(TestModel.batch_id == batch_id)
    if start_date is not None:
        test_stmt = test_stmt.where(TestModel.test_date >= start_date)
    if end_date is not None:
        test_stmt = test_stmt.where(TestModel.test_date <= end_date)
    tests = list(session.scalars(test_stmt).all())
    test_ids = [t.id for t in tests]

    # Scores calculation across tests
    avg_score_pct = 0.0
    students_tested_count = 0
    percentages: list[float] = []
    if test_ids:
        results_stmt = select(TestResult).where(TestResult.test_id.in_(test_ids))
        results = list(session.scalars(results_stmt).all())
        test_map = {t.id: t for t in tests}
        tested_students = set()
        for r in results:
            if getattr(r, "is_absent", False):
                continue
            t = test_map.get(r.test_id)
            if t and t.max_marks > 0:
                pct = (r.marks / t.max_marks) * 100.0
                percentages.append(pct)
                tested_students.add(r.student_id)
        if percentages:
            avg_score_pct = sum(percentages) / len(percentages)
        students_tested_count = len(tested_students)

    # Attendance overall in scope
    att_stmt = select(Attendance)
    if batch_id is not None:
        att_stmt = att_stmt.where(Attendance.batch_id == batch_id)
    if start_date is not None:
        att_stmt = att_stmt.where(Attendance.date >= start_date)
    if end_date is not None:
        att_stmt = att_stmt.where(Attendance.date <= end_date)
    att_records = list(session.scalars(att_stmt).all())
    required_att = sum(1 for a in att_records if a.status != "LEAVE")
    present_att = sum(1 for a in att_records if a.status in ("PRESENT", "LATE"))
    avg_attendance_pct = (present_att / required_att * 100.0) if required_att > 0 else 0.0

    # Risk detection summary
    risk_data = get_student_risk_analysis(
        session,
        batch_id=batch_id,
        start_date=start_date,
        end_date=end_date,
    )
    high_risk_count = sum(1 for r in risk_data if r["risk_level"] == "High Attention")
    needs_attn_count = sum(1 for r in risk_data if r["risk_level"] == "Needs Attention")

    # Improvement summary
    improvement_data = get_student_improvement_analysis(
        session,
        batch_id=batch_id,
    )
    improving_count = sum(1 for s in improvement_data if s["trend"] == "Improving")
    declining_count = sum(1 for s in improvement_data if s["trend"] == "Declining")

    # Teaching progress in scope
    lesson_stmt = select(Lesson)
    if batch_id is not None:
        lesson_stmt = lesson_stmt.where(Lesson.batch_id == batch_id)
    all_lessons = list(session.scalars(lesson_stmt).all())
    valid_lessons = [l for l in all_lessons if l.status != "CANCELLED"]
    completed_lessons = [l for l in valid_lessons if l.status == "COMPLETED"]
    syllabus_pct = (len(completed_lessons) / len(valid_lessons) * 100.0) if valid_lessons else 0.0

    # Urgent action items (top 5 high priority risk or decline cases)
    action_items = []
    for r in risk_data:
        if r["risk_level"] in ("High Attention", "Needs Attention"):
            action_items.append({
                "student_id": r["student_id"],
                "name": r["student_name"],
                "admission_number": r["admission_number"],
                "batch_name": r["batch_name"],
                "level": r["risk_level"],
                "reason": "; ".join(r["reasons"][:2]),
                "action": r["recommendation"],
            })
            if len(action_items) >= 6:
                break

    score_bands = {
        "Distinction (>=80%)": sum(1 for p in percentages if p >= 80.0),
        "Merit (60-79%)": sum(1 for p in percentages if 60.0 <= p < 80.0),
        "Pass (40-59%)": sum(1 for p in percentages if 40.0 <= p < 60.0),
        "Needs Help (<40%)": sum(1 for p in percentages if p < 40.0),
    }

    return {
        "active_students": total_active_students,
        "students_tested": students_tested_count,
        "avg_score_pct": round(avg_score_pct, 1),
        "avg_attendance_pct": round(avg_attendance_pct, 1),
        "high_risk_count": high_risk_count,
        "needs_attention_count": needs_attn_count,
        "improving_count": improving_count,
        "declining_count": declining_count,
        "syllabus_completion_pct": round(syllabus_pct, 1),
        "score_bands": score_bands,
        "action_items": action_items,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. STUDENT PERFORMANCE ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

def get_student_performance_records(
    session: Session,
    *,
    batch_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """
    Computes per-student performance metrics:
    - Tests attended vs total batch tests
    - Average %, highest %, lowest %
    - Performance vs batch average gap
    - Trend direction
    - Attendance %
    """
    # 1. Fetch relevant students
    stmt = select(Student)
    if batch_id is not None:
        stmt = stmt.where(Student.batch_id == batch_id)
    students = list(session.scalars(stmt).all())

    if search:
        s_term = search.strip().lower()
        students = [
            s for s in students
            if s_term in s.first_name.lower()
            or (s.last_name and s_term in s.last_name.lower())
            or (s.admission_number and s_term in s.admission_number.lower())
        ]

    # Pre-fetch all batches for fast name lookup
    batches = {b.id: b for b in session.scalars(select(Batch)).all()}

    # Fetch tests in date range
    t_stmt = select(TestModel)
    if start_date is not None:
        t_stmt = t_stmt.where(TestModel.test_date >= start_date)
    if end_date is not None:
        t_stmt = t_stmt.where(TestModel.test_date <= end_date)
    tests = list(session.scalars(t_stmt).all())
    test_map = {t.id: t for t in tests}

    # Fetch test results for these tests
    if tests:
        res_stmt = select(TestResult).where(TestResult.test_id.in_([t.id for t in tests]))
        results = list(session.scalars(res_stmt).all())
    else:
        results = []

    # Map student_id -> list of test results sorted by test_date
    student_results: dict[int, list[TestResult]] = {}
    for r in results:
        student_results.setdefault(r.student_id, []).append(r)

    # Sort each student's results chronologically
    for sid, rlist in student_results.items():
        rlist.sort(key=lambda res: test_map[res.test_id].test_date if res.test_id in test_map else date.min)

    # Fetch attendance summaries per student
    att_stmt = select(
        Attendance.student_id,
        func.sum(case((Attendance.status != "LEAVE", 1), else_=0)).label("total"),
        func.sum(case((Attendance.status.in_(("PRESENT", "LATE")), 1), else_=0)).label("present"),
    ).group_by(Attendance.student_id)
    if start_date:
        att_stmt = att_stmt.where(Attendance.date >= start_date)
    if end_date:
        att_stmt = att_stmt.where(Attendance.date <= end_date)
    att_map = {}
    for row in session.execute(att_stmt).all():
        total = row.total or 0
        present = row.present or 0
        att_map[row.student_id] = (present / total * 100.0) if total > 0 else 0.0

    # Calculate batch averages for comparison
    batch_percentages: dict[int, list[float]] = {}
    for r in results:
        if getattr(r, "is_absent", False):
            continue
        t = test_map.get(r.test_id)
        if t and t.max_marks > 0:
            pct = (r.marks / t.max_marks) * 100.0
            batch_percentages.setdefault(t.batch_id, []).append(pct)
    batch_avg_map = {
        bid: (sum(pcts) / len(pcts) if pcts else 0.0)
        for bid, pcts in batch_percentages.items()
    }

    records = []
    for s in students:
        b = batches.get(s.batch_id)
        batch_name = b.name if b else "Unassigned"
        s_res = student_results.get(s.id, [])

        pct_list = []
        for r in s_res:
            if getattr(r, "is_absent", False):
                continue
            t = test_map.get(r.test_id)
            if t and t.max_marks > 0:
                pct_list.append((r.marks / t.max_marks) * 100.0)

        tests_taken = len(pct_list)
        if tests_taken > 0:
            avg_pct = sum(pct_list) / tests_taken
            high_pct = max(pct_list)
            low_pct = min(pct_list)
            latest_pct = pct_list[-1]
            # Simple trend: compare first half to second half if >= 2 tests
            if tests_taken >= 2:
                mid = tests_taken // 2
                first_half = sum(pct_list[:mid]) / mid
                second_half = sum(pct_list[mid:]) / (tests_taken - mid)
                diff = second_half - first_half
                trend = "Improving" if diff > 3.0 else ("Declining" if diff < -3.0 else "Stable")
            else:
                trend = "Provisional"
        else:
            avg_pct = 0.0
            high_pct = 0.0
            low_pct = 0.0
            latest_pct = 0.0
            trend = "No Tests"

        batch_avg = batch_avg_map.get(s.batch_id, 0.0)
        diff_from_batch = avg_pct - batch_avg if tests_taken > 0 else 0.0
        att_pct = att_map.get(s.id, 0.0)

        full_name = f"{s.first_name} {s.last_name or ''}".strip()
        records.append({
            "student_id": s.id,
            "name": full_name,
            "admission_number": s.admission_number,
            "batch_name": batch_name,
            "status": s.status,
            "tests_taken": tests_taken,
            "latest_pct": round(latest_pct, 1) if tests_taken > 0 else None,
            "avg_pct": round(avg_pct, 1) if tests_taken > 0 else None,
            "high_pct": round(high_pct, 1) if tests_taken > 0 else None,
            "low_pct": round(low_pct, 1) if tests_taken > 0 else None,
            "diff_from_batch": round(diff_from_batch, 1) if tests_taken > 0 else None,
            "trend": trend,
            "attendance_pct": round(att_pct, 1),
        })

    # Sort by avg_pct descending (placing students with tests first)
    records.sort(key=lambda x: (x["avg_pct"] is not None, x["avg_pct"] or 0.0), reverse=True)
    return records


# ─────────────────────────────────────────────────────────────────────────────
# 3. BATCH PERFORMANCE COMPARISON
# ─────────────────────────────────────────────────────────────────────────────

def get_batch_comparison_data(
    session: Session,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    """
    Compares batches on:
    - Active student count
    - Average test %
    - Overall attendance %
    - Tests conducted
    - Syllabus completion %
    """
    batches = list(session.scalars(select(Batch).order_by(Batch.name.asc())).all())
    comparison = []

    for b in batches:
        # Active students in batch
        students = list(session.scalars(
            select(Student).where(Student.batch_id == b.id, Student.status == "ACTIVE")
        ).all())
        student_count = len(students)

        # Tests conducted
        t_stmt = select(TestModel).where(TestModel.batch_id == b.id)
        if start_date:
            t_stmt = t_stmt.where(TestModel.test_date >= start_date)
        if end_date:
            t_stmt = t_stmt.where(TestModel.test_date <= end_date)
        tests = list(session.scalars(t_stmt).all())
        test_count = len(tests)

        # Average score
        scores = []
        if tests:
            test_map = {t.id: t for t in tests}
            res_stmt = select(TestResult).where(TestResult.test_id.in_([t.id for t in tests]))
            for r in session.scalars(res_stmt).all():
                if getattr(r, "is_absent", False):
                    continue
                t = test_map.get(r.test_id)
                if t and t.max_marks > 0:
                    scores.append((r.marks / t.max_marks) * 100.0)
        avg_score = (sum(scores) / len(scores)) if scores else 0.0

        # Attendance %
        a_stmt = select(Attendance).where(Attendance.batch_id == b.id)
        if start_date:
            a_stmt = a_stmt.where(Attendance.date >= start_date)
        if end_date:
            a_stmt = a_stmt.where(Attendance.date <= end_date)
        att_records = list(session.scalars(a_stmt).all())
        required_att = sum(1 for a in att_records if a.status != "LEAVE")
        present_att = sum(1 for a in att_records if a.status in ("PRESENT", "LATE"))
        att_pct = (present_att / required_att * 100.0) if required_att > 0 else 0.0

        # Syllabus progress
        lessons = list(session.scalars(
            select(Lesson).where(Lesson.batch_id == b.id, Lesson.status != "CANCELLED")
        ).all())
        completed_lessons = [l for l in lessons if l.status == "COMPLETED"]
        syl_pct = (len(completed_lessons) / len(lessons) * 100.0) if lessons else 0.0

        comparison.append({
            "batch_id": b.id,
            "batch_name": b.name,
            "active_students": student_count,
            "tests_conducted": test_count,
            "avg_score_pct": round(avg_score, 1),
            "attendance_pct": round(att_pct, 1),
            "syllabus_pct": round(syl_pct, 1),
            "reliable_sample": student_count >= 3 and test_count >= 1,
        })

    return comparison


# ─────────────────────────────────────────────────────────────────────────────
# 4. ATTENDANCE & ENGAGEMENT ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

def get_attendance_analytics(
    session: Session,
    *,
    batch_id: int | None = None,
    threshold_pct: float = 75.0,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Detailed attendance breakdown:
    - Overall attendance percentage
    - Distribution bands (>90%, 75-90%, 60-75%, <60%)
    - Students below threshold
    - Consecutive absences detection
    """
    att_stmt = select(Attendance)
    if batch_id is not None:
        att_stmt = att_stmt.where(Attendance.batch_id == batch_id)
    if start_date is not None:
        att_stmt = att_stmt.where(Attendance.date >= start_date)
    if end_date is not None:
        att_stmt = att_stmt.where(Attendance.date <= end_date)
    att_records = list(session.scalars(att_stmt).all())

    # Map student -> list of Attendance sorted by date
    student_records: dict[int, list[Attendance]] = {}
    for a in att_records:
        student_records.setdefault(a.student_id, []).append(a)

    for sid, rlist in student_records.items():
        rlist.sort(key=lambda x: x.date)

    # Students lookup
    s_stmt = select(Student)
    if batch_id is not None:
        s_stmt = s_stmt.where(Student.batch_id == batch_id)
    students = {s.id: s for s in session.scalars(s_stmt).all()}
    batches = {b.id: b for b in session.scalars(select(Batch)).all()}

    bands = {"Excellent (>90%)": 0, "Good (75-90%)": 0, "Moderate (60-75%)": 0, "Critical (<60%)": 0}
    low_attendance_students = []

    for sid, s in students.items():
        recs = student_records.get(sid, [])
        total = len(recs)
        required = sum(1 for r in recs if r.status != "LEAVE")
        if required == 0:
            continue
        present = sum(1 for r in recs if r.status in ("PRESENT", "LATE"))
        pct = (present / required) * 100.0

        if pct >= 90.0:
            bands["Excellent (>90%)"] += 1
        elif pct >= 75.0:
            bands["Good (75-90%)"] += 1
        elif pct >= 60.0:
            bands["Moderate (60-75%)"] += 1
        else:
            bands["Critical (<60%)"] += 1

        # Check consecutive recent absences
        consecutive_absent = 0
        for r in reversed(recs):
            if r.status == "ABSENT":
                consecutive_absent += 1
            else:
                break

        if pct < threshold_pct or consecutive_absent >= 2:
            b = batches.get(s.batch_id)
            low_attendance_students.append({
                "student_id": s.id,
                "name": f"{s.first_name} {s.last_name or ''}".strip(),
                "admission_number": s.admission_number,
                "batch_name": b.name if b else "—",
                "attendance_pct": round(pct, 1),
                "total_classes": total,
                "classes_missed": total - present,
                "consecutive_absent": consecutive_absent,
            })

    low_attendance_students.sort(key=lambda x: x["attendance_pct"])

    overall_total = len(att_records)
    overall_required = sum(1 for a in att_records if a.status != "LEAVE")
    overall_present = sum(1 for a in att_records if a.status in ("PRESENT", "LATE"))
    overall_pct = (overall_present / overall_required * 100.0) if overall_required > 0 else 0.0

    return {
        "overall_attendance_pct": round(overall_pct, 1),
        "total_sessions_logged": overall_total,
        "distribution_bands": bands,
        "low_attendance_students": low_attendance_students,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. TESTS & ASSESSMENTS ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

def get_tests_analytics(
    session: Session,
    *,
    batch_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Statistical breakdown across all tests:
    - Average score %
    - Highest & lowest scores
    - Participation rate
    - Score bands distribution (Distinction >80%, First Class 60-80%, Pass 40-60%, Fail <40%)
    - List of tests with stats
    """
    stmt = select(TestModel).order_by(TestModel.test_date.desc())
    if batch_id is not None:
        stmt = stmt.where(TestModel.batch_id == batch_id)
    if start_date is not None:
        stmt = stmt.where(TestModel.test_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(TestModel.test_date <= end_date)
    tests = list(session.scalars(stmt).all())

    batches = {b.id: b for b in session.scalars(select(Batch)).all()}
    test_summaries = []
    overall_bands = {"Distinction (≥80%)": 0, "Merit (60-79%)": 0, "Pass (40-59%)": 0, "Needs Help (<40%)": 0}

    for t in tests:
        res_stmt = select(TestResult).where(TestResult.test_id == t.id)
        results = list(session.scalars(res_stmt).all())
        # Total active students in this batch
        batch_students = list(session.scalars(
            select(Student).where(Student.batch_id == t.batch_id, Student.status == "ACTIVE")
        ).all())
        expected_count = len(batch_students)

        pcts = [(r.marks / t.max_marks * 100.0) for r in results if t.max_marks > 0 and not getattr(r, "is_absent", False)]
        avg_pct = (sum(pcts) / len(pcts)) if pcts else 0.0
        high_pct = max(pcts) if pcts else 0.0
        low_pct = min(pcts) if pcts else 0.0

        for p in pcts:
            if p >= 80.0:
                overall_bands["Distinction (≥80%)"] += 1
            elif p >= 60.0:
                overall_bands["Merit (60-79%)"] += 1
            elif p >= 40.0:
                overall_bands["Pass (40-59%)"] += 1
            else:
                overall_bands["Needs Help (<40%)"] += 1

        b = batches.get(t.batch_id)
        participation_pct = (len(results) / expected_count * 100.0) if expected_count > 0 else 0.0

        test_summaries.append({
            "test_id": t.id,
            "test_name": t.name,
            "batch_name": b.name if b else "—",
            "test_date": t.test_date.strftime("%d %b %Y"),
            "max_marks": t.max_marks,
            "students_appeared": len(results),
            "expected_students": expected_count,
            "participation_pct": round(participation_pct, 1),
            "avg_pct": round(avg_pct, 1),
            "high_pct": round(high_pct, 1),
            "low_pct": round(low_pct, 1),
        })

    return {
        "tests_count": len(tests),
        "score_bands": overall_bands,
        "tests": test_summaries,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 6. STUDENT RISK DETECTION & INTERVENTION (CENTREPIECE)
# ─────────────────────────────────────────────────────────────────────────────

def get_student_risk_analysis(
    session: Session,
    *,
    batch_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    attendance_threshold: float = 75.0,
    score_threshold: float = 45.0,
) -> list[dict[str, Any]]:
    """
    Transparent, explainable risk detection based on deterministic rules:
    - High Attention: >= 2 signals (e.g. low attendance + low scores or consecutive absences)
    - Needs Attention: 1 warning signal
    - On Track: sufficient data, no warning signals
    - Insufficient Data: student has < 2 tests and < 3 attendance records

    Returns list sorted by risk priority.
    """
    # Active students only
    stmt = select(Student).where(Student.status == "ACTIVE")
    if batch_id is not None:
        stmt = stmt.where(Student.batch_id == batch_id)
    students = list(session.scalars(stmt).all())
    batches = {b.id: b for b in session.scalars(select(Batch)).all()}

    # All tests
    t_stmt = select(TestModel)
    if start_date:
        t_stmt = t_stmt.where(TestModel.test_date >= start_date)
    if end_date:
        t_stmt = t_stmt.where(TestModel.test_date <= end_date)
    tests = {t.id: t for t in session.scalars(t_stmt).all()}

    # Results
    if tests:
        res_stmt = select(TestResult).where(TestResult.test_id.in_(list(tests.keys())))
        results = list(session.scalars(res_stmt).all())
    else:
        results = []

    student_results: dict[int, list[TestResult]] = {}
    for r in results:
        student_results.setdefault(r.student_id, []).append(r)

    # Sort each student's results chronologically
    for sid, rlist in student_results.items():
        rlist.sort(key=lambda x: tests[x.test_id].test_date if x.test_id in tests else date.min)

    # Attendance
    a_stmt = select(Attendance)
    if start_date:
        a_stmt = a_stmt.where(Attendance.date >= start_date)
    if end_date:
        a_stmt = a_stmt.where(Attendance.date <= end_date)
    att_records = list(session.scalars(a_stmt).all())
    student_att: dict[int, list[Attendance]] = {}
    for a in att_records:
        student_att.setdefault(a.student_id, []).append(a)

    for sid, alist in student_att.items():
        alist.sort(key=lambda x: x.date)

    risk_list = []
    for s in students:
        b = batches.get(s.batch_id)
        batch_name = b.name if b else "—"

        # Calculate attendance
        s_atts = student_att.get(s.id, [])
        total_att = len(s_atts)
        required_att = sum(1 for a in s_atts if a.status != "LEAVE")
        present_att = sum(1 for a in s_atts if a.status in ("PRESENT", "LATE"))
        att_pct = (present_att / required_att * 100.0) if required_att > 0 else None

        # Check consecutive recent absences
        consecutive_absences = 0
        for a in reversed(s_atts):
            if a.status == "ABSENT":
                consecutive_absences += 1
            else:
                break

        # Calculate scores
        s_res = student_results.get(s.id, [])
        score_pcts = []
        for r in s_res:
            if getattr(r, "is_absent", False):
                continue
            t = tests.get(r.test_id)
            if t and t.max_marks > 0:
                score_pcts.append((r.marks / t.max_marks) * 100.0)

        avg_score = (sum(score_pcts) / len(score_pcts)) if score_pcts else None

        # Calculate decline trend
        is_declining = False
        if len(score_pcts) >= 2:
            mid = len(score_pcts) // 2
            first_half = sum(score_pcts[:mid]) / mid
            second_half = sum(score_pcts[mid:]) / (len(score_pcts) - mid)
            if (second_half - first_half) < -5.0:
                is_declining = True

        # Signals evaluation
        signals = []
        if att_pct is not None and att_pct < attendance_threshold:
            signals.append(f"Low attendance ({att_pct:.1f}% vs threshold {attendance_threshold:.0f}%)")
        if consecutive_absences >= 2:
            signals.append(f"{consecutive_absences} consecutive classes missed")
        if avg_score is not None and avg_score < score_threshold:
            signals.append(f"Low test average ({avg_score:.1f}% vs threshold {score_threshold:.0f}%)")
        if is_declining:
            signals.append("Declining scores across recent comparable assessments")

        # Determine level & action
        if total_att < 3 and len(score_pcts) < 1:
            level = "Insufficient Data"
            rec = "Record more attendance and conduct initial diagnostic test."
        elif len(signals) >= 2:
            level = "High Attention"
            if "attendance" in signals[0].lower() or consecutive_absences >= 2:
                rec = "Schedule 1-on-1 parent call & review missed lesson concepts."
            else:
                rec = "Arrange targeted revision session and assign remedial practice test."
        elif len(signals) == 1:
            level = "Needs Attention"
            rec = "Monitor closely in next class session and assess next test performance."
        else:
            level = "On Track"
            rec = "Keep encouraging steady study habits."

        full_name = f"{s.first_name} {s.last_name or ''}".strip()
        risk_list.append({
            "student_id": s.id,
            "student_name": full_name,
            "admission_number": s.admission_number,
            "batch_name": batch_name,
            "risk_level": level,
            "reasons": signals if signals else (["Data history too sparse"] if level == "Insufficient Data" else ["Consistent performance & attendance"]),
            "attendance_pct": round(att_pct, 1) if att_pct is not None else None,
            "avg_score_pct": round(avg_score, 1) if avg_score is not None else None,
            "recommendation": rec,
        })

    # Sort: High Attention first, then Needs Attention, then Insufficient Data, then On Track
    priority_order = {"High Attention": 0, "Needs Attention": 1, "Insufficient Data": 2, "On Track": 3}
    risk_list.sort(key=lambda x: priority_order.get(x["risk_level"], 9))
    return risk_list


# ─────────────────────────────────────────────────────────────────────────────
# 7. STUDENT IMPROVEMENT & DECLINE ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

def get_student_improvement_analysis(
    session: Session,
    *,
    batch_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    """
    Identifies students with strongest improvements, largest declines, or stable trajectories.
    Compares earlier tests against recent tests (normalised to percentage).
    Requires at least 2 tests for comparison.
    """
    stmt = select(Student).where(Student.status == "ACTIVE")
    if batch_id is not None:
        stmt = stmt.where(Student.batch_id == batch_id)
    students = list(session.scalars(stmt).all())
    batches = {b.id: b for b in session.scalars(select(Batch)).all()}

    # All tests ordered chronologically
    t_stmt = select(TestModel)
    if start_date is not None:
        t_stmt = t_stmt.where(TestModel.test_date >= start_date)
    if end_date is not None:
        t_stmt = t_stmt.where(TestModel.test_date <= end_date)
    t_stmt = t_stmt.order_by(TestModel.test_date.asc())
    tests = list(session.scalars(t_stmt).all())
    test_map = {t.id: t for t in tests}

    res_stmt = select(TestResult)
    results = list(session.scalars(res_stmt).all())
    student_res_map: dict[int, list[TestResult]] = {}
    for r in results:
        student_res_map.setdefault(r.student_id, []).append(r)

    # Sort each student's results chronologically
    for sid, rlist in student_res_map.items():
        rlist.sort(key=lambda x: test_map[x.test_id].test_date if x.test_id in test_map else date.min)

    improvement_records = []
    for s in students:
        s_res = student_res_map.get(s.id, [])
        score_pcts = []
        for r in s_res:
            if getattr(r, "is_absent", False):
                continue
            t = test_map.get(r.test_id)
            if t and t.max_marks > 0:
                score_pcts.append((r.marks / t.max_marks) * 100.0)

        n = len(score_pcts)
        b = batches.get(s.batch_id)
        batch_name = b.name if b else "—"
        full_name = f"{s.first_name} {s.last_name or ''}".strip()

        if n < 2:
            improvement_records.append({
                "student_id": s.id,
                "name": full_name,
                "admission_number": s.admission_number,
                "batch_name": batch_name,
                "tests_count": n,
                "initial_avg": round(score_pcts[0], 1) if n == 1 else None,
                "recent_avg": round(score_pcts[0], 1) if n == 1 else None,
                "delta": 0.0,
                "trend": "Insufficient Data",
            })
            continue

        mid = n // 2
        initial_avg = sum(score_pcts[:mid]) / mid
        recent_avg = sum(score_pcts[mid:]) / (n - mid)
        delta = recent_avg - initial_avg

        if delta >= 4.0:
            trend = "Improving"
        elif delta <= -4.0:
            trend = "Declining"
        else:
            trend = "Stable"

        improvement_records.append({
            "student_id": s.id,
            "name": full_name,
            "admission_number": s.admission_number,
            "batch_name": batch_name,
            "tests_count": n,
            "initial_avg": round(initial_avg, 1),
            "recent_avg": round(recent_avg, 1),
            "delta": round(delta, 1),
            "trend": trend,
        })

    # Sort by delta descending (strongest improvers first, largest decliners last)
    improvement_records.sort(key=lambda x: (x["trend"] != "Insufficient Data", x["delta"]), reverse=True)
    return improvement_records


# ─────────────────────────────────────────────────────────────────────────────
# 8. TEACHING EFFECTIVENESS & SYLLABUS ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

def get_teaching_analytics(
    session: Session,
    *,
    batch_id: int | None = None,
) -> dict[str, Any]:
    """
    Evaluates lesson completion and chapter progress:
    - Planned vs Completed vs Cancelled
    - Chapter-wise completion breakdown
    - Sessions taught (ClassRecords logged)
    """
    stmt = select(Lesson)
    if batch_id is not None:
        stmt = stmt.where(Lesson.batch_id == batch_id)
    lessons = list(session.scalars(stmt).all())

    total_lessons = len(lessons)
    completed_lessons = sum(1 for l in lessons if l.status == "COMPLETED")
    planned_lessons = sum(1 for l in lessons if l.status == "PLANNED")
    in_progress_lessons = sum(1 for l in lessons if l.status == "IN_PROGRESS")
    cancelled_lessons = sum(1 for l in lessons if l.status == "CANCELLED")

    valid_total = total_lessons - cancelled_lessons
    completion_rate = (completed_lessons / valid_total * 100.0) if valid_total > 0 else 0.0

    # Chapter breakdown
    chapter_dict: dict[str, dict[str, int]] = {}
    for l in lessons:
        ch = l.chapter or "(Unspecified Chapter)"
        chapter_dict.setdefault(ch, {"total": 0, "completed": 0, "cancelled": 0})
        chapter_dict[ch]["total"] += 1
        if l.status == "COMPLETED":
            chapter_dict[ch]["completed"] += 1
        elif l.status == "CANCELLED":
            chapter_dict[ch]["cancelled"] += 1

    chapters = []
    for ch_name, stats in chapter_dict.items():
        v = stats["total"] - stats["cancelled"]
        pct = (stats["completed"] / v * 100.0) if v > 0 else 0.0
        chapters.append({
            "chapter": ch_name,
            "total": stats["total"],
            "completed": stats["completed"],
            "remaining": max(0, v - stats["completed"]),
            "completion_pct": round(pct, 1),
        })
    chapters.sort(key=lambda x: x["completion_pct"], reverse=True)

    # Class records (teaching logs) count
    cr_stmt = select(func.count(ClassRecord.id))
    if batch_id is not None:
        cr_stmt = cr_stmt.where(ClassRecord.batch_id == batch_id)
    class_sessions_count = session.scalar(cr_stmt) or 0

    return {
        "total_lessons": total_lessons,
        "completed_lessons": completed_lessons,
        "planned_lessons": planned_lessons,
        "in_progress_lessons": in_progress_lessons,
        "cancelled_lessons": cancelled_lessons,
        "completion_rate_pct": round(completion_rate, 1),
        "class_sessions_logged": class_sessions_count,
        "chapters": chapters,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 9. STUDENT RETENTION & ENROLLMENT
# ─────────────────────────────────────────────────────────────────────────────

def get_retention_analytics(session: Session) -> dict[str, Any]:
    """
    Analyzes student status distribution and admissions history.
    """
    students = list(session.scalars(select(Student)).all())
    status_counts = {"ACTIVE": 0, "INACTIVE": 0, "LEFT": 0}
    for s in students:
        status_counts[s.status] = status_counts.get(s.status, 0) + 1

    total_enrolled = len(students)
    active_rate = (status_counts.get("ACTIVE", 0) / total_enrolled * 100.0) if total_enrolled > 0 else 0.0

    # Admissions by month for students who have admission_date
    admissions_by_month: dict[str, int] = {}
    for s in students:
        if s.admission_date:
            m_key = s.admission_date.strftime("%b %Y")
            admissions_by_month[m_key] = admissions_by_month.get(m_key, 0) + 1

    return {
        "total_all_time": total_enrolled,
        "active_count": status_counts.get("ACTIVE", 0),
        "inactive_count": status_counts.get("INACTIVE", 0),
        "left_count": status_counts.get("LEFT", 0),
        "retention_rate_pct": round(active_rate, 1),
        "admissions_by_month": admissions_by_month,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 10. CSV EXPORT HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def export_analytics_report_csv(
    session: Session,
    report_type: str,
    *,
    batch_id: int | None = None,
) -> str:
    """
    Generates CSV string content for the requested intelligence report:
    - 'risk': At-risk students and recommended teacher interventions
    - 'performance': Complete student-by-student marks, trend & attendance
    - 'batches': Batch comparison matrix
    - 'syllabus': Chapter-by-chapter curriculum completion
    """
    output = io.StringIO()
    writer = csv.writer(output)

    if report_type == "risk":
        writer.writerow(["Student ID", "Admission No", "Student Name", "Batch", "Risk Level", "Observed Reasons", "Attendance %", "Avg Score %", "Suggested Next Action"])
        records = get_student_risk_analysis(session, batch_id=batch_id)
        for r in records:
            writer.writerow([
                r["student_id"],
                r["admission_number"],
                r["student_name"],
                r["batch_name"],
                r["risk_level"],
                "; ".join(r["reasons"]),
                f"{r['attendance_pct']}%" if r["attendance_pct"] is not None else "N/A",
                f"{r['avg_score_pct']}%" if r["avg_score_pct"] is not None else "N/A",
                r["recommendation"],
            ])

    elif report_type == "performance":
        writer.writerow(["Admission No", "Student Name", "Batch", "Status", "Tests Taken", "Latest Score %", "Average Score %", "High Score %", "Low Score %", "Diff From Batch", "Trend", "Attendance %"])
        records = get_student_performance_records(session, batch_id=batch_id)
        for r in records:
            writer.writerow([
                r["admission_number"],
                r["name"],
                r["batch_name"],
                r["status"],
                r["tests_taken"],
                f"{r['latest_pct']}%" if r["latest_pct"] is not None else "N/A",
                f"{r['avg_pct']}%" if r["avg_pct"] is not None else "N/A",
                f"{r['high_pct']}%" if r["high_pct"] is not None else "N/A",
                f"{r['low_pct']}%" if r["low_pct"] is not None else "N/A",
                f"{r['diff_from_batch']:+.1f}%" if r["diff_from_batch"] is not None else "N/A",
                r["trend"],
                f"{r['attendance_pct']}%",
            ])

    elif report_type == "batches":
        writer.writerow(["Batch Name", "Active Students", "Tests Conducted", "Average Score %", "Attendance %", "Syllabus Progress %", "Sufficient Sample"])
        batches = get_batch_comparison_data(session)
        for b in batches:
            writer.writerow([
                b["batch_name"],
                b["active_students"],
                b["tests_conducted"],
                f"{b['avg_score_pct']}%",
                f"{b['attendance_pct']}%",
                f"{b['syllabus_pct']}%",
                "Yes" if b["reliable_sample"] else "Low Data",
            ])

    elif report_type == "syllabus":
        writer.writerow(["Chapter / Unit", "Total Planned", "Completed", "Remaining", "Completion %"])
        data = get_teaching_analytics(session, batch_id=batch_id)
        for ch in data["chapters"]:
            writer.writerow([
                ch["chapter"],
                ch["total"],
                ch["completed"],
                ch["remaining"],
                f"{ch['completion_pct']}%",
            ])

    return output.getvalue()
