from copy import deepcopy

from PySide6.QtCore import QEvent
from PySide6.QtGui import QFocusEvent, QKeySequence
from PySide6.QtWidgets import QTabWidget

from src.config.settings import DEFAULT_PARAMS
from src.desktop.settings_dialog import SettingsDialog
from src.services.runes import (
    find_rune_keystone_path,
    get_rune_page_icon_paths,
    split_rune_page_perk_ids,
    strip_active_suffix,
)


class ImmediateTaskRunner:
    def submit(self, function, on_success, on_error=None):
        try:
            on_success(function())
        except Exception as exc:
            if on_error:
                on_error(str(exc))
        return "task"


class FakeDataDragon:
    all_names = ["Ashe", "Garen", "Lux", "Teemo"]

    def get_champion_icon(self, _name):
        return None

    def get_summoner_icon(self, _name):
        return None

    def get_rune_perk_icon_path(self, perk_id):
        return f"perk-{perk_id}.png"

    def get_rune_perk_name(self, perk_id):
        return f"Perk {perk_id}"


class FakeWebSocket:
    def is_active(self):
        return False

    def fetch_rune_pages(self):
        return []

    def fetch_rune_styles(self):
        return {}

    def fetch_current_rune_page(self):
        return None


def build_dialog(qtbot):
    dialog = SettingsDialog(
        settings=deepcopy(DEFAULT_PARAMS),
        data_dragon=FakeDataDragon(),
        websocket_manager=FakeWebSocket(),
        task_runner=ImmediateTaskRunner(),
    )
    qtbot.addWidget(dialog)
    return dialog


def test_find_rune_keystone_path_uses_selected_perk_id():
    page = {"selectedPerkIds": [8112]}
    style = {"perks": [{"id": 8112, "iconPath": "fallback.png"}]}
    assert find_rune_keystone_path(page, style, FakeDataDragon()) == "perk-8112.png"


def test_find_rune_keystone_path_falls_back_to_first_perk():
    style = {"perks": [{"id": 8005, "iconPath": "first.png"}]}
    assert find_rune_keystone_path({}, style) == "first.png"


def test_get_rune_page_icon_paths_returns_keystone_and_sub_style():
    page = {"primaryStyleId": 8000, "subStyleId": 8100, "selectedPerkIds": [8005]}
    styles = {
        8000: {"perks": [{"id": 8005, "iconPath": "keystone.png"}]},
        8100: {"iconPath": "substyle.png"},
    }
    assert get_rune_page_icon_paths(page, styles) == ("keystone.png", "substyle.png")


def test_split_rune_page_perk_ids_groups_primary_secondary_and_shards():
    page = {"selectedPerkIds": list(range(1, 10))}
    assert split_rune_page_perk_ids(page) == ([1, 2, 3, 4], [5, 6], [7, 8, 9])


def test_strip_active_suffix_removes_only_lcu_active_marker():
    assert strip_active_suffix("My runes (active)") == "My runes"
    assert strip_active_suffix("active plan") == "active plan"


def test_settings_expose_website_choices_and_current_values(qtbot):
    dialog = build_dialog(qtbot)
    assert dialog.stats_site.currentData() == "opgg"
    assert dialog.hotkey_site.currentData() == "porofessor"
    assert dialog.stats_site.count() == 4
    assert dialog.hotkey_site.count() == 4
    assert all(not button.icon().isNull() for button in dialog.pick_buttons.values())
    assert all(not button.icon().isNull() for button in dialog.spell_buttons.values())
    assert all(not button.icon().isNull() for button in dialog.rune_buttons.values())
    assert all(not button.icon().isNull() for button in dialog.skin_buttons.values())
    tabs = dialog.findChild(QTabWidget)
    assert tabs is not None
    assert all(not tabs.tabIcon(index).isNull() for index in range(tabs.count()))


def test_preset_master_switch_emits_once_and_updates_all_flags(qtbot):
    dialog = build_dialog(qtbot)
    emitted = []
    dialog.presets_changed.connect(emitted.append)
    dialog.presets_toggle.setChecked(False)
    assert emitted == [False]
    assert dialog.settings["presets_enabled"] is False
    assert dialog.settings["auto_pick_enabled"] is False
    assert dialog.settings["auto_summoners_enabled"] is False
    assert all(not button.isEnabled() for button in dialog.pick_buttons.values())


def test_champion_change_clears_only_that_slots_skin(qtbot):
    dialog = build_dialog(qtbot)
    other_skin = deepcopy(dialog.settings["pick_slots"]["pick_2"])
    dialog._select_champion("pick_1", "selected_pick_1", "Lux")
    first = dialog.settings["pick_slots"]["pick_1"]
    assert first["skin_mode"] == "none"
    assert first["skin_id"] == 0
    assert dialog.settings["pick_slots"]["pick_2"] == other_skin


def test_champion_exclusions_avoid_other_picks_and_ban(qtbot):
    dialog = build_dialog(qtbot)
    excluded = dialog._excluded_champions("pick_1")
    assert "Lux" in excluded
    assert "Ashe" in excluded
    assert "Teemo" in excluded
    assert "Garen" not in excluded


def test_unique_hotkey_is_normalized_and_emitted(qtbot):
    dialog = build_dialog(qtbot)
    values = []
    dialog.setting_changed.connect(lambda key, value: values.append((key, value)))
    dialog.toggle_hotkey.setKeySequence(QKeySequence("Ctrl+Shift+K"))
    dialog._save_hotkey("hotkey_toggle_window", dialog.toggle_hotkey)
    assert ("hotkey_toggle_window", "ctrl+shift+k") in values


def test_duplicate_hotkey_is_rejected(qtbot, monkeypatch):
    dialog = build_dialog(qtbot)
    warnings = []
    monkeypatch.setattr(
        "src.desktop.settings_dialog.QMessageBox.warning",
        lambda *args: warnings.append(args),
    )
    dialog.toggle_hotkey.setKeySequence(QKeySequence("Alt+P"))
    dialog._save_hotkey("hotkey_toggle_window", dialog.toggle_hotkey)
    assert warnings
    assert dialog.settings["hotkey_toggle_window"] == "alt+c"


def test_hotkey_capture_signals_suspend_until_focus_leaves(qtbot):
    dialog = build_dialog(qtbot)
    events = []
    dialog.hotkey_capture_started.connect(lambda: events.append("started"))
    dialog.hotkey_capture_finished.connect(lambda: events.append("finished"))

    dialog.toggle_hotkey.focusInEvent(QFocusEvent(QEvent.Type.FocusIn))
    dialog.toggle_hotkey.focusOutEvent(QFocusEvent(QEvent.Type.FocusOut))

    assert events == ["started", "finished"]


def test_theme_change_emits_selected_theme_once(qtbot):
    dialog = build_dialog(qtbot)
    themes = []
    dialog.theme_changed.connect(themes.append)
    dialog.theme_combo.setCurrentIndex(dialog.theme_combo.findData("flatly"))
    assert themes == ["flatly"]
