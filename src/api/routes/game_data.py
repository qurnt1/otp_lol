"""Status for local League game data and its available fallbacks."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api", tags=["game-data"])


@router.get("/game-data/status")
async def game_data_status(request: Request) -> dict[str, Any]:
    return await resolved_game_data_status(request.app.state.context)


async def resolved_game_data_status(context: Any) -> dict[str, Any]:
    await context.ensure_static_data()
    status = context.static_data.status
    catalogues = {
        name: bool(catalogue["available"])
        for name, catalogue in status["catalogs"].items()
    }
    local_source = status["source"]
    needs_champions = not catalogues.get("champions", False)
    needs_spells = not catalogues.get("spells", False)
    if needs_champions and not context.data_dragon.loaded:
        await context.ensure_data_dragon()

    uses_datadragon_champions = (
        needs_champions
        and context.data_dragon.loaded
        and bool(context.data_dragon.by_id)
    )
    uses_datadragon_spells = (
        needs_spells
        and context.data_dragon.summoner_loaded
        and bool(context.data_dragon.summoner_data)
    )
    if uses_datadragon_champions:
        catalogues["champions"] = True
    if uses_datadragon_spells:
        catalogues["spells"] = True
    used_datadragon = uses_datadragon_champions or uses_datadragon_spells

    source = local_source or ("datadragon" if used_datadragon else None)
    if local_source and used_datadragon:
        source = "mixed"

    return {
        "source": source,
        "game_version": status["game_version"],
        "connected": status["connected"],
        "cache_available": status["cache_available"],
        "cache_version": status["cache_version"],
        "fallback": "datadragon" if used_datadragon else None,
        "catalogs": catalogues,
    }
