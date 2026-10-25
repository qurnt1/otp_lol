import { ArrowDown, ArrowUp, CircleOff, GripVertical, Moon, Swords } from "lucide-react";
import { useState, type Ref } from "react";

import { runeAssetUrl, safeImageUrl } from "../../domain/assets";
import { cn } from "../../lib/cn";
import type { Champion, PresetPreview, PresetSlot, SummonerSpell } from "../../types/api";
import type { PresetSlotKey } from "../../domain/presets";
import { AssetImage } from "../../components/game/AssetImage";
import { fr } from "../../content/fr";
import { routeToHash } from "../../app/routes";

interface ChampionPriorityCardProps {
  slotKey: PresetSlotKey;
  slot: PresetSlot | undefined;
  index: number;
  spells: SummonerSpell[];
  preview?: PresetPreview;
  champion?: Champion;
  isOpen?: boolean;
  triggerRef?: Ref<HTMLAnchorElement>;
  reorderDisabled?: boolean;
  isDragging?: boolean;
  onMove?: (slotKey: PresetSlotKey, delta: -1 | 1) => void;
  onDragStart?: (slotKey: PresetSlotKey) => void;
  onDragEnd?: () => void;
  onDrop?: (source: PresetSlotKey, target: PresetSlotKey) => void;
}

export function ChampionPriorityCard({ slotKey, slot, index, spells, preview, champion, isOpen = false, triggerRef, reorderDisabled = false, isDragging = false, onMove, onDragStart, onDragEnd, onDrop }: ChampionPriorityCardProps) {
  const [isDropTarget, setIsDropTarget] = useState(false);
  const championName = slot?.champion?.trim() ?? "";
  const skinMode = slot?.skin_mode ?? "none";
  const skinLabel = skinMode === "fixed" ? preview?.skin_name || fr.presets.skinFixed : skinMode === "random" ? fr.presets.skinRandom : fr.presets.skinNone;
  const championSubtitle = championName ? champion?.title : "À configurer";
  const primarySpell = spells.find((spell) => spell.name === slot?.spell_1);
  const secondarySpell = spells.find((spell) => spell.name === slot?.spell_2);
  const runeKeystoneId = slot?.rune_keystone_id ?? 0;
  const runeIcon = runeKeystoneId > 0
    ? `/api/assets/runes/perk/${runeKeystoneId}.png`
    : runeAssetUrl(slot?.rune_keystone_path, "perk");
  const subRuneIcon = runeAssetUrl(slot?.rune_sub_style_icon_path, "style");
  const championIconUrl = safeImageUrl(preview?.champion_icon_url) ?? safeImageUrl(champion?.icon_url);
  const splashUrl = safeImageUrl(skinMode === "none" ? null : preview?.skin_preview_url)
    ?? safeImageUrl(preview?.champion_splash_url)
    ?? safeImageUrl(champion?.splash_url);

  return <article className={cn("priority-card", !championName && "is-empty", isDragging && "is-dragging", isDropTarget && "is-drop-target")} onDragEnter={() => { if (!reorderDisabled) setIsDropTarget(true); }} onDragLeave={(event) => {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setIsDropTarget(false);
  }} onDragOver={(event) => { if (!reorderDisabled) event.preventDefault(); }} onDrop={(event) => {
    event.preventDefault();
    setIsDropTarget(false);
    const source = event.dataTransfer.getData("text/plain") as PresetSlotKey;
    if (source && source !== slotKey) onDrop?.(source, slotKey);
  }}>
    <div className="priority-card-order" role="group" aria-label={`Réordonner le preset ${index + 1}`}>
      <button className="priority-card-drag" type="button" draggable={!reorderDisabled} disabled={reorderDisabled} aria-label={`${fr.dashboard.dragPriority} : ${championName || fr.dashboard.configure}`} title={fr.dashboard.dragPriority} onDragStart={(event) => {
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", slotKey);
        onDragStart?.(slotKey);
      }} onDragEnd={onDragEnd}>
        <GripVertical size={15} aria-hidden="true" />
      </button>
      <button className="priority-card-order-button" type="button" disabled={reorderDisabled || index === 0} aria-label={`${fr.dashboard.movePriorityUp} : ${championName || fr.dashboard.configure}`} title={fr.dashboard.movePriorityUp} onClick={() => onMove?.(slotKey, -1)}><ArrowUp size={13} aria-hidden="true" /></button>
      <button className="priority-card-order-button" type="button" disabled={reorderDisabled || index === 2} aria-label={`${fr.dashboard.movePriorityDown} : ${championName || fr.dashboard.configure}`} title={fr.dashboard.movePriorityDown} onClick={() => onMove?.(slotKey, 1)}><ArrowDown size={13} aria-hidden="true" /></button>
    </div>
    <a ref={triggerRef} className="priority-card-link" href={routeToHash({ page: "dashboard", action: slotKey })} aria-haspopup="dialog" aria-expanded={isOpen} aria-disabled={reorderDisabled} aria-label={`${championName ? `Modifier ${championName}` : "Configurer un champion"}, preset ${index + 1}`} onClick={(event) => { if (reorderDisabled) event.preventDefault(); }}>
      <div className="priority-art">
      {splashUrl && <AssetImage src={splashUrl} alt="" width="640" height="340" loading={index === 0 ? "eager" : "lazy"} />}
      <span className="priority-shade" aria-hidden="true" />
      <span className="priority-number">0{index + 1}</span>
      <span className="priority-caption"><h3>{championName || "Configurer un champion"}</h3>{championSubtitle && <small>{championSubtitle}</small>}</span>
      {!championName && <span className="priority-placeholder"><Swords size={26} aria-hidden="true" /></span>}
      </div>
      <div className="priority-details">
      <div className="asset-row summoner-row" aria-label="Sorts d’invocateur">
        <span className="asset-pair">
          <AssetImage src={safeImageUrl(preview?.spell_1_url ?? primarySpell?.icon_url) ?? undefined} alt={slot?.spell_1 || "Sort 1"} title={slot?.spell_1 || "Sort 1"} width="30" height="30" fallback="S1" />
          <AssetImage src={safeImageUrl(preview?.spell_2_url ?? secondarySpell?.icon_url) ?? undefined} alt={slot?.spell_2 || "Sort 2"} title={slot?.spell_2 || "Sort 2"} width="30" height="30" fallback="S2" />
        </span>
      </div>
      <div className="asset-row rune-row" aria-label="Runes">
        <span className="asset-pair">
          <AssetImage className="rune-asset" src={runeIcon ?? undefined} alt={slot?.rune_page_name || fr.presets.runeNoneHint} title={slot?.rune_page_name || fr.presets.runeNoneHint} width="30" height="30" loading="lazy" fallback={<CircleOff size={15} aria-hidden="true" />} />
          {subRuneIcon && <AssetImage className="rune-asset" src={subRuneIcon} alt="Rune secondaire" title="Rune secondaire" width="22" height="22" loading="lazy" fallback="" />}
        </span>
        <span className="rune-name" title={slot?.rune_page_name || fr.presets.runeNoneHint}>{slot?.rune_page_name || fr.presets.runeNoneHint}</span>
      </div>
      <div className="skin-preview">
        <AssetImage src={championIconUrl ?? undefined} alt="" width="34" height="34" loading="lazy" fallback={<Moon size={15} aria-hidden="true" />} />
        <span><small>SKIN</small><strong>{skinLabel}</strong></span>
      </div>
      </div>
    </a>
  </article>;
}
