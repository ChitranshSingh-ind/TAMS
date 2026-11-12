"""
Printable Document & Template Customization Dialogs for TAMS.

Provides:
- FeeReceiptDialog: Live preview, dual-copy toggle, payment scope selection, printing, and PDF export.
- AdmissionFormDialog: Editable WYSIWYG admission form sheet + persistent template builder (fields,
  custom extra fields, rules, declaration, signatures) + printing and PDF export.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import QBuffer, QIODevice, QMarginsF, QSizeF, Qt
from PyQt6.QtGui import (
    QFont,
    QImage,
    QPageLayout,
    QPageSize,
    QTextCharFormat,
    QTextDocument,
)
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from app.database.connection import SessionLocal
from app.database.models.student import Student
from app.services.branding_service import image_file_to_data_uri, resolve_app_branding
from app.services.document_service import (
    A4_MARGIN_MM,
    A4_PAGE_WIDTH_MM,
    A4_PRINTABLE_HEIGHT_PT,
    A4_PRINTABLE_WIDTH_PT,
    DEFAULT_ADMISSION_FORM_CONFIG,
    STANDARD_ADMISSION_FIELDS,
    build_admission_form_student_data,
    build_fee_receipt_data,
    get_admission_form_config,
    mm_to_layout_px,
    render_admission_form_html,
    render_fee_receipt_html,
    reset_admission_form_config,
    save_admission_form_config,
)
from app.ui.theme import CREAM, DARK_NAVY, GOLD, LIGHT_GOLD, MUTED, NAVY, TEXT, WHITE


def qt_image_to_data_uri(image_path: Path | str | None) -> str | None:
    """
    Converts an image path to an embedded base64 data URI for reliable QTextDocument
    rendering across screen preview, printers, and PDF exports (including .ico files).
    """
    if not image_path:
        return None
    p = Path(image_path)
    if not p.exists() or not p.is_file():
        return None

    ext = p.suffix.lower()
    if ext == ".svg":
        return image_file_to_data_uri(p)

    img = QImage(str(p))
    if not img.isNull():
        buf = QBuffer()
        if buf.open(QIODevice.OpenModeFlag.WriteOnly):
            if img.save(buf, "PNG"):
                import base64
                b64 = base64.b64encode(bytes(buf.data())).decode("ascii")
                return f"data:image/png;base64,{b64}"

    return image_file_to_data_uri(p)


def _create_configured_printer(
    *,
    pdf_path: str | Path | None = None,
) -> QPrinter:
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    page_layout = QPageLayout(
        QPageSize(QPageSize.PageSizeId.A4),
        QPageLayout.Orientation.Portrait,
        QMarginsF(A4_MARGIN_MM, A4_MARGIN_MM, A4_MARGIN_MM, A4_MARGIN_MM),
        QPageLayout.Unit.Millimeter,
    )
    printer.setPageLayout(page_layout)
    if pdf_path is not None:
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(pdf_path))
    return printer


def configure_a4_document(document: QTextDocument) -> None:
    """Normalizes document margins, default font, and logical A4 page size."""
    document.setDocumentMargin(0)
    document.setDefaultFont(QFont("Arial", 10))
    document.setPageSize(QSizeF(A4_PRINTABLE_WIDTH_PT, A4_PRINTABLE_HEIGHT_PT))


def _configure_a4_sheet_widget(text_widget: QTextEdit) -> QFrame:
    """Wraps a QTextEdit/QTextBrowser as an A4-proportioned sheet centered on a subtle backdrop."""
    sheet_width_px = mm_to_layout_px(A4_PAGE_WIDTH_MM)
    margin_px = mm_to_layout_px(A4_MARGIN_MM)

    text_widget.setFixedWidth(sheet_width_px)
    text_widget.setStyleSheet(f"""
        {text_widget.__class__.__name__} {{
            background-color: #FFFFFF;
            color: {TEXT};
            border: 1px solid #D1C7A3;
            border-radius: 3px;
            padding: {margin_px}px;
        }}
    """)
    configure_a4_document(text_widget.document())

    backdrop = QFrame()
    backdrop.setStyleSheet(
        f"QFrame {{ background-color: #EAE5D3; border: 1px solid {LIGHT_GOLD}; border-radius: 6px; }}"
    )
    b_layout = QHBoxLayout(backdrop)
    b_layout.setContentsMargins(16, 12, 16, 12)
    b_layout.addStretch()
    b_layout.addWidget(text_widget)
    b_layout.addStretch()
    return backdrop


def print_text_document(
    document: QTextDocument,
    parent: QWidget,
    job_title: str = "Document",
) -> bool:
    """Opens the native OS Print dialog and prints the QTextDocument sized for A4."""
    printer = _create_configured_printer()
    dialog = QPrintDialog(printer, parent)
    dialog.setWindowTitle(f"Print {job_title}")
    if dialog.exec() == QDialog.DialogCode.Accepted:
        configure_a4_document(document)
        document.setPageSize(QSizeF(printer.pageRect(QPrinter.Unit.Point).size()))
        document.print(printer)
        return True
    return False


def export_text_document_pdf(
    document: QTextDocument,
    filepath: str | Path,
) -> None:
    """Exports the QTextDocument cleanly to an ISO A4 PDF file."""
    printer = _create_configured_printer(pdf_path=filepath)
    configure_a4_document(document)
    document.setPageSize(QSizeF(printer.pageRect(QPrinter.Unit.Point).size()))
    document.print(printer)


def _apply_print_dialog_styles(dialog: QDialog) -> None:
    dialog.setStyleSheet(f"""
        QDialog {{
            background-color: {CREAM};
        }}
        QFrame#docToolbarCard {{
            background-color: {WHITE};
            border: 1px solid {LIGHT_GOLD};
            border-radius: 8px;
        }}
        QFrame#tplCard {{
            background-color: {WHITE};
            border: 1px solid {LIGHT_GOLD};
            border-radius: 8px;
        }}
        QPushButton#primaryPrintBtn {{
            background-color: {NAVY};
            color: {WHITE};
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: 600;
            font-size: 13px;
        }}
        QPushButton#primaryPrintBtn:hover {{
            background-color: {DARK_NAVY};
        }}
        QPushButton#secondaryPrintBtn {{
            background-color: {LIGHT_GOLD};
            color: {NAVY};
            border: 1px solid {GOLD};
            border-radius: 6px;
            padding: 8px 14px;
            font-weight: 600;
            font-size: 13px;
        }}
        QPushButton#secondaryPrintBtn:hover {{
            background-color: {GOLD};
        }}
        QPushButton#neutralPrintBtn {{
            background-color: {WHITE};
            color: {TEXT};
            border: 1px solid {LIGHT_GOLD};
            border-radius: 6px;
            padding: 8px 14px;
            font-weight: 600;
            font-size: 13px;
        }}
        QPushButton#neutralPrintBtn:hover {{
            background-color: #F1EBD3;
        }}
        QPushButton#formatBtn {{
            background-color: {WHITE};
            color: {NAVY};
            border: 1px solid {LIGHT_GOLD};
            border-radius: 4px;
            padding: 4px 10px;
            font-size: 12px;
            font-weight: 700;
        }}
        QPushButton#formatBtn:checked, QPushButton#formatBtn:hover {{
            background-color: {LIGHT_GOLD};
            border-color: {GOLD};
        }}
    """)


class FeeReceiptDialog(QDialog):
    """
    Dialog to preview, customize (single vs dual copy / installment selection),
    print, or export a student fee receipt to PDF.
    """

    def __init__(self, fee_id: int, payment_id: int | None = None, parent=None):
        super().__init__(parent)
        self.fee_id = fee_id
        self.initial_payment_id = payment_id
        self.branding = resolve_app_branding()
        self.logo_data_uri = qt_image_to_data_uri(self.branding.get("logo_path"))
        self.current_receipt_data: dict[str, Any] = {}

        self.setWindowTitle(f"Fee Receipt — {self.branding['app_name']}")
        self.resize(920, 740)
        _apply_print_dialog_styles(self)

        self._build_ui()
        self._load_receipt_options()
        self._refresh_preview()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("Fee Payment Receipt (A4)")
        title.setStyleSheet(f"color: {NAVY}; font-size: 20px; font-weight: 700;")
        subtitle = QLabel("Preview official A4 fee receipt, print directly, or save as PDF.")
        subtitle.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()
        layout.addLayout(header)

        # Options bar
        toolbar_card = QFrame()
        toolbar_card.setObjectName("docToolbarCard")
        tb_layout = QHBoxLayout(toolbar_card)
        tb_layout.setContentsMargins(14, 10, 14, 10)
        tb_layout.setSpacing(14)

        tb_layout.addWidget(QLabel("Receipt Scope:"))
        self.scope_combo = QComboBox()
        self.scope_combo.setMinimumWidth(280)
        self.scope_combo.setFixedHeight(32)
        self.scope_combo.currentIndexChanged.connect(self._refresh_preview)
        tb_layout.addWidget(self.scope_combo, 1)

        self.dual_copy_cb = QCheckBox("Dual Copy (Student + Office on 1 A4 Page)")
        self.dual_copy_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dual_copy_cb.toggled.connect(self._refresh_preview)
        tb_layout.addWidget(self.dual_copy_cb)

        layout.addWidget(toolbar_card)

        # A4 Preview canvas
        self.preview_browser = QTextBrowser()
        self.preview_browser.setOpenExternalLinks(False)
        a4_backdrop = _configure_a4_sheet_widget(self.preview_browser)
        layout.addWidget(a4_backdrop, 1)

        # Footer action bar
        footer = QHBoxLayout()
        footer.setSpacing(10)

        self.print_btn = QPushButton("🖨 Print Receipt...")
        self.print_btn.setObjectName("primaryPrintBtn")
        self.print_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.print_btn.setFixedHeight(38)
        self.print_btn.clicked.connect(self._on_print_clicked)

        self.pdf_btn = QPushButton("📄 Save as PDF...")
        self.pdf_btn.setObjectName("secondaryPrintBtn")
        self.pdf_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pdf_btn.setFixedHeight(38)
        self.pdf_btn.clicked.connect(self._on_save_pdf_clicked)

        self.close_btn = QPushButton("Close")
        self.close_btn.setObjectName("neutralPrintBtn")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setFixedHeight(38)
        self.close_btn.clicked.connect(self.accept)

        footer.addWidget(self.print_btn)
        footer.addWidget(self.pdf_btn)
        footer.addStretch()
        footer.addWidget(self.close_btn)
        layout.addLayout(footer)

    def _load_receipt_options(self) -> None:
        self.scope_combo.blockSignals(True)
        self.scope_combo.clear()

        try:
            with SessionLocal() as session:
                consolidated = build_fee_receipt_data(session, self.fee_id, payment_id=None)
        except Exception as exc:
            QMessageBox.critical(self, "Receipt Error", str(exc))
            self.scope_combo.blockSignals(False)
            return

        payments = consolidated.get("payments") or []
        curr = self.branding.get("currency_symbol") or "₹"

        if len(payments) > 1:
            self.scope_combo.addItem(
                f"Consolidated Statement ({len(payments)} payments — {curr}{consolidated['total_paid']:,.2f})",
                None,
            )

        for p in payments:
            self.scope_combo.addItem(
                f"{p['receipt_number']} — {curr}{p['amount']:,.2f} ({p['payment_date']})",
                p["id"],
            )

        if len(payments) == 0:
            self.scope_combo.addItem("Fee Obligation Statement (No payments recorded yet)", None)

        if self.initial_payment_id is not None:
            idx = self.scope_combo.findData(self.initial_payment_id)
            if idx >= 0:
                self.scope_combo.setCurrentIndex(idx)

        self.scope_combo.blockSignals(False)

    def _refresh_preview(self) -> None:
        selected_payment_id = self.scope_combo.currentData()
        try:
            with SessionLocal() as session:
                self.current_receipt_data = build_fee_receipt_data(
                    session, self.fee_id, payment_id=selected_payment_id
                )
        except Exception as exc:
            self.preview_browser.setPlainText(f"Unable to build receipt: {exc}")
            return

        html_content = render_fee_receipt_html(
            self.current_receipt_data,
            self.branding,
            dual_copy=self.dual_copy_cb.isChecked(),
            logo_data_uri=self.logo_data_uri,
        )
        self.preview_browser.setHtml(html_content)
        configure_a4_document(self.preview_browser.document())

    def _on_print_clicked(self) -> None:
        receipt_no = self.current_receipt_data.get("receipt_number", "FeeReceipt")
        print_text_document(self.preview_browser.document(), self, job_title=f"Fee Receipt ({receipt_no})")

    def _on_save_pdf_clicked(self) -> None:
        receipt_no = self.current_receipt_data.get("receipt_number", "FeeReceipt")
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(receipt_no))
        default_name = f"Fee_Receipt_{safe_name}.pdf"
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Fee Receipt as PDF",
            default_name,
            "PDF Files (*.pdf)",
        )
        if not filepath:
            return
        if not filepath.lower().endswith(".pdf"):
            filepath += ".pdf"

        try:
            export_text_document_pdf(self.preview_browser.document(), filepath)
            QMessageBox.information(
                self,
                "PDF Exported",
                f"Fee receipt saved successfully to:\n{filepath}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "PDF Export Failed", f"Could not export PDF: {exc}")


class AdmissionFormDialog(QDialog):
    """
    Dialog for viewing, freely editing (both freehand WYSIWYG text & persistent structured template),
    printing, and exporting to PDF a student's admission form (or a blank walk-in form).
    """

    def __init__(self, student_id: int | None = None, parent=None):
        super().__init__(parent)
        self.initial_student_id = student_id
        self.branding = resolve_app_branding()
        self.logo_data_uri = qt_image_to_data_uri(self.branding.get("logo_path"))

        with SessionLocal() as session:
            self.form_cfg = get_admission_form_config(session)

        self.setWindowTitle(f"Admission Form Editor & Printer — {self.branding['app_name']}")
        self.resize(960, 760)
        _apply_print_dialog_styles(self)

        self._build_ui()
        self._populate_student_combo()
        self._load_template_editor_controls()
        self._reload_document_from_template()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        # Header
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("Printable & Editable Admission Form")
        title.setStyleSheet(f"color: {NAVY}; font-size: 20px; font-weight: 700;")
        subtitle = QLabel(
            "Pre-fill a student record or print a blank form. Edit text directly or customize the reusable template."
        )
        subtitle.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_layout.addLayout(title_box)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {LIGHT_GOLD};
                border-radius: 6px;
                background: {CREAM};
            }}
            QTabBar::tab {{
                background: {LIGHT_GOLD};
                color: {NAVY};
                padding: 8px 18px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 600;
                font-size: 13px;
            }}
            QTabBar::tab:selected {{
                background: {NAVY};
                color: {WHITE};
            }}
        """)

        self.tabs.addTab(self._create_editor_tab(), "📄 Edit & Print Form")
        self.tabs.addTab(self._create_template_tab(), "⚙ Customize Form Template")
        layout.addWidget(self.tabs, 1)

        # Shared Footer
        footer = QHBoxLayout()
        footer.setSpacing(10)

        hint_lbl = QLabel("Tip: Click anywhere on the form sheet to edit fields, notes, or wording before printing.")
        hint_lbl.setStyleSheet(f"color: {MUTED}; font-size: 11px;")

        self.print_btn = QPushButton("🖨 Print Admission Form...")
        self.print_btn.setObjectName("primaryPrintBtn")
        self.print_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.print_btn.setFixedHeight(38)
        self.print_btn.clicked.connect(self._on_print_clicked)

        self.pdf_btn = QPushButton("📄 Save as PDF...")
        self.pdf_btn.setObjectName("secondaryPrintBtn")
        self.pdf_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pdf_btn.setFixedHeight(38)
        self.pdf_btn.clicked.connect(self._on_save_pdf_clicked)

        self.close_btn = QPushButton("Close")
        self.close_btn.setObjectName("neutralPrintBtn")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setFixedHeight(38)
        self.close_btn.clicked.connect(self.accept)

        footer.addWidget(hint_lbl)
        footer.addStretch()
        footer.addWidget(self.print_btn)
        footer.addWidget(self.pdf_btn)
        footer.addWidget(self.close_btn)
        layout.addLayout(footer)

    def _create_editor_tab(self) -> QWidget:
        tab = QWidget()
        v_layout = QVBoxLayout(tab)
        v_layout.setContentsMargins(12, 12, 12, 12)
        v_layout.setSpacing(10)

        # Student Selection & Document Actions Bar
        top_card = QFrame()
        top_card.setObjectName("docToolbarCard")
        top_bar = QHBoxLayout(top_card)
        top_bar.setContentsMargins(12, 8, 12, 8)
        top_bar.setSpacing(10)

        top_bar.addWidget(QLabel("Pre-fill With:"))
        self.student_combo = QComboBox()
        self.student_combo.setMinimumWidth(260)
        self.student_combo.setFixedHeight(32)
        self.student_combo.currentIndexChanged.connect(self._reload_document_from_template)
        top_bar.addWidget(self.student_combo, 1)

        self.reload_btn = QPushButton("🔄 Reload Template")
        self.reload_btn.setObjectName("neutralPrintBtn")
        self.reload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reload_btn.clicked.connect(self._reload_document_from_template)
        top_bar.addWidget(self.reload_btn)

        self.save_layout_btn = QPushButton("💾 Save Current Sheet as Layout")
        self.save_layout_btn.setObjectName("secondaryPrintBtn")
        self.save_layout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_layout_btn.setToolTip("Saves your direct rich-text edits as the default custom admission form layout")
        self.save_layout_btn.clicked.connect(self._on_save_current_html_as_template)
        top_bar.addWidget(self.save_layout_btn)

        v_layout.addWidget(top_card)

        # WYSIWYG Formatting Bar
        fmt_bar = QHBoxLayout()
        fmt_bar.setSpacing(6)

        self.bold_btn = QPushButton("B")
        self.bold_btn.setObjectName("formatBtn")
        self.bold_btn.setCheckable(True)
        self.bold_btn.clicked.connect(self._toggle_bold)

        self.italic_btn = QPushButton("I")
        self.italic_btn.setObjectName("formatBtn")
        self.italic_btn.setCheckable(True)
        self.italic_btn.clicked.connect(self._toggle_italic)

        self.underline_btn = QPushButton("U")
        self.underline_btn.setObjectName("formatBtn")
        self.underline_btn.setCheckable(True)
        self.underline_btn.clicked.connect(self._toggle_underline)

        self.font_size_combo = QComboBox()
        self.font_size_combo.setFixedHeight(28)
        for pt in (9, 10, 11, 12, 13, 14, 16, 18, 20):
            self.font_size_combo.addItem(f"{pt} pt", pt)
        self.font_size_combo.setCurrentIndex(2)
        self.font_size_combo.currentIndexChanged.connect(self._change_font_size)

        align_left_btn = QPushButton("⬅ Left")
        align_left_btn.setObjectName("formatBtn")
        align_left_btn.clicked.connect(lambda: self.editor.setAlignment(Qt.AlignmentFlag.AlignLeft))

        align_center_btn = QPushButton("⬌ Center")
        align_center_btn.setObjectName("formatBtn")
        align_center_btn.clicked.connect(lambda: self.editor.setAlignment(Qt.AlignmentFlag.AlignCenter))

        align_right_btn = QPushButton("➡ Right")
        align_right_btn.setObjectName("formatBtn")
        align_right_btn.clicked.connect(lambda: self.editor.setAlignment(Qt.AlignmentFlag.AlignRight))

        for w in (
            self.bold_btn,
            self.italic_btn,
            self.underline_btn,
            self.font_size_combo,
            align_left_btn,
            align_center_btn,
            align_right_btn,
        ):
            w.setCursor(Qt.CursorShape.PointingHandCursor)
            fmt_bar.addWidget(w)

        fmt_bar.addStretch()
        v_layout.addLayout(fmt_bar)

        # Direct WYSIWYG Document Editor framed at exact ISO A4 proportions
        self.editor = QTextEdit()
        self.editor.cursorPositionChanged.connect(self._sync_format_buttons)
        sheet_backdrop = _configure_a4_sheet_widget(self.editor)
        v_layout.addWidget(sheet_backdrop, 1)

        return tab

    def _create_template_tab(self) -> QWidget:
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; } "
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )

        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(16, 14, 16, 14)
        c_layout.setSpacing(14)

        # Card 1: Title & Layout Options
        hdr_card = QFrame()
        hdr_card.setObjectName("tplCard")
        hdr_layout = QVBoxLayout(hdr_card)
        hdr_layout.setContentsMargins(16, 14, 16, 14)
        hdr_layout.setSpacing(10)

        h_lbl = QLabel("Form Header & Layout Options")
        h_lbl.setStyleSheet(f"color: {NAVY}; font-size: 14px; font-weight: 700;")
        hdr_layout.addWidget(h_lbl)

        h_form = QFormLayout()
        h_form.setSpacing(10)

        self.tpl_title_input = QLineEdit()
        self.tpl_title_input.setPlaceholderText("e.g. STUDENT ADMISSION FORM")
        h_form.addRow("Form Heading:", self.tpl_title_input)

        self.tpl_subtitle_input = QLineEdit()
        self.tpl_subtitle_input.setPlaceholderText("e.g. Please fill all details neatly in BLOCK letters.")
        h_form.addRow("Form Subtitle:", self.tpl_subtitle_input)

        self.tpl_photo_label_input = QLineEdit()
        self.tpl_photo_label_input.setPlaceholderText("e.g. Affix Recent Passport Size Photo")
        h_form.addRow("Photo Box Label:", self.tpl_photo_label_input)

        hdr_layout.addLayout(h_form)

        cb_row = QHBoxLayout()
        cb_row.setSpacing(18)
        self.tpl_show_logo_cb = QCheckBox("Show Institute Logo")
        self.tpl_show_photo_cb = QCheckBox("Show Passport Photo Box")
        self.tpl_show_office_cb = QCheckBox("Show 'For Office Use Only' Box")
        cb_row.addWidget(self.tpl_show_logo_cb)
        cb_row.addWidget(self.tpl_show_photo_cb)
        cb_row.addWidget(self.tpl_show_office_cb)
        cb_row.addStretch()
        hdr_layout.addLayout(cb_row)

        c_layout.addWidget(hdr_card)

        # Card 2: Standard Student & Parent Fields
        std_card = QFrame()
        std_card.setObjectName("tplCard")
        std_layout = QVBoxLayout(std_card)
        std_layout.setContentsMargins(16, 14, 16, 14)
        std_layout.setSpacing(10)

        s_lbl = QLabel("Standard Student & Parent Fields to Include")
        s_lbl.setStyleSheet(f"color: {NAVY}; font-size: 14px; font-weight: 700;")
        std_layout.addWidget(s_lbl)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)
        self.tpl_field_cbs: dict[str, QCheckBox] = {}
        for idx, (key, label, _group) in enumerate(STANDARD_ADMISSION_FIELDS):
            cb = QCheckBox(label)
            self.tpl_field_cbs[key] = cb
            grid.addWidget(cb, idx // 3, idx % 3)
        std_layout.addLayout(grid)
        c_layout.addWidget(std_card)

        # Card 3: Custom Additional Fields
        cust_card = QFrame()
        cust_card.setObjectName("tplCard")
        cust_layout = QVBoxLayout(cust_card)
        cust_layout.setContentsMargins(16, 14, 16, 14)
        cust_layout.setSpacing(10)

        cu_lbl = QLabel("Custom Additional Fields (Add/Edit Your Own Fields)")
        cu_lbl.setStyleSheet(f"color: {NAVY}; font-size: 14px; font-weight: 700;")
        cust_layout.addWidget(cu_lbl)

        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self.custom_field_input = QLineEdit()
        self.custom_field_input.setPlaceholderText("e.g. Aadhar Number, Blood Group, Transport Route...")
        self.custom_field_input.setFixedHeight(34)

        add_field_btn = QPushButton("＋ Add Field")
        add_field_btn.setObjectName("secondaryPrintBtn")
        add_field_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_field_btn.clicked.connect(self._on_add_custom_field)

        remove_field_btn = QPushButton("🗑 Remove Selected")
        remove_field_btn.setObjectName("neutralPrintBtn")
        remove_field_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_field_btn.clicked.connect(self._on_remove_custom_field)

        add_row.addWidget(self.custom_field_input, 1)
        add_row.addWidget(add_field_btn)
        add_row.addWidget(remove_field_btn)
        cust_layout.addLayout(add_row)

        self.custom_fields_list = QListWidget()
        self.custom_fields_list.setMaximumHeight(140)
        cust_layout.addWidget(self.custom_fields_list)
        c_layout.addWidget(cust_card)

        # Card 4: Terms, Declaration & Signatures
        terms_card = QFrame()
        terms_card.setObjectName("tplCard")
        t_layout = QVBoxLayout(terms_card)
        t_layout.setContentsMargins(16, 14, 16, 14)
        t_layout.setSpacing(10)

        t_lbl = QLabel("Rules, Terms, Declaration & Signatures")
        t_lbl.setStyleSheet(f"color: {NAVY}; font-size: 14px; font-weight: 700;")
        t_layout.addWidget(t_lbl)

        t_form = QFormLayout()
        t_form.setSpacing(10)

        self.tpl_terms_edit = QPlainTextEdit()
        self.tpl_terms_edit.setFixedHeight(95)
        t_form.addRow("Rules & Terms:", self.tpl_terms_edit)

        self.tpl_declaration_edit = QPlainTextEdit()
        self.tpl_declaration_edit.setFixedHeight(70)
        t_form.addRow("Declaration:", self.tpl_declaration_edit)

        sig_row = QHBoxLayout()
        sig_row.setSpacing(10)
        self.tpl_student_sig_input = QLineEdit()
        self.tpl_parent_sig_input = QLineEdit()
        self.tpl_authority_sig_input = QLineEdit()
        sig_row.addWidget(self.tpl_student_sig_input)
        sig_row.addWidget(self.tpl_parent_sig_input)
        sig_row.addWidget(self.tpl_authority_sig_input)
        t_form.addRow("Signature Labels:", sig_row)

        t_layout.addLayout(t_form)
        c_layout.addWidget(terms_card)

        # Save / Reset Bar
        tpl_btns = QHBoxLayout()
        tpl_btns.setSpacing(10)

        self.reset_template_btn = QPushButton("↺ Reset Template to Default")
        self.reset_template_btn.setObjectName("neutralPrintBtn")
        self.reset_template_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_template_btn.clicked.connect(self._on_reset_template)

        self.save_template_btn = QPushButton("💾 Save & Apply Template")
        self.save_template_btn.setObjectName("primaryPrintBtn")
        self.save_template_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_template_btn.clicked.connect(self._on_save_template)

        tpl_btns.addWidget(self.reset_template_btn)
        tpl_btns.addStretch()
        tpl_btns.addWidget(self.save_template_btn)
        c_layout.addLayout(tpl_btns)

        scroll.setWidget(container)
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return tab

    def _populate_student_combo(self) -> None:
        self.student_combo.blockSignals(True)
        self.student_combo.clear()
        self.student_combo.addItem("-- Blank Admission Form (Manual Fill-in) --", None)

        with SessionLocal() as session:
            students = session.scalars(
                select(Student).order_by(Student.first_name.asc(), Student.last_name.asc())
            ).all()
            for s in students:
                full_name = f"{s.first_name} {s.last_name or ''}".strip()
                adm = s.admission_number or "—"
                self.student_combo.addItem(f"{full_name} ({adm})", s.id)

        if self.initial_student_id is not None:
            idx = self.student_combo.findData(self.initial_student_id)
            if idx >= 0:
                self.student_combo.setCurrentIndex(idx)

        self.student_combo.blockSignals(False)

    def _load_template_editor_controls(self) -> None:
        cfg = self.form_cfg
        self.tpl_title_input.setText(cfg.get("form_title", "STUDENT ADMISSION FORM"))
        self.tpl_subtitle_input.setText(cfg.get("form_subtitle", ""))
        self.tpl_photo_label_input.setText(cfg.get("photo_box_label", "Affix Recent Passport Size Photo"))
        self.tpl_show_logo_cb.setChecked(bool(cfg.get("show_logo", True)))
        self.tpl_show_photo_cb.setChecked(bool(cfg.get("show_photo_box", True)))
        self.tpl_show_office_cb.setChecked(bool(cfg.get("show_office_use_section", True)))

        included = set(cfg.get("included_fields") or [])
        for key, cb in self.tpl_field_cbs.items():
            cb.setChecked(key in included)

        self.custom_fields_list.clear()
        for f_label in cfg.get("custom_fields") or []:
            item = QListWidgetItem(str(f_label))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.custom_fields_list.addItem(item)

        self.tpl_terms_edit.setPlainText(cfg.get("terms_and_conditions", ""))
        self.tpl_declaration_edit.setPlainText(cfg.get("declaration_text", ""))
        self.tpl_student_sig_input.setText(cfg.get("student_sig_label", "Student Signature"))
        self.tpl_parent_sig_input.setText(cfg.get("parent_sig_label", "Parent / Guardian Signature"))
        self.tpl_authority_sig_input.setText(cfg.get("authority_sig_label", "Authorized Signatory"))

    def _reload_document_from_template(self) -> None:
        selected_student_id = self.student_combo.currentData()
        curr = self.branding.get("currency_symbol") or "₹"
        with SessionLocal() as session:
            student_data = build_admission_form_student_data(
                session, selected_student_id, currency_symbol=curr
            )
        html_content = render_admission_form_html(
            self.form_cfg,
            student_data,
            self.branding,
            logo_data_uri=self.logo_data_uri,
        )
        self.editor.setHtml(html_content)
        configure_a4_document(self.editor.document())

    def _on_add_custom_field(self) -> None:
        text = self.custom_field_input.text().strip()
        if not text:
            return
        item = QListWidgetItem(text)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.custom_fields_list.addItem(item)
        self.custom_field_input.clear()

    def _on_remove_custom_field(self) -> None:
        row = self.custom_fields_list.currentRow()
        if row >= 0:
            self.custom_fields_list.takeItem(row)

    def _collect_template_from_controls(self) -> dict[str, Any]:
        included = [
            key for key, _, _ in STANDARD_ADMISSION_FIELDS
            if self.tpl_field_cbs.get(key) and self.tpl_field_cbs[key].isChecked()
        ]
        custom_fields = [
            self.custom_fields_list.item(i).text().strip()
            for i in range(self.custom_fields_list.count())
            if self.custom_fields_list.item(i).text().strip()
        ]
        return {
            "form_title": self.tpl_title_input.text().strip() or "STUDENT ADMISSION FORM",
            "form_subtitle": self.tpl_subtitle_input.text().strip(),
            "show_logo": self.tpl_show_logo_cb.isChecked(),
            "show_photo_box": self.tpl_show_photo_cb.isChecked(),
            "photo_box_label": self.tpl_photo_label_input.text().strip() or "Affix Passport Size Photo",
            "show_office_use_section": self.tpl_show_office_cb.isChecked(),
            "included_fields": included,
            "custom_fields": custom_fields,
            "terms_and_conditions": self.tpl_terms_edit.toPlainText().strip(),
            "declaration_text": self.tpl_declaration_edit.toPlainText().strip(),
            "student_sig_label": self.tpl_student_sig_input.text().strip() or "Student Signature",
            "parent_sig_label": self.tpl_parent_sig_input.text().strip() or "Parent / Guardian Signature",
            "authority_sig_label": self.tpl_authority_sig_input.text().strip() or "Authorized Signatory",
            "use_custom_html": False,
            "custom_html_template": "",
        }

    def _on_save_template(self) -> None:
        cfg_data = self._collect_template_from_controls()
        with SessionLocal() as session:
            self.form_cfg = save_admission_form_config(session, cfg_data)
        self._reload_document_from_template()
        self.tabs.setCurrentIndex(0)
        QMessageBox.information(
            self,
            "Template Saved",
            "Your custom admission form template has been saved and applied.",
        )

    def _on_reset_template(self) -> None:
        with SessionLocal() as session:
            self.form_cfg = reset_admission_form_config(session)
        self._load_template_editor_controls()
        self._reload_document_from_template()
        self.tabs.setCurrentIndex(0)

    def _on_save_current_html_as_template(self) -> None:
        cfg_copy = dict(self.form_cfg)
        cfg_copy["use_custom_html"] = True
        cfg_copy["custom_html_template"] = self.editor.toHtml()
        with SessionLocal() as session:
            self.form_cfg = save_admission_form_config(session, cfg_copy)
        QMessageBox.information(
            self,
            "Custom Layout Saved",
            "Your edited admission form sheet has been saved as the active custom layout.\n\n"
            "You can switch back to the structured form builder anytime from 'Customize Form Template'.",
        )

    def _toggle_bold(self, checked: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Bold if checked else QFont.Weight.Normal)
        self.editor.mergeCurrentCharFormat(fmt)

    def _toggle_italic(self, checked: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontItalic(checked)
        self.editor.mergeCurrentCharFormat(fmt)

    def _toggle_underline(self, checked: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontUnderline(checked)
        self.editor.mergeCurrentCharFormat(fmt)

    def _change_font_size(self) -> None:
        pt = self.font_size_combo.currentData()
        if pt:
            fmt = QTextCharFormat()
            fmt.setFontPointSize(float(pt))
            self.editor.mergeCurrentCharFormat(fmt)

    def _sync_format_buttons(self) -> None:
        fmt = self.editor.currentCharFormat()
        self.bold_btn.blockSignals(True)
        self.italic_btn.blockSignals(True)
        self.underline_btn.blockSignals(True)
        self.bold_btn.setChecked(fmt.fontWeight() >= QFont.Weight.Bold)
        self.italic_btn.setChecked(fmt.fontItalic())
        self.underline_btn.setChecked(fmt.fontUnderline())
        self.bold_btn.blockSignals(False)
        self.italic_btn.blockSignals(False)
        self.underline_btn.blockSignals(False)

    def _on_print_clicked(self) -> None:
        print_text_document(self.editor.document(), self, job_title="Student Admission Form")

    def _on_save_pdf_clicked(self) -> None:
        student_text = self.student_combo.currentText()
        default_name = "Admission_Form.pdf"
        if self.student_combo.currentData() is not None:
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in student_text)
            default_name = f"Admission_Form_{safe[:40]}.pdf"

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Admission Form as PDF",
            default_name,
            "PDF Files (*.pdf)",
        )
        if not filepath:
            return
        if not filepath.lower().endswith(".pdf"):
            filepath += ".pdf"

        try:
            export_text_document_pdf(self.editor.document(), filepath)
            QMessageBox.information(
                self,
                "PDF Exported",
                f"Admission form saved successfully to:\n{filepath}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "PDF Export Failed", f"Could not export PDF: {exc}")
