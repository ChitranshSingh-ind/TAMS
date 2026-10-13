"""
PyQt6 Custom Micro-Chart Widgets for TAMS Coaching Intelligence Suite.
Built natively using QPainter for zero external dependency, fast GPU/vector rendering,
high DPI crispness, clean TAMS palette, and robust empty-state handling.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PyQt6.QtWidgets import QWidget, QSizePolicy


# ─────────────────────────────────────────────────────────────────────────────
# 1. BAR CHART WIDGET (Single / Comparison Bars)
# ─────────────────────────────────────────────────────────────────────────────

class SimpleBarChartWidget(QWidget):
    """
    Renders clean horizontal or vertical bars with labels, values, and percentage scaling.
    data format: list of tuples (label: str, value: float, max_value: float, optional_color: str)
    """

    def __init__(
        self,
        title: str = "",
        unit: str = "%",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.title = title
        self.unit = unit
        self.items: list[dict] = []
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)

    def set_title(self, title: str):
        self.title = title
        self.update()

    def set_data(self, items: list[dict | tuple]):
        """
        items: list of dicts with keys ('label', 'value', 'color', 'sublabel', 'val_text')
        or list of tuples (label, value, color[, sublabel, val_text])
        """
        normalized = []
        for it in items:
            if isinstance(it, (tuple, list)):
                lbl = str(it[0]) if len(it) > 0 else ""
                val = float(it[1]) if len(it) > 1 else 0.0
                clr = str(it[2]) if len(it) > 2 else "#012D54"
                sub = str(it[3]) if len(it) > 3 else ""
                vtxt = str(it[4]) if len(it) > 4 else ""
                normalized.append({"label": lbl, "value": val, "color": clr, "sublabel": sub, "val_text": vtxt})
            elif isinstance(it, dict):
                normalized.append({
                    "label": str(it.get("label", "")),
                    "value": float(it.get("value", 0.0)),
                    "color": str(it.get("color", "#012D54")),
                    "sublabel": str(it.get("sublabel", "")),
                    "val_text": str(it.get("val_text", "")),
                })
        self.items = normalized
        # Adjust minimum height based on items to ensure bars are never squished
        min_h = max(200, int(48 + len(self.items) * 40 + 16))
        self.setMinimumHeight(min_h)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        w, h = rect.width(), rect.height()

        # Background card fill
        painter.setBrush(QBrush(QColor("#FEFEFE")))
        painter.setPen(QPen(QColor("#E9DEBA"), 1))
        painter.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 8, 8)

        # Title
        painter.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        painter.setPen(QColor("#012D54"))
        top_offset = 26
        if self.title:
            painter.drawText(16, top_offset, self.title)
            top_offset += 20

        if not self.items:
            painter.setFont(QFont("Inter", 10))
            painter.setPen(QColor("#615F4B"))
            painter.drawText(
                QRectF(0, top_offset, w, h - top_offset),
                Qt.AlignmentFlag.AlignCenter,
                "No assessment records available for the selected filters",
            )
            return

        # Calculate layout
        n = len(self.items)
        row_height = 38.0
        max_val = 100.0 if self.unit == "%" else max([item["value"] for item in self.items] + [100.0])

        label_width = min(220.0, max(140.0, w * 0.30))
        bar_right_margin = 65.0
        bar_area_width = max(50.0, w - label_width - bar_right_margin - 40)

        for i, item in enumerate(self.items):
            y = top_offset + i * row_height
            val = float(item["value"])
            label = str(item.get("label", ""))
            sublabel = str(item.get("sublabel", ""))
            color_hex = str(item.get("color", "#012D54"))

            # Draw Label (with optional sublabel and ellipsis elision)
            painter.setFont(QFont("Inter", 9, QFont.Weight.DemiBold))
            painter.setPen(QColor("#012D54"))
            elided_label = painter.fontMetrics().elidedText(label, Qt.TextElideMode.ElideRight, int(label_width - 4))

            if sublabel:
                label_rect = QRectF(16, y, label_width, 18)
                painter.drawText(label_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided_label)

                painter.setFont(QFont("Inter", 8))
                painter.setPen(QColor("#615F4B"))
                elided_sub = painter.fontMetrics().elidedText(sublabel, Qt.TextElideMode.ElideRight, int(label_width - 4))
                sub_rect = QRectF(16, y + 17, label_width, 14)
                painter.drawText(sub_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided_sub)
            else:
                label_rect = QRectF(16, y, label_width, row_height - 6)
                painter.drawText(label_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided_label)

            # Draw Bar Background track
            bar_x = 16 + label_width + 10
            bar_y = y + (row_height - 14) / 2
            bar_h = 14.0
            painter.setBrush(QBrush(QColor("#F8F6EA")))
            painter.setPen(QPen(QColor("#E9DEBA"), 1))
            painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_area_width, bar_h), 4, 4)

            # Draw Active Filled Bar
            fill_w = (val / max_val) * bar_area_width if max_val > 0 else 0
            if fill_w > 0:
                painter.setBrush(QBrush(QColor(color_hex)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(QRectF(bar_x, bar_y, max(5.0, min(bar_area_width, fill_w)), bar_h), 4, 4)

            # Draw Value Label
            painter.setFont(QFont("Inter", 9, QFont.Weight.Bold))
            painter.setPen(QColor("#012D54") if val > 0 else QColor("#615F4B"))
            custom_val_text = item.get("val_text", "")
            if custom_val_text:
                val_text = custom_val_text
            else:
                val_text = f"{val:.1f}{self.unit}" if self.unit == "%" else f"{val:.0f}{self.unit}"
            val_rect = QRectF(bar_x + bar_area_width + 8, y, bar_right_margin, row_height - 4)
            painter.drawText(val_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, val_text)


# ─────────────────────────────────────────────────────────────────────────────
# 2. DISTRIBUTION BREAKDOWN (SEGMENTED BAR)
# ─────────────────────────────────────────────────────────────────────────────

class SegmentedDistributionWidget(QWidget):
    """
    Renders stacked score band distributions (e.g. Distinction, Merit, Pass, Needs Help)
    with colored legend chips and percentages.
    """

    def __init__(self, title: str = "Performance Distribution", parent: QWidget | None = None):
        super().__init__(parent)
        self.title = title
        self.segments: list[dict] = []
        self.setMinimumHeight(130)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_data(self, segments: list[dict | tuple]):
        """
        segments: list of dicts with: 'label', 'count', 'color'
        or list of tuples: (label, count, color)
        """
        normalized = []
        for s in segments:
            if isinstance(s, (tuple, list)):
                lbl = str(s[0]) if len(s) > 0 else ""
                cnt = int(s[1]) if len(s) > 1 else 0
                clr = str(s[2]) if len(s) > 2 else "#012D54"
                normalized.append({"label": lbl, "count": cnt, "color": clr})
            elif isinstance(s, dict):
                normalized.append({
                    "label": str(s.get("label", "")),
                    "count": int(s.get("count", 0)),
                    "color": str(s.get("color", "#012D54")),
                })
        self.segments = normalized
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        w, h = rect.width(), rect.height()

        # Background
        painter.setBrush(QBrush(QColor("#FEFEFE")))
        painter.setPen(QPen(QColor("#E9DEBA"), 1))
        painter.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 8, 8)

        # Title
        painter.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        painter.setPen(QColor("#012D54"))
        painter.drawText(16, 26, self.title)

        total_count = sum(
            s.get("count", 0) if isinstance(s, dict) else (s[1] if len(s) > 1 else 0)
            for s in self.segments
        )
        if total_count == 0:
            painter.setFont(QFont("Inter", 10))
            painter.setPen(QColor("#615F4B"))
            painter.drawText(QRectF(0, 40, w, h - 45), Qt.AlignmentFlag.AlignCenter, "No score entries in selected range")
            return

        # Stacked bar track
        bar_x = 16.0
        bar_y = 44.0
        bar_w = w - 32.0
        bar_h = 22.0

        current_x = bar_x
        for seg in self.segments:
            if isinstance(seg, dict):
                cnt = seg.get("count", 0)
                color_hex = seg.get("color", "#012D54")
            else:
                cnt = seg[1] if len(seg) > 1 else 0
                color_hex = seg[2] if len(seg) > 2 else "#012D54"

            if cnt <= 0:
                continue
            seg_w = (cnt / total_count) * bar_w
            painter.setBrush(QBrush(QColor(color_hex)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(QRectF(current_x, bar_y, seg_w, bar_h))
            current_x += seg_w

        # Legend row with auto-wrapping
        legend_y = 86.0
        chip_x = 16.0
        painter.setFont(QFont("Inter", 9))

        for seg in self.segments:
            if isinstance(seg, dict):
                cnt = seg.get("count", 0)
                color = QColor(seg.get("color", "#012D54"))
                lbl = seg.get("label", "")
            else:
                cnt = seg[1] if len(seg) > 1 else 0
                color = QColor(seg[2] if len(seg) > 2 else "#012D54")
                lbl = seg[0] if len(seg) > 0 else ""

            pct = (cnt / total_count * 100.0) if total_count > 0 else 0.0
            text = f"{lbl}: {cnt} ({pct:.0f}%)"
            chip_width = 16.0 + painter.fontMetrics().horizontalAdvance(text) + 20.0

            if chip_x + chip_width > w - 16 and chip_x > 16:
                chip_x = 16.0
                legend_y += 22.0

            # Color dot
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(chip_x, legend_y + 1, 10, 10), 3, 3)

            # Label text
            painter.setPen(QColor("#1F2937"))
            painter.drawText(QRectF(chip_x + 16, legend_y - 2, chip_width - 16, 16), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
            chip_x += chip_width


# ─────────────────────────────────────────────────────────────────────────────
# 3. TREND LINE CHART WIDGET
# ─────────────────────────────────────────────────────────────────────────────

class TrendLineChartWidget(QWidget):
    """
    Renders chronological line trends (e.g. Test Scores over time, Attendance over time)
    with data nodes, gridlines, axis labels, and gradient fills.
    """

    def __init__(self, title: str = "", unit: str = "%", parent: QWidget | None = None):
        super().__init__(parent)
        self.title = title
        self.unit = unit
        self.points: list[tuple[str, float]] = []
        self.line_color = "#012D54"
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)

    def set_data(self, points: list[tuple[str, float]], color: str = "#012D54"):
        """
        points: list of (x_label: str, y_value: float)
        """
        self.points = points
        self.line_color = color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        w, h = rect.width(), rect.height()

        # Background
        painter.setBrush(QBrush(QColor("#FEFEFE")))
        painter.setPen(QPen(QColor("#E9DEBA"), 1))
        painter.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 8, 8)

        # Title
        painter.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        painter.setPen(QColor("#012D54"))
        if self.title:
            painter.drawText(16, 26, self.title)

        if len(self.points) < 2:
            painter.setFont(QFont("Inter", 10))
            painter.setPen(QColor("#615F4B"))
            msg = "Need at least 2 chronological data points to draw trend line" if self.points else "No test records available"
            painter.drawText(QRectF(0, 40, w, h - 45), Qt.AlignmentFlag.AlignCenter, msg)
            return

        margin_left = 48.0
        margin_right = 24.0
        margin_top = 44.0
        margin_bottom = 36.0

        plot_w = w - margin_left - margin_right
        plot_h = h - margin_top - margin_bottom

        # Grid lines (0%, 25%, 50%, 75%, 100%)
        painter.setFont(QFont("Inter", 8))
        grid_steps = [0, 25, 50, 75, 100]
        for val in grid_steps:
            gy = margin_top + plot_h - (val / 100.0 * plot_h)
            painter.setPen(QPen(QColor("#F1EBD3"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(margin_left, gy), QPointF(margin_left + plot_w, gy))

            painter.setPen(QColor("#615F4B"))
            painter.drawText(QRectF(4, gy - 8, margin_left - 8, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{val}%")

        # Plot points coordinates
        n = len(self.points)
        x_step = plot_w / (n - 1) if n > 1 else plot_w
        canvas_points: list[QPointF] = []

        for i, (label, val) in enumerate(self.points):
            clamped_val = max(0.0, min(100.0, float(val)))
            px = margin_left + i * x_step
            py = margin_top + plot_h - (clamped_val / 100.0 * plot_h)
            canvas_points.append(QPointF(px, py))

        # Draw connecting line
        line_pen = QPen(QColor(self.line_color), 2.5)
        painter.setPen(line_pen)
        for i in range(len(canvas_points) - 1):
            painter.drawLine(canvas_points[i], canvas_points[i + 1])

        # Draw nodes & value labels
        for i, pt in enumerate(canvas_points):
            label, val = self.points[i]

            # Circle node
            painter.setBrush(QBrush(QColor("#FEFEFE")))
            painter.setPen(QPen(QColor(self.line_color), 2))
            painter.drawEllipse(pt, 4.0, 4.0)

            # Value label over node
            painter.setFont(QFont("Inter", 8, QFont.Weight.Bold))
            painter.setPen(QColor("#012D54"))
            painter.drawText(QRectF(pt.x() - 25, pt.y() - 18, 50, 14), Qt.AlignmentFlag.AlignCenter, f"{val:.0f}%")

            # X-axis label
            painter.setFont(QFont("Inter", 8))
            painter.setPen(QColor("#615F4B"))
            x_label = label[:10]
            painter.drawText(QRectF(pt.x() - 30, h - margin_bottom + 8, 60, 16), Qt.AlignmentFlag.AlignCenter, x_label)
