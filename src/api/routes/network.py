"""Local Internet availability routes used by the startup gate."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request

from ..schemas import NetworkStatusResponse

router = APIRouter(prefix="/api/network", tags=["network"])


def _network_status(request: Request):
    return request.app.state.context.network_status


@router.get("/status", response_model=NetworkStatusResponse)
async def network_status(request: Request) -> NetworkStatusResponse:
    """Return the cached status, refreshing it when its TTL has expired."""
    service = _network_status(request)
    return await asyncio.to_thread(service.check)


@router.post("/check", response_model=NetworkStatusResponse)
async def check_network(request: Request) -> NetworkStatusResponse:
    """Force one bounded asset-origin probe for the retry button."""
    service = _network_status(request)
    return await asyncio.to_thread(service.check, force=True)


__all__ = ["router"]
