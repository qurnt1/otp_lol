import { useMemo } from "react";
import { Check, CircleOff } from "lucide-react";

import { fr } from "../../content/fr";
import { runeAssetUrl, safeImageUrl } from "../../domain/assets";
import { cn } from "../../lib/cn";
import type { PresetSlot, RunePage, RunesResponse } from "../../types/api";
import { AssetImage } from "../../components/game/AssetImage";

export function RunePicker({ slot, runes, onUpdate }: { slot: PresetSlot; runes: RunesResponse; onUpdate: (values: Partial<PresetSlot>) => void }) {
  const page = slot.rune_page_id > 0 ? runes.pages.find((item) => item.id === slot.rune_page_id) : undefined;
  const savedPageMissing = slot.rune_page_id > 0 && !page;
  const perkById = useMemo(() => new Map(Object.values(runes.styles).flatMap((style) => style.perks.map((perk) => [perk.id, perk]))), [runes.styles]);
  const primaryStyle = page ? runes.styles[String(page.primaryStyleId)] : undefined;
  const secondaryStyle = page ? runes.styles[String(page.subStyleId)] : undefined;
  const selectNone = () => onUpdate({
    rune_page_id: 0,
    rune_page_name: "",
    rune_keystone_id: 0,
    rune_keystone_path: "",
    rune_sub_style_icon_path: "",
  });
  const selectPage = (next: RunePage) => {
    const keystoneId = next.selectedPerkIds[0] ?? 0;
    const keystone = perkById.get(keystoneId);
    const subStyle = runes.styles[String(next.subStyleId)];
    onUpdate({
      rune_page_id: next.id,
      rune_page_name: next.name,
      rune_keystone_id: keystoneId,
      rune_keystone_path: keystone?.iconPath ?? "",
      rune_sub_style_icon_path: subStyle?.iconPath ?? "",
    });
  };
  return <div className="rune-picker">
    <div className="rune-picker-head"><div><span className="section-label">{fr.presets.runePage}</span><h3>{page?.name || (savedPageMissing ? fr.presets.runeMissing : fr.presets.runeNone)}</h3></div><span className="field-hint">{fr.presets.runeCapacity}</span></div>
    {!runes.available && <div className="picker-empty"><CircleOff size={18} aria-hidden="true" /><strong>{fr.presets.runesUnavailable}</strong><span>{fr.presets.runesUnavailableHint}</span></div>}
    {savedPageMissing && <div className="state-error" role="alert"><strong>{fr.presets.runeMissing}</strong><span>{fr.presets.runeMissingHint}</span></div>}
    <div className="rune-pages">
      <button className={cn("rune-page-option", slot.rune_page_id === 0 && "is-selected")} aria-pressed={slot.rune_page_id === 0} type="button" onClick={selectNone}>
        <span>{slot.rune_page_id === 0 ? <Check size={13} aria-hidden="true" /> : <CircleOff size={15} aria-hidden="true" />}</span>
        <strong>{fr.presets.runeNone}</strong>
        <small>{fr.presets.runeNoneHint}</small>
      </button>
      {runes.available && runes.pages.map((item) => <RunePageOption key={item.id} item={item} selected={item.id === slot.rune_page_id} perkById={perkById} onSelect={selectPage} />)}
    </div>
    {page && <div className="rune-loadout"><RuneGroup label={fr.presets.primaryTree} style={primaryStyle} ids={page.selectedPerkIds.slice(0, 4)} perkById={perkById} /><RuneGroup label={fr.presets.secondaryTree} style={secondaryStyle} ids={page.selectedPerkIds.slice(4, 6)} perkById={perkById} /><RuneGroup label={fr.presets.shards} ids={page.selectedPerkIds.slice(6, 9)} perkById={perkById} /></div>}
  </div>;
}

function RunePageOption({ item, selected, perkById, onSelect }: { item: RunePage; selected: boolean; perkById: Map<number, { id: number; name: string; icon_url?: string | null; iconPath: string }>; onSelect: (page: RunePage) => void }) {
  const keystoneId = item.selectedPerkIds[0] ?? 0;
  const keystone = perkById.get(keystoneId);
  const icon = keystoneId > 0 ? `/api/assets/runes/perk/${keystoneId}.png` : runeAssetUrl(keystone?.iconPath, "perk");
  return <button className={cn("rune-page-option", selected && "is-selected")} aria-pressed={selected} type="button" onClick={() => onSelect(item)}>
    <span>{selected ? <Check size={13} aria-hidden="true" /> : ""}</span>
    <AssetImage src={safeImageUrl(icon) ?? undefined} alt="" width="28" height="28" fallback={<CircleOff size={15} aria-hidden="true" />} />
    <strong>{item.name}</strong>
    <small>{keystone?.name ? `${keystone.name} · ` : ""}{item.selectedPerkIds.length} {fr.presets.runesSelected}</small>
  </button>;
}

function RuneGroup({ label, style, ids, perkById }: { label: string; style?: { name: string; icon_url?: string | null; iconPath: string }; ids: number[]; perkById: Map<number, { id: number; name: string; icon_url?: string | null; iconPath: string }> }) {
  return <section className="rune-group"><div className="rune-group-title">{style?.icon_url && <AssetImage src={safeImageUrl(style.icon_url) ?? undefined} alt="" width="24" height="24" fallback="" />}<span>{label}</span>{style?.name && <strong>{style.name}</strong>}</div><div className="rune-icons">{ids.map((id) => { const perk = perkById.get(id); return <span className="rune-icon-wrap" key={id}><AssetImage src={safeImageUrl(perk?.icon_url) ?? `/api/assets/runes/perk/${id}.png`} alt={perk?.name || "Rune"} title={perk?.name} width="32" height="32" fallback="R" /></span>; })}</div></section>;
}
