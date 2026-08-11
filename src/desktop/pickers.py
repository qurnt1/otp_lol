"""PySide6 champion, spell, rune, and skin selection dialogs."""

import weakref
from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)
from shiboken6 import isValid

from src.config import SUMMONER_SPELL_LIST
from src.services.champion_roles import champion_matches_role, sort_champions_for_role
from src.services.runes import get_rune_page_icon_paths, safe_int, split_rune_page_perk_ids, strip_active_suffix
from src.services.skin_catalog import merge_catalog_and_owned_skins, skin_selection_warning, sort_skins_for_display

from .images import pil_to_qimage, qpixmap_from_image
from .tasks import TaskRunner

_ROLE_LABELS = {
    "GLOBAL": "All",
    "TOP": "Top",
    "JUNGLE": "Jungle",
    "MIDDLE": "Mid",
    "BOTTOM": "ADC",
    "UTILITY": "Support",
}


def _guarded_callback(owner: QDialog, method_name: str):
    owner_ref = weakref.ref(owner)

    def callback(value: Any) -> None:
        target = owner_ref()
        if target is not None and isValid(target):
            getattr(target, method_name)(value)

    return callback


def _websocket_is_active(websocket_manager: Any) -> bool:
    if websocket_manager is None:
        return False
    active = getattr(websocket_manager, "is_active", False)
    return bool(active() if callable(active) else active)


class ChampionPickerDialog(QDialog):
    champion_selected = Signal(str)

    def __init__(
        self,
        *,
        data_dragon: Any,
        task_runner: TaskRunner,
        excluded: set[str] | None = None,
        current: str = "",
        title: str = "Select champion",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(780, 680)
        self.data_dragon = data_dragon
        self.task_runner = task_runner
        self.excluded = set(excluded or ())
        self.current = current
        self._icons: dict[str, QIcon] = {}

        root = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.role = QComboBox()
        for value, label in _ROLE_LABELS.items():
            self.role.addItem(label, value)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search champions")
        self.result_count = QLabel()
        self.result_count.setProperty("secondary", True)
        controls.addWidget(self.role)
        controls.addWidget(self.search, 1)
        controls.addWidget(self.result_count)
        root.addLayout(controls)

        self.list = QListWidget()
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setMovement(QListWidget.Movement.Static)
        self.list.setUniformItemSizes(True)
        self.list.setGridSize(QSize(118, 88))
        self.list.setIconSize(QSize(46, 46))
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        root.addWidget(self.list, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.search.textChanged.connect(self._refresh)
        self.role.currentIndexChanged.connect(self._refresh)
        self.list.itemActivated.connect(self._choose)
        self.list.itemDoubleClicked.connect(self._choose)
        self._refresh()
        self._load_icons()

    def _candidate_names(self) -> list[str]:
        names = [name for name in self.data_dragon.all_names if name not in self.excluded]
        role = str(self.role.currentData() or "GLOBAL")
        if role != "GLOBAL":
            names = [name for name in names if champion_matches_role(self.data_dragon, name, role)]
        query = self.search.text().strip().casefold()
        if query:
            names = [name for name in names if query in name.casefold()]
        return sort_champions_for_role(names, self.data_dragon, role)

    def _refresh(self) -> None:
        selected_name = self.current
        current_item = self.list.currentItem()
        if current_item:
            selected_name = str(current_item.data(Qt.ItemDataRole.UserRole) or "")

        self.list.clear()
        none_item = QListWidgetItem("(None)")
        none_item.setData(Qt.ItemDataRole.UserRole, "(None)")
        self.list.addItem(none_item)
        names = self._candidate_names()
        for name in names:
            item = QListWidgetItem(self._icons.get(name, QIcon()), name)
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.list.addItem(item)
            if name == selected_name:
                item.setSelected(True)
                self.list.setCurrentItem(item)
        if selected_name == "(None)":
            none_item.setSelected(True)
            self.list.setCurrentItem(none_item)
        self.result_count.setText(f"{len(names)} champions")

    def _load_icons(self) -> None:
        names = list(self.data_dragon.all_names)

        def load() -> dict[str, Any]:
            return {
                name: pil_to_qimage(self.data_dragon.get_champion_icon(name), size=(46, 46))
                for name in names
            }

        self.task_runner.submit(load, _guarded_callback(self, "_apply_icons"))

    def _apply_icons(self, images: Mapping[str, Any]) -> None:
        self._icons = {
            name: QIcon(qpixmap_from_image(image))
            for name, image in images.items()
            if image is not None
        }
        self._refresh()

    def _choose(self, item: QListWidgetItem) -> None:
        value = str(item.data(Qt.ItemDataRole.UserRole) or "(None)")
        self.champion_selected.emit(value)
        self.accept()


class SpellPickerDialog(QDialog):
    spell_selected = Signal(str)

    def __init__(
        self,
        *,
        data_dragon: Any,
        task_runner: TaskRunner,
        current: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select summoner spell")
        self.resize(420, 520)
        self.data_dragon = data_dragon
        self.task_runner = task_runner
        root = QVBoxLayout(self)
        self.list = QListWidget()
        self.list.setIconSize(QSize(36, 36))
        for spell in SUMMONER_SPELL_LIST:
            item = QListWidgetItem(spell)
            item.setData(Qt.ItemDataRole.UserRole, spell)
            self.list.addItem(item)
            if spell == current:
                self.list.setCurrentItem(item)
        self.list.itemActivated.connect(self._choose)
        self.list.itemDoubleClicked.connect(self._choose)
        root.addWidget(self.list)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._load_icons()

    def _load_icons(self) -> None:
        def load() -> dict[str, Any]:
            return {
                spell: pil_to_qimage(self.data_dragon.get_summoner_icon(spell), size=(36, 36))
                for spell in SUMMONER_SPELL_LIST
                if spell != "(None)"
            }

        self.task_runner.submit(load, _guarded_callback(self, "_apply_icons"))

    def _apply_icons(self, images: Mapping[str, Any]) -> None:
        for index in range(self.list.count()):
            item = self.list.item(index)
            image = images.get(str(item.data(Qt.ItemDataRole.UserRole)))
            if image is not None:
                item.setIcon(QIcon(qpixmap_from_image(image)))

    def _choose(self, item: QListWidgetItem) -> None:
        self.spell_selected.emit(str(item.data(Qt.ItemDataRole.UserRole) or "(None)"))
        self.accept()


class RunePickerDialog(QDialog):
    rune_selected = Signal(object)

    def __init__(
        self,
        *,
        data_dragon: Any,
        websocket_manager: Any,
        task_runner: TaskRunner,
        slot_data: Mapping[str, Any],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Rune page")
        self.resize(560, 620)
        self.data_dragon = data_dragon
        self.websocket_manager = websocket_manager
        self.task_runner = task_runner
        self.slot_data = dict(slot_data)
        self.styles: dict[Any, Any] = {}
        self._page_icon_paths: dict[int, tuple[str, str]] = {}

        root = QVBoxLayout(self)
        header = QHBoxLayout()
        self.status = QLabel("Loading rune pages…")
        self.status.setProperty("secondary", True)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        header.addWidget(self.status, 1)
        header.addWidget(refresh)
        root.addLayout(header)

        self.list = QListWidget()
        self.list.setIconSize(QSize(38, 38))
        self.list.currentItemChanged.connect(self._show_details)
        root.addWidget(self.list, 1)
        self.details = QLabel("Select a page to inspect it.")
        self.details.setWordWrap(True)
        self.details.setProperty("secondary", True)
        root.addWidget(self.details)
        self.auto_apply = QCheckBox("Apply this rune page during champion select")
        self.auto_apply.setChecked(bool(self.slot_data.get("rune_auto_apply", True)))
        root.addWidget(self.auto_apply)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.refresh()

    def refresh(self) -> None:
        self.status.setText("Loading rune pages…")
        self.list.setEnabled(False)

        def load() -> dict[str, Any]:
            pages = self.websocket_manager.fetch_rune_pages()
            styles = self.websocket_manager.fetch_rune_styles()
            page_icon_paths: dict[int, tuple[str, str]] = {}
            page_images: dict[int, Any] = {}
            compose_rune = getattr(self.data_dragon, "compose_rune_button_icon", None)
            if callable(compose_rune) and isinstance(pages, list) and isinstance(styles, Mapping):
                for page in pages:
                    if not isinstance(page, Mapping):
                        continue
                    page_id = safe_int(page.get("id"))
                    icon_paths = get_rune_page_icon_paths(page, styles, self.data_dragon)
                    page_icon_paths[page_id] = icon_paths
                    page_images[page_id] = pil_to_qimage(
                        compose_rune(icon_paths[0], icon_paths[1], size=38)
                        if icon_paths[0]
                        else None,
                        size=(38, 38),
                    )
            return {
                "pages": pages,
                "styles": styles,
                "active": self.websocket_manager.fetch_current_rune_page(),
                "page_icon_paths": page_icon_paths,
                "page_images": page_images,
            }

        self.task_runner.submit(
            load,
            _guarded_callback(self, "_apply_pages"),
            _guarded_callback(self, "_show_error"),
        )

    def _show_error(self, message: str) -> None:
        self.status.setText(f"Unable to load rune pages: {message}")

    def _apply_pages(self, payload: Mapping[str, Any]) -> None:
        pages = payload.get("pages", [])
        self.styles = dict(payload.get("styles", {})) if isinstance(payload.get("styles"), Mapping) else {}
        self._page_icon_paths = dict(payload.get("page_icon_paths", {}))
        page_images = payload.get("page_images", {})
        active = payload.get("active", {})
        active_id = safe_int(active.get("id")) if isinstance(active, Mapping) else 0
        selected_id = safe_int(self.slot_data.get("rune_page_id"))
        self.list.clear()
        if not isinstance(pages, list) or not pages:
            self.status.setText("No rune pages available. Connect the League client and refresh.")
            self.list.setEnabled(False)
            return
        self.list.setEnabled(True)
        for page in pages:
            if not isinstance(page, dict):
                continue
            page_id = safe_int(page.get("id"))
            label = strip_active_suffix(str(page.get("name") or f"Rune page {page_id}"))
            if page_id == active_id:
                label += " (active)"
            item = QListWidgetItem(label)
            page_image = page_images.get(page_id) if isinstance(page_images, Mapping) else None
            if page_image is not None:
                item.setIcon(QIcon(qpixmap_from_image(page_image)))
            item.setData(Qt.ItemDataRole.UserRole, page)
            self.list.addItem(item)
            if page_id == selected_id:
                self.list.setCurrentItem(item)
        self.status.setText(f"{self.list.count()} rune pages available")

    def _show_details(self, current: QListWidgetItem | None) -> None:
        if current is None:
            return
        page = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(page, Mapping):
            return
        primary, secondary, shards = split_rune_page_perk_ids(page)
        names = [self.data_dragon.get_rune_perk_name(perk_id) or str(perk_id) for perk_id in primary + secondary]
        self.details.setText(
            f"Primary: {', '.join(names[:4]) or 'Unknown'}\n"
            f"Secondary: {', '.join(names[4:]) or 'Unknown'}\n"
            f"Shards: {', '.join(map(str, shards)) or 'Unknown'}"
        )

    def _save(self) -> None:
        current = self.list.currentItem()
        if current is None:
            QMessageBox.information(self, "Rune page", "Select a rune page first.")
            return
        page = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(page, Mapping):
            return
        page_id = safe_int(page.get("id"))
        icon_paths = self._page_icon_paths.get(page_id)
        if icon_paths is None:
            icon_paths = get_rune_page_icon_paths(page, self.styles, self.data_dragon)
        keystone, sub_style = icon_paths
        self.rune_selected.emit(
            {
                "rune_page_id": safe_int(page.get("id")),
                "rune_page_name": strip_active_suffix(str(page.get("name") or "")),
                "rune_auto_apply": self.auto_apply.isChecked(),
                "rune_keystone_path": keystone,
                "rune_sub_style_icon_path": sub_style,
            }
        )
        self.accept()


class SkinPickerDialog(QDialog):
    skin_selected = Signal(object)

    def __init__(
        self,
        *,
        data_dragon: Any,
        websocket_manager: Any,
        task_runner: TaskRunner,
        champion_name: str,
        slot_data: Mapping[str, Any],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{champion_name} skins")
        self.resize(700, 650)
        self.data_dragon = data_dragon
        self.websocket_manager = websocket_manager
        self.task_runner = task_runner
        self.champion_name = champion_name
        self.slot_data = dict(slot_data)
        self.skins: list[dict[str, Any]] = []
        self.lcu_available = _websocket_is_active(websocket_manager)
        self._updating = False

        root = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel("Mode"))
        self.mode = QComboBox()
        self.mode.addItem("Off", "none")
        self.mode.addItem("Fixed skin", "fixed")
        self.mode.addItem("Random pool", "random")
        mode_index = self.mode.findData(str(self.slot_data.get("skin_mode") or "none"))
        self.mode.setCurrentIndex(max(mode_index, 0))
        refresh = QPushButton("Refresh ownership")
        refresh.clicked.connect(self.refresh)
        header.addWidget(self.mode)
        header.addStretch()
        header.addWidget(refresh)
        root.addLayout(header)
        self.status = QLabel("Loading skins…")
        self.status.setProperty("secondary", True)
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Skin", "Availability"])
        self.tree.setRootIsDecorated(False)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.itemChanged.connect(self._item_changed)
        root.addWidget(self.tree, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.mode.currentIndexChanged.connect(self._render)
        self.refresh()

    def refresh(self) -> None:
        self.status.setText("Loading skin catalog and account ownership…")
        self.tree.setEnabled(False)
        champion_id = safe_int(self.data_dragon.resolve_champion(self.champion_name))

        def load() -> dict[str, Any]:
            catalog = self.data_dragon.get_skin_catalog(champion_id)
            ownership = self.websocket_manager.fetch_owned_skins_for_champion(champion_id)
            owned = ownership.get("owned_skins", []) if isinstance(ownership, Mapping) else []
            skins = merge_catalog_and_owned_skins(catalog, owned)
            get_preview_url = getattr(self.data_dragon, "get_skin_preview_url", None)
            get_remote_image = getattr(self.data_dragon, "get_remote_image", None)
            skin_images: dict[int, Any] = {}
            if callable(get_preview_url) and callable(get_remote_image):
                for skin in skins:
                    skin_id = safe_int(skin.get("skin_id"))
                    skin_url = (
                        skin.get("tile_url")
                        or skin.get("centered_splash_url")
                        or skin.get("uncentered_splash_url")
                        or skin.get("splash_url")
                    )
                    if not skin_url:
                        skin_url = get_preview_url(
                            self.champion_name,
                            skin_name=skin.get("skin_name"),
                            skin_id=skin_id,
                            skin_num=skin.get("skin_num"),
                        )
                    if skin_url:
                        skin_images[skin_id] = pil_to_qimage(
                            get_remote_image(skin_url, cache_key=f"picker_skin_{champion_id}_{skin_id}"),
                            size=(40, 40),
                        )
            return {
                "skins": skins,
                "skin_images": skin_images,
                "ok": bool(ownership.get("ok")) if isinstance(ownership, Mapping) else False,
                "message": str(ownership.get("message") or "") if isinstance(ownership, Mapping) else "",
            }

        self.task_runner.submit(
            load,
            _guarded_callback(self, "_apply_skins"),
            _guarded_callback(self, "_show_error"),
        )

    def _show_error(self, message: str) -> None:
        self.status.setText(f"Unable to load skins: {message}")

    def _apply_skins(self, payload: Mapping[str, Any]) -> None:
        self.skins = [dict(skin) for skin in payload.get("skins", []) if isinstance(skin, Mapping)]
        self.skin_images = payload.get("skin_images", {})
        self.lcu_available = bool(payload.get("ok"))
        message = str(payload.get("message") or "")
        self.status.setText(message or f"{len(self.skins)} skins available")
        self.tree.setEnabled(True)
        self._render()

    def _render(self) -> None:
        if not hasattr(self, "tree"):
            return
        self._updating = True
        self.tree.clear()
        mode = str(self.mode.currentData() or "none")
        fixed_id = safe_int(self.slot_data.get("skin_id"))
        pool = self.slot_data.get("random_skin_pool", [])
        pool_ids = {
            safe_int(entry.get("skin_id"))
            for entry in pool
            if isinstance(entry, Mapping) and safe_int(entry.get("skin_id")) > 0
        }
        skins = sort_skins_for_display(self.skins, mode=mode, fixed_skin_id=fixed_id, pool_ids=pool_ids)
        for skin in skins:
            skin_id = safe_int(skin.get("skin_id"))
            item = QTreeWidgetItem([str(skin.get("skin_name") or skin.get("name") or skin_id), "Owned" if skin.get("owned") else "Unverified"])
            skin_image = self.skin_images.get(skin_id) if isinstance(self.skin_images, Mapping) else None
            if skin_image is not None:
                item.setIcon(0, QIcon(qpixmap_from_image(skin_image)))
            item.setData(0, Qt.ItemDataRole.UserRole, skin)
            if mode == "random":
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked if skin_id in pool_ids else Qt.CheckState.Unchecked)
            self.tree.addTopLevelItem(item)
            if mode == "fixed" and skin_id == fixed_id:
                self.tree.setCurrentItem(item)
        self.tree.setEnabled(mode != "none" and bool(skins))
        self._updating = False

    def _item_changed(self, item: QTreeWidgetItem, _column: int) -> None:
        if self._updating or self.mode.currentData() != "random" or item.checkState(0) != Qt.CheckState.Checked:
            return
        skin = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(skin, Mapping) or self._confirm_skin(skin):
            return
        self._updating = True
        item.setCheckState(0, Qt.CheckState.Unchecked)
        self._updating = False

    def _confirm_skin(self, skin: Mapping[str, Any]) -> bool:
        warning = skin_selection_warning(skin, lcu_available=self.lcu_available)
        if warning is None:
            return True
        title, message = warning
        return QMessageBox.question(self, title, message) == QMessageBox.StandardButton.Yes

    def _save(self) -> None:
        mode = str(self.mode.currentData() or "none")
        if mode == "none":
            self.skin_selected.emit(
                {
                    "skin_mode": "none",
                    "skin_id": 0,
                    "skin_name": "",
                    "skin_num": 0,
                    "random_skin_id": 0,
                    "random_skin_name": "",
                    "random_skin_num": 0,
                    "random_skin_pool": [],
                }
            )
            self.accept()
            return

        if mode == "fixed":
            item = self.tree.currentItem()
            if item is None:
                QMessageBox.information(self, "Skin", "Select a fixed skin first.")
                return
            skin = item.data(0, Qt.ItemDataRole.UserRole)
            if not isinstance(skin, Mapping) or not self._confirm_skin(skin):
                return
            self.skin_selected.emit(
                {
                    "skin_mode": "fixed",
                    "skin_id": safe_int(skin.get("skin_id")),
                    "skin_name": str(skin.get("skin_name") or skin.get("name") or ""),
                    "skin_num": safe_int(skin.get("skin_num")),
                }
            )
            self.accept()
            return

        pool: list[dict[str, Any]] = []
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            if item.checkState(0) != Qt.CheckState.Checked:
                continue
            skin = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(skin, Mapping):
                pool.append(
                    {
                        "skin_id": safe_int(skin.get("skin_id")),
                        "skin_name": str(skin.get("skin_name") or skin.get("name") or ""),
                        "skin_num": safe_int(skin.get("skin_num")),
                    }
                )
        if not pool:
            QMessageBox.information(self, "Random skins", "Select at least one skin for the random pool.")
            return
        representative = pool[0]
        self.skin_selected.emit(
            {
                "skin_mode": "random",
                "random_skin_id": representative["skin_id"],
                "random_skin_name": representative["skin_name"],
                "random_skin_num": representative["skin_num"],
                "random_skin_pool": pool,
            }
        )
        self.accept()
