import { LoaderCircle } from "lucide-react";

import { fr } from "../../content/fr";
import { cn } from "../../lib/cn";

export interface AutomationItem {
  id: string;
  label: string;
  detail: string;
  enabled: boolean;
  pending: boolean;
  onToggle: () => void;
}

export function AutomationBar({ items }: { items: AutomationItem[] }) {
  return <section className="surface automation-panel" aria-labelledby="automation-heading"><div className="section-head"><div><div className="section-label">{fr.dashboard.automations}</div><h2 id="automation-heading">{fr.dashboard.automations}</h2></div><a className="text-button" href="#settings">{fr.dashboard.manage}</a></div><div className="automation-bar">{items.map((item) => <div className={cn("automation-item", item.enabled && "is-enabled")} key={item.id}><div><strong>{item.label}</strong><small>{item.detail}</small></div><button className="switch" type="button" role="switch" aria-label={item.label} aria-checked={item.enabled} aria-busy={item.pending} disabled={item.pending} onClick={item.onToggle}>{item.pending ? <LoaderCircle size={12} aria-hidden="true" /> : <span aria-hidden="true" />}</button></div>)}</div></section>;
}
