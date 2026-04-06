"""Persistent Qt overlay host process."""

from __future__ import annotations

import argparse
import logging
import os
import socket
import threading
from typing import Any, Dict, Sequence

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QApplication

from .overlay_runtime import (
    CMD_HIDE,
    CMD_NAVIGATE,
    CMD_SET_MODE,
    CMD_SHOW,
    CMD_SHUTDOWN,
    CMD_TOGGLE_MODE,
    MODE_INTERACTIVE,
    OVERLAY_HOST,
    normalize_overlay_mode,
    read_overlay_command,
)
from .overlay_window import OverlayWindow, compute_overlay_geometry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MAIN LOL persistent overlay host")
    parser.add_argument("--overlay-host", action="store_true", help="Internal flag used by MAIN LOL.")
    parser.add_argument("--port", type=int, help="Local TCP port used to control the overlay.")
    parser.add_argument("--token", help="Shared secret for overlay commands.")
    parser.add_argument("--url", help="Initial stats page to display.")
    parser.add_argument("--title", default="MAIN LOL - Overlay stats", help="Overlay window title.")
    parser.add_argument("--mode", default=MODE_INTERACTIVE, help="Initial overlay mode.")
    parser.add_argument("--width-ratio", type=float, default=0.92, help="Overlay width as a fraction of the desktop.")
    parser.add_argument("--height-ratio", type=float, default=0.88, help="Overlay height as a fraction of the desktop.")
    return parser


def _load_bootstrap_config(args) -> Dict[str, Any]:
    env = os.environ
    port = args.port if args.port is not None else int(env.get("MAIN_LOL_OVERLAY_PORT", "0") or 0)
    token = args.token or env.get("MAIN_LOL_OVERLAY_TOKEN", "")
    url = args.url or env.get("MAIN_LOL_OVERLAY_URL", "")
    title = args.title if args.title != "MAIN LOL - Overlay stats" else env.get("MAIN_LOL_OVERLAY_TITLE", args.title)
    mode = normalize_overlay_mode(args.mode if args.mode != MODE_INTERACTIVE else env.get("MAIN_LOL_OVERLAY_MODE", args.mode))
    width_ratio = (
        args.width_ratio
        if args.width_ratio != 0.92
        else float(env.get("MAIN_LOL_OVERLAY_WIDTH_RATIO", str(args.width_ratio)))
    )
    height_ratio = (
        args.height_ratio
        if args.height_ratio != 0.88
        else float(env.get("MAIN_LOL_OVERLAY_HEIGHT_RATIO", str(args.height_ratio)))
    )
    if not (port and token and url):
        raise ValueError("Configuration overlay incomplete.")
    return {
        "port": port,
        "token": token,
        "url": url,
        "title": title,
        "mode": mode,
        "width_ratio": width_ratio,
        "height_ratio": height_ratio,
    }


class OverlayCommandServer(threading.Thread):
    """Tiny TCP server that forwards overlay commands to the Qt thread."""

    def __init__(self, port: int, token: str, dispatcher) -> None:
        super().__init__(daemon=True)
        self.port = port
        self.token = token
        self.dispatcher = dispatcher
        self._stop_event = threading.Event()
        self._server_socket: socket.socket | None = None

    def run(self) -> None:  # pragma: no cover - requires live socket loop
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            self._server_socket = server
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((OVERLAY_HOST, self.port))
            server.listen(5)
            server.settimeout(0.3)

            while not self._stop_event.is_set():
                try:
                    connection, _ = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break

                with connection:
                    try:
                        payload = read_overlay_command(connection)
                    except Exception as exc:
                        logging.debug("Commande overlay invalide: %s", exc)
                        continue
                if payload.get("token") != self.token:
                    continue
                self.dispatcher(payload)

    def stop(self) -> None:
        self._stop_event.set()
        if self._server_socket:
            try:
                self._server_socket.close()
            except OSError:
                pass


class OverlayDispatcher(QObject):
    command_received = Signal(dict)

    def __init__(self, window: OverlayWindow, app: QApplication) -> None:
        super().__init__()
        self.window = window
        self.app = app
        self.command_received.connect(self._dispatch_overlay_command)

    @Slot(dict)
    def _dispatch_overlay_command(self, payload: Dict[str, Any]) -> None:
        command = payload.get("command")
        url = str(payload.get("url", "")).strip()
        mode = normalize_overlay_mode(payload.get("mode"))

        if command == CMD_SHOW:
            if url:
                self.window.navigate(url)
            self.window.set_mode(mode, activate=(mode == MODE_INTERACTIVE))
            self.window.show_overlay(activate=(mode == MODE_INTERACTIVE))
            return
        if command == CMD_HIDE:
            self.window.hide_overlay()
            return
        if command == CMD_SET_MODE:
            self.window.set_mode(mode, activate=(mode == MODE_INTERACTIVE))
            return
        if command == CMD_TOGGLE_MODE:
            self.window.toggle_mode()
            return
        if command == CMD_NAVIGATE:
            if url:
                self.window.navigate(url)
            return
        if command == CMD_SHUTDOWN:
            self.window.hide_overlay()
            self.app.quit()


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = _load_bootstrap_config(args)
    except Exception as exc:
        logging.error("Impossible de lire la configuration de l'overlay: %s", exc)
        return 1
    app = QApplication.instance() or QApplication([__name__])
    app.setQuitOnLastWindowClosed(False)
    width, height, x, y = compute_overlay_geometry(app, config["width_ratio"], config["height_ratio"])
    window = OverlayWindow(config["title"], width, height, x, y, config["mode"])
    window.navigate(config["url"])
    window.show_overlay(activate=(window.mode == MODE_INTERACTIVE))
    dispatcher = OverlayDispatcher(window, app)

    server = OverlayCommandServer(
        config["port"],
        config["token"],
        dispatcher=dispatcher.command_received.emit,
    )
    app.aboutToQuit.connect(server.stop)
    server.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
