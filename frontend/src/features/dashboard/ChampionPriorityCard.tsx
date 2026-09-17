import { Moon, Swords } from "lucide-react";

import { runeAssetUrl, safeImageUrl } from "../../domain/assets";
import { cn } from "../../lib/cn";
import type { Champion, PresetPreview, PresetSlot, SummonerSpell } from "../../types/api";
import { AssetImage } from "../../components/game/AssetImage";
import { Select } from "../../components/ui/Select";
import { fr } from "../../content/fr";
import { routeToHash } from "../../app/routes";

export type SkinMode = PresetSlot["skin_mode"];

interface ChampionPriorityCardProps {
  slotKey: "pick_1" | "pick_2" | "pick_3";
  slot: PresetSlot | undefined;
  index: number;
  spells: SummonerSpell[];
  preview?: PresetPreview;
  champion?: Champion;
  onSkinModeChange: (mode: SkinMode) => void;
  pending?: boolean;
}

const modes = [
  { id: "none", label: fr.presets.skinNone },
  { id: "fixed", label: fr.presets.skinFixed },
  { id: "random", label: fr.presets.skinRandom },
] as const;

export function ChampionPriorityCard({ slotKey, slot, index, spells, preview, champion, onSkinModeChange, pending = false }: ChampionPriorityCardProps) {
  const championName = slot?.champion?.trim() ?? "";
  const skinMode = slot?.skin_mode ?? "none";
  const skinLabel = skinMode === "fixed" ? preview?.skin_name || fr.presets.skinFixed : skinMode === "random" ? fr.presets.skinRandom : fr.presets.skinNone;
  const primarySpell = spells.find((spell) => spell.name === slot?.spell_1);
  const secondarySpell = spells.find((spell) => spell.name === slot?.spell_2);
  const runeIcon = runeAssetUrl(slot?.rune_keystone_path, "perk");
  const subRuneIcon = runeAssetUrl(slot?.rune_sub_style_icon_path, "style");
  const splashUrl = safeImageUrl(skinMode === "none" ? null : preview?.skin_preview_url)
    ?? safeImageUrl(preview?.champion_splash_url)
    ?? safeImageUrl(champion?.splash_url);

  return <article className={cn("priority-card", !championName && "is-empty")}>
    <a className="priority-card-link" href={routeToHash({ page: "presets", action: slotKey })} aria-label={`${championName ? `Modifier ${championName}` : "Configurer un champion"}, preset ${index + 1}`}>
      <div className="priority-art">
      {splashUrl && <AssetImage src={splashUrl} alt="" width="640" height="340" loading={index === 0 ? "eager" : "lazy"} />}
      <span className="priority-shade" aria-hidden="true" />
      <span className="priority-number">0{index + 1}</span>
      <span className="priority-caption"><h3>{championName || "Configurer un champion"}</h3><small>{champion?.title || (championName ? "Prêt" : "À configurer")}</small></span>
      {!championName && <span className="priority-placeholder"><Swords size={26} aria-hidden="true" /></span>}
      </div>
      <div className="priority-details">
      <div className="asset-row" aria-label="Sorts d’invocateur et rune">
        <span className="asset-pair">
          <AssetImage src={safeImageUrl(preview?.spell_1_url ?? primarySpell?.icon_url) ?? undefined} alt={slot?.spell_1 || "Sort 1"} title={slot?.spell_1 || "Sort 1"} width="30" height="30" fallback="S1" />
          <AssetImage src={safeImageUrl(preview?.spell_2_url ?? secondarySpell?.icon_url) ?? undefined} alt={slot?.spell_2 || "Sort 2"} title={slot?.spell_2 || "Sort 2"} width="30" height="30" fallback="S2" />
        </span>
        <span className="asset-pair">
          <AssetImage src={runeIcon ?? undefined} alt={slot?.rune_page_name || "Rune principale"} title={slot?.rune_page_name || "Rune principale"} width="30" height="30" loading="lazy" fallback="R" />
          {subRuneIcon && <AssetImage src={subRuneIcon} alt="Rune secondaire" title="Rune secondaire" width="22" height="22" loading="lazy" fallback="" />}
        </span>
        <span className="rune-name">{slot?.rune_page_name || "Runes par défaut"}</span>
      </div>
      <div className="skin-preview">
        <AssetImage src={safeImageUrl(preview?.skin_preview_url) ?? undefined} alt="" width="62" height="34" loading="lazy" fallback={<Moon size={15} aria-hidden="true" />} />
        <span><small>SKIN</small><strong>{skinLabel}</strong></span>
      </div>
      </div>
    </a>
    <div className="mode-select priority-mode-select"><Select className="priority-mode-trigger" label={`Mode de skin du slot ${index + 1}`} value={skinMode} options={modes} disabled={pending} onChange={(value) => onSkinModeChange(value as SkinMode)} /></div>
  </article>;
}
