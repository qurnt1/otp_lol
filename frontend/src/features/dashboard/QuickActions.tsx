import { ExternalLink, ListChecks, WandSparkles } from "lucide-react";

import { fr } from "../../content/fr";
import { openExternalUrl } from "../../domain/external";

export function QuickActions({ statsUrl }: { statsUrl: string | null | undefined }) {
  return <section className="surface quick-panel" aria-labelledby="quick-heading"><div className="section-head"><div><div className="section-label">{fr.dashboard.quickActions}</div><h2 id="quick-heading">{fr.dashboard.quickActions}</h2></div><WandSparkles size={17} aria-hidden="true" /></div><div className="quick-list">
    {statsUrl ? <a className="quick-link" href={statsUrl} onClick={(event) => { event.preventDefault(); void openExternalUrl(statsUrl); }}>{fr.dashboard.stats}<ExternalLink size={13} aria-hidden="true" /></a> : <a className="quick-link" href="#settings">{fr.dashboard.chooseStats}<ExternalLink size={13} aria-hidden="true" /></a>}
    <a className="quick-link" href="#presets">{fr.dashboard.reviewSequence}<ListChecks size={13} aria-hidden="true" /></a>
    <a className="quick-link" href="#settings">{fr.dashboard.keyboardShortcuts}<span className="key-hint">Alt+C</span></a>
  </div></section>;
}
