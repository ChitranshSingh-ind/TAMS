import sys
import platform

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from app.ui.main_window import MainWindow

current_OS = platform.system()
def main():
    app = QApplication(sys.argv)

    # Set Inter as the primary application font
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