"""PySide6 action-history viewer."""

from PySide6.QtCore import QSize, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from src.config import APP_ICON_FILES, resource_path
from src.services.history import clear_history_entries, format_history_entry, get_history_entries

FILTERS = ("All", "Connection", "Champion Select", "Summs", "Error")


def _history_icon_path(entry: dict[str, str]) -> str:
    content = f"{entry.get('category', '')} {entry.get('message', '')}".lower()
    if "spell" in content or "summoner" in content:
        return APP_ICON_FILES["spells"]
    if "rune" in content:
        return APP_ICON_FILES["runes"]
    if "skin" in content:
        return APP_ICON_FILES["skin"]
    if "champion" in content or "pick" in content or "ban" in content:
        return APP_ICON_FILES["champion_select"]
    if "connect" in content or "client" in content:
        return APP_ICON_FILES["connection"]
    return APP_ICON_FILES["activity"]


class HistoryDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("OTP LOL history")
        self.resize(820, 560)
        root = QVBoxLayout(self)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Filter"))
        self.filter = QComboBox()
        self.filter.addItems(FILTERS)
        self.filter.currentTextChanged.connect(self.refresh)
        controls.addWidget(self.filter)
        controls.addStretch()
        clear = QPushButton("Clear history")
        clear.clicked.connect(self.clear_history)
        controls.addWidget(clear)
        root.addLayout(controls)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Time", "Level", "Category", "Action"])
        self.tree.setColumnWidth(0, 90)
        self.tree.setColumnWidth(1, 90)
        self.tree.setColumnWidth(2, 150)
        self.tree.setIconSize(QSize(22, 22))
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setRootIsDecorated(True)
        root.addWidget(self.tree, 1)

        self.empty = QLabel("No local automation events yet.")
        self.empty.setProperty("secondary", True)
        root.addWidget(self.empty)
        self.timer = QTimer(self)
        self.timer.setInterval(1500)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.refresh()

    def refresh(self) -> None:
        selected_filter = self.filter.currentText() or "All"
        entries = [format_history_entry(entry) for entry in get_history_entries(150)]
        if selected_filter != "All":
            entries = [entry for entry in entries if entry["category"] == selected_filter]
        self.tree.clear()
        for entry in entries:
            item = QTreeWidgetItem(
                [entry["time"], entry["level_label"], entry["category"], entry["message"]]
            )
            item.setIcon(0, QIcon(resource_path(_history_icon_path(entry))))
            for line in entry["detail_lines"]:
                item.addChild(QTreeWidgetItem(["", "", "", line]))
            self.tree.addTopLevelItem(item)
        self.empty.setVisible(not entries)

    def clear_history(self) -> None:
        answer = QMessageBox.question(
            self,
            "Clear history",
            "Delete the local automation history?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        clear_history_entries()
        self.refresh()

    def closeEvent(self, event) -> None:
        self.timer.stop()
        super().closeEvent(event)
