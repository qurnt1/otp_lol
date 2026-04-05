"""Persistent action history helpers."""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..config import HISTORY_PATH

MAX_HISTORY_ENTRIES = 250


def _read_history() -> List[Dict[str, Any]]:
    if not os.path.exists(HISTORY_PATH):
        return []
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, list):
            return [entry for entry in payload if isinstance(entry, dict)]
    except (OSError, json.JSONDecodeError) as e:
        logging.debug(f"Historique illisible: {e}")
    return []


def _write_history(entries: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(entries[-MAX_HISTORY_ENTRIES:], f, indent=2, ensure_ascii=False)


def log_history_event(event_type: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "type": event_type,
        "message": message,
        "details": details or {},
    }
    entries = _read_history()
    entries.append(entry)
    try:
        _write_history(entries)
    except OSError as e:
        logging.debug(f"Impossible d'ecrire l'historique: {e}")


def get_history_entries(limit: int = 100) -> List[Dict[str, Any]]:
    entries = _read_history()
    return list(reversed(entries[-limit:]))


def clear_history_entries() -> None:
    try:
        _write_history([])
    except OSError as e:
        logging.debug(f"Impossible de vider l'historique: {e}")
