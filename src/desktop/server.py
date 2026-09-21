"""Supervise the local FastAPI server used by the WebView shell."""

from __future__ import annotations

import logging
import socket
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
        port: int = 0,
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
        self._socket: socket.socket | None = None

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
        bound_socket = self._bind_socket()
        self._stop_event.clear()
        self._thread = Thread(target=self._run, daemon=True, name="otp-lol-api")
        try:
            self._thread.start()
        except Exception:
            self._close_socket(bound_socket)
            self._thread = None
            raise

    def _bind_socket(self) -> socket.socket:
        self._close_socket()
        bound_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            bound_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            bound_socket.bind((self.host, int(self.port)))
            bound_socket.listen(socket.SOMAXCONN)
            bound_socket.setblocking(False)
            self.port = int(bound_socket.getsockname()[1])
            self._socket = bound_socket
            return bound_socket
        except Exception:
            bound_socket.close()
            raise

    def _close_socket(self, candidate: socket.socket | None = None) -> None:
        bound_socket = candidate or self._socket
        if bound_socket is None:
            return
        if self._socket is bound_socket:
            self._socket = None
        try:
            bound_socket.close()
        except OSError:
            pass

    def _run(self) -> None:
        while not self._stop_event.is_set():
            server = self._server_factory()
            bound_socket = self._socket
            with self._server_lock:
                self._server = server
                if self._stop_event.is_set():
                    server.should_exit = True
            try:
                server.run(sockets=[bound_socket] if bound_socket is not None else None)
            except Exception:
                logging.exception("Embedded API server stopped unexpectedly.")
            finally:
                with self._server_lock:
                    if self._server is server:
                        self._server = None
                self._close_socket(bound_socket)

            if not self._stop_event.wait(1.0):
                logging.warning("Embedded API server exited; restarting it.")
                try:
                    self._bind_socket()
                except OSError:
                    logging.exception("Embedded API server could not reserve a restart port.")
                    if not self._stop_event.wait(1.0):
                        continue

    def stop(self) -> None:
        self._stop_event.set()
        with self._server_lock:
            server = self._server
        if server is not None:
            server.should_exit = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._close_socket()
        self._thread = None


__all__ = ["EmbeddedApiServer"]
