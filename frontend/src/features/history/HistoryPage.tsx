import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Trash2 } from "lucide-react";

import { api } from "../../api/client";
import { Button } from "../../components/ui/button";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { fr } from "../../content/fr";
import type { HistoryEntry } from "../../types/api";

const filters = ["all", "connection", "ready_check", "champion_select", "runes", "skins", "errors"] as const;
type HistoryFilter = typeof filters[number];
const filterLabels: Record<HistoryFilter, string> = { all: fr.history.all, connection: fr.history.connection, ready_check: fr.history.readyCheck, champion_select: fr.history.championSelect, runes: fr.history.runes, skins: fr.history.skins, errors: fr.history.errors };

function entryFilter(entry: HistoryEntry): HistoryFilter {
  const value = `${entry.type} ${entry.category} ${entry.action}`.toLowerCase();
  if (value.includes("error") || entry.level === "error") return "errors";
  if (value.includes("connection") || value.includes("connect")) return "connection";
  if (value.includes("ready")) return "ready_check";
  if (value.includes("rune")) return "runes";
  if (value.includes("skin")) return "skins";
  if (value.includes("champion") || value.includes("pick") || value.includes("ban")) return "champion_select";
  return "all";
}

export function HistoryPage() {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<HistoryFilter>("all");
  const [search, setSearch] = useState("");
  const [confirmClear, setConfirmClear] = useState(false);
  const history = useQuery({ queryKey: ["history"], queryFn: () => api.getHistory(250), staleTime: 15_000 });
  const clearHistory = useMutation({ mutationFn: api.clearHistory, onSuccess: () => { setConfirmClear(false); void queryClient.invalidateQueries({ queryKey: ["history"] }); } });
  const items = useMemo(() => (history.data?.items ?? []).filter((entry) => {
    const matchesFilter = filter === "all" || entryFilter(entry) === filter;
    const needle = search.trim().toLowerCase();
    return matchesFilter && (!needle || `${entry.message} ${entry.action} ${entry.category}`.toLowerCase().includes(needle));
  }), [filter, history.data?.items, search]);

  return <div className="history-page">
    <div className="page-heading"><div><h1>{fr.history.title}</h1><p>{fr.history.subtitle}</p></div><Button variant="danger" type="button" disabled={!history.data?.items.length || clearHistory.isPending} onClick={() => setConfirmClear(true)}><Trash2 size={14} aria-hidden="true" />{fr.history.clear}</Button></div>
    <div className="history-tools"><div className="filter-group">{filters.map((key) => <button key={key} className={`filter-button ${filter === key ? "is-active" : ""}`} type="button" aria-pressed={filter === key} onClick={() => setFilter(key)}>{filterLabels[key]}</button>)}</div><input className="field-input" value={search} onChange={(event) => setSearch(event.target.value)} placeholder={fr.history.search} aria-label={fr.history.search} /></div>
    <section className="surface history-surface" aria-label={fr.history.title}>
      {history.isPending && <div className="history-status empty-state">{fr.history.loading}</div>}
      {history.isError && <div className="history-status empty-state status-danger">{fr.history.error}<button className="text-button" type="button" onClick={() => void history.refetch()}>{fr.common.retry}</button></div>}
      {clearHistory.isSuccess && <div className="feedback" role="status"><Check size={13} aria-hidden="true" /> {fr.history.cleared}</div>}
      {!history.isPending && !history.isError && !items.length && <div className="history-status empty-state">{fr.history.empty}</div>}
      {!history.isPending && !history.isError && Boolean(items.length) && <div className="history-table-wrap"><table className="history-table"><thead><tr><th>{fr.history.time}</th><th>{fr.history.type}</th><th>{fr.history.action}</th><th>{fr.history.detail}</th><th>{fr.history.status}</th></tr></thead><tbody>{items.map((entry, index) => <tr key={`${entry.timestamp}-${entry.type}-${index}`}><td>{new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(entry.timestamp))}</td><td>{entry.category}</td><td>{entry.action}</td><td><strong>{entry.message}</strong></td><td className={entry.level === "error" ? "status-danger" : entry.level === "success" ? "status-success" : ""}>{entry.level}</td></tr>)}</tbody></table></div>}
    </section>
    <ConfirmDialog open={confirmClear} title={fr.history.clear} description={fr.history.confirm} confirmLabel={fr.history.clear} onCancel={() => setConfirmClear(false)} onConfirm={() => clearHistory.mutate()} />
  </div>;
}
