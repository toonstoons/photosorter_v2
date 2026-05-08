import sys
import os
from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "duplicate_check.sqlite")


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow(db_path=DB_PATH)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
