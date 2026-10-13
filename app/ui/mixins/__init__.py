"""
TAMS UI Page Mixins.
Deconstructs the MainWindow into focused, decoupled, maintainable page controllers.
"""

from app.ui.mixins.dashboard_mixin import DashboardMixin
from app.ui.mixins.students_mixin import StudentsMixin
from app.ui.mixins.attendance_mixin import AttendanceMixin
from app.ui.mixins.results_mixin import ResultsMixin
from app.ui.mixins.fees_mixin import FeesMixin
from app.ui.mixins.expenses_mixin import ExpensesMixin
from app.ui.mixins.teaching_mixin import TeachingMixin
from app.ui.mixins.analysis_mixin import AnalysisMixin

__all__ = [
    "DashboardMixin",
    "StudentsMixin",
    "AttendanceMixin",
    "ResultsMixin",
    "FeesMixin",
    "ExpensesMixin",
    "TeachingMixin",
    "AnalysisMixin",
]
