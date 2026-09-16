import type { ProviderCatalog, ProviderOption } from "../types/api";

export const defaultProviderCatalog: ProviderCatalog = {
  stats: [{ id: "opgg", label: "OP.GG" }, { id: "deeplol", label: "DeepLOL" }, { id: "dpm", label: "DPM.LOL" }, { id: "leagueofgraphs", label: "League of Graphs" }],
  hotkey: [{ id: "porofessor", label: "Porofessor" }, { id: "deeplol", label: "DeepLOL" }, { id: "dpm", label: "DPM.LOL" }, { id: "opgg", label: "OP.GG" }],
  regions: ["euw", "eune", "na", "kr", "jp", "br", "lan", "las", "oce", "tr", "ru"].map((id) => ({ id, label: id.toUpperCase() })),
};

export function catalogOrFallback(catalog: ProviderCatalog | undefined, key: keyof ProviderCatalog): ProviderOption[] {
  const options = catalog?.[key];
  return options?.length ? options : defaultProviderCatalog[key];
}
