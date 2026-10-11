"""
Standalone CoachingHelper Companion Application for TAMS.
Entry point for running the background helper on Windows and Linux.
Provides system tray notifications, pause/resume controls,
background queue processing, automated SQLite backups, and single-instance protection.

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

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("TAMS.CoachingHelper")

# Ensure repository root is in python path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database.connection import DATABASE_PATH, DATA_DIR
from app.services.backup_service import create_database_backup
from app.services.coaching_helper_service import (
    APP_VERSION,
    CoachingHelperEngine,
    check_for_updates,
    is_helper_process_running,
)


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
    """Runs CoachingHelper with a Windows/Desktop System Tray icon."""
    try:
        from PyQt6.QtCore import QTimer
        from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
        from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon
    except ImportError:
        logger.warning("PyQt6 not installed or GUI libraries unavailable. Falling back to headless mode.")
        run_headless()
        return

    # Check if display / tray is supported
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

    # Create tray icon
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

    # Title header
    title_action = QAction(f"TAMS CoachingHelper v{APP_VERSION}", menu)
    title_action.setEnabled(False)
    menu.addAction(title_action)

    status_action = QAction("Status: Initializing...", menu)
    status_action.setEnabled(False)
    menu.addAction(status_action)

    menu.addSeparator()

    # Process Now action
    def trigger_immediate_process():
        res = engine.run_single_cycle()
        summary = res.get("summary", {})
        processed = summary.get("processed", 0)
        tray_icon.showMessage(
            "TAMS Queue Processed",
            f"Processed {processed} messages. Accepted: {summary.get('accepted', 0)}, Failed: {summary.get('failed', 0)}",
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    process_now_action = QAction("⚡ Process Queue Now", menu)
    process_now_action.triggered.connect(trigger_immediate_process)
    menu.addAction(process_now_action)

    # Pause / Resume action
    pause_action = QAction("⏸ Pause Processing", menu)

    def toggle_pause():
        if engine.is_paused:
            engine.resume()
            pause_action.setText("⏸ Pause Processing")
            tray_icon.setIcon(make_icon("#012D54"))
        else:
            engine.pause()
            pause_action.setText("▶ Resume Processing")
            tray_icon.setIcon(make_icon("#615F4B"))

    pause_action.triggered.connect(toggle_pause)
    menu.addAction(pause_action)

    # Backup action
    def trigger_backup():
        res = create_database_backup(custom_label="tray_manual", max_retention=10)
        if res["success"]:
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

    backup_action = QAction("📦 Create Database Backup Now", menu)
    backup_action.triggered.connect(trigger_backup)
    menu.addAction(backup_action)

    # Update check action
    def trigger_update_check():
        info = check_for_updates()
        tray_icon.showMessage(
            "TAMS Version Check",
            f"Current: v{info['current_version']} (Up to date)",
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    update_action = QAction("🔄 Check for Updates", menu)
    update_action.triggered.connect(trigger_update_check)
    menu.addAction(update_action)

    menu.addSeparator()

    # Open TAMS GUI
    def open_main_app():
        main_script = ROOT_DIR / "main.py"
        try:
            subprocess.Popen([sys.executable, str(main_script)])
        except Exception as e:
            logger.error("Could not launch main TAMS application: %s", e)

    open_tams_action = QAction("🚀 Open TAMS Application", menu)
    open_tams_action.triggered.connect(open_main_app)
    menu.addAction(open_tams_action)

    menu.addSeparator()

    # Exit action
    def exit_helper():
        engine.stop()
        tray_icon.hide()
        app.quit()

    exit_action = QAction("❌ Exit CoachingHelper", menu)
    exit_action.triggered.connect(exit_helper)
    menu.addAction(exit_action)

    tray_icon.setContextMenu(menu)
    tray_icon.show()

    # Periodic background timer
    timer = QTimer()

    def on_timer():
        res = engine.run_single_cycle()
        st = res.get("status", "RUNNING")
        status_action.setText(f"Status: {st} ({'Online' if engine.last_online_status else 'Offline'})")

    timer.timeout.connect(on_timer)
    timer.start(15000)  # 15 seconds

    # Initial cycle
    QTimer.singleShot(500, on_timer)

    # Clean app exit hook
    app.aboutToQuit.connect(engine.stop)

    sys.exit(app.exec())


def main():
    parser = argparse.ArgumentParser(description="TAMS CoachingHelper Background Service")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without system tray GUI (ideal for daemon/background mode)",
    )
    args = parser.parse_args()

    if args.headless or not os.environ.get("DISPLAY", "") and sys.platform != "win32":
        run_headless()
    else:
        run_tray()


if __name__ == "__main__":
    main()
