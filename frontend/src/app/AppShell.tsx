import type { PropsWithChildren } from "react";
import { BookOpen, LayoutDashboard, Settings2, Swords } from "lucide-react";

import { fr } from "../content/fr";
import { cn } from "../lib/cn";
import type { PageId } from "../types/api";

interface AppShellProps extends PropsWithChildren { activePage: PageId; version?: string }
const navigation = [
  { id: "dashboard", icon: LayoutDashboard, label: fr.nav.dashboard },
  { id: "presets", icon: Swords, label: fr.nav.presets },
  { id: "history", icon: BookOpen, label: fr.nav.history },
  { id: "settings", icon: Settings2, label: fr.nav.settings },
] as const;

export function AppShell({ activePage, version, children }: AppShellProps) {
  return <div className="app-shell">
    <aside className="app-sidebar" aria-label={fr.runtime.navigationLabel}>
      <a className="brand-mark" href="#dashboard" aria-label={fr.app.name}>
        <img src="/assets/app/garen.webp" alt="" width="34" height="34" />
        <span><strong>OTP</strong><small>LOL</small></span>
      </a>
      <nav className="sidebar-nav">{navigation.map(({ id, icon: Icon, label }) => <a key={id} className={cn("sidebar-link", activePage === id && "is-active")} href={`#${id}`} aria-current={activePage === id ? "page" : undefined} title={label}><Icon size={18} aria-hidden="true" /><span>{label}</span></a>)}</nav>
      <div className="sidebar-footer"><span className="sidebar-version">{fr.app.version} {version ? `v${version}` : ""}</span></div>
    </aside>
    <div className="app-workspace">{children}</div>
  </div>;
}
