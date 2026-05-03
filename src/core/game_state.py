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
- Standard library: threading, typing
"""

from threading import Lock
from typing import Optional, Set


class GameState:
    """Store the mutable runtime state shared by the websocket and automation layers."""

    def __init__(self):
        """Initialize runtime flags, timestamps, and cached identifiers for one app session."""
        self.current_phase: str = "None"
        self.summoner: str = ""
        self.summoner_id: Optional[int] = None
        self.puuid: Optional[str] = None
        self.auto_game_name: Optional[str] = None
        self.auto_tag_line: Optional[str] = None
        self.platform_routing: str = "euw1"
        self.region_routing: str = "europe"
        self.assigned_position: str = ""
        self.timer_phase: str = ""
        self.time_left_ms: int = 0
        self.has_picked: bool = False
        self.has_banned: bool = False
        self.intent_done: bool = False
        self.completed_actions: Set[int] = set()
        self.last_action_try_ts: float = 0.0
        self.last_intent_try_ts: float = 0.0
        self.last_game_start_notify_ts: float = 0.0
        self._last_cs_session_fetch: float = 0.0
        self._last_cs_timer_fetch: float = 0.0
        self.has_played_accept_sound: bool = False
        self.last_reported_summoner: Optional[str] = None
        self.has_prepicked: bool = False
        self.last_prepick_slot: Optional[str] = None
        self.last_locked_pick_slot: Optional[str] = None
        self.prepick_wait_started_ts: float = 0.0
        self.last_prepick_try_ts: float = 0.0
        self.last_ban_try_ts: float = 0.0
        self.last_pick_try_ts: float = 0.0
        self.desired_spell_ids: Optional[tuple[int, int]] = None
        self.last_confirmed_spell_ids: Optional[tuple[int, int]] = None
        self.last_spell_try_ts: float = 0.0
        self.spell_apply_in_progress: bool = False
        self.desired_skin_id: Optional[int] = None
        self.last_confirmed_skin_id: Optional[int] = None
        self.last_skin_try_ts: float = 0.0
        self.skin_apply_in_progress: bool = False
        self.locked_random_skin_id: Optional[int] = None
        self.desired_rune_page_id: Optional[int] = None
        self.last_confirmed_rune_page_id: Optional[int] = None
        self.last_rune_try_ts: float = 0.0
        self.rune_apply_in_progress: bool = False
        self.rune_applied_for_session: bool = False
        self.rune_task_scheduled: int = 0
        self.last_flow_note: str = ""
        self.cache_lock = Lock()

    def reset_between_games(self) -> None:
        """Clear all match-specific transient state before a new champion-select flow starts."""
        self.completed_actions.clear()
        self.has_picked = False
        self.has_banned = False
        self.intent_done = False
        self.assigned_position = ""
        self.timer_phase = ""
        self.time_left_ms = 0
        self.last_action_try_ts = 0.0
        self.last_intent_try_ts = 0.0
        self._last_cs_session_fetch = 0.0
        self._last_cs_timer_fetch = 0.0
        self.has_played_accept_sound = False
        self.has_prepicked = False
        self.last_prepick_slot = None
        self.last_locked_pick_slot = None
        self.prepick_wait_started_ts = 0.0
        self.last_prepick_try_ts = 0.0
        self.last_ban_try_ts = 0.0
        self.last_pick_try_ts = 0.0
        self.desired_spell_ids = None
        self.last_confirmed_spell_ids = None
        self.last_spell_try_ts = 0.0
        self.spell_apply_in_progress = False
        self.desired_skin_id = None
        self.last_confirmed_skin_id = None
        self.last_skin_try_ts = 0.0
        self.skin_apply_in_progress = False
        self.locked_random_skin_id = None
        self.desired_rune_page_id = None
        self.last_confirmed_rune_page_id = None
        self.last_rune_try_ts = 0.0
        self.rune_apply_in_progress = False
        self.rune_applied_for_session = False
        self.rune_task_scheduled = 0
        self.last_flow_note = ""
