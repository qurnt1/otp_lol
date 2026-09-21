import type { components } from "../generated/api";
import type { DashboardAction } from "../domain/presets";

export type { DashboardAction } from "../domain/presets";

export type SettingsPatch = components["schemas"]["SettingsPatch"];
export type PresetSlotPatch = components["schemas"]["PresetSlotPatch"];
export type SettingsImport = components["schemas"]["SettingsImport"];

export type PageId = "dashboard" | "statistics" | "live" | "history" | "settings" | "diagnostics";
export type SettingsSection = "general" | "automations" | "account" | "links" | "shortcuts" | "appearance" | "advanced";
export type AppRoute =
  | { page: "settings"; section: SettingsSection }
  | { page: "dashboard"; action?: DashboardAction }
  | { page: Exclude<PageId, "settings" | "dashboard"> };

export interface RuntimeSnapshot {
  version: string;
  connected: boolean;
  phase: string;
  riot_id: string | null;
  region: string | null;
  queue_id: number;
  assigned_position: string;
  presets_enabled: boolean;
  auto_accept_enabled: boolean;
  auto_pick_enabled: boolean;
  auto_ban_enabled: boolean;
  auto_summoners_enabled: boolean;
}

export interface RuntimeEvent {
  type: string;
  data: unknown;
  timestamp: string;
}

export interface Settings {
  auto_accept_enabled: boolean;
  auto_pick_enabled: boolean;
  auto_ban_enabled: boolean;
  auto_summoners_enabled: boolean;
  presets_enabled: boolean;
  onboarding_completed: boolean;
  selected_pick_1: string;
  selected_pick_2: string;
  selected_pick_3: string;
  selected_ban: string;
  theme: "darkly" | "flatly";
  summoner_name_auto_detect: boolean;
  manual_summoner_name: string;
  manual_region: string;
  auto_detected_riot_id: string;
  auto_detected_region: string;
  auto_detected_platform: string;
  auto_detected_account_valid: boolean;
  preferred_stats_site: string;
  preferred_hotkey_site: string;
  hotkey_toggle_window: string;
  hotkey_open_site: string;
  auto_play_again_enabled: boolean;
  auto_hide_on_connect: boolean;
  close_app_on_lol_exit: boolean;
  ignored_update_version: string;
  skin_automation_enabled: boolean;
  window_x: number;
  window_y: number;
  window_width: number;
  window_height: number;
  window_maximized: boolean;
}

export interface PresetSlot {
  champion: string;
  spell_1: string;
  spell_2: string;
  skin_mode: "none" | "fixed" | "random";
  skin_id: number;
  skin_name: string;
  skin_num: number;
  random_skin_id: number;
  random_skin_name: string;
  random_skin_num: number;
  random_skin_pool: SkinReference[];
  rune_page_id: number;
  rune_page_name: string;
  rune_keystone_id: number;
  rune_keystone_path: string;
  rune_sub_style_icon_path: string;
}

export interface SkinReference {
  skin_id: number;
  skin_name: string;
  skin_num: number;
}

export interface PresetsResponse {
  presets_enabled: boolean;
  selected_ban: string;
  slots: Record<string, PresetSlot>;
}

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

export interface HistoryEntry {
  timestamp: string;
  type: string;
  level: string;
  category: string;
  action: string;
  message: string;
  details: Record<string, unknown>;
}

export interface HistoryResponse {
  items: HistoryEntry[];
  count: number;
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
export interface DiagnosticsResponse { runtime: RuntimeSnapshot; account_identity: AccountIdentity; hotkeys?: Record<"window" | "site", HotkeyStatus>; game_data: GameDataStatus; requests: DiagnosticRequestEntry[]; events: DiagnosticEventEntry[]; errors: DiagnosticErrorEntry[]; endpoint_checks: DiagnosticEndpoint[]; endpoint_results: DiagnosticCheckResult[] }
export interface DiagnosticsRunResponse { results: DiagnosticCheckResult[] }

export interface ProviderOption {
  id: string;
  label: string;
  logo_url: string;
}

export interface RegionOption {
  id: string;
  label: string;
}

export interface ProviderCatalog {
  stats: ProviderOption[];
  live: ProviderOption[];
  regions: RegionOption[];
}

export interface BootstrapResponse {
  runtime: RuntimeSnapshot;
  settings: Settings;
  presets: PresetsResponse;
  preset_previews?: Record<string, PresetPreview>;
  ban_preview?: PresetPreview | null;
}

export interface PresetPreview {
  champion_id: number | null;
  champion_name: string;
  champion_icon_url: string | null;
  champion_splash_url: string | null;
  spell_1_url: string | null;
  spell_2_url: string | null;
  skin_name: string | null;
  skin_preview_url: string | null;
}
