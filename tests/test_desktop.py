import ctypes
import json
import os
import sys
import tempfile
import time
import unittest
import socket
import urllib.request
from ctypes import wintypes
from threading import Event
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from src.desktop.bridge import DesktopBridge
from src.desktop.hotkeys import (
    HotkeyManager,
    _WindowsHotkeyBackend,
    parse_windows_hotkey,
)
from src.desktop.provider_browser import ProviderBrowserWindow, ProviderWindowManager
from src.desktop.server import EmbeddedApiServer
from src.desktop.tray import TrayController
from src.desktop.webview import _configure_hotkeys, _settings_update_changes_hotkeys
from src.desktop.window import (
    WebViewWindow,
    WebViewWindowConfig,
    _valid_window_position,
    get_webview2_runtime_version,
    has_webview2_runtime,
)


class FakeNativeWindow:
    def __init__(self):
        self.calls = []
        self.minimized = False

    def show(self):
        self.calls.append("show")

    def restore(self):
        self.calls.append("restore")
        self.minimized = False

    def hide(self):
        self.calls.append("hide")

    def destroy(self):
        self.calls.append("destroy")

    def load_url(self, url):
        self.calls.append(("load_url", url))

    def resize(self, width, height):
        self.calls.append(("resize", width, height))


class FakeEventSignal:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def fire(self):
        return [handler() for handler in self.handlers]


class DesktopWindowTests(unittest.TestCase):
    @patch("src.desktop.window.sys.platform", "win32")
    def test_saved_window_position_accepts_a_monitor_left_of_primary(self):
        class MonitorInfo(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        class FakeUser32:
            def EnumDisplayMonitors(self, _desktop, _clip, callback, _data):
                rect = wintypes.RECT()
                return callback(None, None, ctypes.byref(rect), 0)

            def GetMonitorInfoW(self, _monitor, info_pointer):
                work_area = ctypes.cast(info_pointer, ctypes.POINTER(MonitorInfo)).contents.rcWork
                work_area.left = -1920
                work_area.top = 0
                work_area.right = 0
                work_area.bottom = 1080
                return 1

        with patch.object(ctypes, "windll", SimpleNamespace(user32=FakeUser32()), create=True):
            self.assertTrue(_valid_window_position(-1800, 100))
            self.assertFalse(_valid_window_position(100, 100))

    def test_windows_hotkey_parser_supports_alt_c_and_named_modifiers(self):
        modifiers, virtual_key = parse_windows_hotkey("alt+c")
        self.assertEqual(virtual_key, ord("C"))
        self.assertTrue(modifiers & 0x0001)

        modifiers, virtual_key = parse_windows_hotkey("ctrl+shift+f12")
        self.assertEqual(virtual_key, 0x7B)
        self.assertTrue(modifiers & 0x0002)
        self.assertTrue(modifiers & 0x0004)

    def test_windows_hotkey_parser_rejects_duplicate_modifiers(self):
        with self.assertRaises(ValueError):
            parse_windows_hotkey("alt+alt+c")

    def test_windows_hotkeys_keep_working_when_one_shortcut_is_taken(self):
        quit_message = Event()

        class FakeUser32:
            def PeekMessageW(self, *_args):
                return 1

            def RegisterHotKey(self, _window, hotkey_id, _modifiers, _key):
                return hotkey_id != 2

            def GetMessageW(self, *_args):
                quit_message.wait(timeout=1)
                return 0

            def PostThreadMessageW(self, *_args):
                quit_message.set()
                return 1

            def UnregisterHotKey(self, *_args):
                return 1

        class FakeKernel32:
            def GetCurrentThreadId(self):
                return 123

            def GetLastError(self):
                return 1409

        backend = _WindowsHotkeyBackend()
        with patch("src.desktop.hotkeys.ctypes.windll", SimpleNamespace(user32=FakeUser32(), kernel32=FakeKernel32())):
            with self.assertLogs(level="INFO") as logs:
                self.assertTrue(backend.setup([("alt+c", lambda: None), ("alt+p", lambda: None)]))
            self.assertEqual(backend.registered_indices, {0})
            self.assertTrue(any("alt+p" in message and "1409" in message for message in logs.output))
            backend.shutdown()

    @patch("src.desktop.hotkeys.sys.platform", "linux")
    @patch("src.desktop.hotkeys.keyboard.remove_hotkey")
    @patch("src.desktop.hotkeys.keyboard.add_hotkey", side_effect=[1, 2])
    def test_keyboard_hook_registers_shortcuts_independently(self, add_hotkey, _remove_hotkey):
        manager = HotkeyManager()

        self.assertTrue(manager.setup(lambda: None, lambda: None, "alt+c", "alt+p"))
        manager.shutdown()

        self.assertEqual(add_hotkey.call_count, 2)
        self.assertEqual(add_hotkey.call_args_list[0].kwargs["suppress"], False)
        self.assertEqual(add_hotkey.call_args_list[1].kwargs["suppress"], False)

    @patch("src.desktop.hotkeys.sys.platform", "win32")
    @patch("src.desktop.hotkeys._RegisterHotKeyBackend")
    @patch("src.desktop.hotkeys.keyboard.add_hotkey", side_effect=[1, RuntimeError("hook unavailable")])
    def test_register_hotkey_fallback_is_scoped_to_the_failed_shortcut(self, add_hotkey, backend_type):
        backend = backend_type.return_value
        backend.setup.return_value = True
        backend.registered_indices = {0}
        manager = HotkeyManager()

        self.assertTrue(manager.setup(lambda: None, lambda: None, "alt+c", "alt+p"))

        backend.setup.assert_called_once()
        self.assertEqual(backend.setup.call_args.args[0][0][0], "alt+p")
        self.assertEqual(manager.status("alt+c", "alt+p"), {
            "window": {"hotkey": "alt+c", "backend": "keyboard_hook", "active": True},
            "site": {"hotkey": "alt+p", "backend": "register_hotkey", "active": True},
        })
        manager.shutdown()

    @patch("src.desktop.hotkeys.sys.platform", "linux")
    @patch("src.desktop.hotkeys.keyboard.remove_hotkey")
    @patch("src.desktop.hotkeys.keyboard.add_hotkey", side_effect=[1, 2, 3, 4])
    def test_hotkey_setup_cleans_up_before_reregistering(self, add_hotkey, remove_hotkey):
        manager = HotkeyManager()
        self.assertTrue(manager.setup(lambda: None, lambda: None, "alt+c", "alt+p"))
        self.assertTrue(manager.setup(lambda: None, lambda: None, "alt+c", "alt+p"))
        self.assertEqual(remove_hotkey.call_count, 2)
        manager.shutdown()

    def test_hotkey_listener_only_reloads_for_hotkey_settings(self):
        self.assertTrue(_settings_update_changes_hotkeys(SimpleNamespace(
            type="settings_updated", data={"keys": ["hotkey_toggle_window"]}
        )))
        self.assertFalse(_settings_update_changes_hotkeys(SimpleNamespace(
            type="settings_updated", data={"keys": ["presets_enabled"]}
        )))

    def test_live_stats_hotkey_shows_window_and_routes_internally_without_lcu_lookup(self):
        params = {"preferred_hotkey_site": "porofessor"}
        context = SimpleNamespace(
            get_params=lambda: params,
            runtime=SimpleNamespace(snapshot=Mock(side_effect=AssertionError("LCU must not be queried"))),
        )
        window = WebViewWindow(WebViewWindowConfig(title="OTP LOL", url="http://127.0.0.1:1234/"))
        native = FakeNativeWindow()
        native.minimized = True
        window.window = native

        class Hotkeys:
            def setup(self, **callbacks):
                self.callbacks = callbacks
                return True

        hotkeys = Hotkeys()
        self.assertTrue(_configure_hotkeys(context, hotkeys, window))
        hotkeys.callbacks["open_hotkey_site"]()

        self.assertEqual(native.calls, ["restore", "show", ("load_url", "http://127.0.0.1:1234/#live")])
        self.assertTrue(window.visible)

    def test_live_stats_hotkey_requests_provider_and_only_falls_back_when_unavailable(self):
        params = {"preferred_hotkey_site": "porofessor", "hotkey_open_site": "alt+p"}
        provider_manager = SimpleNamespace(request_open=Mock(return_value={"ok": True, "state": "loading"}))
        context = SimpleNamespace(get_params=lambda: params, provider_window_manager=provider_manager)
        window = WebViewWindow(WebViewWindowConfig(title="OTP LOL", url="http://127.0.0.1:1234/"))
        native = FakeNativeWindow()
        window.window = native

        class Hotkeys:
            def setup(self, **callbacks):
                self.callbacks = callbacks
                return True

        hotkeys = Hotkeys()
        self.assertTrue(_configure_hotkeys(context, hotkeys, window))
        hotkeys.callbacks["open_hotkey_site"]()
        provider_manager.request_open.assert_called_once_with("live", source="hotkey")
        self.assertEqual(native.calls, [])

        provider_manager.request_open.return_value = {"ok": False, "reason": "account_unavailable"}
        hotkeys.callbacks["open_hotkey_site"]()
        self.assertEqual(native.calls, ["show", ("load_url", "http://127.0.0.1:1234/#live")])

    def test_native_route_rejects_unknown_route(self):
        window = WebViewWindow(WebViewWindowConfig(title="OTP LOL", url="http://127.0.0.1:1234/"))
        native = FakeNativeWindow()
        window.window = native

        self.assertFalse(window.open_route("https://example.com"))
        self.assertEqual(native.calls, [])

    def test_visibility_and_settings_navigation_delegate_to_native_window(self):
        window = WebViewWindow(WebViewWindowConfig(title="OTP LOL", url="http://127.0.0.1:1234/"))
        native = FakeNativeWindow()
        window.window = native

        window.hide()
        self.assertFalse(window.visible)
        window.show()
        self.assertTrue(window.visible)
        window.open_settings()
        self.assertTrue(window.visible)
        window.destroy()

        self.assertEqual(native.calls, ["hide", "show", "show", ("load_url", "http://127.0.0.1:1234/#settings/general"), "destroy"])

    def test_user_close_hides_to_tray_and_explicit_destroy_still_quits(self):
        window = WebViewWindow(WebViewWindowConfig(title="OTP LOL", url="http://127.0.0.1:1234/"))
        native = FakeNativeWindow()
        window.window = native
        window.set_close_to_tray(True)

        self.assertFalse(window._on_closing())
        self.assertFalse(window.visible)
        self.assertEqual(native.calls, ["hide"])

        window.destroy()
        self.assertTrue(window._on_closing())
        self.assertEqual(native.calls, ["hide", "destroy"])

    def test_user_close_is_a_normal_quit_when_tray_is_unavailable(self):
        window = WebViewWindow(WebViewWindowConfig(title="OTP LOL", url="http://127.0.0.1:1234/"))
        native = FakeNativeWindow()
        window.window = native

        self.assertTrue(window._on_closing())
        self.assertEqual(native.calls, [])

    def test_native_bridge_resizes_with_the_window_minimum(self):
        window = WebViewWindow(WebViewWindowConfig(
            title="OTP LOL",
            url="http://127.0.0.1:1234/",
            min_width=420,
            min_height=250,
        ))
        native = FakeNativeWindow()
        window.window = native
        bridge = DesktopBridge()
        bridge.attach(window)

        bridge.resize_window(100, 100)

        self.assertEqual(native.calls, [("resize", 420, 250)])

    def test_window_config_is_resizable_and_restores_saved_bounds(self):
        class GeometryWindow(FakeNativeWindow):
            is_maximized = False

            def get_size(self):
                return (1280, 800)

            def get_position(self):
                return (20, 30)

            def move(self, x, y):
                self.calls.append(("move", x, y))

            def maximize(self):
                self.calls.append("maximize")

        config = WebViewWindowConfig(title="OTP LOL", url="http://127.0.0.1:1234/")
        self.assertTrue(config.resizable)
        self.assertEqual((config.min_width, config.min_height), (800, 540))
        window = WebViewWindow(config)
        native = GeometryWindow()
        window.window = native
        window.restore_geometry({"window_width": 1240, "window_height": 720, "window_x": 20, "window_y": 30, "window_maximized": True})
        self.assertEqual(native.calls[:3], [("move", 20, 30), ("resize", 1240, 720), "maximize"])
        self.assertEqual(window.geometry(), {"window_width": 1280, "window_height": 800, "window_x": 20, "window_y": 30, "window_maximized": False})

    def test_create_passes_saved_geometry_to_pywebview_before_start(self):
        calls = []
        native = FakeNativeWindow()
        closing = FakeEventSignal()
        fake_window = SimpleNamespace(
            events=SimpleNamespace(closing=closing, maximized=None, restored=None),
            hide=native.hide,
        )
        fake_webview = SimpleNamespace(
            create_window=lambda *args, **kwargs: calls.append((args, kwargs)) or fake_window
        )
        config = WebViewWindowConfig(
            title="OTP LOL",
            url="http://127.0.0.1:1234/",
            width=1240,
            height=720,
            x=20,
            y=30,
            maximized=True,
        )
        window = WebViewWindow(config)

        with patch.dict(sys.modules, {"webview": fake_webview}):
            window.create()

        window.set_close_to_tray(True)
        self.assertEqual(closing.fire(), [False])
        self.assertEqual(native.calls, ["hide"])

        self.assertEqual(calls, [(
            ("OTP LOL",),
            {
                "url": "http://127.0.0.1:1234/",
                "width": 1240,
                "height": 720,
                "min_size": (800, 540),
                "resizable": True,
                "maximized": True,
                "js_api": None,
                "x": 20,
                "y": 30,
            },
        )])

    def test_geometry_skips_unshown_pywebview_window(self):
        shown = SimpleNamespace(is_set=lambda: False)
        native = SimpleNamespace(events=SimpleNamespace(shown=shown))
        window = WebViewWindow(WebViewWindowConfig(title="OTP LOL", url="http://127.0.0.1:1234/"))
        window.window = native

        self.assertEqual(window.geometry(), {})

    def test_geometry_uses_pywebview_properties_when_legacy_methods_are_unavailable(self):
        class PropertyWindow(FakeNativeWindow):
            width = 1366
            height = 768
            x = 40
            y = 50

        window = WebViewWindow(WebViewWindowConfig(title="OTP LOL", url="http://127.0.0.1:1234/"))
        window.window = PropertyWindow()

        self.assertEqual(window.geometry(), {
            "window_width": 1366,
            "window_height": 768,
            "window_x": 40,
            "window_y": 50,
            "window_maximized": False,
        })

    @patch("src.desktop.bridge.webbrowser.open", return_value=True)
    def test_native_bridge_only_opens_allowlisted_https_urls(self, open_browser):
        bridge = DesktopBridge()

        self.assertTrue(bridge.open_external_url("https://op.gg/fr/summoners/euw/Test-Tag"))
        self.assertTrue(bridge.open_external_url("https://porofessor.gg/fr/live/euw/Test-Tag/ranked-only"))
        self.assertTrue(bridge.open_external_url("https://www.deeplol.gg/summoner/euw/Test-Tag"))
        self.assertTrue(bridge.open_external_url("https://www.leagueofgraphs.com/fr/summoner/euw/Test-Tag"))
        self.assertFalse(bridge.open_external_url("https://evil.example/"))
        self.assertFalse(bridge.open_external_url("http://op.gg/"))
        self.assertEqual(open_browser.call_count, 4)

    def test_provider_window_uses_an_allowlisted_top_level_url_without_the_app_bridge(self):
        created = []
        closed = Mock()
        close_event = FakeEventSignal()
        native = FakeNativeWindow()
        fake_window = SimpleNamespace(events=SimpleNamespace(closed=close_event), show=native.show)
        fake_webview = SimpleNamespace(
            settings={},
            create_window=lambda *args, **kwargs: created.append((args, kwargs)) or fake_window,
        )
        provider_window = ProviderBrowserWindow(
            "deeplol",
            "https://www.deeplol.gg/summoner/euw/Player-EUW/ingame",
            closed,
        )

        with patch.dict(sys.modules, {"webview": fake_webview}):
            self.assertTrue(provider_window.open())

        self.assertEqual(created[0][1]["url"], "https://www.deeplol.gg/summoner/euw/Player-EUW/ingame")
        self.assertIsNone(created[0][1]["js_api"])
        self.assertTrue(fake_webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"])
        close_event.fire()
        closed.assert_called_once_with()

    def test_provider_window_navigates_and_focuses_an_existing_window(self):
        native = FakeNativeWindow()
        provider_window = ProviderBrowserWindow(
            "deeplol",
            "https://www.deeplol.gg/summoner/euw/Player-EUW",
            Mock(),
        )
        provider_window.window = native
        native.minimized = True

        self.assertTrue(provider_window.navigate("opgg", "https://op.gg/fr/lol/summoners/euw/Player-EUW", reveal=True))
        self.assertEqual(provider_window.provider_id, "opgg")
        self.assertEqual(provider_window.url, "https://op.gg/fr/lol/summoners/euw/Player-EUW")
        self.assertEqual(native.calls, [("load_url", "https://op.gg/fr/lol/summoners/euw/Player-EUW"), "restore", "show"])

    def test_provider_bridge_builds_url_from_configured_account_and_rejects_other_provider(self):
        params = {
            "preferred_stats_site": "deeplol",
            "summoner_name_auto_detect": False,
            "manual_summoner_name": "Player#EUW",
            "manual_region": "euw",
        }
        context = SimpleNamespace(
            get_params=lambda: params,
            runtime=SimpleNamespace(snapshot=Mock(side_effect=AssertionError("manual account must not query LCU"))),
        )
        bridge = DesktopBridge(context)
        with patch("src.desktop.provider_browser.ProviderBrowserWindow.open", return_value=True):
            self.assertTrue(bridge.open_provider_window("deeplol", "stats"))
            self.assertFalse(bridge.open_provider_window("opgg", "stats"))

        self.assertEqual(
            bridge._provider_windows["stats"].url,
            "https://www.deeplol.gg/summoner/euw/Player-EUW",
        )

    def test_provider_bridge_uses_the_saved_account_when_league_is_closed(self):
        params = {
            "preferred_stats_site": "deeplol",
            "summoner_name_auto_detect": True,
            "auto_detected_riot_id": "Saved#EUW",
            "auto_detected_region": "euw",
            "auto_detected_platform": "euw1",
        }
        context = SimpleNamespace(
            get_params=lambda: params,
            runtime=SimpleNamespace(snapshot=Mock(return_value=SimpleNamespace(connected=False, riot_id="", region=""))),
        )
        bridge = DesktopBridge(context)
        with patch("src.desktop.provider_browser.ProviderBrowserWindow.open", return_value=True):
            self.assertTrue(bridge.open_provider_window("deeplol", "stats"))

        self.assertEqual(
            bridge._provider_windows["stats"].url,
            "https://www.deeplol.gg/summoner/euw/Saved-EUW",
        )

    def test_provider_bridge_reuses_and_navigates_one_window_per_kind(self):
        params = {
            "preferred_stats_site": "deeplol",
            "summoner_name_auto_detect": False,
            "manual_summoner_name": "Player#EUW",
            "manual_region": "euw",
        }
        context = SimpleNamespace(
            get_params=lambda: params,
            runtime=SimpleNamespace(snapshot=Mock(side_effect=AssertionError("manual account must not query LCU"))),
        )
        bridge = DesktopBridge(context)
        provider_window = Mock()
        provider_window.window = object()
        provider_window.provider_id = "deeplol"
        provider_window.url = "https://www.deeplol.gg/summoner/euw/Player-EUW"
        with patch("src.desktop.provider_browser.ProviderBrowserWindow", return_value=provider_window):
            provider_window.open.return_value = True
            self.assertTrue(bridge.open_provider_window("deeplol", "stats"))
            self.assertTrue(bridge.open_provider_window("deeplol", "stats"))
            params["preferred_stats_site"] = "opgg"
            self.assertTrue(bridge.open_provider_window("opgg", "stats"))

        provider_window.focus.assert_called_once_with()
        provider_window.navigate.assert_called_once_with("opgg", "https://op.gg/fr/lol/summoners/euw/Player-EUW", reveal=True)

    def test_provider_preload_is_hidden_only_once_and_user_show_stays_visible(self):
        native = FakeNativeWindow()
        events = SimpleNamespace(loaded=FakeEventSignal(), shown=FakeEventSignal(), closed=FakeEventSignal())
        native.events = events
        provider_window = ProviderBrowserWindow(
            "deeplol",
            "https://www.deeplol.gg/summoner/euw/Player-EUW",
            Mock(),
        )
        with patch.dict(sys.modules, {"webview": SimpleNamespace(settings={}, create_window=lambda *_args, **_kwargs: native)}):
            self.assertTrue(provider_window.open(preload=True))
        events.shown.fire()
        self.assertEqual(provider_window.state, "hidden")
        events.loaded.fire()
        self.assertEqual(provider_window.state, "hidden")

        provider_window.focus()
        events.shown.fire()
        self.assertEqual(provider_window.state, "visible")
        self.assertEqual(native.calls.count("hide"), 1)

    def test_provider_show_during_loading_is_revealed_after_load(self):
        native = FakeNativeWindow()
        events = SimpleNamespace(loaded=FakeEventSignal(), shown=FakeEventSignal(), closed=FakeEventSignal())
        native.events = events
        provider_window = ProviderBrowserWindow(
            "deeplol",
            "https://www.deeplol.gg/summoner/euw/Player-EUW",
            Mock(),
        )
        with patch.dict(sys.modules, {"webview": SimpleNamespace(settings={}, create_window=lambda *_args, **_kwargs: native)}):
            self.assertTrue(provider_window.open(preload=True))
        events.shown.fire()
        provider_window.request_reveal()
        events.loaded.fire()
        self.assertEqual(provider_window.state, "visible")
        self.assertIn("show", native.calls)

    def test_provider_reused_window_becomes_visible_when_show_has_no_second_shown_event(self):
        native = FakeNativeWindow()
        shown = Mock()
        provider_window = ProviderBrowserWindow(
            "deeplol",
            "https://www.deeplol.gg/summoner/euw/Player-EUW",
            Mock(),
            on_shown=shown,
        )
        provider_window.window = native
        provider_window.state = "hidden"
        provider_window.last_loaded_url = provider_window.url

        self.assertTrue(provider_window.focus())
        self.assertEqual(provider_window.state, "visible")
        shown.assert_called_once_with()

    def test_provider_background_navigation_does_not_focus_hidden_window(self):
        native = FakeNativeWindow()
        provider_window = ProviderBrowserWindow(
            "deeplol",
            "https://www.deeplol.gg/summoner/euw/Player-EUW",
            Mock(),
        )
        provider_window.window = native
        provider_window.state = "hidden"
        self.assertTrue(provider_window.navigate("opgg", "https://op.gg/fr/lol/summoners/euw/Player-EUW"))
        self.assertEqual(native.calls, [("load_url", "https://op.gg/fr/lol/summoners/euw/Player-EUW")])
        provider_window._on_loaded()
        self.assertEqual(provider_window.state, "hidden")

    def test_provider_background_navigation_preserves_visible_window(self):
        native = FakeNativeWindow()
        events = SimpleNamespace(loaded=FakeEventSignal(), shown=FakeEventSignal(), closed=FakeEventSignal())
        native.events = events
        provider_window = ProviderBrowserWindow(
            "deeplol",
            "https://www.deeplol.gg/summoner/euw/Player-EUW",
            Mock(),
        )
        provider_window.window = native
        provider_window.state = "visible"
        provider_window._visible_requested = True
        provider_window._native_shown = True
        native.set_title = lambda title: native.calls.append(("set_title", title))
        self.assertTrue(provider_window.navigate("opgg", "https://op.gg/fr/lol/summoners/euw/Player-EUW"))
        self.assertEqual(native.calls, [("set_title", "OP.GG | OTP LOL"), ("load_url", "https://op.gg/fr/lol/summoners/euw/Player-EUW")])
        provider_window._on_loaded()
        self.assertEqual(provider_window.state, "visible")

    def test_closed_provider_window_can_be_reopened(self):
        class ProviderNative(FakeNativeWindow):
            def __init__(self):
                super().__init__()
                self.events = SimpleNamespace(loaded=FakeEventSignal(), shown=FakeEventSignal(), closed=FakeEventSignal())

            def set_title(self, _title):
                pass

        params = {
            "preferred_stats_site": "opgg",
            "preferred_hotkey_site": "porofessor",
            "summoner_name_auto_detect": False,
            "manual_summoner_name": "Player#EUW",
            "manual_region": "euw",
        }
        context = SimpleNamespace(get_params=lambda: params, runtime=SimpleNamespace(snapshot=Mock()))
        created: list[ProviderNative] = []
        fake_webview = SimpleNamespace(settings={}, create_window=lambda *_args, **_kwargs: created.append(ProviderNative()) or created[-1])
        manager = ProviderWindowManager(context)
        old = ProviderBrowserWindow("opgg", "https://op.gg/fr/lol/summoners/euw/Player-EUW", Mock())
        old.window = ProviderNative()
        manager._windows["stats"] = old
        old.close()
        manager.mark_main_window_shown(preload=False)

        with patch.dict(sys.modules, {"webview": fake_webview}):
            result = manager.open_result("opgg", "stats")

        self.assertTrue(result["ok"])
        self.assertEqual(len(created), 1)
        self.assertEqual(manager.status()["stats"]["state"], "loading")

    def test_provider_manager_waits_for_main_window_and_reuses_each_kind(self):
        class ProviderNative(FakeNativeWindow):
            def __init__(self):
                super().__init__()
                self.events = SimpleNamespace(
                    loaded=FakeEventSignal(),
                    shown=FakeEventSignal(),
                    closed=FakeEventSignal(),
                )

            def bring_to_front(self):
                self.calls.append("bring_to_front")

            def reload(self):
                self.calls.append("reload")

            def destroy(self):
                self.calls.append("destroy")

            def set_title(self, title):
                self.calls.append(("set_title", title))

        params = {
            "preferred_stats_site": "deeplol",
            "preferred_hotkey_site": "porofessor",
            "summoner_name_auto_detect": False,
            "manual_summoner_name": "Player#EUW",
            "manual_region": "euw",
        }
        context = SimpleNamespace(get_params=lambda: params, runtime=SimpleNamespace(snapshot=Mock()))
        created: list[ProviderNative] = []
        fake_webview = SimpleNamespace(
            settings={},
            create_window=lambda *_args, **_kwargs: created.append(ProviderNative()) or created[-1],
        )
        manager = ProviderWindowManager(context)

        with patch.dict(sys.modules, {"webview": fake_webview}):
            self.assertFalse(manager.open("deeplol", "stats"))
            manager.mark_main_window_shown(preload=False)
            self.assertTrue(manager.open("deeplol", "stats"))
            created[0].events.loaded.fire()
            self.assertEqual(manager.status()["stats"]["state"], "visible")
            self.assertTrue(manager.reload("stats"))
            self.assertIn("reload", created[0].calls)
            params["preferred_stats_site"] = "opgg"
            self.assertTrue(manager.open("opgg", "stats"))

        self.assertEqual(len(created), 1)
        self.assertEqual(manager.status()["stats"]["provider_id"], "opgg")
        self.assertIn(("set_title", "OP.GG | OTP LOL"), created[0].calls)

    def test_provider_manager_preloads_only_after_main_window_shown_and_shutdown_rejects_actions(self):
        class ProviderNative(FakeNativeWindow):
            def __init__(self):
                super().__init__()
                self.events = SimpleNamespace(loaded=FakeEventSignal(), shown=FakeEventSignal(), closed=FakeEventSignal())

            def bring_to_front(self):
                pass

        params = {
            "preferred_stats_site": "opgg",
            "preferred_hotkey_site": "porofessor",
            "summoner_name_auto_detect": False,
            "manual_summoner_name": "Player#EUW",
            "manual_region": "euw",
        }
        context = SimpleNamespace(get_params=lambda: params, runtime=SimpleNamespace(snapshot=Mock()))
        created: list[ProviderNative] = []
        fake_webview = SimpleNamespace(settings={}, create_window=lambda *_args, **_kwargs: created.append(ProviderNative()) or created[-1])
        manager = ProviderWindowManager(context)

        with patch.dict(sys.modules, {"webview": fake_webview}):
            manager.preload()
            self.assertEqual(created, [])
            manager.mark_main_window_shown(preload=True)
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline and len(created) < 2:
                time.sleep(0.01)
            self.assertLessEqual(len(created), 2)
            self.assertNotEqual(manager.status()["stats"]["state"], "not_created")
            manager.shutdown()

        self.assertTrue(manager.shutting_down)
        self.assertEqual(manager.status()["stats"]["state"], "closed")
        self.assertFalse(manager.open("opgg", "stats"))
        self.assertFalse(manager.reload("stats"))
        self.assertFalse(manager.show("stats"))
        self.assertFalse(manager.request_show("stats")["ok"])
        self.assertFalse(manager.request_hide("stats")["ok"])

    def test_provider_manager_async_open_focuses_an_existing_visible_window(self):
        params = {
            "preferred_stats_site": "opgg",
            "preferred_hotkey_site": "porofessor",
            "summoner_name_auto_detect": False,
            "manual_summoner_name": "Player#EUW",
            "manual_region": "euw",
        }
        context = SimpleNamespace(get_params=lambda: params, runtime=SimpleNamespace(snapshot=Mock()))
        manager = ProviderWindowManager(context)
        manager._main_window_ready = True
        url = "https://op.gg/fr/lol/summoners/euw/Player-EUW"
        native = FakeNativeWindow()
        window = ProviderBrowserWindow("opgg", url, Mock())
        window.window = native
        window.state = "visible"
        manager._windows["stats"] = window

        result = manager.request_open("stats")
        self.assertTrue(result["ok"])
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline and "show" not in native.calls:
            time.sleep(0.01)

        self.assertIn("show", native.calls)

    def test_provider_manager_rejects_remote_actions_without_network(self):
        context = SimpleNamespace(
            get_params=lambda: {},
            network_status=SimpleNamespace(is_online=lambda: False),
        )
        manager = ProviderWindowManager(context)
        manager.mark_main_window_shown(preload=False)

        result = manager.request_open("stats")

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "network_unavailable")

    def test_provider_manager_can_show_existing_window_when_network_is_lost(self):
        context = SimpleNamespace(
            get_params=lambda: {},
            network_status=SimpleNamespace(is_online=lambda: False),
        )
        manager = ProviderWindowManager(context)
        native = FakeNativeWindow()
        window = ProviderBrowserWindow("opgg", "https://op.gg/", Mock())
        window.window = native
        window.state = "hidden"
        manager._windows["stats"] = window
        manager.mark_main_window_shown(preload=False)

        result = manager.request_show("stats")

        self.assertTrue(result["ok"])
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline and "show" not in native.calls:
            time.sleep(0.01)
        self.assertIn("show", native.calls)

    def test_provider_manager_can_open_existing_window_when_network_is_lost(self):
        params = {
            "preferred_stats_site": "opgg",
            "summoner_name_auto_detect": False,
            "manual_summoner_name": "Player#EUW",
            "manual_region": "euw",
        }
        context = SimpleNamespace(
            get_params=lambda: params,
            runtime=SimpleNamespace(snapshot=Mock()),
            network_status=SimpleNamespace(is_online=lambda: False),
        )
        manager = ProviderWindowManager(context)
        native = FakeNativeWindow()
        url = "https://op.gg/fr/lol/summoners/euw/Player-EUW"
        window = ProviderBrowserWindow("opgg", url, Mock())
        window.window = native
        window.state = "hidden"
        window.last_loaded_url = url
        manager._windows["stats"] = window
        manager.mark_main_window_shown(preload=False)

        result = manager.request_open("stats")

        self.assertTrue(result["ok"])
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline and "show" not in native.calls:
            time.sleep(0.01)
        self.assertIn("show", native.calls)

    def test_provider_window_survives_disconnect_and_reconnect(self):
        params = {
            "preferred_stats_site": "opgg",
            "preferred_hotkey_site": "porofessor",
            "summoner_name_auto_detect": False,
            "manual_summoner_name": "Player#EUW",
            "manual_region": "euw",
        }
        network = {"online": True}
        context = SimpleNamespace(
            get_params=lambda: params,
            runtime=SimpleNamespace(snapshot=Mock()),
            network_status=SimpleNamespace(is_online=lambda: network["online"]),
        )
        manager = ProviderWindowManager(context)
        manager.mark_main_window_shown(preload=False)
        native = FakeNativeWindow()
        window = ProviderBrowserWindow(
            "opgg", "https://op.gg/fr/lol/summoners/euw/Player-EUW", Mock()
        )
        window.window = native
        window.state = "hidden"
        window.last_loaded_url = window.url
        manager._windows["stats"] = window

        network["online"] = False
        result = manager.request_open("stats")
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline and "show" not in native.calls:
            time.sleep(0.01)
        self.assertTrue(result["ok"])
        self.assertIn("show", native.calls)

        network["online"] = True
        params["manual_summoner_name"] = "Reconnect#EUW"
        manager.preload()
        self.assertIn(
            ("load_url", "https://op.gg/fr/lol/summoners/euw/Reconnect-EUW"),
            native.calls,
        )

    def test_provider_shutdown_closes_every_window_and_stops_preload_timer(self):
        class ProviderNative(FakeNativeWindow):
            def __init__(self):
                super().__init__()
                self.events = SimpleNamespace(
                    loaded=FakeEventSignal(),
                    shown=FakeEventSignal(),
                    closed=FakeEventSignal(),
                )

        params = {
            "preferred_stats_site": "opgg",
            "preferred_hotkey_site": "porofessor",
            "summoner_name_auto_detect": False,
            "manual_summoner_name": "Player#EUW",
            "manual_region": "euw",
        }
        context = SimpleNamespace(get_params=lambda: params, runtime=SimpleNamespace(snapshot=Mock()))
        created = []
        fake_webview = SimpleNamespace(
            settings={},
            create_window=lambda *_args, **_kwargs: created.append(ProviderNative()) or created[-1],
        )
        manager = ProviderWindowManager(context)
        manager.mark_main_window_shown(preload=False)
        with patch.dict(sys.modules, {"webview": fake_webview}):
            self.assertTrue(manager.create("stats", "opgg"))
            self.assertTrue(manager.create("live", "porofessor"))
            manager.schedule_preload(delay=60)
            manager.shutdown()

        self.assertEqual(len(created), 2)
        self.assertTrue(all("destroy" in native.calls for native in created))
        self.assertTrue(manager.shutting_down)
        self.assertIsNone(manager._preload_timer)

    def test_diagnostics_export_native_success_cancel_and_write_error(self):
        class ReadyNative(FakeNativeWindow):
            def __init__(self, selected):
                super().__init__()
                self.selected = selected
                self.events = SimpleNamespace(shown=SimpleNamespace(is_set=lambda: True))

            def create_file_dialog(self, *_args, **_kwargs):
                return self.selected

        report = {"runtime": {"connected": False}, "errors": []}
        context = SimpleNamespace(diagnostics=SimpleNamespace(export=Mock(return_value=report)))
        bridge = DesktopBridge(context)
        with tempfile.TemporaryDirectory() as directory:
            target = os.path.join(directory, "report.json")
            window = WebViewWindow(WebViewWindowConfig(title="OTP LOL", url="http://127.0.0.1:1234/"))
            window.window = ReadyNative(target)
            bridge.attach(window)
            with patch.dict(sys.modules, {"webview": SimpleNamespace(SAVE_DIALOG="save")}):
                result = bridge.export_diagnostics_report(True)
            self.assertEqual(result, {"success": True, "path": target})
            self.assertEqual(json.loads(open(target, encoding="utf-8").read()), report)
            context.diagnostics.export.assert_called_with(True)

            window.window.selected = None
            with patch.dict(sys.modules, {"webview": SimpleNamespace(SAVE_DIALOG="save")}):
                self.assertEqual(bridge.export_diagnostics_report(), {"success": False, "cancelled": True})

            window.window.selected = target
            with patch("builtins.open", side_effect=OSError("disk full")):
                with patch.dict(sys.modules, {"webview": SimpleNamespace(SAVE_DIALOG="save")}):
                    error = bridge.export_diagnostics_report()
            self.assertFalse(error["success"])
            self.assertIn("disk full", error["error"])

    def test_tray_setup_failure_disables_close_to_tray_fallback(self):
        failed = Mock()
        tray = TrayController()

        with patch("src.desktop.tray.Image.open", side_effect=OSError("missing icon")):
            with self.assertLogs(level="WARNING"):
                available = tray.setup(
                    executor=Mock(),
                    toggle_window=Mock(),
                    open_settings=Mock(),
                    toggle_presets_automation=Mock(),
                    is_presets_automation_enabled=Mock(return_value=False),
                    quit_callback=Mock(),
                    on_failure=failed,
                )

        self.assertFalse(available)
        failed.assert_called_once_with()

    def test_tray_exposes_only_the_preset_automation_master(self):
        items = {}
        master_toggle = Mock()
        tray = TrayController()
        fake_image = Mock()
        fake_image.resize.return_value = object()

        def menu_item(label, callback, **options):
            items[label] = (callback, options)
            return label

        with (
            patch("src.desktop.tray.Image.open", return_value=fake_image),
            patch("src.desktop.tray.pystray.MenuItem", side_effect=menu_item),
            patch("src.desktop.tray.pystray.Menu", side_effect=lambda *entries: entries),
            patch("src.desktop.tray.pystray.Icon"),
        ):
            self.assertTrue(tray.setup(
                executor=Mock(),
                toggle_window=Mock(),
                open_settings=Mock(),
                toggle_presets_automation=master_toggle,
                is_presets_automation_enabled=Mock(return_value=False),
                quit_callback=Mock(),
                on_failure=Mock(),
            ))

        self.assertEqual(set(items), {"Show/Hide", "Settings", "Enable presets automations", "Quit"})
        items["Enable presets automations"][0]()
        master_toggle.assert_called_once_with()

    @patch("src.desktop.window.has_webview2_runtime", return_value=True)
    def test_start_passes_the_configured_icon_to_pywebview(self, _runtime):
        calls = []
        fake_webview = SimpleNamespace(start=lambda **kwargs: calls.append(kwargs))
        window = WebViewWindow(WebViewWindowConfig(title="OTP LOL", url="http://127.0.0.1:1234/", icon="garen.ico"))

        with patch.dict(sys.modules, {"webview": fake_webview}):
            window.start()

        self.assertEqual(calls, [{"debug": False, "icon": "garen.ico"}])

    @patch("src.desktop.window.sys.platform", "linux")
    def test_non_windows_runtime_does_not_require_registry_access(self):
        self.assertTrue(has_webview2_runtime())
        self.assertIsNone(get_webview2_runtime_version())

    @patch("src.desktop.window.sys.platform", "win32")
    def test_webview2_version_reads_only_a_valid_registered_version(self):
        registry = MagicMock()
        registry.HKEY_CURRENT_USER = 1
        registry.HKEY_LOCAL_MACHINE = 2
        registry.OpenKey.return_value.__enter__.return_value = object()
        registry.QueryValueEx.return_value = ("145.0.1.2", None)
        with patch.dict(sys.modules, {"winreg": registry}):
            self.assertEqual(get_webview2_runtime_version(), "145.0.1.2")


class FakeApiServer:
    instances = []

    def __init__(self):
        self.should_exit = False
        self.run_count = 0
        self.instances.append(self)

    def run(self, sockets=None):
        self.sockets = sockets or []
        self.socket_name = self.sockets[0].getsockname() if self.sockets else None
        self.run_count += 1
        if self.run_count == 1:
            return
        while not self.should_exit:
            time.sleep(0.01)


class EmbeddedApiServerTests(unittest.TestCase):
    def test_server_restarts_after_an_unexpected_exit_and_stops(self):
        FakeApiServer.instances = []
        server = EmbeddedApiServer(
            object(),
            host="127.0.0.1",
            port=1234,
            server_factory=FakeApiServer,
        )

        server.start()
        deadline = time.monotonic() + 3
        while len(FakeApiServer.instances) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        server.stop()

        self.assertGreaterEqual(len(FakeApiServer.instances), 2)

    def test_ephemeral_port_is_reserved_before_server_thread_runs(self):
        FakeApiServer.instances = []
        server = EmbeddedApiServer(
            object(), host="127.0.0.1", port=0, server_factory=FakeApiServer
        )

        server.start()
        try:
            self.assertGreater(server.port, 0)
            deadline = time.monotonic() + 1
            while (
                (not FakeApiServer.instances or not hasattr(FakeApiServer.instances[0], "socket_name"))
                and time.monotonic() < deadline
            ):
                time.sleep(0.01)
            self.assertTrue(FakeApiServer.instances)
            bound = FakeApiServer.instances[0]
            self.assertEqual(bound.socket_name[1], server.port)
        finally:
            server.stop()

    def test_port_is_released_after_stop_and_start_stop_can_repeat(self):
        FakeApiServer.instances = []
        server = EmbeddedApiServer(
            object(), host="127.0.0.1", port=0, server_factory=FakeApiServer
        )

        for _ in range(2):
            server.start()
            port = server.port
            self.assertGreater(port, 0)
            server.stop()
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind(("127.0.0.1", port))

    def test_health_endpoint_responds_on_reserved_port(self):
        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        server = EmbeddedApiServer(app, host="127.0.0.1", port=0)
        server.start()
        try:
            deadline = time.monotonic() + 5
            response = None
            while time.monotonic() < deadline:
                try:
                    response = urllib.request.urlopen(
                        f"http://127.0.0.1:{server.port}/health", timeout=0.5
                    )
                    break
                except OSError:
                    time.sleep(0.05)
            self.assertIsNotNone(response)
            assert response is not None
            with response:
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read()), {"status": "ok"})
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
