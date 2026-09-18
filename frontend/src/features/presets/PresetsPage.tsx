import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, Check, LoaderCircle } from "lucide-react";

import { api } from "../../api/client";
import { AssetImage } from "../../components/game/AssetImage";
import { Button } from "../../components/ui/button";
import { fr } from "../../content/fr";
import { safeImageUrl } from "../../domain/assets";
import { useRuntimeStore } from "../../stores/runtimeStore";
import type { Champion, PresetsAction, PresetSlot, PresetsResponse, SettingsPatch } from "../../types/api";
import { PresetAutomationMaster, usePresetAutomationMaster } from "../automation/PresetAutomationMaster";
import { ChampionPicker } from "./ChampionPicker";
import { PickerDialog, type Picker } from "./PickerDialog";
import { PresetCard, type PresetSlotKey } from "./PresetCard";
import { PresetEditorDialog } from "./PresetEditorDialog";
import { RunePicker } from "./RunePicker";
import { SkinPicker } from "./SkinPicker";

const slotKeys: readonly PresetSlotKey[] = ["pick_1", "pick_2", "pick_3"];

export function PresetsPage({ action, onActionClose }: { action?: PresetsAction; onActionClose?: () => void }) {
  const queryClient = useQueryClient();
  const runtime = useRuntimeStore((state) => state.runtime);
  const presetMaster = usePresetAutomationMaster();
  const [editingSlot, setEditingSlot] = useState<PresetSlotKey | null>(null);
  const [picker, setPicker] = useState<Picker>(null);
  const [feedback, setFeedback] = useState("");
  const [feedbackIsError, setFeedbackIsError] = useState(false);
  const cardFocusRef = useRef<HTMLButtonElement | null>(null);
  const championChoiceFocusRef = useRef<HTMLButtonElement | null>(null);
  const cardTriggerRefs = useRef<Record<PresetSlotKey, HTMLButtonElement | null>>({ pick_1: null, pick_2: null, pick_3: null });
  const appliedActionRef = useRef<PresetsAction | null>(null);
  const pickerFocusRef = useRef<HTMLButtonElement | null>(null);
  const banFocusRef = useRef<HTMLButtonElement | null>(null);
  const presets = useQuery({ queryKey: ["presets"], queryFn: api.getPresets, staleTime: Infinity });
  const bootstrap = useQuery({ queryKey: ["bootstrap"], queryFn: api.getBootstrap, staleTime: Infinity });
  const hasChampionData = Boolean(presets.data?.selected_ban || slotKeys.some((key) => presets.data?.slots[key]?.champion));
  const champions = useQuery({ queryKey: ["champions", "catalog"], queryFn: () => api.getChampions(), enabled: hasChampionData || picker?.kind === "champion" || Boolean(editingSlot), staleTime: 3_600_000 });
  const spells = useQuery({ queryKey: ["spells"], queryFn: api.getSpells, enabled: hasChampionData || Boolean(editingSlot), staleTime: 3_600_000 });
  const editingData = editingSlot ? presets.data?.slots[editingSlot] : undefined;
  const editingChampion = champions.data?.items.find((item) => item.name.toLocaleLowerCase() === editingData?.champion.toLocaleLowerCase());
  const activePickerSlot = picker?.slot ? presets.data?.slots[picker.slot] : editingData;
  const selectedChampion = activePickerSlot?.champion || "";
  const selectedChampionData = champions.data?.items.find((item) => item.name.toLocaleLowerCase() === selectedChampion.toLocaleLowerCase());
  const championId = selectedChampionData?.id
    ?? (editingSlot ? bootstrap.data?.preset_previews?.[editingSlot]?.champion_id ?? undefined : undefined);
  const skins = useQuery({ queryKey: ["skins", championId], queryFn: () => api.getSkins(championId ?? 0), enabled: picker?.kind === "skin" && Boolean(championId), staleTime: 3_600_000 });
  const runes = useQuery({ queryKey: ["runes"], queryFn: api.getRunes, enabled: picker?.kind === "runes", staleTime: 3_600_000 });

  useEffect(() => {
    if (!action) {
      if (appliedActionRef.current === "ban") setPicker(null);
      if (appliedActionRef.current && appliedActionRef.current !== "ban") {
        setEditingSlot(null);
        setPicker(null);
      }
      appliedActionRef.current = null;
      return;
    }
    if (appliedActionRef.current === action) return;
    appliedActionRef.current = action;
    if (action === "ban") {
      setEditingSlot(null);
      pickerFocusRef.current = banFocusRef.current;
      setPicker({ kind: "ban" });
    } else {
      cardFocusRef.current = cardTriggerRefs.current[action];
      pickerFocusRef.current = championChoiceFocusRef.current;
      setEditingSlot(action);
      setPicker(null);
    }
  }, [action]);

  useEffect(() => {
    if (action === "ban" && !pickerFocusRef.current) {
      pickerFocusRef.current = banFocusRef.current;
    } else if (action && action !== "ban" && !cardFocusRef.current) {
      cardFocusRef.current = cardTriggerRefs.current[action];
    }
    if (action && action !== "ban" && !pickerFocusRef.current) {
      pickerFocusRef.current = championChoiceFocusRef.current;
    }
  }, [action, editingSlot, presets.data]);

  const showFeedback = (message: string, isError = false) => {
    setFeedback(message);
    setFeedbackIsError(isError);
  };

  const updatePreset = useMutation({
    mutationFn: ({ slot, values }: { slot: PresetSlotKey; values: Partial<PresetSlot> }) => api.patchPreset(slot, values),
    onMutate: async ({ slot, values }) => {
      await queryClient.cancelQueries({ queryKey: ["presets"] });
      const previous = queryClient.getQueryData<PresetsResponse>(["presets"]);
      queryClient.setQueryData<PresetsResponse>(["presets"], (current) => current
        ? { ...current, slots: { ...current.slots, [slot]: { ...current.slots[slot], ...values } } }
        : current);
      return { previous };
    },
    onSuccess: () => showFeedback(fr.presets.saved),
    onError: (_error, _variables, context) => {
      if (context?.previous) queryClient.setQueryData(["presets"], context.previous);
      showFeedback(fr.presets.saveFailed, true);
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["presets"] });
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
      void queryClient.invalidateQueries({ queryKey: ["bootstrap"] });
    },
  });

  const updateSettings = useMutation({
    mutationFn: (values: SettingsPatch) => api.patchSettings(values),
    onSuccess: (next) => {
      queryClient.setQueryData(["settings"], next);
      void queryClient.invalidateQueries({ queryKey: ["presets"] });
      void queryClient.invalidateQueries({ queryKey: ["bootstrap"] });
      showFeedback(fr.presets.saved);
    },
    onError: () => showFeedback(fr.presets.saveFailed, true),
  });

  const openPicker = (kind: "champion" | "skin" | "runes", trigger: HTMLButtonElement) => {
    pickerFocusRef.current = trigger;
    setPicker({ kind, slot: editingSlot ?? undefined });
  };
  const openBanPicker = () => {
    pickerFocusRef.current = banFocusRef.current;
    setPicker({ kind: "ban" });
  };
  const closeCardPicker = () => {
    setPicker(null);
    window.requestAnimationFrame(() => {
      const fallbackFocusTarget = action && action !== "ban" ? championChoiceFocusRef.current : null;
      (pickerFocusRef.current?.isConnected ? pickerFocusRef.current : fallbackFocusTarget)?.focus();
    });
  };
  const updateEditingPreset = (values: Partial<PresetSlot>) => {
    if (editingSlot && !updatePreset.isPending) updatePreset.mutate({ slot: editingSlot, values });
  };
  const setChampion = async (champion: Champion) => {
    if (!picker || updatePreset.isPending || updateSettings.isPending) return;
    try {
      if (picker.kind === "ban") {
        await updateSettings.mutateAsync({ selected_ban: champion.name });
        setPicker(null);
        if (action === "ban") onActionClose?.();
      } else if (picker.slot) {
        await updatePreset.mutateAsync({ slot: picker.slot, values: { champion: champion.name } });
        setPicker(null);
      }
    } catch {
      // The mutation exposes the failure in the page feedback and keeps the picker open.
    }
  };

  if (presets.isPending && !presets.data) return <div className="page-loading">{fr.common.loading}</div>;
  if (presets.isError || !presets.data) return <div className="state-error"><strong>{fr.presets.championLoadError}</strong><Button variant="primary" type="button" onClick={() => void presets.refetch()}>{fr.common.retry}</Button></div>;

  const isSaving = updatePreset.isPending || updateSettings.isPending || presetMaster.pending;
  const selectedBan = presets.data.selected_ban;
  const banChampion = champions.data?.items.find((item) => item.name.toLocaleLowerCase() === selectedBan.toLocaleLowerCase());
  const banIcon = bootstrap.data?.ban_preview?.champion_icon_url ?? banChampion?.icon_url;
  const activeDialog = editingSlot ? picker : picker?.kind === "ban" ? picker : null;
  const pickerContent = activeDialog
    ? <PickerContent
        picker={activeDialog}
        selectedBan={selectedBan}
        selectedChampion={activeDialog.kind === "ban" ? selectedBan : activePickerSlot?.champion || ""}
        selectedSlot={activeDialog.kind === "ban" ? undefined : activePickerSlot}
        skins={skins.data}
        skinsLoading={skins.isPending}
        skinsError={skins.isError}
        runes={runes.data}
        runesLoading={runes.isPending}
        runesError={runes.isError}
        onChampionSelect={setChampion}
        onUpdate={updateEditingPreset}
        onRetrySkins={() => void skins.refetch()}
        onRetryRunes={() => void runes.refetch()}
      />
    : null;
  const cardPicker = <PickerDialog picker={editingSlot ? picker : null} onClose={closeCardPicker} returnFocusRef={pickerFocusRef}>{pickerContent}</PickerDialog>;

  return <div className="presets-page">
    <div className="page-heading">
      <div><h1>{fr.presets.title}</h1><p>{fr.presets.subtitle}</p></div>
    </div>

    <PresetAutomationMaster enabled={presetMaster.enabled} ready={presetMaster.ready} pending={presetMaster.pending} errorMessage={presetMaster.errorMessage} onToggle={presetMaster.toggle} />

    <div className="preset-grid">{slotKeys.map((key, index) => {
      const slot = presets.data.slots[key];
      const champion = champions.data?.items.find((item) => item.name.toLocaleLowerCase() === slot.champion.toLocaleLowerCase());
      return <PresetCard
        key={key}
        slotKey={key}
        slot={slot}
        index={index}
        champion={champion}
        preview={bootstrap.data?.preset_previews?.[key]}
        spells={spells.data?.items ?? []}
        triggerRef={(node) => { cardTriggerRefs.current[key] = node; }}
        isOpen={editingSlot === key}
        onOpen={(slotKey, trigger) => { cardFocusRef.current = trigger; setEditingSlot(slotKey); setPicker(null); }}
      />;
    })}</div>

    <section className="surface ban-editor">
      <AssetImage src={safeImageUrl(banIcon) ?? undefined} alt={selectedBan || ""} width="42" height="42" fallback={<Ban size={19} aria-hidden="true" />} />
      <div><div className="section-label">{fr.dashboard.ban}</div><h2>{selectedBan || fr.dashboard.noBan}</h2><p>{fr.presets.banHint}</p></div>
      <button ref={banFocusRef} className="button" type="button" disabled={isSaving} onClick={openBanPicker}>{fr.presets.editBan}</button>
    </section>

    <p className={feedbackIsError ? "feedback feedback-error" : "feedback"} role={feedbackIsError ? "alert" : "status"} aria-live={feedbackIsError ? "assertive" : "polite"}>
      {isSaving ? fr.presets.saving : feedback && <>{!feedbackIsError && <Check size={13} aria-hidden="true" />} {feedback}</>}
    </p>

    {editingSlot && <PresetEditorDialog
      open
      slotKey={editingSlot}
      slot={editingData}
      priority={slotKeys.indexOf(editingSlot) + 1}
      champion={editingChampion}
      preview={bootstrap.data?.preset_previews?.[editingSlot]}
      spells={spells.data?.items ?? [{ name: "(None)", icon_url: null }]}
      pending={updatePreset.isPending || spells.isPending}
      feedback={feedbackIsError ? "" : feedback}
      leagueConnected={Boolean(runtime?.connected)}
      presetAutomationsEnabled={presetMaster.enabled}
      returnFocusRef={cardFocusRef}
      championChoiceRef={championChoiceFocusRef}
      onClose={() => { setEditingSlot(null); setPicker(null); if (action && action !== "ban") onActionClose?.(); }}
      onOpenPicker={openPicker}
      onUpdate={updateEditingPreset}
    >{cardPicker}</PresetEditorDialog>}

    {!editingSlot && picker?.kind === "ban" && <PickerDialog picker={picker} onClose={() => { setPicker(null); if (action === "ban") onActionClose?.(); }} returnFocusRef={pickerFocusRef}>{pickerContent}</PickerDialog>}
  </div>;
}

function PickerContent({ picker, selectedBan, selectedChampion, selectedSlot, skins, skinsLoading, skinsError, runes, runesLoading, runesError, onChampionSelect, onUpdate, onRetrySkins, onRetryRunes }: {
  picker: Exclude<Picker, null>;
  selectedBan: string;
  selectedChampion: string;
  selectedSlot?: PresetSlot;
  skins?: Awaited<ReturnType<typeof api.getSkins>>;
  skinsLoading: boolean;
  skinsError: boolean;
  runes?: Awaited<ReturnType<typeof api.getRunes>>;
  runesLoading: boolean;
  runesError: boolean;
  onChampionSelect: (champion: Champion) => void;
  onUpdate: (values: Partial<PresetSlot>) => void;
  onRetrySkins: () => void;
  onRetryRunes: () => void;
}) {
  if (picker.kind === "champion" || picker.kind === "ban") return <ChampionPicker selected={picker.kind === "ban" ? selectedBan : selectedChampion} onSelect={onChampionSelect} />;
  if (picker.kind === "skin" && skinsError) return <div className="state-error"><strong>{fr.presets.skinLoadError}</strong><Button type="button" onClick={onRetrySkins}>{fr.common.retry}</Button></div>;
  if (picker.kind === "skin" && skinsLoading) return <div className="page-loading">{fr.common.loading}</div>;
  if (picker.kind === "skin" && selectedSlot && skins) return <SkinPicker slot={selectedSlot} skins={skins} onUpdate={onUpdate} />;
  if (picker.kind === "runes" && runesError) return <div className="state-error"><strong>{fr.presets.runeLoadError}</strong><Button type="button" onClick={onRetryRunes}>{fr.common.retry}</Button></div>;
  if (picker.kind === "runes" && runesLoading) return <div className="page-loading">{fr.common.loading}</div>;
  if (picker.kind === "runes" && selectedSlot && runes) return <RunePicker slot={selectedSlot} runes={runes} onUpdate={onUpdate} />;
  return <div className="picker-empty">{fr.common.loading}</div>;
}
