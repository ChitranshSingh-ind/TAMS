"""
Automated Test Suite for TAMS Messaging System & Meta WhatsApp Cloud API Integration.
Mocks all network requests to Meta servers to ensure 0 external network dependency.
"""

from __future__ import annotations

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
    get_eligible_recipients,
    get_message_history_records,
    get_messaging_config,
    get_messaging_overview_stats,
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
    assert rendered == "Hello Aarav Sharma, your fee of ₹4500 is due on 15/10/2026."


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
