import { Ban, Pencil } from "lucide-react";
import type { Ref } from "react";

import { safeImageUrl } from "../../domain/assets";
import { fr } from "../../content/fr";
import type { Champion, PresetPreview } from "../../types/api";
import { AssetImage } from "../../components/game/AssetImage";
import { routeToHash } from "../../app/routes";

export function BanPanel({ banName, autoBanEnabled, preview, champion, isOpen = false, triggerRef }: { banName: string; autoBanEnabled: boolean; preview?: PresetPreview | null; champion?: Champion; isOpen?: boolean; triggerRef?: Ref<HTMLAnchorElement> }) {
  const hasBan = banName !== fr.dashboard.noBan;
  const iconUrl = preview?.champion_icon_url ?? champion?.icon_url;
  return <a ref={triggerRef} id="dashboard-edit-ban" className="surface ban-panel ban-panel-link" href={routeToHash({ page: "dashboard", action: "ban" })} aria-haspopup="dialog" aria-expanded={isOpen} aria-label={`${fr.dashboard.edit} ${fr.dashboard.ban.toLocaleLowerCase()} : ${banName}`}>
    <div className="section-head"><div><div className="section-label">{fr.dashboard.ban}</div><h2 id="ban-heading">{banName}</h2></div><Ban size={17} aria-hidden="true" /></div>
    <div className="ban-visual"><AssetImage src={safeImageUrl(iconUrl) ?? undefined} alt={hasBan ? banName : ""} width="74" height="74" fallback={<Ban size={23} aria-hidden="true" />} /><div><strong>{autoBanEnabled ? fr.dashboard.enabled : fr.dashboard.disabled}</strong><small>{hasBan ? fr.dashboard.banApplied : fr.dashboard.banConfigure}</small></div></div>
    <span className="text-button"><Pencil size={13} aria-hidden="true" />{fr.dashboard.edit}</span>
  </a>;
}
