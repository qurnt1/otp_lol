import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, UserRound } from "lucide-react";

import { api } from "../../api/client";
import { fr } from "../../content/fr";
import { cn } from "../../lib/cn";
import type { Champion } from "../../types/api";
import { AssetImage } from "../../components/game/AssetImage";
import { filterChampions, roleFilters, type RoleFilterId } from "./picker-utils";

export function ChampionPicker({ selected, onSelect }: { selected: string; onSelect: (champion: Champion) => void }) {
  const [query, setQuery] = useState("");
  const [role, setRole] = useState<RoleFilterId>("all");
  const champions = useQuery({ queryKey: ["champions", "catalog"], queryFn: () => api.getChampions(), staleTime: 3_600_000 });
  const items = useMemo(() => filterChampions(champions.data?.items ?? [], query, role), [champions.data?.items, query, role]);
  return <div className="champion-picker"><label className="field-label" htmlFor="champion-search"><Search size={13} aria-hidden="true" />{fr.presets.searchChampion}</label><input id="champion-search" className="field-input" autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder={fr.presets.searchChampion} />
    <div className="role-filters" role="group" aria-label={fr.presets.positionFilters}>{roleFilters.map((item) => <button key={item.id} className={cn("filter-button", role === item.id && "is-active")} type="button" aria-pressed={role === item.id} onClick={() => setRole(item.id)}>{item.label}</button>)}</div>
    <div className="picker-summary"><span>{items.length} {fr.presets.championsFound}</span>{selected && <span>{fr.presets.currentSelection}: <strong>{selected}</strong></span>}</div>
    <div className="champion-grid" role="listbox" aria-label={fr.presets.selectChampion}>{champions.isPending && <span className="empty-state">{fr.common.loading}</span>}{champions.isError && <span className="empty-state status-danger">{fr.presets.championLoadError}</span>}{items.map((item) => <button key={item.id} className={cn("champion-option", item.name === selected && "is-selected")} type="button" role="option" aria-selected={item.name === selected} onClick={() => onSelect(item)}><AssetImage src={item.icon_url ?? undefined} alt="" width="42" height="42" fallback={<UserRound size={18} aria-hidden="true" />} /><span><strong>{item.name}</strong><small>{item.roles?.map((itemRole) => itemRole === "MIDDLE" ? "Mid" : itemRole === "BOTTOM" ? "ADC" : itemRole === "UTILITY" ? "Support" : itemRole[0] + itemRole.slice(1).toLowerCase()).join(" · ") || item.tags.join(" · ")}</small></span></button>)}{!champions.isPending && !champions.isError && !items.length && <span className="empty-state">{fr.presets.noResults}</span>}</div>
  </div>;
}
