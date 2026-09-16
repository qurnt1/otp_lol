"""Supervise the local FastAPI server used by the WebView shell."""

from __future__ import annotations

import logging
from threading import Event, Lock, Thread
from typing import Any, Callable

import uvicorn


class EmbeddedApiServer:
    """Run Uvicorn in a restartable daemon thread for the native desktop shell."""

    def __init__(
        self,
        application: Any,
        *,
        host: str,
        port: int,
        server_factory: Callable[[], uvicorn.Server] | None = None,
    ) -> None:
        self.application = application
        self.host = host
        self.port = port
        self._server_factory = server_factory or self._build_server
        self._stop_event = Event()
        self._server_lock = Lock()
        self._server: uvicorn.Server | None = None
        self._thread: Thread | None = None

    def _build_server(self) -> uvicorn.Server:
        return uvicorn.Server(
            uvicorn.Config(
                self.application,
                host=self.host,
                port=self.port,
                log_level="warning",
                access_log=False,
            )
        )

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._run, daemon=True, name="otp-lol-api")
        self._thread.start()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            server = self._server_factory()
            with self._server_lock:
                self._server = server
            try:
                server.run()
            except Exception:
                logging.exception("Embedded API server stopped unexpectedly.")
            finally:
                with self._server_lock:
                    if self._server is server:
                        self._server = None

            if not self._stop_event.wait(1.0):
                logging.warning("Embedded API server exited; restarting it.")

    def stop(self) -> None:
        self._stop_event.set()
        with self._server_lock:
            server = self._server
        if server is not None:
            server.should_exit = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None


__all__ = ["EmbeddedApiServer"]
