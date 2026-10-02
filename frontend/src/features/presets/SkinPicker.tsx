import { useMemo, useState } from "react";
import { Check, CircleOff } from "lucide-react";

import { fr } from "../../content/fr";
import { safeImageUrl } from "../../domain/assets";
import { cn } from "../../lib/cn";
import type { PresetSlot, Skin, SkinsResponse } from "../../types/api";
import { AssetImage } from "../../components/game/AssetImage";
import { selectAllVisibleSkins, updateSkinPool } from "./picker-utils";

export function SkinPicker({ slot, skins, onUpdate }: { slot: PresetSlot; skins: SkinsResponse; onUpdate: (values: Partial<PresetSlot>) => void }) {
  const [ownedOnly, setOwnedOnly] = useState(skins.owned.ok);
  const ownedIds = useMemo(() => new Set(skins.owned.owned_skins.map((skin) => skin.skin_id)), [skins.owned.owned_skins]);
  const visibleSkins = useMemo(() => skins.catalog.filter((skin) => !ownedOnly || !skins.owned.ok || skin.skin_num === 0 || ownedIds.has(skin.skin_id)), [ownedIds, ownedOnly, skins.catalog, skins.owned.ok]);
  const poolIds = useMemo(() => new Set(slot.random_skin_pool.map((skin) => skin.skin_id)), [slot.random_skin_pool]);
  const updatePool = (skin: Skin, checked: boolean) => {
    const pool = updateSkinPool(slot.random_skin_pool, skins.catalog, skin, checked);
    const first = pool[0];
    onUpdate({ random_skin_pool: pool, random_skin_id: first?.skin_id ?? 0, random_skin_name: first?.skin_name ?? "", random_skin_num: first?.skin_num ?? 0 });
  };
  const selectAll = () => {
    const pool = selectAllVisibleSkins(slot.random_skin_pool, visibleSkins);
    const first = pool[0];
    onUpdate({ random_skin_pool: pool, random_skin_id: first?.skin_id ?? 0, random_skin_name: first?.skin_name ?? "", random_skin_num: first?.skin_num ?? 0 });
  };
  return <div className="skin-picker">
    {slot.skin_mode === "none" ? <div className="picker-empty"><CircleOff size={22} aria-hidden="true" /><strong>{fr.presets.skinDisabled}</strong><span>{fr.presets.skinDisabledHint}</span></div> : <><div className="picker-toolbar"><label className="check-control"><input type="checkbox" checked={ownedOnly} onChange={(event) => setOwnedOnly(event.target.checked)} />{fr.presets.ownedOnly}</label><span className="field-hint">{visibleSkins.length} {fr.presets.skinsFound}</span>{slot.skin_mode === "random" && <><span className="pool-count">{poolIds.size} {fr.presets.selectedCount}</span><button className="filter-button" type="button" onClick={selectAll}>{fr.presets.selectAll}</button><button className="filter-button" type="button" onClick={() => onUpdate({ random_skin_pool: [], random_skin_id: 0, random_skin_name: "", random_skin_num: 0 })}>{fr.presets.clearAll}</button></>}</div>{skins.owned.ok !== true && ownedOnly && <p className="field-hint">{fr.presets.ownedFallback}</p>}<div className="skin-grid">{visibleSkins.map((skin) => { const selected = slot.skin_mode === "fixed" ? slot.skin_id === skin.skin_id : poolIds.has(skin.skin_id); return <div className={cn("skin-option", selected && "is-selected")} key={skin.skin_id}>{slot.skin_mode === "random" && <input type="checkbox" checked={selected} aria-label={`${skin.skin_name || fr.presets.skinNone}`} onChange={(event) => updatePool(skin, event.target.checked)} />}<AssetImage src={safeImageUrl(skin.tile_url) ?? undefined} alt="" width="130" height="68" fallback={<span>SKIN</span>} /><div><strong>{skin.skin_name || fr.presets.skinNone}</strong>{selected && <Check size={14} aria-hidden="true" />}</div>{slot.skin_mode === "fixed" && <button className="skin-select-button" type="button" onClick={() => onUpdate({ skin_id: skin.skin_id, skin_name: skin.skin_name, skin_num: skin.skin_num })}>{selected ? fr.presets.selected : fr.presets.choose}</button>}</div>; })}{!visibleSkins.length && <span className="empty-state">{fr.presets.noSkins}</span>}</div></>}
  </div>;
}
