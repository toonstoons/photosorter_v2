from PySide6.QtWidgets import QMainWindow, QStackedWidget
from PySide6.QtGui import QAction

from gui.views.browse_view import BrowseView
from gui.views.manage_view import ManageView


class MainWindow(QMainWindow):
    def __init__(self, db_path: str) -> None:
        super().__init__()
        self.setWindowTitle("PhotoSorter — Duplicate Checker")
        self.resize(1024, 600)

        # --- Central stacked widget (one frame per view) ---
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # --- Register views ---
        self._browse_view = BrowseView(db_path)
        self._manage_view = ManageView()

        self._stack.addWidget(self._browse_view)   # index 0
        self._stack.addWidget(self._manage_view)   # index 1

        # --- Menu bar ---
        menu = self.menuBar()

        browse_action = QAction("Browse Table", self)
        browse_action.triggered.connect(lambda: self._stack.setCurrentIndex(0))
        menu.addAction(browse_action)

        manage_action = QAction("Manage Table", self)
        manage_action.triggered.connect(lambda: self._stack.setCurrentIndex(1))
        menu.addAction(manage_action)

        # Start on the browse view
        self._stack.setCurrentIndex(0)
