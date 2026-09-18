"""Bounded, read-only requests over the existing local LCU connection."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from time import monotonic
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit

MAX_JSON_RESPONSE_BYTES = 32 * 1024 * 1024
MAX_BINARY_RESPONSE_BYTES = 8 * 1024 * 1024
_ALLOWED_PREFIXES = ("/lol-", "/riotclient/")
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LcuResponse:
    """Safe result metadata and decoded payload from one LCU GET."""

    status_code: int | None
    duration_ms: float
    payload: Any = None
    content_type: str = ""
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status_code is not None and 200 <= self.status_code < 300


class LcuClient:
    """Use the active lcu-driver connection without handling its credentials."""

    def __init__(
        self,
        get_connection: Callable[[], Any],
        *,
        timeout_s: float = 5.0,
        request_observer: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self._get_connection = get_connection
        self._timeout_s = timeout_s
        self._request_observer = request_observer

    async def get_json(self, path: str) -> LcuResponse:
        return await self._get(path, binary=False)

    async def get_bytes(self, path: str) -> LcuResponse:
        return await self._get(path, binary=True)

    async def _get(self, path: str, *, binary: bool) -> LcuResponse:
        _validate_lcu_path(path)
        started = monotonic()
        connection = self._get_connection()
        if connection is None:
            response = LcuResponse(None, _elapsed_ms(started), error="disconnected")
            self._observe(path, response)
            return response

        try:
            response = await asyncio.wait_for(
                self._read_response(connection, path, binary=binary),
                timeout=self._timeout_s,
            )
        except asyncio.TimeoutError:
            response = LcuResponse(None, _elapsed_ms(started), error="timeout")
        except Exception as error:  # noqa: BLE001 - client transport errors have library-specific types.
            _LOGGER.debug("LCU request failed: %s", type(error).__name__)
            response = LcuResponse(None, _elapsed_ms(started), error="request_error")

        response = LcuResponse(
            status_code=response.status_code,
            duration_ms=_elapsed_ms(started),
            payload=response.payload,
            content_type=response.content_type,
            error=response.error,
        )
        self._observe(path, response)
        return response

    async def _read_response(self, connection: Any, path: str, *, binary: bool) -> LcuResponse:
        upstream = await connection.request("get", path)
        status = getattr(upstream, "status", None)
        if not isinstance(status, int):
            return LcuResponse(None, 0.0, error="invalid_response")
        headers = getattr(upstream, "headers", {})
        content_type = str(headers.get("Content-Type", headers.get("content-type", "")))
        if not 200 <= status < 300:
            return LcuResponse(status, 0.0, content_type=content_type, error="http_error")

        max_bytes = MAX_BINARY_RESPONSE_BYTES if binary else MAX_JSON_RESPONSE_BYTES
        body = await _read_limited(upstream, max_bytes)
        if body is None:
            return LcuResponse(status, 0.0, content_type=content_type, error="response_too_large")
        if binary:
            return LcuResponse(status, 0.0, payload=body, content_type=content_type)
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return LcuResponse(status, 0.0, content_type=content_type, error="invalid_json")
        return LcuResponse(status, 0.0, payload=payload, content_type=content_type)

    def _observe(self, path: str, response: LcuResponse) -> None:
        if self._request_observer is None:
            return
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "method": "GET",
            "path": _diagnostic_path(path),
            "status": response.status_code,
            "duration_ms": response.duration_ms,
            "success": response.ok,
            "error": response.error,
        }
        try:
            self._request_observer(record)
        except Exception as error:  # noqa: BLE001 - an observer must never break the live request.
            _LOGGER.debug("LCU diagnostic observer failed: %s", type(error).__name__)


async def _read_limited(response: Any, limit: int) -> bytes | None:
    content = getattr(response, "content", None)
    iter_chunked = getattr(content, "iter_chunked", None)
    if iter_chunked is not None:
        chunks = []
        total = 0
        async for chunk in iter_chunked(64 * 1024):
            total += len(chunk)
            if total > limit:
                return None
            chunks.append(chunk)
        return b"".join(chunks)

    body = await response.read()
    return body if len(body) <= limit else None


def _validate_lcu_path(path: str) -> None:
    if not isinstance(path, str):
        raise TypeError("Only local LCU endpoint paths are allowed")
    if len(path) > 4096:
        raise ValueError("Only local LCU endpoint paths are allowed")
    try:
        parts = urlsplit(path)
    except ValueError as error:
        raise ValueError("Only local LCU endpoint paths are allowed") from error
    decoded_path = _decode_path_layers(parts.path)
    if decoded_path is None:
        raise ValueError("Only local LCU endpoint paths are allowed")
    segments = decoded_path.split("/")
    query = parse_qsl(parts.query, strict_parsing=True) if parts.query else []
    valid_match_query = (
        decoded_path == "/lol-match-history/v1/products/lol/current-summoner/matches"
        and len(query) == 2
        and {key for key, _ in query} == {"begIndex", "endIndex"}
        and all(value.isdecimal() for _, value in query)
        and int(dict(query)["begIndex"]) <= int(dict(query)["endIndex"])
        and int(dict(query)["endIndex"]) - int(dict(query)["begIndex"]) < 100
    )
    if (
        parts.scheme
        or parts.netloc
        or (parts.query and not valid_match_query)
        or parts.fragment
        or "?" in decoded_path
        or "#" in decoded_path
        or "\\" in decoded_path
        or "//" in decoded_path
        or any(segment in {".", ".."} for segment in segments)
        or not any(decoded_path.startswith(prefix) for prefix in _ALLOWED_PREFIXES)
    ):
        raise ValueError("Only local LCU endpoint paths are allowed")


def _decode_path_layers(path: str) -> str | None:
    decoded = path
    for _ in range(16):
        unquoted = unquote(decoded)
        if unquoted == decoded:
            return decoded
        decoded = unquoted
    return None if re.search(r"%[0-9a-fA-F]{2}", decoded) else decoded


def _diagnostic_path(path: str) -> str:
    """Hide account/game identifiers from bounded diagnostic request history."""
    return re.sub(r"(?<=/)\w{20,}(?=/|$)", "{id}", urlsplit(path).path)


def _elapsed_ms(started: float) -> float:
    return round((monotonic() - started) * 1000, 1)
