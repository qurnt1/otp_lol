import type { components } from "../generated/api";
import type { DashboardAction } from "../domain/presets";

export type { DashboardAction } from "../domain/presets";

export type SettingsPatch = components["schemas"]["SettingsPatch"];
export type PresetSlotPatch = components["schemas"]["PresetSlotPatch"];
export type PresetSlot = components["schemas"]["PresetSlot"];
export type SettingsImport = components["schemas"]["SettingsImport"];
export type RuntimeSnapshot = components["schemas"]["RuntimeSnapshotResponse"];
export type HistoryEntry = components["schemas"]["HistoryEntry"];
export type PresetsResponse = components["schemas"]["PresetsResponse"];
export type HistoryResponse = components["schemas"]["HistoryResponse"];
export type ProviderOption = components["schemas"]["ProviderOption"];
export type RegionOption = components["schemas"]["RegionOption"];
export type ProviderCatalog = components["schemas"]["ProviderCatalog"];
export type SkinReference = components["schemas"]["SkinReference"];
export type PresetPreview = Required<components["schemas"]["PresetPreview"]>;

export type PageId = "dashboard" | "statistics" | "live" | "history" | "settings" | "diagnostics";
export type SettingsSection = "general" | "automations" | "account" | "links" | "shortcuts" | "appearance" | "advanced";
export type AppRoute =
  | { page: "settings"; section: SettingsSection }
  | { page: "dashboard"; action?: DashboardAction }
  | { page: Exclude<PageId, "settings" | "dashboard"> };

export interface RuntimeEvent {
  type: string;
  data: unknown;
  timestamp: string;
}

export type Settings = Omit<components["schemas"]["SettingsResponse"], "config_version" | "config_schema_version" | "pick_slots">;

export interface Champion {
  id: number;
  name: string;
  slug: string;
  title?: string;
  tags: string[];
  roles?: string[];
  icon_url: string | null;
  splash_url: string | null;
}

export interface SummonerSpell {
  name: string;
  icon_url: string | null;
}

export interface Skin {
  champion_id: number;
  champion_name: string;
  champion_slug: string;
  skin_id: number;
  skin_num: number;
  skin_name: string;
  splash_url: string;
  tile_url: string;
  centered_splash_url: string;
  uncentered_splash_url: string;
  owned?: boolean;
}

export interface OwnedSkin {
  skin_id: number;
  skin_num: number;
  skin_name: string;
  preview_url: string;
  tile_url: string;
  splash_url: string;
}

export interface SkinsResponse {
  champion_id: number;
  catalog: Skin[];
  owned: {
    ok: boolean;
    message: string;
    owned_skins: OwnedSkin[];
    source?: string;
  };
}

export interface RunePage {
  id: number;
  name: string;
  primaryStyleId: number;
  subStyleId: number;
  selectedPerkIds: number[];
  selectedPerkPaths?: string[];
  current: boolean;
}

export interface RunePerk {
  id: number;
  name: string;
  iconPath: string;
  icon_url?: string | null;
}

export interface RuneStyle {
  name: string;
  iconPath: string;
  icon_url?: string | null;
  perks: RunePerk[];
}

export interface RunesResponse {
  available: boolean;
  pages: RunePage[];
  styles: Record<string, RuneStyle>;
}

export type UpdateResponse = components["schemas"]["UpdatesResponse"];
export type AccountIdentity = components["schemas"]["AccountIdentityResponse"];
export type StatsLinkResponse = components["schemas"]["StatsLinkResponse"];
export type LiveLinkResponse = components["schemas"]["LiveLinkResponse"];

export interface GameDataStatus {
  source: "lcu" | "cache" | "mixed" | "datadragon" | null;
  game_version: string | null;
  connected: boolean;
  cache_available: boolean;
  cache_version: string | null;
  fallback: "datadragon" | null;
  catalogs: Record<string, boolean>;
}

export interface DiagnosticRequestEntry { timestamp: string; method: string; path: string; status: number | null; duration_ms: number; success: boolean; error: string | null }
export interface DiagnosticEventEntry { timestamp: string; topic: string; event_type: string; summary: string; payload: unknown; payload_truncated: boolean; payload_redacted: boolean }
export interface DiagnosticErrorEntry { timestamp: string; source: string; error: string; method: string | null; path: string | null; status: number | null }
export interface DiagnosticEndpoint { id: string; label: string; path: string; method: string }
export interface DiagnosticCheckResult extends DiagnosticEndpoint { status: number | null; duration_ms: number; success: boolean; error: string | null; summary: string }
export interface HotkeyStatus { hotkey: string; backend: "keyboard_hook" | "register_hotkey" | "unavailable"; active: boolean }
export interface DiagnosticsResponse { runtime: Omit<RuntimeSnapshot, "riot_id">; account_identity: AccountIdentity; hotkeys?: Record<"window" | "site", HotkeyStatus>; game_data: GameDataStatus; requests: DiagnosticRequestEntry[]; events: DiagnosticEventEntry[]; errors: DiagnosticErrorEntry[]; endpoint_checks: DiagnosticEndpoint[]; endpoint_results: DiagnosticCheckResult[] }
export interface DiagnosticsRunResponse { results: DiagnosticCheckResult[] }

export type BootstrapResponse = Omit<components["schemas"]["BootstrapResponse"], "settings" | "preset_previews" | "ban_preview"> & {
  settings: Settings;
  preset_previews?: Record<string, PresetPreview>;
  ban_preview?: PresetPreview | null;
};
