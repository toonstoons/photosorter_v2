from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTableView, QLabel, QComboBox,
)
from PySide6.QtSql import QSqlDatabase, QSqlTableModel
from PySide6.QtCore import Qt


class BrowseView(QWidget):
    """Displays any table from the SQLite database in a sortable table view."""

    def __init__(self, db_path: str) -> None:
        super().__init__()
        self._db_path = db_path
        self._db = self._open_db(db_path)

        self._build_ui()
        self._populate_table_selector()

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _open_db(db_path: str) -> QSqlDatabase:
        db = QSqlDatabase.addDatabase("QSQLITE", "browse_connection")
        db.setDatabaseName(db_path)
        if not db.open():
            raise RuntimeError(f"Cannot open database: {db_path}")
        return db

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Top bar: label + table selector
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Table:"))

        self._table_selector = QComboBox()
        self._table_selector.currentTextChanged.connect(self._load_table)
        top_bar.addWidget(self._table_selector)
        top_bar.addStretch()

        root.addLayout(top_bar)

        # Table view
        self._model = QSqlTableModel(db=self._db)
        self._model.setEditStrategy(QSqlTableModel.EditStrategy.OnManualSubmit)

        self._table_view = QTableView()
        self._table_view.setModel(self._model)
        self._table_view.setSortingEnabled(True)
        self._table_view.horizontalHeader().setStretchLastSection(True)
        self._table_view.setAlternatingRowColors(True)
        self._table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)

        root.addWidget(self._table_view)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _populate_table_selector(self) -> None:
        tables = self._db.tables()
        self._table_selector.addItems(tables)
        if tables:
            self._load_table(tables[0])

    def _load_table(self, table_name: str) -> None:
        if not table_name:
            return
        self._model.setTable(table_name)
        self._model.select()
        self._table_view.resizeColumnsToContents()
