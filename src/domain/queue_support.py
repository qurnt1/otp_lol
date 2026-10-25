"""Queue labels and preset-automation eligibility for the live League session."""

from __future__ import annotations

from ..config.constants import (
    PRACTICE_TOOL_GAME_MODE,
    PRESET_ENABLED_QUEUE_IDS,
    QUEUE_ID_LABELS,
)


def presets_supported_for_queue(queue_id: int, game_mode: str = "") -> bool | None:
    """Return whether presets are supported, or None while the queue is unknown."""
    if game_mode.strip().upper() == PRACTICE_TOOL_GAME_MODE:
        return True
    if queue_id <= 0:
        return None
    return queue_id in PRESET_ENABLED_QUEUE_IDS


def queue_label(queue_id: int, game_mode: str = "") -> str | None:
    """Return a readable queue name without requiring a network catalogue lookup."""
    if game_mode.strip().upper() == PRACTICE_TOOL_GAME_MODE:
        return QUEUE_ID_LABELS[0]
    if queue_id <= 0:
        return None
    return QUEUE_ID_LABELS.get(queue_id, f"File {queue_id}")
