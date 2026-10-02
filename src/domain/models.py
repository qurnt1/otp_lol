"""Data snapshots exposed by the runtime boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    version: str
    connected: bool
    phase: str
    riot_id: str | None
    region: str
    queue_id: int
    assigned_position: str
    presets_enabled: bool
    auto_accept_enabled: bool
    auto_pick_enabled: bool
    auto_ban_enabled: bool
    auto_summoners_enabled: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "connected": self.connected,
            "phase": self.phase,
            "riot_id": self.riot_id,
            "region": self.region,
            "queue_id": self.queue_id,
            "assigned_position": self.assigned_position,
            "presets_enabled": self.presets_enabled,
            "auto_accept_enabled": self.auto_accept_enabled,
            "auto_pick_enabled": self.auto_pick_enabled,
            "auto_ban_enabled": self.auto_ban_enabled,
            "auto_summoners_enabled": self.auto_summoners_enabled,
        }
