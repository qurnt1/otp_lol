import { describe, expect, it } from "vitest";

import { localizeRuntimeStatus } from "./runtimeStatus";

describe("runtime status localization", () => {
  it("uses structured action data to format champion-select activity", () => {
    expect(localizeRuntimeStatus({ action: "role_detected", level: "ROLE", params: { role: "TOP" } }).message)
      .toBe("Rôle détecté : Top.");
    expect(localizeRuntimeStatus({ action: "prepick_confirmed", params: { champion: "Garen" } }).message)
      .toBe("Champion pré-sélectionné : Garen.");
    expect(localizeRuntimeStatus({ action: "ban_confirmed", params: { champion: "Teemo" } }).message)
      .toBe("Champion banni : Teemo.");
    expect(localizeRuntimeStatus({ action: "pick_confirmed", params: { champion: "Lux" } }).message)
      .toBe("Champion sélectionné : Lux.");
  });

  it("formats spell, skin, rune, account and retry updates in French", () => {
    expect(localizeRuntimeStatus({ action: "summoners_applied", params: { spell_1: "Flash", spell_2: "Ignite" } }).message)
      .toBe("Sorts sélectionnés : Flash + Ignite.");
    expect(localizeRuntimeStatus({ action: "skin_selected", params: { skin: "God-King Garen" } }).message)
      .toBe("Skin sélectionné : God-King Garen.");
    expect(localizeRuntimeStatus({ action: "runes_applied", params: { page: "Conquérant" } }).message)
      .toBe("Runes configurées : Conquérant.");
    expect(localizeRuntimeStatus({ action: "account_connected", params: { riot_id: "Quentin#EUW" } }).message)
      .toBe("Compte synchronisé : Quentin#EUW.");
    expect(localizeRuntimeStatus({ action: "summoners_unconfirmed", level: "WARN" }))
      .toEqual({ message: "Les sorts ne sont pas encore confirmés, nouvelle tentative en attente.", level: "WARN" });
  });

  it("never exposes unknown backend text directly and retains the event level", () => {
    expect(localizeRuntimeStatus({ action: "future_backend_message", level: "ERROR", params: { text: "raw English" } }))
      .toEqual({ message: "Activité League mise à jour.", level: "ERROR" });
    expect(localizeRuntimeStatus("raw English"))
      .toEqual({ message: "Activité League mise à jour.", level: "INFO" });
  });
});
