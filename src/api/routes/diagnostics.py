"""Safe diagnostics endpoints for the local League Client connection."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StrictStr

from ...config import CURRENT_VERSION
from ...desktop.window import get_webview2_runtime_version
from .game_data import resolved_game_data_status

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


class DiagnosticRunRequest(BaseModel):
    endpoint_ids: list[StrictStr] | None = Field(default=None, max_length=16)


@router.get("")
async def read_diagnostics(request: Request) -> dict[str, Any]:
    context = request.app.state.context
    runtime = context.runtime.snapshot(context.get_params()).as_dict()
    identity = context.runtime.get_account_identity(context.get_params())
    runtime.pop("riot_id", None)
    return {
        "runtime": runtime,
        "account_identity": identity,
        "hotkeys": context.get_hotkey_status(),
        "game_data": await resolved_game_data_status(context),
        **context.diagnostics.snapshot(),
    }


@router.post("/run")
async def run_diagnostics(
    request: Request,
    payload: DiagnosticRunRequest,
) -> dict[str, Any]:
    try:
        results = await request.app.state.context.diagnostics.run(payload.endpoint_ids)
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"results": results}


@router.get("/export")
async def export_diagnostics(request: Request, include_riot_id: bool = False) -> JSONResponse:
    context = request.app.state.context
    report = context.diagnostics.export(include_riot_id=include_riot_id)
    runtime = context.runtime.snapshot(context.get_params()).as_dict()
    identity = context.runtime.get_account_identity(context.get_params())
    game_data = await resolved_game_data_status(context)
    report.update(
        {
            "app_version": CURRENT_VERSION,
            "webview2_version": get_webview2_runtime_version(),
            "league_connected": runtime["connected"],
            "account_identity": identity,
            "hotkeys": context.get_hotkey_status(),
            "league_version": game_data["game_version"],
            "game_data": game_data,
        }
    )
    if not include_riot_id:
        report.pop("riot_id", None)
        if isinstance(report.get("account_identity"), dict):
            report["account_identity"]["riot_id"] = None
    return JSONResponse(
        content=report,
        headers={"Content-Disposition": 'attachment; filename="otp-lol-diagnostics.json"'},
    )
