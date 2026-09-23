import { lazy, Suspense, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, ExternalLink, LoaderCircle } from "lucide-react";

import { api } from "./api/client";
import { connectRuntimeEvents } from "./api/events";
import { AppShell } from "./app/AppShell";
import { useHashRoute } from "./app/useHashRoute";
import { Button } from "./components/ui/button";
import { fr } from "./content/fr";
import { localizeRuntimeStatus } from "./domain/runtimeStatus";
import { NetworkWarning } from "./features/network/NetworkGate";
import { useRuntimeStore } from "./stores/runtimeStore";
import type { RuntimeEvent, RuntimeSnapshot, UpdateResponse } from "./types/api";

const DashboardPage = lazy(() => import("./features/dashboard/DashboardPage").then(({ DashboardPage: page }) => ({ default: page })));
const HistoryPage = lazy(() => import("./features/history/HistoryPage").then(({ HistoryPage: page }) => ({ default: page })));
const LiveStatisticsPage = lazy(() => import("./features/live/LiveStatisticsPage").then(({ LiveStatisticsPage: page }) => ({ default: page })));
const StatisticsPage = lazy(() => import("./features/statistics/StatisticsPage").then(({ StatisticsPage: page }) => ({ default: page })));
const DiagnosticsPage = lazy(() => import("./features/diagnostics/DiagnosticsPage").then(({ DiagnosticsPage: page }) => ({ default: page })));
const SettingsPage = lazy(() => import("./features/settings/SettingsPage").then(({ SettingsPage: page }) => ({ default: page })));
const UPDATE_CHECK_INTERVAL = 21_600_000;

function updateRuntimeFromEvent(
  event: RuntimeEvent,
  setRuntime: (runtime: RuntimeSnapshot) => void,
  setStatus: (status: { message: string; level: string; tone: "success" | "info" | "warning"; timestamp: string }) => void,
) {
  if (event.type === "runtime_snapshot" && event.data && typeof event.data === "object") {
    setRuntime(event.data as RuntimeSnapshot);
    return;
  }
  if (event.type === "status") {
    setStatus({ ...localizeRuntimeStatus(event.data), timestamp: event.timestamp });
    return;
  }
}

function PageFallback() {
  return <div className="page-loading" role="status" aria-live="polite"><LoaderCircle size={18} aria-hidden="true" />{fr.common.loading}</div>;
}

function UpdateBanner() {
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.getSettings, staleTime: Infinity });
  const updates = useQuery({ queryKey: ["updates"], queryFn: api.getUpdates, enabled: false, staleTime: UPDATE_CHECK_INTERVAL });
  const update = updates.data?.available ? updates.data.update : null;
  const ignoreUpdate = useMutation({
    mutationFn: () => api.patchSettings({ ignored_update_version: update?.version ?? "" }),
    onSuccess: (next) => {
      queryClient.setQueryData(["settings"], next);
      queryClient.setQueryData<UpdateResponse>(["updates"], { available: false, update: null });
    },
  });
  if (!update || update.version === settings.data?.ignored_update_version) return null;
  return <section className="update-banner" aria-label={fr.updates.label}>
    <div className="update-banner-copy"><span className="section-label">{fr.updates.label}</span><strong>{fr.updates.available(update.version)}</strong>{update.highlights && <span>{update.highlights}</span>}</div>
    <div className="update-banner-actions">
      {update.release_url && <a className="button button-secondary" href={update.release_url} target="_blank" rel="noreferrer"><ExternalLink size={14} aria-hidden="true" />{fr.updates.releaseNotes}</a>}
      {update.asset_url && <a className="button button-primary" href={update.asset_url} target="_blank" rel="noreferrer"><Download size={14} aria-hidden="true" />{fr.updates.download}</a>}
      <Button variant="quiet" type="button" onClick={() => ignoreUpdate.mutate()} disabled={ignoreUpdate.isPending}>{fr.updates.ignore}</Button>
    </div>
  </section>;
}

function App() {
  const [activeRoute, navigate, replaceRoute] = useHashRoute();
  const queryClient = useQueryClient();
  const setRuntime = useRuntimeStore((state) => state.setRuntime);
  const setStatus = useRuntimeStore((state) => state.setStatus);
  const storedRuntime = useRuntimeStore((state) => state.runtime);
  const network = useQuery({
    queryKey: ["network-status"],
    queryFn: api.getNetworkStatus,
    staleTime: 0,
    retry: false,
    refetchInterval: (query) => query.state.data?.online ? false : 5_000,
  });
  const bootstrap = useQuery({ queryKey: ["bootstrap"], queryFn: api.getBootstrap, staleTime: Infinity, gcTime: Infinity, retry: 1 });
  const runtime = storedRuntime ?? bootstrap.data?.runtime ?? null;
  useEffect(() => { performance.mark("otp:t5-react-mount"); }, []);
  useEffect(() => {
    const refreshNetwork = () => {
      void api.checkNetworkStatus()
        .then((next) => queryClient.setQueryData(["network-status"], next))
        .catch(() => undefined);
    };
    window.addEventListener("online", refreshNetwork);
    window.addEventListener("offline", refreshNetwork);
    return () => {
      window.removeEventListener("online", refreshNetwork);
      window.removeEventListener("offline", refreshNetwork);
    };
  }, [queryClient]);
  useEffect(() => {
    if (!bootstrap.data) return;
    performance.mark("otp:t6-bootstrap");
    setRuntime(bootstrap.data.runtime);
    document.documentElement.dataset.theme = bootstrap.data.settings.theme === "flatly" ? "light" : "dark";
    queryClient.setQueryData(["settings"], bootstrap.data.settings);
    queryClient.setQueryData(["presets"], bootstrap.data.presets);
  }, [bootstrap.data, queryClient, setRuntime]);

  useEffect(() => {
    let disposed = false;
    const refreshRuntime = () => void api.getRuntime().then((snapshot) => { if (!disposed) setRuntime(snapshot); }).catch(() => undefined);
    const reconciliationTimer = window.setInterval(refreshRuntime, 30_000);
    const disconnect = connectRuntimeEvents((event) => {
      updateRuntimeFromEvent(event, setRuntime, setStatus);
      if (event.type === "settings_updated") {
        refreshRuntime();
        void queryClient.invalidateQueries({ queryKey: ["settings"] });
        void queryClient.invalidateQueries({ queryKey: ["account-identity"] });
        void queryClient.invalidateQueries({ queryKey: ["presets"] });
        void queryClient.invalidateQueries({ queryKey: ["bootstrap"] });
        void queryClient.invalidateQueries({ queryKey: ["stats-link"] });
        void queryClient.invalidateQueries({ queryKey: ["live-stats-link"] });
      }
      if (event.type === "account_identity_updated") {
        void queryClient.invalidateQueries({ queryKey: ["settings"] });
        void queryClient.invalidateQueries({ queryKey: ["account-identity"] });
        void queryClient.invalidateQueries({ queryKey: ["stats-link"] });
        void queryClient.invalidateQueries({ queryKey: ["live-stats-link"] });
      }
      if (event.type === "game_data_updated") {
        for (const queryKey of [
          ["bootstrap"], ["champions"], ["spells"], ["runes"], ["skins"],
          ["diagnostics"], ["game-data-status"],
        ]) {
          void queryClient.invalidateQueries({ queryKey });
        }
      }
      if (event.type === "provider_window") {
        void queryClient.invalidateQueries({ queryKey: ["provider-window-status"] });
      }
      if (event.type === "network_status") {
        void queryClient.invalidateQueries({ queryKey: ["network-status"] });
      }
      if (["summoner_update", "connected", "disconnected"].includes(event.type)) {
        refreshRuntime();
        void queryClient.invalidateQueries({ queryKey: ["settings"] });
        void queryClient.invalidateQueries({ queryKey: ["account-identity"] });
        void queryClient.invalidateQueries({ queryKey: ["stats-link"] });
        void queryClient.invalidateQueries({ queryKey: ["live-stats-link"] });
        void queryClient.invalidateQueries({ queryKey: ["diagnostics"] });
        void queryClient.invalidateQueries({ queryKey: ["game-data-status"] });
      }
      if (["phase_change", "champion_picked", "champion_banned", "spells_set", "toast"].includes(event.type)) void queryClient.invalidateQueries({ queryKey: ["history"] });
    });
    return () => { disposed = true; window.clearInterval(reconciliationTimer); disconnect(); };
  }, [queryClient, setRuntime, setStatus]);

  useEffect(() => {
    let disposed = false;
    let timer: number | undefined;
    const schedule = (delay: number) => {
      timer = window.setTimeout(async () => {
        if (disposed) return;
        try {
          await queryClient.prefetchQuery({ queryKey: ["updates"], queryFn: api.getUpdates, staleTime: UPDATE_CHECK_INTERVAL, retry: false });
        } catch {
          // A failed check is retried on the next scheduled cycle.
        }
        if (!disposed) schedule(UPDATE_CHECK_INTERVAL);
      }, delay);
    };
    schedule(7_000);
    return () => { disposed = true; if (timer !== undefined) window.clearTimeout(timer); };
  }, [queryClient]);
  useEffect(() => { if (activeRoute.page === "dashboard") performance.mark("otp:t7-dashboard-interactive"); }, [activeRoute.page]);

  if (bootstrap.isPending && !bootstrap.data) return <div className="boot-screen"><div className="boot-mark">O</div><strong>{fr.app.name}</strong><span>{fr.common.loading}</span></div>;
  if (bootstrap.isError && !bootstrap.data) return <div className="boot-screen"><div className="state-error"><strong>{fr.app.serverNotResponding}</strong><span>{fr.app.serverHint}</span><Button variant="primary" type="button" onClick={() => void bootstrap.refetch()}>{fr.common.retry}</Button></div></div>;

  if (network.isError) return <div className="boot-screen"><div className="state-error"><strong>{fr.app.serverNotResponding}</strong><span>{fr.app.serverHint}</span><Button variant="primary" type="button" onClick={() => void network.refetch()}>{fr.common.retry}</Button></div></div>;
  const retryNetwork = async () => {
    try {
      const next = await api.checkNetworkStatus();
      queryClient.setQueryData(["network-status"], next);
    } catch {
      await network.refetch();
    }
  };
  const networkWarning = network.isPending || network.data?.state === "checking"
    ? <NetworkWarning state="checking" />
    : network.data?.online === false
      ? <NetworkWarning state="offline" onRetry={() => void retryNetwork()} />
      : null;

  return <AppShell activePage={activeRoute.page} runtime={runtime} version={runtime?.version} updateBanner={<>{networkWarning}<UpdateBanner /></>}>
    <main className="content-area" id="main-content" tabIndex={-1}>
      <div className="page-content"><Suspense fallback={<PageFallback />}>
        {activeRoute.page === "dashboard" && <DashboardPage action={activeRoute.action} onActionClose={() => replaceRoute({ page: "dashboard" })} />}
        {activeRoute.page === "statistics" && <StatisticsPage />}
        {activeRoute.page === "diagnostics" && <DiagnosticsPage />}
        {activeRoute.page === "live" && <LiveStatisticsPage />}
        {activeRoute.page === "history" && <HistoryPage />}
        {activeRoute.page === "settings" && <SettingsPage section={activeRoute.section} onSectionChange={(section) => navigate({ page: "settings", section })} />}
      </Suspense></div>
    </main>
  </AppShell>;
}

export default App;
