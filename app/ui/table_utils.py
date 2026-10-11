"""
Reusable Table UX & Styling Utility for TAMS.
Enforces consistent horizontal scrolling, explicit sensible column widths,
smooth pixel scrolling, auto-tooltips for long text, state preservation across
refreshes, and polished TAMS navy/gold/cream styling across all tables.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QPoint, QModelIndex, QRect
from PyQt6.QtGui import QFontMetrics, QPainter
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QTableView,
    QStyleOptionViewItem,
)

# TAMS Palette
NAVY = "#012D54"
DARK_NAVY = "#04294D"
GOLD = "#D9B85F"
LIGHT_GOLD = "#E9DEBA"
CREAM = "#F8F6EA"
WHITE = "#FEFEFE"
TEXT = "#1F2937"
MUTED = "#615F4B"
BORDER = "#E5E7EB"


class TAMSItemDelegate(QStyledItemDelegate):
    """
    Item delegate providing automatic tooltip when text exceeds visible cell width,
    ensuring full accessibility of long cell values without truncation loss.
    """

    def helpEvent(self, event, view, option, index):
        if not event or not view:
            return False

        text = index.data(Qt.ItemDataRole.DisplayRole)
        custom_tooltip = index.data(Qt.ItemDataRole.ToolTipRole)

        if custom_tooltip:
            # Explicit tooltip provided
            return super().helpEvent(event, view, option, index)

        if text and isinstance(text, str):
            font = option.font
            metrics = QFontMetrics(font)
            text_width = metrics.horizontalAdvance(text)
            available_width = option.rect.width() - 16  # account for margins/padding

            if text_width > available_width:
                from PyQt6.QtWidgets import QToolTip
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
    border: none;
    background: {CREAM};
    height: 10px;
    margin: 0px 0px 0px 0px;
    border-radius: 5px;
}}

QScrollBar::handle:horizontal {{
    background: {LIGHT_GOLD};
    min-width: 24px;
    border-radius: 5px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {GOLD};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
    background: none;
}}

QScrollBar:vertical {{
    border: none;
    background: {CREAM};
    width: 10px;
    margin: 0px 0px 0px 0px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical {{
    background: {LIGHT_GOLD};
    min-height: 24px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical:hover {{
    background: {GOLD};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    background: none;
}}
"""


def configure_table_ux(
    table: QTableWidget | QTableView,
    *,
    column_widths: dict[int, int] | list[int] | None = None,
    stretch_column: int | None = None,
    default_row_height: int = 38,
    enable_alternate_colors: bool = True,
    alternating_colors: bool | None = None,
    apply_stylesheet: bool = True,
) -> None:
    """
    Applies comprehensive UX upgrades to any QTableWidget or QTableView:
    1. Smooth pixel-based horizontal & vertical scrolling.
    2. Scrollbars enabled as needed.
    3. Prevents auto-squishing: uses Interactive resize mode with sensible explicit widths.
    4. Attaches TAMSItemDelegate for automatic hover tooltips on elided content.
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
    header.setMinimumSectionSize(60)
    header.setStretchLastSection(False)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    # 4. Column widths
    if column_widths:
        if isinstance(column_widths, list):
            for col_idx, width in enumerate(column_widths):
                if stretch_column is not None and col_idx == stretch_column:
                    header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Stretch)
                else:
                    header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Interactive)
                    table.setColumnWidth(col_idx, width)
        elif isinstance(column_widths, dict):
            for col_idx, width in column_widths.items():
                if stretch_column is not None and col_idx == stretch_column:
                    header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Stretch)
                else:
                    header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Interactive)
                    table.setColumnWidth(col_idx, width)

    if stretch_column is not None:
        header.setSectionResizeMode(stretch_column, QHeaderView.ResizeMode.Stretch)

    # 5. Attach delegate for auto-tooltips
    table.setItemDelegate(TAMSItemDelegate(table))

    # 6. Apply stylesheet
    if apply_stylesheet:
        table.setStyleSheet(TABLE_STYLESHEET)


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
