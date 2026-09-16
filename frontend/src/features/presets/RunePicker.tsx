import { useMemo } from "react";
import { Check, CircleOff } from "lucide-react";

import { fr } from "../../content/fr";
import { safeImageUrl } from "../../domain/assets";
import { cn } from "../../lib/cn";
import type { PresetSlot, RunePage, RunesResponse } from "../../types/api";
import { AssetImage } from "../../components/game/AssetImage";

export function RunePicker({ slot, runes, onUpdate }: { slot: PresetSlot; runes: RunesResponse; onUpdate: (values: Partial<PresetSlot>) => void }) {
  const page = runes.pages.find((item) => item.id === slot.rune_page_id);
  const perkById = useMemo(() => new Map(Object.values(runes.styles).flatMap((style) => style.perks.map((perk) => [perk.id, perk]))), [runes.styles]);
  const primaryStyle = page ? runes.styles[String(page.primaryStyleId)] : undefined;
  const secondaryStyle = page ? runes.styles[String(page.subStyleId)] : undefined;
  const selectPage = (next: RunePage) => {
    const keystone = perkById.get(next.selectedPerkIds[0]);
    const subStyle = runes.styles[String(next.subStyleId)];
    onUpdate({ rune_page_id: next.id, rune_page_name: next.name, rune_keystone_path: keystone?.iconPath ?? "", rune_sub_style_icon_path: subStyle?.iconPath ?? "" });
  };
  if (!runes.available) return <div className="picker-empty"><CircleOff size={22} aria-hidden="true" /><strong>{fr.presets.runesUnavailable}</strong><span>{fr.presets.runesUnavailableHint}</span></div>;
  return <div className="rune-picker"><div className="rune-picker-head"><div><span className="section-label">{fr.presets.runePage}</span><h3>{page?.name || fr.presets.chooseRunePage}</h3></div><span className="field-hint">{fr.presets.runeCapacity}</span></div><div className="rune-pages">{runes.pages.map((item) => <button className={cn("rune-page-option", item.id === slot.rune_page_id && "is-selected")} aria-pressed={item.id === slot.rune_page_id} type="button" key={item.id} onClick={() => selectPage(item)}><span>{item.id === slot.rune_page_id ? <Check size={13} aria-hidden="true" /> : ""}</span><strong>{item.name}</strong><small>{item.selectedPerkIds.length} {fr.presets.runesSelected}</small></button>)}</div>{page && <div className="rune-loadout"><RuneGroup label={fr.presets.primaryTree} style={primaryStyle} ids={page.selectedPerkIds.slice(0, 4)} perkById={perkById} /><RuneGroup label={fr.presets.secondaryTree} style={secondaryStyle} ids={page.selectedPerkIds.slice(4, 6)} perkById={perkById} /><RuneGroup label={fr.presets.shards} ids={page.selectedPerkIds.slice(6, 9)} perkById={perkById} /></div>}</div>;
}

function RuneGroup({ label, style, ids, perkById }: { label: string; style?: { name: string; icon_url?: string | null; iconPath: string }; ids: number[]; perkById: Map<number, { id: number; name: string; icon_url?: string | null; iconPath: string }> }) {
  return <section className="rune-group"><div className="rune-group-title">{style?.icon_url && <AssetImage src={safeImageUrl(style.icon_url) ?? undefined} alt="" width="24" height="24" fallback="" />}<span>{label}</span>{style?.name && <strong>{style.name}</strong>}</div><div className="rune-icons">{ids.map((id) => { const perk = perkById.get(id); return <span className="rune-icon-wrap" key={id}><AssetImage src={safeImageUrl(perk?.icon_url) ?? `/api/assets/runes/perk/${id}.png`} alt={perk?.name || "Rune"} title={perk?.name} width="32" height="32" fallback="R" /></span>; })}</div></section>;
}
