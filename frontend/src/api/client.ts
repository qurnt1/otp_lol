import type {
  Champion, HistoryResponse, PresetsResponse, RuntimeSnapshot, RunesResponse, Settings,
  SkinsResponse, StatsLinkResponse, SummonerSpell, UpdateResponse, PresetSlot, PresetSlotPatch, SettingsPatch, ProviderCatalog,
  BootstrapResponse, SettingsImport, LiveLinkResponse,
  DiagnosticsResponse, DiagnosticsRunResponse, AccountIdentity,
} from "../types/api";

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

export async function parseApiError(response: Response): Promise<string> {
  const raw = await response.text();
  let detail = raw;
  try {
    const payload: unknown = raw ? JSON.parse(raw) : null;
    if (payload && typeof payload === "object" && "detail" in payload) {
      const value = payload.detail;
      detail = Array.isArray(value)
        ? value.map((item) => item && typeof item === "object" && "msg" in item ? String(item.msg) : String(item)).join(", ")
        : String(value);
    }
  } catch {
    // The local API can return plain text for infrastructure failures.
  }
  console.error("[OTP LOL API]", response.status, detail);
  const normalized = detail.toLowerCase();
  if (normalized.includes("global hotkeys must be different") || normalized.includes("duplicate hotkey")) return "Ce raccourci est déjà utilisé.";
  if (normalized.includes("unknown summoner spell")) return "Ce sort d'invocateur n'est pas reconnu.";
  return detail || "La requête locale a échoué.";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...init, headers });
  if (!response.ok) throw new ApiError(await parseApiError(response), response.status);
  return (await response.json()) as T;
}

export const api = {
  getBootstrap: () => request<BootstrapResponse>("/api/bootstrap"),
  getRuntime: () => request<RuntimeSnapshot>("/api/runtime"),
  getSettings: () => request<Settings>("/api/settings"),
  patchSettings: (values: SettingsPatch) => request<Settings>("/api/settings", { method: "PATCH", body: JSON.stringify(values) }),
  getPresets: () => request<PresetsResponse>("/api/presets"),
  resetPresets: () => request<Settings>("/api/presets/reset", { method: "POST" }),
  clearPresets: () => request<Settings>("/api/presets/clear", { method: "POST" }),
  patchPreset: (slot: string, values: PresetSlotPatch | Partial<PresetSlot>) => request<PresetsResponse>("/api/presets/" + slot, { method: "PUT", body: JSON.stringify(values) }),
  getChampions: (query = "", signal?: AbortSignal) => request<{ items: Champion[]; count: number }>("/api/champions?q=" + encodeURIComponent(query), { signal }),
  getSpells: () => request<{ items: SummonerSpell[] }>("/api/spells"),
  getSkins: (championId: number) => request<SkinsResponse>("/api/skins/" + championId),
  getRunes: () => request<RunesResponse>("/api/runes"),
  getStatsLink: () => request<StatsLinkResponse>("/api/links/stats"),
  getLiveLink: () => request<LiveLinkResponse>("/api/links/live"),
  getAccountIdentity: () => request<AccountIdentity>("/api/account/identity"),
  getDiagnostics: () => request<DiagnosticsResponse>("/api/diagnostics"),
  runDiagnostics: (endpointIds?: string[]) => request<DiagnosticsRunResponse>("/api/diagnostics/run", { method: "POST", body: JSON.stringify({ endpoint_ids: endpointIds ?? null }) }),
  exportDiagnostics: (includeRiotId: boolean) => request<Record<string, unknown>>(`/api/diagnostics/export?include_riot_id=${includeRiotId}`),
  getProviders: () => request<ProviderCatalog>("/api/catalog/providers"),
  getHistory: (limit = 100) => request<HistoryResponse>("/api/history?limit=" + limit),
  getUpdates: () => request<UpdateResponse>("/api/updates"),
  clearHistory: () => request<{ ok: boolean }>("/api/history", { method: "DELETE" }),
  resetSettings: () => request<Settings>("/api/settings/reset", { method: "POST" }),
  clearLastDetectedAccount: () => request<Settings>("/api/settings/last-detected-account", { method: "DELETE" }),
  importSettings: (values: SettingsImport) => request<Settings>("/api/settings/import", { method: "POST", body: JSON.stringify(values) }),
};
