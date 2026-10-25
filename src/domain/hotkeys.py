"""Shared validation for user-configured global hotkeys."""

from __future__ import annotations


_MODIFIER_ALIASES = {
    "alt": "alt",
    "ctrl": "ctrl",
    "control": "ctrl",
    "shift": "shift",
    "win": "win",
    "windows": "win",
    "meta": "win",
}

_KEY_ALIASES = {
    "return": "enter",
    "esc": "escape",
}

_SPECIAL_KEYS = {
    "backspace",
    "tab",
    "enter",
    "escape",
    "space",
    "pageup",
    "pagedown",
    "end",
    "home",
    "left",
    "up",
    "right",
    "down",
    "insert",
    "delete",
}


def normalize_hotkey(hotkey: str) -> str:
    """Return canonical ``modifier+key`` syntax or reject an invalid shortcut."""
    parts = [part.strip().lower() for part in str(hotkey or "").replace("-", "+").split("+") if part.strip()]
    if len(parts) < 2:
        raise ValueError("A global hotkey needs a modifier and a key")

    modifiers: list[str] = []
    for part in parts[:-1]:
        modifier = _MODIFIER_ALIASES.get(part)
        if modifier is None:
            raise ValueError(f"Unsupported hotkey modifier: {part}")
        if modifier in modifiers:
            raise ValueError(f"Duplicate hotkey modifier: {part}")
        modifiers.append(modifier)

    key = _KEY_ALIASES.get(parts[-1], parts[-1])
    is_simple_key = len(key) == 1 and key.isascii() and key.isalnum()
    is_function_key = key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24
    if not (is_simple_key or is_function_key or key in _SPECIAL_KEYS):
        raise ValueError(f"Unsupported hotkey key: {parts[-1]}")

    return "+".join([*modifiers, key])


def validate_hotkey_pair(toggle_window: str, open_site: str) -> tuple[str, str]:
    """Normalize two shortcuts and reject collisions between their actions."""
    normalized_toggle = normalize_hotkey(toggle_window)
    normalized_open_site = normalize_hotkey(open_site)
    if normalized_toggle == normalized_open_site:
        raise ValueError("Global hotkeys must be different")
    return normalized_toggle, normalized_open_site


__all__ = ["normalize_hotkey", "validate_hotkey_pair"]
