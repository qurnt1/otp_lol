import type { ReactNode, RefObject } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { ChevronRight, CircleOff, Sparkles, Swords, X } from "lucide-react";

import { AssetImage } from "../../components/game/AssetImage";
import { Select } from "../../components/ui/Select";
import { fr } from "../../content/fr";
import { presetAutomationCopy } from "../../content/presetAutomation";
import { runeAssetUrl, safeImageUrl } from "../../domain/assets";
import type { Champion, PresetPreview, PresetSlot, SummonerSpell } from "../../types/api";
import type { PresetSlotKey } from "./PresetCard";

export function PresetEditorDialog({
  open,
  slotKey,
  slot,
  priority,
  champion,
  preview,
  spells,
  pending,
  feedback,
  leagueConnected,
  presetAutomationsEnabled,
  returnFocusRef,
  championChoiceRef,
  onClose,
  onOpenPicker,
  onUpdate,
  children,
}: {
  open: boolean;
  slotKey: PresetSlotKey | null;
  slot?: PresetSlot;
  priority: number;
  champion?: Champion;
  preview?: PresetPreview;
  spells: SummonerSpell[];
  pending: boolean;
  feedback: string;
  leagueConnected: boolean;
  presetAutomationsEnabled: boolean;
  returnFocusRef: RefObject<HTMLButtonElement | null>;
  championChoiceRef?: RefObject<HTMLButtonElement | null>;
  onClose: () => void;
  onOpenPicker: (kind: "champion" | "skin" | "runes", trigger: HTMLButtonElement) => void;
  onUpdate: (values: Partial<PresetSlot>) => void;
  children: ReactNode;
}) {
  if (!slotKey || !slot) return null;

  const runeIcon = runeAssetUrl(slot.rune_keystone_path, "perk");
  const skinName = getSkinName(slot);
  const skinPreview = getSkinPreviewUrl(slot, preview);
  const championIcon = safeImageUrl(champion?.icon_url ?? preview?.champion_icon_url);
  const spellOptions = spells.map((spell) => ({
    id: spell.name,
    label: spell.name === "(None)" ? fr.common.none : spell.name,
  }));
  const renderSpell = (option: (typeof spellOptions)[number]) => {
    const spell = spells.find((item) => item.name === option.id);
    return <span className="spell-select-option">
      <AssetImage className="spell-select-icon" src={safeImageUrl(spell?.icon_url) ?? undefined} alt="" width="22" height="22" fallback={<CircleOff size={14} aria-hidden="true" />} />
      <span>{option.label}</span>
    </span>;
  };

  return (
    <Dialog.Root open={open} onOpenChange={(nextOpen) => { if (!nextOpen) onClose(); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="drawer preset-editor-overlay">
          <Dialog.Content
            className="preset-editor-dialog"
            aria-describedby="preset-editor-description"
            onCloseAutoFocus={(event) => {
              event.preventDefault();
              returnFocusRef.current?.focus();
            }}
          >
          <header className="preset-editor-header">
            <div>
              <span className="eyebrow">{fr.presets.priority} {priority}</span>
              <Dialog.Title>{fr.presets.editPreset} {priority}</Dialog.Title>
              <Dialog.Description id="preset-editor-description">{fr.presets.editPresetHint}</Dialog.Description>
            </div>
            <Dialog.Close asChild><button className="icon-button" type="button" aria-label={fr.common.close}><X size={16} aria-hidden="true" /></button></Dialog.Close>
          </header>

          <div className="preset-editor-body">
            <section className="preset-editor-section">
              <h3>{fr.presets.championLabel}</h3>
              <button ref={championChoiceRef} className="champion-choice" type="button" disabled={pending} onClick={(event) => onOpenPicker("champion", event.currentTarget)}>
                <AssetImage src={champion?.icon_url ?? undefined} alt="" width="42" height="42" fallback={<Swords size={18} aria-hidden="true" />} />
                <span><strong>{slot.champion || fr.presets.selectChampion}</strong><small>{champion?.title || fr.presets.chooseChampionHint}</small></span>
                <ChevronRight size={15} aria-hidden="true" />
              </button>
            </section>

            <section className="preset-editor-section" aria-labelledby="preset-spells-heading">
              <h3 id="preset-spells-heading">{fr.dashboard.spells}</h3>
              <div className="preset-editor-spells">
                <label className="editor-spell"><span>{fr.presets.spellOne}</span><Select label={fr.presets.spellOne} value={slot.spell_1 || "(None)"} options={spellOptions} disabled={pending} renderOption={renderSpell} onChange={(value) => onUpdate({ spell_1: value })} /></label>
                <label className="editor-spell"><span>{fr.presets.spellTwo}</span><Select label={fr.presets.spellTwo} value={slot.spell_2 || "(None)"} options={spellOptions} disabled={pending} renderOption={renderSpell} onChange={(value) => onUpdate({ spell_2: value })} /></label>
              </div>
            </section>

            <section className="preset-editor-section">
              <h3>{fr.dashboard.runes}</h3>
              <div className="preset-editor-runes">
                <button className="editor-choice" type="button" disabled={pending} onClick={(event) => onOpenPicker("runes", event.currentTarget)}>
                  <AssetImage src={runeIcon ?? undefined} alt="" width="28" height="28" fallback={<Sparkles size={16} aria-hidden="true" />} />
                  <span className="editor-choice-copy"><small>{fr.presets.runePage}</small><strong>{slot.rune_page_name || fr.common.default}</strong></span>
                  <ChevronRight size={15} aria-hidden="true" />
                </button>
                <div className="editor-switch-row"><span>{fr.presets.runeAuto}</span><button className="switch" type="button" role="switch" aria-label={fr.presets.runeAuto} aria-checked={slot.rune_auto_apply} aria-busy={pending} title={!presetAutomationsEnabled ? presetAutomationCopy.masterRequired : undefined} disabled={pending || !presetAutomationsEnabled} onClick={() => onUpdate({ rune_auto_apply: !slot.rune_auto_apply })}><span aria-hidden="true" /></button></div>
              </div>
              {!presetAutomationsEnabled && <p className="preset-editor-note">{presetAutomationCopy.masterRequired}</p>}
              {!leagueConnected && <p className="preset-editor-note">{fr.presets.runesUnavailableHint} {fr.presets.savedRunePageHint}</p>}
            </section>

            <section className="preset-editor-section">
              <h3>{fr.dashboard.skin}</h3>
              <fieldset className="skin-mode-options" disabled={pending} aria-label={fr.presets.skinMode}>
                <label className="skin-mode-option"><input type="radio" name={`skin-mode-${slotKey}`} value="none" checked={slot.skin_mode === "none"} onChange={() => onUpdate({ skin_mode: "none" })} />{fr.presets.skinNone}</label>
                <label className="skin-mode-option"><input type="radio" name={`skin-mode-${slotKey}`} value="fixed" checked={slot.skin_mode === "fixed"} onChange={() => onUpdate({ skin_mode: "fixed" })} />{fr.presets.skinFixed}</label>
                <label className="skin-mode-option"><input type="radio" name={`skin-mode-${slotKey}`} value="random" checked={slot.skin_mode === "random"} onChange={() => onUpdate({ skin_mode: "random" })} />{fr.presets.skinRandom}</label>
              </fieldset>
              <button className="editor-choice" type="button" disabled={pending || slot.skin_mode === "none"} onClick={(event) => onOpenPicker("skin", event.currentTarget)}>
                <AssetImage className="editor-skin-preview" src={safeImageUrl(skinPreview) ?? championIcon ?? undefined} alt="" width="62" height="36" fallback={<Swords size={17} aria-hidden="true" />} />
                <span className="editor-choice-copy"><small>{slot.skin_mode === "random" ? fr.presets.randomPool : fr.presets.skinGallery}</small><strong>{skinName}</strong></span>
                <ChevronRight size={15} aria-hidden="true" />
              </button>
            </section>
          </div>

          <footer className="preset-editor-footer">
            <span className="feedback" role="status" aria-live="polite">{pending ? fr.presets.saving : feedback}</span>
            <Dialog.Close asChild><button className="button button-primary" type="button">{fr.common.close}</button></Dialog.Close>
          </footer>
            {children}
          </Dialog.Content>
        </Dialog.Overlay>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function getSkinName(slot: PresetSlot): string {
  if (slot.skin_mode === "none") return fr.presets.skinNone;
  if (slot.skin_mode === "fixed") return slot.skin_name || fr.presets.skinFixed;
  return slot.random_skin_name || slot.random_skin_pool[0]?.skin_name || fr.presets.skinRandom;
}

function getSkinPreviewUrl(slot: PresetSlot, preview?: PresetPreview): string | null {
  if (!preview?.skin_preview_url || slot.skin_mode === "none") return null;
  if (slot.skin_mode === "fixed") {
    return preview.skin_name?.toLocaleLowerCase() === slot.skin_name.toLocaleLowerCase()
      ? preview.skin_preview_url
      : null;
  }

  const selectedNames = [slot.random_skin_name, ...slot.random_skin_pool.map((skin) => skin.skin_name)]
    .filter(Boolean)
    .map((name) => name.toLocaleLowerCase());
  return selectedNames.length === 0 || selectedNames.includes(preview.skin_name?.toLocaleLowerCase() ?? "")
    ? preview.skin_preview_url
    : null;
}
