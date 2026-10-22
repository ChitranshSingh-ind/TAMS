"""
Messaging Service Layer for TAMS.
Coordinates message composition, recipient deduplication, template variable interpolation,
persistent queue lifecycle, claim/lease locking, exponential backoff retries,
event-driven automation rules, and analytics reporting.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session, joinedload

from app.database.models.batch import Batch
from app.database.models.parent import Parent
from app.database.models.student import Student
from app.database.models.message import (
    Message,
    MessageTemplate,
    MessagingConfig,
    NotificationRule,
    RecipientPreference,
)
from app.services.whatsapp_provider import (
    DEFAULT_GRAPH_API_VERSION,
    WhatsAppCloudProvider,
    WhatsAppConfig,
    get_access_token,
    mask_phone_number,
    normalize_phone_number,
)

logger = logging.getLogger("TAMS.MessagingService")


# ─────────────────────────────────────────────────────────────────────────────
# 1. DEFAULT SEED DATA & CONFIGURATION MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_CONFIGS: dict[str, str] = {
    "whatsapp_environment": "PRODUCTION",  # "PRODUCTION" or "DEVELOPMENT"
    "whatsapp_phone_number_id": "1480753541781147",
    "whatsapp_waba_id": "970600618872001",
    "whatsapp_api_version": "v26.0",
    "retry_limit": "3",
    "retry_backoff_base": "60",  # 60s -> 120s -> 240s
    "helper_polling_interval": "15",
    "queue_enabled": "true",
    "quiet_hours_enabled": "false",
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "07:00",
    "max_bulk_batch_size": "100",
    # General & Coaching Profile
    "coaching_name": "TAMS Coaching Academy",
    "coaching_tagline": "Excellence in Education",
    "coaching_phone": "",
    "coaching_email": "",
    "coaching_address": "",
    "academic_session": "2026–2027",
    # Operational & Academic Defaults
    "currency_symbol": "₹",
    "default_fee_due_day": "5",
    "attendance_warning_threshold": "75",
    "pass_percentage_threshold": "40",
    # UI & Data Privacy
    "ui_compact_tables": "false",
    "ui_confirm_deletions": "true",
    "ui_mask_phone_numbers": "false",
    # WhatsApp & Automation enhancements
    "default_country_code": "+91",
    "emergency_automation_pause": "false",
    "dry_run_mode": "false",
    "max_daily_messages_per_student": "3",
    # Backup & Maintenance
    "max_backup_retention": "10",
    "auto_backup_on_exit": "false",
}


DEFAULT_TEMPLATES: list[dict[str, Any]] = [
    {
        "name": "hello_world",
        "meta_template_name": "hello_world",
        "category": "UTILITY",
        "language": "en_US",
        "body": "Welcome and congratulations! This message confirms your WhatsApp connection with TAMS.",
        "parameters_json": "[]",
        "is_active": True,
        "meta_status": "APPROVED",
        "associated_trigger": "MANUAL",
    },
    {
        "name": "fee_due_reminder",
        "meta_template_name": "fee_due_reminder",
        "category": "UTILITY",
        "language": "en",
        "body": "Dear Parent, reminder that tuition fee of ₹{{amount}} for {{student_name}} (Batch: {{batch_name}}) is due on {{due_date}}. Thank you, Vishal Sir's Coaching.",
        "parameters_json": '["amount", "student_name", "batch_name", "due_date"]',
        "is_active": True,
        "meta_status": "LOCAL_ONLY",
        "associated_trigger": "FEE_DUE",
    },
    {
        "name": "fee_overdue_reminder",
        "meta_template_name": "fee_overdue_reminder",
        "category": "UTILITY",
        "language": "en",
        "body": "Dear Parent, tuition fee of ₹{{amount}} for {{student_name}} is overdue since {{due_date}}. Kindly clear the outstanding fee at your earliest convenience. Thank you, Vishal Sir's Coaching",
        "parameters_json": '["amount", "student_name", "due_date"]',
        "is_active": True,
        "meta_status": "LOCAL_ONLY",
        "associated_trigger": "FEE_OVERDUE",
    },
    {
        "name": "payment_receipt",
        "meta_template_name": "payment_receipt",
        "category": "UTILITY",
        "language": "en",
        "body": "Dear Parent, payment of ₹{{amount}} for {{student_name}} has been received successfully via {{payment_mode}}. Receipt No: {{receipt_no}}. Thank you, Vishal Sir's Coaching.",
        "parameters_json": '["amount", "student_name", "payment_mode", "receipt_no"]',
        "is_active": True,
        "meta_status": "LOCAL_ONLY",
        "associated_trigger": "PAYMENT_RECEIPT",
    },
    {
        "name": "absence_alert",
        "meta_template_name": "absence_alert",
        "category": "UTILITY",
        "language": "en",
        "body": "Dear Parent, {{student_name}} was marked absent today ({{date}}) in {{batch_name}}. If this absence was unintended, please contact coaching administration.",
        "parameters_json": '["student_name", "date", "batch_name"]',
        "is_active": True,
        "meta_status": "LOCAL_ONLY",
        "associated_trigger": "ABSENCE",
    },
    {
        "name": "repeated_absence_alert",
        "meta_template_name": "repeated_absence_alert",
        "category": "UTILITY",
        "language": "en",
        "body": "Dear Parent, {{student_name}} has been absent for {{consecutive_days}} consecutive classes in {{batch_name}}. Regular attendance is crucial for academic results. Please contact us.",
        "parameters_json": '["student_name", "consecutive_days", "batch_name"]',
        "is_active": True,
        "meta_status": "LOCAL_ONLY",
        "associated_trigger": "CONSECUTIVE_ABSENCE",
    },
    {
        "name": "test_result_notification",
        "meta_template_name": "test_result_notification",
        "category": "UTILITY",
        "language": "en",
        "body": "Dear Parent, {{student_name}} scored {{marks}}/{{max_marks}} ({{percentage}}%) in {{test_name}} on {{test_date}}. Batch Average: {{batch_avg}}%. Vishal Sir's Coaching.\n*If your child has scored less marks then average then contact us*.",
        "parameters_json": '["student_name", "marks", "max_marks", "percentage", "test_name", "test_date", "batch_avg"]',
        "is_active": True,
        "meta_status": "LOCAL_ONLY",
        "associated_trigger": "TEST_RESULT",
    },
    {
        "name": "general_announcement",
        "meta_template_name": "general_announcement",
        "category": "UTILITY",
        "language": "en",
        "body": "Important Announcement from TAMS: {{announcement_text}}. Batch: {{batch_name}} ,Thanks.",
        "parameters_json": '["announcement_text", "batch_name"]',
        "is_active": True,
        "meta_status": "LOCAL_ONLY",
        "associated_trigger": "MANUAL",
    },
]

DEFAULT_NOTIFICATION_RULES: list[dict[str, Any]] = [
    {
        "name": "Fee Due Reminder (3 Days Prior)",
        "trigger_event": "FEE_DUE",
        "is_enabled": False,  # DISABLED BY DEFAULT
        "days_offset": -3,
        "cooldown_days": 3,
        "template_name": "fee_due_reminder",
    },
    {
        "name": "Overdue Fee Notice (1 Day Overdue)",
        "trigger_event": "FEE_OVERDUE",
        "is_enabled": False,  # DISABLED BY DEFAULT
        "days_offset": 1,
        "cooldown_days": 5,
        "template_name": "fee_overdue_reminder",
    },
    {
        "name": "Fee Payment Acknowledgement",
        "trigger_event": "PAYMENT_RECEIPT",
        "is_enabled": False,  # DISABLED BY DEFAULT
        "days_offset": 0,
        "cooldown_days": 1,
        "template_name": "payment_receipt",
    },
    {
        "name": "Daily Student Absence Alert",
        "trigger_event": "ABSENCE",
        "is_enabled": False,  # DISABLED BY DEFAULT
        "days_offset": 0,
        "cooldown_days": 1,
        "template_name": "absence_alert",
    },
    {
        "name": "Repeated Absence Flag (2+ Consecutive)",
        "trigger_event": "CONSECUTIVE_ABSENCE",
        "is_enabled": False,  # DISABLED BY DEFAULT
        "min_consecutive_days": 2,
        "cooldown_days": 3,
        "template_name": "repeated_absence_alert",
    },
    {
        "name": "Test Results Release Notice",
        "trigger_event": "TEST_RESULT",
        "is_enabled": False,  # DISABLED BY DEFAULT
        "days_offset": 0,
        "cooldown_days": 0,
        "template_name": "test_result_notification",
    },
]


def ensure_messaging_seed_data(session: Session) -> None:
    """Initializes default configurations, templates, and automation rules if not present."""
    # 1. Configs
    existing_configs = {c.key: c for c in session.scalars(select(MessagingConfig)).all()}
    for key, val in DEFAULT_CONFIGS.items():
        if key not in existing_configs:
            session.add(MessagingConfig(key=key, value=val))
        elif key in ("whatsapp_phone_number_id", "whatsapp_waba_id", "whatsapp_api_version") and not existing_configs[key].value:
            existing_configs[key].value = val

    # 2. Templates
    existing_tmpl = {t.name: t for t in session.scalars(select(MessageTemplate)).all()}
    for tmpl in DEFAULT_TEMPLATES:
        if tmpl["name"] not in existing_tmpl:
            session.add(MessageTemplate(
                name=tmpl["name"],
                meta_template_name=tmpl["meta_template_name"],
                category=tmpl["category"],
                language=tmpl["language"],
                body=tmpl["body"],
                parameters_json=tmpl["parameters_json"],
                is_active=tmpl["is_active"],
                meta_status=tmpl["meta_status"],
                associated_trigger=tmpl["associated_trigger"],
            ))
        else:
            # Sync updated default template attributes into database
            curr = existing_tmpl[tmpl["name"]]
            curr.body = tmpl["body"]
            curr.meta_template_name = tmpl["meta_template_name"]
            curr.category = tmpl["category"]
            curr.parameters_json = tmpl["parameters_json"]
            curr.associated_trigger = tmpl["associated_trigger"]

    session.flush()

    # 3. Notification Rules
    tmpl_map = {t.name: t.id for t in session.scalars(select(MessageTemplate)).all()}
    existing_rules = {r.name: r for r in session.scalars(select(NotificationRule)).all()}
    for r in DEFAULT_NOTIFICATION_RULES:
        if r["name"] not in existing_rules:
            session.add(NotificationRule(
                name=r["name"],
                trigger_event=r["trigger_event"],
                is_enabled=r["is_enabled"],
                days_offset=r.get("days_offset", 0),
                cooldown_days=r.get("cooldown_days", 0 if r["trigger_event"] == "TEST_RESULT" else 2),
                min_consecutive_days=r.get("min_consecutive_days", 2),
                template_id=tmpl_map.get(r["template_name"]),
            ))
        else:
            # Sync rule parameters like cooldown_days for TEST_RESULT
            curr_rule = existing_rules[r["name"]]
            if r["trigger_event"] == "TEST_RESULT":
                curr_rule.cooldown_days = 0

    session.commit()


def get_messaging_config(session: Session) -> dict[str, str]:
    """Returns all key-value messaging configuration pairs with defaults merged."""
    configs = dict(DEFAULT_CONFIGS)
    rows = session.scalars(select(MessagingConfig)).all()
    for r in rows:
        configs[r.key] = r.value
    return configs


def update_messaging_config(session: Session, new_configs: dict[str, str]) -> None:
    """Updates key-value messaging configs."""
    for key, val in new_configs.items():
        existing = session.scalar(select(MessagingConfig).where(MessagingConfig.key == key))
        if existing:
            existing.value = str(val)
        else:
            session.add(MessagingConfig(key=key, value=str(val)))
    session.commit()


def get_whatsapp_provider_client(session: Session) -> WhatsAppCloudProvider:
    """Builds and returns a configured WhatsAppCloudProvider instance."""
    cfg = get_messaging_config(session)
    token = get_access_token() or ""
    provider_config = WhatsAppConfig(
        environment=cfg.get("whatsapp_environment", "DEVELOPMENT"),
        phone_number_id=cfg.get("whatsapp_phone_number_id", ""),
        waba_id=cfg.get("whatsapp_waba_id", ""),
        api_version=cfg.get("whatsapp_api_version", DEFAULT_GRAPH_API_VERSION),
        access_token=token,
    )
    return WhatsAppCloudProvider(provider_config)


# ─────────────────────────────────────────────────────────────────────────────
# 2. RECIPIENT RESOLUTION, DEDUPLICATION & CONSENT
# ─────────────────────────────────────────────────────────────────────────────

def get_eligible_recipients(
    session: Session,
    *,
    target_type: str,  # "STUDENT", "BATCH", "CUSTOM_PHONE", "ALL"
    target_ids: list[int] | None = None,
    custom_phone: str | None = None,
    custom_name: str | None = None,
) -> dict[str, Any]:
    """
    Resolves eligible recipients from students/parents/batches.
    Enforces deduplication (when a parent is associated with multiple students),
    checks opt-out status, and validates phone numbers.
    Returns:
    {
        'eligible': [{'phone': '+91...', 'name': '...', 'student_id': ..., 'student_name': ..., 'batch_name': ...}],
        'skipped': [{'phone': '...', 'name': '...', 'reason': '...'}],
        'total_candidates': int,
        'eligible_count': int,
        'skipped_count': int,
    }
    """
    candidates: list[dict[str, Any]] = []

    if target_type == "CUSTOM_PHONE":
        candidates.append({
            "raw_phone": custom_phone or "",
            "recipient_name": custom_name or "Custom Contact",
            "student_id": None,
            "parent_id": None,
            "batch_id": None,
            "student_name": "—",
            "batch_name": "Direct Contact",
        })

    elif target_type in ("STUDENT", "BATCH", "ALL"):
        query = (
            select(Student)
            .options(joinedload(Student.parent), joinedload(Student.batch))
            .where(Student.status == "ACTIVE")
        )
        if target_type == "STUDENT" and target_ids:
            query = query.where(Student.id.in_(target_ids))
        elif target_type == "BATCH" and target_ids:
            query = query.where(Student.batch_id.in_(target_ids))

        students = list(session.scalars(query).all())

        for s in students:
            parent = s.parent
            # Prioritize parent WhatsApp number, fallback to parent primary phone
            raw_phone = parent.whatsapp_number if (parent and parent.whatsapp_number) else (
                parent.phone if (parent and parent.phone) else None
            )
            p_name = parent.name if (parent and parent.name) else f"Parent of {s.first_name}"
            b = s.batch

            candidates.append({
                "raw_phone": raw_phone,
                "recipient_name": p_name,
                "student_id": s.id,
                "parent_id": parent.id if parent else None,
                "batch_id": s.batch_id,
                "student_name": f"{s.first_name} {s.last_name or ''}".strip(),
                "batch_name": b.name if b else "—",
            })

    # Fetch opt-out records
    opted_out_phones = set(session.scalars(
        select(RecipientPreference.phone_number).where(RecipientPreference.is_opted_out == True)
    ).all())

    eligible: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    seen_phones: dict[str, dict[str, Any]] = {}

    for cand in candidates:
        raw_phone = cand.get("raw_phone")
        if not raw_phone:
            skipped.append({
                "name": cand["recipient_name"],
                "student_name": cand["student_name"],
                "phone": "—",
                "reason": "Missing contact phone number in student/parent profile",
            })
            continue

        is_valid, e164_phone, error_reason = normalize_phone_number(raw_phone)
        if not is_valid:
            skipped.append({
                "name": cand["recipient_name"],
                "student_name": cand["student_name"],
                "phone": raw_phone,
                "reason": f"Invalid phone format: {error_reason}",
            })
            continue

        if e164_phone in opted_out_phones:
            skipped.append({
                "name": cand["recipient_name"],
                "student_name": cand["student_name"],
                "phone": mask_phone_number(e164_phone),
                "reason": "Recipient has opted out of coaching notifications",
            })
            continue

        # Deduplication logic: If parent was already added (e.g. multiple children selected)
        if e164_phone in seen_phones:
            prior = seen_phones[e164_phone]
            # Merge student names to inform teacher
            prior["student_name"] = f"{prior['student_name']} & {cand['student_name']}"
            continue

        record = {
            "phone": e164_phone,
            "masked_phone": mask_phone_number(e164_phone),
            "recipient_name": cand["recipient_name"],
            "student_id": cand["student_id"],
            "parent_id": cand["parent_id"],
            "batch_id": cand["batch_id"],
            "student_name": cand["student_name"],
            "batch_name": cand["batch_name"],
        }
        seen_phones[e164_phone] = record
        eligible.append(record)

    return {
        "eligible": eligible,
        "skipped": skipped,
        "total_candidates": len(candidates),
        "eligible_count": len(eligible),
        "skipped_count": len(skipped),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. TEMPLATE INTERPOLATION & QUEUE OPERATIONS
# ─────────────────────────────────────────────────────────────────────────────

def is_date_key(key: str) -> bool:
    """Checks whether a template variable key represents a date field."""
    k = key.lower().strip()
    return (
        k == "date"
        or k.endswith("_date")
        or k.startswith("date_")
        or "_date_" in k
        or k in {"test_date", "due_date", "attendance_date", "birth_date", "admission_date", "payment_date"}
    )


def normalize_date_variable(val: Any) -> str:
    """
    Normalizes a date/datetime object or recognizable date string to ISO YYYY-MM-DD.
    Complies with Meta WhatsApp Cloud API template variable specifications.
    """
    if val is None:
        return ""
    if isinstance(val, (date, datetime)):
        return val.strftime("%Y-%m-%d")
    val_str = str(val).strip()
    if not val_str:
        return ""
    if re.match(r"^\d{4}-\d{2}-\d{2}$", val_str):
        return val_str
    for fmt in (
        "%d %b %Y",    # 21 Oct 2026
        "%d %B %Y",    # 21 October 2026
        "%d/%m/%Y",    # 21/10/2026
        "%d-%m-%Y",    # 21-10-2026
        "%Y/%m/%d",    # 2026/10/21
        "%Y.%m.%d",    # 2026.10.21
        "%d.%m.%Y",    # 21.10.2026
        "%m/%d/%Y",    # 10/21/2026
    ):
        try:
            return datetime.strptime(val_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return val_str


def get_default_parameter_fallback(key: str, recipient_name: str | None = None) -> str:
    """
    Returns a safe non-empty fallback value for a template variable.
    Prevents Meta WhatsApp API Error 131008 (Parameter of type text is missing text value).
    """
    k = key.lower().strip()
    if k == "student_name":
        return recipient_name or "Student"
    elif k == "batch_name":
        return "General"
    elif is_date_key(k):
        return date.today().strftime("%Y-%m-%d")
    elif k == "amount":
        return "0"
    elif k == "announcement_text":
        return "Important Notice"
    elif k == "payment_mode":
        return "Cash"
    elif k == "receipt_no":
        return "REC-001"
    elif k in ("marks", "max_marks", "percentage", "batch_avg"):
        return "0"
    return "—"


def render_template_text(template_body: str, context: dict[str, Any]) -> str:
    """
    Renders template text by replacing {{key}} tokens with context values.
    Supports both named placeholders like {{student_name}} and positional {{1}}.
    Formats all date variables as YYYY-MM-DD to comply with Meta WhatsApp API requirements.
    """
    rendered = template_body
    for k, v in context.items():
        if isinstance(v, (date, datetime)):
            val_str = v.strftime("%Y-%m-%d")
        elif is_date_key(k):
            val_str = normalize_date_variable(v)
        else:
            val_str = str(v) if v is not None else ""
        placeholder_named = f"{{{{{k}}}}}"
        rendered = rendered.replace(placeholder_named, val_str)

    # Also handle numeric parameters if given as param_1, param_2
    for i in range(1, 10):
        if f"param_{i}" in context:
            p_val = context[f"param_{i}"]
            if isinstance(p_val, (date, datetime)):
                p_val_str = p_val.strftime("%Y-%m-%d")
            else:
                p_val_str = str(p_val) if p_val is not None else ""
            rendered = rendered.replace(f"{{{{{i}}}}}", p_val_str)

    return rendered


def queue_message(
    session: Session,
    *,
    recipient_phone: str,
    recipient_name: str,
    message_body: str,
    student_id: int | None = None,
    parent_id: int | None = None,
    batch_id: int | None = None,
    template_id: int | None = None,
    template_name: str | None = None,
    parameters: list[str] | dict[str, Any] | None = None,
    category: str = "UTILITY",
    trigger_type: str = "MANUAL",
    source_module: str | None = None,
    source_record_id: int | None = None,
    environment: str = "PRODUCTION",
) -> Message:
    """Queues a single outgoing message safely into the database."""
    is_valid, e164_phone, reason = normalize_phone_number(recipient_phone)
    if not is_valid:
        raise ValueError(f"Cannot queue message: {reason}")

    params_json_str = None
    if parameters is not None:
        if isinstance(parameters, dict):
            normalized_dict = {}
            for k, v in parameters.items():
                if isinstance(v, (date, datetime)):
                    normalized_dict[k] = v.strftime("%Y-%m-%d")
                elif is_date_key(k):
                    normalized_dict[k] = normalize_date_variable(v)
                else:
                    normalized_dict[k] = v
            params_json_str = json.dumps(normalized_dict)
        elif isinstance(parameters, list):
            normalized_list = []
            for p in parameters:
                if isinstance(p, (date, datetime)):
                    normalized_list.append(p.strftime("%Y-%m-%d"))
                else:
                    normalized_list.append(normalize_date_variable(p) if isinstance(p, str) and ("-" in p or "/" in p or " " in p) else p)
            params_json_str = json.dumps(normalized_list)
        elif isinstance(parameters, str):
            params_json_str = parameters
        else:
            params_json_str = json.dumps(parameters)

    msg = Message(
        recipient_phone=e164_phone,
        recipient_name=recipient_name,
        student_id=student_id,
        parent_id=parent_id,
        batch_id=batch_id,
        template_id=template_id,
        template_name=template_name,
        parameters_json=params_json_str,
        message_body=message_body.strip(),
        category=category,
        trigger_type=trigger_type,
        source_module=source_module,
        source_record_id=source_record_id,
        status="QUEUED",
        provider="WHATSAPP_CLOUD",
        environment=environment,
        retry_count=0,
        max_retries=3,
        queued_at=datetime.now(timezone.utc),
    )
    session.add(msg)
    session.flush()
    return msg


def queue_bulk_messages(
    session: Session,
    *,
    recipients: list[dict[str, Any]],
    message_body_template: str,
    template_id: int | None = None,
    template_name: str | None = None,
    category: str = "UTILITY",
    trigger_type: str = "MANUAL",
    source_module: str | None = None,
) -> int:
    """Queues a batch of messages for eligible recipients."""
    cfg = get_messaging_config(session)
    env = cfg.get("whatsapp_environment", "DEVELOPMENT")
    queued_count = 0

    template = None
    if template_id:
        template = session.get(MessageTemplate, template_id)
    if not template and template_name:
        template = session.scalar(select(MessageTemplate).where(MessageTemplate.name == template_name))

    for r in recipients:
        phone = r["phone"]
        r_name = r.get("recipient_name") or "Parent"
        st_name = r.get("student_name") or r_name or "Student"
        b_name = r.get("batch_name") or "General"
        today_iso = date.today().strftime("%Y-%m-%d")

        context = {
            "student_name": st_name,
            "batch_name": b_name,
            "recipient_name": r_name,
            "date": today_iso,
            "due_date": today_iso,
            "test_date": today_iso,
        }

        # If sending announcement template or general notice, extract custom message body
        announcement_content = ""
        if "Important Announcement from TAMS:" in message_body_template:
            ann_match = re.search(r"Important Announcement from TAMS:\s*(.*?)(?:\.\s*Batch:|$)", message_body_template, re.DOTALL)
            if ann_match:
                announcement_content = ann_match.group(1).strip()
        if not announcement_content:
            announcement_content = message_body_template.strip()
        context["announcement_text"] = announcement_content

        body = render_template_text(message_body_template, context)

        params_list = None
        if template and template.parameters_json:
            try:
                param_keys = json.loads(template.parameters_json)
                params_list = []
                for k in param_keys:
                    val = context.get(k)
                    if val is None or not str(val).strip():
                        val = get_default_parameter_fallback(k, r_name)
                    if is_date_key(k):
                        params_list.append(normalize_date_variable(val))
                    else:
                        params_list.append(str(val))
            except Exception:
                params_list = None

        queue_message(
            session,
            recipient_phone=phone,
            recipient_name=r_name,
            message_body=body,
            student_id=r.get("student_id"),
            parent_id=r.get("parent_id"),
            batch_id=r.get("batch_id"),
            template_id=template_id,
            template_name=template_name,
            parameters=params_list,
            category=category,
            trigger_type=trigger_type,
            source_module=source_module,
            environment=env,
        )
        queued_count += 1

    session.commit()
    return queued_count


# ─────────────────────────────────────────────────────────────────────────────
# 4. QUEUE PROCESSING & LEASE CLAIM MECHANISM (COACHING HELPER WORKER)
# ─────────────────────────────────────────────────────────────────────────────

def is_within_quiet_hours(cfg: dict[str, str]) -> bool:
    """Checks if current time falls within configured quiet hours."""
    if cfg.get("quiet_hours_enabled", "false").lower() != "true":
        return False
    try:
        now_time = datetime.now().time()
        start_parts = [int(p) for p in cfg.get("quiet_hours_start", "22:00").split(":")]
        end_parts = [int(p) for p in cfg.get("quiet_hours_end", "07:00").split(":")]
        start_t = time(start_parts[0], start_parts[1])
        end_t = time(end_parts[0], end_parts[1])

        if start_t <= end_t:
            return start_t <= now_time <= end_t
        else:
            # Over midnight: e.g. 22:00 to 07:00
            return now_time >= start_t or now_time <= end_t
    except Exception:
        return False


def extract_template_parameters(
    message: Message,
    template: MessageTemplate,
) -> tuple[bool, list[str], str]:
    """
    Extracts and validates ordered parameter list for Meta template message.
    Returns: (is_valid: bool, parameters: list[str], error_message: str)
    """
    expected_param_keys = []
    if template.parameters_json:
        try:
            expected_param_keys = json.loads(template.parameters_json)
        except Exception:
            expected_param_keys = []

    # 1. Check message.parameters_json
    if message.parameters_json:
        try:
            params = json.loads(message.parameters_json)
            if isinstance(params, list):
                if expected_param_keys and len(params) != len(expected_param_keys):
                    return False, [], f"Template parameter mismatch: expected {len(expected_param_keys)} parameters ({expected_param_keys}), got {len(params)}"
                result = []
                for idx, p in enumerate(params):
                    k = expected_param_keys[idx] if idx < len(expected_param_keys) else ""
                    val = p
                    if val is None or not str(val).strip():
                        val = get_default_parameter_fallback(k, message.recipient_name)
                    if is_date_key(k):
                        result.append(normalize_date_variable(val))
                    elif isinstance(val, (date, datetime)):
                        result.append(val.strftime("%Y-%m-%d"))
                    else:
                        result.append(str(val))
                return True, result, ""
            elif isinstance(params, dict):
                ordered = []
                for k in expected_param_keys:
                    val = params.get(k)
                    if val is None or not str(val).strip():
                        val = get_default_parameter_fallback(k, message.recipient_name)
                    if is_date_key(k):
                        ordered.append(normalize_date_variable(val))
                    elif isinstance(val, (date, datetime)):
                        ordered.append(val.strftime("%Y-%m-%d"))
                    else:
                        ordered.append(str(val))
                return True, ordered, ""
        except Exception as e:
            return False, [], f"Invalid parameters_json format: {e}"

    # 2. If template requires no parameters (e.g. hello_world)
    if not expected_param_keys:
        return True, [], ""

    # 3. Fallback: Parse from rendered message_body using template.body regex
    try:
        pattern = re.escape(template.body)
        for idx, key in enumerate(expected_param_keys, 1):
            pattern = pattern.replace(r"\{\{" + key + r"\}\}", rf"(?P<{key}>.+?)")
            pattern = pattern.replace(r"\{\{\ " + key + r"\ \}\}", rf"(?P<{key}>.+?)")
            pattern = pattern.replace(r"\{\{" + str(idx) + r"\}\}", rf"(?P<{key}>.+?)")
            pattern = pattern.replace(r"\{\{\ " + str(idx) + r"\ \}\}", rf"(?P<{key}>.+?)")
        pattern = "^" + pattern + "$"
        match = re.match(pattern, message.message_body.strip())
        if match:
            params = []
            for k in expected_param_keys:
                raw_val = match.group(k)
                if raw_val is None or not str(raw_val).strip():
                    raw_val = get_default_parameter_fallback(k, message.recipient_name)
                if is_date_key(k):
                    params.append(normalize_date_variable(raw_val))
                else:
                    params.append(str(raw_val))
            return True, params, ""
    except Exception:
        pass

    # Required parameters could not be resolved
    return False, [], f"Missing required parameters for template '{template.name}'. Expected keys: {expected_param_keys}"


def process_message_queue(
    session: Session,
    worker_id: str = "TAMS_QueueWorker",
    batch_limit: int = 10,
) -> dict[str, Any]:
    """
    Processes eligible pending messages using atomic claim/lease locking.
    Safe for SQLite multi-process concurrency, network timeouts, and crash recovery.
    Returns processing summary: {'processed': N, 'accepted': N, 'failed': N, 'retried': N}
    """
    cfg = get_messaging_config(session)
    if cfg.get("queue_enabled", "true").lower() != "true":
        return {"status": "DISABLED", "processed": 0}

    if is_within_quiet_hours(cfg):
        return {"status": "QUIET_HOURS", "processed": 0}

    now = datetime.now(timezone.utc)
    lease_duration = timedelta(seconds=90)
    lease_expiry = now + lease_duration

    # 1. Identify candidate messages:
    # - New messages: status == "QUEUED"
    # - Scheduled retries: status == "RETRY_SCHEDULED" where next_retry_at <= now
    # - Recover expired leases (worker crash recovery): status == "SENDING" where leased_until < now
    claim_stmt = select(Message).where(
        or_(
            Message.status == "QUEUED",
            and_(
                Message.status == "RETRY_SCHEDULED",
                Message.next_retry_at <= now,
            ),
            and_(
                Message.status == "SENDING",
                Message.leased_until < now,
            ),
        ),
        or_(
            Message.leased_until.is_(None),
            Message.leased_until < now,
        )
    ).order_by(Message.queued_at.asc()).limit(batch_limit)

    candidate_messages = list(session.scalars(claim_stmt).all())
    if not candidate_messages:
        return {"status": "IDLE", "processed": 0, "accepted": 0, "failed": 0, "retried": 0}

    # Atomically claim candidates using UPDATE to prevent competing workers from double-claiming
    claimed_ids = []
    for cand in candidate_messages:
        claim_update = (
            update(Message)
            .where(
                Message.id == cand.id,
                or_(Message.leased_until.is_(None), Message.leased_until < now),
            )
            .values(
                status="SENDING",
                lease_holder=worker_id,
                leased_until=lease_expiry,
            )
            .execution_options(synchronize_session=False)
        )
        res = session.execute(claim_update)
        if res.rowcount == 1:
            claimed_ids.append(cand.id)

    session.commit()

    if not claimed_ids:
        return {"status": "IDLE", "processed": 0, "accepted": 0, "failed": 0, "retried": 0}

    # Fetch fresh claimed messages
    messages_to_process = list(
        session.scalars(select(Message).where(Message.id.in_(claimed_ids))).all()
    )

    # 2. Process each claimed message with provider
    provider = get_whatsapp_provider_client(session)
    backoff_base = int(cfg.get("retry_backoff_base", "60"))
    accepted_cnt = 0
    failed_cnt = 0
    retried_cnt = 0

    for m in messages_to_process:
        try:
            # Check if this message uses a pre-configured template
            template = None
            if m.template_id:
                template = session.get(MessageTemplate, m.template_id)
            if not template and m.template_name:
                template = session.scalar(
                    select(MessageTemplate).where(MessageTemplate.name == m.template_name)
                )

            if template:
                # Validate parameters against template definition
                valid, params, err_msg = extract_template_parameters(m, template)
                if not valid:
                    # Parameter mismatch: fail before sending to provider
                    m.status = "FAILED"
                    m.error_code = "PARAM_MISMATCH"
                    m.error_message = err_msg
                    m.lease_holder = None
                    m.leased_until = None
                    failed_cnt += 1
                    session.commit()
                    continue

                # Correct Meta WhatsApp template fields:
                meta_template_name = template.meta_template_name
                lang_code = template.language or "en_US"

                expected_param_keys = []
                if template.parameters_json:
                    try:
                        expected_param_keys = json.loads(template.parameters_json)
                    except Exception:
                        expected_param_keys = []

                res = provider.send_template_message(
                    recipient_phone=m.recipient_phone,
                    template_name=meta_template_name,
                    language_code=lang_code,
                    parameters=params if params else None,
                    parameter_names=expected_param_keys if expected_param_keys else None,
                )
            elif m.template_name:
                # Template name without template record (fallback)
                res = provider.send_template_message(
                    recipient_phone=m.recipient_phone,
                    template_name=m.template_name,
                    language_code="en_US",
                )
            else:
                # Free-form text message (applicable within 24h window)
                res = provider.send_text_message(
                    recipient_phone=m.recipient_phone,
                    message_body=m.message_body,
                )

            if res.success:
                m.status = "ACCEPTED"
                m.provider_message_id = res.provider_message_id
                m.sent_at = datetime.now(timezone.utc)
                m.error_message = None
                m.error_code = None
                m.lease_holder = None
                m.leased_until = None
                accepted_cnt += 1
            else:
                err_text = res.error_message or "Unknown failure"
                if getattr(res, "is_ambiguous", False):
                    err_text = f"[AMBIGUOUS_OUTCOME] {err_text}"

                if res.is_retryable and m.retry_count < m.max_retries:
                    m.status = "RETRY_SCHEDULED"
                    m.retry_count += 1
                    backoff_secs = backoff_base * (2 ** (m.retry_count - 1))
                    m.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_secs)
                    m.error_message = err_text
                    m.error_code = res.error_code
                    m.lease_holder = None
                    m.leased_until = None
                    retried_cnt += 1
                else:
                    m.status = "FAILED"
                    m.error_message = err_text
                    m.error_code = res.error_code
                    m.lease_holder = None
                    m.leased_until = None
                    failed_cnt += 1

        except Exception as ex:
            logger.error("Exception processing message %d: %s", m.id, ex)
            m.status = "FAILED"
            m.error_message = f"Processor exception: {type(ex).__name__} - {ex}"
            m.lease_holder = None
            m.leased_until = None
            failed_cnt += 1

        session.commit()

    return {
        "status": "COMPLETED",
        "processed": len(messages_to_process),
        "accepted": accepted_cnt,
        "failed": failed_cnt,
        "retried": retried_cnt,
    }


def retry_failed_message(session: Session, message_id: int) -> bool:
    """Requeues a single failed message immediately."""
    msg = session.get(Message, message_id)
    if not msg:
        return False
    msg.status = "QUEUED"
    msg.next_retry_at = None
    msg.lease_holder = None
    msg.leased_until = None
    session.commit()
    return True


def cancel_pending_message(session: Session, message_id: int) -> bool:
    """Cancels a pending or retry-scheduled message if not currently in flight."""
    msg = session.get(Message, message_id)
    if not msg or msg.status in ("SENDING", "ACCEPTED", "DELIVERED", "READ", "CANCELLED"):
        return False
    msg.status = "CANCELLED"
    msg.lease_holder = None
    msg.leased_until = None
    session.commit()
    return True


def clear_completed_messages(session: Session, days_old: int = 30) -> int:
    """Removes old successfully delivered or read messages older than specified days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_old)
    del_stmt = select(Message).where(
        Message.status.in_(["DELIVERED", "READ"]),
        Message.queued_at < cutoff,
    )
    old_msgs = list(session.scalars(del_stmt).all())
    count = len(old_msgs)
    for m in old_msgs:
        session.delete(m)
    session.commit()
    return count


# ─────────────────────────────────────────────────────────────────────────────
# 5. AUTOMATION RULES TRIGGER & COOLDOWN ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def trigger_automation_event(
    session: Session,
    *,
    event_type: str,
    event_data: dict[str, Any],
    batch_id: int | None = None,
    student_id: int | None = None,
    source_record_id: int | None = None,
) -> int:
    """
    Evaluates enabled notification rules matching event_type.
    Applies cooldown periods and record-level deduplication to prevent duplicate messages.
    """
    rules_stmt = select(NotificationRule).where(
        NotificationRule.trigger_event == event_type,
        NotificationRule.is_enabled == True,
    )
    if batch_id:
        rules_stmt = rules_stmt.where(
            or_(NotificationRule.batch_id.is_(None), NotificationRule.batch_id == batch_id)
        )
    rules = list(session.scalars(rules_stmt).all())
    if not rules:
        return 0

    templates = {t.id: t for t in session.scalars(select(MessageTemplate)).all()}
    queued_count = 0
    now = datetime.now(timezone.utc)

    for rule in rules:
        template = templates.get(rule.template_id)
        if not template or not template.is_active:
            continue

        # Cooldown & deduplication check
        if student_id:
            # 1. Deduplication per specific record (e.g. test_id, payment_id)
            if source_record_id is not None:
                record_msg = session.scalar(
                    select(Message).where(
                        Message.student_id == student_id,
                        Message.template_name == template.name,
                        Message.trigger_type == "AUTOMATED",
                        Message.source_record_id == source_record_id,
                    )
                )
                if record_msg:
                    # Message for this exact record was already queued; prevent duplicate send
                    continue

            # 2. General time-based cooldown window (only if cooldown_days > 0 and no source_record_id)
            if rule.cooldown_days > 0 and source_record_id is None:
                cooldown_cutoff = now - timedelta(days=rule.cooldown_days)
                recent_msg = session.scalar(
                    select(Message).where(
                        Message.student_id == student_id,
                        Message.template_name == template.name,
                        Message.trigger_type == "AUTOMATED",
                        Message.queued_at >= cooldown_cutoff,
                    )
                )
                if recent_msg:
                    # Still within cooldown window; prevent duplicate send
                    continue

        # Resolve recipient
        res = get_eligible_recipients(session, target_type="STUDENT", target_ids=[student_id] if student_id else None)
        for r in res["eligible"]:
            ctx = dict(event_data)
            ctx["student_name"] = r["student_name"]
            ctx["batch_name"] = r["batch_name"]
            ctx["recipient_name"] = r["recipient_name"]

            # Normalize any date variables in ctx to YYYY-MM-DD
            for k, v in list(ctx.items()):
                if isinstance(v, (date, datetime)):
                    ctx[k] = v.strftime("%Y-%m-%d")
                elif is_date_key(k):
                    ctx[k] = normalize_date_variable(v)

            body = render_template_text(template.body, ctx)

            cfg = get_messaging_config(session)
            queue_message(
                session,
                recipient_phone=r["phone"],
                recipient_name=r["recipient_name"],
                message_body=body,
                student_id=r["student_id"],
                parent_id=r["parent_id"],
                batch_id=r["batch_id"],
                template_id=template.id,
                template_name=template.name,
                parameters=ctx,
                category=template.category,
                trigger_type="AUTOMATED",
                source_module=event_type,
                source_record_id=source_record_id,
                environment=cfg.get("whatsapp_environment", "PRODUCTION"),
            )
            queued_count += 1

    session.commit()
    return queued_count


# ─────────────────────────────────────────────────────────────────────────────
# 6. ANALYTICS & AUDIT REPORTING
# ─────────────────────────────────────────────────────────────────────────────

def get_messaging_overview_stats(
    session: Session,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """Computes comprehensive messaging KPI cards and distribution statistics."""
    stmt = select(Message)
    if start_date:
        stmt = stmt.where(Message.queued_at >= datetime.combine(start_date, time.min, tzinfo=timezone.utc))
    if end_date:
        stmt = stmt.where(Message.queued_at <= datetime.combine(end_date, time.max, tzinfo=timezone.utc))

    all_messages = list(session.scalars(stmt).all())
    total_count = len(all_messages)

    status_counts = {
        "QUEUED": 0,
        "SENDING": 0,
        "ACCEPTED": 0,
        "DELIVERED": 0,
        "READ": 0,
        "FAILED": 0,
        "RETRY_SCHEDULED": 0,
        "CANCELLED": 0,
    }
    failure_reasons: dict[str, int] = {}
    categories_count: dict[str, int] = {}

    for m in all_messages:
        st = m.status
        status_counts[st] = status_counts.get(st, 0) + 1
        cat = m.category or "UTILITY"
        categories_count[cat] = categories_count.get(cat, 0) + 1

        if st == "FAILED" and m.error_message:
            short_reason = m.error_message[:40]
            failure_reasons[short_reason] = failure_reasons.get(short_reason, 0) + 1

    cfg = get_messaging_config(session)
    env = cfg.get("whatsapp_environment", "DEVELOPMENT")
    has_token = bool(get_access_token())
    has_phone = bool(cfg.get("whatsapp_phone_number_id"))

    if not has_token or not has_phone:
        conn_status = "NOT_CONFIGURED"
    else:
        conn_status = "CONFIGURED"

    return {
        "total_messages": total_count,
        "status_counts": status_counts,
        "categories_count": categories_count,
        "failure_reasons": failure_reasons,
        "environment": env,
        "connection_status": conn_status,
        "is_queue_enabled": cfg.get("queue_enabled", "true").lower() == "true",
    }


def get_message_history_records(
    session: Session,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    batch_id: int | None = None,
    status_filter: str | None = None,
    category_filter: str | None = None,
    trigger_filter: str | None = None,
    search_query: str | None = None,
    limit: int = 150,
) -> list[dict[str, Any]]:
    """Returns filtered message records formatted for UI history table."""
    stmt = select(Message).order_by(Message.queued_at.desc())

    if start_date:
        stmt = stmt.where(Message.queued_at >= datetime.combine(start_date, time.min, tzinfo=timezone.utc))
    if end_date:
        stmt = stmt.where(Message.queued_at <= datetime.combine(end_date, time.max, tzinfo=timezone.utc))
    if batch_id:
        stmt = stmt.where(Message.batch_id == batch_id)
    if status_filter and status_filter != "All Statuses":
        stmt = stmt.where(Message.status == status_filter)
    if category_filter and category_filter != "All Categories":
        stmt = stmt.where(Message.category == category_filter)
    if trigger_filter and trigger_filter != "All Triggers":
        stmt = stmt.where(Message.trigger_type == trigger_filter)

    if search_query:
        term = f"%{search_query.strip()}%"
        stmt = stmt.outerjoin(Student, Message.student_id == Student.id).where(
            or_(
                Message.recipient_name.ilike(term),
                Message.recipient_phone.ilike(term),
                Student.first_name.ilike(term),
                Student.last_name.ilike(term),
            )
        )

    messages = list(session.scalars(stmt.limit(limit)).all())
    student_ids = {m.student_id for m in messages if m.student_id is not None}
    batch_ids = {m.batch_id for m in messages if m.batch_id is not None}

    students = (
        {s.id: s for s in session.scalars(select(Student).where(Student.id.in_(student_ids))).all()}
        if student_ids else {}
    )
    batches = (
        {b.id: b for b in session.scalars(select(Batch).where(Batch.id.in_(batch_ids))).all()}
        if batch_ids else {}
    )

    output = []
    for m in messages:
        s = students.get(m.student_id) if m.student_id else None
        b = batches.get(m.batch_id) if m.batch_id else None

        s_name = f"{s.first_name} {s.last_name or ''}".strip() if s else "—"
        b_name = b.name if b else "—"

        output.append({
            "id": m.id,
            "date_time": m.queued_at.strftime("%d %b %Y, %H:%M"),
            "recipient_name": m.recipient_name,
            "student_name": s_name,
            "batch_name": b_name,
            "phone_masked": mask_phone_number(m.recipient_phone),
            "template_name": m.template_name or "Free-form",
            "category": m.category,
            "trigger_type": m.trigger_type,
            "status": m.status,
            "retry_count": m.retry_count,
            "provider_message_id": m.provider_message_id or "—",
            "error_message": m.error_message or "—",
            "environment": m.environment,
            "message_body": m.message_body,
        })

    return output


def export_message_history_csv(
    session: Session,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    batch_id: int | None = None,
    status_filter: str | None = None,
) -> str:
    """Exports filtered message history to CSV. Strips all credentials and masks numbers."""
    records = get_message_history_records(
        session,
        start_date=start_date,
        end_date=end_date,
        batch_id=batch_id,
        status_filter=status_filter,
        limit=5000,
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Message ID",
        "Timestamp",
        "Recipient Name",
        "Student Name",
        "Batch",
        "Phone Number",
        "Template",
        "Category",
        "Trigger",
        "Status",
        "Retries",
        "Provider Message ID",
        "Failure Reason",
    ])
    for r in records:
        writer.writerow([
            r["id"],
            r["date_time"],
            r["recipient_name"],
            r["student_name"],
            r["batch_name"],
            r["phone_masked"],
            r["template_name"],
            r["category"],
            r["trigger_type"],
            r["status"],
            r["retry_count"],
            r["provider_message_id"],
            r["error_message"],
        ])
    return output.getvalue()
