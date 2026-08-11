from PIL import Image
from PySide6.QtCore import QAbstractAnimation
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QCheckBox

from src.core.events import (
    Connected,
    Disconnected,
    ProfileUpdated,
    RankedEntry,
    SpellsApplied,
    StatusChanged,
    UpdateAvailable,
)
from src.desktop.main_window import MainWindow


class ImmediateTaskRunner:
    def submit(self, function, on_success, on_error=None):
        try:
            on_success(function())
        except Exception as exc:
            if on_error:
                on_error(str(exc))
        return "task"


class FakeDataDragon:
    def __init__(self):
        self.rank_tiers = []

    def get_rank_icon(self, tier):
        self.rank_tiers.append(tier)
        return Image.new("RGBA", (40, 40), (40, 220, 130, 255))

    def get_champion_icon(self, _name):
        return None

    def get_summoner_icon(self, _name):
        return None

    def compose_rune_button_icon(self, *_args, **_kwargs):
        return None

    def get_skin_preview_url(self, *_args, **_kwargs):
        return None

    def get_remote_image(self, *_args, **_kwargs):
        return None


def build_settings():
    return {
        "auto_accept_enabled": True,
        "presets_enabled": True,
        "auto_ban_enabled": False,
        "auto_play_again_enabled": False,
        "selected_pick_1": "Garen",
        "selected_pick_2": "Lux",
        "selected_pick_3": "Ashe",
        "selected_ban": "Teemo",
    }


def test_runtime_events_update_visible_state(qtbot):
    window = MainWindow(build_settings())
    qtbot.addWidget(window)

    window.handle_runtime_event(Connected())
    window.handle_runtime_event(StatusChanged("Champion select", "INFO"))
    window.handle_runtime_event(SpellsApplied("Flash", "Teleport"))

    assert window.connection_chip.text() == "League client connected"
    assert window.status_label.text() == "Champion select"
    assert window.spells_label.text() == "Spells: Flash + Teleport"

    window.handle_runtime_event(Disconnected(False, "client_stopped"))
    assert window.connection_chip.text() == "League client offline"


def test_connected_header_animates_only_the_connection_dot(qtbot):
    window = MainWindow(build_settings())
    qtbot.addWidget(window)

    window.handle_runtime_event(Connected())

    assert window._connection_pulse.state() == QAbstractAnimation.State.Running
    assert window.connection_panel.height() == 56
    assert window.riot_client_button.height() == window.connection_panel.height()
    assert not window.riot_client_button.icon().isNull()

    window.handle_runtime_event(Disconnected(False, "client_stopped"))
    assert window._connection_pulse.state() == QAbstractAnimation.State.Stopped
    assert window.connection_dot.property("connected") is False


def test_profile_event_loads_tier_specific_rank_asset(qtbot):
    data_dragon = FakeDataDragon()
    window = MainWindow(
        build_settings(),
        data_dragon=data_dragon,
        task_runner=ImmediateTaskRunner(),
    )
    qtbot.addWidget(window)

    window.handle_runtime_event(
        ProfileUpdated(
            riot_id="Player#EUW",
            summoner_id=42,
            puuid="puuid",
            profile_icon_id=None,
            summoner_level=125,
            ranked_entries=(RankedEntry("RANKED_SOLO_5x5", "EMERALD", "I", 45, 20, 15),),
        )
    )

    assert data_dragon.rank_tiers == ["emerald"]
    assert window.rank_icon.pixmap().toImage().pixelColor(20, 20).green() > 100


def test_active_preset_shows_selected_ban_and_real_icon(qtbot):
    data_dragon = FakeDataDragon()
    data_dragon.get_champion_icon = lambda _name: Image.new("RGBA", (32, 32), (230, 80, 80, 255))
    window = MainWindow(
        build_settings(),
        data_dragon=data_dragon,
        task_runner=ImmediateTaskRunner(),
    )
    qtbot.addWidget(window)

    assert window.active_ban_label.text() == "Ban  Teemo"
    assert window.active_ban_icon.pixmap().toImage().pixelColor(15, 15).red() > 150


def test_recent_activity_uses_champion_image_and_action_color_contract(qtbot):
    data_dragon = FakeDataDragon()
    data_dragon.get_champion_icon = lambda _name: Image.new("RGBA", (32, 32), (230, 80, 80, 255))
    window = MainWindow(
        build_settings(),
        data_dragon=data_dragon,
        task_runner=ImmediateTaskRunner(),
    )
    qtbot.addWidget(window)
    entry = {
        "action": "ban",
        "category": "Champion Select",
        "message": "Automatic ban confirmed on Garen.",
        "details": {"champion": "Garen"},
        "level": "success",
    }

    image = window._activity_image(entry)

    assert not image.isNull()
    assert window._activity_status_label(entry) == "BAN"
    assert window._activity_action({"action": "set", "category": "Summs"}) == "spells"


def test_recent_activity_uses_selected_rune_image(qtbot):
    data_dragon = FakeDataDragon()
    data_dragon.compose_rune_button_icon = lambda *_args, **_kwargs: Image.new(
        "RGBA", (32, 32), (80, 120, 230, 255)
    )
    window = MainWindow(
        build_settings(),
        data_dragon=data_dragon,
        task_runner=ImmediateTaskRunner(),
    )
    qtbot.addWidget(window)
    image = window._activity_image(
        {
            "action": "runes",
            "details": {
                "rune_keystone_path": "7201",
                "rune_sub_style_icon_path": "8300",
            },
        }
    )

    assert not image.isNull()


def test_profile_event_updates_rank_and_keeps_visual_fallbacks(qtbot):
    window = MainWindow(build_settings())
    qtbot.addWidget(window)

    window.handle_runtime_event(
        ProfileUpdated(
            riot_id="Player#EUW",
            summoner_id=42,
            puuid="puuid",
            profile_icon_id=123,
            summoner_level=125,
            ranked_entries=(RankedEntry("RANKED_SOLO_5x5", "PLATINUM", "II", 45, 20, 15),),
        )
    )

    assert window.account_name.text() == "Player#EUW"
    assert window.rank_title.text() == "Ranked Solo/Duo Platinum II"
    assert window.rank_detail.text() == "45 LP · 20W 15L"
    assert not window.account_avatar.pixmap().isNull()
    assert not window.rank_icon.pixmap().isNull()


def test_presets_switch_emits_canonical_command(qtbot):
    window = MainWindow(build_settings())
    qtbot.addWidget(window)
    spy = QSignalSpy(window.presets_changed)
    presets_switch = next(
        checkbox
        for checkbox in window.findChildren(QCheckBox)
        if checkbox.accessibleName() == "Pick presets"
    )

    presets_switch.setChecked(False)

    assert spy.count() == 1
    assert spy.at(0)[0] is False


def test_home_automation_controls_and_rune_binding(qtbot):
    settings = build_settings()
    settings.update(
        {
            "auto_pick_enabled": True,
            "auto_summoners_enabled": True,
            "preferred_hotkey_site": "porofessor",
            "pick_slots": {"pick_1": {"rune_auto_apply": True}},
        }
    )
    window = MainWindow(settings)
    qtbot.addWidget(window)

    assert set(window.home_automation_cards) == {
        "auto_accept_enabled",
        "auto_pick_enabled",
        "auto_ban_enabled",
        "auto_summoners_enabled",
        "rune_auto_apply",
        "auto_play_again_enabled",
    }
    assert window.shortcut_site_label.text() == "Open Porofessor"

    spy = QSignalSpy(window.setting_changed)
    window.home_automation_cards["rune_auto_apply"].switch.setChecked(False)

    assert spy.count() == 1
    assert spy.at(0)[0] == "pick_slots"
    assert spy.at(0)[1]["pick_1"]["rune_auto_apply"] is False


def test_news_panel_uses_update_highlights(qtbot):
    window = MainWindow(build_settings())
    qtbot.addWidget(window)

    window.handle_runtime_event(UpdateAvailable("11.1", "- First change\n- Second change"))

    assert window.news_version_label.text() == "OTP LOL v11.1"
    assert "First change" in window.news_highlights_label.text()
    assert "Second change" in window.news_highlights_label.text()
