import type { components } from "../generated/api";
import type { DashboardAction } from "../domain/presets";

export type { DashboardAction } from "../domain/presets";

export type SettingsPatch = components["schemas"]["SettingsPatch"];
export type PresetSlotPatch = components["schemas"]["PresetSlotPatch"];
export type PresetSlot = components["schemas"]["PresetSlot"];
export type PresetOrderRequest = components["schemas"]["PresetOrderRequest"];
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

export type Champion = components["schemas"]["ChampionCatalogEntry"];
export type ChampionCatalogResponse = components["schemas"]["ChampionCatalogResponse"];
export type SummonerSpell = components["schemas"]["SummonerSpellEntry"];
export type SummonerSpellCatalogResponse = components["schemas"]["SummonerSpellCatalogResponse"];
export type Skin = components["schemas"]["SkinCatalogEntry"];
export type OwnedSkin = components["schemas"]["OwnedSkinEntry"];
export type SkinsResponse = components["schemas"]["SkinsResponse"];
export type RunePage = components["schemas"]["RunePageResponse"];
export type RunePerk = components["schemas"]["RunePerkResponse"];
export type RuneStyle = components["schemas"]["RuneStyleResponse"];
export type RunesResponse = components["schemas"]["RunesResponse"];

export type UpdateResponse = components["schemas"]["UpdatesResponse"];
export type AccountIdentity = components["schemas"]["AccountIdentityResponse"];
export type StatsLinkResponse = components["schemas"]["StatsLinkResponse"];
export type LiveLinkResponse = components["schemas"]["LiveLinkResponse"];

export type GameDataStatus = components["schemas"]["GameDataStatusResponse"];
export type DiagnosticRequestEntry = components["schemas"]["DiagnosticRequestEntry"];
export type DiagnosticEventEntry = components["schemas"]["DiagnosticEventEntry"];
export type DiagnosticErrorEntry = components["schemas"]["DiagnosticErrorEntry"];
export type DiagnosticEndpoint = components["schemas"]["DiagnosticEndpoint"];
export type DiagnosticCheckResult = components["schemas"]["DiagnosticCheckResult"];
export type HotkeyStatus = components["schemas"]["DiagnosticHotkeyStatus"];
export type DiagnosticsResponse = components["schemas"]["DiagnosticsResponse"];
export type DiagnosticsRunResponse = components["schemas"]["DiagnosticsRunResponse"];
export type DiagnosticsExportResponse = components["schemas"]["DiagnosticsExportResponse"];
export type HistoryClearResponse = components["schemas"]["HistoryClearResponse"];
export type ProviderWindowStatus = components["schemas"]["ProviderWindowStatus"];
export type ProviderWindowsStatusResponse = components["schemas"]["ProviderWindowsStatusResponse"];
export type ProviderWindowActionResponse = components["schemas"]["ProviderWindowActionResponse"];
export type NetworkStatus = components["schemas"]["NetworkStatusResponse"];
export type BootstrapResponse = components["schemas"]["BootstrapResponse"];
