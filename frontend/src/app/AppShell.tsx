import type { PropsWithChildren, ReactNode } from "react";
import { Activity, BarChart3, BookOpen, LayoutDashboard, UserRound, Wifi, WifiOff, Settings2 } from "lucide-react";

import { fr } from "../content/fr";
import { cn } from "../lib/cn";
import type { PageId, RuntimeSnapshot } from "../types/api";

interface AppShellProps extends PropsWithChildren { activePage: PageId; runtime?: RuntimeSnapshot | null; version?: string; updateBanner?: ReactNode }
const navigation = [
  { id: "dashboard", icon: LayoutDashboard, label: fr.nav.dashboard },
  { id: "statistics", icon: BarChart3, label: fr.nav.statistics },
  { id: "live", icon: Activity, label: fr.nav.live },
  { id: "history", icon: BookOpen, label: fr.nav.history },
  { id: "settings", icon: Settings2, label: fr.nav.settings },
] as const;

export function AppShell({ activePage, runtime, version, updateBanner, children }: AppShellProps) {
  const connected = Boolean(runtime?.connected);
  const account = connected ? runtime?.riot_id || fr.runtime.noAccount : fr.runtime.noAccount;
  return <div className="app-shell">
    <aside className="app-sidebar" aria-label={fr.runtime.navigationLabel}>
      <a className="brand-mark" href="#dashboard" aria-label={fr.app.name}>
        <img src="/assets/app/garen.webp" alt="" width="34" height="34" />
        <span><strong>OTP</strong><small>LOL</small></span>
      </a>
      <nav className="sidebar-nav">{navigation.map(({ id, icon: Icon, label }) => <a key={id} className={cn("sidebar-link", activePage === id && "is-active")} href={id === "settings" ? "#settings/general" : `#${id}`} aria-current={activePage === id ? "page" : undefined} title={label}><Icon size={18} aria-hidden="true" /><span>{label}</span></a>)}</nav>
      <div className="sidebar-footer">
        <div className={connected ? "sidebar-runtime is-connected" : "sidebar-runtime"} role="status" aria-label={connected ? fr.runtime.connected : fr.runtime.waiting} title={connected ? fr.runtime.connected : fr.runtime.waiting}>
          {connected ? <Wifi size={13} aria-hidden="true" /> : <WifiOff size={13} aria-hidden="true" />}
          <span className="sidebar-runtime-dot" aria-hidden="true" />
          <strong>{connected ? fr.runtime.connected : fr.runtime.waiting}</strong>
        </div>
        <div className="sidebar-account" title={account}><UserRound size={13} aria-hidden="true" /><span>{account}</span></div>
        <span className="sidebar-version">{fr.app.version} {version ? `v${version}` : ""}</span>
      </div>
    </aside>
    <div className="app-workspace">
      {updateBanner}
      {children}
    </div>
  </div>;
}
