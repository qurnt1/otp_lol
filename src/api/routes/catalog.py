"""Champion, spell, rune and skin catalog routes."""

from __future__ import annotations

import asyncio
import os
from io import BytesIO
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse

from ...config import (
    REGION_LIST,
    SUMMONER_SPELL_LIST,
    SUMMONER_SPELL_MAP,
    URL_DD_IMG_ITEM,
)
from ...config.paths import resource_path
from ...integrations.communitydragon import CommunityDragonClient
from ...lcu.runtime import RuntimeUnavailable
from ...services.champion_roles import get_champion_positions
from ...services.urls import PROVIDER_LOGO_FILES, provider_catalog_options
from ..asset_urls import versioned_asset_url
from ..schemas import ProviderCatalog

router = APIRouter(prefix="/api")
def _context(request: Request) -> Any:
    return request.app.state.context


def _png_response(image: Any) -> Response:
    if image is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    buffer = BytesIO()
    image.convert("RGBA").save(buffer, format="PNG")
    return Response(
        content=buffer.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "no-cache"},
    )


def _lcu_records(payload: Any, collection: str) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for field in (collection, "items", "data"):
            nested = payload.get(field)
            if isinstance(nested, (list, dict)):
                payload = nested
                break
        if isinstance(payload, dict):
            payload = list(payload.values())
    if not isinstance(payload, list):
        return []
    return [record for record in payload if isinstance(record, dict)]


def _lcu_champions(payload: Any, context: Any) -> list[dict[str, Any]] | None:
    static_data = getattr(context, "static_data", None)
    if static_data is None:
        return None
    records = _lcu_records(payload, "champions")
    items = []
    for record in records:
        raw_id = record.get("championId", record.get("key", record.get("id")))
        try:
            champion_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        name = str(record.get("name") or record.get("alias") or "").strip()
        if champion_id <= 0 or not name:
            continue
        alias = str(record.get("alias") or record.get("id") or name).strip()
        tags = record.get("tags")
        roles = record.get("roles")
        items.append(
            {
                "id": champion_id,
                "name": name,
                "slug": alias,
                "title": str(record.get("title") or ""),
                "tags": [str(tag) for tag in tags if isinstance(tag, str)] if isinstance(tags, list) else [],
                "roles": sorted({str(role).upper() for role in roles if isinstance(role, str)}) if isinstance(roles, list) else [],
                "icon_url": versioned_asset_url(
                    f"/api/assets/champions/{champion_id}.png",
                    static_data.status.get("game_version"),
                ),
                "splash_url": (
                    versioned_asset_url(
                        f"/api/assets/champions/{champion_id}/splash",
                        context.data_dragon.version,
                    )
                    if getattr(context.data_dragon, "loaded", False)
                    else None
                ),
            }
        )
    return items or None


@router.get("/champions")
async def champions(request: Request, q: str = "") -> dict[str, Any]:
    context = _context(request)
    normalized_query = q.strip().lower()
    await context.ensure_static_data()
    static_data = getattr(context, "static_data", None)
    catalogue = static_data.load_champions() if static_data is not None else None
    lcu_items = _lcu_champions(catalogue, context) if catalogue is not None else None
    if lcu_items is None:
        await context.ensure_data_dragon()
        items = []
        for champion_id, info in context.data_dragon.by_id.items():
            name = str(info.get("name") or "")
            slug = str(info.get("id") or "")
            if normalized_query and normalized_query not in name.lower() and normalized_query not in slug.lower():
                continue
            image_name = str(info.get("image", {}).get("full") or "")
            items.append(
                {
                    "id": champion_id,
                    "name": name,
                    "slug": slug,
                    "title": str(info.get("title") or ""),
                    "tags": context.data_dragon.get_champion_tags(champion_id),
                    "roles": sorted(get_champion_positions(context.data_dragon, name)),
                    "icon_url": versioned_asset_url(f"/api/assets/champions/{champion_id}.png", context.data_dragon.version) if image_name else None,
                    "splash_url": versioned_asset_url(f"/api/assets/champions/{champion_id}/splash", context.data_dragon.version) if image_name else None,
                }
            )
    else:
        items = [
            item for item in lcu_items
            if not normalized_query
            or normalized_query in item["name"].lower()
            or normalized_query in item["slug"].lower()
        ]
    items.sort(key=lambda item: item["name"].lower())
    return {"items": items, "count": len(items)}


@router.get("/catalog/providers", response_model=ProviderCatalog)
def providers() -> ProviderCatalog:
    return {
        "stats": provider_catalog_options("stats"),
        "live": provider_catalog_options("live"),
        "regions": [{"id": region, "label": region.upper()} for region in REGION_LIST],
    }


@router.get("/assets/providers/{provider_id}")
def provider_logo(provider_id: str) -> FileResponse:
    filename = PROVIDER_LOGO_FILES.get(provider_id)
    if filename is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    path = resource_path(os.path.join("config", "images", "websites", filename))
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@router.get("/spells")
async def spells(request: Request) -> dict[str, Any]:
    context = _context(request)
    await context.ensure_static_data()
    static_data = getattr(context, "static_data", None)
    catalogue = static_data.load_summoner_spells() if static_data is not None else None
    has_lcu_assets = {
        name: bool(
            catalogue is not None
            and spell_id > 0
            and static_data is not None
            and static_data.asset_path("spell", spell_id) is not None
        )
        for name, spell_id in SUMMONER_SPELL_MAP.items()
    }
    if not all(has_lcu_assets.get(name, False) for name in SUMMONER_SPELL_LIST if SUMMONER_SPELL_MAP[name] > 0):
        await context.ensure_data_dragon()
        await asyncio.to_thread(context.data_dragon.load_summoners)
    items = []
    for name in SUMMONER_SPELL_LIST:
        spell_id = SUMMONER_SPELL_MAP.get(name, 0)
        has_lcu_asset = has_lcu_assets.get(name, False)
        has_fallback_asset = context.data_dragon.summoner_data.get(name)
        items.append(
            {
                "name": name,
                "icon_url": (
                    versioned_asset_url(
                        f"/api/assets/spells/{spell_id}.png",
                        static_data.status.get("game_version") or "",
                    )
                    if has_lcu_asset
                    else versioned_asset_url(f"/api/assets/spells?name={quote(name)}", context.data_dragon.version)
                    if has_fallback_asset
                    else None
                ),
            }
        )
    return {"items": items}


@router.get("/skins/{champion_id}")
async def skins(request: Request, champion_id: int) -> dict[str, Any]:
    context = _context(request)
    catalog = await context.runtime.get_skin_catalog(champion_id)
    for skin in catalog:
        if (
            skin.get("tile_url")
            or skin.get("centered_splash_url")
            or skin.get("uncentered_splash_url")
            or skin.get("splash_url")
        ):
            skin["tile_url"] = versioned_asset_url(
                f"/api/assets/skins/{champion_id}/{skin['skin_id']}.png", context.data_dragon.version
            )
    owned: dict[str, Any] = {"ok": False, "owned_skins": [], "message": "League client is not connected."}
    if context.runtime.is_active:
        try:
            owned = await context.runtime.fetch_owned_skins(champion_id)
        except RuntimeUnavailable:
            pass
    return {"champion_id": champion_id, "catalog": catalog, "owned": owned}


@router.get("/runes")
async def runes(request: Request) -> dict[str, Any]:
    context = _context(request)
    if not context.runtime.is_active:
        return {"available": False, "pages": [], "styles": {}}
    try:
        pages, styles = await asyncio.gather(
            context.runtime.fetch_rune_pages(),
            context.runtime.fetch_rune_styles(),
        )
    except RuntimeUnavailable:
        return {"available": False, "pages": [], "styles": {}}
    perk_paths = {
        int(perk["id"]): str(perk.get("iconPath") or "")
        for style in styles.values()
        for perk in style.get("perks", [])
        if isinstance(perk, dict) and str(perk.get("id") or "").isdigit()
    }
    for page in pages:
        page["selectedPerkPaths"] = [
            perk_paths.get(perk_id, "")
            for perk_id in page.get("selectedPerkIds", [])
            if isinstance(perk_id, int)
        ]
    for style in styles.values():
        style_path = str(style.get("iconPath") or "")
        style["icon_url"] = f"/api/assets/runes/style?path={quote(style_path)}" if style_path else None
        for perk in style.get("perks", []):
            perk_id = int(perk.get("id") or 0)
            perk["icon_url"] = f"/api/assets/runes/perk/{perk_id}.png" if perk_id > 0 else None
    return {"available": True, "pages": pages, "styles": styles}


@router.get("/assets/champions/{champion_id}.png")
async def champion_asset(request: Request, champion_id: int) -> Response:
    context = _context(request)
    asset_service = getattr(context, "asset_service", None)
    if asset_service is not None:
        asset = await asset_service.get_asset("champion", champion_id)
        if asset is not None:
            return Response(content=asset.content, media_type=asset.content_type, headers={"Cache-Control": "public, max-age=86400"})
    await context.ensure_data_dragon()
    image = await asyncio.to_thread(context.data_dragon.get_champion_icon, champion_id)
    return _png_response(image)


@router.get("/assets/champions/{champion_id}/splash")
async def champion_splash_asset(request: Request, champion_id: int) -> Response:
    context = _context(request)
    await context.ensure_data_dragon()
    image = await asyncio.to_thread(context.data_dragon.get_champion_splash, champion_id)
    return _png_response(image)


@router.get("/assets/spells")
async def spell_asset(request: Request, name: str) -> Response:
    context = _context(request)
    await context.ensure_data_dragon()
    image = await asyncio.to_thread(context.data_dragon.get_summoner_icon, name)
    return _png_response(image)


@router.get("/assets/spells/{spell_id}.png")
async def spell_asset_by_id(request: Request, spell_id: int) -> Response:
    context = _context(request)
    asset_service = getattr(context, "asset_service", None)
    if asset_service is not None:
        asset = await asset_service.get_asset("spell", spell_id)
        if asset is not None:
            return Response(content=asset.content, media_type=asset.content_type, headers={"Cache-Control": "public, max-age=86400"})
    spell_name = next(
        (name for name, value in SUMMONER_SPELL_MAP.items() if value == spell_id and value > 0),
        None,
    )
    if spell_name is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    await context.ensure_data_dragon()
    await asyncio.to_thread(context.data_dragon.load_summoners)
    image = await asyncio.to_thread(context.data_dragon.get_summoner_icon, spell_name)
    return _png_response(image)


@router.get("/assets/runes/perk/{perk_id}.png")
async def rune_perk_asset(request: Request, perk_id: int) -> Response:
    context = _context(request)
    asset_service = getattr(context, "asset_service", None)
    if asset_service is not None:
        asset = await asset_service.get_asset("perk", perk_id)
        if asset is not None:
            return Response(content=asset.content, media_type=asset.content_type, headers={"Cache-Control": "public, max-age=86400"})

    def load_image() -> Any:
        path = context.data_dragon.get_rune_perk_icon_path(perk_id)
        return context.data_dragon.get_rune_perk_icon(path) if path else None

    return _png_response(await asyncio.to_thread(load_image))


@router.get("/assets/items/{item_id}.png")
async def item_asset(request: Request, item_id: int) -> Response:
    if item_id <= 0:
        raise HTTPException(status_code=404, detail="Asset not found")
    context = _context(request)
    asset_service = getattr(context, "asset_service", None)
    if asset_service is not None:
        asset = await asset_service.get_asset("item", item_id)
        if asset is not None:
            return Response(
                content=asset.content,
                media_type=asset.content_type,
                headers={"Cache-Control": "no-cache"},
            )
    await context.ensure_data_dragon()
    version = context.data_dragon.version
    if not version:
        raise HTTPException(status_code=404, detail="Asset not found")
    image_url = URL_DD_IMG_ITEM.format(version=version, filename=f"{item_id}.png")
    image = await asyncio.to_thread(
        context.data_dragon.get_remote_image,
        image_url,
        cache_key=f"frontend_item_{version}_{item_id}",
    )
    return _png_response(image)


@router.get("/assets/runes/perk")
async def rune_perk_asset_by_path(request: Request, path: str) -> Response:
    """Serve a validated CommunityDragon perk path already returned by the LCU."""
    context = _context(request)
    if not CommunityDragonClient.asset_url(path):
        raise HTTPException(status_code=404, detail="Asset not found")
    image = await asyncio.to_thread(context.data_dragon.get_rune_perk_icon, path)
    return _png_response(image)


@router.get("/assets/runes/style")
async def rune_style_asset(request: Request, path: str) -> Response:
    context = _context(request)
    image = await asyncio.to_thread(context.data_dragon.get_rune_style_icon, path)
    return _png_response(image)


@router.get("/assets/skins/{champion_id}/{skin_id}.png")
async def skin_asset(request: Request, champion_id: int, skin_id: int, skin_num: int | None = None) -> Response:
    context = _context(request)
    asset_service = getattr(context, "asset_service", None)
    if asset_service is not None:
        asset = await asset_service.get_asset("skin", skin_id)
        if asset is not None:
            return Response(content=asset.content, media_type=asset.content_type, headers={"Cache-Control": "public, max-age=86400"})
    await context.ensure_data_dragon()

    def load_image() -> Any:
        catalog = context.data_dragon.get_cached_skin_catalog(champion_id)
        skin = next((item for item in catalog if int(item.get("skin_id") or 0) == skin_id), None)
        if not skin:
            return context.data_dragon.get_skin_preview(champion_id, skin_num) if skin_num is not None else None
        preview_url = (
            skin.get("tile_url")
            or skin.get("centered_splash_url")
            or skin.get("uncentered_splash_url")
            or skin.get("splash_url")
        )
        if not preview_url:
            return context.data_dragon.get_skin_preview(champion_id, skin_num) if skin_num is not None else None
        image = context.data_dragon.get_remote_image(
            preview_url, cache_key=f"frontend_skin_{champion_id}_{skin_id}"
        )
        if image is None and skin_num is not None:
            return context.data_dragon.get_skin_preview(champion_id, skin_num)
        return image

    return _png_response(await asyncio.to_thread(load_image))


@router.get("/assets/skins/{champion_id}/{skin_id}/splash")
async def skin_splash_asset(
    request: Request,
    champion_id: int,
    skin_id: int,
    skin_num: int | None = None,
) -> Response:
    context = _context(request)
    asset_service = getattr(context, "asset_service", None)
    if asset_service is not None:
        asset = await asset_service.get_asset("skin", skin_id, variant="splash")
        if asset is not None:
            return Response(content=asset.content, media_type=asset.content_type, headers={"Cache-Control": "public, max-age=86400"})
    await context.ensure_data_dragon()

    def load_image() -> Any:
        skin = next(
            (
                item
                for item in context.data_dragon.get_cached_skin_catalog(champion_id)
                if int(item.get("skin_id") or 0) == skin_id
            ),
            None,
        )
        if skin is None and skin_num is not None:
            return context.data_dragon.get_skin_preview(champion_id, skin_num)
        if skin is None:
            return None

        for field in ("centered_splash_url", "uncentered_splash_url", "splash_url", "tile_url"):
            image_url = str(skin.get(field) or "").strip()
            if image_url:
                image = context.data_dragon.get_remote_image(
                    image_url,
                    cache_key=f"frontend_skin_splash_{champion_id}_{skin_id}_{field}",
                )
                if image is not None:
                    return image
        return None

    return _png_response(await asyncio.to_thread(load_image))
