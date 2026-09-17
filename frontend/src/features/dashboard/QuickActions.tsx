import { Activity, BarChart3, ListChecks, Settings2, WandSparkles } from "lucide-react";

import { fr } from "../../content/fr";

export function QuickActions() {
  return <section className="surface quick-panel" aria-labelledby="quick-heading"><div className="section-head"><div><div className="section-label">{fr.dashboard.quickActions}</div><h2 id="quick-heading">{fr.dashboard.quickActions}</h2></div><WandSparkles size={17} aria-hidden="true" /></div><div className="quick-list">
    <a className="quick-link" href="#statistics">{fr.dashboard.stats}<BarChart3 size={13} aria-hidden="true" /></a>
    <a className="quick-link" href="#live">{fr.dashboard.liveStats}<Activity size={13} aria-hidden="true" /></a>
    <a className="quick-link" href="#settings/links">{fr.dashboard.chooseStats}<Settings2 size={13} aria-hidden="true" /></a>
    <a className="quick-link" href="#presets">{fr.dashboard.reviewSequence}<ListChecks size={13} aria-hidden="true" /></a>
    <a className="quick-link" href="#settings/shortcuts">{fr.dashboard.keyboardShortcuts}<span className="key-hint">Alt+C</span></a>
  </div></section>;
}
