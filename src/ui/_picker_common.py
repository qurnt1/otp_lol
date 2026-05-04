"""
Shared colors, messages, and helpers for the rune and skin picker popups.

Both pickers are opened from SettingsWindow and should share the same visual
language, status wording, and LCU-availability awareness.
"""

from typing import Any, Dict

from ..config import THEME_PALETTE

# ---------------------------------------------------------------------------
# Standardised status messages
# ---------------------------------------------------------------------------

LCU_NOT_DETECTED = "LoL client is not detected. Launch League of Legends to refresh."


def picker_lcu_status_message(kind: str) -> str:
    """Return the standardised status message shown when the LCU is absent."""
    return f"Unable to fetch {kind}: {LCU_NOT_DETECTED}"


def picker_empty_message(kind: str) -> str:
    """Return the message shown when the account has no entries of *kind*."""
    templates: Dict[str, str] = {
        "runes": "No valid rune pages found on your account.",
        "skins": "No skins detected for this champion.",
    }
    return templates.get(kind, f"No {kind} found on your account.")


# ---------------------------------------------------------------------------
# Unified color scheme – based on the former _get_skin_picker_colors,
# extended with the card-level keys the rune picker needs.
# ---------------------------------------------------------------------------


def get_picker_colors(theme_name: str) -> Dict[str, str]:
    """Return the shared color palette for the rune and skin picker popups."""
    palette = THEME_PALETTE.get(theme_name, THEME_PALETTE["darkly"])
    if theme_name == "flatly":
        return {
            "window_bg": palette["window_bg"],
            "surface_bg": "#ffffff",
            "surface_hover": "#f1f5f9",
            "selected_bg": "#3f4a3d",
            "selected_hover": "#4a5747",
            "selected_text": "#ffffff",
            "text": palette["text"],
            "muted": "#4b5563",
            "border": "#cbd5e1",
            "active_border": "#7f9a7a",
            "warning": palette.get("history_warning", "#c9973a"),
            "button_bg": "#f8fafc",
            "button_text": "#ffffff",
            "inactive_button_text": "#1f2937",
        }
    return {
        "window_bg": palette["window_bg"],
        "surface_bg": "#242424",
        "surface_hover": "#303030",
        "selected_bg": "#3f4a3d",
        "selected_hover": "#4a5747",
        "selected_text": "#ffffff",
        "text": palette["text"],
        "muted": "#c3c3c3",
        "border": "#4a4a4a",
        "active_border": "#7f9a7a",
        "warning": palette.get("history_warning", "#d6a84f"),
        "button_bg": "#242424",
        "button_text": palette["text"],
        "inactive_button_text": palette["text"],
    }
