"""Runtime status and live event routes."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

from ...config import CURRENT_VERSION, REGION_LIST, SUMMONER_SPELL_MAP
from ...domain.events import RuntimeEvent
from ...services.profile_config import build_effective_profile_config
from ...services.skin_modes import get_effective_skin_mode_for_slot
from ...services.updates import check_for_updates
from ...services.urls import (
    HOTKEY_PROVIDERS,
    STATS_PROVIDERS,
    build_hotkey_provider_home_url,
    build_hotkey_site_url,
    build_stats_provider_home_url,
    build_stats_site_url,
    is_valid_riot_id,
    resolve_provider_account,
)
from ..asset_urls import versioned_asset_url
from ..schemas import (
    BootstrapResponse,
    HealthResponse,
    LiveLinkResponse,
    MetadataResponse,
    PresetPreview,
    RuntimeSnapshotResponse,
    StatsLinkResponse,
    UpdatesResponse,
)

router = APIRouter(prefix="/api")


def _context(request: Request) -> Any:
    return request.app.state.context


def _cached_champion(data_dragon: Any, name_or_id: Any) -> tuple[int, dict[str, Any]] | None:
    if not getattr(data_dragon, "loaded", False):
        return None
    try:
        champion_id = int(name_or_id)
    except (TypeError, ValueError):
        normalizer = getattr(data_dragon, "_normalize", None)
        if not callable(normalizer):
            return None
        champion_id = data_dragon.by_norm_name.get(normalizer(str(name_or_id)))
    if not champion_id:
        return None
    champion = data_dragon.by_id.get(int(champion_id))
    return (int(champion_id), champion) if isinstance(champion, dict) else None


def _lcu_champion_record(static_data: Any, name_or_id: Any) -> dict[str, Any] | None:
    catalogue = static_data.load_champions()
    if isinstance(catalogue, dict):
        catalogue = catalogue.get("champions", catalogue.get("items", catalogue.get("data")))
        if isinstance(catalogue, dict):
            catalogue = list(catalogue.values())
    if not isinstance(catalogue, list):
        return None
    requested_name = str(name_or_id or "").strip().casefold()
    try:
        requested_id = int(name_or_id)
    except (TypeError, ValueError):
        requested_id = 0
    for record in catalogue:
        if not isinstance(record, dict):
            continue
        try:
            champion_id = int(record.get("championId", record.get("key", record.get("id", 0))))
        except (TypeError, ValueError):
            continue
        aliases = {
            str(record.get(field) or "").strip().casefold()
            for field in ("name", "alias", "id")
        }
        if champion_id == requested_id or requested_name in aliases:
            return record
    return None


def _preview_for_champion(context: Any, champion_name: Any) -> PresetPreview:
    name = str(champion_name or "").strip()
    static_data = getattr(context, "static_data", None)
    if static_data is not None:
        record = _lcu_champion_record(static_data, name)
        if record is not None:
            try:
                champion_id = int(record.get("championId", record.get("key", record.get("id", 0))))
            except (TypeError, ValueError):
                champion_id = 0
            if champion_id > 0:
                has_icon = static_data.asset_path("champion", champion_id) is not None
                cached = _cached_champion(context.data_dragon, champion_id)
                has_splash = bool(cached and (cached[1].get("image") or {}).get("full"))
                return PresetPreview(
                    champion_id=champion_id,
                    champion_name=str(record.get("name") or record.get("alias") or name),
                    champion_icon_url=versioned_asset_url(
                        f"/api/assets/champions/{champion_id}.png",
                        static_data.status.get("game_version"),
                    ) if has_icon else None,
                    champion_splash_url=versioned_asset_url(
                        f"/api/assets/champions/{champion_id}/splash",
                        context.data_dragon.version,
                    ) if has_splash else None,
                )

    cached = _cached_champion(context.data_dragon, name)
    if not cached:
        return PresetPreview(champion_name=name)
    champion_id, champion = cached
    has_image = bool((champion.get("image") or {}).get("full"))
    return PresetPreview(
        champion_id=champion_id,
        champion_name=str(champion.get("name") or name),
        champion_icon_url=versioned_asset_url(
            f"/api/assets/champions/{champion_id}.png", context.data_dragon.version
        ) if has_image else None,
        champion_splash_url=versioned_asset_url(
            f"/api/assets/champions/{champion_id}/splash", context.data_dragon.version
        ) if has_image else None,
    )


def _build_preset_previews(context: Any, params: dict[str, Any], effective: dict[str, Any]) -> dict[str, PresetPreview]:
    previews: dict[str, PresetPreview] = {}
    slots = effective.get("pick_slots") if isinstance(effective.get("pick_slots"), dict) else {}
    for slot_key in ("pick_1", "pick_2", "pick_3"):
        slot = slots.get(slot_key) if isinstance(slots.get(slot_key), dict) else {}
        champion_name = str(slot.get("champion") or "").strip()
        preview = _preview_for_champion(context, champion_name)
        if preview.champion_id:
            spell_1 = str(slot.get("spell_1") or "")
            spell_2 = str(slot.get("spell_2") or "")
            static_data = getattr(context, "static_data", None)
            spell_catalogue = static_data.load_summoner_spells() if static_data is not None else None
            for spell_name, field in ((spell_1, "spell_1_url"), (spell_2, "spell_2_url")):
                spell_id = SUMMONER_SPELL_MAP.get(spell_name, 0)
                has_lcu_asset = bool(
                    spell_catalogue is not None
                    and spell_id > 0
                    and static_data.asset_path("spell", spell_id)
                )
                if has_lcu_asset:
                    setattr(
                        preview,
                        field,
                        versioned_asset_url(
                            f"/api/assets/spells/{spell_id}.png",
                            static_data.status.get("game_version"),
                        ),
                    )
                elif context.data_dragon.summoner_loaded and spell_name in context.data_dragon.summoner_data:
                    setattr(
                        preview,
                        field,
                        versioned_asset_url(
                            f"/api/assets/spells?name={quote(spell_name)}",
                            context.data_dragon.version,
                        ),
                    )
            mode = get_effective_skin_mode_for_slot(slot_key, effective)
            if mode == "fixed":
                skin_id = int(slot.get("skin_id") or 0)
                skin_name = str(slot.get("skin_name") or "").strip()
                skin_num = int(slot.get("skin_num") or 0)
            elif mode == "random":
                pool = slot.get("random_skin_pool") if isinstance(slot.get("random_skin_pool"), list) else []
                first_pool = pool[0] if pool and isinstance(pool[0], dict) else {}
                skin_id = int(slot.get("random_skin_id") or first_pool.get("skin_id") or 0)
                skin_name = str(slot.get("random_skin_name") or first_pool.get("skin_name") or "").strip()
                skin_num = int(slot.get("random_skin_num") or first_pool.get("skin_num") or 0)
            else:
                skin_id = skin_num = 0
                skin_name = ""
            preview.skin_name = skin_name or None
            if skin_num > 0:
                preview.skin_preview_url = versioned_asset_url(
                    f"/api/assets/skins/{preview.champion_id}/{skin_id}/splash?skin_num={skin_num}",
                    context.data_dragon.version,
                )
        previews[slot_key] = preview
    return previews


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    context = _context(request)
    return {
        "ok": True,
        "service": "otp-lol",
        "version": CURRENT_VERSION,
        "lcu_connected": context.runtime.is_active,
    }


@router.get("/runtime", response_model=RuntimeSnapshotResponse)
def runtime_snapshot(request: Request) -> RuntimeSnapshotResponse:
    context = _context(request)
    return context.runtime.snapshot(context.get_params()).as_dict()


@router.get("/bootstrap", response_model=BootstrapResponse)
def bootstrap(request: Request) -> BootstrapResponse:
    """Return only persisted/runtime state, never a remote catalogue."""
    context = _context(request)
    params = context.get_params()
    effective = build_effective_profile_config(params)
    return {
        "runtime": context.runtime.snapshot(params).as_dict(),
        "settings": params,
        "presets": {
            "presets_enabled": effective["presets_enabled"],
            "selected_ban": effective["selected_ban"],
            "slots": effective["pick_slots"],
        },
        "preset_previews": _build_preset_previews(context, params, effective),
        "ban_preview": _preview_for_champion(context, params.get("selected_ban")),
    }


@router.get("/metadata", response_model=MetadataResponse)
async def metadata(request: Request) -> MetadataResponse:
    context = _context(request)
    await context.ensure_data_dragon()
    return context.runtime.metadata()


@router.get("/updates", response_model=UpdatesResponse)
async def updates(request: Request) -> UpdatesResponse:
    context = _context(request)
    update = await asyncio.to_thread(check_for_updates)
    ignored_version = str(context.get_params().get("ignored_update_version") or "")
    if update and update.get("version") == ignored_version:
        update = None
    return {"available": update is not None, "update": update}


@router.get("/links/stats", response_model=StatsLinkResponse)
def stats_link(request: Request) -> StatsLinkResponse:
    context = _context(request)
    params = context.get_params()
    riot_id, region, account_source = resolve_provider_account(params, context.runtime)
    site = str(params.get("preferred_stats_site") or "opgg").strip().lower()
    if site not in STATS_PROVIDERS:
        site = "opgg"
    available = is_valid_riot_id(riot_id) and region in REGION_LIST
    return {
        "available": available,
        "site": site,
        "url": build_stats_site_url(site, region, riot_id) if available else None,
        "homepage_url": build_stats_provider_home_url(site),
        "riot_id": riot_id if available else None,
        "region": region if available else None,
        "account_source": account_source,
    }


@router.get("/links/live", response_model=LiveLinkResponse)
def live_link(request: Request) -> LiveLinkResponse:
    context = _context(request)
    params = context.get_params()
    riot_id, region, account_source = resolve_provider_account(params, context.runtime)
    site = str(params.get("preferred_hotkey_site") or "porofessor").strip().lower()
    if site not in HOTKEY_PROVIDERS:
        site = "porofessor"
    available = is_valid_riot_id(riot_id) and region in REGION_LIST
    return {
        "available": available,
        "site": site,
        "url": build_hotkey_site_url(site, region, riot_id) if available else None,
        "homepage_url": build_hotkey_provider_home_url(site),
        "riot_id": riot_id if available else None,
        "region": region if available else None,
        "account_source": account_source,
    }


@router.websocket("/events")
async def events(websocket: WebSocket) -> None:
    origin = websocket.headers.get("origin")
    host = websocket.headers.get("host", "").lower()
    allowed_origins = {f"http://{host}", *websocket.app.state.dev_origins}
    if not origin or origin not in allowed_origins:
        await websocket.close(code=1008, reason="Origin not allowed")
        return
    await websocket.accept()
    context = websocket.app.state.context
    subscription = context.broker.subscribe()
    try:
        await websocket.send_json(
            RuntimeEvent(
                "runtime_snapshot",
                context.runtime.snapshot(context.get_params()).as_dict(),
            ).as_dict()
        )
        while True:
            receive_task = asyncio.create_task(websocket.receive())
            event_task = asyncio.create_task(subscription.next_event())
            done, pending = await asyncio.wait(
                {receive_task, event_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

            if receive_task in done:
                message = receive_task.result()
                if message.get("type") == "websocket.disconnect":
                    return
                continue
            event = event_task.result()
            await websocket.send_json(event.as_dict())
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        subscription.close()
