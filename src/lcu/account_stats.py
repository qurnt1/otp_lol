"""Allowlisted, cache-backed account statistics from the local LCU."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import math
import os
import re
import tempfile
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Literal

from .client import LcuResponse

MAX_MATCHES = 20
MAX_MASTERY_ENTRIES = 20
MAX_CHALLENGE_ENTRIES = 50
MAX_CACHE_BYTES = 2 * 1024 * 1024
MAX_CACHE_DETAILS = 20
MAX_MATCH_OFFSET = 1_000_000
MAX_TIMELINE_EVENTS = 500

_CACHE_VERSION = 1
_ERROR_CODES = frozenset(
    {
        "disconnected",
        "timeout",
        "request_error",
        "http_error",
        "invalid_response",
        "response_too_large",
        "invalid_json",
    }
)
_SOURCE = Literal["lcu", "cache", "mixed", "unavailable"]

RequestJson = Callable[[str], Awaitable[LcuResponse]]


@dataclass(frozen=True, slots=True)
class AccountStatsResult:
    """Sanitized JSON data and freshness metadata for one independent section."""

    data: dict[str, Any] | None
    source: _SOURCE
    from_cache: bool
    last_synced_at: str | None
    errors: dict[str, str] = field(default_factory=dict)
    available: bool = field(init=False)
    stale: bool = field(init=False)
    last_synced: str | None = field(init=False)
    error: str | None = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "available", self.data is not None)
        object.__setattr__(self, "stale", self.from_cache)
        object.__setattr__(self, "last_synced", self.last_synced_at)
        if not self.errors:
            error = None
        elif self.data is not None:
            error = "partial_failure"
        else:
            error = next(iter(self.errors.values()))
        object.__setattr__(self, "error", error)

    def as_dict(self) -> dict[str, Any]:
        return {
            "data": self.data,
            "available": self.available,
            "stale": self.stale,
            "last_synced": self.last_synced,
            "error": self.error,
            "source": self.source,
            "from_cache": self.from_cache,
            "errors": dict(self.errors),
        }


@dataclass(frozen=True, slots=True)
class _Identity:
    cache_key: str | None
    puuid: str | None
    summoner_id: str | None


@dataclass(frozen=True, slots=True)
class _CachedSection:
    data: dict[str, Any]
    synced_at: Any


class AccountStatsService:
    """Read-only account stats using injected LCU/runtime dependencies.

    ``cache_path`` is a directory. Cache filenames are SHA-256 hashes of a
    stable identity, and their contents contain only normalized DTO fields.
    """

    def __init__(
        self,
        request_json: RequestJson,
        connected: Callable[[], bool],
        cache_path: str | os.PathLike[str],
        get_identity: Callable[[], Any],
    ) -> None:
        self._request_json = request_json
        self._connected = connected
        self._cache_dir = Path(cache_path)
        self._get_identity = get_identity
        self._cache_lock = RLock()

    async def overview(self) -> AccountStatsResult:
        """Load the current account summary without triggering other sections."""
        return await self.summary()

    async def get_summary(self) -> AccountStatsResult:
        return await self.summary()

    async def get_ranked(self) -> AccountStatsResult:
        return await self.ranked()

    async def get_masteries(self, limit: int = 10) -> AccountStatsResult:
        return await self.masteries(limit)

    async def get_challenges(self, limit: int = 3) -> AccountStatsResult:
        return await self.challenges(limit)

    async def get_matches(self, limit: int = MAX_MATCHES) -> AccountStatsResult:
        return await self.matches(limit, 0)

    async def get_match_detail(self, game_id: int | str) -> AccountStatsResult:
        return await self.detail(game_id)

    async def summary(self) -> AccountStatsResult:
        """Load the current summoner's allowlisted profile summary."""
        return await self._simple_section(
            "summary",
            "/lol-summoner/v1/current-summoner",
            _normalize_summary,
        )

    async def ranked(self) -> AccountStatsResult:
        """Load current ranked queue entries from the LCU."""
        return await self._simple_section(
            "ranked",
            "/lol-ranked/v1/current-ranked-stats",
            _normalize_ranked,
        )

    async def masteries(self, limit: int = MAX_MASTERY_ENTRIES) -> AccountStatsResult:
        """Load a bounded mastery list and score, isolating the two requests."""
        count = _validated_limit(limit, MAX_MASTERY_ENTRIES)
        cache_path, cached, cache_error, _identity, is_connected = await self._context()
        old = _cached_section(cached, "masteries", _normalize_masteries_cache)
        old_data = old.data if old else {}
        old_times = old.synced_at if old else {}
        errors: dict[str, str] = {}
        fresh: set[str] = set()
        values: dict[str, Any] = {}
        synced_at: dict[str, str | None] = {}

        if is_connected:
            paths = {
                "champions": "/lol-champion-mastery/v1/local-player/champion-mastery",
                "score": "/lol-champion-mastery/v1/local-player/champion-mastery-score",
            }
            outcomes = await asyncio.gather(
                *(_request(self._request_json, path) for path in paths.values())
            )
            for (field_name, _path), outcome in zip(paths.items(), outcomes):
                normalized = (
                    _normalize_mastery_list(outcome[1], count)
                    if outcome[0] is None and field_name == "champions"
                    else _normalize_mastery_score(outcome[1])
                    if outcome[0] is None
                    else None
                )
                if normalized is not None:
                    values[field_name] = normalized
                    synced_at[field_name] = _now()
                    fresh.add(field_name)
                else:
                    errors[field_name] = outcome[0] or "invalid_payload"
        else:
            errors["request"] = "disconnected"

        cached_fields: set[str] = set()
        for field_name in ("champions", "score"):
            if field_name not in values and field_name in old_data:
                old_value = old_data[field_name]
                values[field_name] = (
                    _normalize_mastery_list(old_value, count)
                    if field_name == "champions"
                    else _normalize_mastery_score(old_value)
                )
                if values[field_name] is not None:
                    cached_fields.add(field_name)
                    synced_at[field_name] = _valid_timestamp(old_times.get(field_name))
        values = {key: value for key, value in values.items() if value is not None}

        if values:
            record = {
                "data": {
                    **old_data,
                    **values,
                },
                "synced_at": {
                    **(old_times if isinstance(old_times, dict) else {}),
                    **{key: stamp for key, stamp in synced_at.items() if stamp},
                },
            }
            if cache_path and fresh:
                self._save_section(cache_path, "masteries", record)
            data = {
                "champions": values.get("champions", old_data.get("champions", [])),
                "score": values.get("score", old_data.get("score")),
            }
            source = _result_source(fresh, cached_fields)
            last_synced = _latest_timestamp(synced_at.values())
        else:
            data = None
            source = "unavailable"
            last_synced = None
        if cache_error:
            errors["cache"] = cache_error
        return AccountStatsResult(
            data,
            source,
            bool(cached_fields),
            last_synced,
            errors,
        )

    async def challenges(self, limit: int = MAX_CHALLENGE_ENTRIES) -> AccountStatsResult:
        """Load local-player challenge progress and category summaries."""
        count = _validated_limit(limit, MAX_CHALLENGE_ENTRIES)
        cache_path, cached, cache_error, _identity, is_connected = await self._context()
        old = _cached_section(cached, "challenges", _normalize_challenges_cache)
        old_data = old.data if old else {}
        old_times = old.synced_at if old else {}
        errors: dict[str, str] = {}
        fresh: set[str] = set()
        values: dict[str, Any] = {}
        synced_at: dict[str, str | None] = {}

        if is_connected:
            paths = {
                "challenges": "/lol-challenges/v1/challenges/local-player",
                "categories": "/lol-challenges/v1/challenges/category-data",
            }
            outcomes = await asyncio.gather(
                *(_request(self._request_json, path) for path in paths.values())
            )
            for (field_name, _path), outcome in zip(paths.items(), outcomes):
                normalizer = (
                    (lambda payload: _normalize_challenges(payload, MAX_CHALLENGE_ENTRIES))
                    if field_name == "challenges"
                    else _normalize_categories
                )
                normalized = normalizer(outcome[1]) if outcome[0] is None else None
                if normalized is not None:
                    values[field_name] = normalized
                    synced_at[field_name] = _now()
                    fresh.add(field_name)
                else:
                    errors[field_name] = outcome[0] or "invalid_payload"
        else:
            errors["request"] = "disconnected"

        cached_fields: set[str] = set()
        for field_name in ("challenges", "categories"):
            if field_name not in values and field_name in old_data:
                normalizer = (
                    (lambda payload: _normalize_challenges(payload, MAX_CHALLENGE_ENTRIES))
                    if field_name == "challenges"
                    else _normalize_categories
                )
                values[field_name] = normalizer(old_data[field_name])
                if values[field_name] is not None:
                    cached_fields.add(field_name)
                    synced_at[field_name] = _valid_timestamp(old_times.get(field_name))
        values = {key: value for key, value in values.items() if value is not None}

        if values:
            record = {
                "data": {**old_data, **values},
                "synced_at": {
                    **(old_times if isinstance(old_times, dict) else {}),
                    **{key: stamp for key, stamp in synced_at.items() if stamp},
                },
            }
            if cache_path and fresh:
                self._save_section(cache_path, "challenges", record)
            challenge_data = values.get("challenges", old_data.get("challenges"))
            if not isinstance(challenge_data, dict):
                challenge_data = {"challenges": []}
            data = {
                "challenges": challenge_data,
                "categories": values.get("categories", old_data.get("categories", [])),
            }
            data["challenges"] = {
                **challenge_data,
                "challenges": challenge_data.get("challenges", [])[:count],
            }
            data["challenges"] = {
                **data["challenges"],
                "challenges": data["challenges"].get("challenges", [])[:count],
            }
            source = _result_source(fresh, cached_fields)
            last_synced = _latest_timestamp(synced_at.values())
        else:
            data = None
            source = "unavailable"
            last_synced = None
        if cache_error:
            errors["cache"] = cache_error
        return AccountStatsResult(data, source, bool(cached_fields), last_synced, errors)

    async def matches(
        self,
        limit: int = MAX_MATCHES,
        offset: int = 0,
    ) -> AccountStatsResult:
        """Load one bounded page of matches. End index is inclusive."""
        count = _validated_limit(limit, MAX_MATCHES)
        start = _validated_offset(offset, count)
        cache_path, cached, cache_error, identity, is_connected = await self._context()
        old = _cached_section(cached, "matches", _normalize_matches_cache)
        old_data = old.data if old else None
        errors: dict[str, str] = {}

        if is_connected:
            path = (
                "/lol-match-history/v1/products/lol/current-summoner/matches"
                f"?begIndex={start}&endIndex={start + count - 1}"
            )
            error, payload = await _request(self._request_json, path)
            normalized = _normalize_matches(payload, count, start, identity) if error is None else None
            if normalized is not None:
                synced_at = _now()
                if cache_path:
                    self._save_section(
                        cache_path,
                        "matches",
                        {"data": normalized, "synced_at": synced_at},
                    )
                return AccountStatsResult(normalized, "lcu", False, synced_at)
            errors["matches"] = error or "invalid_payload"
        else:
            errors["matches"] = "disconnected"

        if cache_error:
            errors["cache"] = cache_error
        if old_data and int(old_data.get("offset", -1)) == start:
            old_data["matches"] = old_data["matches"][:count]
            return AccountStatsResult(
                old_data,
                "cache",
                True,
                _valid_timestamp(old.synced_at),
                errors,
            )
        return AccountStatsResult(None, "unavailable", False, None, errors)

    async def detail(self, game_id: int | str) -> AccountStatsResult:
        """Fetch one match detail on demand."""
        valid_game_id = _validated_game_id(game_id)
        cache_path, cached, cache_error, _identity, is_connected = await self._context()
        details = cached.get("details", {}) if isinstance(cached, dict) else {}
        cached_detail = _cached_detail(details, valid_game_id)
        errors: dict[str, str] = {}

        if is_connected:
            path = f"/lol-match-history/v1/games/{valid_game_id}"
            error, payload = await _request(self._request_json, path)
            normalized = _normalize_detail(payload, valid_game_id) if error is None else None
            if normalized is not None:
                synced_at = _now()
                if cache_path:
                    self._save_detail(cache_path, valid_game_id, normalized, synced_at)
                return AccountStatsResult(normalized, "lcu", False, synced_at)
            errors["detail"] = error or "invalid_payload"
        else:
            errors["detail"] = "disconnected"

        if cache_error:
            errors["cache"] = cache_error
        if cached_detail:
            return AccountStatsResult(
                cached_detail.data,
                "cache",
                True,
                _valid_timestamp(cached_detail.synced_at),
                errors,
            )
        return AccountStatsResult(None, "unavailable", False, None, errors)

    async def timeline(self, game_id: int | str) -> AccountStatsResult:
        """Fetch one bounded, normalized match timeline only when requested."""
        valid_game_id = _validated_game_id(game_id)
        _cache_path, _cached, cache_error, _identity, is_connected = await self._context()
        if not is_connected:
            errors = {"timeline": "disconnected"}
            if cache_error:
                errors["cache"] = cache_error
            return AccountStatsResult(None, "unavailable", False, None, errors)

        path = f"/lol-match-history/v1/game-timelines/{valid_game_id}"
        error, payload = await _request(self._request_json, path)
        normalized = _normalize_timeline(payload, valid_game_id) if error is None else None
        if normalized is None:
            return AccountStatsResult(
                None,
                "unavailable",
                False,
                None,
                {"timeline": error or "invalid_payload"},
            )
        return AccountStatsResult(normalized, "lcu", False, _now())

    async def _simple_section(
        self,
        name: str,
        path: str,
        normalizer: Callable[[Any], dict[str, Any] | None],
    ) -> AccountStatsResult:
        cache_path, cached, cache_error, _identity, is_connected = await self._context()
        old = _cached_section(cached, name, normalizer)
        errors: dict[str, str] = {}
        if is_connected:
            error, payload = await _request(self._request_json, path)
            normalized = normalizer(payload) if error is None else None
            if normalized is not None:
                synced_at = _now()
                if cache_path:
                    self._save_section(
                        cache_path,
                        name,
                        {"data": normalized, "synced_at": synced_at},
                    )
                return AccountStatsResult(normalized, "lcu", False, synced_at)
            errors[name] = error or "invalid_payload"
        else:
            errors[name] = "disconnected"

        if cache_error:
            errors["cache"] = cache_error
        if old:
            return AccountStatsResult(
                old.data,
                "cache",
                True,
                _valid_timestamp(old.synced_at),
                errors,
            )
        return AccountStatsResult(None, "unavailable", False, None, errors)

    async def _context(self) -> tuple[Path | None, dict[str, Any], str | None, _Identity, bool]:
        identity = await _read_identity(self._get_identity)
        try:
            is_connected = bool(self._connected())
        except Exception:  # noqa: BLE001 - the injected runtime is an isolation boundary
            is_connected = False
        if identity.cache_key:
            self._remember_identity(identity.cache_key)
        elif not is_connected:
            cache_key = self._read_last_identity_key()
            if cache_key:
                identity = _Identity(cache_key, None, None)
        cache_path = (
            self._cache_dir / f"account-{identity.cache_key}.json"
            if identity.cache_key
            else None
        )
        cached, cache_error = self._read_cache(cache_path) if cache_path else ({}, None)
        return cache_path, cached, cache_error, identity, is_connected

    def _remember_identity(self, cache_key: str) -> None:
        if not re.fullmatch(r"[a-f0-9]{64}", cache_key):
            return
        self._write_atomic(self._cache_dir / "last-account.json", {"cache_key": cache_key})

    def _read_last_identity_key(self) -> str | None:
        pointer = self._cache_dir / "last-account.json"
        try:
            if pointer.stat().st_size > 256:
                return None
            document = json.loads(pointer.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        cache_key = document.get("cache_key") if isinstance(document, dict) else None
        return cache_key if isinstance(cache_key, str) and re.fullmatch(r"[a-f0-9]{64}", cache_key) else None

    def _write_atomic(self, path: Path, document: dict[str, str]) -> None:
        encoded = json.dumps(document, separators=(",", ":"))
        with self._cache_lock:
            temporary_path: str | None = None
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=path.parent,
                    prefix=f".{path.stem}-",
                    suffix=".tmp",
                    delete=False,
                ) as temporary_file:
                    temporary_path = temporary_file.name
                    temporary_file.write(encoded)
                    temporary_file.flush()
                    os.fsync(temporary_file.fileno())
                os.replace(temporary_path, path)
                temporary_path = None
            except OSError:
                return
            finally:
                if temporary_path:
                    try:
                        os.unlink(temporary_path)
                    except OSError:
                        pass

    def _read_cache(self, path: Path) -> tuple[dict[str, Any], str | None]:
        with self._cache_lock:
            try:
                if not path.is_file():
                    return {}, None
                if path.stat().st_size > MAX_CACHE_BYTES:
                    return {}, "cache_corrupt"
                document = json.loads(path.read_text(encoding="utf-8"))
                if (
                    not isinstance(document, dict)
                    or type(document.get("version")) is not int
                    or document.get("version") != _CACHE_VERSION
                    or not isinstance(document.get("sections", {}), dict)
                    or not isinstance(document.get("details", {}), dict)
                ):
                    return {}, "cache_corrupt"
                sections = _sanitize_cache_sections(document["sections"])
                details = _sanitize_cache_details(document["details"])
                return {"sections": sections, "details": details}, None
            except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
                return {}, "cache_corrupt"

    def _save_section(
        self,
        path: Path,
        name: str,
        section: dict[str, Any],
    ) -> None:
        with self._cache_lock:
            root, _ = self._read_cache(path)
            sections = dict(root.get("sections", {}))
            sections[name] = section
            self._save_root(path, {**root, "sections": sections})

    def _save_detail(
        self,
        path: Path,
        game_id: int,
        data: dict[str, Any],
        synced_at: str,
    ) -> None:
        with self._cache_lock:
            root, _ = self._read_cache(path)
            details = dict(root.get("details", {}))
            details[str(game_id)] = {"data": data, "synced_at": synced_at}
            details = dict(list(details.items())[-MAX_CACHE_DETAILS:])
            self._save_root(path, {**root, "details": details})

    def _save_root(self, path: Path, root: dict[str, Any]) -> None:
        document = {
            "version": _CACHE_VERSION,
            "sections": root.get("sections", {}),
            "details": root.get("details", {}),
        }
        try:
            encoded = json.dumps(document, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            if len(encoded.encode("utf-8")) > MAX_CACHE_BYTES:
                return
            with self._cache_lock:
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary_path: str | None = None
                try:
                    with tempfile.NamedTemporaryFile(
                        mode="w",
                        encoding="utf-8",
                        dir=path.parent,
                        prefix=f".{path.stem}-",
                        suffix=".tmp",
                        delete=False,
                    ) as temporary_file:
                        temporary_path = temporary_file.name
                        temporary_file.write(encoded)
                        temporary_file.flush()
                        os.fsync(temporary_file.fileno())
                    os.replace(temporary_path, path)
                    temporary_path = None
                finally:
                    if temporary_path:
                        try:
                            os.unlink(temporary_path)
                        except OSError:
                            pass
        except (OSError, TypeError, ValueError):
            return


async def _read_identity(get_identity: Callable[[], Any]) -> _Identity:
    try:
        value = get_identity()
        if inspect.isawaitable(value):
            value = await value
    except Exception:  # noqa: BLE001 - injected identity failures must not escape
        value = None
    puuid = _safe_text(_field(value, "puuid", "PUUID"), 128)
    riot_id = _safe_text(_field(value, "riot_id", "riotId", "display_name", "displayName"), 128)
    region = _safe_text(_field(value, "region", "platform_id", "platformId"), 32)
    summoner_id = _safe_id(_field(value, "summoner_id", "summonerId", "id"))
    stable = puuid or (f"{region.lower()}|{riot_id.casefold()}" if riot_id else None)
    stable = stable or (f"{region.lower()}|{summoner_id}" if summoner_id else None)
    key = hashlib.sha256(stable.encode("utf-8")).hexdigest() if stable else None
    return _Identity(key, puuid, summoner_id)


async def _request(
    request_json: RequestJson,
    path: str,
) -> tuple[str | None, Any]:
    try:
        response = await request_json(path)
    except Exception:  # noqa: BLE001 - never expose injected request exception details
        return "request_error", None
    if not isinstance(response, LcuResponse):
        return "invalid_response", None
    if not response.ok:
        if response.error in _ERROR_CODES:
            return response.error, None
        status = response.status_code
        return (f"http_{status}" if isinstance(status, int) and 400 <= status < 600 else "request_error"), None
    return None, response.payload


def _normalize_summary(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    data: dict[str, Any] = {}
    _put_int(data, "level", _field(payload, "summonerLevel", "summoner_level", "level"), 0, 10000)
    _put_int(data, "profile_icon_id", _field(payload, "profileIconId", "profile_icon_id"), 0, 1000000)
    _put_int(data, "xp_since_last_level", _field(payload, "xpSinceLastLevel", "xp_since_last_level"), 0, 100000000)
    _put_int(data, "xp_until_next_level", _field(payload, "xpUntilNextLevel", "xp_until_next_level"), 0, 100000000)
    if not data:
        return None
    return data


def _normalize_ranked(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    queue_map = _field(payload, "queueMap", "queue_map")
    queue_values: list[tuple[str, Any]] = []
    if isinstance(queue_map, Mapping):
        queue_values.extend((str(key), value) for key, value in queue_map.items())
    queues = _field(payload, "queues")
    if isinstance(queues, list):
        queue_values.extend(("", item) for item in queues)
    highest = _field(payload, "highestRankedEntry", "highest_ranked_entry")
    if not queue_values and isinstance(highest, Mapping):
        queue_values.append(("", highest))
    if queue_map is None and queues is None and highest is None:
        return None

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for queue_name, entry in queue_values:
        if not isinstance(entry, Mapping):
            continue
        queue = _safe_text(_field(entry, "queueType", "queue_type") or queue_name, 40)
        if not queue or not re.fullmatch(r"[A-Za-z0-9_]+", queue) or queue in seen:
            continue
        tier = _safe_text(_field(entry, "tier"), 24)
        division = _safe_text(_field(entry, "division"), 8)
        if tier and not re.fullmatch(r"[A-Za-z ]+", tier):
            continue
        if division and not re.fullmatch(r"[A-Za-z0-9]+", division):
            division = ""
        item: dict[str, Any] = {"queue_type": queue}
        if tier:
            item["tier"] = tier.upper()
        if division:
            item["division"] = division.upper()
        _put_int(item, "league_points", _field(entry, "leaguePoints", "league_points"), 0, 1000000)
        _put_int(item, "wins", _field(entry, "wins"), 0, 100000000)
        _put_int(item, "losses", _field(entry, "losses"), 0, 100000000)
        normalized.append(item)
        seen.add(queue)
        if len(normalized) >= 10:
            break
    return {"queues": normalized}


def _normalize_mastery_list(payload: Any, limit: int) -> list[dict[str, Any]] | None:
    rows = payload
    if isinstance(payload, Mapping):
        rows = _field(payload, "masteries", "championMasteries", "champion_masteries")
    if not isinstance(rows, list):
        return None
    normalized: list[dict[str, Any]] = []
    seen: set[int] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        champion_id = _bounded_int(_field(row, "championId", "champion_id"), 1, 10000)
        if champion_id is None or champion_id in seen:
            continue
        item: dict[str, Any] = {"champion_id": champion_id}
        _put_int(item, "level", _field(row, "championLevel", "champion_level", "level"), 0, 10)
        _put_int(item, "points", _field(row, "championPoints", "champion_points", "points"), 0, 2**63 - 1)
        _put_int(item, "last_play_time", _field(row, "lastPlayTime", "last_play_time"), 0, 2**63 - 1)
        _put_bool(item, "chest_granted", _field(row, "chestGranted", "chest_granted"))
        normalized.append(item)
        seen.add(champion_id)
        if len(normalized) >= limit:
            break
    return normalized


def _normalize_mastery_score(payload: Any) -> int | None:
    if isinstance(payload, Mapping):
        payload = _field(payload, "score", "championMasteryScore", "champion_mastery_score")
    return _bounded_int(payload, 0, 2**63 - 1)


def _normalize_challenges(payload: Any, limit: int) -> dict[str, Any] | None:
    if isinstance(payload, list):
        rows, total = payload, None
    elif isinstance(payload, Mapping):
        rows = _field(payload, "challenges", "playerChallenges")
        total = _field(payload, "totalPoints", "total_points")
    else:
        return None
    if not isinstance(rows, list):
        return None
    total_value = _bounded_int(total, 0, 2**63 - 1)
    if isinstance(total, Mapping):
        total_value = _bounded_int(_field(total, "current", "total", "value"), 0, 2**63 - 1)
    result: dict[str, Any] = {
        "challenges": _normalize_challenge_rows(rows, limit),
    }
    if total_value is not None:
        result["total_points"] = total_value
    return result


def _normalize_challenge_rows(rows: list[Any], limit: int) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[int] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        challenge_id = _bounded_int(_field(row, "challengeId", "challenge_id", "id"), 0, 2**31 - 1)
        if challenge_id is None or challenge_id in seen:
            continue
        item: dict[str, Any] = {"id": challenge_id}
        _put_int(item, "value", _field(row, "value", "currentValue"), 0, 2**63 - 1)
        _put_float(item, "percentile", _field(row, "percentile"), 0.0, 100.0)
        level = _safe_text(_field(row, "level", "tier"), 32)
        category = _safe_text(_field(row, "category", "categoryName"), 32)
        if level:
            item["level"] = level.upper()
        if category:
            item["category"] = category.upper()
        normalized.append(item)
        seen.add(challenge_id)
        if len(normalized) >= limit:
            break
    return normalized


def _normalize_categories(payload: Any) -> list[dict[str, Any]] | None:
    rows: list[tuple[str, Any]] = []
    if isinstance(payload, list):
        rows = [("", item) for item in payload]
    elif isinstance(payload, Mapping):
        categories = _field(payload, "categories", "categoryData", "category_data")
        if isinstance(categories, list):
            rows = [("", item) for item in categories]
        elif isinstance(categories, Mapping):
            rows = [(str(key), item) for key, item in categories.items()]
        else:
            rows = [(str(key), value) for key, value in payload.items()]
    else:
        return None
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for fallback, row in rows:
        if not isinstance(row, Mapping):
            continue
        name = _safe_text(_field(row, "category", "name", "categoryName") or fallback, 32)
        if not name or not re.fullmatch(r"[A-Za-z0-9_ -]+", name):
            continue
        name = name.upper()
        if name in seen:
            continue
        item: dict[str, Any] = {"category": name}
        _put_int(item, "current", _field(row, "current", "currentPoints", "value"), 0, 2**63 - 1)
        _put_int(item, "max", _field(row, "max", "maxPoints"), 0, 2**63 - 1)
        _put_float(item, "percentile", _field(row, "percentile"), 0.0, 100.0)
        normalized.append(item)
        seen.add(name)
        if len(normalized) >= 20:
            break
    return normalized


def _normalize_matches(
    payload: Any,
    limit: int,
    offset: int,
    identity: _Identity,
) -> dict[str, Any] | None:
    rows = payload
    if isinstance(payload, Mapping):
        games = _field(payload, "games")
        if isinstance(games, Mapping):
            rows = _field(games, "games", "matches")
        elif isinstance(games, list):
            rows = games
        else:
            rows = _field(payload, "matches")
    if not isinstance(rows, list):
        return None
    normalized = []
    for game in rows:
        if not isinstance(game, Mapping):
            continue
        game_id = _bounded_int(_field(game, "gameId", "game_id"), 1, 2**64 - 1)
        if game_id is None:
            continue
        item: dict[str, Any] = {"game_id": str(game_id)}
        _put_int(item, "creation", _field(game, "gameCreation", "game_creation", "creation"), 0, 2**63 - 1)
        _put_int(item, "duration", _field(game, "gameDuration", "game_duration", "duration"), 0, 100000)
        _put_int(item, "queue_id", _field(game, "queueId", "queue_id"), 0, 100000)
        player = _find_local_participant(game, identity)
        if player is not None:
            _put_int(item, "champion_id", _field(player, "championId", "champion_id"), 1, 10000)
            stats = _field(player, "stats")
            if isinstance(stats, Mapping):
                _put_bool(item, "win", _field(stats, "win"))
                _put_int(item, "kills", _field(stats, "kills"), 0, 100000)
                _put_int(item, "deaths", _field(stats, "deaths"), 0, 100000)
                _put_int(item, "assists", _field(stats, "assists"), 0, 100000)
        else:
            _put_int(item, "champion_id", _field(game, "champion_id"), 1, 10000)
            _put_bool(item, "win", _field(game, "win"))
            for stat in ("kills", "deaths", "assists"):
                _put_int(item, stat, _field(game, stat), 0, 100000)
        normalized.append(item)
        if len(normalized) >= limit:
            break
    game_container = _field(payload, "games") if isinstance(payload, Mapping) else None
    count_value = _field(payload, "gameCount") if isinstance(payload, Mapping) else None
    if count_value is None and isinstance(game_container, Mapping):
        count_value = _field(game_container, "gameCount")
    count = _bounded_int(count_value, 0, 2**31 - 1)
    return {"offset": offset, "matches": normalized, "total": count}


def _normalize_detail(payload: Any, requested_id: int) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    game_id = _bounded_int(_field(payload, "gameId", "game_id"), 1, 2**64 - 1)
    if game_id is None or game_id != requested_id:
        return None
    result: dict[str, Any] = {"game_id": str(game_id)}
    _put_int(result, "creation", _field(payload, "gameCreation", "game_creation", "creation"), 0, 2**63 - 1)
    _put_int(result, "duration", _field(payload, "gameDuration", "game_duration", "duration"), 0, 100000)
    _put_int(result, "queue_id", _field(payload, "queueId", "queue_id"), 0, 100000)
    participants = _field(payload, "participants")
    if isinstance(participants, list):
        result["participants"] = _normalize_participants(participants)
    else:
        result["participants"] = []
    return result


def _normalize_timeline(payload: Any, requested_id: int) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    game_id = _bounded_int(_field(payload, "gameId", "game_id"), 1, 2**64 - 1)
    frames = _field(payload, "frames")
    if game_id != requested_id or not isinstance(frames, list):
        return None
    allowed_types = {
        "CHAMPION_KILL",
        "ELITE_MONSTER_KILL",
        "BUILDING_KILL",
        "TURRET_PLATE_DESTROYED",
        "ITEM_PURCHASED",
        "ITEM_SOLD",
        "ITEM_DESTROYED",
        "SKILL_LEVEL_UP",
        "GAME_END",
    }
    events: list[dict[str, Any]] = []
    for frame in frames[:150]:
        frame_time = _bounded_int(_field(frame, "timestamp"), 0, 2**63 - 1)
        frame_events = _field(frame, "events")
        if frame_time is None or not isinstance(frame_events, list):
            continue
        for event in frame_events:
            event_type = _field(event, "type")
            timestamp = _bounded_int(_field(event, "timestamp"), 0, 2**63 - 1)
            if (
                not isinstance(event, Mapping)
                or not isinstance(event_type, str)
                or event_type not in allowed_types
                or timestamp is None
            ):
                continue
            normalized = {"type": event_type, "timestamp": timestamp}
            for output, *aliases in (
                ("participant_id", "participantId"),
                ("killer_id", "killerId"),
                ("victim_id", "victimId"),
                ("item_id", "itemId"),
                ("skill_slot", "skillSlot"),
            ):
                _put_int(normalized, output, _field(event, *aliases), 0, 100000)
            assists = _field(event, "assistingParticipantIds")
            if isinstance(assists, list):
                normalized["assisting_participant_ids"] = [
                    value
                    for item in assists[:10]
                    if (value := _bounded_int(item, 0, 100000)) is not None
                ]
            events.append(normalized)
            if len(events) >= MAX_TIMELINE_EVENTS:
                break
        if len(events) >= MAX_TIMELINE_EVENTS:
            break
    return {"game_id": str(game_id), "events": events}


def _normalize_participants(rows: list[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows[:10]:
        if not isinstance(row, Mapping):
            continue
        participant: dict[str, Any] = {}
        _put_int(participant, "champion_id", _field(row, "championId", "champion_id"), 1, 10000)
        _put_int(participant, "team_id", _field(row, "teamId", "team_id"), 0, 100000)
        stats = _field(row, "stats")
        if not isinstance(stats, Mapping):
            stats = row
        if isinstance(stats, Mapping):
            _put_bool(participant, "win", _field(stats, "win"))
            for key in ("kills", "deaths", "assists", "goldEarned", "totalMinionsKilled", "visionScore"):
                output_key = re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower()
                _put_int(participant, output_key, _field(stats, key, output_key), 0, 100000000)
            raw_items = _field(stats, "items")
            participant["items"] = (
                [
                    item_id
                    for item in raw_items[:7]
                    if (item_id := _bounded_int(item, 1, 100000)) is not None
                ]
                if isinstance(raw_items, list)
                else [
                    item_id
                    for slot in range(7)
                    if (item_id := _bounded_int(_field(stats, f"item{slot}"), 1, 100000)) is not None
                ]
            )
        if participant:
            result.append(participant)
    return result


def _find_local_participant(game: Mapping[str, Any], identity: _Identity) -> Mapping[str, Any] | None:
    participants = _field(game, "participants")
    if not isinstance(participants, list):
        return None
    identities = _field(game, "participantIdentities", "participant_identities")
    identity_by_participant: dict[Any, Any] = {}
    if isinstance(identities, list):
        identity_by_participant = {
            _field(row, "participantId", "participant_id"): _field(row, "player")
            for row in identities
            if isinstance(row, Mapping)
        }
    for participant in participants:
        if not isinstance(participant, Mapping):
            continue
        if _field(participant, "isCurrentPlayer", "is_current_player") is True:
            return participant
        participant_id = _field(participant, "participantId", "participant_id")
        player = identity_by_participant.get(participant_id)
        if not isinstance(player, Mapping):
            continue
        if identity.puuid and _field(player, "puuid", "PUUID") == identity.puuid:
            return participant
        player_summoner_id = _safe_id(_field(player, "summonerId", "summoner_id"))
        if identity.summoner_id and player_summoner_id == identity.summoner_id:
            return participant
    return None


def _cached_section(
    root: dict[str, Any],
    name: str,
    normalizer: Callable[[Any], Any],
) -> _CachedSection | None:
    section = root.get("sections", {}).get(name)
    if not isinstance(section, Mapping):
        return None
    data = normalizer(section.get("data"))
    timestamp = section.get("synced_at")
    if data is None:
        return None
    if isinstance(timestamp, Mapping) and isinstance(data, Mapping):
        field_times = {
            key: valid_time
            for key in data
            if (valid_time := _valid_timestamp(timestamp.get(key))) is not None
        }
        data = {key: value for key, value in data.items() if key in field_times}
        if not data:
            return None
        return _CachedSection(data, field_times)
    timestamp = _valid_timestamp(timestamp)
    if timestamp is None:
        return None
    return _CachedSection(data, timestamp)


def _normalize_masteries_cache(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    champions = _normalize_mastery_list(_field(payload, "champions"), MAX_MASTERY_ENTRIES)
    score = _normalize_mastery_score(_field(payload, "score"))
    if champions is None and score is None:
        return None
    result: dict[str, Any] = {}
    if champions is not None:
        result["champions"] = champions
    if score is not None:
        result["score"] = score
    return result


def _normalize_challenges_cache(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    challenges = _normalize_challenges(_field(payload, "challenges"), MAX_CHALLENGE_ENTRIES)
    categories = _normalize_categories(_field(payload, "categories"))
    if challenges is None and categories is None:
        return None
    result: dict[str, Any] = {}
    if challenges is not None:
        result["challenges"] = challenges
    if categories is not None:
        result["categories"] = categories
    return result


def _normalize_matches_cache(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    offset = _bounded_int(_field(payload, "offset"), 0, MAX_MATCH_OFFSET)
    if offset is None:
        return None
    normalized = _normalize_matches(
        {"matches": _field(payload, "matches"), "gameCount": _field(payload, "total")},
        MAX_MATCHES,
        offset,
        _Identity(None, None, None),
    )
    return normalized


def _cached_detail(details: Any, game_id: int) -> _CachedSection | None:
    section = details.get(str(game_id)) if isinstance(details, Mapping) else None
    if not isinstance(section, Mapping):
        return None
    data = _normalize_detail(section.get("data"), game_id)
    timestamp = section.get("synced_at")
    if data is None or _valid_timestamp(timestamp) is None:
        return None
    return _CachedSection(data, timestamp)


def _sanitize_cache_sections(raw_sections: Mapping[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    simple_normalizers = {
        "summary": _normalize_summary,
        "ranked": _normalize_ranked,
        "matches": _normalize_matches_cache,
    }
    partial_normalizers = {
        "masteries": _normalize_masteries_cache,
        "challenges": _normalize_challenges_cache,
    }
    for name, section in raw_sections.items():
        if not isinstance(section, Mapping):
            continue
        data = section.get("data")
        timestamp = section.get("synced_at")
        normalizer = simple_normalizers.get(name)
        if normalizer is not None:
            normalized = normalizer(data)
            valid_time = _valid_timestamp(timestamp)
            if normalized is not None and valid_time:
                sanitized[name] = {"data": normalized, "synced_at": valid_time}
            continue

        normalizer = partial_normalizers.get(name)
        if normalizer is None or not isinstance(timestamp, Mapping):
            continue
        normalized = normalizer(data)
        if normalized is None:
            continue
        field_times = {
            key: valid_time
            for key in normalized
            if (valid_time := _valid_timestamp(timestamp.get(key))) is not None
        }
        normalized = {key: value for key, value in normalized.items() if key in field_times}
        if normalized:
            sanitized[name] = {"data": normalized, "synced_at": field_times}
    return sanitized


def _sanitize_cache_details(raw_details: Mapping[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for raw_game_id, section in list(raw_details.items())[-MAX_CACHE_DETAILS:]:
        if not isinstance(raw_game_id, str) or not raw_game_id.isdecimal() or not isinstance(section, Mapping):
            continue
        try:
            game_id = _validated_game_id(raw_game_id)
        except ValueError:
            continue
        data = _normalize_detail(section.get("data"), game_id)
        timestamp = _valid_timestamp(section.get("synced_at"))
        if data is not None and timestamp:
            sanitized[str(game_id)] = {"data": data, "synced_at": timestamp}
    return sanitized


def _field(value: Any, *keys: str) -> Any:
    if isinstance(value, Mapping):
        for key in keys:
            if key in value:
                return value[key]
    else:
        for key in keys:
            if hasattr(value, key):
                return getattr(value, key)
    return None


def _put_int(target: dict[str, Any], key: str, value: Any, minimum: int, maximum: int) -> None:
    number = _bounded_int(value, minimum, maximum)
    if number is not None:
        target[key] = number


def _bounded_int(value: Any, minimum: int, maximum: int) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and value.isdecimal():
        value = int(value)
    if not isinstance(value, int) or not minimum <= value <= maximum:
        return None
    return value


def _put_bool(target: dict[str, Any], key: str, value: Any) -> None:
    if isinstance(value, bool):
        target[key] = value


def _put_float(target: dict[str, Any], key: str, value: Any, minimum: float, maximum: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return
    number = float(value)
    if math.isfinite(number) and minimum <= number <= maximum:
        target[key] = number


def _safe_text(value: Any, maximum: int) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(char for char in value.strip()[:maximum] if char.isprintable())


def _safe_id(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    text = str(value)
    return text if text.isdecimal() and len(text) <= 32 else None


def _validated_limit(value: Any, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ValueError(f"limit must be between 1 and {maximum}")
    return value


def _validated_offset(value: Any, limit: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_MATCH_OFFSET:
        raise ValueError(f"offset must be between 0 and {MAX_MATCH_OFFSET}")
    if value + limit > 2**32:
        raise ValueError("match page exceeds the LCU index range")
    return value


def _validated_game_id(value: Any) -> int:
    if isinstance(value, bool):
        raise TypeError("game_id must be an unsigned 64-bit integer")
    if isinstance(value, str):
        if not value.isdecimal():
            raise ValueError("game_id must be an unsigned 64-bit integer")
        if len(value) > 20:
            raise ValueError("game_id must be an unsigned 64-bit integer")
        value = int(value)
    if not isinstance(value, int):
        raise TypeError("game_id must be an unsigned 64-bit integer")
    if not 1 <= value <= 2**64 - 1:
        raise ValueError("game_id must be an unsigned 64-bit integer")
    return value


def _valid_timestamp(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


def _latest_timestamp(values: Any) -> str | None:
    valid = [_valid_timestamp(value) for value in values]
    valid = [value for value in valid if value]
    return max(valid) if valid else None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _result_source(fresh: set[str], cached: set[str]) -> _SOURCE:
    if fresh and cached:
        return "mixed"
    if fresh:
        return "lcu"
    if cached:
        return "cache"
    return "unavailable"
