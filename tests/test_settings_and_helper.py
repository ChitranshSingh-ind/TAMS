"""
Automated Test Suite for TAMS Consolidated Settings, Backup Service, and CoachingHelper.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from PyQt6.QtWidgets import QApplication

from app.database.connection import DATABASE_PATH, DATA_DIR, SessionLocal
from app.database.models.message import MessagingConfig, NotificationRule
from app.services.backup_service import (
    create_database_backup,
    get_backup_directory,
    list_backups,
    restore_database_backup,
)
from app.services.coaching_helper_service import (
    APP_VERSION,
    SingleInstanceLock,
    check_for_updates,
    check_internet_connectivity,
    get_helper_status_file_path,
)
from app.services.messaging_service import (
    get_messaging_config,
    update_messaging_config,
)
from app.services.whatsapp_provider import (
    get_access_token,
    mask_token,
    remove_access_token,
    save_access_token,
)
from app.ui.settings_dialog import SettingsDialog


@pytest.fixture
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


# ─────────────────────────────────────────────────────────────────────────────
# 1. SETTINGS DIALOG CONSOLIDATION TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_settings_dialog_tabs_structure(qapp):
    dialog = SettingsDialog()
    assert dialog.settings_menu.count() == 5
    assert "General" in dialog.settings_menu.item(0).text()
    assert "Batches" in dialog.settings_menu.item(1).text()
    assert "WhatsApp" in dialog.settings_menu.item(2).text()
    assert "Automation" in dialog.settings_menu.item(3).text()
    assert "Backup" in dialog.settings_menu.item(4).text()
    dialog.close()


def test_settings_dialog_initial_tab_navigation(qapp):
    # Test navigating directly to WhatsApp tab (index 2)
    wa_dialog = SettingsDialog(initial_tab=2)
    assert wa_dialog.settings_menu.currentRow() == 2
    assert wa_dialog.pages.currentIndex() == 2
    wa_dialog.close()

    # Test navigating directly to Automation tab (index 3)
    auto_dialog = SettingsDialog(initial_tab=3)
    assert auto_dialog.settings_menu.currentRow() == 3
    assert auto_dialog.pages.currentIndex() == 3
    auto_dialog.close()

    # Test navigating directly to Backup tab (index 4)
    backup_dialog = SettingsDialog(initial_tab=4)
    assert backup_dialog.settings_menu.currentRow() == 4
    assert backup_dialog.pages.currentIndex() == 4
    backup_dialog.close()


def test_settings_dialog_whatsapp_save_and_load(qapp):
    dialog = SettingsDialog(initial_tab=2)

    # Modify WhatsApp inputs
    dialog.wa_env_combo.setCurrentIndex(dialog.wa_env_combo.findData("PRODUCTION"))
    dialog.wa_phone_id_input.setText("9988776655")
    dialog.wa_waba_id_input.setText("1122334455")
    dialog.wa_api_version_input.setText("v21.0")

    # Enter a temporary test token
    dialog.wa_new_token_input.setText("EAAB_TEST_TOKEN_12345")

    with mock.patch("PyQt6.QtWidgets.QMessageBox.information"):
        dialog._on_save_whatsapp_settings()

    # Verify token saved securely
    saved_token = get_access_token()
    assert saved_token == "EAAB_TEST_TOKEN_12345"
    assert mask_token(saved_token).startswith("EAAB")

    # Verify configs in DB
    with SessionLocal() as session:
        cfg = get_messaging_config(session)
        assert cfg.get("whatsapp_environment") == "PRODUCTION"
        assert cfg.get("whatsapp_phone_number_id") == "9988776655"
        assert cfg.get("whatsapp_waba_id") == "1122334455"
        assert cfg.get("whatsapp_api_version") == "v21.0"

    # Clean up test token
    remove_access_token()
    dialog.close()


def test_settings_dialog_automation_save_and_load(qapp):
    dialog = SettingsDialog(initial_tab=3)

    dialog.auto_queue_enabled_cb.setChecked(True)
    dialog.auto_retry_limit_spin.setValue(5)
    dialog.auto_backoff_base_spin.setValue(90)
    dialog.auto_polling_interval_spin.setValue(20)
    dialog.auto_max_bulk_spin.setValue(150)
    dialog.auto_quiet_hours_cb.setChecked(True)

    with mock.patch("PyQt6.QtWidgets.QMessageBox.information"):
        dialog._on_save_automation_settings()

    with SessionLocal() as session:
        cfg = get_messaging_config(session)
        assert cfg.get("queue_enabled") == "true"
        assert cfg.get("retry_limit") == "5"
        assert cfg.get("retry_backoff_base") == "90"
        assert cfg.get("helper_polling_interval") == "20"
        assert cfg.get("max_bulk_batch_size") == "150"
        assert cfg.get("quiet_hours_enabled") == "true"
        update_messaging_config(session, {"quiet_hours_enabled": "false"})

    dialog.close()


# ─────────────────────────────────────────────────────────────────────────────
# 2. DATABASE BACKUP SERVICE TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_backup_service_create_and_list():
    # Create backup with custom label
    res = create_database_backup(custom_label="test_suite")
    assert res["success"] is True
    assert res["backup_path"] is not None

    backup_file = Path(res["backup_path"])
    assert backup_file.exists()
    assert "test_suite" in backup_file.name

    # List backups
    backups = list_backups()
    assert len(backups) > 0
    found = any(b["filename"] == backup_file.name for b in backups)
    assert found is True

    # Clean up test backup file
    backup_file.unlink(missing_ok=True)


def test_backup_service_retention_policy():
    backup_dir = get_backup_directory()
    test_files = []
    for i in range(5):
        p = backup_dir / f"tams_backup_20260101_00000{i}_retention.db"
        p.touch()
        test_files.append(p)

    # Create backup with max_retention=3
    res = create_database_backup(custom_label="retention_enforce", max_retention=3)
    assert res["success"] is True

    all_backups = list_backups()
    assert len(all_backups) <= 4

    # Clean up created files
    for p in test_files:
        p.unlink(missing_ok=True)
    if res["backup_path"]:
        Path(res["backup_path"]).unlink(missing_ok=True)


def test_backup_service_restore_with_safety_snapshot():
    # 1. Create a baseline backup
    res = create_database_backup(custom_label="pre_restore_point")
    assert res["success"] is True
    backup_file = Path(res["backup_path"])

    # 2. Restore from baseline backup
    restore_res = restore_database_backup(backup_file)
    assert restore_res["success"] is True
    assert restore_res["safety_snapshot_path"] is not None

    snapshot_file = Path(restore_res["safety_snapshot_path"])
    assert snapshot_file.exists()
    assert "pre_restore_safety" in snapshot_file.name

    # Clean up and reset pool
    backup_file.unlink(missing_ok=True)
    snapshot_file.unlink(missing_ok=True)
    from app.database.connection import engine
    engine.dispose()



# ─────────────────────────────────────────────────────────────────────────────
# 3. COACHING HELPER SERVICE TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_coaching_helper_single_instance_lock():
    lock_file = DATA_DIR / "test_coaching_helper.lock"
    lock1 = SingleInstanceLock(lock_path=lock_file)
    lock2 = SingleInstanceLock(lock_path=lock_file)

    # First lock succeeds
    assert lock1.acquire() is True

    # Second lock fails (process duplication prevented)
    assert lock2.acquire() is False

    # Release first lock
    lock1.release()

    # Now second lock succeeds
    assert lock2.acquire() is True
    lock2.release()

    lock_file.unlink(missing_ok=True)


def test_coaching_helper_check_for_updates():
    res = check_for_updates()
    assert isinstance(res, dict)
    assert res.get("status") in ("up_to_date", "error", "offline")
    assert res.get("current_version") == APP_VERSION


def test_coaching_helper_status_file():
    status_file = get_helper_status_file_path()
    assert status_file.parent.exists()
    assert status_file.name == "helper_status.json"


def test_settings_dialog_helper_controls(qapp):
    """Verify that settings dialog helper action triggers execute without NameError (QTimer defined)."""
    dialog = SettingsDialog()

    with mock.patch("app.ui.settings_dialog.get_helper_process_info", return_value={"running": True, "pid": 9999}):
        with mock.patch("app.ui.settings_dialog.trigger_helper_queue_cycle") as mock_trigger:
            with mock.patch("app.ui.settings_dialog.QMessageBox.information"):
                dialog._on_process_helper_queue_clicked()
                assert mock_trigger.called

    with mock.patch("app.ui.settings_dialog.start_helper_process"):
        dialog._on_start_helper_clicked()

    with mock.patch("app.ui.settings_dialog.stop_helper_process"):
        dialog._on_stop_helper_clicked()

    with mock.patch("app.ui.settings_dialog.restart_helper_process"):
        dialog._on_restart_helper_clicked()


def test_check_for_updates_asset_extraction():
    mock_cm = mock.MagicMock()
    mock_cm.__enter__.return_value.status = 200
    mock_cm.__enter__.return_value.read.return_value = json.dumps({
        "tag_name": "v2.5.0",
        "body": "New version with bulk promotion and auto-updates.",
        "html_url": "https://github.com/ChitranshSingh-ind/TAMS/releases/tag/v2.5.0",
        "assets": [
            {
                "name": "TAMS_Setup_v2.5.0.exe",
                "size": 52428800,
                "browser_download_url": "https://github.com/ChitranshSingh-ind/TAMS/releases/download/v2.5.0/TAMS_Setup_v2.5.0.exe",
            }
        ]
    }).encode("utf-8")

    with mock.patch("urllib.request.urlopen", return_value=mock_cm):
        res = check_for_updates()
        assert res.get("status") == "update_available"
        assert res.get("latest_version") == "2.5.0"
        assert res.get("download_url") == "https://github.com/ChitranshSingh-ind/TAMS/releases/download/v2.5.0/TAMS_Setup_v2.5.0.exe"
        assert res.get("asset_name") == "TAMS_Setup_v2.5.0.exe"
        assert res.get("asset_size") == 52428800


def test_app_update_dialog_ui(qapp):
    from app.ui.app_update_dialog import AppUpdateDialog

    update_info = {
        "status": "update_available",
        "message": "Update v2.5.0 is available.",
        "current_version": "2.0.0",
        "latest_version": "2.5.0",
        "release_notes": "Changelog:\n- Auto-updater",
        "release_url": "https://github.com/ChitranshSingh-ind/TAMS/releases/tag/v2.5.0",
        "download_url": "https://github.com/ChitranshSingh-ind/TAMS/releases/download/v2.5.0/TAMS_Setup_v2.5.0.exe",
        "asset_name": "TAMS_Setup_v2.5.0.exe",
        "asset_size": 52428800,
    }

    dlg = AppUpdateDialog(update_info)
    assert dlg.windowTitle() == "Update Available - TAMS v2.5.0"
    assert "Changelog" in dlg.notes_edit.toPlainText()
    assert dlg.update_btn.isEnabled()
    assert dlg.cancel_btn.text() == "Remind Me Later"


def test_main_window_auto_check_updates_on_startup(qapp):
    from app.ui.main_window import MainWindow
    from app.ui.app_update_dialog import AppUpdateDialog

    update_payload = {
        "status": "update_available",
        "message": "Update v2.5.0 is available.",
        "current_version": "2.1.3",
        "latest_version": "2.5.0",
        "release_notes": "New features",
    }

    win = MainWindow()
    win.show()

    dialog_opened = []

    def mock_dialog_exec(self):
        dialog_opened.append(self.update_info)
        return 0

    with mock.patch("app.services.coaching_helper_service.check_for_updates", return_value=update_payload):
        with mock.patch.object(AppUpdateDialog, "exec", mock_dialog_exec):
            # Temporarily unmask test env check inside the method
            with mock.patch.dict(os.environ, {}, clear=False):
                if "PYTEST_CURRENT_TEST" in os.environ:
                    del os.environ["PYTEST_CURRENT_TEST"]
                try:
                    win.check_for_system_updates_on_startup()
                    assert hasattr(win, "_startup_update_worker")
                    win._startup_update_worker.wait(5000)
                    qapp.processEvents()
                    assert len(dialog_opened) == 1
                    assert dialog_opened[0]["latest_version"] == "2.5.0"
                finally:
                    os.environ["PYTEST_CURRENT_TEST"] = "1"

    win.close()


def test_main_window_auto_check_updates_disabled_by_config(qapp):
    from app.ui.main_window import MainWindow

    win = MainWindow()
    win.show()

    with SessionLocal() as session:
        update_messaging_config(session, {"auto_check_updates_on_startup": "false"})

    with mock.patch.dict(os.environ, {}, clear=False):
        if "PYTEST_CURRENT_TEST" in os.environ:
            del os.environ["PYTEST_CURRENT_TEST"]
        try:
            win.check_for_system_updates_on_startup()
            assert not hasattr(win, "_startup_update_worker")
        finally:
            os.environ["PYTEST_CURRENT_TEST"] = "1"
            with SessionLocal() as session:
                update_messaging_config(session, {"auto_check_updates_on_startup": "true"})

    win.close()


def test_settings_dialog_auto_update_toggle(qapp):
    dialog = SettingsDialog()
    dialog.load_backup_page()
    assert hasattr(dialog, "auto_check_updates_cb")
    assert dialog.auto_check_updates_cb.isChecked() is True

    # Toggle off
    dialog.auto_check_updates_cb.setChecked(False)
    with SessionLocal() as session:
        cfg = get_messaging_config(session)
        assert cfg.get("auto_check_updates_on_startup") == "false"

    # Toggle back on
    dialog.auto_check_updates_cb.setChecked(True)
    with SessionLocal() as session:
        cfg = get_messaging_config(session)
        assert cfg.get("auto_check_updates_on_startup") == "true"

    dialog.close()


