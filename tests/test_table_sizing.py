import os
import sys
import pytest
from PyQt6.QtCore import QEvent, QSize, Qt
from PyQt6.QtGui import QFont, QResizeEvent
from PyQt6.QtWidgets import (
    QApplication,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from app.ui.table_utils import (
    TableColumnConfig,
    TableResizeFilter,
    TableSizingStrategy,
    apply_table_column_sizing,
    auto_fit_columns,
    configure_table_ux,
    measure_column_preferred_width,
    restore_table_state,
    save_table_state,
)


@pytest.fixture(scope="session")
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_empty_table_configuration(qapp):
    """Verify that configure_table_ux gracefully handles empty tables without crash."""
    table = QTableWidget(0, 4)
    table.setHorizontalHeaderLabels(["ID", "Name", "Batch", "Actions"])
    configure_table_ux(
        table,
        column_widths=[60, 180, 120, 100],
        flexible_columns=[1],
        strategy=TableSizingStrategy.BOUNDED_AND_FLEXIBLE,
    )

    assert hasattr(table, "_tams_table_config")
    config: TableColumnConfig = table._tams_table_config
    assert config.flexible_columns == {1}
    assert config.strategy == TableSizingStrategy.BOUNDED_AND_FLEXIBLE
    assert table.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded

    # Sizing on empty table should set base widths without error
    auto_fit_columns(table)
    assert table.columnWidth(0) >= 60
    assert table.columnWidth(1) >= 180
    assert table.columnWidth(2) >= 120
    assert table.columnWidth(3) >= 100


def test_surplus_width_distribution_no_dead_space(qapp):
    """
    When available viewport width exceeds total preferred column width,
    surplus pixels must be allocated to flexible columns, preventing blank space.
    """
    table = QTableWidget(2, 3)
    table.setHorizontalHeaderLabels(["Date", "Description", "Amount"])
    table.resize(900, 300)

    table.setItem(0, 0, QTableWidgetItem("2026-03-01"))
    table.setItem(0, 1, QTableWidgetItem("Short text"))
    table.setItem(0, 2, QTableWidgetItem("150.00"))

    configure_table_ux(
        table,
        column_widths=[100, 200, 100],
        flexible_columns=[1],
        fixed_columns=[0, 2],
        strategy=TableSizingStrategy.BOUNDED_AND_FLEXIBLE,
    )

    apply_table_column_sizing(table)

    viewport_w = table.viewport().width()
    if viewport_w <= 0:
        viewport_w = max(0, table.width() - 4)

    col0_w = table.columnWidth(0)
    col1_w = table.columnWidth(1)
    col2_w = table.columnWidth(2)

    # Fixed columns should maintain their preferred/base width
    assert col0_w >= 100
    assert col2_w >= 100
    # Flexible column must expand to consume surplus
    assert col1_w > 200
    # Total visible columns width should reach or exceed available viewport width
    assert (col0_w + col1_w + col2_w) >= viewport_w - 2


def test_narrow_viewport_preserves_minimum_widths(qapp):
    """
    When table is narrower than required column widths, columns must NOT shrink
    below readability thresholds, enabling horizontal scrollbar instead of clipping.
    """
    table = QTableWidget(2, 3)
    table.setHorizontalHeaderLabels(["Col 1", "Col 2", "Col 3"])
    table.resize(250, 300)

    configure_table_ux(
        table,
        column_widths=[120, 140, 130],
        flexible_columns=[1],
        strategy=TableSizingStrategy.WIDE_SCROLLABLE,
    )

    apply_table_column_sizing(table)

    # Each column must preserve its base readable width
    assert table.columnWidth(0) >= 120
    assert table.columnWidth(1) >= 140
    assert table.columnWidth(2) >= 130
    total_w = table.columnWidth(0) + table.columnWidth(1) + table.columnWidth(2)
    assert total_w == 390
    assert total_w > table.width()


def test_hidden_column_handling(qapp):
    """Hidden columns must not factor into surplus space distribution or cause index errors."""
    table = QTableWidget(1, 4)
    table.setHorizontalHeaderLabels(["ID", "Name", "Secret", "Status"])
    table.resize(800, 300)

    configure_table_ux(
        table,
        column_widths=[80, 200, 150, 90],
        flexible_columns=[1],
        strategy=TableSizingStrategy.BOUNDED_AND_FLEXIBLE,
    )

    table.setColumnHidden(2, True)
    apply_table_column_sizing(table)

    assert table.isColumnHidden(2)
    # Flexible column 1 should expand into spare space
    assert table.columnWidth(1) > 200
    assert table.columnWidth(0) >= 80
    assert table.columnWidth(3) >= 90


def test_embedded_cell_widget_measurement(qapp):
    """Cell widgets (buttons, multi-button containers) must be measured by their size hints."""
    table = QTableWidget(1, 2)
    table.setHorizontalHeaderLabels(["Name", "Actions"])

    btn = QPushButton("Edit | Delete | View")
    btn.setMinimumWidth(175)
    table.setCellWidget(0, 1, btn)

    configure_table_ux(
        table,
        column_widths=[150, 80],
        flexible_columns=[0],
        fixed_columns=[1],
        strategy=TableSizingStrategy.BOUNDED_AND_FLEXIBLE,
    )

    config = table._tams_table_config
    measured = measure_column_preferred_width(table, 1, config)
    # Column width must accommodate the button's minimum width (175 + padding)
    assert measured >= 175


def test_auto_fit_columns_content_measurement(qapp):
    """Content text width should be accurately factored into preferred width."""
    table = QTableWidget(1, 2)
    table.setHorizontalHeaderLabels(["A", "Long Description Header"])
    long_text = "This is a comprehensive and detailed syllabus entry for senior physics"
    table.setItem(0, 1, QTableWidgetItem(long_text))

    configure_table_ux(
        table,
        column_widths=[60, 100],
        flexible_columns=[1],
        strategy=TableSizingStrategy.CONTENT_WITH_STRETCH,
    )

    auto_fit_columns(table)
    # Column 1 should expand significantly beyond 100px due to long text
    assert table.columnWidth(1) > 200


def test_table_resize_event_filter(qapp):
    """TableResizeFilter should respond to Resize events and call apply_table_column_sizing."""
    table = QTableWidget(1, 2)
    table.setHorizontalHeaderLabels(["A", "B"])
    table.resize(400, 200)

    configure_table_ux(
        table,
        column_widths=[100, 100],
        flexible_columns=[1],
        strategy=TableSizingStrategy.BOUNDED_AND_FLEXIBLE,
    )

    initial_col1_w = table.columnWidth(1)

    # Test event filter on resize event
    filter_obj = TableResizeFilter(table)
    table.resize(800, 200)
    event = QResizeEvent(QSize(800, 200), QSize(400, 200))
    filter_obj.eventFilter(table, event)

    # The filter recalculates and column 1 absorbs new surplus
    assert table.columnWidth(1) >= initial_col1_w


def test_save_and_restore_table_state(qapp):
    """Table column widths and scrollbar positions should be saved and restored correctly."""
    table = QTableWidget(2, 3)
    table.setHorizontalHeaderLabels(["ID", "Name", "Status"])
    configure_table_ux(table, column_widths=[75, 220, 110])

    table.setColumnWidth(0, 95)
    table.setColumnWidth(1, 310)

    saved = save_table_state(table)
    assert saved["widths"][0] == 95
    assert saved["widths"][1] == 310

    # Create new table and restore
    new_table = QTableWidget(2, 3)
    new_table.setHorizontalHeaderLabels(["ID", "Name", "Status"])
    configure_table_ux(new_table, column_widths=[50, 50, 50])

    restore_table_state(new_table, saved)
    assert new_table.columnWidth(0) == 95
    assert new_table.columnWidth(1) == 310
