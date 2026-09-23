import { useEffect, useRef, useState, type RefObject } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import { Button } from "../../components/ui/button";
import { fr } from "../../content/fr";
import { useRuntimeStore } from "../../stores/runtimeStore";
import type { Champion, DashboardAction, PresetSlot, PresetsResponse, SettingsPatch } from "../../types/api";
import { presetSlotKeys, type PresetSlotKey } from "../../domain/presets";
import { ChampionPicker } from "./ChampionPicker";
import { PickerDialog, type Picker } from "./PickerDialog";
import { PresetEditorDialog } from "./PresetEditorDialog";
import { RunePicker } from "./RunePicker";
import { SkinPicker } from "./SkinPicker";

export function PresetEditorFlow({ action, onClose, returnFocusRef }: {
  action?: DashboardAction;
  onClose: () => void;
  returnFocusRef: RefObject<HTMLElement | null>;
}) {
  const queryClient = useQueryClient();
  const runtime = useRuntimeStore((state) => state.runtime);
  const editingSlot: PresetSlotKey | null = action && action !== "ban" ? action : null;
  const [picker, setPicker] = useState<Picker>(null);
  const [feedback, setFeedback] = useState("");
  const [feedbackIsError, setFeedbackIsError] = useState(false);
  const pickerFocusRef = useRef<HTMLElement | null>(null);
  const championChoiceFocusRef = useRef<HTMLButtonElement | null>(null);
  const presets = useQuery({ queryKey: ["presets"], queryFn: api.getPresets, staleTime: Infinity });
  const bootstrap = useQuery({ queryKey: ["bootstrap"], queryFn: api.getBootstrap, staleTime: Infinity });
  const editingData = editingSlot ? presets.data?.slots[editingSlot] : undefined;
  const activePickerSlot = picker?.slot ? presets.data?.slots[picker.slot] : editingData;
  const selectedChampion = activePickerSlot?.champion || "";
  const champions = useQuery({
    queryKey: ["champions", "catalog"],
    queryFn: () => api.getChampions(),
    enabled: Boolean(action),
    staleTime: 3_600_000,
  });
  const spells = useQuery({
    queryKey: ["spells"],
    queryFn: api.getSpells,
    enabled: Boolean(editingSlot),
    staleTime: 3_600_000,
  });
  const selectedChampionData = champions.data?.items.find((item) => item.name.toLocaleLowerCase() === selectedChampion.toLocaleLowerCase());
  const championId = selectedChampionData?.id ?? (editingSlot ? bootstrap.data?.preset_previews?.[editingSlot]?.champion_id ?? undefined : undefined);
  const skins = useQuery({
    queryKey: ["skins", championId],
    queryFn: () => api.getSkins(championId ?? 0),
    enabled: picker?.kind === "skin" && Boolean(championId),
    staleTime: 3_600_000,
  });
  const runes = useQuery({
    queryKey: ["runes"],
    queryFn: api.getRunes,
    enabled: picker?.kind === "runes",
    staleTime: 0,
    refetchOnMount: "always",
  });

  useEffect(() => {
    setPicker(action === "ban" ? { kind: "ban" } : null);
    setFeedback("");
    setFeedbackIsError(false);
  }, [action]);

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

  const closePicker = () => {
    setPicker(null);
    window.requestAnimationFrame(() => pickerFocusRef.current?.focus());
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
        onClose();
      } else if (picker.slot) {
        await updatePreset.mutateAsync({ slot: picker.slot, values: { champion: champion.name } });
        setPicker(null);
      }
    } catch {
      // The mutation exposes the failure in the editor feedback and keeps the picker open.
    }
  };

  if (!action || !presets.data) return null;

  const editingChampion = champions.data?.items.find((item) => item.name.toLocaleLowerCase() === editingData?.champion.toLocaleLowerCase());
  const selectedBan = presets.data.selected_ban;
  const activeDialog = picker;
  const pickerContent = activeDialog
    ? <PickerContent
        picker={activeDialog}
        selectedBan={selectedBan}
        selectedChampion={activeDialog.kind === "ban" ? selectedBan : selectedChampion}
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
  const isSaving = updatePreset.isPending || updateSettings.isPending || spells.isPending;
  const closeEditor = () => {
    setPicker(null);
    onClose();
    window.requestAnimationFrame(() => returnFocusRef.current?.focus());
  };

  if (editingSlot) {
    return <PresetEditorDialog
      open
      slotKey={editingSlot}
      slot={editingData}
      priority={presetSlotKeys.indexOf(editingSlot) + 1}
      champion={editingChampion}
      preview={bootstrap.data?.preset_previews?.[editingSlot]}
      spells={spells.data?.items ?? [{ name: "(None)", icon_url: null }]}
      pending={isSaving}
      feedback={feedback}
      feedbackIsError={feedbackIsError}
      leagueConnected={Boolean(runtime?.connected)}
      returnFocusRef={returnFocusRef}
      championChoiceRef={championChoiceFocusRef}
      onClose={closeEditor}
      onOpenPicker={openPicker}
      onUpdate={updateEditingPreset}
    >
      <PickerDialog picker={picker} onClose={closePicker} returnFocusRef={pickerFocusRef} feedback={feedback} feedbackIsError={feedbackIsError}>{pickerContent}</PickerDialog>
    </PresetEditorDialog>;
  }

  return <PickerDialog picker={picker} onClose={closeEditor} returnFocusRef={returnFocusRef} feedback={feedback} feedbackIsError={feedbackIsError}>{pickerContent}</PickerDialog>;
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
