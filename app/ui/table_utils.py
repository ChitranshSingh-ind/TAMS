"""
Reusable Table UX, Sizing & Styling Architecture for TAMS.
Provides an intelligent, responsive column-sizing system that:
1. Displays complete cell content without truncation.
2. Intelligently uses available window width without leaving large blank regions on the right.
3. Automatically enables smooth horizontal scrolling when tables exceed viewport width.
4. Distributes surplus space to flexible columns (e.g. Student Name, Description, Remarks)
   while keeping compact columns (e.g. Dates, IDs, Actions, A/P buttons) properly sized.
5. Preserves usability, tooltips, scroll states, and TAMS Navy/Gold/Cream design system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStyledItemDelegate,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QToolTip,
)

# TAMS Design Palette
NAVY = "#012D54"
DARK_NAVY = "#04294D"
GOLD = "#D9B85F"
LIGHT_GOLD = "#E9DEBA"
CREAM = "#F8F6EA"
WHITE = "#FEFEFE"
TEXT = "#1F2937"
MUTED = "#615F4B"
BORDER = "#E5E7EB"


class TableSizingStrategy(Enum):
    """
    Column sizing strategies tailored to table content and role.
    """
    CONTENT_FIRST = auto()        # Sized strictly to content + header (compact tables)
    CONTENT_WITH_STRETCH = auto() # Content-based, designated flexible columns absorb spare width
    BOUNDED_AND_FLEXIBLE = auto() # Explicit bounds on compact cols, flexible cols fill viewport
    WIDE_SCROLLABLE = auto()      # Large tables: preserve readable widths, scroll horizontally


@dataclass
class TableColumnConfig:
    """Stores configuration and metadata for responsive table column layout."""
    base_widths: dict[int, int] = field(default_factory=dict)
    flexible_columns: set[int] = field(default_factory=set)
    fixed_columns: set[int] = field(default_factory=set)
    min_widths: dict[int, int] = field(default_factory=dict)
    max_widths: dict[int, int] = field(default_factory=dict)
    strategy: TableSizingStrategy = TableSizingStrategy.BOUNDED_AND_FLEXIBLE
    auto_fit_content: bool = True
    default_row_height: int = 38
    padding: int = 24
    max_sample_rows: int = 80


class TAMSItemDelegate(QStyledItemDelegate):
    """
    Item delegate providing automatic hover tooltips when text exceeds visible cell width,
    ensuring complete accessibility of long cell values without truncation loss.
    """

    def helpEvent(self, event, view, option, index):
        if not event or not view:
            return False

        text = index.data(Qt.ItemDataRole.DisplayRole)
        custom_tooltip = index.data(Qt.ItemDataRole.ToolTipRole)

        if custom_tooltip:
            return super().helpEvent(event, view, option, index)

        if text and isinstance(text, str):
            font = option.font
            metrics = QFontMetrics(font)
            text_width = metrics.horizontalAdvance(text)
            available_width = option.rect.width() - 16

            if text_width > available_width:
                QToolTip.showText(event.globalPos(), text, view)
                return True

        return super().helpEvent(event, view, option, index)


TABLE_STYLESHEET = f"""
QTableWidget, QTableView {{
    background-color: {WHITE};
    alternate-background-color: {CREAM};
    gridline-color: #EFE9D2;
    border: 1px solid {LIGHT_GOLD};
    border-radius: 6px;
    selection-background-color: {NAVY};
    selection-color: {WHITE};
    font-size: 13px;
    color: {TEXT};
    outline: none;
}}

QTableWidget::item, QTableView::item {{
    padding: 6px 10px;
    border-bottom: 1px solid #F1EBD3;
}}

QTableWidget::item:selected, QTableView::item:selected {{
    background-color: {NAVY};
    color: {WHITE};
}}

QHeaderView::section {{
    background-color: {NAVY};
    color: {WHITE};
    font-weight: 700;
    font-size: 12px;
    padding: 8px 10px;
    border: none;
    border-right: 1px solid #04294D;
    border-bottom: 2px solid {GOLD};
}}

QHeaderView::section:hover {{
    background-color: {DARK_NAVY};
}}

QScrollBar:horizontal {{
    border: 1px solid #E9DEBA;
    background: #F8F6EA;
    height: 11px;
    margin: 0px;
    border-radius: 5px;
}}

QScrollBar::handle:horizontal {{
    background: #D9B85F;
    min-width: 30px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal:hover {{
    background: #012D54;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
    background: none;
}}

QScrollBar::vertical {{
    border: 1px solid #E9DEBA;
    background: #F8F6EA;
    width: 11px;
    margin: 0px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical {{
    background: #D9B85F;
    min-height: 30px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: #012D54;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    background: none;
}}
"""


class TableResizeFilter(QObject):
    """
    Event filter installed on a table and its viewport to automatically recalculate
    and redistribute column widths whenever window, dialog, or tab dimensions change.
    """

    def __init__(self, table: QTableWidget | QTableView, parent: QObject | None = None):
        super().__init__(parent or table)
        self.table = table
        self._is_handling = False

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            if not self._is_handling:
                self._is_handling = True
                try:
                    apply_table_column_sizing(self.table)
                finally:
                    self._is_handling = False
        return super().eventFilter(obj, event)


def measure_column_preferred_width(
    table: QTableWidget | QTableView,
    col_idx: int,
    config: TableColumnConfig,
) -> int:
    """
    Computes preferred width for a column by measuring:
    1. Header label text width + sort arrow space + padding.
    2. Actual cell text content across sampled rows.
    3. Custom cell widgets (buttons, checkboxes, containers) size hints.
    """
    header = table.horizontalHeader()
    header_font = header.font()
    header_metrics = QFontMetrics(header_font)
    table_font = table.font()
    cell_metrics = QFontMetrics(table_font)

    # 1. Measure header text
    model = table.model()
    header_text = ""
    if hasattr(table, "horizontalHeaderItem"):
        item = table.horizontalHeaderItem(col_idx)
        if item:
            header_text = item.text()
    elif model:
        header_text = str(model.headerData(col_idx, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) or "")

    header_text_width = header_metrics.horizontalAdvance(header_text) if header_text else 0
    # Include padding + sort indicator buffer (24px)
    max_measured = header_text_width + config.padding + 16

    # 2. Measure rows if QTableWidget and rows exist
    if isinstance(table, QTableWidget) and config.auto_fit_content:
        row_count = table.rowCount()
        sample_limit = min(row_count, config.max_sample_rows)
        for row in range(sample_limit):
            cell_widget = table.cellWidget(row, col_idx)
            if cell_widget:
                w_widget = 0
                hint = cell_widget.sizeHint()
                if hint.isValid() and hint.width() > 0:
                    w_widget = max(w_widget, hint.width())
                min_hint = cell_widget.minimumSizeHint()
                if min_hint.isValid() and min_hint.width() > 0:
                    w_widget = max(w_widget, min_hint.width())
                if cell_widget.minimumWidth() > 0:
                    w_widget = max(w_widget, cell_widget.minimumWidth())
                if w_widget > 0:
                    max_measured = max(max_measured, w_widget + 16)
                continue

            # Check text item
            cell_item = table.item(row, col_idx)
            if cell_item:
                text = cell_item.text()
                if text:
                    # Single-line measurement
                    w = cell_metrics.horizontalAdvance(text) + config.padding
                    max_measured = max(max_measured, w)

    # Base minimum for column
    base_min = config.base_widths.get(col_idx, 60)
    config_min = config.min_widths.get(col_idx, 50)
    result = max(max_measured, base_min, config_min)

    # Apply maximum clamp if defined (prevents runaway width from giant strings)
    config_max = config.max_widths.get(col_idx, 500)
    return min(result, config_max)


def apply_table_column_sizing(table: QTableWidget | QTableView) -> None:
    """
    Core layout engine that balances column content requirements against available viewport space.
    - If viewport > required width: distributes surplus to flexible columns (eliminates blank right region).
    - If viewport <= required width: preserves required widths and enables horizontal scrolling.
    """
    header = table.horizontalHeader()
    col_count = header.count()
    if col_count == 0:
        return

    config: TableColumnConfig | None = getattr(table, "_tams_table_config", None)
    if not config:
        return

    # 1. Determine preferred/minimum width for each visible column
    preferred_widths: dict[int, int] = {}
    visible_cols: list[int] = []

    for col in range(col_count):
        if table.isColumnHidden(col):
            continue
        visible_cols.append(col)
        # Use base width if auto_fit is disabled or column is explicitly fixed
        if not config.auto_fit_content and col in config.base_widths:
            preferred_widths[col] = config.base_widths[col]
        else:
            w = measure_column_preferred_width(table, col, config)
            # Ensure base width is honored as minimum
            if col in config.base_widths:
                w = max(w, config.base_widths[col])
            preferred_widths[col] = w

    if not visible_cols:
        return

    # 2. Measure available viewport width
    viewport_width = table.viewport().width()
    if viewport_width <= 0:
        # Fallback to widget width minus standard margins
        viewport_width = max(0, table.width() - 4)

    total_preferred = sum(preferred_widths.values())

    # 3. Determine flexible columns to absorb spare space
    flex_cols = [c for c in config.flexible_columns if c in visible_cols]
    if not flex_cols and config.strategy != TableSizingStrategy.CONTENT_FIRST:
        # Auto-detect candidate flexible column: choose widest visible column not marked as fixed
        candidates = [c for c in visible_cols if c not in config.fixed_columns]
        if candidates:
            # Pick the column with the highest preferred width (e.g. Student Name, Description)
            best_flex = max(candidates, key=lambda c: preferred_widths[c])
            flex_cols = [best_flex]

    # 4. Allocate widths based on space availability
    final_widths: dict[int, int] = {}

    if viewport_width > total_preferred and flex_cols:
        # Surplus available: give fixed columns their preferred size, distribute surplus to flexible columns
        surplus = viewport_width - total_preferred
        per_col_surplus = surplus // len(flex_cols)
        remainder = surplus % len(flex_cols)

        for col in visible_cols:
            base = preferred_widths[col]
            if col in flex_cols:
                extra = per_col_surplus + (1 if remainder > 0 else 0)
                remainder -= 1
                final_widths[col] = base + extra
            else:
                final_widths[col] = base
    else:
        # Viewport is smaller than required, or no flexible columns:
        # Preserve minimum readable widths so text is never crushed, and enable horizontal scroll
        for col in visible_cols:
            final_widths[col] = preferred_widths[col]

    # 5. Apply column widths and ensure Interactive mode
    header.blockSignals(True)
    for col in visible_cols:
        header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        table.setColumnWidth(col, final_widths[col])
    header.blockSignals(False)


def configure_table_ux(
    table: QTableWidget | QTableView,
    *,
    column_widths: dict[int, int] | list[int] | None = None,
    stretch_column: int | None = None,
    flexible_columns: list[int] | set[int] | None = None,
    fixed_columns: list[int] | set[int] | None = None,
    min_widths: dict[int, int] | None = None,
    max_widths: dict[int, int] | None = None,
    strategy: TableSizingStrategy = TableSizingStrategy.BOUNDED_AND_FLEXIBLE,
    auto_fit_content: bool = True,
    default_row_height: int = 38,
    enable_alternate_colors: bool = True,
    alternating_colors: bool | None = None,
    apply_stylesheet: bool = True,
) -> None:
    """
    Applies comprehensive UX upgrades and intelligent responsive column sizing:
    1. Smooth pixel-based horizontal & vertical scrolling (as needed).
    2. Dynamic column width allocation: expands flexible columns to fill viewport without blank margins.
    3. Preserves minimum widths when viewport is narrow, triggering smooth horizontal scrolling.
    4. Attaches TAMSItemDelegate for automatic hover tooltips on long text.
    5. Sets default row height and alternate row colors.
    6. Applies established TAMS Navy/Gold styling.
    """
    if alternating_colors is not None:
        enable_alternate_colors = alternating_colors

    # 1. Scroll policies & pixel scroll
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

    # 2. Row styling & selection behavior
    table.setAlternatingRowColors(enable_alternate_colors)
    if default_row_height > 0:
        table.verticalHeader().setDefaultSectionSize(default_row_height)
    table.verticalHeader().setVisible(False)

    # 3. Header setup
    header = table.horizontalHeader()
    header.setMinimumSectionSize(50)
    header.setStretchLastSection(False)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    # 4. Build configuration
    base_dict: dict[int, int] = {}
    if column_widths:
        if isinstance(column_widths, list):
            for i, w in enumerate(column_widths):
                base_dict[i] = w
        elif isinstance(column_widths, dict):
            base_dict = dict(column_widths)

    flex_set: set[int] = set()
    if flexible_columns:
        flex_set = set(flexible_columns)
    elif stretch_column is not None:
        flex_set = {stretch_column}

    fixed_set: set[int] = set(fixed_columns) if fixed_columns else set()

    config = TableColumnConfig(
        base_widths=base_dict,
        flexible_columns=flex_set,
        fixed_columns=fixed_set,
        min_widths=dict(min_widths or {}),
        max_widths=dict(max_widths or {}),
        strategy=strategy,
        auto_fit_content=auto_fit_content,
        default_row_height=default_row_height,
    )
    table._tams_table_config = config

    # Set initial interactive widths from base
    for col_idx, width in base_dict.items():
        header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Interactive)
        table.setColumnWidth(col_idx, width)

    # 5. Attach delegate for auto-tooltips
    table.setItemDelegate(TAMSItemDelegate(table))

    # 6. Apply stylesheet
    if apply_stylesheet:
        table.setStyleSheet(TABLE_STYLESHEET)

    # 7. Install resize filter on both table and its viewport for responsive auto-layout
    resize_filter = TableResizeFilter(table)
    table.installEventFilter(resize_filter)
    table.viewport().installEventFilter(resize_filter)
    table._tams_resize_filter = resize_filter

    # Initial column sizing application
    apply_table_column_sizing(table)


def auto_fit_columns(table: QTableWidget | QTableView) -> None:
    """
    Public helper to recalculate and apply smart column sizing after data population.
    Call this whenever a table finishes loading data or row count changes.
    """
    apply_table_column_sizing(table)


def save_table_state(table: QTableWidget | QTableView) -> dict:
    """
    Saves horizontal and vertical scrollbar positions and column widths so
    that data refresh operations do not abruptly reset the view.
    """
    widths = {}
    header = table.horizontalHeader()
    for col in range(header.count()):
        widths[col] = table.columnWidth(col)

    h_scroll = table.horizontalScrollBar().value()
    v_scroll = table.verticalScrollBar().value()

    return {
        "widths": widths,
        "h_scroll": h_scroll,
        "v_scroll": v_scroll,
    }


def restore_table_state(table: QTableWidget | QTableView, state: dict | None) -> None:
    """
    Restores column widths and scrollbar positions saved prior to a reload.
    """
    if not state:
        return

    widths = state.get("widths", {})
    for col, width in widths.items():
        if col < table.columnCount():
            table.setColumnWidth(col, width)

    if "h_scroll" in state:
        table.horizontalScrollBar().setValue(state["h_scroll"])
    if "v_scroll" in state:
        table.verticalScrollBar().setValue(state["v_scroll"])


def create_table_badge(text: str, bg_color: str, fg_color: str) -> QTableWidgetItem:
    """
    Creates a styled item for table cells (e.g. status badge).
    """
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    return item
