"""
Automated Tests for Application Branding (App Name, Logo, Icon),
Printable Fee Receipts, and Customizable & Printable Admission Forms.
"""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path
from unittest import mock

import pytest
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication, QMessageBox

import app.database.connection as conn
from app.services.batch_service import create_batch
from app.services.branding_service import (
    clear_branding_images,
    get_branding_dir,
    image_file_to_data_uri,
    resolve_app_branding,
    save_branding_image,
)
from app.services.document_service import (
    A4_MARGIN_MM,
    A4_PAGE_HEIGHT_MM,
    A4_PAGE_WIDTH_MM,
    A4_PRINTABLE_HEIGHT_PT,
    A4_PRINTABLE_WIDTH_PT,
    DEFAULT_ADMISSION_FORM_CONFIG,
    PASSPORT_PHOTO_HEIGHT_MM,
    PASSPORT_PHOTO_WIDTH_MM,
    amount_to_words,
    build_admission_form_student_data,
    build_fee_receipt_data,
    get_admission_form_config,
    mm_to_print_pt,
    render_admission_form_html,
    render_fee_receipt_html,
    reset_admission_form_config,
    save_admission_form_config,
)
from app.services.fee_service import create_fee, record_payment
from app.services.messaging_service import get_messaging_config, update_messaging_config
from app.services.student_service import create_student_with_parent
from app.ui.main_window import MainWindow
from app.ui.print_dialogs import (
    AdmissionFormDialog,
    FeeReceiptDialog,
    configure_a4_document,
    export_text_document_pdf,
)
from app.ui.settings_dialog import SettingsDialog


def _create_dummy_png(path: Path, color_hex: int = 0xFF012D54) -> Path:
    img = QImage(32, 32, QImage.Format.Format_ARGB32)
    img.fill(color_hex)
    assert img.save(str(path), "PNG")
    return path


@pytest.fixture
def sample_billing_and_student():
    uid = uuid.uuid4().hex[:8]
    with conn.SessionLocal() as session:
        batch = create_batch(session, name=f"PrintBatch {uid}", monthly_fee=2500.0)
        student = create_student_with_parent(
            session,
            admission_number=f"PRT-{uid}",
            first_name="Aarav",
            last_name="Verma",
            batch_id=batch.id,
            parent_name="Rajesh Verma",
            parent_phone="+919876543210",
            whatsapp_number="+919876543210",
            date_of_birth=date(2010, 5, 14),
            school_name="Delhi Public School",
            admission_date=date(2026, 4, 1),
            status="ACTIVE",
            monthly_fee=2200.0,
            notes="Prefers front row",
        )
        fee = create_fee(
            session,
            student_id=student.id,
            batch_id=batch.id,
            academic_year="2026-2027",
            fee_month=date.today().month,
            amount_due=2200.0,
            discount=200.0,
            due_date=date.today(),
            notes="Monthly installment",
        )
        pmt1 = record_payment(
            session,
            fee_id=fee.id,
            amount=1200.0,
            payment_date=date.today(),
            payment_method="UPI",
            receipt_number=f"REC1-{uid}",
            notes="First installment",
        )
        pmt2 = record_payment(
            session,
            fee_id=fee.id,
            amount=800.0,
            payment_date=date.today(),
            payment_method="Cash",
            receipt_number=f"REC2-{uid}",
            notes="Final installment",
        )
        return {
            "batch_id": batch.id,
            "student_id": student.id,
            "fee_id": fee.id,
            "pmt1_id": pmt1.id,
            "pmt2_id": pmt2.id,
            "uid": uid,
        }


# ─────────────────────────────────────────────────────────────────────────────
# 1. APPLICATION BRANDING (APP NAME, LOGO & ICON)
# ─────────────────────────────────────────────────────────────────────────────


def test_branding_service_save_and_resolve(qapp, tmp_path):
    logo_src = _create_dummy_png(tmp_path / "custom_logo.png", 0xFFD9B85F)
    icon_src = _create_dummy_png(tmp_path / "custom_icon.png", 0xFF15803D)

    saved_logo = save_branding_image(logo_src, "logo")
    saved_icon = save_branding_image(icon_src, "icon")
    assert Path(saved_logo).exists()
    assert Path(saved_icon).exists()
    assert Path(saved_logo).parent == get_branding_dir().resolve()

    data_uri = image_file_to_data_uri(saved_logo)
    assert data_uri is not None
    assert data_uri.startswith("data:image/png;base64,")

    resolved = resolve_app_branding({
        "app_name": "Apex Studio",
        "coaching_name": "Apex Academy",
        "app_logo_path": saved_logo,
        "app_icon_path": saved_icon,
        "academic_session": "2026-2027",
    })
    assert resolved["app_name"] == "Apex Studio"
    assert resolved["has_custom_logo"] is True
    assert resolved["has_custom_icon"] is True
    assert resolved["logo_path"] == Path(saved_logo)
    assert resolved["icon_path"] == Path(saved_icon)

    # Unsupported extension validation
    bad_file = tmp_path / "notes.txt"
    bad_file.write_text("not an image")
    with pytest.raises(ValueError, match="Unsupported image format"):
        save_branding_image(bad_file, "logo")

    clear_branding_images("logo")
    clear_branding_images("icon")


def test_settings_dialog_and_main_window_custom_branding(qapp, tmp_path):
    logo_src = _create_dummy_png(tmp_path / "my_logo.png", 0xFFD9B85F)
    icon_src = _create_dummy_png(tmp_path / "my_icon.png", 0xFF012D54)

    win = MainWindow()
    try:
        dialog = SettingsDialog(parent=win, initial_tab=0)
        assert hasattr(dialog, "gen_app_name_input")
        assert hasattr(dialog, "gen_logo_preview")
        assert hasattr(dialog, "gen_icon_preview")

        dialog.gen_app_name_input.setText("EduPulse Pro")
        dialog.gen_coaching_name_input.setText("Bright Minds Institute")
        dialog._pending_logo_path = str(logo_src)
        dialog._pending_icon_path = str(icon_src)
        dialog._update_branding_preview("logo", str(logo_src))
        dialog._update_branding_preview("icon", str(icon_src))

        with mock.patch("PyQt6.QtWidgets.QMessageBox.information"):
            dialog._on_save_general_settings()

        # Verify persisted in DB & refreshed on MainWindow
        with conn.SessionLocal() as session:
            cfg = get_messaging_config(session)
            assert cfg.get("app_name") == "EduPulse Pro"
            assert Path(cfg.get("app_logo_path", "")).exists()
            assert Path(cfg.get("app_icon_path", "")).exists()

        assert "EduPulse Pro" in win.windowTitle()
        assert "EduPulse Pro" in win.app_title_label.text()
        assert win.app_logo_label.pixmap() is not None
        assert not win.app_logo_label.pixmap().isNull()

        # Reset branding assets to defaults cleanly
        dialog._reset_branding_asset("logo")
        dialog._reset_branding_asset("icon")
        dialog.gen_app_name_input.setText("TAMS")
        dialog.gen_coaching_name_input.setText("TAMS Coaching Academy")
        with mock.patch("PyQt6.QtWidgets.QMessageBox.information"):
            dialog._on_save_general_settings()

        with conn.SessionLocal() as session:
            cfg_reset = get_messaging_config(session)
            assert cfg_reset.get("app_name") == "TAMS"
            assert cfg_reset.get("app_logo_path") == ""
            assert cfg_reset.get("app_icon_path") == ""

        dialog.close()
    finally:
        with conn.SessionLocal() as session:
            update_messaging_config(
                session,
                {
                    "app_name": "TAMS",
                    "coaching_name": "TAMS Coaching Academy",
                    "app_logo_path": "",
                    "app_icon_path": "",
                },
            )
        clear_branding_images("logo")
        clear_branding_images("icon")
        win.close()


# ─────────────────────────────────────────────────────────────────────────────
# 2. PRINTABLE FEE RECEIPTS
# ─────────────────────────────────────────────────────────────────────────────


def test_amount_to_words():
    assert amount_to_words(1200, "₹") == "Rupees One Thousand Two Hundred Only"
    assert amount_to_words(250.50, "₹") == "Rupees Two Hundred Fifty and Fifty Paise Only"
    assert amount_to_words(500, "$") == "Five Hundred Only"


def test_fee_receipt_data_and_html_rendering(sample_billing_and_student):
    fee_id = sample_billing_and_student["fee_id"]
    pmt1_id = sample_billing_and_student["pmt1_id"]
    uid = sample_billing_and_student["uid"]

    branding = resolve_app_branding({
        "app_name": "TestPortal",
        "coaching_name": "Bright Coaching Center",
        "coaching_phone": "+91 99999 00000",
        "coaching_address": "123 Knowledge Lane",
        "currency_symbol": "₹",
    })

    with conn.SessionLocal() as session:
        single_data = build_fee_receipt_data(session, fee_id, payment_id=pmt1_id)
        assert single_data["receipt_number"] == f"REC1-{uid}"
        assert single_data["receipt_amount"] == 1200.0
        assert single_data["total_paid"] == 2000.0
        assert single_data["outstanding_balance"] == 0.0
        assert single_data["student_name"] == "Aarav Verma"

        consolidated_data = build_fee_receipt_data(session, fee_id, payment_id=None)
        assert consolidated_data["is_consolidated"] is True
        assert consolidated_data["receipt_amount"] == 2000.0
        assert len(consolidated_data["payments"]) == 2

    html_single = render_fee_receipt_html(single_data, branding, dual_copy=False)
    assert "Bright Coaching Center" in html_single
    assert f"REC1-{uid}" in html_single
    assert "Aarav Verma" in html_single
    assert "Rupees One Thousand Two Hundred Only" in html_single

    html_dual = render_fee_receipt_html(consolidated_data, branding, dual_copy=True)
    assert "STUDENT / PARENT COPY" in html_dual
    assert "OFFICE COPY" in html_dual
    assert f"REC2-{uid}" in html_dual


def test_fee_receipt_dialog_and_pdf_export(qapp, sample_billing_and_student, tmp_path):
    fee_id = sample_billing_and_student["fee_id"]
    pmt2_id = sample_billing_and_student["pmt2_id"]

    dlg = FeeReceiptDialog(fee_id, payment_id=pmt2_id)
    assert dlg.scope_combo.count() >= 3  # Consolidated + 2 individual payments
    assert dlg.scope_combo.currentData() == pmt2_id
    assert "Aarav Verma" in dlg.preview_browser.toPlainText()

    # Toggle dual copy
    dlg.dual_copy_cb.setChecked(True)
    assert "OFFICE COPY" in dlg.preview_browser.toPlainText()
    assert "STUDENT / PARENT COPY" in dlg.preview_browser.toPlainText()

    # Export real PDF file
    pdf_path = tmp_path / "test_receipt.pdf"
    with mock.patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName", return_value=(str(pdf_path), "PDF Files (*.pdf)")):
        with mock.patch("PyQt6.QtWidgets.QMessageBox.information"):
            dlg._on_save_pdf_clicked()

    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(b"%PDF-")
    dlg.close()


def test_fees_mixin_receipt_button_present(qapp, sample_billing_and_student):
    win = MainWindow()
    win.change_page(4)
    assert win.fees_table.rowCount() >= 1
    actions_widget = win.fees_table.cellWidget(0, 9)
    assert actions_widget is not None
    btn_texts = [btn.text() for btn in actions_widget.findChildren(type(win.sidebar_buttons[0]))]
    assert any("Receipt" in t for t in btn_texts)
    win.close()


# ─────────────────────────────────────────────────────────────────────────────
# 3. EDITABLE & PRINTABLE ADMISSION FORMS
# ─────────────────────────────────────────────────────────────────────────────


def test_admission_form_template_persistence_and_rendering(sample_billing_and_student):
    student_id = sample_billing_and_student["student_id"]
    uid = sample_billing_and_student["uid"]

    try:
        with conn.SessionLocal() as session:
            default_cfg = get_admission_form_config(session)
            assert default_cfg["form_title"] == DEFAULT_ADMISSION_FORM_CONFIG["form_title"]

            # Customize template
            custom_cfg = dict(default_cfg)
            custom_cfg["form_title"] = "CUSTOM ACADEMY ADMISSION FORM"
            custom_cfg["custom_fields"] = ["Aadhar ID", "Transport Needed"]
            custom_cfg["terms_and_conditions"] = "Rule A: Always bring ID card."
            saved = save_admission_form_config(session, custom_cfg)
            assert saved["form_title"] == "CUSTOM ACADEMY ADMISSION FORM"

            reloaded = get_admission_form_config(session)
            assert reloaded["custom_fields"] == ["Aadhar ID", "Transport Needed"]

            prefilled = build_admission_form_student_data(session, student_id)
            assert prefilled["student_name"] == "Aarav Verma"
            assert prefilled["admission_number"] == f"PRT-{uid}"

            blank = build_admission_form_student_data(session, None)
            assert blank["student_name"] == ""

        branding = resolve_app_branding({"app_name": "TAMS", "coaching_name": "TAMS Academy"})
        html_filled = render_admission_form_html(reloaded, prefilled, branding)
        assert "CUSTOM ACADEMY ADMISSION FORM" in html_filled
        assert "Aarav Verma" in html_filled
        assert "Aadhar ID" in html_filled
        assert "Rule A: Always bring ID card." in html_filled

        html_blank = render_admission_form_html(reloaded, blank, branding)
        assert "CUSTOM ACADEMY ADMISSION FORM" in html_blank
        assert "Aarav Verma" not in html_blank
        assert "____" in html_blank
    finally:
        with conn.SessionLocal() as session:
            reset_admission_form_config(session)


def test_admission_form_dialog_edit_template_and_pdf(qapp, sample_billing_and_student, tmp_path):
    student_id = sample_billing_and_student["student_id"]

    try:
        dlg = AdmissionFormDialog(student_id=student_id)
        assert "Aarav Verma" in dlg.editor.toPlainText()

        # Edit template controls on Tab 2
        dlg.tpl_title_input.setText("2026 ENROLLMENT SHEET")
        dlg.custom_field_input.setText("Medical Allergies")
        dlg._on_add_custom_field()
        dlg.tpl_terms_edit.setPlainText("Custom rule: 85% minimum attendance.")

        with mock.patch("PyQt6.QtWidgets.QMessageBox.information"):
            dlg._on_save_template()

        assert "2026 ENROLLMENT SHEET" in dlg.editor.toPlainText()
        assert "Medical Allergies" in dlg.editor.toPlainText()
        assert "Custom rule: 85% minimum attendance." in dlg.editor.toPlainText()

        # Direct freehand user editing right inside the sheet before printing
        dlg.editor.append("\nSpecial Scholarship Note: 20% Merit Waiver Approved.")
        assert "Special Scholarship Note: 20% Merit Waiver Approved." in dlg.editor.toPlainText()

        # Export edited form directly to PDF
        pdf_path = tmp_path / "edited_admission_form.pdf"
        with mock.patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName", return_value=(str(pdf_path), "PDF Files (*.pdf)")):
            with mock.patch("PyQt6.QtWidgets.QMessageBox.information"):
                dlg._on_save_pdf_clicked()

        assert pdf_path.exists()
        assert pdf_path.read_bytes().startswith(b"%PDF-")

        # Switch to blank form mode cleanly
        dlg.student_combo.setCurrentIndex(0)
        assert dlg.student_combo.currentData() is None
        assert "Aarav Verma" not in dlg.editor.toPlainText()

        # Save WYSIWYG layout as custom template and reload
        dlg.editor.setPlainText("Custom Header {{student_name}} - {{admission_number}}")
        with mock.patch("PyQt6.QtWidgets.QMessageBox.information"):
            dlg._on_save_current_html_as_template()
        with conn.SessionLocal() as session:
            cfg = get_admission_form_config(session)
            assert cfg["use_custom_html"] is True
            assert "{{student_name}}" in cfg["custom_html_template"]

        dlg.close()
    finally:
        with conn.SessionLocal() as session:
            reset_admission_form_config(session)


def test_students_page_has_admission_form_buttons(qapp, sample_billing_and_student):
    win = MainWindow()
    win.change_page(1)
    assert hasattr(win, "admission_form_button")
    assert win.students_table.rowCount() >= 1
    actions_widget = win.students_table.cellWidget(0, 6)
    assert actions_widget is not None
    btn_texts = [btn.text() for btn in actions_widget.findChildren(type(win.admission_form_button))]
    assert "Form" in btn_texts
    win.close()


def test_payment_history_dialog_print_buttons(qapp, sample_billing_and_student):
    from app.ui.fee_dialogs import PaymentHistoryDialog

    hist = PaymentHistoryDialog(sample_billing_and_student["fee_id"])
    assert hasattr(hist, "print_all_btn")
    assert hist.table.rowCount() == 2
    action_w = hist.table.cellWidget(0, 6)
    assert action_w is not None
    btn_texts = [b.text() for b in action_w.findChildren(type(hist.print_all_btn))]
    assert any("Print" in t for t in btn_texts)
    assert "Reverse" in btn_texts
    hist.close()


def test_a4_geometry_units_and_passport_photo_standard(qapp, sample_billing_and_student, tmp_path):
    """Verify A4 page constants, pt typography, and standard 35x45 mm passport photo sizing."""
    import base64
    import re
    import subprocess
    import shutil

    assert A4_PAGE_WIDTH_MM == 210.0
    assert A4_PAGE_HEIGHT_MM == 297.0
    assert A4_MARGIN_MM == 12.0
    assert PASSPORT_PHOTO_WIDTH_MM == 35.0
    assert PASSPORT_PHOTO_HEIGHT_MM == 45.0
    assert mm_to_print_pt(PASSPORT_PHOTO_WIDTH_MM) == 99
    assert mm_to_print_pt(PASSPORT_PHOTO_HEIGHT_MM) == 128

    branding = resolve_app_branding({"app_name": "TestAcademy", "coaching_name": "Test Academy"})
    with conn.SessionLocal() as session:
        receipt_data = build_fee_receipt_data(session, sample_billing_and_student["fee_id"])
        student_data = build_admission_form_student_data(session, sample_billing_and_student["student_id"])

    receipt_html = render_fee_receipt_html(receipt_data, branding, dual_copy=True)
    form_html = render_admission_form_html(DEFAULT_ADMISSION_FORM_CONFIG, student_data, branding)

    # Typography must strictly use absolute point (pt) sizing rather than screen px
    assert not re.search(r"font-size:\s*[0-9.]+px", receipt_html)
    assert not re.search(r"font-size:\s*[0-9.]+px", form_html)
    assert "pt;" in receipt_html
    assert "pt;" in form_html

    # Passport photo SVG must carry exact 35 mm × 45 mm viewBox and 99 × 128 pt print dimensions
    match = re.search(r'data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)" width="99" height="128"', form_html)
    assert match is not None, "Expected 99x128 pt (35x45 mm) SVG passport photo box"
    svg_xml = base64.b64decode(match.group(1)).decode("utf-8")
    assert 'viewBox="0 0 35 45"' in svg_xml
    assert "35 mm × 45 mm" in svg_xml

    # Dialogs configure QTextDocument to A4 printable dimensions in points with zero internal margin
    rec_dlg = FeeReceiptDialog(sample_billing_and_student["fee_id"])
    assert rec_dlg.preview_browser.document().documentMargin() == 0
    assert rec_dlg.preview_browser.document().pageSize().width() == pytest.approx(A4_PRINTABLE_WIDTH_PT)
    assert rec_dlg.preview_browser.document().pageSize().height() == pytest.approx(A4_PRINTABLE_HEIGHT_PT)
    rec_dlg.close()

    form_dlg = AdmissionFormDialog(student_id=sample_billing_and_student["student_id"])
    assert form_dlg.editor.document().documentMargin() == 0
    assert form_dlg.editor.document().pageSize().width() == pytest.approx(A4_PRINTABLE_WIDTH_PT)
    assert form_dlg.editor.document().pageSize().height() == pytest.approx(A4_PRINTABLE_HEIGHT_PT)

    pdf_path = tmp_path / "a4_check.pdf"
    export_text_document_pdf(form_dlg.editor.document(), pdf_path)
    form_dlg.close()
    assert pdf_path.exists()

    if shutil.which("pdfinfo"):
        info = subprocess.check_output(["pdfinfo", str(pdf_path)], text=True)
        assert "A4" in info
        assert "Pages:           1" in info or "Pages:          1" in info


