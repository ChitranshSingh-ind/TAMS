import sys

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from app.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    # Set Inter as the primary application font
    app_font = QFont("Inter", 10)
    app_font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(app_font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()