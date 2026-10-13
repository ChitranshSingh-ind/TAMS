"""
Standalone CoachingHelper Companion Application for TAMS.
Entry point for running the background helper on Windows and Linux.
Provides system tray notifications, pause/resume controls,
background queue processing, automated SQLite backups, IPC control,
and single-instance protection. All queue operations are executed in a background QThread.

Usage:
  python coaching_helper_main.py             # Runs with System Tray (if available)
  python coaching_helper_main.py --headless  # Runs as background daemon without GUI
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import subprocess
import sys
from pathlib import Path

# Ensure repository root is in python path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database.connection import DATABASE_PATH
from app.services.backup_service import create_database_backup
from app.services.coaching_helper_service import (
    APP_VERSION,
    CoachingHelperEngine,
    check_for_updates,
    setup_helper_logging,
)

# Initialize bounded rotating logging
setup_helper_logging()
logger = logging.getLogger("TAMS.CoachingHelper")


def run_headless():
    """Runs CoachingHelper as a headless background process."""
    engine = CoachingHelperEngine(poll_interval=15)

    if not engine.start():
        print("⚠️ CoachingHelper is already running in another process. Exiting.")
        sys.exit(0)

    def sig_handler(signum, frame):
        logger.info("Signal %s received. Stopping CoachingHelper...", signum)
        engine.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    print(f"✅ CoachingHelper v{APP_VERSION} running in background (PID: {os.getpid()})")
    print(f"📁 Database: {DATABASE_PATH}")
    print("Press Ctrl+C to stop.")

    try:
        engine.run_loop()
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop()


def run_tray():
    """Runs CoachingHelper with a Windows/Desktop System Tray icon and non-blocking worker thread."""
    try:
        from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal
        from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
        from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon
    except ImportError:
        logger.warning("PyQt6 not installed or GUI libraries unavailable. Falling back to headless mode.")
        run_headless()
        return

    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        logger.info("System tray is not available in current environment. Running headless.")
        run_headless()
        return

    engine = CoachingHelperEngine(poll_interval=15)
    if not engine.start():
        QMessageBox.information(
            None,
            "TAMS CoachingHelper",
            "CoachingHelper is already running in the background.",
        )
        sys.exit(0)

    # ─────────────────────────────────────────────────────────────────────────
    # Non-blocking Worker Thread for Queue Processing Cycles
    # ─────────────────────────────────────────────────────────────────────────
    class HelperWorkerThread(QThread):
        cycle_done = pyqtSignal(dict, bool)  # (result_dict, is_manual_trigger)
        status_updated = pyqtSignal(str, bool)  # (status_text, is_online)

        def __init__(self, engine_instance: CoachingHelperEngine, parent: QObject | None = None):
            super().__init__(parent)
            self.engine = engine_instance
            self._pending_manual = False
            self._running = True

        def trigger_cycle(self, manual: bool = False):
            if manual:
                self._pending_manual = True
            if not self.isRunning():
                self.start()

        def stop(self):
            self._running = False
            self.wait(3000)

        def run(self):
            manual = self._pending_manual
            self._pending_manual = False

            # Check IPC commands first
            self.engine.check_and_handle_ipc_commands()
            if not self.engine.is_running:
                return

            res = self.engine.run_single_cycle()
            st = res.get("status", "RUNNING")
            online = self.engine.last_online_status
            self.status_updated.emit(st, online)
            self.cycle_done.emit(res, manual)

    worker = HelperWorkerThread(engine)

    # ─────────────────────────────────────────────────────────────────────────
    # Tray Icon & Visuals
    # ─────────────────────────────────────────────────────────────────────────
    tray_icon = QSystemTrayIcon()

    def make_icon(color_hex="#012D54"):
        pix = QPixmap(32, 32)
        pix.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(color_hex))
        painter.setPen(QColor("#D9B85F"))
        painter.drawEllipse(2, 2, 28, 28)
        painter.setPen(QColor("#FEFEFE"))
        painter.drawText(pix.rect(), 0x0084, "T")  # AlignCenter
        painter.end()
        return QIcon(pix)

    tray_icon.setIcon(make_icon("#012D54"))
    tray_icon.setToolTip(f"TAMS CoachingHelper v{APP_VERSION} — Running")

    # Tray Menu
    menu = QMenu()

    title_action = QAction(f"TAMS CoachingHelper v{APP_VERSION}", menu)
    title_action.setEnabled(False)
    menu.addAction(title_action)

    status_action = QAction("Status: Initializing...", menu)
    status_action.setEnabled(False)
    menu.addAction(status_action)

    menu.addSeparator()

    # Manual process queue action
    def on_manual_process_clicked():
        status_action.setText("Status: Processing queue...")
        worker.trigger_cycle(manual=True)

    process_now_action = QAction("⚡ Process Queue Now", menu)
    process_now_action.triggered.connect(on_manual_process_clicked)
    menu.addAction(process_now_action)

    # Pause / Resume action
    pause_action = QAction("⏸ Pause Processing", menu)

    def toggle_pause():
        if engine.is_paused:
            engine.resume()
            pause_action.setText("⏸ Pause Processing")
            tray_icon.setIcon(make_icon("#012D54"))
            status_action.setText("Status: RUNNING")
        else:
            engine.pause()
            pause_action.setText("▶ Resume Processing")
            tray_icon.setIcon(make_icon("#615F4B"))
            status_action.setText("Status: PAUSED")

    pause_action.triggered.connect(toggle_pause)
    menu.addAction(pause_action)

    # Backup action (in background)
    class BackupWorkerThread(QThread):
        backup_done = pyqtSignal(dict)

        def run(self):
            res = create_database_backup(custom_label="tray_manual", max_retention=10)
            self.backup_done.emit(res)

    backup_worker = BackupWorkerThread()

    def on_backup_done(res):
        if res.get("success"):
            tray_icon.showMessage(
                "Backup Successful",
                f"Saved to {res.get('backup_filename')}",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
        else:
            tray_icon.showMessage(
                "Backup Failed",
                res.get("error", "Unknown error"),
                QSystemTrayIcon.MessageIcon.Warning,
                4000,
            )

    backup_worker.backup_done.connect(on_backup_done)

    backup_action = QAction("📦 Create Database Backup Now", menu)
    backup_action.triggered.connect(backup_worker.start)
    menu.addAction(backup_action)

    # Update check action (non-blocking)
    class UpdateWorkerThread(QThread):
        update_done = pyqtSignal(dict)

        def run(self):
            res = check_for_updates()
            self.update_done.emit(res)

    update_worker = UpdateWorkerThread()

    def on_update_done(info):
        is_newer = not info.get("is_up_to_date", True)
        tray_icon.showMessage(
            "TAMS Version Check",
            f"Latest: v{info.get('latest_version')} — {info.get('message')}",
            QSystemTrayIcon.MessageIcon.Information if not is_newer else QSystemTrayIcon.MessageIcon.Warning,
            4000,
        )

    update_worker.update_done.connect(on_update_done)

    update_action = QAction("🔄 Check for Updates", menu)
    update_action.triggered.connect(update_worker.start)
    menu.addAction(update_action)

    menu.addSeparator()

    # Open TAMS GUI
    def open_main_app():
        if getattr(sys, "frozen", False):
            tams_exe = Path(sys.executable).parent / "TAMS.exe"
            cmd = [str(tams_exe)] if tams_exe.exists() else [sys.executable]
        else:
            main_script = ROOT_DIR / "main.py"
            cmd = [sys.executable, str(main_script)]
        try:
            subprocess.Popen(cmd)
        except Exception as e:
            logger.error("Could not launch main TAMS application: %s", e)

    open_tams_action = QAction("🚀 Open TAMS Application", menu)
    open_tams_action.triggered.connect(open_main_app)
    menu.addAction(open_tams_action)

    menu.addSeparator()

    # Exit action
    def exit_helper():
        worker.stop()
        engine.stop()
        tray_icon.hide()
        app.quit()

    exit_action = QAction("❌ Exit CoachingHelper", menu)
    exit_action.triggered.connect(exit_helper)
    menu.addAction(exit_action)

    tray_icon.setContextMenu(menu)
    tray_icon.show()

    # Connect worker signals
    def on_status_updated(st: str, online: bool):
        status_action.setText(f"Status: {st} ({'Online' if online else 'Offline'})")
        if not engine.is_running:
            app.quit()

    def on_cycle_done(res: dict, manual: bool):
        summary = res.get("summary", {})
        processed = summary.get("processed", 0)
        accepted = summary.get("accepted", 0)
        failed = summary.get("failed", 0)

        if manual:
            tray_icon.showMessage(
                "TAMS Queue Processed",
                f"Processed: {processed} | Accepted: {accepted} | Failed: {failed}",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
        elif processed > 0:
            tray_icon.showMessage(
                "TAMS Background Delivery",
                f"Dispatched {processed} messages ({accepted} accepted by Meta).",
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )

    worker.status_updated.connect(on_status_updated)
    worker.cycle_done.connect(on_cycle_done)

    # Periodic background timer (triggers worker thread)
    timer = QTimer()

    def on_timer_tick():
        if not worker.isRunning():
            worker.trigger_cycle(manual=False)

    timer.timeout.connect(on_timer_tick)
    timer.start(15000)  # 15 seconds

    # Initial cycle shortly after event loop starts
    QTimer.singleShot(1000, on_timer_tick)

    # Clean app exit hook
    app.aboutToQuit.connect(exit_helper)

    sys.exit(app.exec())


def main():
    parser = argparse.ArgumentParser(description="TAMS CoachingHelper Background Service")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without system tray GUI (ideal for daemon/background mode)",
    )
    args = parser.parse_args()

    if args.headless or (not os.environ.get("DISPLAY", "") and sys.platform != "win32"):
        run_headless()
    else:
        run_tray()


if __name__ == "__main__":
    main()
