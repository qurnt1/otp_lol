import { fr } from "../content/fr";

const PHASE_LABELS: Record<string, string> = {
  None: fr.runtime.phases.none,
  Lobby: fr.runtime.phases.lobby,
  Matchmaking: fr.runtime.phases.matchmaking,
  ReadyCheck: fr.runtime.phases.readyCheck,
  ChampSelect: fr.runtime.phases.championSelect,
  InProgress: fr.runtime.phases.inProgress,
  EndOfGame: fr.runtime.phases.endOfGame,
  WaitingForStats: fr.runtime.phases.waitingForStats,
  PreEndOfGame: fr.runtime.phases.endOfGame,
};

export function phaseLabel(phase: string | null | undefined): string {
  return PHASE_LABELS[phase || "None"] ?? fr.runtime.unknownPhase;
}

export function roleLabel(role: string | null | undefined): string {
  return {
    TOP: fr.runtime.roles.top,
    JUNGLE: fr.runtime.roles.jungle,
    MIDDLE: fr.runtime.roles.middle,
    BOTTOM: fr.runtime.roles.bottom,
    UTILITY: fr.runtime.roles.utility,
  }[String(role || "").toUpperCase()] ?? fr.runtime.roles.global;
}

export function connectionLabel(connected: boolean): string {
  return connected ? fr.runtime.connected : fr.runtime.waiting;
}
