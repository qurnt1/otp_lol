"""Bounded, redacted diagnostics for the local League Client runtime."""

from __future__ import annotations

import asyncio
import json
import math
import re
from collections import deque
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import RLock
from time import monotonic
from types import MappingProxyType
from typing import Any

REQUEST_BUFFER_SIZE = 200
EVENT_BUFFER_SIZE = 500
ERROR_BUFFER_SIZE = 100
MAX_PAYLOAD_BYTES = 4 * 1024

_MAX_TEXT_CHARS = 512
_MAX_PAYLOAD_DEPTH = 6
_MAX_PAYLOAD_NODES = 128
_MAX_CONTAINER_ITEMS = 32
_MAX_PAYLOAD_STRING_BYTES = 1024
_MAX_ENDPOINT_IDS_PER_RUN = 16
_NORMALIZED_ERRORS = frozenset(
    {
        "disconnected",
        "timeout",
        "request_error",
        "http_error",
        "invalid_response",
        "response_too_large",
        "invalid_json",
        "request_failed",
    }
)


@dataclass(frozen=True, slots=True)
class EndpointCheck:
    """A fixed, read-only LCU check; callers select it by ID, never by path."""

    id: str
    label: str
    path: str
    method: str = "GET"


ENDPOINT_CHECKS: Mapping[str, EndpointCheck] = MappingProxyType(
    {
        check.id: check
        for check in (
            EndpointCheck("gameflow_phase", "Game phase", "/lol-gameflow/v1/gameflow-phase"),
            EndpointCheck("current_summoner", "Current summoner", "/lol-summoner/v1/current-summoner"),
            EndpointCheck("game_version", "League game version", "/lol-patch/v1/game-version"),
            EndpointCheck(
                "champion_summary",
                "Champion catalogue",
                "/lol-game-data/assets/v1/champion-summary.json",
            ),
            EndpointCheck("ranked_stats", "Ranked statistics", "/lol-ranked/v1/current-ranked-stats"),
            EndpointCheck(
                "masteries",
                "Champion masteries",
                "/lol-champion-mastery/v1/local-player/champion-mastery",
            ),
            EndpointCheck(
                "match_history",
                "Match history",
                "/lol-match-history/v1/products/lol/current-summoner/matches",
            ),
        )
    }
)

JsonRequester = Callable[[str], Awaitable[Any]]

_SENSITIVE_KEY_PARTS = (
    "auth",
    "authorization",
    "cookie",
    "displayname",
    "password",
    "passwd",
    "playername",
    "token",
    "secret",
    "credential",
    "puuid",
    "riotid",
    "summonerid",
    "summonername",
    "accountid",
    "gamename",
    "tagline",
    "apikey",
)
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b([a-z0-9_-]*(?:authorization|auth|cookie|password|passwd|token|secret|credential|puuid|riot[_ -]?id|api[_ -]?key)[a-z0-9_-]*)\b"
    r"\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_COOKIE_ASSIGNMENT = re.compile(r"(?i)\b([a-z0-9_-]*cookie)\b\s*[:=]\s*[^\r\n]*")
_BEARER_OR_BASIC = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]+")
_RIOT_ID_TEXT = re.compile(r"(?<![\w])[\w .'-]{1,64}#[\w-]{1,16}(?![\w])")
_OPAQUE_ID = re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{32,}(?![A-Za-z0-9_-])")
_WINDOWS_PATH = re.compile(r"(?i)(?<![\w])(?:[A-Z]:\\|\\\\[^\\\s]+\\)[^\r\n\"<>|]*")
_UNIX_USER_PATH = re.compile(
    r"(?<![\w])(?:/home/|/Users/|/root/|/tmp/|/private/|/var/folders/|/mnt/)[^\s\"'<>]*"
)
_FILE_URL = re.compile(r"(?i)file://[^\s\"'<>]+")
_ENV_USER_PATH = re.compile(r"(?i)(?:%APPDATA%|%LOCALAPPDATA%|%USERPROFILE%|~)[\\/][^\s\"'<>]*")
_SAFE_RIOT_ID = re.compile(r"^.{1,64}#[A-Za-z0-9_-]{1,16}$")


class DiagnosticsService:
    """Collect serializable diagnostic copies without retaining raw LCU payloads."""

    def __init__(
        self,
        request_json: JsonRequester | None = None,
        *,
        get_riot_id: Callable[[], str | None] | None = None,
    ) -> None:
        self._request_json = request_json
        self._get_riot_id = get_riot_id
        self._requests: deque[dict[str, Any]] = deque(maxlen=REQUEST_BUFFER_SIZE)
        self._events: deque[dict[str, Any]] = deque(maxlen=EVENT_BUFFER_SIZE)
        self._errors: deque[dict[str, Any]] = deque(maxlen=ERROR_BUFFER_SIZE)
        self._endpoint_results: dict[str, dict[str, Any]] = {}
        self._requests_lock = RLock()
        self._events_lock = RLock()
        self._errors_lock = RLock()
        self._endpoint_results_lock = RLock()
        self._run_lock = asyncio.Lock()

    def record_request(self, record: Mapping[str, Any]) -> None:
        """Record the safe metadata emitted by ``LcuClient.request_observer``."""
        if not isinstance(record, Mapping):
            return
        safe_record = {
            "timestamp": _safe_timestamp(record.get("timestamp")),
            "method": _safe_method(record.get("method")),
            "path": _redact_text(_safe_text(record.get("path"), limit=_MAX_TEXT_CHARS)),
            "status": _safe_status(record.get("status")),
            "duration_ms": _safe_duration(record.get("duration_ms")),
            "success": record.get("success") is True,
            "error": _safe_error(record.get("error")) if record.get("error") is not None else None,
        }
        with self._requests_lock:
            self._requests.append(safe_record)

    def record_event(self, topic: Any, event_type: Any, payload: Any) -> None:
        """Store a bounded, redacted event summary and JSON-safe payload preview."""
        safe_topic = _redact_text(_safe_text(topic, limit=160))
        if safe_topic == "otp-lol/summoner_update":
            safe_payload, truncated, redacted = "[REDACTED]", False, True
        else:
            sensitive_fields = (
                frozenset({"name"})
                if safe_topic.rstrip("/").endswith("/lol-chat/v1/me")
                else frozenset()
            )
            safe_payload, truncated, redacted = _bounded_payload(
                payload, sensitive_fields=sensitive_fields
            )
        event = {
            "timestamp": _now(),
            "topic": safe_topic,
            "event_type": _redact_text(_safe_text(event_type, limit=80)),
            "summary": _payload_summary(safe_payload),
            "payload": safe_payload,
            "payload_truncated": truncated,
            "payload_redacted": redacted,
        }
        with self._events_lock:
            self._events.append(event)

    def record_error(
        self,
        source: Any,
        error: Any,
        *,
        method: Any = None,
        path: Any = None,
        status: Any = None,
    ) -> None:
        """Record a sanitized error code; exception messages are never retained."""
        entry = {
            "timestamp": _now(),
            "source": _redact_text(_safe_text(source, limit=80)),
            "error": _safe_error(error),
            "method": _safe_method(method) if method is not None else None,
            "path": _redact_text(_safe_text(path, limit=_MAX_TEXT_CHARS)) if path is not None else None,
            "status": _safe_status(status),
        }
        with self._errors_lock:
            self._errors.append(entry)

    def snapshot(self) -> dict[str, Any]:
        """Return detached JSON-serializable copies of all bounded buffers."""
        with self._requests_lock:
            requests = list(self._requests)
        with self._events_lock:
            events = list(self._events)
        with self._errors_lock:
            errors = list(self._errors)
        with self._endpoint_results_lock:
            endpoint_results = [
                dict(self._endpoint_results[endpoint_id])
                for endpoint_id in ENDPOINT_CHECKS
                if endpoint_id in self._endpoint_results
            ]
        return _json_copy(
            {
                "requests": requests,
                "events": events,
                "errors": errors,
                "endpoint_checks": [asdict(check) for check in ENDPOINT_CHECKS.values()],
                "endpoint_results": endpoint_results,
            }
        )

    def export(self, include_riot_id: bool = False) -> dict[str, Any]:
        """Return a redacted report, with Riot ID only after explicit opt-in."""
        report = self.snapshot()
        report["generated_at"] = _now()
        if include_riot_id is True and self._get_riot_id is not None:
            try:
                riot_id = self._get_riot_id()
            except Exception:  # noqa: BLE001 - an optional identity provider must not break a redacted export.
                riot_id = None
            if isinstance(riot_id, str):
                safe_riot_id = _optional_riot_id(riot_id)
                if safe_riot_id:
                    report["riot_id"] = safe_riot_id
        return _json_copy(report)

    async def run(self, endpoint_ids: Iterable[str] | None = None) -> list[dict[str, Any]]:
        """Run selected fixed GET checks through the injected LCU runtime facade."""
        checks = _select_checks(endpoint_ids)
        if self._request_json is None:
            raise RuntimeError("Diagnostics GET requester is not configured")

        results: list[dict[str, Any]] = []
        async with self._run_lock:
            for check in checks:
                started = monotonic()
                try:
                    response = await self._request_json(check.path)
                except Exception as error:  # noqa: BLE001 - isolate failures so remaining checks still run.
                    duration_ms = round((monotonic() - started) * 1000, 1)
                    error_code = _safe_error(error)
                    self.record_error(
                        f"endpoint:{check.id}",
                        error,
                        method="GET",
                        path=check.path,
                    )
                    result = _check_result(check, None, duration_ms, False, error_code, "")
                    results.append(result)
                    continue

                status = _safe_status(getattr(response, "status_code", None))
                duration_ms = _safe_duration(getattr(response, "duration_ms", 0.0))
                error_value = getattr(response, "error", None)
                success = bool(getattr(response, "ok", False))
                error_code = _safe_error(error_value) if error_value is not None else None
                summary = _payload_summary(_bounded_payload(getattr(response, "payload", None))[0])
                if not success:
                    self.record_error(
                        f"endpoint:{check.id}",
                        error_code or "request_failed",
                        method="GET",
                        path=check.path,
                        status=status,
                    )
                result = _check_result(check, status, duration_ms, success, error_code, summary)
                results.append(result)
            if results:
                self._record_endpoint_results(results)
        return _json_copy(results)

    def _record_endpoint_results(self, results: list[dict[str, Any]]) -> None:
        with self._endpoint_results_lock:
            self._endpoint_results.update({result["id"]: result for result in results})


def _select_checks(endpoint_ids: Iterable[str] | None) -> tuple[EndpointCheck, ...]:
    if endpoint_ids is None:
        return tuple(ENDPOINT_CHECKS.values())
    if isinstance(endpoint_ids, (str, bytes)):
        raise TypeError("Select diagnostic checks by endpoint ID")
    selected_ids = []
    try:
        for endpoint_id in endpoint_ids:
            if len(selected_ids) >= _MAX_ENDPOINT_IDS_PER_RUN:
                raise ValueError("Too many diagnostic endpoint IDs")
            selected_ids.append(endpoint_id)
    except TypeError as error:
        raise TypeError("Invalid diagnostic endpoint IDs") from error
    if any(not isinstance(endpoint_id, str) for endpoint_id in selected_ids):
        raise TypeError("Invalid diagnostic endpoint ID")
    unknown = set(selected_ids) - ENDPOINT_CHECKS.keys()
    if unknown:
        raise ValueError("Unknown diagnostic endpoint ID")
    selected = set(selected_ids)
    return tuple(check for endpoint_id, check in ENDPOINT_CHECKS.items() if endpoint_id in selected)


def _check_result(
    check: EndpointCheck,
    status: int | None,
    duration_ms: float,
    success: bool,
    error: str | None,
    summary: str,
) -> dict[str, Any]:
    return {
        "id": check.id,
        "label": check.label,
        "method": "GET",
        "path": check.path,
        "status": status,
        "duration_ms": duration_ms,
        "success": success,
        "error": error,
        "summary": summary,
    }


def _bounded_payload(
    value: Any, *, sensitive_fields: frozenset[str] = frozenset()
) -> tuple[Any, bool, bool]:
    state = {"nodes": 0, "truncated": False, "redacted": False}
    safe_value = _json_safe(
        value, state=state, depth=0, seen=set(), sensitive_fields=sensitive_fields
    )
    try:
        encoded = _encode_json(safe_value)
    except (TypeError, ValueError):
        encoded = b""
    if len(encoded) > MAX_PAYLOAD_BYTES:
        safe_value = {"truncated": True, "shape": _payload_shape(safe_value)}
        state["truncated"] = True
        encoded = _encode_json(safe_value)
        while len(encoded) > MAX_PAYLOAD_BYTES:
            safe_value = {"truncated": True, "shape": "payload omitted"}
            encoded = _encode_json(safe_value)
    return safe_value, bool(state["truncated"]), bool(state["redacted"])


def _json_safe(
    value: Any,
    *,
    state: dict[str, Any],
    depth: int,
    seen: set[int],
    sensitive_fields: frozenset[str],
) -> Any:
    state["nodes"] += 1
    if state["nodes"] > _MAX_PAYLOAD_NODES or depth >= _MAX_PAYLOAD_DEPTH:
        state["truncated"] = True
        return "[truncated]"
    if value is None or isinstance(value, (bool, int)):
        if isinstance(value, int) and not isinstance(value, bool) and value.bit_length() > 63:
            state["redacted"] = True
            return "[REDACTED_ID]"
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        cleaned = _redact_text(value)
        if cleaned != value:
            state["redacted"] = True
        encoded = cleaned.encode("utf-8", errors="replace")
        if len(encoded) > _MAX_PAYLOAD_STRING_BYTES:
            state["truncated"] = True
            cleaned = _truncate_utf8(cleaned, _MAX_PAYLOAD_STRING_BYTES)
        return cleaned
    if isinstance(value, bytes):
        state["redacted"] = True
        return "[binary omitted]"
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in seen:
            state["truncated"] = True
            return "[cycle omitted]"
        seen.add(identity)
        safe_mapping: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= _MAX_CONTAINER_ITEMS or state["nodes"] >= _MAX_PAYLOAD_NODES:
                state["truncated"] = True
                safe_mapping["$truncated"] = True
                break
            if not isinstance(key, str):
                safe_key = "[unsupported-key]"
            else:
                safe_key = _truncate_text(_redact_text(key), 100)
            if _is_sensitive_key(key) or (
                isinstance(key, str) and key.casefold() in sensitive_fields
            ):
                safe_mapping[safe_key] = "[REDACTED]"
                state["redacted"] = True
            else:
                safe_mapping[safe_key] = _json_safe(
                    item,
                    state=state,
                    depth=depth + 1,
                    seen=seen,
                    sensitive_fields=sensitive_fields,
                )
        seen.remove(identity)
        return safe_mapping
    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in seen:
            state["truncated"] = True
            return "[cycle omitted]"
        seen.add(identity)
        safe_items = []
        for index, item in enumerate(value):
            if index >= _MAX_CONTAINER_ITEMS or state["nodes"] >= _MAX_PAYLOAD_NODES:
                state["truncated"] = True
                safe_items.append("[truncated]")
                break
            safe_items.append(
                _json_safe(
                    item,
                    state=state,
                    depth=depth + 1,
                    seen=seen,
                    sensitive_fields=sensitive_fields,
                )
            )
        seen.remove(identity)
        return safe_items
    return "[unsupported]"


def _payload_shape(value: Any) -> str:
    if isinstance(value, Mapping):
        keys = [
            key
            for key in value
            if isinstance(key, str) and not _is_sensitive_key(key) and key != "$truncated"
        ][:12]
        return "object keys: " + ", ".join(keys)
    if isinstance(value, list):
        return f"array with at most {len(value)} entries"
    return type(value).__name__


def _payload_summary(value: Any) -> str:
    if isinstance(value, Mapping):
        details = []
        for key in ("phase", "status", "state", "playerResponse", "queueId", "championId"):
            item = value.get(key)
            if isinstance(item, (str, int, float, bool)) and not isinstance(item, bool):
                details.append(f"{key}={_truncate_text(_redact_text(str(item)), 48)}")
            elif isinstance(item, bool):
                details.append(f"{key}={str(item).lower()}")
        return _truncate_text(", ".join(details) if details else _payload_shape(value), 256)
    if isinstance(value, list):
        return f"array ({len(value)} entries)"
    if value is None:
        return "empty"
    if isinstance(value, (str, int, float, bool)):
        return _truncate_text(_redact_text(str(value)), 256)
    return "payload unavailable"


def _is_sensitive_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _redact_text(value: str, *, allow_riot_id: bool = False) -> str:
    text = _BEARER_OR_BASIC.sub(lambda match: f"{match.group(1)} [REDACTED]", value)
    text = _COOKIE_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    text = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    text = _WINDOWS_PATH.sub("[LOCAL_PATH]", text)
    text = _UNIX_USER_PATH.sub("[LOCAL_PATH]", text)
    text = _FILE_URL.sub("[LOCAL_PATH]", text)
    text = _ENV_USER_PATH.sub("[LOCAL_PATH]", text)
    if not allow_riot_id:
        text = _RIOT_ID_TEXT.sub("[RIOT_ID]", text)
    text = _OPAQUE_ID.sub("[REDACTED_ID]", text)
    return _truncate_text(text, _MAX_TEXT_CHARS)


def _safe_text(value: Any, *, limit: int = _MAX_TEXT_CHARS) -> str:
    return _truncate_text(value, limit) if isinstance(value, str) else ""


def _truncate_text(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: max(0, limit - 14)] + "[truncated]"


def _truncate_utf8(value: str, limit: int) -> str:
    marker = "[truncated]"
    marker_bytes = marker.encode("utf-8")
    prefix = value.encode("utf-8")[: max(0, limit - len(marker_bytes))]
    return prefix.decode("utf-8", errors="ignore") + marker


def _safe_timestamp(value: Any) -> str:
    if isinstance(value, str) and value and len(value) <= 40:
        return _redact_text(value)
    return _now()


def _safe_status(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 999 else None


def _safe_method(value: Any) -> str:
    if isinstance(value, str) and value.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        return value.upper()
    return "UNKNOWN"


def _safe_duration(value: Any) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return round(min(max(float(value), 0.0), 86_400_000.0), 1)
    return 0.0


def _safe_error(error: Any) -> str:
    if isinstance(error, BaseException):
        return _truncate_text(_redact_text(type(error).__name__), 80)
    if isinstance(error, str):
        normalized = error.strip().lower()
        return normalized if normalized in _NORMALIZED_ERRORS else "unknown_error"
    return "unknown_error" if error is None else _truncate_text(_redact_text(type(error).__name__), 80)


def _optional_riot_id(value: str) -> str | None:
    candidate = value.strip()
    if not candidate or len(candidate) > 128 or "\n" in candidate or "\r" in candidate:
        return None
    if not _SAFE_RIOT_ID.fullmatch(candidate):
        return None
    cleaned = _redact_text(candidate, allow_riot_id=True)
    return cleaned if cleaned == candidate else None


def _encode_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _json_copy(value: Any) -> Any:
    return json.loads(_encode_json(value))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")
