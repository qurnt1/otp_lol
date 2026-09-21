import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import { Activity, AlertTriangle, CheckCircle2, Copy, Download, RefreshCw, Wifi, WifiOff, X } from "lucide-react";

import { api } from "../../api/client";
import { Button } from "../../components/ui/button";
import { fr as baseFr } from "../../content/fr";
import type { DiagnosticsResponse } from "../../types/api";
import { diagnosticsCopy as copy } from "./copy";
import { exportDiagnosticsReport } from "../../domain/external";
import { useNativeBridgeReady } from "../../hooks/useNativeBridgeReady";

type LogFilter = "all" | "lcu" | "automation" | "data" | "webview" | "errors";

interface DiagnosticLogRow {
  id: string;
  kind: "requests" | "events" | "errors";
  category: Exclude<LogFilter, "all">;
  timestamp: string;
  title: string;
  detail: string;
  payload?: unknown;
  failed?: boolean;
}

export function DiagnosticsPage() {
  const diagnostics = useQuery({ queryKey: ["diagnostics"], queryFn: api.getDiagnostics, staleTime: 0, refetchInterval: 5_000, retry: false });
  const [filter, setFilter] = useState<LogFilter>("all");
  const [search, setSearch] = useState("");
  const [includeRiotId, setIncludeRiotId] = useState(false);
  const [selectedPayload, setSelectedPayload] = useState<{ title: string; payload: unknown } | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const nativeBridgeReady = useNativeBridgeReady();
  const providerStatus = useQuery({ queryKey: ["provider-window-status"], queryFn: api.getProviderWindowStatus, staleTime: 0, retry: false, refetchInterval: (query) => query.state.data?.windows ? 1000 : false });
  const run = useMutation({ mutationFn: () => api.runDiagnostics(), onSuccess: async () => { setError(""); await diagnostics.refetch(); }, onError: (reason) => setError(reason instanceof Error ? reason.message : copy.runFailed) });

  const logs = useMemo(() => makeLogRows(diagnostics.data), [diagnostics.data]);
  const visibleLogs = logs.filter((entry) => {
    if (filter === "errors" ? !entry.failed : filter !== "all" && filter !== entry.category) return false;
    const query = search.trim().toLocaleLowerCase();
    return !query || `${entry.title} ${entry.detail} ${JSON.stringify(entry.payload ?? "")}`.toLocaleLowerCase().includes(query);
  });

  const exportReport = async () => {
    setError("");
    setNotice("");
    try {
      if (nativeBridgeReady) {
        const result = await exportDiagnosticsReport(includeRiotId);
        if (result) {
          if (result.cancelled) {
            setNotice(copy.exportCancelled);
            return;
          }
          if (!result.success) throw new Error(result.error || copy.exportFailed);
          setNotice(copy.exported);
          return;
        }
      }
      const report = await api.exportDiagnostics(includeRiotId);
      const file = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(file);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "otp-lol-diagnostics.json";
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : copy.exportFailed);
    }
  };

  const copyReport = async () => {
    setError("");
    setNotice("");
    try {
      const report = await api.exportDiagnostics(includeRiotId);
      await navigator.clipboard.writeText(JSON.stringify(report, null, 2));
      setNotice(copy.copied);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : copy.exportFailed);
    }
  };

  const data = diagnostics.data;
  const endpointResults = data?.endpoint_results ?? [];
  const accountIdentity = data?.account_identity;
  const accountValid = Boolean(accountIdentity?.riot_id && accountIdentity.region && accountIdentity.platform_id && accountIdentity.regional_routing && accountIdentity.source !== "unavailable");
  return <div className="diagnostics-page">
    <div className="page-heading">
      <div><h1>{copy.title}</h1><p>{copy.subtitle}</p></div>
      <div className="diagnostics-actions">
        <Button variant="quiet" type="button" onClick={() => void diagnostics.refetch()} disabled={diagnostics.isFetching}><RefreshCw size={14} aria-hidden="true" />{copy.refresh}</Button>
        <Button variant="quiet" type="button" onClick={() => run.mutate()} disabled={run.isPending || data?.runtime.connected === false}><Activity size={14} aria-hidden="true" />{run.isPending ? copy.running : copy.run}</Button>
        <Button variant="quiet" type="button" onClick={() => void copyReport()}><Copy size={14} aria-hidden="true" />{copy.copy}</Button>
        <Button variant="primary" type="button" onClick={() => void exportReport()}><Download size={14} aria-hidden="true" />{copy.export}</Button>
      </div>
    </div>

    {diagnostics.isPending && <p className="page-loading" role="status">{baseFr.common.loading}</p>}
    {diagnostics.isError && <div className="state-error" role="alert"><span>{copy.runFailed}</span><Button variant="quiet" type="button" onClick={() => void diagnostics.refetch()}>{baseFr.common.retry}</Button></div>}
    {error && <p className="inline-error" role="alert">{error}</p>}
    {notice && <p className="feedback" role="status">{notice}</p>}
    {data && <>
      <div className="diagnostics-status-grid">
        <section className="surface diagnostics-status-card">
          {data.runtime.connected ? <Wifi size={17} aria-hidden="true" /> : <WifiOff size={17} aria-hidden="true" />}
          <div><span className="section-label">{copy.connection}</span><strong>{data.runtime.connected ? baseFr.runtime.connected : baseFr.runtime.waiting}</strong><small>{data.runtime.phase}</small><small>{copy.latency}: {data.requests[data.requests.length - 1]?.duration_ms ?? "—"} {copy.milliseconds}</small></div>
        </section>
        <section className="surface diagnostics-status-card">
          <Activity size={17} aria-hidden="true" />
          <div><span className="section-label">{copy.gameData}</span><strong>{sourceLabel(data.game_data.source)}</strong><small>{copy.version}: {data.game_data.game_version ?? "—"}</small></div>
        </section>
        <section className="surface diagnostics-status-card">
          {data.game_data.cache_available ? <CheckCircle2 size={17} aria-hidden="true" /> : <AlertTriangle size={17} aria-hidden="true" />}
          <div><span className="section-label">{copy.cache}</span><strong>{data.game_data.cache_available ? copy.available : copy.unavailable}</strong><small>{data.game_data.cache_version ?? copy.none}</small></div>
        </section>
        {data.hotkeys && <section className="surface diagnostics-status-card diagnostics-hotkeys-card">
          <Activity size={17} aria-hidden="true" />
          <div>
            <span className="section-label">{copy.hotkeys}</span>
            {(["window", "site"] as const).map((key) => {
              const status = data.hotkeys?.[key];
              if (!status) return null;
              const backend = status.backend === "keyboard_hook" ? copy.keyboardHook : status.backend === "register_hotkey" ? copy.registerHotkey : copy.shortcutUnavailable;
              return <small key={key}>{key === "window" ? copy.windowShortcut : copy.siteShortcut}: {status.hotkey} · {backend} · {status.active ? copy.available : copy.shortcutUnavailable}</small>;
            })}
          </div>
        </section>}
        {providerStatus.data && <section className="surface diagnostics-status-card diagnostics-hotkeys-card">
          <Activity size={17} aria-hidden="true" />
          <div>
            <span className="section-label">{copy.providerWindows}</span>
            {(["stats", "live"] as const).map((kind) => {
              const status = providerStatus.data.windows?.[kind];
              return <small key={kind}>{kind === "stats" ? copy.providerStats : copy.providerLive}: {status?.state ?? copy.notAvailable}{status?.last_error ? ` · ${status.last_error}` : ""}</small>;
            })}
          </div>
        </section>}
      </div>

      <section className="surface diagnostics-account-card" aria-labelledby="diagnostics-account-heading">
        <div className="statistics-card-heading"><div><span className="section-label">{copy.account}</span><h2 id="diagnostics-account-heading">{data.account_identity.riot_id ?? "—"}</h2></div><span className={accountValid ? "diagnostics-check is-success" : "diagnostics-check is-error"}>{accountValid ? copy.accountValid : copy.accountUnavailable}</span></div>
        <dl className="diagnostics-account-grid">
          <div><dt>{copy.accountRiotId}</dt><dd>{data.account_identity.riot_id ?? "—"}</dd></div>
          <div><dt>{copy.accountPlatform}</dt><dd>{data.account_identity.platform_id?.toUpperCase() ?? "—"}</dd></div>
          <div><dt>{copy.accountRegion}</dt><dd>{data.account_identity.region?.toUpperCase() ?? "—"}</dd></div>
          <div><dt>{copy.accountRouting}</dt><dd>{data.account_identity.regional_routing?.toUpperCase() ?? "—"}</dd></div>
          <div><dt>{copy.accountSource}</dt><dd>{copy.routingSources[(data.account_identity.routing_source ?? data.account_identity.source) as keyof typeof copy.routingSources] ?? data.account_identity.source}</dd></div>
          <div><dt>{copy.accountState}</dt><dd>{data.account_identity.connected ? baseFr.runtime.connected : baseFr.runtime.waiting}</dd></div>
        </dl>
      </section>

      {!data.runtime.connected && <p className="diagnostics-note" role="status">{copy.noLeague}</p>}
      <p className="diagnostics-note">{copy.redacted}</p>

      <section className="surface diagnostics-tests">
        <div className="statistics-card-heading"><div><span className="section-label">{copy.endpoints}</span><h2>{copy.testResults}</h2></div></div>
        <div className="diagnostics-test-list">{data.endpoint_checks.map((endpoint) => {
          const result = endpointResults.find((entry) => entry.id === endpoint.id);
          return <div className="diagnostics-test-row" key={endpoint.id}><span className={result ? result.success ? "diagnostics-check is-success" : "diagnostics-check is-error" : "diagnostics-check"}>{result ? result.success ? copy.success : copy.failure : copy.notRun}</span><strong>{endpoint.label}</strong><code>{endpoint.method} {endpoint.path}</code><small>{result ? `${result.status ?? "—"} · ${result.duration_ms} ${copy.milliseconds}` : "—"}</small></div>;
        })}</div>
      </section>

      <section className="surface diagnostics-log-panel">
        <div className="statistics-card-heading"><div><span className="section-label">{copy.events}</span><h2>{copy.requests} · {copy.events} · {copy.errors}</h2></div><small>{logs.length}</small></div>
        <div className="diagnostics-log-controls">
          <label><span className="sr-only">{copy.search}</span><input className="field-input" type="search" placeholder={copy.search} value={search} onChange={(event) => setSearch(event.target.value)} /></label>
          <div className="diagnostics-filter" aria-label={copy.search}>{(["all", "lcu", "automation", "data", "webview", "errors"] as const).map((value) => <button key={value} type="button" aria-pressed={filter === value} onClick={() => setFilter(value)}>{value === "all" ? copy.all : value === "lcu" ? copy.lcuFilter : value === "automation" ? copy.automation : value === "data" ? copy.data : value === "webview" ? copy.webview : copy.onlyErrors}</button>)}</div>
          <label className="diagnostics-opt-in"><input type="checkbox" checked={includeRiotId} onChange={(event) => setIncludeRiotId(event.target.checked)} />{copy.includeRiotId}</label>
        </div>
        <div className="diagnostics-log-list">
          {visibleLogs.map((entry) => <article className="diagnostics-log-row" key={entry.id}>
            <span className={`diagnostics-log-kind is-${entry.kind}`}>{entry.kind}</span>
            <time>{formatTimestamp(entry.timestamp)}</time>
            <strong>{entry.title}</strong>
            <small>{entry.detail}</small>
            {entry.payload !== undefined && <Button className="diagnostics-json-button" type="button" onClick={() => setSelectedPayload({ title: entry.title, payload: entry.payload })}>{copy.viewJson}</Button>}
          </article>)}
          {!visibleLogs.length && <p className="statistics-empty">{copy.noEntries}</p>}
        </div>
      </section>
    </>}
    <Dialog.Root open={selectedPayload !== null} onOpenChange={(open) => { if (!open) setSelectedPayload(null); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay" />
        <Dialog.Content className="confirm-dialog diagnostics-json-dialog" aria-describedby="diagnostics-json-description">
          <div className="drawer-head"><div><Dialog.Title>{copy.jsonTitle}</Dialog.Title><Dialog.Description id="diagnostics-json-description">{selectedPayload?.title ?? copy.jsonDescription}</Dialog.Description></div><Dialog.Close asChild><button className="icon-button" type="button" aria-label={baseFr.common.close}><X size={16} aria-hidden="true" /></button></Dialog.Close></div>
          <pre><code>{selectedPayload ? JSON.stringify(selectedPayload.payload, null, 2) : ""}</code></pre>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  </div>;
}

function makeLogRows(data?: DiagnosticsResponse): DiagnosticLogRow[] {
  if (!data) return [];
  return [
    ...data.requests.map((item, index): DiagnosticLogRow => ({ id: `request-${index}-${item.timestamp}`, kind: "requests", category: "lcu", failed: !item.success, timestamp: item.timestamp, title: `${item.method} ${item.path}`, detail: `${item.status ?? "—"} · ${item.duration_ms} ms${item.error ? ` · ${item.error}` : ""}` })),
    ...data.events.map((item, index): DiagnosticLogRow => ({ id: `event-${index}-${item.timestamp}`, kind: "events", category: eventCategory(item), failed: false, timestamp: item.timestamp, title: `${item.topic} · ${item.event_type}`, detail: item.summary, payload: item.payload })),
    ...data.errors.map((item, index): DiagnosticLogRow => ({ id: `error-${index}-${item.timestamp}`, kind: "errors", category: eventCategoryFromSource(item.source), failed: true, timestamp: item.timestamp, title: `${item.source} · ${item.error}`, detail: [item.method, item.path, item.status].filter((part) => part !== null && part !== undefined).join(" · ") })),
  ].sort((left, right) => right.timestamp.localeCompare(left.timestamp));
}

function eventCategory(event: DiagnosticsResponse["events"][number]): DiagnosticLogRow["category"] {
  const source = `${event.topic} ${event.event_type} ${JSON.stringify(event.payload ?? "")}`.toLocaleLowerCase();
  if (source.includes("webview")) return "webview";
  if (source.includes("automation") || /champion_(picked|banned)|spells_set|runes_applied|skin_selected|(?:pick|ban|spell|rune|skin)_(?:confirmed|applied|selected|failed)/.test(source)) return "automation";
  return eventCategoryFromSource(source);
}

function eventCategoryFromSource(source: string): DiagnosticLogRow["category"] {
  const normalized = source.toLocaleLowerCase();
  if (normalized.includes("webview")) return "webview";
  if (normalized.includes("data") || normalized.includes("dragon") || normalized.includes("static")) return "data";
  if (normalized.includes("automation")) return "automation";
  return "lcu";
}

function sourceLabel(source: DiagnosticsResponse["game_data"]["source"]): string {
  if (source === "lcu") return copy.lcu;
  if (source === "cache") return copy.cacheSource;
  if (source === "mixed") return copy.mixed;
  if (source === "datadragon") return copy.datadragon;
  return copy.none;
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleTimeString("fr-FR");
}
