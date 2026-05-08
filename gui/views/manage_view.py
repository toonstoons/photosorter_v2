from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


class ManageView(QWidget):
    """Placeholder for table management features (delete duplicates, etc.)."""

    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        label = QLabel("Manage Table — coming soon")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
