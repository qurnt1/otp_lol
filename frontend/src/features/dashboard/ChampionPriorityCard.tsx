import { ChevronDown, Moon, Swords } from "lucide-react";

import { runeAssetUrl, safeImageUrl } from "../../domain/assets";
import { cn } from "../../lib/cn";
import type { Champion, PresetPreview, PresetSlot, SummonerSpell } from "../../types/api";
import { AssetImage } from "../../components/game/AssetImage";

export type MainSkinMode = "inherit" | "none" | "fixed" | "random";

interface ChampionPriorityCardProps {
  slot: PresetSlot | undefined;
  index: number;
  override: MainSkinMode;
  spells: SummonerSpell[];
  preview?: PresetPreview;
  champion?: Champion;
  onOverride: (mode: MainSkinMode) => void;
}

const modes = [
  { value: "inherit", label: "INHERIT" },
  { value: "none", label: "OFF" },
  { value: "fixed", label: "FIXED" },
  { value: "random", label: "RANDOM" },
] as const;

export function ChampionPriorityCard({ slot, index, override, spells, preview, champion, onOverride }: ChampionPriorityCardProps) {
  const championName = slot?.champion?.trim() ?? "";
  const effectiveMode = override === "inherit" ? slot?.skin_mode ?? "none" : override;
  const skinLabel = preview?.skin_name || (effectiveMode === "fixed" ? "Skin fixe" : effectiveMode === "random" ? "Pool aléatoire" : "Sans skin");
  const primarySpell = spells.find((spell) => spell.name === slot?.spell_1);
  const secondarySpell = spells.find((spell) => spell.name === slot?.spell_2);
  const runeIcon = runeAssetUrl(slot?.rune_keystone_path, "perk");
  const subRuneIcon = runeAssetUrl(slot?.rune_sub_style_icon_path, "style");

  return <article className={cn("priority-card", !championName && "is-empty")}>
    <a className="priority-art" href="#presets" aria-label={championName ? `Modifier ${championName}` : "Configurer un champion"}>
      {(preview?.champion_splash_url || champion?.splash_url) && <AssetImage src={safeImageUrl(preview?.champion_splash_url ?? champion?.splash_url) ?? undefined} alt="" width="640" height="340" loading={index === 0 ? "eager" : "lazy"} />}
      <span className="priority-shade" aria-hidden="true" />
      <span className="priority-number">0{index + 1}</span>
      <span className="priority-caption"><h3>{championName || "Configurer un champion"}</h3><small>{champion?.title || (championName ? "Prêt" : "À configurer")}</small></span>
      {!championName && <span className="priority-placeholder"><Swords size={26} aria-hidden="true" /></span>}
    </a>
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
        <label className="mode-select"><span className="sr-only">Mode de skin du slot {index + 1}</span><select value={override} aria-label={`Mode de skin du slot ${index + 1}`} onChange={(event) => onOverride(event.target.value as MainSkinMode)}>{modes.map((mode) => <option key={mode.value} value={mode.value}>{mode.label}</option>)}</select><ChevronDown size={13} aria-hidden="true" /></label>
      </div>
    </div>
  </article>;
}
