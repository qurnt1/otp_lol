"""Settings and preset routes."""

from __future__ import annotations

import asyncio
import copy
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from ...config import (
    FIRST_LAUNCH_PARAMS,
    PICK_SLOT_ORDER,
    STARTER_PRESET_CONFIG,
    build_pick_slot_defaults,
)
from ...domain.hotkeys import validate_hotkey_pair
from ...domain.presets import PRESET_SETTING_KEYS, validate_preset_invariants
from ...services.profile_config import build_effective_profile_config
from ..schemas import (
    PresetSlotPatch,
    PresetsResponse,
    SettingsImport,
    SettingsPatch,
    SettingsResponse,
)

router = APIRouter(prefix="/api")
LOCAL_ACCOUNT_KEYS = ("auto_detected_riot_id", "auto_detected_region", "auto_detected_platform")


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
    try:
        validate_preset_invariants(
            candidate,
            changed_keys=set(values),
            validate_pick_selection=True,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/settings", response_model=SettingsResponse)
def read_settings(request: Request) -> SettingsResponse:
    return _context(request).get_params()


@router.patch("/settings", response_model=SettingsResponse)
async def patch_settings(request: Request, payload: SettingsPatch) -> SettingsResponse:
    context = _context(request)
    values = payload.model_dump(exclude_unset=True)
    _complete_onboarding_for_edit(context, values)
    _validate_settings_candidate(context, values)
    try:
        updated = await asyncio.to_thread(
            context.persist_parameters,
            values,
            validate_pick_selection=True,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if updated is None:
        raise HTTPException(status_code=500, detail="Unable to save settings")
    context.broker.publish("settings_updated", {"keys": list(values)})
    return updated


@router.get("/settings/export")
def export_settings(request: Request) -> JSONResponse:
    """Return a portable JSON copy without exposing credentials or runtime objects."""
    values = _context(request).get_params()
    for key in LOCAL_ACCOUNT_KEYS:
        values.pop(key, None)
    return JSONResponse(
        content=values,
        headers={"Content-Disposition": 'attachment; filename="otp-lol-settings.json"'},
    )


@router.post("/settings/import", response_model=SettingsResponse)
async def import_settings(request: Request, payload: SettingsImport) -> SettingsResponse:
    context = _context(request)
    values = payload.model_dump(exclude_unset=True)
    for key in LOCAL_ACCOUNT_KEYS:
        values.pop(key, None)
    _complete_onboarding_for_edit(context, values)
    candidate = context.get_params()
    candidate.update(values)
    _validate_settings_candidate(context, values)
    try:
        updated = await asyncio.to_thread(
            context.persist_parameters,
            values,
            validate_pick_selection=True,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if updated is None:
        raise HTTPException(status_code=500, detail="Unable to save settings")
    context.broker.publish("settings_updated", {"keys": list(values)})
    return updated


@router.delete("/settings/last-detected-account", response_model=SettingsResponse)
async def clear_last_detected_account(request: Request) -> SettingsResponse:
    context = _context(request)
    values = {key: "" for key in LOCAL_ACCOUNT_KEYS}
    updated = await asyncio.to_thread(context.persist_parameters, values)
    if updated is None:
        raise HTTPException(status_code=500, detail="Unable to forget the last detected account")
    context.broker.publish("account_identity_updated", {"keys": list(values)})
    return updated


@router.post("/settings/reset", response_model=SettingsResponse)
async def reset_settings(request: Request) -> SettingsResponse:
    context = _context(request)
    updated = await asyncio.to_thread(context.persist_parameters, FIRST_LAUNCH_PARAMS)
    if updated is None:
        raise HTTPException(status_code=500, detail="Unable to reset settings")
    context.broker.publish("settings_updated", {"keys": list(FIRST_LAUNCH_PARAMS)})
    return updated


@router.post("/presets/reset", response_model=SettingsResponse)
async def reset_presets(request: Request) -> SettingsResponse:
    """Restore the starter picks and keep all preset automations safely disabled."""
    context = _context(request)
    values = copy.deepcopy(STARTER_PRESET_CONFIG)
    values.update({"presets_enabled": False, "onboarding_completed": False})
    updated = await asyncio.to_thread(context.persist_parameters, values)
    if updated is None:
        raise HTTPException(status_code=500, detail="Unable to restore preset examples")
    context.broker.publish("settings_updated", {"keys": list(values)})
    return updated


@router.post("/presets/clear", response_model=SettingsResponse)
async def clear_presets(request: Request) -> SettingsResponse:
    """Clear preset choices while leaving the rest of the settings untouched."""
    context = _context(request)
    values = {
        "selected_pick_1": "",
        "selected_pick_2": "",
        "selected_pick_3": "",
        "selected_ban": "",
        "pick_slots": build_pick_slot_defaults(),
        "onboarding_completed": True,
    }
    updated = await asyncio.to_thread(context.persist_parameters, values)
    if updated is None:
        raise HTTPException(status_code=500, detail="Unable to clear presets")
    context.broker.publish("settings_updated", {"keys": list(values)})
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
    try:
        validate_preset_invariants(candidate)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    try:
        updated = await asyncio.to_thread(
            context.persist_preset_slot,
            slot_key,
            values,
            selected_champion=champion,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if updated is None:
        raise HTTPException(status_code=500, detail="Unable to save settings")
    context.broker.publish("settings_updated", {"keys": ["pick_slots", slot_key]})
    return read_presets(request)


def _complete_onboarding_for_edit(context: Any, values: dict[str, Any]) -> None:
    """Keep onboarding closed after edits or dismissal, except through reset."""
    if PRESET_SETTING_KEYS.intersection(values) or context.get_params().get("onboarding_completed"):
        values["onboarding_completed"] = True
