"""Lifecycle manager for the two top-level provider WebView windows."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from threading import Event, RLock, Thread, Timer
from typing import Any

from ..services.urls import get_provider, is_allowed_provider_url

_WINDOW_KINDS = ("stats", "live")
LOGGER = logging.getLogger("otp_lol.provider")


class ProviderBrowserWindow:
    """One provider window with explicit lifecycle state."""

    def __init__(self, provider_id: str, url: str, on_closed: Callable[[], None], *, on_loaded: Callable[[], None] | None = None) -> None:
        self.provider_id = provider_id
        self.url = url
        self.on_closed = on_closed
        self.on_loaded = on_loaded
        self.window: Any = None
        self.state = "not_created"
        self.last_loaded_url: str | None = None
        self.last_error: str | None = None
        self.last_action = "not_created"
        self.last_transition_at: float | None = None
        self.load_started_at: float | None = None
        self.last_load_duration_ms: float | None = None
        self._preload = True

    def _transition(self, state: str, action: str, error: str | None = None) -> None:
        self.state = state
        self.last_action = action
        self.last_error = error
        self.last_transition_at = time.time()
        if state == "loading":
            self.load_started_at = self.last_transition_at
        LOGGER.debug(
            "provider_transition provider=%s state=%s action=%s error=%s",
            self.provider_id,
            state,
            action,
            error,
        )

    def open(self, *, preload: bool = True) -> bool:
        self._preload = preload
        provider = get_provider(self.provider_id)
        if provider is None or not is_allowed_provider_url(self.provider_id, self.url):
            self._transition("error", "create", "url_unavailable")
            return False
        try:
            import webview

            webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
            kwargs = {
                "url": self.url,
                "width": 1100,
                "height": 760,
                "min_size": (800, 540),
                "resizable": True,
                "js_api": None,
                "text_select": True,
                "focus": not preload,
            }
            # Preload windows are hidden after the native shown event. Creating
            # them at a normal position avoids a permanently off-screen window
            # when focus/show is requested later.
            try:
                self._transition("creating", "create")
                self.window = webview.create_window(f"{provider.label} | OTP LOL", **kwargs)
            except TypeError:
                # Older pywebview backends may not accept the focus option.
                kwargs.pop("focus", None)
                self.window = webview.create_window(f"{provider.label} | OTP LOL", **kwargs)
            events = getattr(self.window, "events", None)
            loaded = getattr(events, "loaded", None)
            closed = getattr(events, "closed", None)
            shown = getattr(events, "shown", None)
            if loaded is not None:
                loaded += self._on_loaded
            if closed is not None:
                closed += self._on_closed
            if shown is not None:
                shown += self._on_shown
            self._transition("loading", "create")
            return True
        except Exception as error:  # noqa: BLE001 - surface backend failures through state.
            LOGGER.warning("provider_create_failed provider=%s error=%s", self.provider_id, error)
            self._transition("error", "create", "create_failed")
            return False

    def _on_loaded(self, *_args: Any, **_kwargs: Any) -> None:
        self.last_loaded_url = self.url
        if self.load_started_at is not None:
            self.last_load_duration_ms = round((time.time() - self.load_started_at) * 1000, 1)
        self._transition("visible" if self.state == "visible" else "ready", "loaded")
        LOGGER.info(
            "provider_loaded provider=%s state=%s duration_ms=%s",
            self.provider_id,
            self.state,
            self.last_load_duration_ms,
        )
        if self.on_loaded is not None:
            self.on_loaded()

    def _on_closed(self, *_args: Any, **_kwargs: Any) -> None:
        self._transition("closed", "close")
        self.window = None
        self.on_closed()

    def _on_shown(self, *_args: Any, **_kwargs: Any) -> None:
        if self._preload:
            self.hide()
        elif self.last_loaded_url == self.url and self.state in {"ready", "hidden"}:
            self._transition("visible", "show")

    def navigate(self, provider_id: str, url: str) -> bool:
        provider = get_provider(provider_id)
        if provider is None or not is_allowed_provider_url(provider_id, url) or self.window is None:
            self._transition("error", "navigate", "url_unavailable")
            return False
        load_url = getattr(self.window, "load_url", None)
        if not callable(load_url):
            self._transition("error", "navigate", "bridge_not_ready")
            return False
        self.provider_id = provider_id
        self.url = url
        self.last_loaded_url = None
        self._transition("loading", "navigate")
        try:
            set_title = getattr(self.window, "set_title", None)
            if callable(set_title):
                set_title(f"{provider.label} | OTP LOL")
            else:
                self.window.title = f"{provider.label} | OTP LOL"
            load_url(url)
        except (AttributeError, OSError, RuntimeError, TypeError):
            self._transition("error", "navigate", "navigate_failed")
            return False
        if not self.focus():
            self._transition("error", "navigate", "show_failed")
            return False
        return True

    def reload(self) -> bool:
        if self.window is None or not self.url:
            self.last_error = "not_created"
            return False
        reload_view = getattr(self.window, "reload", None)
        load_url = getattr(self.window, "load_url", None)
        try:
            if callable(reload_view):
                reload_view()
            elif callable(load_url):
                load_url(self.url)
            else:
                self.last_error = "reload_failed"
                return False
        except (AttributeError, OSError, RuntimeError, TypeError):
            self._transition("error", "reload", "reload_failed")
            return False
        self._transition("loading", "reload")
        self.last_loaded_url = None
        return True

    def focus(self) -> bool:
        if self.window is None:
            self.last_error = "not_created"
            return False
        try:
            if getattr(self.window, "minimized", False):
                restore = getattr(self.window, "restore", None)
                if callable(restore):
                    restore()
            x = getattr(self.window, "x", None)
            y = getattr(self.window, "y", None)
            move = getattr(self.window, "move", None)
            if callable(move) and isinstance(x, (int, float)) and isinstance(y, (int, float)) and (x < -1000 or y < -1000):
                move(100, 100)
            show = getattr(self.window, "show", None)
            if callable(show):
                show()
            bring_to_front = getattr(self.window, "bring_to_front", None)
            if callable(bring_to_front):
                bring_to_front()
            if self.state in {"ready", "hidden"}:
                self._transition("visible", "show")
            return True
        except (AttributeError, OSError, RuntimeError, TypeError):
            self._transition("error", "show", "show_failed")
            return False

    def hide(self) -> bool:
        if self.window is None:
            self.last_error = "not_created"
            return False
        hide = getattr(self.window, "hide", None)
        if not callable(hide):
            self.last_error = "hide_failed"
            return False
        try:
            hide()
        except (AttributeError, OSError, RuntimeError, TypeError):
            self._transition("error", "hide", "hide_failed")
            return False
        self._transition("hidden", "hide")
        return True

    def close(self) -> None:
        window = self.window
        self.window = None
        self._transition("closed", "close")
        if window is None:
            return
        events = getattr(window, "events", None)
        for event_name, callback in (("loaded", self._on_loaded), ("shown", self._on_shown), ("closed", self._on_closed)):
            event = getattr(events, event_name, None)
            remove = getattr(event, "__isub__", None)
            if callable(remove):
                try:
                    remove(callback)
                except (AttributeError, TypeError, ValueError):
                    pass
        destroy = getattr(window, "destroy", None)
        if callable(destroy):
            try:
                destroy()
            except (AttributeError, OSError, RuntimeError, TypeError):
                LOGGER.debug("provider_close_failed provider=%s", self.provider_id, exc_info=True)


class ProviderWindowManager:
    """Own at most one reusable WebView per provider kind."""

    def __init__(self, context: Any = None) -> None:
        self._context = context
        self._lock = RLock()
        self._windows: dict[str, ProviderBrowserWindow | None] = {kind: None for kind in _WINDOW_KINDS}
        self._main_window_ready = False
        self._shutting_down = False
        self._preload_cancel = Event()
        self._preload_thread: Thread | None = None
        self._preload_timer: Timer | None = None
        self._pending_actions: set[str] = set()
        self._last_action: dict[str, str] = {kind: "not_created" for kind in _WINDOW_KINDS}
        self._last_error: dict[str, str | None] = {kind: None for kind in _WINDOW_KINDS}

    @property
    def shutting_down(self) -> bool:
        with self._lock:
            return self._shutting_down

    @property
    def stats_window(self) -> ProviderBrowserWindow | None:
        with self._lock:
            return self._windows["stats"]

    @property
    def live_window(self) -> ProviderBrowserWindow | None:
        with self._lock:
            return self._windows["live"]

    def _network_ready(self) -> bool:
        service = getattr(self._context, "network_status", None)
        checker = getattr(service, "is_online", None)
        return not callable(checker) or bool(checker())

    def mark_main_window_shown(self, *, preload: bool = True) -> None:
        with self._lock:
            if self._shutting_down:
                return
            self._main_window_ready = True
        if preload:
            self.schedule_preload(delay=0)

    def schedule_preload(self, *, delay: float = 0.35) -> None:
        """Run one preload pass after a small debounce window."""
        with self._lock:
            if self._shutting_down or not self._main_window_ready:
                return
            if self._preload_timer is not None:
                self._preload_timer.cancel()
            self._preload_cancel.clear()
            if delay <= 0:
                self._start_preload_locked()
                return
            self._preload_timer = Timer(delay, self._start_preload)
            self._preload_timer.daemon = True
            self._preload_timer.name = "otp-lol-provider-preload-debounce"
            self._preload_timer.start()

    def _start_preload_locked(self) -> None:
        thread = self._preload_thread
        if thread is None or not thread.is_alive():
            self._preload_thread = Thread(target=self.preload, name="otp-lol-provider-preload", daemon=True)
            self._preload_thread.start()

    def _start_preload(self) -> None:
        with self._lock:
            if self._shutting_down:
                return
            self._start_preload_locked()

    def notify_identity_updated(self) -> None:
        LOGGER.info("provider_preload_requested reason=account_identity_updated")
        self.schedule_preload()

    def _resolve_with_reason(self, kind: str, provider_id: str | None = None) -> tuple[tuple[str, str] | None, str | None]:
        if self._context is None:
            return None, "context_unavailable"
        if kind not in _WINDOW_KINDS:
            return None, "invalid_kind"
        from ..services.urls import build_provider_url, resolve_provider_account

        params = self._context.get_params()
        setting = "preferred_stats_site" if kind == "stats" else "preferred_hotkey_site"
        selected = str(provider_id or params.get(setting) or "").strip().lower()
        if selected != str(params.get(setting) or "").strip().lower():
            return None, "provider_mismatch"
        riot_id, region, _source = resolve_provider_account(params, self._context.runtime)
        if not riot_id or not region:
            return None, "account_unavailable"
        url = build_provider_url(selected, kind, region, riot_id)
        if not url or not is_allowed_provider_url(selected, url):
            return None, "url_unavailable"
        return (selected, url), None

    def _resolve(self, kind: str, provider_id: str | None = None) -> tuple[str, str] | None:
        resolved, _reason = self._resolve_with_reason(kind, provider_id)
        return resolved

    def _on_closed(self, kind: str) -> None:
        with self._lock:
            window = self._windows.get(kind)
            if window is not None:
                self._last_action[kind] = "close"
                self._last_error[kind] = None
                window.state = "closed"
        self._publish_provider_event(kind)

    def _public_status(self, kind: str) -> dict[str, Any]:
        status = self.status().get(kind, {})
        return {
            key: status.get(key)
            for key in (
                "state",
                "provider_id",
                "last_error",
                "last_action",
                "last_transition_at",
                "load_started_at",
                "last_load_duration_ms",
            )
        }

    def _publish_provider_event(self, kind: str) -> None:
        broker = getattr(self._context, "broker", None)
        publish = getattr(broker, "publish", None)
        if callable(publish):
            publish("provider_window", {"kind": kind, **self._public_status(kind)})

    def _record_result(self, kind: str, window: ProviderBrowserWindow | None, *, action: str, ok: bool, reason: str | None = None) -> dict[str, Any]:
        with self._lock:
            if kind in self._last_action:
                self._last_action[kind] = action
                self._last_error[kind] = reason
            result = {
                "ok": ok,
                "reason": reason,
                "state": window.state if window is not None else "not_created",
                "provider_id": window.provider_id if window is not None else None,
                "url": window.url if window is not None else None,
            }
        LOGGER.info(
            "provider_action kind=%s action=%s provider=%s ok=%s state=%s reason=%s",
            kind,
            action,
            result["provider_id"],
            ok,
            result["state"],
            reason,
        )
        return result

    def open_result(self, provider_id: str, kind: str) -> dict[str, Any]:
        if kind not in _WINDOW_KINDS:
            return {"ok": False, "reason": "invalid_kind", "state": "not_created", "provider_id": None, "url": None}
        with self._lock:
            if self._shutting_down:
                return self._record_result(kind, None, action="open", ok=False, reason="shutting_down")
            if not self._main_window_ready:
                return self._record_result(kind, None, action="open", ok=False, reason="main_not_ready")
        if not self._network_ready():
            return self._record_result(kind, self._windows.get(kind), action="open", ok=False, reason="network_unavailable")
        resolved, reason = self._resolve_with_reason(kind, provider_id)
        if resolved is None:
            return self._record_result(kind, None, action="open", ok=False, reason=reason)
        selected, url = resolved
        with self._lock:
            existing = self._windows.get(kind)
        if existing is not None and existing.window is not None and existing.state != "closed":
            if existing.provider_id != selected or existing.url != url:
                ok = existing.navigate(selected, url)
                return self._record_result(kind, existing, action="navigate", ok=ok, reason=None if ok else existing.last_error or "navigate_failed")
            if existing.state in {"creating", "loading"}:
                return self._record_result(kind, existing, action="open", ok=True, reason="already_loading")
            ok = existing.focus()
            return self._record_result(kind, existing, action="show", ok=ok, reason=None if ok else existing.last_error or "show_failed")
        return self.create_result(kind, selected, preload=False)

    def open(self, provider_id: str, kind: str) -> bool:
        return bool(self.open_result(provider_id, kind)["ok"])

    def create_result(self, kind: str, provider_id: str | None = None, *, preload: bool = False) -> dict[str, Any]:
        if kind not in _WINDOW_KINDS:
            return {"ok": False, "reason": "invalid_kind", "state": "not_created", "provider_id": None, "url": None}
        with self._lock:
            if self._shutting_down:
                return self._record_result(kind, None, action="create", ok=False, reason="shutting_down")
            if not self._main_window_ready:
                return self._record_result(kind, None, action="create", ok=False, reason="main_not_ready")
        if not self._network_ready():
            return self._record_result(kind, self._windows.get(kind), action="create", ok=False, reason="network_unavailable")
        resolved, reason = self._resolve_with_reason(kind, provider_id)
        if resolved is None:
            return self._record_result(kind, None, action="create", ok=False, reason=reason)
        selected, url = resolved
        with self._lock:
            existing = self._windows.get(kind)
            if existing is not None and existing.state in {"creating", "loading", "ready", "hidden", "visible"}:
                return self._record_result(kind, existing, action="create", ok=True)
            window = ProviderBrowserWindow(
                selected,
                url,
                lambda: self._on_closed(kind),
                on_loaded=lambda: self._publish_provider_event(kind),
            )
            self._windows[kind] = window
        ok = window.open(preload=preload)
        if not ok:
            return self._record_result(kind, window, action="create", ok=False, reason=window.last_error or "create_failed")
        return self._record_result(kind, window, action="create", ok=True)

    def request_open(self, kind: str) -> dict[str, Any]:
        """Schedule an open/show action without waiting on native WebView callbacks."""
        if kind not in _WINDOW_KINDS:
            return self.open_result("", kind)
        with self._lock:
            if self._shutting_down:
                return self._record_result(kind, None, action="open", ok=False, reason="shutting_down")
            if not self._main_window_ready:
                return self._record_result(kind, None, action="open", ok=False, reason="main_not_ready")
        if not self._network_ready():
            return self._record_result(kind, self._windows.get(kind), action="open", ok=False, reason="network_unavailable")
        resolved, reason = self._resolve_with_reason(kind)
        if resolved is None:
            return self._record_result(kind, None, action="open", ok=False, reason=reason)
        selected, url = resolved
        old_window: ProviderBrowserWindow | None = None
        with self._lock:
            existing = self._windows.get(kind)
            if kind in self._pending_actions:
                return self._record_result(kind, existing, action="open", ok=True, reason="already_loading")
            if existing is not None and existing.provider_id == selected and existing.url == url and existing.state in {"creating", "loading"}:
                return self._record_result(kind, existing, action="open", ok=True, reason="already_loading")
            if existing is not None and existing.provider_id == selected and existing.url == url:
                window = existing
            else:
                old_window = existing
                window = ProviderBrowserWindow(
                    selected,
                    url,
                    lambda: self._on_closed(kind),
                    on_loaded=lambda: self._publish_provider_event(kind),
                )
                window._transition("creating", "open")
                self._windows[kind] = window
            self._pending_actions.add(kind)
        if old_window is not None:
            old_window.close()
        Thread(
            target=self._run_open_request,
            args=(kind, window, selected, url),
            name=f"otp-lol-provider-{kind}-open",
            daemon=True,
        ).start()
        return self._record_result(kind, window, action="open", ok=True, reason="scheduled")

    def _run_open_request(self, kind: str, window: ProviderBrowserWindow, provider_id: str, url: str) -> None:
        try:
            if window.window is None:
                window.open(preload=False)
            elif window.provider_id != provider_id or window.url != url:
                window.navigate(provider_id, url)
            elif window.state in {"loading", "creating"}:
                pass
            else:
                window.focus()
            self._publish_provider_event(kind)
        except Exception:
            LOGGER.exception("provider_async_open_failed kind=%s provider=%s", kind, provider_id)
            window._transition("error", "open", "create_failed")
        finally:
            with self._lock:
                self._pending_actions.discard(kind)

    def request_reload(self, kind: str) -> dict[str, Any]:
        if not self._network_ready():
            return self._record_result(kind, self._windows.get(kind), action="reload", ok=False, reason="network_unavailable")
        with self._lock:
            window = self._windows.get(kind)
            if self._shutting_down:
                return self._record_result(kind, window, action="reload", ok=False, reason="shutting_down")
            if window is None:
                return self._record_result(kind, None, action="reload", ok=False, reason="not_created")
            if kind in self._pending_actions or window.state in {"creating", "loading"}:
                return self._record_result(kind, window, action="reload", ok=True, reason="already_loading")
            self._pending_actions.add(kind)
        Thread(target=self._run_reload_request, args=(kind, window), name=f"otp-lol-provider-{kind}-reload", daemon=True).start()
        return self._record_result(kind, window, action="reload", ok=True, reason="scheduled")

    def _run_reload_request(self, kind: str, window: ProviderBrowserWindow) -> None:
        try:
            window.reload()
            self._publish_provider_event(kind)
        finally:
            with self._lock:
                self._pending_actions.discard(kind)

    def request_show(self, kind: str) -> dict[str, Any]:
        if not self._network_ready():
            return self._record_result(kind, self._windows.get(kind), action="show", ok=False, reason="network_unavailable")
        with self._lock:
            window = self._windows.get(kind)
            if self._shutting_down:
                return self._record_result(kind, window, action="show", ok=False, reason="shutting_down")
            if window is None:
                return self._record_result(kind, None, action="show", ok=False, reason="not_created")
            if window.state in {"creating", "loading"}:
                return self._record_result(kind, window, action="show", ok=True, reason="already_loading")
            if kind in self._pending_actions:
                return self._record_result(kind, window, action="show", ok=True, reason="already_loading")
            self._pending_actions.add(kind)
        Thread(target=self._run_show_request, args=(kind, window), name=f"otp-lol-provider-{kind}-show", daemon=True).start()
        return self._record_result(kind, window, action="show", ok=True, reason="scheduled")

    def _run_show_request(self, kind: str, window: ProviderBrowserWindow) -> None:
        try:
            window.focus()
            self._publish_provider_event(kind)
        finally:
            with self._lock:
                self._pending_actions.discard(kind)

    def request_hide(self, kind: str) -> dict[str, Any]:
        with self._lock:
            window = self._windows.get(kind)
            if self._shutting_down:
                return self._record_result(kind, window, action="hide", ok=False, reason="shutting_down")
            if window is None:
                return self._record_result(kind, None, action="hide", ok=False, reason="not_created")
            if kind in self._pending_actions:
                return self._record_result(kind, window, action="hide", ok=True, reason="already_loading")
            self._pending_actions.add(kind)
        Thread(target=self._run_hide_request, args=(kind, window), name=f"otp-lol-provider-{kind}-hide", daemon=True).start()
        return self._record_result(kind, window, action="hide", ok=True, reason="scheduled")

    def _run_hide_request(self, kind: str, window: ProviderBrowserWindow) -> None:
        try:
            window.hide()
            self._publish_provider_event(kind)
        finally:
            with self._lock:
                self._pending_actions.discard(kind)

    def create(self, kind: str, provider_id: str | None = None, *, preload: bool = False) -> bool:
        """Create one provider window when the main window is ready."""
        if kind not in _WINDOW_KINDS:
            return False
        return bool(self.create_result(kind, provider_id, preload=preload)["ok"])

    def navigate(self, kind: str, provider_id: str) -> bool:
        return self.open(provider_id, kind)

    def preload(self) -> None:
        with self._lock:
            if self._shutting_down or not self._main_window_ready:
                return
        if not self._network_ready():
            for kind in _WINDOW_KINDS:
                self._record_result(kind, self._windows.get(kind), action="preload", ok=False, reason="network_unavailable")
            return
        for kind in _WINDOW_KINDS:
            if self._preload_cancel.is_set():
                return
            resolved = self._resolve(kind)
            if resolved is None:
                self._record_result(kind, self._windows.get(kind), action="preload", ok=False, reason="account_unavailable")
                continue
            selected, url = resolved
            with self._lock:
                existing = self._windows.get(kind)
            if existing is not None and existing.window is not None and existing.state != "closed":
                if existing.provider_id != selected or existing.url != url:
                    existing.navigate(selected, url)
                continue
            self.create_result(kind, selected, preload=True)

    def reload(self, kind: str) -> bool:
        if not self._network_ready():
            return False
        with self._lock:
            if self._shutting_down:
                return False
            window = self._windows.get(kind)
        return window.reload() if window is not None else False

    def show(self, kind: str) -> bool:
        if not self._network_ready():
            return False
        with self._lock:
            if self._shutting_down:
                return False
            window = self._windows.get(kind)
        return window.focus() if window is not None else False

    def hide(self, kind: str) -> bool:
        with self._lock:
            window = self._windows.get(kind)
        return window.hide() if window is not None else False

    def close(self, kind: str) -> None:
        with self._lock:
            window = self._windows.get(kind)
        if window is not None:
            window.close()

    def status(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {
                kind: {
                    "state": window.state if window is not None else "not_created",
                    "provider_id": window.provider_id if window is not None else None,
                    "url": window.url if window is not None else None,
                    "last_loaded_url": window.last_loaded_url if window is not None else None,
                    "last_error": window.last_error if window is not None else self._last_error[kind],
                    "last_action": window.last_action if window is not None else self._last_action[kind],
                    "last_transition_at": window.last_transition_at if window is not None else None,
                    "load_started_at": window.load_started_at if window is not None else None,
                    "last_load_duration_ms": window.last_load_duration_ms if window is not None else None,
                }
                for kind, window in self._windows.items()
            }

    def shutdown(self) -> None:
        with self._lock:
            if self._shutting_down:
                return
            self._shutting_down = True
            self._preload_cancel.set()
            if self._preload_timer is not None:
                self._preload_timer.cancel()
            windows = [window for window in self._windows.values() if window is not None]
            preload_thread = self._preload_thread
        if preload_thread is not None and preload_thread.is_alive():
            preload_thread.join(timeout=1)
        for window in windows:
            window.close()


__all__ = ["ProviderBrowserWindow", "ProviderWindowManager"]
