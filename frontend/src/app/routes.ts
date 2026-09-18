import type { AppRoute, PageId, PresetsAction, SettingsSection } from "../types/api";
import { fr } from "../content/fr";
import { diagnosticsCopy } from "../features/diagnostics/copy";

export const settingsSections = ["general", "automations", "account", "links", "shortcuts", "appearance", "advanced"] as const satisfies readonly SettingsSection[];
export const pageIds: readonly PageId[] = ["dashboard", "presets", "statistics", "live", "history", "settings", "diagnostics"];

export const pageLabels: Record<PageId, string> = {
  dashboard: fr.nav.dashboard,
  presets: fr.nav.presets,
  statistics: fr.nav.statistics,
  live: fr.nav.live,
  history: fr.nav.history,
  settings: fr.nav.settings,
  diagnostics: diagnosticsCopy.title,
};

export function parseHashRoute(hash = window.location.hash): AppRoute | null {
  const [path, query = ""] = hash.replace(/^#/, "").split("?", 2);
  const [page, section, ...extra] = path.split("/");
  if (extra.length > 0) return null;
  if (page === "presets") {
    const parameters = new URLSearchParams(query);
    const returnValues = parameters.getAll("return");
    const action = section as PresetsAction | undefined;
    if (query && [...parameters.keys()].some((key) => key !== "return")) return null;
    if (returnValues.length > 1 || (returnValues.length === 1 && returnValues[0] !== "dashboard")) return null;
    if (action && !["ban", "pick_1", "pick_2", "pick_3"].includes(action)) return null;
    if (!action && query) return null;
    if (returnValues.length && action !== "ban") return null;
    return { page, ...(action ? { action } : {}), ...(returnValues.length ? { returnTo: "dashboard" as const } : {}) };
  }
  if (page === "settings") {
    const settingsSection = section ?? "general";
    return settingsSections.includes(settingsSection as SettingsSection)
      ? { page, section: settingsSection as SettingsSection }
      : null;
  }
  return !section && pageIds.includes(page as PageId) && page !== "settings" ? { page: page as Exclude<PageId, "settings"> } : null;
}

export function routeToHash(route: AppRoute): string {
  if (route.page === "settings") return `#settings/${route.section}`;
  if (route.page === "presets") {
    const action = route.action ? `/${route.action}` : "";
    const returnTo = route.returnTo ? `?return=${route.returnTo}` : "";
    return `#presets${action}${returnTo}`;
  }
  return `#${route.page}`;
}
