"""Normalized account statistics backed by the local League Client."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from fastapi import APIRouter, HTTPException, Path, Query, Request

from ..account_models import (
    AccountResult,
    AccountSummary,
    ChallengesStats,
    MasteryStats,
    MatchDetail,
    MatchHistory,
    MatchTimeline,
    RankedStats,
)

router = APIRouter(prefix="/api/account", tags=["account"])


def _context(request: Request) -> Any:
    return request.app.state.context


def _catalogue_records(payload: Any, collection: str) -> list[tuple[Any, Mapping[str, Any]]]:
    if isinstance(payload, Mapping):
        for key in (collection, "data", "items"):
            nested = payload.get(key)
            if isinstance(nested, (Mapping, list)):
                payload = nested
                break
    if isinstance(payload, Mapping):
        return [(key, item) for key, item in payload.items() if isinstance(item, Mapping)]
    if isinstance(payload, list):
        return [(None, item) for item in payload if isinstance(item, Mapping)]
    return []


def _catalogue_index(payload: Any, collection: str, id_fields: tuple[str, ...]) -> dict[int, Mapping[str, Any]]:
    indexed: dict[int, Mapping[str, Any]] = {}
    for key, record in _catalogue_records(payload, collection):
        raw_id = next((record[field] for field in id_fields if record.get(field) is not None), key)
        if isinstance(raw_id, bool):
            continue
        if isinstance(raw_id, int):
            record_id = raw_id
        elif isinstance(raw_id, str) and raw_id.isascii() and raw_id.isdecimal():
            record_id = int(raw_id)
        else:
            continue
        if record_id > 0:
            indexed[record_id] = record
    return indexed


def _display_name(record: Mapping[str, Any]) -> str | None:
    localized = record.get("localizedNames")
    name = (
        localized.get("fr_FR") or localized.get("en_US")
        if isinstance(localized, Mapping)
        else None
    )
    if not isinstance(name, str) or not name.strip():
        name = record.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    return name.strip()[:100]


def _attach_local_game_data(
    context: Any, result: dict[str, Any], *, include_item_names: bool = False
) -> dict[str, Any]:
    data = result.get("data")
    static_data = getattr(context, "static_data", None)
    if not isinstance(data, dict) or static_data is None:
        return result

    data = deepcopy(data)
    result["data"] = data
    queues = _catalogue_index(static_data.load_queues(), "queues", ("queueId", "id", "key"))
    maps = _catalogue_index(static_data.load_maps(), "maps", ("mapId", "id", "key"))
    matches = data.get("matches") if isinstance(data.get("matches"), list) else [data]
    for match in matches:
        if not isinstance(match, dict):
            continue
        queue_id = match.get("queue_id")
        try:
            queue = queues.get(int(queue_id))
        except (TypeError, ValueError):
            queue = None
        if queue is None:
            continue
        queue_name = _display_name(queue)
        if queue_name:
            match["queue_name"] = queue_name
        try:
            map_id = int(queue.get("mapId"))
        except (TypeError, ValueError):
            map_id = 0
        map_record = maps.get(map_id)
        map_name = _display_name(map_record) if map_record else None
        if map_name:
            match["map_name"] = map_name

    if include_item_names:
        item_ids = {
            item_id
            for participant in data.get("participants", [])
            if isinstance(participant, dict)
            for item_id in participant.get("items", [])
            if isinstance(item_id, int) and not isinstance(item_id, bool) and item_id > 0
        }
        item_ids.update(
            event["item_id"]
            for event in data.get("events", [])
            if isinstance(event, dict)
            and isinstance(event.get("item_id"), int)
            and not isinstance(event["item_id"], bool)
            and event["item_id"] > 0
        )
        items = (
            _catalogue_index(static_data.load_items(), "items", ("itemId", "id", "key"))
            if item_ids
            else {}
        )
        data["item_names"] = {
            item_id: name
            for item_id in item_ids
            if (record := items.get(item_id)) is not None
            if (name := _display_name(record)) is not None
        }
    return result


@router.get("/summary", response_model=AccountResult[AccountSummary])
async def account_summary(request: Request) -> dict[str, Any]:
    return (await _context(request).account_stats.get_summary()).as_dict()


@router.get("/ranked", response_model=AccountResult[RankedStats])
async def account_ranked(request: Request) -> dict[str, Any]:
    return (await _context(request).account_stats.get_ranked()).as_dict()


@router.get("/masteries", response_model=AccountResult[MasteryStats])
async def account_masteries(
    request: Request,
    limit: int = Query(default=10, ge=1, le=20),
) -> dict[str, Any]:
    try:
        result = await _context(request).account_stats.get_masteries(limit)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return result.as_dict()


@router.get("/challenges", response_model=AccountResult[ChallengesStats])
async def account_challenges(
    request: Request,
    limit: int = Query(default=3, ge=1, le=50),
) -> dict[str, Any]:
    try:
        result = await _context(request).account_stats.get_challenges(limit)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return result.as_dict()


@router.get("/matches", response_model=AccountResult[MatchHistory])
async def account_matches(
    request: Request,
    limit: int = Query(default=20, ge=1, le=20),
) -> dict[str, Any]:
    try:
        result = await _context(request).account_stats.get_matches(limit)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _attach_local_game_data(_context(request), result.as_dict())


@router.get("/matches/{game_id}", response_model=AccountResult[MatchDetail])
async def account_match_detail(
    request: Request,
    game_id: int = Path(gt=0, le=2**64 - 1),
) -> dict[str, Any]:
    try:
        result = await _context(request).account_stats.get_match_detail(game_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _attach_local_game_data(_context(request), result.as_dict(), include_item_names=True)


@router.get("/matches/{game_id}/timeline", response_model=AccountResult[MatchTimeline])
async def account_match_timeline(
    request: Request,
    game_id: int = Path(gt=0, le=2**64 - 1),
) -> dict[str, Any]:
    try:
        result = await _context(request).account_stats.timeline(game_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _attach_local_game_data(_context(request), result.as_dict(), include_item_names=True)
