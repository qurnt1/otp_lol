"""Persistent action history helpers."""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..config import HISTORY_PATH

MAX_HISTORY_ENTRIES = 250

EVENT_DEFAULTS: Dict[str, Dict[str, str]] = {
    "connection": {"level": "info", "category": "Connection", "action": "client"},
    "ready_check": {"level": "success", "category": "Match found", "action": "accept"},
    "hover": {"level": "info", "category": "Champion Select", "action": "hover"},
    "ban": {"level": "success", "category": "Champion Select", "action": "ban"},
    "pick": {"level": "success", "category": "Champion Select", "action": "pick"},
    "spells": {"level": "success", "category": "Spells", "action": "set"},
    "play_again": {"level": "success", "category": "End game", "action": "play_again"},
    "error": {"level": "error", "category": "Error", "action": "error"},
}

LEVEL_LABELS = {
    "info": "Info",
    "success": "Success",
    "warning": "Warning",
    "error": "Error",
}

CATEGORY_LABELS = {
    "Connexion": "Connection",
    "Partie trouvee": "Match found",
    "Champ Select": "Champion Select",
    "Sorts": "Spells",
    "Fin de partie": "End game",
    "Erreur": "Error",
}


def _read_history() -> List[Dict[str, Any]]:
    if not os.path.exists(HISTORY_PATH):
        return []
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, list):
            return [entry for entry in payload if isinstance(entry, dict)]
    except (OSError, json.JSONDecodeError) as e:
        logging.debug(f"Unreadable history: {e}")
    return []


def _write_history(entries: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(entries[-MAX_HISTORY_ENTRIES:], f, indent=2, ensure_ascii=False)


def log_history_event(
    event_type: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    *,
    level: Optional[str] = None,
    category: Optional[str] = None,
    action: Optional[str] = None,
) -> None:
    defaults = EVENT_DEFAULTS.get(event_type, {})
    entry = {
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "type": event_type,
        "level": level or defaults.get("level", "info"),
        "category": category or defaults.get("category", "General"),
        "action": action or defaults.get("action", event_type),
        "message": message,
        "details": details or {},
    }
    entries = _read_history()
    entries.append(entry)
    try:
        _write_history(entries)
    except OSError as e:
        logging.debug(f"Unable to write history: {e}")


def get_history_entries(limit: int = 100) -> List[Dict[str, Any]]:
    entries = _read_history()
    return list(reversed(entries[-limit:]))


def clear_history_entries() -> None:
    try:
        _write_history([])
    except OSError as e:
        logging.debug(f"Unable to clear history: {e}")


def _format_timestamp(timestamp: str) -> str:
    if not timestamp:
        return "--:--:--"
    try:
        return datetime.fromisoformat(timestamp).strftime("%H:%M:%S")
    except ValueError:
        return timestamp[-8:] if len(timestamp) >= 8 else timestamp


def _build_detail_lines(details: Dict[str, Any]) -> List[str]:
    if not isinstance(details, dict):
        return []

    lines: List[str] = []
    champion = details.get("champion") or details.get("champion_name")
    if champion:
        lines.append(f"Champion: {champion}")

    spell_1 = details.get("spell_1")
    spell_2 = details.get("spell_2")
    if spell_1 or spell_2:
        lines.append(f"Spells: {spell_1 or '?'} + {spell_2 or '?'}")

    role = details.get("role") or details.get("resolved_role")
    if role:
        lines.append(f"Profile: {role}")

    region = details.get("region")
    if region:
        lines.append(f"Region: {region}")

    reason = details.get("reason")
    if reason:
        lines.append(f"Reason: {reason}")

    for key, value in details.items():
        if key in {"champion", "champion_name", "spell_1", "spell_2", "role", "resolved_role", "region", "reason"}:
            continue
        if key.endswith("_id") or key == "action_id":
            continue
        if value in ("", None, {}, []):
            continue
        lines.append(f"{str(key).replace('_', ' ').capitalize()}: {value}")

    return lines


def format_history_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    event_type = entry.get("type", "info")
    defaults = EVENT_DEFAULTS.get(event_type, {})
    level = entry.get("level") or defaults.get("level", "info")
    category = entry.get("category") or defaults.get("category", "General")
    category = CATEGORY_LABELS.get(category, category)
    return {
        "time": _format_timestamp(entry.get("timestamp", "")),
        "level": level,
        "level_label": LEVEL_LABELS.get(level, LEVEL_LABELS["info"]),
        "category": category,
        "message": entry.get("message", "Event"),
        "detail_lines": _build_detail_lines(entry.get("details", {})),
    }
