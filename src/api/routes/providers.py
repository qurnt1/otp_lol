"""Local HTTP control surface for native provider windows."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/desktop/providers", tags=["desktop-providers"])
_KINDS = frozenset({"stats", "live"})


def _manager(request: Request) -> Any:
    manager = getattr(request.app.state.context, "provider_window_manager", None)
    if manager is None:
        raise HTTPException(status_code=503, detail="desktop_provider_manager_unavailable")
    return manager


def _public_status(manager: Any) -> dict[str, dict[str, Any]]:
    status = manager.status()
    return {
        kind: {
            key: values.get(key)
            for key in (
                "state",
                "provider_id",
                "last_error",
                "last_action",
                "last_transition_at",
                "load_started_at",
                "last_load_duration_ms",
            )
        }
        for kind, values in status.items()
    }


def _check_kind(kind: str) -> None:
    if kind not in _KINDS:
        raise HTTPException(status_code=404, detail="unknown_provider_kind")


def _public_result(kind: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": kind,
        "ok": bool(result.get("ok")),
        "reason": result.get("reason"),
        "state": result.get("state", "not_created"),
        "provider_id": result.get("provider_id"),
    }


@router.get("/status")
def provider_status(request: Request) -> dict[str, Any]:
    manager = _manager(request)
    return {"windows": _public_status(manager)}


@router.post("/{kind}/open")
def open_provider(request: Request, kind: str) -> dict[str, Any]:
    _check_kind(kind)
    manager = _manager(request)
    result = manager.request_open(kind)
    return _public_result(kind, result)


@router.post("/{kind}/show")
def show_provider(request: Request, kind: str) -> dict[str, Any]:
    _check_kind(kind)
    manager = _manager(request)
    result = manager.request_show(kind)
    return _public_result(kind, result)


@router.post("/{kind}/reload")
def reload_provider(request: Request, kind: str) -> dict[str, Any]:
    _check_kind(kind)
    manager = _manager(request)
    result = manager.request_reload(kind)
    return _public_result(kind, result)


@router.post("/{kind}/hide")
def hide_provider(request: Request, kind: str) -> dict[str, Any]:
    _check_kind(kind)
    manager = _manager(request)
    return _public_result(kind, manager.request_hide(kind))
