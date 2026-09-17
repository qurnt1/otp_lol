"""UI-independent façade around the existing League Client runtime."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from ..config import CURRENT_VERSION
from ..core.datadragon import DataDragon
from ..core.websocket import WebSocketManager
from ..domain.events import EventBroker
from ..domain.models import RuntimeSnapshot


class RuntimeUnavailable(RuntimeError):
    """Raised when an async LCU operation is requested before the loop is ready."""


class LcuRuntime:
    """Adapt the legacy manager to a thread-safe, UI-agnostic runtime API."""

    def __init__(
        self,
        *,
        data_dragon: DataDragon,
        get_params: Callable[[], dict[str, Any]],
        update_param: Callable[[str, Any], None] | None,
        broker: EventBroker,
        event_hook: Callable[[str, Any], None] | None = None,
        manager_type: type[WebSocketManager] = WebSocketManager,
    ) -> None:
        self.data_dragon = data_dragon
        self.broker = broker
        self.event_hook = event_hook
        self.manager = manager_type(
            event_callback=self._publish_event,
            dd=data_dragon,
            get_params=get_params,
            update_param=update_param,
        )

    _SNAPSHOT_EVENTS = frozenset(
        {
            "connected",
            "disconnected",
            "phase_change",
            "champion_picked",
            "champion_banned",
            "spells_set",
            "summoner_update",
        }
    )

    def _publish_event(self, event_type: str, data: Any = None) -> None:
        if self.event_hook is not None:
            self.event_hook(event_type, data)
        self.broker.publish(event_type, data)
        if event_type in self._SNAPSHOT_EVENTS:
            self.broker.publish(
                "runtime_snapshot",
                self.snapshot(self.manager.get_params()).as_dict(),
            )

    @property
    def is_active(self) -> bool:
        return self.manager.is_active

    def start(self) -> None:
        self.manager.start()

    def stop(self) -> None:
        self.manager.stop()

    def snapshot(self, params: dict[str, Any]) -> RuntimeSnapshot:
        state = self.manager.state
        try:
            queue_id = int(state.current_queue_id or 0)
        except (TypeError, ValueError):
            queue_id = 0
        return RuntimeSnapshot(
            version=CURRENT_VERSION,
            connected=self.is_active,
            phase=str(state.current_phase or "None"),
            riot_id=self.manager.get_riot_id(),
            region=self.manager.get_platform_for_websites(),
            queue_id=queue_id,
            assigned_position=str(state.assigned_position or ""),
            presets_enabled=bool(params.get("presets_enabled", True)),
            auto_accept_enabled=bool(params.get("auto_accept_enabled", True)),
            auto_pick_enabled=bool(params.get("auto_pick_enabled", True)),
            auto_ban_enabled=bool(params.get("auto_ban_enabled", True)),
            auto_summoners_enabled=bool(params.get("auto_summoners_enabled", True)),
        )

    async def load_data_dragon(self) -> None:
        await asyncio.to_thread(self.data_dragon.load)

    async def _submit(self, coroutine_factory: Callable[[], Any]) -> Any:
        loop = self.manager.loop
        if loop is None or loop.is_closed():
            raise RuntimeUnavailable("The League Client runtime is not ready")
        future = asyncio.run_coroutine_threadsafe(coroutine_factory(), loop)
        return await asyncio.wrap_future(future)

    async def fetch_rune_pages(self) -> list[dict[str, Any]]:
        return await self._submit(self.manager._fetch_rune_pages_async)

    async def fetch_rune_styles(self) -> dict[int, dict[str, Any]]:
        return await self._submit(self.manager._fetch_rune_styles_async)

    async def fetch_current_rune_page(self) -> dict[str, Any] | None:
        return await self._submit(self.manager._fetch_current_rune_page_async)

    async def set_rune_page(self, page_data: dict[str, Any]) -> bool:
        return bool(
            await self._submit(
                lambda: self.manager._set_rune_page_via_perks_async(page_data)
            )
        )

    async def create_rune_page(self, page_data: dict[str, Any]) -> int | None:
        return await self._submit(
            lambda: self.manager._create_rune_page_async(page_data)
        )

    async def delete_rune_page(self, page_id: int) -> bool:
        return bool(
            await self._submit(lambda: self.manager._delete_rune_page_async(page_id))
        )

    async def fetch_owned_skins(self, champion_id: int) -> dict[str, Any]:
        return await self._submit(
            lambda: self.manager._fetch_owned_skins_for_champion(champion_id)
        )

    async def apply_spells(self, slot_key: str | None = None) -> None:
        await self._submit(
            lambda: self.manager._set_spells(self.get_params(), slot_key=slot_key)
        )

    async def apply_skin(self, slot_key: str | None = None) -> None:
        await self._submit(
            lambda: self.manager._set_skin(self.get_params(), slot_key=slot_key)
        )

    async def apply_runes(self, slot_key: str | None = None) -> None:
        await self._submit(
            lambda: self.manager._set_rune_page(self.get_params(), slot_key=slot_key)
        )

    async def lock_in_champion(
        self, action_id: int, champion_id: int, *, action_type: str = "pick"
    ) -> bool:
        if action_type not in {"pick", "ban"}:
            raise ValueError("action_type must be 'pick' or 'ban'")
        return bool(
            await self._submit(
                lambda: self.manager._lock_in_champion(
                    action_id, champion_id, action_type=action_type
                )
            )
        )

    async def get_skin_catalog(self, champion_id: int) -> list[dict[str, Any]]:
        await self.load_data_dragon_if_needed()
        return await asyncio.to_thread(self.data_dragon.get_skin_catalog, champion_id)

    async def load_data_dragon_if_needed(self) -> None:
        if not self.data_dragon.loaded:
            await self.load_data_dragon()

    def metadata(self) -> dict[str, Any]:
        return {
            "version": CURRENT_VERSION,
            "loaded": bool(self.data_dragon.loaded),
            "champion_count": len(self.data_dragon.all_names),
            "data_dragon_version": self.data_dragon.version,
        }
