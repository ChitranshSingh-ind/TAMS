"""
Unit and Integration Test Suite for TAMS CoachingHelper Lifecycle,
IPC Mechanism, Process Discovery, Single-Instance Lock, Stale Lock Recovery,
and Safe Template Parameter Validation.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
import uuid

import pytest
from PyQt6.QtWidgets import QApplication

from app.database.connection import DATABASE_PATH, DATA_DIR, SessionLocal
from app.database.models.message import Message, MessageTemplate, MessagingConfig
from app.services.coaching_helper import CoachingHelper
from app.services.coaching_helper_service import (
    APP_VERSION,
    HELPER_CONTROL_FILE,
    HELPER_LOCK_FILE,
    HELPER_STATUS_FILE,
    SensitiveDataLogFilter,
    SingleInstanceLock,
    check_for_updates,
    check_internet_connectivity,
    get_helper_process_info,
    is_pid_alive,
    read_and_clear_helper_ipc_command,
    read_helper_status,
    send_helper_ipc_command,
    write_helper_status,
)
from app.services.messaging_service import (
    extract_template_parameters,
    process_message_queue,
    queue_message,
)
from app.services.whatsapp_provider import WhatsAppSendResult


@pytest.fixture
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


# ─────────────────────────────────────────────────────────────────────────────
# 1. PROCESS LIVENESS & LOCK TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_pid_liveness():
    # Current process must be alive
    assert is_pid_alive(os.getpid()) is True

    # Invalid / Non-existent PID must be dead
    assert is_pid_alive(-1) is False
    assert is_pid_alive(0) is False
    assert is_pid_alive(99999999) is False


def test_single_instance_lock_basic():
    test_lock_file = DATA_DIR / "test_lifecycle.lock"
    test_lock_file.unlink(missing_ok=True)

    lock1 = SingleInstanceLock(lock_path=test_lock_file)
    lock2 = SingleInstanceLock(lock_path=test_lock_file)

    assert lock1.acquire() is True
    assert lock2.acquire() is False

    lock1.release()
    assert lock2.acquire() is True
    lock2.release()
    test_lock_file.unlink(missing_ok=True)


def test_single_instance_lock_stale_recovery():
    """Verifies that an orphaned lock file from a dead process is automatically recovered."""
    test_lock_file = DATA_DIR / "test_stale.lock"
    # Write a fake dead PID to lock file
    test_lock_file.write_text("PID=99999999\nSTARTED=2026-01-01T00:00:00Z\n", encoding="utf-8")

    lock = SingleInstanceLock(lock_path=test_lock_file)
    # Lock acquire should detect that PID 99999999 is dead and recover
    assert lock.acquire() is True
    lock.release()
    test_lock_file.unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# 2. IPC MECHANISM TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_helper_ipc_commands():
    HELPER_CONTROL_FILE.unlink(missing_ok=True)

    # Invalid command rejected
    assert send_helper_ipc_command("INVALID_CMD") is False

    # Valid command written
    assert send_helper_ipc_command("RUN_CYCLE") is True
    assert HELPER_CONTROL_FILE.exists()

    # Read and consume command
    cmd = read_and_clear_helper_ipc_command()
    assert cmd == "RUN_CYCLE"
    assert not HELPER_CONTROL_FILE.exists()

    # Second read returns None
    assert read_and_clear_helper_ipc_command() is None


def test_helper_status_reporting():
    test_data = {
        "state": "RUNNING",
        "message": "Operational",
        "worker_id": "TestWorker_01",
        "pid": os.getpid(),
        "heartbeat_at": datetime.now(timezone.utc).isoformat(),
        "is_online": True,
        "is_paused": False,
        "version": APP_VERSION,
    }
    write_helper_status(test_data)
    loaded = read_helper_status()
    assert loaded is not None
    assert loaded.get("state") == "RUNNING"
    assert loaded.get("worker_id") == "TestWorker_01"

    info = get_helper_process_info()
    assert isinstance(info, dict)
    assert info.get("running") is True
    assert info.get("pid") == os.getpid()


# ─────────────────────────────────────────────────────────────────────────────
# 3. SENSITIVE DATA LOG FILTER
# ─────────────────────────────────────────────────────────────────────────────

def test_sensitive_data_log_filter():
    log_filter = SensitiveDataLogFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Connecting using token EAAB_TEST_SECRET_TOKEN_XYZ_1234567890 to Graph API with Bearer token_sample_abc_12345678",
        args=(),
        exc_info=None,
    )
    log_filter.filter(record)
    assert "EAAB_TEST_SECRET_TOKEN_XYZ_1234567890" not in record.msg
    assert "EAA***[REDACTED]" in record.msg
    assert "Bearer [REDACTED]" in record.msg


# ─────────────────────────────────────────────────────────────────────────────
# 4. GITHUB UPDATE CHECK RESILIENCE
# ─────────────────────────────────────────────────────────────────────────────

def test_check_for_updates_offline_resilience():
    # Regular call without crashing
    res = check_for_updates()
    assert isinstance(res, dict)
    assert "status" in res
    assert res.get("current_version") == APP_VERSION


def test_check_for_updates_detected_newer():
    mock_cm = mock.MagicMock()
    mock_cm.__enter__.return_value.status = 200
    mock_cm.__enter__.return_value.read.return_value = json.dumps({
        "tag_name": "v3.0.0",
        "body": "Major version upgrade released.",
    }).encode("utf-8")

    with mock.patch("urllib.request.urlopen", return_value=mock_cm):
        res = check_for_updates()
        assert res.get("status") == "update_available"
        assert res.get("latest_version") == "3.0.0"
        assert res.get("is_up_to_date") is False


# ─────────────────────────────────────────────────────────────────────────────
# 5. TEMPLATE PARAMETER EXTRACTION & PRE-FLIGHT VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

def test_extract_template_parameters():
    unique_id = uuid.uuid4().hex[:6]
    with SessionLocal() as session:
        tmpl = MessageTemplate(
            name=f"test_fees_receipt_{unique_id}",
            category="FEES",
            meta_template_name="fee_payment_receipt_v1",
            language="en",
            body="Receipt for {{1}}: Rs. {{2}} received for {{3}}.",
            parameters_json='["student_name", "amount", "month"]',
        )
        session.add(tmpl)
        session.flush()

        msg = Message(
            recipient_phone="+919876543210",
            recipient_name="Test Recipient",
            category="FEES",
            status="QUEUED",
            message_body="Receipt for Aarav: Rs. 5000 received for March.",
            parameters_json='["Aarav", "5000", "March"]',
            template_id=tmpl.id,
        )
        session.add(msg)
        session.flush()

        is_valid, params, err = extract_template_parameters(msg, tmpl)
        assert is_valid is True
        assert params == ["Aarav", "5000", "March"]

        # Test fallback regex extraction when parameters_json is None
        msg.parameters_json = None
        is_valid_regex, params_regex, _ = extract_template_parameters(msg, tmpl)
        assert is_valid_regex is True
        assert len(params_regex) == 3
        assert params_regex[0] == "Aarav"

        session.rollback()


def test_process_message_queue_preflight_parameter_mismatch():
    """Verifies that messages with mismatched parameter counts fail early without calling Meta API."""
    unique_id = uuid.uuid4().hex[:6]
    with SessionLocal() as session:
        # Create template expecting 3 parameters
        tmpl = MessageTemplate(
            name=f"test_mismatch_template_{unique_id}",
            category="ANNOUNCEMENT",
            meta_template_name="announcement_v1",
            language="en",
            body="Notice for {{1}}: {{2}} by {{3}}.",
            parameters_json='["param1", "param2", "param3"]',
        )
        session.add(tmpl)
        session.flush()

        # Enqueue message with only 1 parameter
        msg = Message(
            recipient_phone="+919876543210",
            recipient_name="Test Recipient",
            category="ANNOUNCEMENT",
            status="QUEUED",
            message_body="Invalid param count message",
            parameters_json='["OnlyOneParam"]',
            template_id=tmpl.id,
        )
        session.add(msg)
        session.commit()
        msg_id = msg.id

        # Process queue
        with mock.patch("app.services.whatsapp_provider.WhatsAppCloudProvider.send_template_message") as mock_send:
            summary = process_message_queue(session, worker_id="TestValidatorWorker", batch_limit=5)
            # Send method must NEVER be invoked because preflight validation caught the mismatch
            assert mock_send.call_count == 0

        # Reload message
        reloaded = session.get(Message, msg_id)
        assert reloaded.status == "FAILED"
        assert reloaded.error_code == "PARAM_MISMATCH"
        assert "Template parameter mismatch" in reloaded.error_message

        # Clean up
        session.delete(reloaded)
        session.delete(tmpl)
        session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# 6. ATOMIC LEASE & EXPIRED LEASE RECOVERY
# ─────────────────────────────────────────────────────────────────────────────

def test_process_message_queue_expired_lease_recovery():
    """Verifies that orphaned messages left in SENDING with expired lease are claimed and processed."""
    with SessionLocal() as session:
        expired_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        msg = Message(
            recipient_phone="+919876543210",
            recipient_name="Test Recipient",
            category="CUSTOM",
            status="SENDING",
            message_body="Orphaned message from crashed worker",
            lease_holder="DeadWorker_123",
            leased_until=expired_time,
            retry_count=1,
        )
        session.add(msg)
        session.commit()
        msg_id = msg.id

        mock_result = WhatsAppSendResult(
            success=True,
            status="ACCEPTED",
            provider_message_id="wamid.HBgLMzI0",
            http_status=200,
            raw_response={"messages": [{"id": "wamid.HBgLMzI0"}]},
        )

        with mock.patch("app.services.whatsapp_provider.WhatsAppCloudProvider.send_text_message", return_value=mock_result):
            summary = process_message_queue(session, worker_id="RecoveryWorker_01", batch_limit=5)
            assert summary["accepted"] >= 1

        reloaded = session.get(Message, msg_id)
        assert reloaded.status == "ACCEPTED"
        assert reloaded.provider_message_id == "wamid.HBgLMzI0"

        # Clean up
        session.delete(reloaded)
        session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# 7. QT CONTROLLER / SUPERVISOR TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_coaching_helper_qt_supervisor(qapp):
    supervisor = CoachingHelper()
    assert supervisor.is_running() is not None

    # Test direct fallback execution
    res = supervisor.trigger_immediate_run()
    assert isinstance(res, dict)

    supervisor.stop()


def test_coaching_helper_automated_backup_check():
    """Verify that automated backup check runs without tz/tzinfo parameter error on empty or populated backup lists."""
    from app.services.coaching_helper_service import CoachingHelperEngine

    engine = CoachingHelperEngine()
    engine.last_backup_time = None

    with mock.patch("app.services.coaching_helper_service.list_backups", return_value=[]):
        with mock.patch("app.services.coaching_helper_service.create_database_backup", return_value={"success": True, "backup_filename": "test.db"}):
            engine._check_and_run_automated_backup()
            assert engine.last_backup_time is not None
            assert engine.last_backup_time.tzinfo == timezone.utc

    # Test when backup list has items
    engine.last_backup_time = None
    sample_backup = [{"timestamp_epoch": 1700000000.0, "filename": "sample.db"}]
    with mock.patch("app.services.coaching_helper_service.list_backups", return_value=sample_backup):
        with mock.patch("app.services.coaching_helper_service.create_database_backup", return_value={"success": True, "backup_filename": "test2.db"}):
            engine._check_and_run_automated_backup()
            assert engine.last_backup_time is not None
            assert engine.last_backup_time.tzinfo == timezone.utc
