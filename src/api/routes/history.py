"""Local action history routes."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request

from ...services.history import clear_history_entries, get_history_entries
from ..schemas import HistoryResponse

router = APIRouter(prefix="/api")


@router.get("/history", response_model=HistoryResponse)
async def history(request: Request, limit: int = 100) -> HistoryResponse:
    del request
    bounded_limit = max(0, min(limit, 250))
    entries = await asyncio.to_thread(get_history_entries, bounded_limit)
    return {"items": entries, "count": len(entries)}


@router.delete("/history")
async def clear_history(request: Request) -> dict[str, bool]:
    del request
    await asyncio.to_thread(clear_history_entries)
    return {"ok": True}
