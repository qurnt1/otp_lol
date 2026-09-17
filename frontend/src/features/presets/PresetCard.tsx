import { Dices, Sparkles, Swords } from "lucide-react";
import type { Ref } from "react";

import { AssetImage } from "../../components/game/AssetImage";
import { fr } from "../../content/fr";
import { runeAssetUrl, safeImageUrl } from "../../domain/assets";
import { cn } from "../../lib/cn";
import type { Champion, PresetPreview, PresetSlot, SummonerSpell } from "../../types/api";

export type PresetSlotKey = "pick_1" | "pick_2" | "pick_3";

export function PresetCard({
  slotKey,
  slot,
  index,
  champion,
  preview,
  spells,
  isOpen,
  onOpen,
  triggerRef,
}: {
  slotKey: PresetSlotKey;
  slot: PresetSlot;
  index: number;
  champion?: Champion;
  preview?: PresetPreview;
  spells: SummonerSpell[];
  isOpen: boolean;
  onOpen: (slotKey: PresetSlotKey, trigger: HTMLButtonElement) => void;
  triggerRef?: Ref<HTMLButtonElement>;
}) {
  const championName = slot.champion.trim();
  const skin = getSelectedSkin(slot);
  const generatedSkinSplash = skin && skin.id > 0 && skin.num > 0 && champion?.id
    ? `/api/assets/skins/${champion.id}/${skin.id}/splash?skin_num=${skin.num}`
    : undefined;
  const matchingPreview = preview && skin && preview.skin_name?.toLocaleLowerCase() === skin.name.toLocaleLowerCase()
    ? preview.skin_preview_url
    : undefined;
  const splashUrl = slot.skin_mode === "none"
    ? champion?.splash_url ?? preview?.champion_splash_url
    : matchingPreview ?? generatedSkinSplash ?? champion?.splash_url ?? preview?.champion_splash_url;
  const spellOne = spells.find((spell) => spell.name === slot.spell_1);
  const spellTwo = spells.find((spell) => spell.name === slot.spell_2);
  const runeUrl = runeAssetUrl(slot.rune_keystone_path, "perk");
  const skinLabel = !skin ? fr.presets.skinNone : slot.skin_mode === "random" ? fr.presets.skinRandom : skin.name || fr.presets.skinFixed;

  return (
    <button
      ref={triggerRef}
      className={cn("preset-card", !championName && "is-empty")}
      type="button"
      aria-haspopup="dialog"
      aria-expanded={isOpen}
      aria-label={`${fr.presets.editPreset} ${fr.presets.priority} ${index + 1} · ${championName || fr.presets.selectChampion}`}
      onClick={(event) => onOpen(slotKey, event.currentTarget)}
    >
      <span className="preset-card-art">
        <AssetImage src={safeImageUrl(splashUrl) ?? undefined} alt="" width="620" height="220" loading="lazy" />
        <span className="preset-card-shade" aria-hidden="true" />
        <span className="preset-priority">{fr.presets.priority}{" "}<strong>{index + 1}</strong></span>
        <span className="preset-card-title">
          <strong>{championName || fr.presets.selectChampion}</strong>
          {champion?.title && <small>{champion.title}</small>}
        </span>
        {!championName && <Swords className="preset-card-placeholder" size={25} aria-hidden="true" />}
      </span>
      <span className="preset-card-content">
        <span className="preset-summary-row preset-summary-spells">
          <AssetImage src={spellOne?.icon_url ?? undefined} alt="" title={slot.spell_1 || fr.common.none} width="26" height="26" fallback={<span aria-hidden="true">1</span>} />
          <AssetImage src={spellTwo?.icon_url ?? undefined} alt="" title={slot.spell_2 || fr.common.none} width="26" height="26" fallback={<span aria-hidden="true">2</span>} />
          <span>{slot.spell_1 || fr.common.none} · {slot.spell_2 || fr.common.none}</span>
        </span>
        <span className="preset-summary-row preset-summary-runes">
          <Sparkles size={14} aria-hidden="true" />
          <small>{fr.dashboard.runes}</small>
          <span>{slot.rune_page_name || fr.common.default} · {slot.rune_auto_apply ? fr.presets.autoShort : fr.presets.manualShort}</span>
        </span>
        <span className="preset-summary-row preset-summary-skin">
          {slot.skin_mode === "random" ? <Dices size={14} aria-hidden="true" /> : <Swords size={14} aria-hidden="true" />}
          <small>{fr.dashboard.skin}</small>
          <strong>{skinLabel}</strong>
        </span>
      </span>
    </button>
  );
}

function getSelectedSkin(slot: PresetSlot) {
  if (slot.skin_mode === "fixed") return { id: slot.skin_id, num: slot.skin_num, name: slot.skin_name };
  if (slot.skin_mode === "random") {
    const firstPoolSkin = slot.random_skin_pool[0];
    return {
      id: slot.random_skin_id || firstPoolSkin?.skin_id || 0,
      num: slot.random_skin_num || firstPoolSkin?.skin_num || 0,
      name: slot.random_skin_name || firstPoolSkin?.skin_name || fr.presets.skinRandom,
    };
  }
  return null;
}
