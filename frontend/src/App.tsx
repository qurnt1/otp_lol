import { lazy, Suspense, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle } from "lucide-react";

import { api } from "./api/client";
import { connectRuntimeEvents } from "./api/events";
import { AppShell } from "./app/AppShell";
import { useHashRoute } from "./app/useHashRoute";
import { RuntimeTopBar } from "./components/layout/RuntimeTopBar";
import { Button } from "./components/ui/button";
import { fr } from "./content/fr";
import { localizeRuntimeStatus } from "./domain/runtimeStatus";
import { useRuntimeStore } from "./stores/runtimeStore";
import type { RuntimeEvent, RuntimeSnapshot } from "./types/api";

const DashboardPage = lazy(() => import("./features/dashboard/DashboardPage").then(({ DashboardPage: page }) => ({ default: page })));
const HistoryPage = lazy(() => import("./features/history/HistoryPage").then(({ HistoryPage: page }) => ({ default: page })));
const PresetsPage = lazy(() => import("./features/presets/PresetsPage").then(({ PresetsPage: page }) => ({ default: page })));
const SettingsPage = lazy(() => import("./features/settings/SettingsPage").then(({ SettingsPage: page }) => ({ default: page })));
const UPDATE_CHECK_KEY = "otp-lol:last-update-check";
const UPDATE_CHECK_INTERVAL = 21_600_000;

function updateRuntimeFromEvent(
  event: RuntimeEvent,
  setRuntime: (runtime: RuntimeSnapshot) => void,
  setStatus: (status: { message: string; level: string; timestamp: string }) => void,
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

function App() {
  const [activePage, navigate] = useHashRoute();
  const queryClient = useQueryClient();
  const setRuntime = useRuntimeStore((state) => state.setRuntime);
  const setStatus = useRuntimeStore((state) => state.setStatus);
  const storedRuntime = useRuntimeStore((state) => state.runtime);
  const bootstrap = useQuery({ queryKey: ["bootstrap"], queryFn: api.getBootstrap, staleTime: Infinity, gcTime: Infinity, retry: 1 });
  const runtime = storedRuntime ?? bootstrap.data?.runtime ?? null;

  useEffect(() => { performance.mark("otp:t5-react-mount"); }, []);
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
        void queryClient.invalidateQueries({ queryKey: ["presets"] });
        void queryClient.invalidateQueries({ queryKey: ["bootstrap"] });
      }
      if (["phase_change", "champion_picked", "champion_banned", "spells_set", "toast"].includes(event.type)) void queryClient.invalidateQueries({ queryKey: ["history"] });
    });
    return () => { disposed = true; window.clearInterval(reconciliationTimer); disconnect(); };
  }, [queryClient, setRuntime, setStatus]);

  useEffect(() => {
    let lastCheck = 0;
    try { lastCheck = Number(window.localStorage.getItem(UPDATE_CHECK_KEY) || 0); } catch { /* storage can be unavailable in a restricted WebView */ }
    const elapsed = Date.now() - lastCheck;
    const delay = lastCheck > 0 && elapsed < UPDATE_CHECK_INTERVAL ? UPDATE_CHECK_INTERVAL - elapsed : 7_000;
    const timer = window.setTimeout(() => {
      void queryClient.prefetchQuery({ queryKey: ["updates"], queryFn: api.getUpdates, staleTime: UPDATE_CHECK_INTERVAL, retry: false }).then(() => {
        try { window.localStorage.setItem(UPDATE_CHECK_KEY, String(Date.now())); } catch { /* best effort only */ }
      }).catch(() => undefined);
    }, delay);
    return () => window.clearTimeout(timer);
  }, [queryClient]);
  useEffect(() => { if (activePage === "dashboard") performance.mark("otp:t7-dashboard-interactive"); }, [activePage]);

  if (bootstrap.isPending && !bootstrap.data) return <div className="boot-screen"><div className="boot-mark">O</div><strong>{fr.app.name}</strong><span>{fr.common.loading}</span></div>;
  if (bootstrap.isError && !bootstrap.data) return <div className="boot-screen"><div className="state-error"><strong>{fr.app.serverNotResponding}</strong><span>{fr.app.serverHint}</span><Button variant="primary" type="button" onClick={() => void bootstrap.refetch()}>{fr.common.retry}</Button></div></div>;

  return <AppShell activePage={activePage} version={runtime?.version}>
    <RuntimeTopBar runtime={runtime} onSettings={() => navigate("settings")} />
    <main className="content-area" id="main-content" tabIndex={-1}>
      <div className="page-content"><Suspense fallback={<PageFallback />}>
        {activePage === "dashboard" && <DashboardPage />}
        {activePage === "presets" && <PresetsPage />}
        {activePage === "history" && <HistoryPage />}
        {activePage === "settings" && <SettingsPage />}
      </Suspense></div>
    </main>
  </AppShell>;
}

export default App;
