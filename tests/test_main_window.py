from copy import deepcopy
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication

from src.config.settings import DEFAULT_PARAMS
from src.core.events import Connected, Disconnected, ReadyCheckAccepted
from src.desktop.application import DesktopApplication
from src.desktop.event_bridge import CoreEventBridge
from src.desktop.integrations import GlobalHotkeyManager, TrayController
from src.desktop.main_window import MainWindow
from src.desktop.tasks import TaskRunner


class FakeDataDragon:
    all_names = ["Ashe", "Garen", "Lux", "Teemo"]

    def get_champion_icon(self, _name):
        return None

    def get_summoner_icon(self, _name):
        return None


class FakeWebSocket:
    def __init__(self):
        self.riot_id = "Detected#EUW"
        self.region = "euw"

    def get_riot_id(self):
        return self.riot_id

    def get_platform_for_websites(self):
        return self.region

    def force_refresh_summoner(self):
        return None

    def is_active(self):
        return False

    def fetch_rune_pages(self):
        return []

    def fetch_rune_styles(self):
        return {}

    def fetch_current_rune_page(self):
        return None


class FakeStore:
    def __init__(self, settings):
        self.settings = settings

    def update_many(self, values):
        self.settings.update(deepcopy(values))


class FakeController:
    def __init__(self, settings=None):
        self.settings = deepcopy(settings or DEFAULT_PARAMS)
        self.settings_store = FakeStore(self.settings)
        self.websocket_manager = FakeWebSocket()
        self.data_dragon = FakeDataDragon()
        self.saved = 0
        self.stopped = 0

    def settings_snapshot(self):
        return deepcopy(self.settings)

    def update_setting(self, key, value):
        self.settings[key] = deepcopy(value)

    def set_presets_enabled(self, enabled):
        self.settings.update(
            {
                "presets_enabled": enabled,
                "auto_pick_enabled": enabled,
                "auto_summoners_enabled": enabled,
            }
        )

    def replace_settings(self, settings):
        self.settings = deepcopy(settings)
        self.settings_store.settings = self.settings

    def save_settings(self):
        self.saved += 1
        return True

    def stop(self):
        self.stopped += 1


@pytest.fixture
def desktop(qtbot, monkeypatch):
    monkeypatch.setattr(GlobalHotkeyManager, "setup", lambda self, *_args: False)
    monkeypatch.setattr(TrayController, "setup", lambda self, **_kwargs: False)
    controller = FakeController()
    window = MainWindow(controller.settings_snapshot())
    qtbot.addWidget(window)
    task_runner = TaskRunner()
    application = DesktopApplication(
        qt_app=QApplication.instance(),
        controller=controller,
        event_bridge=CoreEventBridge(),
        main_window=window,
        task_runner=task_runner,
    )
    yield application, controller, window
    application.auto_hide_timer.stop()
    application.disconnect_timer.stop()
    application.hotkeys.shutdown()
    application.tray.shutdown()
    application.audio.shutdown()
    task_runner.shutdown()
    window.allow_close()
    window.close()


def test_main_toggle_updates_store_and_refreshes_card(desktop):
    application, controller, window = desktop
    window.automation_cards["auto_accept_enabled"].switch.setChecked(False)
    assert controller.settings["auto_accept_enabled"] is False
    assert controller.saved == 1
    assert not window.automation_cards["auto_accept_enabled"].switch.isChecked()


def test_preset_toggle_updates_all_related_flags(desktop):
    _application, controller, window = desktop
    window.automation_cards["presets_enabled"].switch.setChecked(False)
    assert controller.settings["presets_enabled"] is False
    assert controller.settings["auto_pick_enabled"] is False
    assert controller.settings["auto_summoners_enabled"] is False


def test_skin_cycle_changes_only_requested_slot(desktop):
    application, controller, _window = desktop
    application._cycle_skin_mode("pick_1")
    overrides = controller.settings["main_skin_mode_overrides"]
    assert overrides["pick_1"] == "none"
    assert overrides["pick_2"] == "inherit"
    assert overrides["pick_3"] == "inherit"


def test_skin_cycle_without_configured_skin_shows_message(desktop):
    application, controller, window = desktop
    slot = controller.settings["pick_slots"]["pick_1"]
    slot.update(
        {
            "skin_mode": "none",
            "skin_id": 0,
            "skin_name": "",
            "random_skin_id": 0,
            "random_skin_name": "",
            "random_skin_pool": [],
        }
    )
    application._cycle_skin_mode("pick_1")
    assert "Configure a fixed or random skin" in window.statusBar().currentMessage()


def test_real_disconnect_schedules_close(desktop):
    application, _controller, _window = desktop
    application._handle_runtime_event(Disconnected(transient=False, reason="client exited"))
    assert application.disconnect_timer.isActive()


def test_transient_disconnect_never_schedules_close(desktop):
    application, _controller, _window = desktop
    application.disconnect_timer.start()
    application._handle_runtime_event(Disconnected(transient=True, reason="scan failed"))
    assert not application.disconnect_timer.isActive()


def test_reconnect_cancels_pending_close(desktop):
    application, _controller, _window = desktop
    application.disconnect_timer.start()
    application._handle_runtime_event(Connected())
    assert not application.disconnect_timer.isActive()


def test_ready_check_uses_qt_audio_manager(desktop):
    application, _controller, _window = desktop
    application.audio.play_accept_sound = Mock()
    application._handle_runtime_event(ReadyCheckAccepted())
    application.audio.play_accept_sound.assert_called_once_with()


def test_website_account_uses_detected_or_manual_settings(desktop):
    application, controller, _window = desktop
    assert application._account_for_websites() == ("Detected#EUW", "euw")
    controller.settings.update(
        {
            "summoner_name_auto_detect": False,
            "manual_summoner_name": "Manual#NA",
            "manual_region": "na",
        }
    )
    assert application._account_for_websites() == ("Manual#NA", "na")


def test_settings_window_is_singleton(desktop):
    application, _controller, _window = desktop
    application.open_settings()
    first = application.settings_dialog
    application.open_settings()
    assert application.settings_dialog is first
    first.close()
