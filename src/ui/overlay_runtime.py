"""Shared protocol helpers for the persistent Qt overlay."""

from __future__ import annotations

import json
import secrets
import socket
from typing import Any, Dict, Optional


OVERLAY_HOST = "127.0.0.1"
MODE_INTERACTIVE = "interactive"
MODE_PASSIVE = "passive"
VALID_MODES = {MODE_INTERACTIVE, MODE_PASSIVE}
CMD_SHOW = "show"
CMD_HIDE = "hide"
CMD_SET_MODE = "set_mode"
CMD_TOGGLE_MODE = "toggle_mode"
CMD_NAVIGATE = "navigate"
CMD_SHUTDOWN = "shutdown"


def normalize_overlay_mode(mode: Optional[str]) -> str:
    return mode if mode in VALID_MODES else MODE_INTERACTIVE


def reserve_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((OVERLAY_HOST, 0))
        return int(sock.getsockname()[1])


def generate_overlay_token() -> str:
    return secrets.token_hex(16)


def send_overlay_command(port: int, token: str, command: str, **payload: Any) -> bool:
    message = {"token": token, "command": command, **payload}
    raw = (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")
    with socket.create_connection((OVERLAY_HOST, port), timeout=0.75) as sock:
        sock.sendall(raw)
    return True


def read_overlay_command(connection: socket.socket) -> Dict[str, Any]:
    data = bytearray()
    while True:
        chunk = connection.recv(4096)
        if not chunk:
            break
        data.extend(chunk)
        if b"\n" in chunk:
            break
    if not data:
        return {}
    line = bytes(data).split(b"\n", 1)[0].decode("utf-8").strip()
    return json.loads(line) if line else {}
