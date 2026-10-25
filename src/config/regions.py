"""Shared League platform and provider-region normalization helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .constants import (
    PLATFORM_TO_REGION,
    PLATFORM_TO_REGIONAL_ROUTING,
    REGION_TO_PLATFORM,
)


@dataclass(frozen=True, slots=True)
class RegionIdentity:
    """One validated platform, provider-region, and regional-routing tuple."""

    platform_id: str
    provider_region: str
    regional_routing: str
    source: str


def normalize_platform_id(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()
    if normalized in PLATFORM_TO_REGION:
        return normalized
    return REGION_TO_PLATFORM.get(normalized)


def normalize_provider_region(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()
    if normalized in REGION_TO_PLATFORM:
        return normalized
    platform_id = normalize_platform_id(normalized)
    return PLATFORM_TO_REGION.get(platform_id) if platform_id else None


def platform_to_provider_region(value: Any) -> str | None:
    """Return the provider region for a platform ID or known alias."""
    return normalize_provider_region(value)


def platform_to_regional_routing(value: Any) -> str | None:
    platform_id = normalize_platform_id(value)
    return PLATFORM_TO_REGIONAL_ROUTING.get(platform_id) if platform_id else None


def normalize_region_identity(value: Any, *, source: str) -> RegionIdentity | None:
    platform_id = normalize_platform_id(value)
    if not platform_id:
        return None
    provider_region = PLATFORM_TO_REGION[platform_id]
    regional_routing = PLATFORM_TO_REGIONAL_ROUTING.get(platform_id)
    if not regional_routing:
        return None
    return RegionIdentity(platform_id, provider_region, regional_routing, source)


def _nested_values(payload: Any) -> list[Any]:
    if isinstance(payload, dict):
        values: list[Any] = list(payload.values())
        for key in ("data", "value", "result", "commandLineArgs", "args"):
            if key in payload:
                values.insert(0, payload[key])
        return values
    if isinstance(payload, (list, tuple)):
        return list(payload)
    return []


def _find_value(payload: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if value not in (None, ""):
                return value
        for value in _nested_values(payload):
            found = _find_value(value, keys)
            if found not in (None, ""):
                return found
    elif isinstance(payload, (list, tuple)):
        for value in payload:
            found = _find_value(value, keys)
            if found not in (None, ""):
                return found
    return payload if isinstance(payload, str) else None


def _command_line_region(payload: Any) -> str | None:
    values: list[Any] = [payload]
    while values:
        value = values.pop()
        if isinstance(value, str):
            match = re.search(r"(?:^|\s)--region(?:=|\s+)([A-Za-z0-9_-]+)", value)
            if match:
                return match.group(1)
            match = re.search(r"(?:^|\s)region=([A-Za-z0-9_-]+)", value)
            if match:
                return match.group(1)
        values.extend(_nested_values(value))
    return None


async def _request_json(connection: Any, path: str) -> Any:
    try:
        response = await connection.request("get", path)
    except Exception:  # noqa: BLE001 - endpoint availability varies by LCU version.
        return None
    if not response or getattr(response, "status", 0) != 200:
        return None
    try:
        return await response.json()
    except Exception:  # noqa: BLE001 - malformed endpoint payloads are treated as unavailable.
        return None


async def detect_account_routing(connection: Any) -> RegionIdentity | None:
    """Resolve routing from stable LCU sources, with explicit fallbacks."""
    sources: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
        (
            "platform_config",
            (
                "/lol-platform-config/v1/namespaces/LoginDataPacket/platformId",
                "/lol-platform-config/v1/namespaces/LoginDataPacket",
            ),
            ("platformId", "platform_id"),
        ),
        ("rso_auth", ("/rso-auth/v1/authorization",), ("currentPlatformId", "platformId", "platform_id")),
        (
            "region_locale",
            ("/riotclient/region-locale", "/riotclient/get_region_locale"),
            ("platformId", "platform_id", "region"),
        ),
    )
    for source, paths, keys in sources:
        for path in paths:
            payload = await _request_json(connection, path)
            value = _find_value(payload, keys)
            identity = normalize_region_identity(value, source=source)
            if identity:
                return identity

    payload = await _request_json(connection, "/riotclient/command-line-args")
    return normalize_region_identity(_command_line_region(payload), source="command_line_args")


__all__ = [
    "RegionIdentity",
    "detect_account_routing",
    "normalize_platform_id",
    "normalize_provider_region",
    "normalize_region_identity",
    "platform_to_provider_region",
    "platform_to_regional_routing",
]
