"""Run the FastAPI runtime inside a local pywebview window."""

from __future__ import annotations

import asyncio
import logging
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Thread
from urllib.error import URLError
from urllib.request import urlopen

from ..api.app import create_app
from ..api.context import ApplicationContext
from ..config import APP_IMAGE_FILES, APP_NAME, CURRENT_VERSION, resource_path
from ..services.single_instance import check_single_instance, remove_lockfile
from .audio import AudioManager
from .bridge import DesktopBridge
from .hotkeys import HotkeyManager
from .server import EmbeddedApiServer
from .tray import TrayController
from .window import WebViewWindow, WebViewWindowConfig, has_webview2_runtime

_HOST = "127.0.0.1"
_SERVER_READY_TIMEOUT_S = 15.0
_NATIVE_WINDOW_WIDTH = 1100
_NATIVE_WINDOW_HEIGHT = 760
_HOTKEY_SETTING_KEYS = frozenset({"hotkey_toggle_window", "hotkey_open_site"})


def _find_free_port() -> int:
    """Reserve a local port number for the short-lived embedded API server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((_HOST, 0))
        return int(probe.getsockname()[1])


def _frontend_dist_dir() -> Path:
    """Resolve frontend assets from source checkout or a PyInstaller bundle."""
    module_root = Path(__file__).resolve().parents[2]
    candidates = [
        module_root / "frontend" / "dist",
        Path(getattr(sys, "_MEIPASS", module_root)) / "frontend" / "dist",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        "Frontend build not found. Run `npm run build` in frontend before launching the WebView."
    )


def _wait_for_server(port: int, timeout: float = _SERVER_READY_TIMEOUT_S) -> None:
    """Wait until FastAPI serves its health endpoint or fail with a clear error."""
    health_url = f"http://{_HOST}:{port}/api/health"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(health_url, timeout=0.4) as response:
                if response.status == 200:
                    return
        except (OSError, URLError):
            time.sleep(0.1)
    raise TimeoutError(f"Embedded API did not become ready within {timeout:.0f}s")


def _start_audio_listener(context: ApplicationContext, audio: AudioManager) -> tuple[Event, Thread]:
    """Forward ready-check events to the optional native audio service."""
    stop_event = Event()

    async def consume() -> None:
        subscription = context.broker.subscribe()
        try:
            while not stop_event.is_set():
                try:
                    event = await asyncio.wait_for(subscription.next_event(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                if event.type == "ready_check_accepted":
                    audio.play_accept_sound()
        finally:
            subscription.close()

    def run() -> None:
        asyncio.run(consume())

    thread = Thread(target=run, daemon=True, name="otp-lol-audio-events")
    thread.start()
    return stop_event, thread


def _configure_hotkeys(context: ApplicationContext, hotkeys: HotkeyManager, window: WebViewWindow) -> bool:
    """Register the current shortcuts and keep their callbacks bound to the native window."""
    params = context.get_params()
    return hotkeys.setup(
        toggle_window=lambda: _toggle_window(window),
        open_hotkey_site=lambda: window.open_route("live"),
        toggle_hotkey=str(params.get("hotkey_toggle_window") or "alt+c"),
        stats_hotkey=str(params.get("hotkey_open_site") or "alt+p"),
    )


def _start_hotkey_listener(
    context: ApplicationContext,
    hotkeys: HotkeyManager,
    window: WebViewWindow,
) -> tuple[Event, Thread]:
    """Reload global shortcuts when their settings change in the WebView."""
    stop_event = Event()

    async def consume() -> None:
        subscription = context.broker.subscribe()
        try:
            while not stop_event.is_set():
                try:
                    event = await asyncio.wait_for(subscription.next_event(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                if _settings_update_changes_hotkeys(event):
                    _configure_hotkeys(context, hotkeys, window)
        finally:
            subscription.close()

    def run() -> None:
        asyncio.run(consume())

    thread = Thread(target=run, daemon=True, name="otp-lol-hotkey-settings")
    thread.start()
    return stop_event, thread


def _settings_update_changes_hotkeys(event) -> bool:
    """Return whether a settings event changes one of the global shortcuts."""
    if event.type != "settings_updated" or not isinstance(event.data, dict):
        return False
    keys = event.data.get("keys")
    if not isinstance(keys, (list, tuple, set, frozenset)):
        return False
    return bool(_HOTKEY_SETTING_KEYS.intersection(keys))


def run_webview() -> None:
    """Start the local API, open the web UI, and shut both down together."""
    startup_started = time.perf_counter()
    logging.info("[STARTUP] T0 launcher=%.0fms", 0.0)
    if not check_single_instance():
        logging.info("Another instance is already running. Closing.")
        return

    server: EmbeddedApiServer | None = None
    services_executor: ThreadPoolExecutor | None = None
    audio: AudioManager | None = None
    audio_stop: Event | None = None
    audio_thread: Thread | None = None
    hotkey_stop: Event | None = None
    hotkey_thread: Thread | None = None
    hotkeys: HotkeyManager | None = None
    tray: TrayController | None = None
    context: ApplicationContext | None = None
    window: WebViewWindow | None = None
    try:
        frontend_dir = _frontend_dist_dir()
        if not has_webview2_runtime():
            raise RuntimeError("Microsoft Edge WebView2 Runtime is required to open OTP LOL.")
        context = ApplicationContext.from_system()
        logging.info("[STARTUP] T1 settings loaded=%.0fms", (time.perf_counter() - startup_started) * 1000)
        api = create_app(context, frontend_dir=frontend_dir)
        port = _find_free_port()
        server = EmbeddedApiServer(api, host=_HOST, port=port)
        server.start()
        _wait_for_server(port)
        logging.info("[STARTUP] T2 FastAPI ready=%.0fms", (time.perf_counter() - startup_started) * 1000)

        bridge = DesktopBridge(context)
        params = context.get_params()
        window = WebViewWindow(
            WebViewWindowConfig(
                title=f"{APP_NAME} v{CURRENT_VERSION}",
                url=f"http://{_HOST}:{port}/",
                width=int(params.get("window_width", _NATIVE_WINDOW_WIDTH)),
                height=int(params.get("window_height", _NATIVE_WINDOW_HEIGHT)),
                x=int(params.get("window_x", 0) or 0),
                y=int(params.get("window_y", 0) or 0),
                maximized=bool(params.get("window_maximized", False)),
                min_width=800,
                min_height=540,
                resizable=True,
                icon=resource_path(APP_IMAGE_FILES["icon_ico"]),
                js_api=bridge,
            )
        )
        bridge.attach(window)
        window.create()
        context.diagnostics.record_event("otp-lol/webview", "created", {})
        context.bind_window(window, shutdown_callback=window.destroy)
        logging.info("[STARTUP] T3 WebView created=%.0fms", (time.perf_counter() - startup_started) * 1000)

        services_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="otp-lol-desktop")
        audio = AudioManager()
        audio_stop, audio_thread = _start_audio_listener(context, audio)
        hotkeys = HotkeyManager()
        _configure_hotkeys(context, hotkeys, window)
        hotkey_stop, hotkey_thread = _start_hotkey_listener(context, hotkeys, window)
        tray = TrayController()

        def tray_unavailable() -> None:
            logging.info("System tray unavailable; continuing without tray integration.")
            window.set_close_to_tray(False)
            if not window.visible:
                window.show()

        tray.setup(
            executor=services_executor,
            toggle_window=lambda: _toggle_window(window),
            open_settings=window.open_settings,
            toggle_presets_automation=lambda: _toggle_preset_automation(context),
            is_presets_automation_enabled=lambda: bool(context.get_params().get("presets_enabled", True)),
            quit_callback=window.destroy,
            on_failure=tray_unavailable,
        )
        window.set_close_to_tray(tray.available)
        window.start()
    finally:
        if tray is not None:
            tray.shutdown()
        if hotkey_stop is not None:
            hotkey_stop.set()
        if hotkey_thread is not None and hotkey_thread.is_alive():
            hotkey_thread.join(timeout=2)
        if hotkeys is not None:
            hotkeys.shutdown()
        if audio_stop is not None:
            audio_stop.set()
        if audio_thread is not None and audio_thread.is_alive():
            audio_thread.join(timeout=2)
        if audio is not None:
            audio.shutdown()
        if services_executor is not None:
            services_executor.shutdown(wait=False, cancel_futures=True)
        if context is not None and window is not None:
            geometry = window.geometry()
            if geometry:
                context.persist_parameters(geometry)
        if server is not None:
            server.stop()
        remove_lockfile()


def _toggle_window(window: WebViewWindow) -> None:
    """Toggle visibility using the native window state exposed by pywebview."""
    if not window.visible:
        window.show()
    else:
        window.hide()


def _toggle_preset_automation(context: ApplicationContext) -> None:
    params = context.get_params()
    enabled = not bool(params.get("presets_enabled", True))
    updated = context.persist_parameters(
        {"presets_enabled": enabled}
    )
    if updated is None:
        logging.error("Unable to persist tray preset automation setting")
        return
    context.broker.publish(
        "settings_updated",
        {"keys": ["presets_enabled"]},
    )
