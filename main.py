"""
TAMS (Tuition Analysis & Management System) — Main Application Entry Point.

This module initializes the application environment, configures platform-specific
fonts, establishes global uncaught-exception crash logging with desktop alert dialogs,
and launches the primary PyQt6 GUI MainWindow.
"""

import logging
import os
import platform
import sys
import traceback

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QMessageBox

from app.database.connection import DATA_DIR
from app.ui.main_window import MainWindow

# Operating System identification for native typography and styling tokens
current_OS = platform.system()


def setup_crash_logging() -> None:
    """
    Configures persistent file and console logging for uncaught exceptions.
    Installs a custom sys.excepthook to capture fatal tracebacks and present
    a helpful error dialog to the user before terminating.
    """
    log_file = DATA_DIR / "tams_crash.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(str(log_file), encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    def excepthook(exc_type, exc_value, exc_tb):
        err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logging.critical("Uncaught application exception:\n%s", err_msg)
        sys.__excepthook__(exc_type, exc_value, exc_tb)

        # Show GUI dialog if Qt is initialized and not headless
        app = QApplication.instance()
        if app and not os.environ.get("PYTEST_CURRENT_TEST") and os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            try:
                QMessageBox.critical(
                    None,
                    "TAMS Application Error",
                    f"An unexpected error occurred:\n\n{exc_type.__name__}: {exc_value}\n\n"
                    f"Details have been recorded in the crash log:\n{log_file}",
                )
            except Exception:
                pass

    sys.excepthook = excepthook


def main():
    setup_crash_logging()
    app = QApplication(sys.argv)

    # Set appropriate application font by platform
    if current_OS == "Windows":
        app_font = QFont("Segoe UI", 10)
        app_font.setStyleHint(QFont.StyleHint.SansSerif)
        app.setFont(app_font)
    elif current_OS == "Darwin":
        app_font = QFont("San Francisco", 12)
        app_font.setStyleHint(QFont.StyleHint.SansSerif)
        app.setFont(app_font)
    else:
        app_font = QFont("Ubuntu", 10)
        app_font.setStyleHint(QFont.StyleHint.SansSerif)
        app.setFont(app_font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()