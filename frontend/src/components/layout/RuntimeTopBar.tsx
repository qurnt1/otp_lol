import { Activity, Cog, Globe2, UserRound, Wifi, WifiOff } from "lucide-react";

import { fr } from "../../content/fr";
import { connectionLabel, phaseLabel, regionLabel } from "../../domain/runtime";
import type { RuntimeSnapshot } from "../../types/api";

export function RuntimeTopBar({ runtime, onSettings }: { runtime: RuntimeSnapshot | null; onSettings: () => void }) {
  const connected = Boolean(runtime?.connected);
  return (
    <header className="runtime-topbar" aria-label={fr.runtime.topbarLabel}>
      <div className={connected ? "runtime-primary is-connected" : "runtime-primary"}>
        {connected ? <Wifi size={17} aria-hidden="true" /> : <WifiOff size={17} aria-hidden="true" />}
        <span className="runtime-dot" aria-hidden="true" /><strong>{connectionLabel(connected)}</strong>
      </div>
      <div className="runtime-facts">
        <span><UserRound size={14} aria-hidden="true" /><small>{fr.runtime.account}</small><strong>{runtime?.riot_id || "—"}</strong></span>
        <span><Globe2 size={14} aria-hidden="true" /><small>{fr.runtime.region}</small><strong>{regionLabel(runtime?.region)}</strong></span>
        <span><Activity size={14} aria-hidden="true" /><small>{fr.runtime.phase}</small><strong>{connected ? phaseLabel(runtime?.phase) : fr.runtime.notDetected}</strong></span>
      </div>
      <button className="icon-button" type="button" onClick={onSettings} aria-label={fr.nav.settings} title={fr.nav.settings}><Cog size={18} aria-hidden="true" /></button>
    </header>
  );
}
