"""Validated request and response payloads for the desktop frontend."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from ..config.constants import CONFIG_SCHEMA_VERSION, SUMMONER_SPELL_MAP
from ..domain.hotkeys import normalize_hotkey
from ..services.urls import is_valid_detected_account

SkinMode = Literal["none", "fixed", "random"]
Theme = Literal["darkly", "flatly"]
Region = Literal[
    "euw", "eune", "na", "kr", "jp", "br", "lan", "las", "oce", "tr", "ru", "sea"
]
StatsProvider = Literal["opgg", "deeplol", "dpm", "leagueofgraphs"]
HotkeyProvider = Literal["porofessor", "deeplol", "dpm", "opgg"]


class SkinReference(BaseModel):
    skin_id: int = Field(ge=0)
    skin_name: str
    skin_num: int = Field(ge=0)


class PresetSlotPatch(BaseModel):
    """Partial update for one of the three champion preset slots."""

    model_config = ConfigDict(extra="forbid")

    champion: str = Field(default=None)
    spell_1: str = Field(default=None)
    spell_2: str = Field(default=None)
    skin_mode: SkinMode = Field(default=None)
    skin_id: int = Field(default=None, ge=0)
    skin_name: str = Field(default=None)
    skin_num: int = Field(default=None, ge=0)
    random_skin_id: int = Field(default=None, ge=0)
    random_skin_name: str = Field(default=None)
    random_skin_num: int = Field(default=None, ge=0)
    random_skin_pool: list[SkinReference] = Field(default=None)
    rune_page_id: int = Field(default=None, ge=0)
    rune_page_name: str = Field(default=None)
    rune_auto_apply: bool = Field(default=None)
    rune_keystone_id: int = Field(default=None, ge=0)
    rune_keystone_path: str = Field(default=None)
    rune_sub_style_icon_path: str = Field(default=None)

    @field_validator("spell_1", "spell_2")
    @classmethod
    def validate_spell(cls, value: str) -> str:
        if value == "" or value in SUMMONER_SPELL_MAP:
            return value
        raise ValueError("Unknown summoner spell")


class PresetSlot(BaseModel):
    """Complete preset slot returned to the frontend."""

    champion: str
    spell_1: str
    spell_2: str
    skin_mode: SkinMode
    skin_id: int
    skin_name: str
    skin_num: int
    random_skin_id: int
    random_skin_name: str
    random_skin_num: int
    random_skin_pool: list[SkinReference]
    rune_page_id: int
    rune_page_name: str
    rune_auto_apply: bool
    rune_keystone_id: int
    rune_keystone_path: str
    rune_sub_style_icon_path: str


class PresetSlotSettings(BaseModel):
    """Persisted slot settings returned without the separate champion pick."""

    spell_1: str
    spell_2: str
    skin_mode: SkinMode
    skin_id: int
    skin_name: str
    skin_num: int
    random_skin_id: int
    random_skin_name: str
    random_skin_num: int
    random_skin_pool: list[SkinReference]
    rune_page_id: int
    rune_page_name: str
    rune_auto_apply: bool
    rune_keystone_id: int
    rune_keystone_path: str
    rune_sub_style_icon_path: str


class SettingsPatch(BaseModel):
    """Allow only settings that the frontend is allowed to edit."""

    model_config = ConfigDict(extra="forbid")

    auto_accept_enabled: bool = Field(default=None)
    auto_pick_enabled: bool = Field(default=None)
    auto_ban_enabled: bool = Field(default=None)
    auto_summoners_enabled: bool = Field(default=None)
    presets_enabled: bool = Field(default=None)
    onboarding_completed: bool = Field(default=None)
    selected_pick_1: str = Field(default=None)
    selected_pick_2: str = Field(default=None)
    selected_pick_3: str = Field(default=None)
    selected_ban: str = Field(default=None)
    pick_slots: dict[str, PresetSlotPatch] = Field(default=None)
    theme: Theme = Field(default=None)
    summoner_name_auto_detect: bool = Field(default=None)
    manual_summoner_name: str = Field(default=None)
    manual_region: Region = Field(default=None)
    preferred_stats_site: StatsProvider = Field(default=None)
    preferred_hotkey_site: HotkeyProvider = Field(default=None)
    hotkey_toggle_window: str = Field(default=None)
    hotkey_open_site: str = Field(default=None)
    auto_play_again_enabled: bool = Field(default=None)
    auto_hide_on_connect: bool = Field(default=None)
    close_app_on_lol_exit: bool = Field(default=None)
    ignored_update_version: str = Field(default=None)
    skin_automation_enabled: bool = Field(default=None)
    window_x: int = Field(default=None)
    window_y: int = Field(default=None)
    window_width: int = Field(default=None, ge=800, le=7680)
    window_height: int = Field(default=None, ge=540, le=4320)
    window_maximized: bool = Field(default=None)

    @field_validator("hotkey_toggle_window", "hotkey_open_site")
    @classmethod
    def validate_hotkey(cls, value: str) -> str:
        return normalize_hotkey(value)

    @field_validator("manual_summoner_name")
    @classmethod
    def validate_riot_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            return ""
        if len(normalized) > 64 or normalized.count("#") != 1:
            raise ValueError("Riot ID must use the GameName#Tag format")
        game_name, tag = (part.strip() for part in normalized.split("#", 1))
        if not game_name or not tag:
            raise ValueError("Riot ID must use the GameName#Tag format")
        return f"{game_name}#{tag}"

    @model_validator(mode="after")
    def validate_hotkey_pair(self) -> SettingsPatch:
        if (
            self.hotkey_toggle_window is not None
            and self.hotkey_open_site is not None
            and self.hotkey_toggle_window == self.hotkey_open_site
        ):
            raise ValueError("Global hotkeys must be different")
        return self


class HealthResponse(BaseModel):
    ok: bool
    service: str
    version: str
    lcu_connected: bool


class NetworkStatusResponse(BaseModel):
    state: Literal["checking", "offline", "online"]
    online: bool
    checked_at: float | None = None
    last_success_at: float | None = None
    reason: str | None = None
    source: str


class RuntimeSnapshotResponse(BaseModel):
    version: str
    connected: bool
    phase: str
    riot_id: str | None
    region: str
    queue_id: int
    assigned_position: str
    presets_enabled: bool
    auto_accept_enabled: bool
    auto_pick_enabled: bool
    auto_ban_enabled: bool
    auto_summoners_enabled: bool


class MetadataResponse(BaseModel):
    version: str
    loaded: bool
    champion_count: int
    data_dragon_version: str | None = None


class UpdateMetadata(BaseModel):
    version: str
    highlights: str = ""
    release_url: str = ""
    asset_name: str = ""
    asset_url: str = ""
    checksum_name: str = ""
    checksum_url: str = ""


class UpdatesResponse(BaseModel):
    available: bool
    update: UpdateMetadata | None


class AccountIdentityResponse(BaseModel):
    riot_id: str | None
    region: str | None
    platform_id: str | None
    regional_routing: str | None
    source: Literal["connected", "saved", "manual", "unavailable"]
    routing_source: str | None = None
    connected: bool


class StatsLinkResponse(BaseModel):
    available: bool
    site: str
    url: str | None
    homepage_url: str
    riot_id: str | None
    region: str | None
    account_source: Literal["connected", "saved", "manual", "unavailable"]


class LiveLinkResponse(StatsLinkResponse):
    """Validated provider link for live-game statistics."""


class SettingsResponse(BaseModel):
    config_version: str
    config_schema_version: int
    auto_accept_enabled: bool
    auto_pick_enabled: bool
    auto_ban_enabled: bool
    auto_summoners_enabled: bool
    presets_enabled: bool
    onboarding_completed: bool
    selected_pick_1: str
    selected_pick_2: str
    selected_pick_3: str
    selected_ban: str
    pick_slots: dict[str, PresetSlotSettings]
    theme: Theme
    summoner_name_auto_detect: bool
    manual_summoner_name: str
    manual_region: str
    auto_detected_riot_id: str
    auto_detected_region: str
    auto_detected_platform: str
    preferred_stats_site: str
    preferred_hotkey_site: str
    hotkey_toggle_window: str
    hotkey_open_site: str
    auto_play_again_enabled: bool
    auto_hide_on_connect: bool
    close_app_on_lol_exit: bool
    ignored_update_version: str
    skin_automation_enabled: bool
    window_x: int
    window_y: int
    window_width: int
    window_height: int
    window_maximized: bool

    @computed_field
    @property
    def auto_detected_account_valid(self) -> bool:
        return is_valid_detected_account(
            self.auto_detected_riot_id,
            self.auto_detected_region,
            self.auto_detected_platform,
        )


class PresetsResponse(BaseModel):
    presets_enabled: bool
    selected_ban: str
    slots: dict[str, PresetSlot]


class SettingsImport(SettingsPatch):
    """Typed current-format settings payload accepted by the import endpoint."""

    config_version: str | None = None
    config_schema_version: int = Field(ge=0)
    pick_slots: dict[str, PresetSlotPatch] | None = None
    auto_detected_riot_id: str | None = None
    auto_detected_region: str | None = None
    auto_detected_platform: str | None = None

    @field_validator("config_schema_version")
    @classmethod
    def validate_current_schema(cls, value: int) -> int:
        if value != CONFIG_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported settings schema (found={value}, expected={CONFIG_SCHEMA_VERSION})"
            )
        return value


class PresetPreview(BaseModel):
    """Metadata-only preview assembled from already loaded local catalog data."""

    champion_id: int | None = None
    champion_name: str = ""
    champion_icon_url: str | None = None
    champion_splash_url: str | None = None
    spell_1_url: str | None = None
    spell_2_url: str | None = None
    skin_name: str | None = None
    skin_preview_url: str | None = None


class BootstrapResponse(BaseModel):
    """Local-only payload required for the first interactive dashboard paint."""

    runtime: RuntimeSnapshotResponse
    settings: SettingsResponse
    presets: PresetsResponse
    preset_previews: dict[str, PresetPreview] = Field(default_factory=dict)
    ban_preview: PresetPreview | None = None


class ProviderOption(BaseModel):
    id: str
    label: str
    logo_url: str


class RegionOption(BaseModel):
    id: str
    label: str


class ProviderCatalog(BaseModel):
    stats: list[ProviderOption]
    live: list[ProviderOption]
    regions: list[RegionOption]


class HistoryEntry(BaseModel):
    timestamp: str
    type: str
    level: str
    category: str
    action: str
    message: str
    details: dict[str, Any]


class HistoryResponse(BaseModel):
    items: list[HistoryEntry]
    count: int


__all__ = [
    "AccountIdentityResponse",
    "BootstrapResponse",
    "HealthResponse",
    "HistoryResponse",
    "LiveLinkResponse",
    "MetadataResponse",
    "PresetPreview",
    "PresetSlotPatch",
    "PresetsResponse",
    "ProviderCatalog",
    "RuntimeSnapshotResponse",
    "SettingsImport",
    "SettingsPatch",
    "SettingsResponse",
    "StatsLinkResponse",
    "UpdatesResponse",
]
