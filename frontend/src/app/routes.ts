import type { PageId } from "../types/api";
import { fr } from "../content/fr";

export const pageIds: readonly PageId[] = ["dashboard", "presets", "history", "settings"];

export const pageLabels: Record<PageId, string> = {
  dashboard: fr.nav.dashboard,
  presets: fr.nav.presets,
  history: fr.nav.history,
  settings: fr.nav.settings,
};

export function pageFromHash(): PageId | null {
  const hash = window.location.hash.replace(/^#/, "") as PageId;
  return pageIds.includes(hash) ? hash : null;
}
