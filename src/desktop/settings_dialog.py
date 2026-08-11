"""PySide6 settings window with all persisted desktop controls."""

import copy
from collections.abc import Mapping
from functools import partial
from typing import Any

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.config import (
    GITHUB_REPO_URL,
    HOTKEY_SITE_LABELS,
    HOTKEY_SITE_ORDER,
    PICK_SLOT_LABELS,
    PICK_SLOT_ORDER,
    REGION_LIST,
    STATS_SITE_LABELS,
    STATS_SITE_ORDER,
    THEME_LABELS,
    THEME_ORDER,
)
from src.config.settings import export_parameters_to_file, import_parameters_from_file

from .images import pil_to_qimage, qpixmap_from_image
from .pickers import ChampionPickerDialog, RunePickerDialog, SkinPickerDialog, SpellPickerDialog
from .tasks import TaskRunner, guarded_callback


class GlobalKeySequenceEdit(QKeySequenceEdit):
    capture_started = Signal()
    capture_finished = Signal()

    def focusInEvent(self, event) -> None:
        self.capture_started.emit()
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.capture_finished.emit()


class SettingsDialog(QDialog):
    setting_changed = Signal(str, object)
    presets_changed = Signal(bool)
    settings_imported = Signal(object)
    theme_changed = Signal(str)
    history_requested = Signal()
    force_summoner_refresh = Signal()
    hotkey_capture_started = Signal()
    hotkey_capture_finished = Signal()

    def __init__(
        self,
        *,
        settings: Mapping[str, Any],
        data_dragon: Any,
        websocket_manager: Any,
        task_runner: TaskRunner,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("OTP LOL settings")
        self.resize(980, 720)
        self.setMinimumSize(820, 620)
        self.settings = copy.deepcopy(dict(settings))
        self.data_dragon = data_dragon
        self.websocket_manager = websocket_manager
        self.task_runner = task_runner
        self.pick_buttons: dict[str, QPushButton] = {}
        self.spell_buttons: dict[tuple[str, int], QPushButton] = {}
        self.rune_buttons: dict[str, QPushButton] = {}
        self.skin_buttons: dict[str, QPushButton] = {}
        self._icon_generation = 0
        self._build_ui()
        self._refresh_slot_buttons()
        self._load_slot_icons()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        heading = QHBoxLayout()
        title = QLabel("Settings")
        title.setObjectName("dialogTitle")
        subtitle = QLabel("Every change is saved locally as you make it.")
        subtitle.setProperty("secondary", True)
        heading.addWidget(title)
        heading.addStretch()
        heading.addWidget(subtitle)
        root.addLayout(heading)

        tabs = QTabWidget()
        tabs.addTab(self._scrollable(self._build_general_tab()), "General")
        tabs.addTab(self._scrollable(self._build_automation_tab()), "Champion select")
        tabs.addTab(self._scrollable(self._build_integrations_tab()), "Websites & shortcuts")
        root.addWidget(tabs, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        root.addWidget(buttons)

    @staticmethod
    def _scrollable(content: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        return scroll

    def _build_general_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(16)

        actions = QHBoxLayout()
        theme_label = QLabel("Theme")
        self.theme_combo = QComboBox()
        for theme in THEME_ORDER:
            self.theme_combo.addItem(THEME_LABELS[theme], theme)
        self.theme_combo.setCurrentIndex(max(self.theme_combo.findData(self.settings.get("theme", "darkly")), 0))
        self.theme_combo.currentIndexChanged.connect(self._change_theme)
        history = QPushButton("History")
        history.clicked.connect(self.history_requested.emit)
        export_button = QPushButton("Export config")
        export_button.clicked.connect(self._export_config)
        import_button = QPushButton("Import config")
        import_button.clicked.connect(self._import_config)
        actions.addWidget(theme_label)
        actions.addWidget(self.theme_combo)
        actions.addStretch()
        actions.addWidget(history)
        actions.addWidget(export_button)
        actions.addWidget(import_button)
        layout.addLayout(actions)

        automation = QGroupBox("Queue")
        automation_layout = QVBoxLayout(automation)
        auto_accept = self._setting_checkbox(
            "Automatically accept the game when a match is found",
            "auto_accept_enabled",
        )
        automation_layout.addWidget(auto_accept)
        layout.addWidget(automation)

        account = QGroupBox("Account")
        account_layout = QVBoxLayout(account)
        self.auto_detect = QCheckBox("Automatic Riot account detection")
        self.auto_detect.setChecked(bool(self.settings.get("summoner_name_auto_detect", True)))
        self.auto_detect.toggled.connect(self._toggle_auto_detect)
        account_layout.addWidget(self.auto_detect)
        form = QFormLayout()
        self.riot_id = QLineEdit(str(self.settings.get("manual_summoner_name") or ""))
        self.riot_id.setPlaceholderText("GameName#Tag")
        self.riot_id.editingFinished.connect(self._save_manual_riot_id)
        self.region = QComboBox()
        self.region.addItems(REGION_LIST)
        self.region.setCurrentText(str(self.settings.get("manual_region") or "euw"))
        self.region.currentTextChanged.connect(partial(self._set_setting, "manual_region"))
        form.addRow("Riot ID", self.riot_id)
        form.addRow("Region", self.region)
        account_layout.addLayout(form)
        detected = str(self.settings.get("auto_detected_riot_id") or "Not detected yet")
        self.detected_account = QLabel(f"Detected: {detected}")
        self.detected_account.setProperty("secondary", True)
        account_layout.addWidget(self.detected_account)
        layout.addWidget(account)

        behavior = QGroupBox("Desktop behavior")
        behavior_layout = QVBoxLayout(behavior)
        behavior_layout.addWidget(
            self._setting_checkbox("Automatically return to lobby after the game", "auto_play_again_enabled")
        )
        behavior_layout.addWidget(
            self._setting_checkbox("Hide OTP LOL three seconds after League connects", "auto_hide_on_connect")
        )
        behavior_layout.addWidget(
            self._setting_checkbox("Close OTP LOL when the League client exits", "close_app_on_lol_exit")
        )
        layout.addWidget(behavior)
        layout.addStretch()
        self._sync_account_controls()
        return page

    def _build_automation_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(16)

        master = QGroupBox("Preset automation")
        master_layout = QVBoxLayout(master)
        self.presets_toggle = QCheckBox("Enable picks, spells, runes and skins presets")
        self.presets_toggle.setChecked(bool(self.settings.get("presets_enabled", False)))
        self.presets_toggle.toggled.connect(self._change_presets)
        master_layout.addWidget(self.presets_toggle)
        layout.addWidget(master)

        presets = QGroupBox("Ordered presets")
        grid = QGridLayout(presets)
        for column, label in enumerate(("Preset", "Champion", "Spell 1", "Spell 2", "Runes", "Skin")):
            heading = QLabel(label)
            heading.setProperty("secondary", True)
            grid.addWidget(heading, 0, column)
        for row, slot_key in enumerate(PICK_SLOT_ORDER, start=1):
            grid.addWidget(QLabel(PICK_SLOT_LABELS[slot_key]), row, 0)
            champion = QPushButton()
            champion.clicked.connect(partial(self._open_champion_picker, slot_key))
            self.pick_buttons[slot_key] = champion
            grid.addWidget(champion, row, 1)
            for spell_number in (1, 2):
                spell = QPushButton()
                spell.clicked.connect(partial(self._open_spell_picker, slot_key, spell_number))
                self.spell_buttons[(slot_key, spell_number)] = spell
                grid.addWidget(spell, row, 1 + spell_number)
            rune = QPushButton()
            rune.clicked.connect(partial(self._open_rune_picker, slot_key))
            self.rune_buttons[slot_key] = rune
            grid.addWidget(rune, row, 4)
            skin = QPushButton()
            skin.clicked.connect(partial(self._open_skin_picker, slot_key))
            self.skin_buttons[slot_key] = skin
            grid.addWidget(skin, row, 5)
        layout.addWidget(presets)

        ban = QGroupBox("Ban")
        ban_layout = QHBoxLayout(ban)
        self.auto_ban = self._setting_checkbox("Ban a configured champion", "auto_ban_enabled")
        self.auto_ban.toggled.connect(self._sync_enabled_states)
        self.ban_button = QPushButton()
        self.ban_button.clicked.connect(self._open_ban_picker)
        ban_layout.addWidget(self.auto_ban)
        ban_layout.addStretch()
        ban_layout.addWidget(self.ban_button)
        layout.addWidget(ban)
        layout.addStretch()
        self._sync_enabled_states()
        return page

    def _build_integrations_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(16)

        websites = QGroupBox("Websites")
        form = QFormLayout(websites)
        self.stats_site = QComboBox()
        for site in STATS_SITE_ORDER:
            self.stats_site.addItem(STATS_SITE_LABELS[site], site)
        self.stats_site.setCurrentIndex(max(self.stats_site.findData(self.settings.get("preferred_stats_site")), 0))
        self.stats_site.currentIndexChanged.connect(
            lambda: self._set_setting("preferred_stats_site", self.stats_site.currentData())
        )
        self.hotkey_site = QComboBox()
        for site in HOTKEY_SITE_ORDER:
            self.hotkey_site.addItem(HOTKEY_SITE_LABELS[site], site)
        self.hotkey_site.setCurrentIndex(max(self.hotkey_site.findData(self.settings.get("preferred_hotkey_site")), 0))
        self.hotkey_site.currentIndexChanged.connect(
            lambda: self._set_setting("preferred_hotkey_site", self.hotkey_site.currentData())
        )
        form.addRow("Preferred stats site", self.stats_site)
        form.addRow("Global-shortcut site", self.hotkey_site)
        layout.addWidget(websites)

        shortcuts = QGroupBox("Global shortcuts")
        shortcut_form = QFormLayout(shortcuts)
        self.toggle_hotkey = GlobalKeySequenceEdit(
            QKeySequence(str(self.settings.get("hotkey_toggle_window") or "Alt+C"))
        )
        self.site_hotkey = GlobalKeySequenceEdit(
            QKeySequence(str(self.settings.get("hotkey_open_site") or "Alt+P"))
        )
        self.toggle_hotkey.editingFinished.connect(partial(self._save_hotkey, "hotkey_toggle_window", self.toggle_hotkey))
        self.site_hotkey.editingFinished.connect(partial(self._save_hotkey, "hotkey_open_site", self.site_hotkey))
        for editor in (self.toggle_hotkey, self.site_hotkey):
            editor.capture_started.connect(self.hotkey_capture_started.emit)
            editor.capture_finished.connect(self.hotkey_capture_finished.emit)
        shortcut_form.addRow("Show / hide app", self.toggle_hotkey)
        shortcut_form.addRow("Open website", self.site_hotkey)
        layout.addWidget(shortcuts)

        issue = QPushButton("Report an issue on GitHub")
        issue.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(f"{GITHUB_REPO_URL}/issues/new"))
        )
        layout.addWidget(issue, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()
        return page

    def _setting_checkbox(self, label: str, key: str) -> QCheckBox:
        checkbox = QCheckBox(label)
        checkbox.setChecked(bool(self.settings.get(key, False)))
        checkbox.toggled.connect(partial(self._set_setting, key))
        return checkbox

    def _set_setting(self, key: str, value: Any) -> None:
        self.settings[key] = value
        self.setting_changed.emit(key, value)

    def _change_theme(self) -> None:
        theme = str(self.theme_combo.currentData() or "darkly")
        self._set_setting("theme", theme)
        self.theme_changed.emit(theme)

    def _toggle_auto_detect(self, enabled: bool) -> None:
        self._set_setting("summoner_name_auto_detect", enabled)
        self._sync_account_controls()
        if enabled:
            self.force_summoner_refresh.emit()

    def _sync_account_controls(self) -> None:
        manual = not self.auto_detect.isChecked()
        self.riot_id.setEnabled(manual)
        self.region.setEnabled(manual)

    def _save_manual_riot_id(self) -> None:
        self._set_setting("manual_summoner_name", self.riot_id.text().strip())

    def _change_presets(self, enabled: bool) -> None:
        self.settings["presets_enabled"] = enabled
        self.settings["auto_pick_enabled"] = enabled
        self.settings["auto_summoners_enabled"] = enabled
        self.presets_changed.emit(enabled)
        self._sync_enabled_states()

    def _sync_enabled_states(self) -> None:
        presets_enabled = bool(getattr(self, "presets_toggle", None) and self.presets_toggle.isChecked())
        for button in [*self.pick_buttons.values(), *self.spell_buttons.values(), *self.rune_buttons.values(), *self.skin_buttons.values()]:
            button.setEnabled(presets_enabled)
        if hasattr(self, "ban_button"):
            self.ban_button.setEnabled(self.auto_ban.isChecked())

    def _pick_slots(self) -> dict[str, dict[str, Any]]:
        raw = self.settings.get("pick_slots", {})
        return copy.deepcopy(raw) if isinstance(raw, dict) else {}

    def _update_slot(self, slot_key: str, updates: Mapping[str, Any]) -> None:
        slots = self._pick_slots()
        slot = slots.setdefault(slot_key, {})
        slot.update(dict(updates))
        self.settings["pick_slots"] = slots
        self.setting_changed.emit("pick_slots", slots)
        self._refresh_slot_buttons()

    def _selected_picks(self) -> dict[str, str]:
        return {slot: str(self.settings.get(f"selected_pick_{index}") or "") for index, slot in enumerate(PICK_SLOT_ORDER, 1)}

    def _excluded_champions(self, slot_key: str | None, *, ban: bool = False) -> set[str]:
        picks = self._selected_picks()
        excluded = {
            champion
            for key, champion in picks.items()
            if champion and champion != "(None)" and (slot_key is None or key != slot_key)
        }
        selected_ban = str(self.settings.get("selected_ban") or "")
        if not ban and selected_ban and selected_ban != "(None)":
            excluded.add(selected_ban)
        return excluded

    def _open_champion_picker(self, slot_key: str) -> None:
        index = PICK_SLOT_ORDER.index(slot_key) + 1
        key = f"selected_pick_{index}"
        picker = ChampionPickerDialog(
            data_dragon=self.data_dragon,
            task_runner=self.task_runner,
            excluded=self._excluded_champions(slot_key),
            current=str(self.settings.get(key) or ""),
            title=f"{PICK_SLOT_LABELS[slot_key]} champion",
            parent=self,
        )
        picker.champion_selected.connect(partial(self._select_champion, slot_key, key))
        picker.exec()

    def _select_champion(self, slot_key: str, setting_key: str, champion: str) -> None:
        self._set_setting(setting_key, champion)
        self._update_slot(
            slot_key,
            {
                "skin_mode": "none",
                "skin_id": 0,
                "skin_name": "",
                "skin_num": 0,
                "random_skin_id": 0,
                "random_skin_name": "",
                "random_skin_num": 0,
                "random_skin_pool": [],
            },
        )
        self._load_slot_icons()

    def _open_ban_picker(self) -> None:
        picker = ChampionPickerDialog(
            data_dragon=self.data_dragon,
            task_runner=self.task_runner,
            excluded=self._excluded_champions(None, ban=True),
            current=str(self.settings.get("selected_ban") or ""),
            title="Ban champion",
            parent=self,
        )
        picker.champion_selected.connect(partial(self._set_setting, "selected_ban"))
        picker.champion_selected.connect(lambda _value: self._refresh_slot_buttons())
        picker.exec()

    def _open_spell_picker(self, slot_key: str, spell_number: int) -> None:
        slot = self._pick_slots().get(slot_key, {})
        picker = SpellPickerDialog(
            data_dragon=self.data_dragon,
            task_runner=self.task_runner,
            current=str(slot.get(f"spell_{spell_number}") or ""),
            parent=self,
        )
        picker.spell_selected.connect(
            lambda value: (self._update_slot(slot_key, {f"spell_{spell_number}": value}), self._load_slot_icons())
        )
        picker.exec()

    def _open_rune_picker(self, slot_key: str) -> None:
        picker = RunePickerDialog(
            data_dragon=self.data_dragon,
            websocket_manager=self.websocket_manager,
            task_runner=self.task_runner,
            slot_data=self._pick_slots().get(slot_key, {}),
            parent=self,
        )
        picker.rune_selected.connect(partial(self._update_slot, slot_key))
        picker.exec()

    def _open_skin_picker(self, slot_key: str) -> None:
        champion = self._selected_picks().get(slot_key, "")
        if not champion or champion == "(None)":
            QMessageBox.information(self, "Skin", "Choose a champion for this preset first.")
            return
        picker = SkinPickerDialog(
            data_dragon=self.data_dragon,
            websocket_manager=self.websocket_manager,
            task_runner=self.task_runner,
            champion_name=champion,
            slot_data=self._pick_slots().get(slot_key, {}),
            parent=self,
        )
        picker.skin_selected.connect(partial(self._update_slot, slot_key))
        picker.exec()

    def _refresh_slot_buttons(self) -> None:
        if not self.pick_buttons:
            return
        picks = self._selected_picks()
        slots = self._pick_slots()
        for slot_key in PICK_SLOT_ORDER:
            slot = slots.get(slot_key, {})
            self.pick_buttons[slot_key].setText(picks[slot_key] or "None")
            for number in (1, 2):
                value = str(slot.get(f"spell_{number}") or "None").replace("(None)", "None")
                self.spell_buttons[(slot_key, number)].setText(value)
            rune_name = str(slot.get("rune_page_name") or "Runes")
            if rune_name and not bool(slot.get("rune_auto_apply", True)):
                rune_name += " · off"
            self.rune_buttons[slot_key].setText(rune_name)
            mode = str(slot.get("skin_mode") or "none")
            if mode == "fixed":
                skin_label = str(slot.get("skin_name") or "Fixed skin")
            elif mode == "random":
                skin_label = f"Random ({len(slot.get('random_skin_pool', []))})"
            else:
                skin_label = "Skin off"
            self.skin_buttons[slot_key].setText(skin_label)
        self.ban_button.setText(str(self.settings.get("selected_ban") or "None"))
        self._sync_enabled_states()

    def _load_slot_icons(self) -> None:
        picks = self._selected_picks()
        slots = self._pick_slots()
        self._icon_generation += 1
        generation = self._icon_generation

        def load() -> dict[str, Any]:
            images: dict[tuple[str, str, int], Any] = {}
            for slot_key in PICK_SLOT_ORDER:
                images[(slot_key, "champion", 0)] = pil_to_qimage(
                    self.data_dragon.get_champion_icon(picks[slot_key]), size=(28, 28)
                )
                for number in (1, 2):
                    spell = str(slots.get(slot_key, {}).get(f"spell_{number}") or "")
                    images[(slot_key, "spell", number)] = pil_to_qimage(
                        self.data_dragon.get_summoner_icon(spell), size=(28, 28)
                    )
            return {"generation": generation, "images": images}

        self.task_runner.submit(load, guarded_callback(self, "_apply_slot_icons"))

    def _apply_slot_icons(self, payload: Mapping[str, Any]) -> None:
        if payload.get("generation") != self._icon_generation:
            return
        images = payload.get("images", {})
        if not isinstance(images, Mapping):
            return
        for slot_key in PICK_SLOT_ORDER:
            champion_image = images.get((slot_key, "champion", 0))
            self.pick_buttons[slot_key].setIcon(QIcon(qpixmap_from_image(champion_image)))
            self.pick_buttons[slot_key].setIconSize(QSize(28, 28))
            for number in (1, 2):
                spell_image = images.get((slot_key, "spell", number))
                self.spell_buttons[(slot_key, number)].setIcon(QIcon(qpixmap_from_image(spell_image)))
                self.spell_buttons[(slot_key, number)].setIconSize(QSize(28, 28))

    def _save_hotkey(self, key: str, editor: QKeySequenceEdit) -> None:
        value = editor.keySequence().toString(QKeySequence.SequenceFormat.PortableText).replace(" ", "").lower()
        if not value:
            return
        other_key = "hotkey_open_site" if key == "hotkey_toggle_window" else "hotkey_toggle_window"
        if value == str(self.settings.get(other_key) or "").lower():
            QMessageBox.warning(self, "Shortcut", "The two global shortcuts must be different.")
            editor.setKeySequence(QKeySequence(str(self.settings.get(key) or "")))
            return
        self._set_setting(key, value)

    def _export_config(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export OTP LOL configuration",
            "otp-lol-settings.toml",
            "TOML (*.toml);;JSON (*.json)",
        )
        if path and not export_parameters_to_file(path, self.settings):
            QMessageBox.warning(self, "Export", "Unable to export the configuration.")

    def _import_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import OTP LOL configuration",
            "",
            "Configuration (*.toml *.json)",
        )
        if not path:
            return
        try:
            imported = import_parameters_from_file(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Import", f"Unable to import this configuration:\n{exc}")
            return
        self.settings = copy.deepcopy(imported)
        self.settings_imported.emit(imported)
        QMessageBox.information(self, "Import", "Configuration imported. Reopen settings to review it.")
        self.accept()
