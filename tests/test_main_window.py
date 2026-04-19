import unittest

from src.core import WebSocketManager
from src.ui.main_window import LoLAssistantUI


class DummyWidget:
    def __init__(self):
        self.last_config = {}
        self.image = None

    def configure(self, **kwargs):
        self.last_config.update(kwargs)


class DummyToastRecorder:
    def __init__(self):
        self.messages = []

    def __call__(self, message, duration=0):
        self.messages.append((message, duration))


class DummySettingsWindow:
    class Window:
        @staticmethod
        def winfo_exists():
            return True

    def __init__(self):
        self.window = self.Window()
        self.sync_calls = 0

    def _sync_from_params(self):
        self.sync_calls += 1


class MutableParamsWindow:
    def __init__(self, params):
        self._params = params
        self.settings_win = DummySettingsWindow()
        self.toasts = []

    def get_params(self):
        return self._params

    def update_param(self, key, value):
        self._params[key] = value

    def show_toast(self, message, duration=0):
        self.toasts.append((message, duration))


class DummyRoot:
    def __init__(self):
        self.calls = []
        self.cancelled = []

    def after(self, delay, callback):
        self.calls.append((delay, callback))
        return len(self.calls)

    def after_cancel(self, after_id):
        self.cancelled.append(after_id)


class MainWindowLogicTests(unittest.TestCase):
    def test_build_feature_preview_payload_uses_global_flags_and_effective_values(self):
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        params = {
            "auto_pick_enabled": True,
            "auto_ban_enabled": False,
            "auto_summoners_enabled": True,
            "main_skin_mode_override": "inherit",
            "main_skin_mode_overrides": {"pick_1": "inherit", "pick_2": "inherit", "pick_3": "inherit"},
        }
        effective = {
            "presets_enabled": False,
            "selected_pick_1": "Garen",
            "selected_pick_2": "Lux",
            "selected_pick_3": "Ashe",
            "selected_ban": "Teemo",
            "pick_slots": {
                "pick_1": {
                    "champion": "Garen",
                    "skin_mode": "fixed",
                    "skin_id": 86000,
                    "skin_name": "Default Garen",
                    "skin_num": 0,
                    "random_skin_id": 0,
                    "random_skin_name": "",
                    "random_skin_num": 0,
                    "random_skin_pool": [],
                },
                "pick_2": {
                    "champion": "Lux",
                    "skin_mode": "none",
                    "skin_id": 0,
                    "skin_name": "",
                    "skin_num": 0,
                    "random_skin_id": 0,
                    "random_skin_name": "",
                    "random_skin_num": 0,
                    "random_skin_pool": [],
                },
                "pick_3": {
                    "champion": "Ashe",
                    "skin_mode": "none",
                    "skin_id": 0,
                    "skin_name": "",
                    "skin_num": 0,
                    "random_skin_id": 0,
                    "random_skin_name": "",
                    "random_skin_num": 0,
                    "random_skin_pool": [],
                },
            },
        }

        payload = window._build_feature_preview_payload(params, effective)

        self.assertFalse(payload["presets"]["enabled"])
        self.assertFalse(payload["ban"]["enabled"])
        self.assertEqual(payload["presets"]["values"], ["Garen", "Lux", "Ashe"])
        self.assertTrue(payload["skins"]["enabled"])
        self.assertEqual(payload["skins"]["mode"], "mixed")
        self.assertEqual(len(payload["skins"]["values"]), 3)
        self.assertEqual(payload["skins"]["values"][0]["mode"], "fixed")
        self.assertEqual(payload["skins"]["values"][1]["mode"], "none")
        self.assertEqual(payload["ban"]["values"], ["Teemo"])

    def test_toggle_main_preview_feature_updates_param_and_syncs_settings(self):
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        params = {
            "auto_pick_enabled": True,
            "auto_summoners_enabled": True,
            "presets_enabled": True,
        }
        updates = []
        recorder = DummyToastRecorder()
        settings = DummySettingsWindow()

        window.get_params = lambda: params.copy()
        window.update_param = lambda key, value: updates.append((key, value))
        window.show_toast = recorder
        window.settings_win = settings
        window.is_main_preview_presets_enabled = lambda: True
        window.set_main_preview_presets_enabled = lambda enabled: updates.extend(
            [
                ("auto_pick_enabled", enabled),
                ("auto_summoners_enabled", enabled),
                ("presets_enabled", enabled),
            ]
        )
        window._sync_settings_window_if_open = lambda: settings._sync_from_params()

        window._toggle_main_preview_feature("presets")

        self.assertEqual(
            updates,
            [
                ("auto_pick_enabled", False),
                ("auto_summoners_enabled", False),
                ("presets_enabled", False),
            ],
        )
        self.assertEqual(settings.sync_calls, 1)
        self.assertEqual(recorder.messages[0][0], "Presets disabled.")

    def test_set_feature_icon_hides_slot_text_when_section_disabled(self):
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        window.theme = "darkly"
        window.preview_placeholder = object()
        widget = DummyWidget()

        window._set_feature_icon(widget, "Flash", is_champion=False, enabled=False, accent="warning")

        self.assertEqual(widget.last_config["text"], "")
        self.assertIs(widget.image, window.preview_placeholder)

    def test_build_preview_signature_changes_when_values_change(self):
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        preview_a = {
            "presets": {"enabled": True, "values": ["Garen", "Lux", "Ashe"]},
            "skins": {"enabled": False, "mode": "none", "values": [{"mode": "none"}, {"mode": "none"}, {"mode": "none"}]},
            "ban": {"enabled": True, "values": ["Teemo"]},
        }
        preview_b = {
            "presets": {"enabled": True, "values": ["Garen", "Lux", "Ashe"]},
            "skins": {"enabled": True, "mode": "fixed", "values": [{"mode": "fixed", "skin_id": 1}, {"mode": "none"}, {"mode": "none"}]},
            "ban": {"enabled": False, "values": ["Teemo"]},
        }

        self.assertNotEqual(window._build_preview_signature(preview_a), window._build_preview_signature(preview_b))

    def test_preview_icon_cache_key_separates_type_and_name(self):
        window = LoLAssistantUI.__new__(LoLAssistantUI)

        champion_key = window._get_preview_icon_cache_key("Garen", True)
        spell_key = window._get_preview_icon_cache_key("Garen", False)

        self.assertNotEqual(champion_key, spell_key)
        self.assertEqual(champion_key, ("champ", "Garen", 30))

    def test_request_quit_from_external_thread_schedules_ui_callback(self):
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        window.root = DummyRoot()
        window._quit_callback = lambda: None

        window.request_quit_from_external_thread()

        self.assertEqual(len(window.root.calls), 1)
        self.assertEqual(window.root.calls[0][0], 0)
        self.assertIs(window.root.calls[0][1], window._quit_callback)

    def test_request_toggle_from_external_thread_schedules_toggle(self):
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        window.root = DummyRoot()
        window.toggle_window = lambda: None

        window.request_toggle_window_from_external_thread()

        self.assertEqual(len(window.root.calls), 1)
        self.assertEqual(window.root.calls[0][0], 0)
        self.assertIs(window.root.calls[0][1], window.toggle_window)

    def test_request_open_settings_from_external_thread_schedules_open(self):
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        window.root = DummyRoot()
        window.open_settings = lambda: None

        window.request_open_settings_from_external_thread()

        self.assertEqual(len(window.root.calls), 1)
        self.assertEqual(window.root.calls[0][0], 0)
        self.assertIs(window.root.calls[0][1], window.open_settings)

    def test_request_toggle_presets_from_external_thread_schedules_toggle(self):
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        window.root = DummyRoot()
        window.toggle_tray_presets_automation = lambda: None

        window.request_toggle_presets_automation_from_external_thread()

        self.assertEqual(len(window.root.calls), 1)
        self.assertEqual(window.root.calls[0][0], 0)
        self.assertIs(window.root.calls[0][1], window.toggle_tray_presets_automation)

    def test_request_toggle_auto_ban_from_external_thread_schedules_toggle(self):
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        window.root = DummyRoot()
        window.toggle_tray_auto_ban = lambda: None

        window.request_toggle_auto_ban_from_external_thread()

        self.assertEqual(len(window.root.calls), 1)
        self.assertEqual(window.root.calls[0][0], 0)
        self.assertIs(window.root.calls[0][1], window.toggle_tray_auto_ban)

    def test_toggle_tray_presets_automation_updates_selected_role(self):
        params = {
            "selected_profile_role": "MIDDLE",
            "presets_enabled": False,
            "role_profiles": {
                "MIDDLE": {
                    "presets_enabled": True,
                }
            },
        }
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        mutable = MutableParamsWindow(params)
        window.get_params = mutable.get_params
        window.update_param = mutable.update_param
        window.show_toast = mutable.show_toast
        window.settings_win = mutable.settings_win

        window.toggle_tray_presets_automation()

        self.assertFalse(params["role_profiles"]["MIDDLE"]["presets_enabled"])
        self.assertEqual(window.settings_win.sync_calls, 1)
        self.assertEqual(mutable.toasts[0][0], "Presets automation disabled for Mid.")

    def test_toggle_tray_auto_ban_updates_global_setting(self):
        params = {"auto_ban_enabled": True}
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        mutable = MutableParamsWindow(params)
        window.get_params = mutable.get_params
        window.update_param = mutable.update_param
        window.show_toast = mutable.show_toast
        window.settings_win = mutable.settings_win

        window.toggle_tray_auto_ban()

        self.assertFalse(params["auto_ban_enabled"])
        self.assertEqual(window.settings_win.sync_calls, 1)
        self.assertEqual(mutable.toasts[0][0], "Auto-ban disabled.")

    def test_set_main_preview_presets_enabled_updates_global_flags_and_global_role(self):
        params = {
            "auto_pick_enabled": False,
            "auto_summoners_enabled": False,
            "presets_enabled": False,
        }
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        mutable = MutableParamsWindow(params)
        window.get_params = mutable.get_params
        window.update_param = mutable.update_param
        window._get_main_preview_role = lambda: "GLOBAL"

        window.set_main_preview_presets_enabled(True)

        self.assertTrue(params["auto_pick_enabled"])
        self.assertTrue(params["auto_summoners_enabled"])
        self.assertTrue(params["presets_enabled"])

    def test_set_main_preview_presets_enabled_updates_detected_role_profile(self):
        params = {
            "auto_pick_enabled": False,
            "auto_summoners_enabled": False,
            "presets_enabled": False,
            "role_profiles": {
                "MIDDLE": {
                    "presets_enabled": False,
                }
            },
        }
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        mutable = MutableParamsWindow(params)
        window.get_params = mutable.get_params
        window.update_param = mutable.update_param
        window._get_main_preview_role = lambda: "MIDDLE"

        window.set_main_preview_presets_enabled(True)

        self.assertTrue(params["auto_pick_enabled"])
        self.assertTrue(params["auto_summoners_enabled"])
        self.assertTrue(params["role_profiles"]["MIDDLE"]["presets_enabled"])

    def test_toggle_main_preview_feature_cycles_skin_modes_in_global_slot(self):
        params = {
            "main_skin_mode_override": "inherit",
            "main_skin_mode_overrides": {"pick_1": "inherit", "pick_2": "inherit", "pick_3": "inherit"},
            "pick_slots": {
                "pick_1": {
                    "skin_mode": "none",
                    "skin_id": 86000,
                    "skin_name": "Default Garen",
                    "skin_num": 0,
                    "random_skin_id": 86001,
                    "random_skin_name": "Fancy Garen",
                    "random_skin_num": 1,
                    "random_skin_pool": [{"skin_id": 86001, "skin_name": "Fancy Garen", "skin_num": 1}],
                }
            }
        }
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        mutable = MutableParamsWindow(params)
        window.get_params = mutable.get_params
        window.update_param = mutable.update_param
        window.show_toast = mutable.show_toast
        window.settings_win = mutable.settings_win
        window._sync_settings_window_if_open = lambda: mutable.settings_win._sync_from_params()
        window._get_main_preview_role = lambda: "TOP"
        window.get_effective_profile_config = lambda role=None: {
            "pick_slots": {
                "pick_1": {
                    "champion": "Garen",
                    "skin_mode": "fixed",
                    "skin_id": 86000,
                    "skin_name": "Default Garen",
                    "skin_num": 0,
                    "random_skin_id": 86001,
                    "random_skin_name": "Fancy Garen",
                    "random_skin_num": 1,
                    "random_skin_pool": [{"skin_id": 86001, "skin_name": "Fancy Garen", "skin_num": 1}],
                    "skin_source_role": "GLOBAL",
                },
                "pick_2": {
                    "champion": "Lux",
                    "skin_mode": "none",
                    "skin_id": 0,
                    "skin_name": "",
                    "skin_num": 0,
                    "random_skin_id": 0,
                    "random_skin_name": "",
                    "random_skin_num": 0,
                    "random_skin_pool": [],
                    "skin_source_role": "GLOBAL",
                },
                "pick_3": {
                    "champion": "Ashe",
                    "skin_mode": "none",
                    "skin_id": 0,
                    "skin_name": "",
                    "skin_num": 0,
                    "random_skin_id": 0,
                    "random_skin_name": "",
                    "random_skin_num": 0,
                    "random_skin_pool": [],
                    "skin_source_role": "GLOBAL",
                },
            }
        }

        window._toggle_main_preview_feature("skins")
        self.assertEqual(
            params["main_skin_mode_overrides"],
            {"pick_1": "fixed", "pick_2": "fixed", "pick_3": "fixed"},
        )
        self.assertEqual(mutable.toasts[-1][0], "Fixed skin enabled.")

        window._toggle_main_preview_feature("skins")
        self.assertEqual(
            params["main_skin_mode_overrides"],
            {"pick_1": "random", "pick_2": "random", "pick_3": "random"},
        )
        self.assertEqual(mutable.toasts[-1][0], "Random skins enabled.")

        window._toggle_main_preview_feature("skins")
        self.assertEqual(
            params["main_skin_mode_overrides"],
            {"pick_1": "none", "pick_2": "none", "pick_3": "none"},
        )
        self.assertEqual(mutable.toasts[-1][0], "Skin off.")

    def test_toggle_main_preview_skin_slot_cycles_only_target_slot(self):
        params = {
            "main_skin_mode_override": "inherit",
            "main_skin_mode_overrides": {"pick_1": "inherit", "pick_2": "inherit", "pick_3": "inherit"},
        }
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        mutable = MutableParamsWindow(params)
        window.get_params = mutable.get_params
        window.update_param = mutable.update_param
        window.show_toast = mutable.show_toast
        window.settings_win = mutable.settings_win
        window._sync_settings_window_if_open = lambda: mutable.settings_win._sync_from_params()
        window._get_main_preview_role = lambda: "GLOBAL"
        window.get_effective_profile_config = lambda role=None: {
            "pick_slots": {
                "pick_1": {
                    "champion": "Garen",
                    "skin_mode": "fixed",
                    "skin_id": 86000,
                    "skin_name": "Default Garen",
                    "skin_num": 0,
                    "random_skin_id": 86001,
                    "random_skin_name": "Fancy Garen",
                    "random_skin_num": 1,
                    "random_skin_pool": [{"skin_id": 86001, "skin_name": "Fancy Garen", "skin_num": 1}],
                },
                "pick_2": {
                    "champion": "Lux",
                    "skin_mode": "fixed",
                    "skin_id": 99010,
                    "skin_name": "Battle Academia Lux",
                    "skin_num": 10,
                    "random_skin_id": 0,
                    "random_skin_name": "",
                    "random_skin_num": 0,
                    "random_skin_pool": [],
                },
                "pick_3": {
                    "champion": "Ashe",
                    "skin_mode": "none",
                    "skin_id": 0,
                    "skin_name": "",
                    "skin_num": 0,
                    "random_skin_id": 0,
                    "random_skin_name": "",
                    "random_skin_num": 0,
                    "random_skin_pool": [],
                },
            }
        }

        window._toggle_main_preview_skin_slot("pick_1")
        self.assertEqual(params["main_skin_mode_overrides"]["pick_1"], "random")
        self.assertEqual(params["main_skin_mode_overrides"]["pick_2"], "inherit")
        self.assertEqual(mutable.toasts[-1][0], "Pick 1 random skin enabled.")

        window._toggle_main_preview_skin_slot("pick_2")
        self.assertEqual(params["main_skin_mode_overrides"]["pick_2"], "none")
        self.assertEqual(mutable.toasts[-1][0], "Pick 2 skin off.")

    def test_toggle_main_preview_feature_shows_toast_when_no_skin_is_configured(self):
        params = {
            "main_skin_mode_override": "inherit",
            "main_skin_mode_overrides": {"pick_1": "inherit", "pick_2": "inherit", "pick_3": "inherit"},
            "pick_slots": {
                "pick_1": {
                    "skin_mode": "none",
                    "skin_id": 0,
                    "skin_name": "",
                    "skin_num": 0,
                    "random_skin_id": 0,
                    "random_skin_name": "",
                    "random_skin_num": 0,
                    "random_skin_pool": [],
                }
            }
        }
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        mutable = MutableParamsWindow(params)
        window.get_params = mutable.get_params
        window.update_param = mutable.update_param
        window.show_toast = mutable.show_toast
        window.settings_win = mutable.settings_win
        window._get_main_preview_role = lambda: "GLOBAL"
        window.get_effective_profile_config = lambda role=None: {
            "pick_slots": {
                "pick_1": {
                    "champion": "Garen",
                    "skin_mode": "none",
                    "skin_id": 0,
                    "skin_name": "",
                    "skin_num": 0,
                    "random_skin_id": 0,
                    "random_skin_name": "",
                    "random_skin_num": 0,
                    "random_skin_pool": [],
                    "skin_source_role": "GLOBAL",
                },
                "pick_2": {
                    "champion": "Lux",
                    "skin_mode": "none",
                    "skin_id": 0,
                    "skin_name": "",
                    "skin_num": 0,
                    "random_skin_id": 0,
                    "random_skin_name": "",
                    "random_skin_num": 0,
                    "random_skin_pool": [],
                    "skin_source_role": "GLOBAL",
                },
                "pick_3": {
                    "champion": "Ashe",
                    "skin_mode": "none",
                    "skin_id": 0,
                    "skin_name": "",
                    "skin_num": 0,
                    "random_skin_id": 0,
                    "random_skin_name": "",
                    "random_skin_num": 0,
                    "random_skin_pool": [],
                    "skin_source_role": "GLOBAL",
                },
            }
        }

        window._toggle_main_preview_feature("skins")

        self.assertEqual(params["main_skin_mode_override"], "inherit")
        self.assertEqual(
            params["main_skin_mode_overrides"],
            {"pick_1": "inherit", "pick_2": "inherit", "pick_3": "inherit"},
        )
        self.assertEqual(mutable.toasts[-1][0], "No skin configured in presets.")

    def test_main_window_local_effective_profile_config_uses_global_skin_fallback(self):
        params = {
            "pick_slots": {
                "pick_1": {
                    "skin_mode": "fixed",
                    "skin_id": 86000,
                    "skin_name": "Default Garen",
                    "skin_num": 0,
                    "random_skin_id": 0,
                    "random_skin_name": "",
                    "random_skin_num": 0,
                    "random_skin_pool": [],
                }
            },
            "role_profiles": {
                "TOP": {
                    "selected_pick_1": "Garen",
                    "pick_slots": {
                        "pick_1": {
                            "skin_mode": "none",
                            "skin_id": 0,
                            "skin_name": "",
                            "skin_num": 0,
                            "random_skin_id": 0,
                            "random_skin_name": "",
                            "random_skin_num": 0,
                            "random_skin_pool": [],
                        }
                    },
                }
            },
        }
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        window.ws_manager = None
        window.get_params = lambda: params

        effective = window.get_effective_profile_config(role="TOP")

        self.assertEqual(effective["pick_slots"]["pick_1"]["skin_mode"], "fixed")
        self.assertEqual(effective["pick_slots"]["pick_1"]["skin_id"], 86000)
        self.assertEqual(effective["pick_slots"]["pick_1"]["skin_source_role"], "GLOBAL")

    def test_handle_core_event_schedules_close_for_real_disconnect(self):
        scheduled = []
        connection_updates = []
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        window.root = DummyRoot()
        window.disconnect_close_after_id = None
        window.update_connection_indicator = lambda connected: connection_updates.append(connected)
        window.get_params = lambda: {"close_app_on_lol_exit": True}
        window._schedule_disconnect_close = lambda: scheduled.append("scheduled")
        window._cancel_disconnect_close = lambda: scheduled.append("cancelled")
        window._queue_feature_preview_refresh = lambda: None
        window._refresh_stats_button = lambda: None
        window.history_window = None

        window._handle_core_event(WebSocketManager.EVENT_DISCONNECTED, None)

        self.assertEqual(connection_updates, [False])
        self.assertEqual(scheduled, ["scheduled"])

    def test_handle_core_event_does_not_schedule_close_for_transient_disconnect(self):
        actions = []
        connection_updates = []
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        window.root = DummyRoot()
        window.disconnect_close_after_id = None
        window.update_connection_indicator = lambda connected: connection_updates.append(connected)
        window.get_params = lambda: {"close_app_on_lol_exit": True}
        window._schedule_disconnect_close = lambda: actions.append("scheduled")
        window._cancel_disconnect_close = lambda: actions.append("cancelled")
        window._queue_feature_preview_refresh = lambda: None
        window._refresh_stats_button = lambda: None
        window.history_window = None

        window._handle_core_event(
            WebSocketManager.EVENT_DISCONNECTED,
            {"transient": True, "reason": "lcu_process_scan_failed"},
        )

        self.assertEqual(connection_updates, [False])
        self.assertEqual(actions, ["cancelled"])


if __name__ == "__main__":
    unittest.main()
