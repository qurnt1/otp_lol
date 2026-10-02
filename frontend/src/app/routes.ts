import type { AppRoute, DashboardAction, PageId, SettingsSection } from "../types/api";
import { fr } from "../content/fr";
import { dashboardActions } from "../domain/presets";
import { diagnosticsCopy } from "../features/diagnostics/copy";

export const settingsSections = ["general", "automations", "account", "links", "shortcuts", "appearance", "advanced"] as const satisfies readonly SettingsSection[];
export const pageIds: readonly PageId[] = ["dashboard", "statistics", "live", "history", "settings", "diagnostics"];

export const pageLabels: Record<PageId, string> = {
  dashboard: fr.nav.dashboard,
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
  if (page === "dashboard") {
    if (query) return null;
    if (!section) return { page };
    if (extra.length > 0 || !dashboardActions.includes(section as DashboardAction)) return null;
    return { page, action: section as DashboardAction };
  }
  if (page === "settings") {
    const settingsSection = section ?? "general";
    return settingsSections.includes(settingsSection as SettingsSection)
      ? { page, section: settingsSection as SettingsSection }
      : null;
  }
  return !section && pageIds.includes(page as PageId) && page !== "settings" ? { page: page as Exclude<PageId, "settings" | "dashboard"> } : null;
}

export function routeToHash(route: AppRoute): string {
  if (route.page === "settings") return `#settings/${route.section}`;
  if (route.page === "dashboard") return route.action ? `#dashboard/${route.action}` : "#dashboard";
  return `#${route.page}`;
}
