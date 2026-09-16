import type { components } from "../generated/api";

export type SettingsPatch = components["schemas"]["SettingsPatch"];
export type PresetSlotPatch = components["schemas"]["PresetSlotPatch"];
export type SettingsImport = components["schemas"]["SettingsImport"];

export type PageId = "dashboard" | "presets" | "history" | "settings";

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
  selected_pick_1: string;
  selected_pick_2: string;
  selected_pick_3: string;
  selected_ban: string;
  theme: "darkly" | "flatly";
  summoner_name_auto_detect: boolean;
  manual_summoner_name: string;
  manual_region: string;
  preferred_stats_site: string;
  preferred_hotkey_site: string;
  hotkey_toggle_window: string;
  hotkey_open_site: string;
  auto_play_again_enabled: boolean;
  auto_hide_on_connect: boolean;
  close_app_on_lol_exit: boolean;
  ignored_update_version: string;
  main_skin_mode_override: "inherit" | "none" | "fixed" | "random";
  main_skin_mode_overrides: Record<string, "inherit" | "none" | "fixed" | "random">;
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
  rune_auto_apply: boolean;
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

export interface UpdateResponse {
  available: boolean;
  update: {
    version: string;
    highlights: string;
    release_url: string;
    asset_name: string;
    asset_url: string;
    checksum_name: string;
    checksum_url: string;
  } | null;
}

export interface StatsLinkResponse {
  available: boolean;
  site: string;
  url: string | null;
}

export interface ProviderOption {
  id: string;
  label: string;
}

export interface ProviderCatalog {
  stats: ProviderOption[];
  hotkey: ProviderOption[];
  regions: ProviderOption[];
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
