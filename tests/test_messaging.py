"""
Automated Test Suite for TAMS Messaging System & Meta WhatsApp Cloud API Integration.
Mocks all network requests to Meta servers to ensure 0 external network dependency.
"""

from __future__ import annotations

import io
import json
import os
import sys
import unittest.mock as mock
from datetime import date, datetime, timedelta, timezone

import pytest
from PyQt6.QtWidgets import QApplication, QTableWidget
from sqlalchemy import select

from app.database.connection import SessionLocal
from app.database.models.batch import Batch
from app.database.models.message import (
    Message,
    MessageTemplate,
    MessagingConfig,
    NotificationRule,
    RecipientPreference,
)
from app.database.models.student import Student
from app.services.messaging_service import (
    cancel_pending_message,
    clear_completed_messages,
    ensure_messaging_seed_data,
    extract_template_parameters,
    get_eligible_recipients,
    get_message_history_records,
    get_messaging_config,
    is_date_key,
    normalize_date_variable,
    process_message_queue,
    queue_message,
    render_template_text,
    retry_failed_message,
    trigger_automation_event,
    update_messaging_config,
)
from app.services.whatsapp_provider import (
    WhatsAppCloudProvider,
    WhatsAppConfig,
    get_access_token,
    is_retryable_whatsapp_error,
    mask_phone_number,
    mask_token,
    normalize_phone_number,
    remove_access_token,
    save_access_token,
)
from app.ui.messages_page_widget import MessagesPageWidget
from app.ui.messaging_settings_widget import MessagingSettingsWidget
from app.ui.table_utils import TAMSItemDelegate, configure_table_ux


@pytest.fixture
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


# ─────────────────────────────────────────────────────────────────────────────
# 1. PHONE & TOKEN UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def test_phone_normalization():
    valid, p1, _ = normalize_phone_number("+91 98765 43210")
    assert valid is True
    assert p1 == "+919876543210"

    valid, p2, _ = normalize_phone_number("9876543210")
    assert valid is True
    assert p2 == "+919876543210"

    valid, p3, _ = normalize_phone_number("09876543210")
    assert valid is True
    assert p3 == "+919876543210"

    valid, _, _ = normalize_phone_number("123")
    assert valid is False

    valid, _, _ = normalize_phone_number("")
    assert valid is False

    valid, _, _ = normalize_phone_number(None)
    assert valid is False


def test_phone_masking():
    masked = mask_phone_number("+919876543210")
    assert "98" in masked
    assert "210" in masked
    assert mask_phone_number(None) == "—"


def test_token_masking():
    assert "EAAX...cdef" in mask_token("EAAXyz1234567890abcdef")
    assert mask_token("short") == "Not Configured"
    assert mask_token(None) == "Not Configured"


def test_secure_token_storage(tmp_path, monkeypatch):
    test_token_path = tmp_path / ".whatsapp_token"
    monkeypatch.setattr("app.services.whatsapp_provider.CREDENTIALS_FILE", test_token_path)

    assert get_access_token() is None
    assert save_access_token("TEST_META_TOKEN_SECRET_123") is True
    assert get_access_token() == "TEST_META_TOKEN_SECRET_123"
    assert remove_access_token() is True
    assert get_access_token() is None


# ─────────────────────────────────────────────────────────────────────────────
# 2. WHATSAPP PROVIDER CLIENT (MOCKED NETWORK)
# ─────────────────────────────────────────────────────────────────────────────

def test_whatsapp_retryable_error_classification():
    # Transient / Rate limiting (http_status, meta_code)
    assert is_retryable_whatsapp_error(429, 130429) is True
    assert is_retryable_whatsapp_error(500, 2) is True
    assert is_retryable_whatsapp_error(503, 1) is True
    # Permanent
    assert is_retryable_whatsapp_error(401, 190) is False  # Invalid token
    assert is_retryable_whatsapp_error(400, 131026) is False  # Undeliverable


@mock.patch("urllib.request.urlopen")
def test_whatsapp_test_connection_success(mock_urlopen):
    mock_response = mock.MagicMock()
    mock_response.getcode.return_value = 200
    mock_response.read.return_value = json.dumps({
        "id": "100200300400",
        "verified_name": "TAMS Coaching Institute",
        "display_phone_number": "+91 98765 43210",
        "quality_rating": "GREEN",
    }).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    config = WhatsAppConfig(
        phone_number_id="100200300400",
        waba_id="999888777",
        access_token="TEST_TOKEN",
    )
    provider = WhatsAppCloudProvider(config)
    result = provider.test_connection()
    assert result["success"] is True
    assert result["verified_name"] == "TAMS Coaching Institute"


@mock.patch("urllib.request.urlopen")
def test_whatsapp_send_template_success(mock_urlopen):
    mock_response = mock.MagicMock()
    mock_response.getcode.return_value = 200
    mock_response.read.return_value = json.dumps({
        "messaging_product": "whatsapp",
        "contacts": [{"input": "+919876543210", "wa_id": "919876543210"}],
        "messages": [{"id": "wamid.HBgLMTIzNDU2Nzg5MA=="}],
    }).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    config = WhatsAppConfig(
        phone_number_id="100200300400",
        waba_id="999888777",
        access_token="TEST_TOKEN",
    )
    provider = WhatsAppCloudProvider(config)
    result = provider.send_template_message(
        recipient_phone="+919876543210",
        template_name="hello_world",
        language_code="en_US",
    )
    assert result.success is True
    assert result.provider_message_id == "wamid.HBgLMTIzNDU2Nzg5MA=="


@mock.patch("urllib.request.urlopen")
def test_whatsapp_send_template_normalizes_date_parameters(mock_urlopen):
    mock_response = mock.MagicMock()
    mock_response.getcode.return_value = 200
    mock_response.read.return_value = json.dumps({
        "messaging_product": "whatsapp",
        "contacts": [{"input": "+919876543210", "wa_id": "919876543210"}],
        "messages": [{"id": "wamid.TEST_DATE_ISO"}],
    }).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    config = WhatsAppConfig(
        phone_number_id="100200300400",
        waba_id="999888777",
        access_token="TEST_TOKEN",
    )
    provider = WhatsAppCloudProvider(config)
    result = provider.send_template_message(
        recipient_phone="+919876543210",
        template_name="absence_alert",
        language_code="en",
        parameters=["Aarav", "21 Oct 2026", "Class 10"],
    )
    assert result.success is True

    # Inspect the JSON payload sent via urllib.request.Request
    call_args = mock_urlopen.call_args[0]
    req = call_args[0]
    payload = json.loads(req.data.decode("utf-8"))
    params = payload["template"]["components"][0]["parameters"]
    assert params[0]["text"] == "Aarav"
    assert params[1]["text"] == "2026-10-21"  # Normalized to ISO YYYY-MM-DD!
    assert params[2]["text"] == "Class 10"


@mock.patch("urllib.request.urlopen")
def test_whatsapp_send_template_named_parameters_and_empty_fallbacks(mock_urlopen):
    mock_response = mock.MagicMock()
    mock_response.getcode.return_value = 200
    mock_response.read.return_value = json.dumps({
        "messaging_product": "whatsapp",
        "contacts": [{"input": "+919876543210", "wa_id": "919876543210"}],
        "messages": [{"id": "wamid.TEST_NAMED_PARAMS"}],
    }).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    config = WhatsAppConfig(
        phone_number_id="100200300400",
        waba_id="999888777",
        access_token="TEST_TOKEN",
    )
    provider = WhatsAppCloudProvider(config)
    # Test with named parameter names and some empty values to test fallback (resolves Meta Error 100 and 131008)
    result = provider.send_template_message(
        recipient_phone="+919876543210",
        template_name="absence_alert",
        language_code="en",
        parameters=["", "21 Oct 2026", ""],
        parameter_names=["student_name", "date", "batch_name"],
    )
    assert result.success is True

    call_args = mock_urlopen.call_args[0]
    req = call_args[0]
    payload = json.loads(req.data.decode("utf-8"))
    params = payload["template"]["components"][0]["parameters"]
    # 1. Parameter names must be present to satisfy Meta Error 100
    assert params[0]["parameter_name"] == "student_name"
    assert params[1]["parameter_name"] == "date"
    assert params[2]["parameter_name"] == "batch_name"
    # 2. Text must not be empty to satisfy Meta Error 131008
    assert params[0]["text"] == "Student"
    assert params[1]["text"] == "2026-10-21"
    assert params[2]["text"] == "General"


@mock.patch("urllib.request.urlopen")
def test_whatsapp_hello_world_error_131058_friendly_message(mock_urlopen):
    import urllib.error
    # Mock HTTP 400 error 131058
    error_content = json.dumps({
        "error": {
            "message": "(#131058) Hello World templates can only be sent from the Public Test Numbers",
            "type": "OAuthException",
            "code": 131058,
            "error_data": {"details": "Hello World templates can only be sent from the Public Test Numbers"},
        }
    }).encode("utf-8")
    fp = io.BytesIO(error_content)
    mock_urlopen.side_effect = urllib.error.HTTPError("https://graph.facebook.com", 400, "Bad Request", {}, fp)

    config = WhatsAppConfig(
        phone_number_id="100200300400",
        waba_id="999888777",
        access_token="TEST_TOKEN",
    )
    provider = WhatsAppCloudProvider(config)
    result = provider.send_template_message(
        recipient_phone="+919876543210",
        template_name="hello_world",
        language_code="en_US",
    )
    assert result.success is False
    assert result.error_code == "131058"
    assert "Public Test Numbers" in result.error_message
    assert "approved templates" in result.error_message


# ─────────────────────────────────────────────────────────────────────────────
# 3. MESSAGING SERVICE LAYER & QUEUE LIFECYCLE
# ─────────────────────────────────────────────────────────────────────────────

def test_template_interpolation():
    template = "Hello {{student_name}}, your fee of ₹{{amount}} is due on {{due_date}}."
    context = {
        "student_name": "Aarav Sharma",
        "amount": "4500",
        "due_date": "15/10/2026",
    }
    rendered = render_template_text(template, context)
    assert rendered == "Hello Aarav Sharma, your fee of ₹4500 is due on 2026-10-15."

    # Test date object interpolation
    context_obj = {
        "student_name": "Aarav Sharma",
        "amount": "4500",
        "due_date": date(2026, 10, 15),
    }
    assert render_template_text(template, context_obj) == "Hello Aarav Sharma, your fee of ₹4500 is due on 2026-10-15."

    # Test already formatted ISO date string
    context_iso = {
        "student_name": "Aarav Sharma",
        "amount": "4500",
        "due_date": "2026-10-15",
    }
    assert render_template_text(template, context_iso) == "Hello Aarav Sharma, your fee of ₹4500 is due on 2026-10-15."


def test_date_normalization_utilities():
    assert is_date_key("date") is True
    assert is_date_key("due_date") is True
    assert is_date_key("test_date") is True
    assert is_date_key("attendance_date") is True
    assert is_date_key("student_name") is False
    assert is_date_key("amount") is False

    assert normalize_date_variable(date(2026, 10, 21)) == "2026-10-21"
    assert normalize_date_variable(datetime(2026, 10, 21, 14, 30)) == "2026-10-21"
    assert normalize_date_variable("21 Oct 2026") == "2026-10-21"
    assert normalize_date_variable("21 October 2026") == "2026-10-21"
    assert normalize_date_variable("21/10/2026") == "2026-10-21"
    assert normalize_date_variable("21-10-2026") == "2026-10-21"
    assert normalize_date_variable("2026-10-21") == "2026-10-21"
    assert normalize_date_variable("2026/10/21") == "2026-10-21"
    assert normalize_date_variable("Not A Date") == "Not A Date"
    assert normalize_date_variable(None) == ""


def test_trigger_automation_event_date_formatting():
    with SessionLocal() as session:
        ensure_messaging_seed_data(session)

        # Create or fetch a test student with parent and batch
        from app.database.models.parent import Parent
        test_parent = Parent(name="Test Guardian", phone="+919876543999")
        session.add(test_parent)
        session.flush()

        test_batch = Batch(name="Test Batch Meta Date", days="Mon,Wed,Fri")
        session.add(test_batch)
        session.flush()

        test_student = Student(
            admission_number="ADM-META-DATE-1",
            first_name="Rohan",
            last_name="Test",
            parent_id=test_parent.id,
            batch_id=test_batch.id,
            status="ACTIVE",
        )
        session.add(test_student)
        session.flush()

        rule = session.scalar(select(NotificationRule).where(NotificationRule.trigger_event == "ABSENCE"))
        orig_enabled = rule.is_enabled if rule else False
        if rule:
            rule.is_enabled = True
            session.flush()

        # Trigger ABSENCE event with date formatted or as date object
        count = trigger_automation_event(
            session,
            event_type="ABSENCE",
            event_data={"date": date(2026, 10, 21)},
            batch_id=test_batch.id,
            student_id=test_student.id,
        )
        assert count >= 1

        # Retrieve the queued message
        msg = session.scalar(
            select(Message).where(
                Message.student_id == test_student.id,
                Message.source_module == "ABSENCE",
            ).order_by(Message.id.desc())
        )
        assert msg is not None
        # Verify date in rendered message body is YYYY-MM-DD
        assert "2026-10-21" in msg.message_body
        assert "Oct" not in msg.message_body

        # Verify parameters_json has date in YYYY-MM-DD
        assert msg.parameters_json is not None
        params_dict = json.loads(msg.parameters_json)
        assert params_dict["date"] == "2026-10-21"

        # Verify extract_template_parameters returns YYYY-MM-DD parameter
        template = session.get(MessageTemplate, msg.template_id)
        valid, params, err = extract_template_parameters(msg, template)
        assert valid is True
        assert "2026-10-21" in params

        # Clean up
        if rule:
            rule.is_enabled = orig_enabled
        session.delete(msg)
        session.delete(test_student)
        session.delete(test_batch)
        session.delete(test_parent)
        session.commit()


def test_messaging_config_and_opt_out():
    with SessionLocal() as session:
        ensure_messaging_seed_data(session)

        config = get_messaging_config(session)
        assert isinstance(config, dict)
        assert config.get("whatsapp_environment") in ("DEVELOPMENT", "PRODUCTION")

        phone = "+919999988888"
        pref = session.scalar(select(RecipientPreference).where(RecipientPreference.phone_number == phone))
        if not pref:
            pref = RecipientPreference(phone_number=phone, is_opted_out=False)
            session.add(pref)
            session.commit()

        pref.is_opted_out = True
        session.commit()

        re_pref = session.scalar(select(RecipientPreference).where(RecipientPreference.phone_number == phone))
        assert re_pref.is_opted_out is True

        session.delete(re_pref)
        session.commit()


def test_enqueue_and_queue_processing_lifecycle():
    with SessionLocal() as session:
        ensure_messaging_seed_data(session)

        # Queue a message
        msg = queue_message(
            session,
            recipient_phone="+919876543210",
            recipient_name="Sunita Sharma",
            message_body="Test Message Hello World",
            template_name="hello_world",
        )
        session.commit()
        assert msg.id is not None
        assert msg.status == "QUEUED"
        msg_id = msg.id

        # Mock WhatsApp Provider to succeed
        with mock.patch("app.services.messaging_service.get_whatsapp_provider_client") as mock_get_client:
            from app.services.whatsapp_provider import WhatsAppSendResult
            mock_client = mock.MagicMock()
            mock_client.config.phone_number_id = "100200300"
            mock_client.send_template_message.return_value = WhatsAppSendResult(
                success=True,
                status="ACCEPTED",
                provider_message_id="wamid.TEST_QUEUE_123",
            )
            mock_get_client.return_value = mock_client

            summary = process_message_queue(session, worker_id="test_worker_1", batch_limit=5)
            assert summary["accepted"] >= 1

        # Check DB status transitioned
        refreshed = session.get(Message, msg_id)
        assert refreshed.status in ("SENT", "ACCEPTED", "ACCEPTED_BY_PROVIDER")
        assert refreshed.provider_message_id == "wamid.TEST_QUEUE_123"

        # Clean up
        session.delete(refreshed)
        session.commit()


def test_queue_retry_exponential_backoff():
    with SessionLocal() as session:
        ensure_messaging_seed_data(session)

        msg = queue_message(
            session,
            recipient_phone="+919876543211",
            recipient_name="Parent Test",
            message_body="Retry test message",
            template_name="hello_world",
        )
        session.commit()
        msg_id = msg.id

        # Mock provider returning transient error (retryable)
        with mock.patch("app.services.messaging_service.get_whatsapp_provider_client") as mock_get_client:
            from app.services.whatsapp_provider import WhatsAppSendResult
            mock_client = mock.MagicMock()
            mock_client.config.phone_number_id = "100200300"
            mock_client.send_template_message.return_value = WhatsAppSendResult(
                success=False,
                status="RETRYABLE_FAILURE",
                is_retryable=True,
                error_code="130429",
                error_message="Rate limit exceeded. Please retry later.",
            )
            mock_get_client.return_value = mock_client

            process_message_queue(session, worker_id="test_worker_2", batch_limit=5)

        refreshed = session.get(Message, msg_id)
        assert refreshed.status == "RETRY_SCHEDULED"
        assert refreshed.retry_count == 1
        assert refreshed.next_retry_at is not None

        # Clean up
        cancel_pending_message(session, msg_id)
        session.delete(refreshed)
        session.commit()


def test_recipient_deduplication():
    with SessionLocal() as session:
        batches = session.scalars(select(Batch)).all()
        if not batches:
            pytest.skip("No batches available for deduplication test")

        test_batch = batches[0]
        result = get_eligible_recipients(session, target_type="BATCH", target_ids=[test_batch.id])
        assert isinstance(result, dict)
        assert "eligible" in result

        eligible = result["eligible"]
        phones = [r["phone"] for r in eligible]
        # Valid phone numbers should be unique (no duplicate sends to the same parent)
        assert len(phones) == len(set(phones))


# ─────────────────────────────────────────────────────────────────────────────
# 4. UI WIDGET TESTS (OFFSCREEN)
# ─────────────────────────────────────────────────────────────────────────────

def test_messages_workspace_ui(qapp):
    widget = MessagesPageWidget()
    assert widget.tabs.count() == 5
    assert "Overview" in widget.tabs.tabText(0)
    assert "Compose" in widget.tabs.tabText(1)
    assert "History" in widget.tabs.tabText(2)
    assert "Queue" in widget.tabs.tabText(3)
    assert "Settings" in widget.tabs.tabText(4)

    # Switch tabs to verify lazy loads
    widget.tabs.setCurrentIndex(1)
    widget.tabs.setCurrentIndex(2)
    widget.tabs.setCurrentIndex(3)
    widget.tabs.setCurrentIndex(4)


def test_messaging_settings_widget_ui(qapp):
    widget = MessagingSettingsWidget()
    assert hasattr(widget, "env_combo")
    assert hasattr(widget, "phone_id_input")
    assert hasattr(widget, "templates_table")
    assert hasattr(widget, "rules_table")

    # Table columns validation
    assert widget.templates_table.columnCount() == 7
    assert widget.rules_table.columnCount() == 6


def test_table_ux_configuration(qapp):
    table = QTableWidget(10, 4)
    configure_table_ux(
        table,
        column_widths=[120, 200, 150, 100],
        stretch_column=1,
        default_row_height=40,
        alternating_colors=True,
    )

    assert table.alternatingRowColors() is True
    assert table.verticalHeader().defaultSectionSize() == 40
    assert table.columnWidth(0) == 120
    assert table.columnWidth(2) == 150
    assert table.columnWidth(3) == 100
    assert isinstance(table.itemDelegate(), TAMSItemDelegate)


def test_main_window_messages_page_navigation(qapp):
    from app.ui.main_window import MainWindow
    win = MainWindow()
    win.change_page(8)
    assert win.pages.currentIndex() == 8
    assert hasattr(win, "messages_page")
    assert win.messages_page.tabs.count() == 5
    win.close()


def test_default_whatsapp_credentials_and_environment():
    from app.services.messaging_service import DEFAULT_CONFIGS
    from app.services.whatsapp_provider import DEFAULT_GRAPH_API_VERSION, WhatsAppConfig

    assert DEFAULT_CONFIGS["whatsapp_environment"] == "PRODUCTION"
    assert DEFAULT_CONFIGS["whatsapp_phone_number_id"] == "1480753541781147"
    assert DEFAULT_CONFIGS["whatsapp_waba_id"] == "970600618872001"
    assert DEFAULT_CONFIGS["whatsapp_api_version"] == "v26.0"
    assert DEFAULT_GRAPH_API_VERSION == "v26.0"

    cfg = WhatsAppConfig()
    assert cfg.environment == "PRODUCTION"
    assert cfg.phone_number_id == "1480753541781147"
    assert cfg.waba_id == "970600618872001"
    assert cfg.api_version == "v26.0"


def test_test_results_automation_deduplication_and_multiple_tests():
    with SessionLocal() as session:
        ensure_messaging_seed_data(session)

        # Setup test parent, batch, student
        from app.database.models.parent import Parent
        parent = Parent(name="Result Parent", phone="+919876543111")
        session.add(parent)
        session.flush()

        batch = Batch(name="Test Batch Results", days="Mon,Tue")
        session.add(batch)
        session.flush()

        student = Student(
            admission_number="ADM-TEST-RES-1",
            first_name="Ananya",
            last_name="Sharma",
            parent_id=parent.id,
            batch_id=batch.id,
            status="ACTIVE",
        )
        session.add(student)
        session.flush()

        # Enable TEST_RESULT rule
        rule = session.scalar(select(NotificationRule).where(NotificationRule.trigger_event == "TEST_RESULT"))
        orig_enabled = rule.is_enabled if rule else False
        orig_cooldown = rule.cooldown_days if rule else 0
        if rule:
            rule.is_enabled = True
            rule.cooldown_days = 0
            session.flush()

        # 1. Trigger Test 1 (ID: 991)
        count1 = trigger_automation_event(
            session,
            event_type="TEST_RESULT",
            event_data={
                "marks": "95",
                "max_marks": "100",
                "percentage": "95.0",
                "test_name": "Math Test 1",
                "test_date": "2026-10-22",
                "batch_avg": "90.0",
            },
            batch_id=batch.id,
            student_id=student.id,
            source_record_id=991,
        )
        assert count1 == 1

        # 2. Re-triggering the same Test 1 (ID: 991) must be deduplicated (count 0)
        count_dup = trigger_automation_event(
            session,
            event_type="TEST_RESULT",
            event_data={
                "marks": "95",
                "max_marks": "100",
                "percentage": "95.0",
                "test_name": "Math Test 1",
                "test_date": "2026-10-22",
                "batch_avg": "90.0",
            },
            batch_id=batch.id,
            student_id=student.id,
            source_record_id=991,
        )
        assert count_dup == 0

        # 3. Triggering a DIFFERENT Test 2 (ID: 992) on the same day must succeed
        count2 = trigger_automation_event(
            session,
            event_type="TEST_RESULT",
            event_data={
                "marks": "88",
                "max_marks": "100",
                "percentage": "88.0",
                "test_name": "Science Test 2",
                "test_date": "2026-10-22",
                "batch_avg": "85.0",
            },
            batch_id=batch.id,
            student_id=student.id,
            source_record_id=992,
        )
        assert count2 == 1

        # Cleanup
        msgs = session.scalars(select(Message).where(Message.student_id == student.id)).all()
        for m in msgs:
            session.delete(m)
        if rule:
            rule.is_enabled = orig_enabled
            rule.cooldown_days = orig_cooldown
        session.delete(student)
        session.delete(batch)
        session.delete(parent)
        session.commit()


def test_messaging_settings_widget_no_development_option(qapp):
    widget = MessagingSettingsWidget()
    # Ensure env_combo only has PRODUCTION and no DEVELOPMENT option
    items = [widget.env_combo.itemData(i) for i in range(widget.env_combo.count())]
    assert "DEVELOPMENT" not in items
    assert "PRODUCTION" in items

