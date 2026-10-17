import { fr } from "../content/fr";
import { roleLabel } from "./runtime";

type StatusParams = Record<string, unknown>;

function textParam(params: StatusParams, key: string): string {
  return typeof params[key] === "string" ? params[key] as string : "";
}

const STATUS_MESSAGES: Record<string, (params: StatusParams) => string> = {
  client_connected: () => fr.runtime.messages.clientConnected,
  client_disconnected: () => fr.runtime.messages.clientDisconnected,
  login_detected: () => fr.runtime.messages.loginDetected,
  match_accepted: () => fr.runtime.messages.matchAccepted,
  play_again_succeeded: () => fr.runtime.messages.playAgainSucceeded,
  presets_disabled: () => fr.runtime.messages.presetsDisabled,
  role_detected: (params) => fr.runtime.messages.roleDetected(roleLabel(textParam(params, "role"))),
  prepick_waiting: () => fr.runtime.messages.prepickWaiting,
  prepick_timed_out: () => fr.runtime.messages.prepickTimedOut,
  prepick_confirmed: (params) => fr.runtime.messages.prepickConfirmed(textParam(params, "champion")),
  prepick_failed: (params) => fr.runtime.messages.prepickFailed(textParam(params, "champion")),
  ban_confirmed: (params) => fr.runtime.messages.banConfirmed(textParam(params, "champion")),
  pickable_unavailable: () => fr.runtime.messages.pickableUnavailable,
  no_champion_available: () => fr.runtime.messages.noChampionAvailable,
  pick_confirmed: (params) => fr.runtime.messages.pickConfirmed(textParam(params, "champion")),
  pick_unconfirmed: () => fr.runtime.messages.pickUnconfirmed,
  summoners_applied: (params) => fr.runtime.messages.summonersApplied(textParam(params, "spell_1"), textParam(params, "spell_2")),
  summoners_unconfirmed: () => fr.runtime.messages.summonersUnconfirmed,
  skin_selected: (params) => fr.runtime.messages.skinSelected(textParam(params, "skin")),
  runes_applied: (params) => fr.runtime.messages.runesApplied(textParam(params, "page")),
  lcu_missing: () => fr.runtime.messages.lcuMissing,
  client_detection_retry: () => fr.runtime.messages.clientDetectionRetry,
  connection_retry: () => fr.runtime.messages.connectionRetry,
  account_connected: (params) => fr.runtime.messages.accountConnected(textParam(params, "riot_id")),
};

export type RuntimeStatusTone = "success" | "info" | "warning";

const SUCCESS_ACTIONS = new Set([
  "client_connected", "account_connected", "match_accepted", "play_again_succeeded",
  "prepick_confirmed", "ban_confirmed", "pick_confirmed", "summoners_applied",
  "skin_selected", "runes_applied",
]);

const WARNING_ACTIONS = new Set([
  "client_disconnected", "prepick_timed_out", "prepick_failed", "pickable_unavailable",
  "no_champion_available", "pick_unconfirmed", "summoners_unconfirmed", "lcu_missing",
  "client_detection_retry", "connection_retry",
]);

function statusTone(action: string, level: string): RuntimeStatusTone {
  if (SUCCESS_ACTIONS.has(action)) return "success";
  if (WARNING_ACTIONS.has(action) || /WARN|ERROR/i.test(level)) return "warning";
  return "info";
}

export function localizeRuntimeStatus(data: unknown): { message: string; level: string; tone: RuntimeStatusTone } {
  if (!data || typeof data !== "object" || !("action" in data) || typeof data.action !== "string") {
    return { message: fr.runtime.messages.unknown, level: "INFO", tone: "info" };
  }

  const params = "params" in data && data.params && typeof data.params === "object"
    ? data.params as StatusParams
    : {};
  const message = STATUS_MESSAGES[data.action]?.(params) ?? fr.runtime.messages.unknown;
  const level = "level" in data && typeof data.level === "string" ? data.level : "INFO";
  return { message, level, tone: statusTone(data.action, level) };
}
