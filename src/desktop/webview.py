"""Run the FastAPI runtime inside a local pywebview window."""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Thread, current_thread
from urllib.error import URLError
from urllib.request import urlopen

from ..api.app import create_app
from ..api.context import ApplicationContext
from ..config import APP_IMAGE_FILES, APP_NAME, resource_path
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
_PROVIDER_SETTING_KEYS = frozenset({"preferred_stats_site", "preferred_hotkey_site"})
LOGGER = logging.getLogger("otp_lol.webview")


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
    available = hotkeys.setup(
        toggle_window=lambda: _toggle_window(window),
        open_hotkey_site=lambda: window.open_route("live"),
        toggle_hotkey=str(params.get("hotkey_toggle_window") or "alt+c"),
        stats_hotkey=str(params.get("hotkey_open_site") or "alt+p"),
    )
    set_status = getattr(context, "set_hotkey_status", None)
    status_getter = getattr(hotkeys, "status", None)
    if callable(set_status) and callable(status_getter):
        set_status(
            status_getter(
                str(params.get("hotkey_toggle_window") or "alt+c"),
                str(params.get("hotkey_open_site") or "alt+p"),
            )
        )
    return available


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


def _start_provider_event_listener(
    context: ApplicationContext,
    bridge: DesktopBridge,
) -> tuple[Event, Thread]:
    """Retry provider preloading when identity or provider settings change."""
    stop_event = Event()

    async def consume() -> None:
        subscription = context.broker.subscribe()
        try:
            while not stop_event.is_set():
                try:
                    event = await asyncio.wait_for(subscription.next_event(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                if event.type == "account_identity_updated" or (
                    event.type == "network_status"
                    and isinstance(event.data, dict)
                    and event.data.get("online")
                ):
                    bridge.notify_provider_identity_updated()
                elif event.type == "settings_updated" and isinstance(event.data, dict):
                    keys = event.data.get("keys")
                    if isinstance(keys, (list, tuple, set, frozenset)) and _PROVIDER_SETTING_KEYS.intersection(keys):
                        bridge.notify_provider_identity_updated()
        finally:
            subscription.close()

    def run() -> None:
        asyncio.run(consume())

    thread = Thread(target=run, daemon=True, name="otp-lol-provider-events")
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


def _configure_logging() -> None:
    """Enable detailed native lifecycle logs only when explicitly requested."""
    debug = "--debug-webview" in sys.argv or os.environ.get("OTP_LOL_LOG_LEVEL", "").upper() == "DEBUG"
    if debug:
        os.environ.setdefault("PYWEBVIEW_LOG", "debug")
        logging.getLogger().setLevel(logging.DEBUG)
        LOGGER.info("webview_debug enabled thread=%s", current_thread().name)


def run_webview() -> None:
    """Start the local API, open the web UI, and shut both down together."""
    _configure_logging()
    startup_started = time.perf_counter()
    LOGGER.info("[STARTUP] T0 launcher=%.0fms", 0.0)
    if not check_single_instance():
        LOGGER.info("Another instance is already running. Closing.")
        return

    server: EmbeddedApiServer | None = None
    services_executor: ThreadPoolExecutor | None = None
    audio: AudioManager | None = None
    audio_stop: Event | None = None
    audio_thread: Thread | None = None
    hotkey_stop: Event | None = None
    hotkey_thread: Thread | None = None
    provider_stop: Event | None = None
    provider_thread: Thread | None = None
    hotkeys: HotkeyManager | None = None
    tray: TrayController | None = None
    context: ApplicationContext | None = None
    window: WebViewWindow | None = None
    bridge: DesktopBridge | None = None
    try:
        frontend_dir = _frontend_dist_dir()
        if not has_webview2_runtime():
            raise RuntimeError("Microsoft Edge WebView2 Runtime is required to open OTP LOL.")
        context = ApplicationContext.from_system()
        LOGGER.info("[STARTUP] T1 settings loaded=%.0fms", (time.perf_counter() - startup_started) * 1000)
        api = create_app(context, frontend_dir=frontend_dir)
        port = _find_free_port()
        server = EmbeddedApiServer(api, host=_HOST, port=port)
        server.start()
        _wait_for_server(port)
        LOGGER.info("[STARTUP] T2 FastAPI ready=%.0fms", (time.perf_counter() - startup_started) * 1000)

        bridge = DesktopBridge(context)
        params = context.get_params()
        window = WebViewWindow(
            WebViewWindowConfig(
                title=APP_NAME,
                url=f"http://{_HOST}:{port}/?desktop=1",
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
        window.set_shown_callback(bridge.mark_main_window_shown)
        window.create()
        provider_stop, provider_thread = _start_provider_event_listener(context, bridge)
        context.diagnostics.record_event("otp-lol/webview", "created", {})

        def shutdown_window() -> None:
            bridge.shutdown()
            window.destroy()

        context.bind_window(window, shutdown_callback=shutdown_window)
        LOGGER.info("[STARTUP] T3 WebView created=%.0fms", (time.perf_counter() - startup_started) * 1000)

        services_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="otp-lol-desktop")
        audio = AudioManager()
        audio_stop, audio_thread = _start_audio_listener(context, audio)
        hotkeys = HotkeyManager()
        _configure_hotkeys(context, hotkeys, window)
        hotkey_stop, hotkey_thread = _start_hotkey_listener(context, hotkeys, window)
        tray = TrayController()

        def tray_unavailable() -> None:
            LOGGER.info("System tray unavailable; continuing without tray integration.")
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
        if provider_stop is not None:
            provider_stop.set()
        if provider_thread is not None and provider_thread.is_alive():
            provider_thread.join(timeout=2)
        if bridge is not None:
            bridge.shutdown()
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
        LOGGER.error("Unable to persist tray preset automation setting")
        return
    context.broker.publish(
        "settings_updated",
        {"keys": ["presets_enabled"]},
    )
