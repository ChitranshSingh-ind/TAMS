"""
Printable Document & Template Service for TAMS.

Generates Qt-compatible HTML documents for:
1. Official Fee Payment Receipts (single transaction or consolidated statement, single or dual copy).
2. Editable & Customizable Student Admission Forms (pre-filled for a student or blank).
"""

from __future__ import annotations

import base64
import html
import json
import textwrap
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database.models.fee import Fee
from app.database.models.student import Student
from app.services.messaging_service import (
    ensure_messaging_seed_data,
    get_messaging_config,
    update_messaging_config,
)

# ─────────────────────────────────────────────────────────────────────────────
# A4 Page Geometry & Physical Unit Constants (ISO 216 A4: 210 mm × 297 mm)
# ─────────────────────────────────────────────────────────────────────────────
A4_PAGE_WIDTH_MM = 210.0
A4_PAGE_HEIGHT_MM = 297.0
A4_MARGIN_MM = 12.0
A4_PRINTABLE_WIDTH_MM = A4_PAGE_WIDTH_MM - (2.0 * A4_MARGIN_MM)    # 186.0 mm
A4_PRINTABLE_HEIGHT_MM = A4_PAGE_HEIGHT_MM - (2.0 * A4_MARGIN_MM)  # 273.0 mm
PT_PER_MM = 72.0 / 25.4
PX_PER_MM = 96.0 / 25.4  # Qt QTextDocument HTML layout uses 96 DPI logical coordinates
A4_PRINTABLE_WIDTH_PT = round(A4_PRINTABLE_WIDTH_MM * PT_PER_MM, 2)    # 527.24 pt
A4_PRINTABLE_HEIGHT_PT = round(A4_PRINTABLE_HEIGHT_MM * PT_PER_MM, 2)  # 773.86 pt

# Standard Passport Size Photo (ICAO / Indian standard: 35 mm × 45 mm)
PASSPORT_PHOTO_WIDTH_MM = 35.0
PASSPORT_PHOTO_HEIGHT_MM = 45.0


def mm_to_layout_px(mm: float) -> int:
    """Converts physical millimeters to 96-DPI Qt widget screen pixel coordinates."""
    return max(1, round(mm * PX_PER_MM))


def mm_to_print_pt(mm: float) -> int:
    """Converts physical millimeters to 72-DPI point attributes for QTextDocument HTML layout."""
    return max(1, round(mm * PT_PER_MM))


MONTH_NAMES: tuple[str, ...] = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

# Ordered list of (field_key, display_label, section_group)
STANDARD_ADMISSION_FIELDS: list[tuple[str, str, str]] = [
    ("admission_number", "Admission / Roll No.", "student"),
    ("student_name", "Student Full Name", "student"),
    ("date_of_birth", "Date of Birth", "student"),
    ("school_name", "Current / Previous School", "student"),
    ("batch_name", "Batch Enrolled / Applied", "student"),
    ("admission_date", "Date of Admission", "student"),
    ("monthly_fee", "Applicable Monthly Fee", "student"),
    ("parent_name", "Parent / Guardian Name", "parent"),
    ("parent_phone", "Parent Contact Number", "parent"),
    ("whatsapp_number", "WhatsApp Number", "parent"),
    ("notes", "Additional Notes / Remarks", "student"),
]

DEFAULT_ADMISSION_FORM_CONFIG: dict[str, Any] = {
    "form_title": "STUDENT ADMISSION FORM",
    "form_subtitle": "Please fill all details neatly in BLOCK letters.",
    "show_logo": True,
    "show_photo_box": True,
    "photo_box_label": "Affix Recent Passport Size Photo",
    "show_office_use_section": True,
    "included_fields": [item[0] for item in STANDARD_ADMISSION_FIELDS],
    "custom_fields": [
        "Gender",
        "Blood Group",
        "Residential Address",
        "Parent / Guardian Occupation",
        "Previous Class & Percentage",
        "Emergency Contact Number",
    ],
    "terms_and_conditions": (
        "1. Monthly tuition fees must be deposited on or before the due date each month.\n"
        "2. Regular attendance, punctuality, and classroom discipline are strictly expected.\n"
        "3. Any change in contact details or residential address should be notified promptly.\n"
        "4. Fees once paid are non-refundable and non-transferable under any circumstances."
    ),
    "declaration_text": (
        "I hereby declare that all the information furnished above is true and complete to the "
        "best of my knowledge. We agree to abide by the rules, fee schedule, and discipline policy "
        "of the institute."
    ),
    "student_sig_label": "Student Signature",
    "parent_sig_label": "Parent / Guardian Signature",
    "authority_sig_label": "Authorized Signatory",
    "use_custom_html": False,
    "custom_html_template": "",
}


_ONES = (
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
    "Seventeen", "Eighteen", "Nineteen",
)
_TENS = (
    "", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety",
)


def _two_digits_to_words(n: int) -> str:
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    return f"{_TENS[tens]} {_ONES[ones]}".strip()


def _three_digits_to_words(n: int) -> str:
    hundreds, rem = divmod(n, 100)
    parts: list[str] = []
    if hundreds:
        parts.append(f"{_ONES[hundreds]} Hundred")
    if rem:
        parts.append(_two_digits_to_words(rem))
    return " ".join(parts).strip()


def _indian_int_to_words(n: int) -> str:
    if n == 0:
        return "Zero"
    parts: list[str] = []
    crores, n = divmod(n, 10_000_000)
    if crores:
        parts.append(f"{_indian_int_to_words(crores)} Crore")
    lakhs, n = divmod(n, 100_000)
    if lakhs:
        parts.append(f"{_two_digits_to_words(lakhs)} Lakh")
    thousands, n = divmod(n, 1_000)
    if thousands:
        parts.append(f"{_two_digits_to_words(thousands)} Thousand")
    if n:
        parts.append(_three_digits_to_words(n))
    return " ".join(parts).strip()


def amount_to_words(amount: float | int | Decimal, currency_symbol: str = "₹") -> str:
    """Converts a monetary amount to readable words suitable for official receipts."""
    dec = Decimal(str(amount or 0)).quantize(Decimal("0.01"))
    if dec < 0:
        dec = abs(dec)

    whole = int(dec)
    fraction = int((dec - Decimal(whole)) * 100)
    whole_words = _indian_int_to_words(whole)

    is_inr = currency_symbol.strip() in ("₹", "Rs", "Rs.", "INR")
    if is_inr:
        if fraction:
            frac_words = _two_digits_to_words(fraction)
            return f"Rupees {whole_words} and {frac_words} Paise Only"
        return f"Rupees {whole_words} Only"

    if fraction:
        frac_words = _two_digits_to_words(fraction)
        return f"{whole_words} and {frac_words}/100 Only"
    return f"{whole_words} Only"


def _render_letterhead_html(
    branding: dict[str, Any],
    *,
    document_badge: str,
    logo_data_uri: str | None = None,
    show_logo: bool = True,
    compact: bool = False,
) -> str:
    coaching_name = html.escape(branding.get("coaching_name") or branding.get("app_name") or "TAMS")
    app_name = html.escape(branding.get("app_name") or "TAMS")
    tagline = html.escape(branding.get("coaching_tagline") or "")
    phone = html.escape(branding.get("coaching_phone") or "")
    email = html.escape(branding.get("coaching_email") or "")
    address = html.escape(branding.get("coaching_address") or "")
    session_str = html.escape(branding.get("academic_session") or "")

    title_pt = 13.5 if compact else 16.0
    sub_pt = 8.0 if compact else 9.0
    badge_pt = 9.0 if compact else 10.0
    logo_mm = 13.0 if compact else 16.0
    logo_pt = mm_to_print_pt(logo_mm)
    logo_col_pt = mm_to_print_pt(logo_mm + 3.0)
    badge_col_pt = mm_to_print_pt(44.0)

    contact_bits: list[str] = []
    if phone:
        contact_bits.append(f"Phone: {phone}")
    if email:
        contact_bits.append(f"Email: {email}")
    contact_line = " &nbsp;|&nbsp; ".join(contact_bits)

    pad_bottom = "5pt" if compact else "7pt"
    margin_bottom = "6pt" if compact else "9pt"

    logo_cell = ""
    if show_logo and logo_data_uri:
        logo_cell = (
            f'<td width="{logo_col_pt}" valign="middle" align="center" '
            f'style="padding-right: 8pt; padding-bottom: {pad_bottom}; border-bottom: 2px solid #012D54;">'
            f'<img src="{logo_data_uri}" width="{logo_pt}" height="{logo_pt}" />'
            f"</td>"
        )

    tagline_html = (
        f'<div style="font-size: {sub_pt}pt; color: #615F4B; font-style: italic; margin-top: 1.5pt;">{tagline}</div>'
        if tagline
        else ""
    )
    address_html = (
        f'<div style="font-size: {sub_pt}pt; color: #374151; margin-top: 1.5pt;">{address}</div>'
        if address
        else ""
    )
    contact_html = (
        f'<div style="font-size: {sub_pt}pt; color: #374151; margin-top: 1.5pt;">{contact_line}</div>'
        if contact_line
        else ""
    )
    session_badge = (
        f'<div style="font-size: {sub_pt}pt; color: #615F4B; margin-top: 3pt;">Session: <b>{session_str}</b></div>'
        if session_str
        else ""
    )
    app_tag = (
        f'<div style="font-size: 7.5pt; color: #615F4B; font-weight: 600; margin-top: 1.5pt;">[{app_name}]</div>'
        if app_name.lower() not in coaching_name.lower()
        else ""
    )

    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           style="margin-bottom: {margin_bottom};">
        <tr>
            {logo_cell}
            <td valign="middle" align="left"
                style="padding-bottom: {pad_bottom}; border-bottom: 2px solid #012D54;">
                <div style="font-size: {title_pt}pt; font-weight: 700; color: #012D54;">
                    {coaching_name}
                </div>
                {tagline_html}
                {address_html}
                {contact_html}
            </td>
            <td width="{badge_col_pt}" valign="middle" align="right"
                style="padding-bottom: {pad_bottom}; border-bottom: 2px solid #012D54;">
                <table width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td align="center" style="background-color: #012D54; color: #FEFEFE;
                                                  padding: 4pt 8pt; font-size: {badge_pt}pt;
                                                  font-weight: 700; border-bottom: 2px solid #D9B85F;">
                            {html.escape(document_badge)}
                        </td>
                    </tr>
                </table>
                {session_badge}
                {app_tag}
            </td>
        </tr>
    </table>
    """


def build_fee_receipt_data(
    session: Session,
    fee_id: int,
    payment_id: int | None = None,
) -> dict[str, Any]:
    """
    Collects complete structured data required to render a fee payment receipt.
    If payment_id is given, generates receipt details scoped to that payment;
    otherwise generates a consolidated statement for the fee obligation.
    """
    stmt = (
        select(Fee)
        .options(
            joinedload(Fee.student).joinedload(Student.parent),
            joinedload(Fee.batch),
            selectinload(Fee.payments),
        )
        .where(Fee.id == fee_id)
    )
    fee = session.scalars(stmt).first()
    if fee is None:
        raise ValueError(f"Fee record #{fee_id} not found.")

    valid_payments = sorted(
        [p for p in fee.payments if not p.is_reversed],
        key=lambda p: (p.payment_date, p.id),
    )

    target_payment = None
    if payment_id is not None:
        for idx, p in enumerate(valid_payments, start=1):
            if p.id == payment_id:
                target_payment = p
                target_index = idx
                break
        if target_payment is None:
            raise ValueError(f"Valid payment #{payment_id} not found for fee #{fee_id}.")
    else:
        target_index = len(valid_payments)

    month_name = (
        MONTH_NAMES[fee.fee_month - 1]
        if 1 <= fee.fee_month <= 12
        else f"Month {fee.fee_month}"
    )
    fee_period = f"{month_name} {fee.academic_year}"

    student = fee.student
    parent = student.parent if student else None
    student_name = f"{student.first_name} {student.last_name or ''}".strip() if student else "Unknown"
    admission_no = (student.admission_number if student else None) or "—"
    batch_name = (fee.batch.name if fee.batch else None) or "—"
    parent_name = (parent.name if parent else None) or "—"
    parent_phone = (parent.whatsapp_number or parent.phone) if parent else "—"

    payments_list = [
        {
            "id": p.id,
            "receipt_number": p.receipt_number or f"PMT-{p.id}",
            "payment_date": p.payment_date.strftime("%d %b %Y"),
            "payment_method": p.payment_method,
            "amount": float(p.amount),
            "notes": p.notes or "",
        }
        for p in valid_payments
    ]

    if target_payment is not None:
        receipt_number = target_payment.receipt_number or f"PMT-{target_payment.id}"
        receipt_date = target_payment.payment_date.strftime("%d %b %Y")
        payment_method = target_payment.payment_method
        payment_notes = target_payment.notes or fee.notes or ""
        receipt_amount = float(target_payment.amount)
        is_consolidated = False
        installment_label = (
            f"Installment {target_index} of {len(valid_payments)}"
            if len(valid_payments) > 1
            else "Single Payment"
        )
    else:
        latest_pmt = valid_payments[-1] if valid_payments else None
        receipt_number = (
            latest_pmt.receipt_number
            if (latest_pmt and len(valid_payments) == 1 and latest_pmt.receipt_number)
            else f"FEE-{fee.academic_year.replace(' ', '')}-{fee.fee_month:02d}-{fee.id}"
        )
        receipt_date = (
            latest_pmt.payment_date.strftime("%d %b %Y")
            if latest_pmt
            else date.today().strftime("%d %b %Y")
        )
        payment_method = (
            ", ".join(sorted({p.payment_method for p in valid_payments}))
            if valid_payments
            else "—"
        )
        payment_notes = fee.notes or ""
        receipt_amount = float(fee.total_paid)
        is_consolidated = len(valid_payments) > 1
        installment_label = (
            f"Consolidated ({len(valid_payments)} payments)"
            if valid_payments
            else "Fee Statement"
        )

    return {
        "fee_id": fee.id,
        "payment_id": target_payment.id if target_payment else None,
        "is_consolidated": is_consolidated,
        "receipt_number": receipt_number,
        "receipt_date": receipt_date,
        "installment_label": installment_label,
        "payment_method": payment_method,
        "payment_notes": payment_notes,
        "receipt_amount": receipt_amount,
        "base_amount": float(fee.amount_due),
        "discount": float(fee.discount),
        "final_amount_due": float(fee.final_amount_due),
        "total_paid": float(fee.total_paid),
        "outstanding_balance": float(fee.outstanding_balance),
        "status": fee.calculate_status(),
        "fee_period": fee_period,
        "academic_year": fee.academic_year,
        "due_date": fee.due_date.strftime("%d %b %Y") if fee.due_date else "—",
        "student_name": student_name,
        "admission_number": admission_no,
        "batch_name": batch_name,
        "parent_name": parent_name,
        "parent_phone": parent_phone or "—",
        "payments": payments_list,
    }


def _render_single_receipt_block(
    receipt_data: dict[str, Any],
    branding: dict[str, Any],
    *,
    copy_label: str,
    logo_data_uri: str | None = None,
    compact: bool = False,
) -> str:
    curr = html.escape(branding.get("currency_symbol") or "₹")
    letterhead = _render_letterhead_html(
        branding,
        document_badge="FEE RECEIPT",
        logo_data_uri=logo_data_uri,
        show_logo=True,
        compact=compact,
    )

    body_pt = 9.0 if compact else 10.0
    small_pt = 8.0 if compact else 9.0
    highlight_pt = 10.0 if compact else 11.0
    meta_pad = "3.5pt 7pt" if compact else "5pt 8pt"
    cell_pad = "4pt 7pt" if compact else "5.5pt 9pt"
    outer_cellpad = 10 if compact else 14
    sig_gap_pt = 14 if compact else 22
    amt_col_pt = mm_to_print_pt(38.0)

    receipt_no = html.escape(str(receipt_data["receipt_number"]))
    receipt_date = html.escape(str(receipt_data["receipt_date"]))
    fee_period = html.escape(str(receipt_data["fee_period"]))
    student_name = html.escape(str(receipt_data["student_name"]))
    adm_no = html.escape(str(receipt_data["admission_number"]))
    batch_name = html.escape(str(receipt_data["batch_name"]))
    parent_name = html.escape(str(receipt_data["parent_name"]))
    parent_phone = html.escape(str(receipt_data["parent_phone"]))
    payment_method = html.escape(str(receipt_data["payment_method"]))
    installment_label = html.escape(str(receipt_data["installment_label"]))
    status = html.escape(str(receipt_data["status"]).replace("_", " "))
    notes = html.escape(str(receipt_data.get("payment_notes") or ""))

    base_amt = float(receipt_data["base_amount"])
    discount = float(receipt_data["discount"])
    final_due = float(receipt_data["final_amount_due"])
    receipt_amt = float(receipt_data["receipt_amount"])
    total_paid = float(receipt_data["total_paid"])
    outstanding = float(receipt_data["outstanding_balance"])

    words = html.escape(amount_to_words(receipt_amt, branding.get("currency_symbol") or "₹"))

    discount_row = ""
    if discount > 0:
        discount_row = f"""
        <tr>
            <td style="padding: {cell_pad}; border-bottom: 1px solid #EFE9D2;">Less: Discount / Waiver</td>
            <td align="right" style="padding: {cell_pad}; border-bottom: 1px solid #EFE9D2; color: #15803D;">- {curr}{discount:,.2f}</td>
        </tr>
        """

    installments_html = ""
    payments = receipt_data.get("payments") or []
    if receipt_data.get("is_consolidated") and len(payments) > 1:
        rows_str = ""
        for p in payments:
            rows_str += f"""
            <tr>
                <td style="padding: 2.5pt 6pt; border-bottom: 1px solid #EFE9D2;">{html.escape(p['receipt_number'])}</td>
                <td style="padding: 2.5pt 6pt; border-bottom: 1px solid #EFE9D2;">{html.escape(p['payment_date'])}</td>
                <td style="padding: 2.5pt 6pt; border-bottom: 1px solid #EFE9D2;">{html.escape(p['payment_method'])}</td>
                <td align="right" style="padding: 2.5pt 6pt; border-bottom: 1px solid #EFE9D2;">{curr}{p['amount']:,.2f}</td>
            </tr>
            """
        installments_html = f"""
        <div style="margin-top: 6pt; font-size: {small_pt}pt; font-weight: 700; color: #012D54;">
            Payment Transactions Included:
        </div>
        <table width="100%" cellpadding="0" cellspacing="0" border="0"
               style="margin-top: 2.5pt; border: 1px solid #E9DEBA; border-collapse: collapse; font-size: {small_pt}pt;">
            <tr style="background-color: #F8F6EA; color: #012D54; font-weight: 700;">
                <td style="padding: 3.5pt 6pt; border-bottom: 1px solid #E9DEBA;">Receipt No.</td>
                <td style="padding: 3.5pt 6pt; border-bottom: 1px solid #E9DEBA;">Date</td>
                <td style="padding: 3.5pt 6pt; border-bottom: 1px solid #E9DEBA;">Mode</td>
                <td align="right" style="padding: 3.5pt 6pt; border-bottom: 1px solid #E9DEBA;">Amount</td>
            </tr>
            {rows_str}
        </table>
        """

    notes_html = (
        f'<div style="font-size: {small_pt}pt; color: #374151; margin-top: 5pt;"><b>Remarks:</b> {notes}</div>'
        if notes
        else ""
    )

    copy_badge = (
        f'<div align="right" style="font-size: 8pt; font-weight: 700; color: #615F4B; '
        f'margin-bottom: 3pt;">{html.escape(copy_label)}</div>'
        if copy_label
        else ""
    )

    printed_on = datetime.now().strftime("%d %b %Y, %I:%M %p")
    out_color = "#B91C1C" if outstanding > 0 else "#15803D"

    return f"""
    <table width="100%" cellpadding="{outer_cellpad}" cellspacing="0" border="0"
           style="border: 1px solid #012D54; background-color: #FFFFFF; border-collapse: collapse;">
        <tr>
            <td>
                {copy_badge}
                {letterhead}

                <table width="100%" cellpadding="0" cellspacing="0" border="0"
                       style="background-color: #F8F6EA; border: 1px solid #E9DEBA;
                              border-collapse: collapse; font-size: {body_pt}pt; margin-bottom: 8pt;">
                    <tr>
                        <td width="50%" style="padding: {meta_pad}; border-bottom: 1px solid #EFE9D2; background-color: #F8F6EA;">
                            <b>Receipt No.:</b> {receipt_no}
                        </td>
                        <td width="50%" align="right" style="padding: {meta_pad}; border-bottom: 1px solid #EFE9D2; background-color: #F8F6EA;">
                            <b>Receipt Date:</b> {receipt_date}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: {meta_pad}; border-bottom: 1px solid #EFE9D2; background-color: #F8F6EA;">
                            <b>Student Name:</b> {student_name}
                        </td>
                        <td align="right" style="padding: {meta_pad}; border-bottom: 1px solid #EFE9D2; background-color: #F8F6EA;">
                            <b>Admission No.:</b> {adm_no}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: {meta_pad}; border-bottom: 1px solid #EFE9D2; background-color: #F8F6EA;">
                            <b>Batch:</b> {batch_name}
                        </td>
                        <td align="right" style="padding: {meta_pad}; border-bottom: 1px solid #EFE9D2; background-color: #F8F6EA;">
                            <b>Fee Period:</b> {fee_period}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: {meta_pad}; border-bottom: 1px solid #EFE9D2; background-color: #F8F6EA;">
                            <b>Parent / Guardian:</b> {parent_name}
                        </td>
                        <td align="right" style="padding: {meta_pad}; border-bottom: 1px solid #EFE9D2; background-color: #F8F6EA;">
                            <b>Contact:</b> {parent_phone}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: {meta_pad}; background-color: #F8F6EA;">
                            <b>Payment Mode:</b> {payment_method} ({installment_label})
                        </td>
                        <td align="right" style="padding: {meta_pad}; background-color: #F8F6EA;">
                            <b>Fee Status:</b> {status}
                        </td>
                    </tr>
                </table>

                <table width="100%" cellpadding="0" cellspacing="0" border="0"
                       style="border: 1px solid #D9B85F; border-collapse: collapse; font-size: {body_pt}pt;">
                    <tr style="background-color: #012D54; color: #FEFEFE; font-weight: 700;">
                        <td style="padding: {cell_pad};">Fee Particulars</td>
                        <td width="{amt_col_pt}" align="right" style="padding: {cell_pad};">Amount</td>
                    </tr>
                    <tr>
                        <td style="padding: {cell_pad}; border-bottom: 1px solid #EFE9D2;">
                            Tuition Fee — {fee_period}
                        </td>
                        <td align="right" style="padding: {cell_pad}; border-bottom: 1px solid #EFE9D2;">
                            {curr}{base_amt:,.2f}
                        </td>
                    </tr>
                    {discount_row}
                    <tr>
                        <td style="padding: {cell_pad}; border-bottom: 1px solid #EFE9D2;">Net Fee Payable</td>
                        <td align="right" style="padding: {cell_pad}; border-bottom: 1px solid #EFE9D2;">
                            {curr}{final_due:,.2f}
                        </td>
                    </tr>
                    <tr style="background-color: #F8F6EA; font-weight: 700; color: #012D54; font-size: {highlight_pt}pt;">
                        <td style="padding: {cell_pad}; border-bottom: 1px solid #D9B85F;">
                            Amount Paid (This Receipt)
                        </td>
                        <td align="right" style="padding: {cell_pad}; border-bottom: 1px solid #D9B85F;">
                            {curr}{receipt_amt:,.2f}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: {cell_pad}; border-bottom: 1px solid #EFE9D2;">
                            Total Paid to Date (All Installments)
                        </td>
                        <td align="right" style="padding: {cell_pad}; border-bottom: 1px solid #EFE9D2;">
                            {curr}{total_paid:,.2f}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: {cell_pad}; font-weight: 700; color: {out_color};">
                            Outstanding Balance
                        </td>
                        <td align="right" style="padding: {cell_pad}; font-weight: 700; color: {out_color};">
                            {curr}{outstanding:,.2f}
                        </td>
                    </tr>
                </table>

                {installments_html}

                <table width="100%" cellpadding="0" cellspacing="0" border="0"
                       style="margin-top: 6pt; background-color: #F8F6EA; border: 1px solid #E9DEBA;
                              border-collapse: collapse; font-size: {small_pt}pt;">
                    <tr>
                        <td style="padding: 4.5pt 8pt; background-color: #F8F6EA;">
                            <b>Amount Paid in Words:</b> {words}
                        </td>
                    </tr>
                </table>
                {notes_html}

                <table width="100%" cellpadding="0" cellspacing="0" border="0"
                       style="font-size: {small_pt}pt; color: #374151;">
                    <tr>
                        <td width="60%" valign="bottom" style="color: #615F4B; font-size: 8pt; padding-top: {sig_gap_pt}pt;">
                            Printed on {printed_on}<br/>
                            Computer-generated official fee receipt.
                        </td>
                        <td width="40%" align="right" valign="bottom" style="padding-top: {sig_gap_pt}pt;">
                            <table width="75%" cellpadding="0" cellspacing="0" border="0" align="right">
                                <tr>
                                    <td align="center" style="border-top: 1px solid #012D54; padding-top: 3pt;
                                                              font-weight: 700; font-size: {small_pt}pt; color: #012D54;">
                                        Authorized Signatory
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
    """


def render_fee_receipt_html(
    receipt_data: dict[str, Any],
    branding: dict[str, Any],
    *,
    dual_copy: bool = False,
    logo_data_uri: str | None = None,
) -> str:
    """Renders complete A4-proportioned printable HTML document for a fee payment receipt."""
    if dual_copy:
        student_copy = _render_single_receipt_block(
            receipt_data,
            branding,
            copy_label="STUDENT / PARENT COPY",
            logo_data_uri=logo_data_uri,
            compact=True,
        )
        office_copy = _render_single_receipt_block(
            receipt_data,
            branding,
            copy_label="OFFICE COPY",
            logo_data_uri=logo_data_uri,
            compact=True,
        )
        body = f"""
        {student_copy}
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 10pt 0;">
            <tr>
                <td width="14" valign="middle" style="color: #615F4B; font-size: 9pt;">&#9986;</td>
                <td valign="middle" style="border-bottom: 1px dashed #9CA3AF; font-size: 3pt;">&nbsp;</td>
            </tr>
        </table>
        {office_copy}
        """
    else:
        body = _render_single_receipt_block(
            receipt_data,
            branding,
            copy_label="",
            logo_data_uri=logo_data_uri,
            compact=False,
        )

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8" /></head>
<body style="font-family: Arial, Helvetica, sans-serif; font-size: 10pt; color: #1F2937; margin: 0; padding: 0;">
{body}
</body>
</html>"""


def get_admission_form_config(session: Session) -> dict[str, Any]:
    """Loads persisted admission form template settings merged with defaults."""
    ensure_messaging_seed_data(session)
    cfg = get_messaging_config(session)
    raw = (cfg.get("admission_form_config") or "").strip()

    merged: dict[str, Any] = json.loads(json.dumps(DEFAULT_ADMISSION_FORM_CONFIG))
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                for key, val in parsed.items():
                    if key in merged:
                        merged[key] = val
        except Exception:
            pass
    return merged


def save_admission_form_config(session: Session, config: dict[str, Any]) -> dict[str, Any]:
    """Validates and persists admission form customization settings."""
    normalized: dict[str, Any] = json.loads(json.dumps(DEFAULT_ADMISSION_FORM_CONFIG))
    for key in normalized:
        if key in config:
            normalized[key] = config[key]

    normalized["form_title"] = str(normalized.get("form_title") or "STUDENT ADMISSION FORM").strip() or "STUDENT ADMISSION FORM"
    normalized["form_subtitle"] = str(normalized.get("form_subtitle") or "").strip()
    normalized["photo_box_label"] = str(normalized.get("photo_box_label") or "Affix Passport Size Photo").strip()
    normalized["show_logo"] = bool(normalized.get("show_logo", True))
    normalized["show_photo_box"] = bool(normalized.get("show_photo_box", True))
    normalized["show_office_use_section"] = bool(normalized.get("show_office_use_section", True))
    normalized["use_custom_html"] = bool(normalized.get("use_custom_html", False))
    normalized["custom_html_template"] = str(normalized.get("custom_html_template") or "")

    valid_keys = {item[0] for item in STANDARD_ADMISSION_FIELDS}
    inc = normalized.get("included_fields")
    if isinstance(inc, list):
        normalized["included_fields"] = [k for k in inc if k in valid_keys]
    else:
        normalized["included_fields"] = [item[0] for item in STANDARD_ADMISSION_FIELDS]

    cust = normalized.get("custom_fields")
    if isinstance(cust, list):
        normalized["custom_fields"] = [str(f).strip() for f in cust if str(f).strip()]
    else:
        normalized["custom_fields"] = []

    update_messaging_config(
        session,
        {"admission_form_config": json.dumps(normalized, ensure_ascii=False)},
    )
    return normalized


def reset_admission_form_config(session: Session) -> dict[str, Any]:
    """Resets the admission form template back to factory defaults."""
    return save_admission_form_config(session, DEFAULT_ADMISSION_FORM_CONFIG)


def build_admission_form_student_data(
    session: Session,
    student_id: int | None = None,
    *,
    currency_symbol: str = "₹",
) -> dict[str, str]:
    """
    Collects field values for pre-filling an admission form.
    Returns empty strings for all keys when student_id is None (blank form mode).
    """
    data: dict[str, str] = {key: "" for key, _, _ in STANDARD_ADMISSION_FIELDS}
    if student_id is None:
        return data

    stmt = (
        select(Student)
        .options(joinedload(Student.parent), joinedload(Student.batch))
        .where(Student.id == student_id)
    )
    student = session.scalars(stmt).first()
    if student is None:
        return data

    full_name = f"{student.first_name} {student.last_name or ''}".strip()
    dob = student.date_of_birth.strftime("%d/%m/%Y") if student.date_of_birth else ""
    adm_date = student.admission_date.strftime("%d/%m/%Y") if student.admission_date else ""
    batch_name = student.batch.name if student.batch else ""

    fee_val = student.monthly_fee
    if fee_val is None and student.batch and student.batch.monthly_fee is not None:
        fee_val = student.batch.monthly_fee
    fee_str = f"{currency_symbol}{float(fee_val):,.2f}" if fee_val is not None else ""

    parent_name = student.parent.name if student.parent else ""
    parent_phone = (student.parent.phone or "") if student.parent else ""
    whatsapp = (student.parent.whatsapp_number or "") if student.parent else ""

    data.update({
        "admission_number": student.admission_number or "",
        "student_name": full_name,
        "date_of_birth": dob,
        "school_name": student.school_name or "",
        "batch_name": batch_name,
        "admission_date": adm_date,
        "monthly_fee": fee_str,
        "parent_name": parent_name,
        "parent_phone": parent_phone,
        "whatsapp_number": whatsapp,
        "notes": student.notes or "",
    })
    return data


def _format_form_value(val: str, *, blank_chars: int = 26) -> str:
    clean = (val or "").strip()
    if clean:
        return html.escape(clean)
    return f'<span style="color: #9CA3AF;">{"_" * blank_chars}</span>'


def _render_fields_table(
    fields: list[tuple[str, str]],
    *,
    label_width_pct: int = 34,
    blank_chars: int = 26,
) -> str:
    if not fields:
        return ""
    val_width_pct = 100 - label_width_pct
    rows = ""
    for label, val in fields:
        rows += f"""
        <tr>
            <td width="{label_width_pct}%" style="padding: 4pt 7pt; background-color: #F8F6EA;
                                   border: 1px solid #E9DEBA; font-weight: 700; color: #012D54;">
                {html.escape(label)}
            </td>
            <td width="{val_width_pct}%" style="padding: 4pt 7pt; border: 1px solid #E9DEBA; color: #1F2937;">
                {_format_form_value(val, blank_chars=blank_chars)}
            </td>
        </tr>
        """
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="border-collapse: collapse; border: 1px solid #E9DEBA; font-size: 9.5pt; margin-bottom: 6pt;">'
        f"{rows}</table>"
    )


def _render_passport_photo_svg_uri(photo_label: str) -> str:
    """
    Generates an inline SVG data URI sized strictly to standard passport photo
    dimensions (35 mm × 45 mm) with clean border, inner frame, and caption.
    """
    clean_label = (photo_label or "Affix Recent Passport Size Photo").strip()
    wrapped = textwrap.wrap(clean_label, width=16)[:3] or ["Passport Size", "Photo"]

    start_y = 19.0 - (len(wrapped) - 1) * 2.1
    label_tspans = ""
    for idx, line in enumerate(wrapped):
        y_pos = start_y + idx * 4.2
        label_tspans += (
            f'<text x="17.5" y="{y_pos:.1f}" font-family="Arial, Helvetica, sans-serif" '
            f'font-size="2.8" font-weight="bold" fill="#012D54" text-anchor="middle">'
            f"{html.escape(line)}</text>"
        )

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{mm_to_print_pt(PASSPORT_PHOTO_WIDTH_MM)}" '
        f'height="{mm_to_print_pt(PASSPORT_PHOTO_HEIGHT_MM)}" '
        f'viewBox="0 0 {PASSPORT_PHOTO_WIDTH_MM:g} {PASSPORT_PHOTO_HEIGHT_MM:g}">'
        '<rect x="0.35" y="0.35" width="34.3" height="44.3" '
        'fill="#F8F6EA" stroke="#012D54" stroke-width="0.5" stroke-dasharray="1.8,1.2"/>'
        '<rect x="1.8" y="1.8" width="31.4" height="41.4" '
        'fill="none" stroke="#D9B85F" stroke-width="0.25"/>'
        f"{label_tspans}"
        '<text x="17.5" y="34.5" font-family="Arial, Helvetica, sans-serif" '
        'font-size="2.4" fill="#615F4B" text-anchor="middle">35 mm × 45 mm</text>'
        '<text x="17.5" y="38.2" font-family="Arial, Helvetica, sans-serif" '
        'font-size="2.1" fill="#615F4B" text-anchor="middle">(Passport Standard)</text>'
        "</svg>"
    )
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _render_section_heading(title_text: str) -> str:
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="margin-top: 6pt; margin-bottom: 4pt;">'
        '<tr><td style="padding-bottom: 2pt; border-bottom: 1px solid #D9B85F; '
        'font-size: 10pt; font-weight: 700; color: #012D54;">'
        f"{title_text}"
        "</td></tr></table>"
    )


def render_admission_form_html(
    form_cfg: dict[str, Any],
    student_data: dict[str, str],
    branding: dict[str, Any],
    *,
    logo_data_uri: str | None = None,
) -> str:
    """
    Renders a printable, user-customizable admission form HTML document sized for ISO A4.
    Supports either structured builder customization or a user-saved custom HTML template.
    """
    if form_cfg.get("use_custom_html") and (form_cfg.get("custom_html_template") or "").strip():
        custom_html = str(form_cfg["custom_html_template"])
        replacements = {
            "coaching_name": html.escape(branding.get("coaching_name") or "TAMS"),
            "app_name": html.escape(branding.get("app_name") or "TAMS"),
            "academic_session": html.escape(branding.get("academic_session") or ""),
            "coaching_phone": html.escape(branding.get("coaching_phone") or ""),
            "coaching_email": html.escape(branding.get("coaching_email") or ""),
            "coaching_address": html.escape(branding.get("coaching_address") or ""),
        }
        for key, _, _ in STANDARD_ADMISSION_FIELDS:
            val = (student_data.get(key) or "").strip()
            replacements[key] = html.escape(val) if val else "____________________"
        for k, v in replacements.items():
            custom_html = custom_html.replace("{{" + k + "}}", v)
        return custom_html

    form_title = html.escape(form_cfg.get("form_title") or "STUDENT ADMISSION FORM")
    form_subtitle = html.escape(form_cfg.get("form_subtitle") or "")
    show_logo = bool(form_cfg.get("show_logo", True))
    show_photo = bool(form_cfg.get("show_photo_box", True))
    photo_label = form_cfg.get("photo_box_label") or "Affix Recent Passport Size Photo"
    show_office_use = bool(form_cfg.get("show_office_use_section", True))

    included = set(form_cfg.get("included_fields") or [])
    student_fields: list[tuple[str, str]] = []
    parent_fields: list[tuple[str, str]] = []
    for key, label, group in STANDARD_ADMISSION_FIELDS:
        if key in included:
            pair = (label, student_data.get(key, ""))
            if group == "parent":
                parent_fields.append(pair)
            else:
                student_fields.append(pair)

    custom_fields = [
        (f_label, student_data.get(f"custom:{f_label}", ""))
        for f_label in (form_cfg.get("custom_fields") or [])
        if str(f_label).strip()
    ]

    letterhead = _render_letterhead_html(
        branding,
        document_badge="ADMISSION FORM",
        logo_data_uri=logo_data_uri,
        show_logo=show_logo,
        compact=False,
    )

    subtitle_html = (
        f'<div style="font-size: 8.5pt; color: #615F4B; margin-top: 1.5pt;">{form_subtitle}</div>'
        if form_subtitle
        else ""
    )

    # Standard 35 mm × 45 mm Passport Photo cell
    photo_cell = ""
    if show_photo:
        photo_svg_uri = _render_passport_photo_svg_uri(photo_label)
        photo_w_pt = mm_to_print_pt(PASSPORT_PHOTO_WIDTH_MM)
        photo_h_pt = mm_to_print_pt(PASSPORT_PHOTO_HEIGHT_MM)
        photo_col_pt = mm_to_print_pt(PASSPORT_PHOTO_WIDTH_MM + 4.0)
        photo_cell = (
            f'<td width="{photo_col_pt}" valign="top" align="right" style="padding-left: 8pt;">'
            f'<img src="{photo_svg_uri}" width="{photo_w_pt}" height="{photo_h_pt}" />'
            f"</td>"
        )

    # Align top 5 student rows cleanly beside the 45 mm tall passport photo box
    rows_beside_photo = 5
    top_student_fields = (
        student_fields[:rows_beside_photo]
        if (show_photo and len(student_fields) > rows_beside_photo)
        else student_fields
    )
    rest_student_fields = (
        student_fields[rows_beside_photo:]
        if (show_photo and len(student_fields) > rows_beside_photo)
        else []
    )

    top_section = f"""
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           style="background-color: #F8F6EA; border: 1px solid #D9B85F;
                  border-collapse: collapse; margin-bottom: 8pt;">
        <tr>
            <td align="center" style="padding: 5.5pt 10pt; background-color: #F8F6EA;">
                <div style="font-size: 12.5pt; font-weight: 700; color: #012D54;">
                    {form_title}
                </div>
                {subtitle_html}
            </td>
        </tr>
    </table>

    {_render_section_heading("1. Student &amp; Academic Details")}
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
            <td valign="top">
                {_render_fields_table(top_student_fields, label_width_pct=40 if show_photo else 34, blank_chars=18 if show_photo else 28)}
            </td>
            {photo_cell}
        </tr>
    </table>
    {_render_fields_table(rest_student_fields, label_width_pct=34, blank_chars=28)}
    """

    parent_section = ""
    if parent_fields:
        parent_section = f"""
        {_render_section_heading("2. Parent / Guardian Contact Details")}
        {_render_fields_table(parent_fields, label_width_pct=34, blank_chars=28)}
        """

    custom_section = ""
    if custom_fields:
        sec_num = 3 if parent_fields else 2
        custom_section = f"""
        {_render_section_heading(f"{sec_num}. Additional Details")}
        {_render_fields_table(custom_fields, label_width_pct=34, blank_chars=28)}
        """

    terms_raw = (form_cfg.get("terms_and_conditions") or "").strip()
    declaration_raw = (form_cfg.get("declaration_text") or "").strip()
    terms_html = ""
    if terms_raw or declaration_raw:
        terms_body = "<br/>".join(
            html.escape(line) for line in terms_raw.splitlines() if line.strip()
        )
        decl_html = (
            '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top: 5pt;">'
            '<tr><td style="border-top: 1px solid #E9DEBA; padding-top: 4pt; font-style: italic; font-size: 8.5pt;">'
            f"<b>Declaration:</b> {html.escape(declaration_raw)}"
            "</td></tr></table>"
            if declaration_raw
            else ""
        )
        terms_html = f"""
        <table width="100%" cellpadding="0" cellspacing="0" border="0"
               style="border: 1px solid #E9DEBA; background-color: #F8F6EA;
                      border-collapse: collapse; font-size: 8.5pt; margin-top: 6pt;">
            <tr>
                <td style="padding: 6pt 9pt; line-height: 135%; background-color: #F8F6EA;">
                    <div style="font-weight: 700; font-size: 9pt; color: #012D54; margin-bottom: 3pt;">
                        Rules, Terms &amp; Declaration
                    </div>
                    <div>{terms_body}</div>
                    {decl_html}
                </td>
            </tr>
        </table>
        """

    student_sig = html.escape(form_cfg.get("student_sig_label") or "Student Signature")
    parent_sig = html.escape(form_cfg.get("parent_sig_label") or "Parent / Guardian Signature")
    auth_sig = html.escape(form_cfg.get("authority_sig_label") or "Authorized Signatory")

    def _sig_cell(label_txt: str) -> str:
        return (
            '<td width="33%" align="center" valign="bottom" style="padding: 0 8pt 4pt 8pt;">'
            '<table width="88%" cellpadding="0" cellspacing="0" border="0" align="center">'
            '<tr><td align="center" style="border-top: 1px solid #012D54; padding-top: 3pt; '
            'font-size: 9pt; font-weight: 700; color: #012D54;">'
            f"{label_txt}</td></tr></table></td>"
        )

    signatures_html = f"""
    <div style="font-size: 16pt; line-height: 16pt;">&nbsp;</div>
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
            {_sig_cell(student_sig)}
            {_sig_cell(parent_sig)}
            {_sig_cell(auth_sig)}
        </tr>
    </table>
    """

    office_html = ""
    if show_office_use:
        office_html = """
        <div style="font-size: 6pt; line-height: 6pt;">&nbsp;</div>
        <table width="100%" cellpadding="0" cellspacing="0" border="0"
               style="border: 1px solid #012D54; border-collapse: collapse; font-size: 9pt;">
            <tr style="background-color: #012D54; color: #FEFEFE; font-weight: 700;">
                <td colspan="2" style="padding: 4pt 8pt;">FOR OFFICE USE ONLY</td>
            </tr>
            <tr>
                <td width="50%" style="padding: 5pt 8pt; border-bottom: 1px solid #E9DEBA; border-right: 1px solid #E9DEBA;">
                    Registration Fee Paid: __________________
                </td>
                <td width="50%" style="padding: 5pt 8pt; border-bottom: 1px solid #E9DEBA;">
                    Receipt No. &amp; Date: ____________________
                </td>
            </tr>
            <tr>
                <td style="padding: 5pt 8pt; border-right: 1px solid #E9DEBA;">
                    Batch Assigned: ______________________
                </td>
                <td style="padding: 5pt 8pt;">
                    Verified By: _________________________
                </td>
            </tr>
        </table>
        """

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8" /></head>
<body style="font-family: Arial, Helvetica, sans-serif; font-size: 9.5pt; color: #1F2937; margin: 0; padding: 0;">
    {letterhead}
    {top_section}
    {parent_section}
    {custom_section}
    {terms_html}
    {signatures_html}
    {office_html}
</body>
</html>"""
