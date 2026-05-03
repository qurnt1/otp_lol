"""
FILE NAME: src/core/game_state.py
GLOBAL PURPOSE:
- Hold mutable runtime state shared by the websocket manager and automation helpers.
- Track the live game phase, temporary automation flags, and confirmation timestamps.
- Provide a clear reset point between matches without rebuilding the whole manager.

KEY FUNCTIONS:
- GameState: Mutable runtime state container for the live client session.
- reset_between_games: Clear champion-select and match-specific transient state.

AUDIENCE & LOGIC:
Why:
This module exists so transport code and automation code can share the same state object instead of duplicating transient flags.
For whom:
Developers maintaining live-client orchestration, retries, and per-match state resets.

DEPENDENCIES:
Used by:
- src/core/websocket.py and src/core/champ_select.py
Uses:
- Standard library: dataclasses, threading, typing
"""

from dataclasses import dataclass, field, fields, MISSING
from threading import Lock
from typing import Optional, Set


@dataclass
class GameState:
    """Store the mutable runtime state shared by the websocket and automation layers."""

    # ---- Persistent fields (survive between games) ----

    current_phase: str = "None"
    summoner: str = ""
    summoner_id: Optional[int] = None
    puuid: Optional[str] = None
    auto_game_name: Optional[str] = None
    auto_tag_line: Optional[str] = None
    platform_routing: str = "euw1"
    region_routing: str = "europe"
    last_game_start_notify_ts: float = 0.0
    last_reported_summoner: Optional[str] = None
    cache_lock: Lock = field(default_factory=Lock, repr=False)

    # ---- Transient fields (reset between every game) ----

    assigned_position: str = field(default="", metadata={"transient": True})
    timer_phase: str = field(default="", metadata={"transient": True})
    time_left_ms: int = field(default=0, metadata={"transient": True})
    has_picked: bool = field(default=False, metadata={"transient": True})
    has_banned: bool = field(default=False, metadata={"transient": True})
    intent_done: bool = field(default=False, metadata={"transient": True})
    completed_actions: Set[int] = field(default_factory=set, metadata={"transient": True})
    last_action_try_ts: float = field(default=0.0, metadata={"transient": True})
    last_intent_try_ts: float = field(default=0.0, metadata={"transient": True})
    _last_cs_session_fetch: float = field(default=0.0, metadata={"transient": True})
    _last_cs_timer_fetch: float = field(default=0.0, metadata={"transient": True})
    has_played_accept_sound: bool = field(default=False, metadata={"transient": True})
    has_prepicked: bool = field(default=False, metadata={"transient": True})
    last_prepick_slot: Optional[str] = field(default=None, metadata={"transient": True})
    last_locked_pick_slot: Optional[str] = field(default=None, metadata={"transient": True})
    prepick_wait_started_ts: float = field(default=0.0, metadata={"transient": True})
    last_prepick_try_ts: float = field(default=0.0, metadata={"transient": True})
    last_ban_try_ts: float = field(default=0.0, metadata={"transient": True})
    last_pick_try_ts: float = field(default=0.0, metadata={"transient": True})
    desired_spell_ids: Optional[tuple[int, int]] = field(default=None, metadata={"transient": True})
    last_confirmed_spell_ids: Optional[tuple[int, int]] = field(default=None, metadata={"transient": True})
    last_spell_try_ts: float = field(default=0.0, metadata={"transient": True})
    spell_apply_in_progress: bool = field(default=False, metadata={"transient": True})
    desired_skin_id: Optional[int] = field(default=None, metadata={"transient": True})
    last_confirmed_skin_id: Optional[int] = field(default=None, metadata={"transient": True})
    last_skin_try_ts: float = field(default=0.0, metadata={"transient": True})
    skin_apply_in_progress: bool = field(default=False, metadata={"transient": True})
    locked_random_skin_id: Optional[int] = field(default=None, metadata={"transient": True})
    desired_rune_page_id: Optional[int] = field(default=None, metadata={"transient": True})
    last_confirmed_rune_page_id: Optional[int] = field(default=None, metadata={"transient": True})
    last_rune_try_ts: float = field(default=0.0, metadata={"transient": True})
    rune_apply_in_progress: bool = field(default=False, metadata={"transient": True})
    rune_applied_for_session: bool = field(default=False, metadata={"transient": True})
    rune_task_scheduled: int = field(default=0, metadata={"transient": True})
    last_flow_note: str = field(default="", metadata={"transient": True})
    bench_enabled_notified: bool = field(default=False, metadata={"transient": True})

    def reset_between_games(self) -> None:
        """Clear all match-specific transient state before a new champion-select flow starts."""
        for f in fields(self):
            if not f.metadata.get("transient"):
                continue
            if f.default is not MISSING:
                setattr(self, f.name, f.default)
            elif f.default_factory is not MISSING:
                setattr(self, f.name, f.default_factory())
