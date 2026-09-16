"""Settings and preset routes."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from ...config import FIRST_LAUNCH_PARAMS, PICK_SLOT_ORDER
from ...domain.hotkeys import validate_hotkey_pair
from ...services.profile_config import build_effective_profile_config
from ..schemas import PresetSlotPatch, PresetsResponse, SettingsImport, SettingsPatch, SettingsResponse

router = APIRouter(prefix="/api")


def _context(request: Request) -> Any:
    return request.app.state.context


def _validate_settings_candidate(context: Any, values: dict[str, Any]) -> None:
    candidate = context.get_params()
    candidate.update(values)
    if "hotkey_toggle_window" in values or "hotkey_open_site" in values:
        try:
            validate_hotkey_pair(candidate["hotkey_toggle_window"], candidate["hotkey_open_site"])
        except (KeyError, TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
    if candidate.get("presets_enabled") and not any(
        str(candidate.get(f"selected_pick_{index}") or "").strip()
        for index in range(1, 4)
    ):
        raise HTTPException(status_code=422, detail="Configure au moins un champion avant d'activer les presets.")
    _validate_preset_invariants(candidate)


def _validate_preset_invariants(candidate: dict[str, Any]) -> None:
    slots = candidate.get("pick_slots") if isinstance(candidate.get("pick_slots"), dict) else {}
    picks = [
        str(candidate.get(f"selected_pick_{index}") or "").strip().casefold()
        for index in range(1, 4)
    ]
    ban = str(candidate.get("selected_ban") or "").strip().casefold()
    for slot_key in PICK_SLOT_ORDER:
        slot = slots.get(slot_key) if isinstance(slots.get(slot_key), dict) else {}
        spell_1 = str(slot.get("spell_1") or "").strip()
        spell_2 = str(slot.get("spell_2") or "").strip()
        if spell_1 and spell_2 and spell_1 == spell_2 and spell_1 != "(None)":
            raise HTTPException(status_code=422, detail=f"Les deux sorts de {slot_key} doivent être différents.")
    if ban and ban in {pick for pick in picks if pick}:
        raise HTTPException(status_code=422, detail="Le champion à bannir doit être différent des picks.")


@router.get("/settings", response_model=SettingsResponse)
def read_settings(request: Request) -> SettingsResponse:
    return _context(request).get_params()


@router.patch("/settings", response_model=SettingsResponse)
async def patch_settings(request: Request, payload: SettingsPatch) -> SettingsResponse:
    context = _context(request)
    values = payload.model_dump(exclude_unset=True)
    _validate_settings_candidate(context, values)
    try:
        updated = await asyncio.to_thread(context.persist_parameters, values)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if updated is None:
        raise HTTPException(status_code=500, detail="Unable to save settings")
    context.broker.publish("settings_updated", {"keys": list(values)})
    return updated


@router.get("/settings/export")
def export_settings(request: Request) -> JSONResponse:
    """Return a portable JSON copy without exposing credentials or runtime objects."""
    return JSONResponse(
        content=_context(request).get_params(),
        headers={"Content-Disposition": 'attachment; filename="otp-lol-settings.json"'},
    )


@router.post("/settings/import", response_model=SettingsResponse)
async def import_settings(request: Request, payload: SettingsImport) -> SettingsResponse:
    context = _context(request)
    values = payload.model_dump(exclude_unset=True)
    candidate = context.get_params()
    candidate.update(values)
    _validate_settings_candidate(context, values)
    try:
        updated = await asyncio.to_thread(context.persist_parameters, values)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if updated is None:
        raise HTTPException(status_code=500, detail="Unable to save settings")
    context.broker.publish("settings_updated", {"keys": list(values)})
    return updated


@router.post("/settings/reset", response_model=SettingsResponse)
async def reset_settings(request: Request) -> SettingsResponse:
    context = _context(request)
    updated = await asyncio.to_thread(context.persist_parameters, FIRST_LAUNCH_PARAMS)
    if updated is None:
        raise HTTPException(status_code=500, detail="Unable to reset settings")
    context.broker.publish("settings_updated", {"keys": list(FIRST_LAUNCH_PARAMS)})
    return updated


@router.get("/presets", response_model=PresetsResponse)
def read_presets(request: Request) -> PresetsResponse:
    context = _context(request)
    params = context.get_params()
    effective = build_effective_profile_config(params)
    return {
        "presets_enabled": effective["presets_enabled"],
        "selected_ban": effective["selected_ban"],
        "slots": effective["pick_slots"],
    }


@router.put("/presets/{slot_key}", response_model=PresetsResponse)
async def patch_preset(request: Request, slot_key: str, payload: PresetSlotPatch) -> PresetsResponse:
    if slot_key not in PICK_SLOT_ORDER:
        raise HTTPException(status_code=404, detail="Unknown preset slot")

    context = _context(request)
    values = payload.model_dump(exclude_unset=True)
    champion = values.pop("champion", None)
    candidate = context.get_params()
    candidate.setdefault("pick_slots", {}).setdefault(slot_key, {}).update(values)
    if champion is not None:
        candidate[f"selected_pick_{PICK_SLOT_ORDER.index(slot_key) + 1}"] = champion
    _validate_preset_invariants(candidate)
    updated = await asyncio.to_thread(
        context.persist_preset_slot,
        slot_key,
        values,
        selected_champion=champion,
    )
    if updated is None:
        raise HTTPException(status_code=500, detail="Unable to save settings")
    context.broker.publish("settings_updated", {"keys": ["pick_slots", slot_key]})
    return read_presets(request)
