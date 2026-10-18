"""Face Attendance - desktop app entry point.   Run:  python main.py"""
import sys

# On Windows, torch must be imported BEFORE PySide6, otherwise some setups fail with
# "DLL initialization routine failed". The try/except keeps the UI usable if torch is missing.
try:
    import torch  # noqa: F401
except Exception:
    pass

from PySide6.QtWidgets import QApplication

from ui import theme
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Face Attendance")
    app.setStyleSheet(theme.stylesheet())
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
