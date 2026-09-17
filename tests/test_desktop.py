import ctypes
import sys
import time
import unittest
from ctypes import wintypes
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.desktop.bridge import DesktopBridge
from src.desktop.hotkeys import (
    HotkeyManager,
    _WindowsHotkeyBackend,
    parse_windows_hotkey,
)
from src.desktop.server import EmbeddedApiServer
from src.desktop.provider_browser import ProviderBrowserWindow
from src.desktop.tray import TrayController
from src.desktop.webview import _configure_hotkeys, _settings_update_changes_hotkeys
from src.desktop.window import (
    WebViewWindow,
    WebViewWindowConfig,
    _valid_window_position,
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
    def test_fallback_hotkeys_log_success_without_a_warning(self, add_hotkey, _remove_hotkey):
        manager = HotkeyManager()

        with self.assertLogs(level="INFO") as logs:
            self.assertTrue(manager.setup(lambda: None, lambda: None, "alt+c", "alt+p"))
        manager.shutdown()

        self.assertEqual(add_hotkey.call_count, 2)
        self.assertTrue(any("fallback hook" in message for message in logs.output))

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
            bridge._provider_windows[("deeplol", "stats")].url,
            "https://www.deeplol.gg/summoner/euw/Player-EUW",
        )

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
                    toggle_auto_ban=Mock(),
                    is_presets_automation_enabled=Mock(return_value=False),
                    is_auto_ban_enabled=Mock(return_value=False),
                    quit_callback=Mock(),
                    on_failure=failed,
                )

        self.assertFalse(available)
        failed.assert_called_once_with()

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


class FakeApiServer:
    instances = []

    def __init__(self):
        self.should_exit = False
        self.run_count = 0
        self.instances.append(self)

    def run(self):
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


if __name__ == "__main__":
    unittest.main()
