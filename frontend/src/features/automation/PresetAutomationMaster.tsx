import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Swords } from "lucide-react";

import { ApiError, api } from "../../api/client";
import { fr } from "../../content/fr";
import { presetAutomationCopy } from "../../content/presetAutomation";
import type { BootstrapResponse, PresetsResponse, Settings } from "../../types/api";

export function usePresetAutomationMaster() {
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.getSettings, staleTime: Infinity });
  const mutation = useMutation({
    mutationFn: (enabled: boolean) => api.patchSettings({ presets_enabled: enabled }),
    onMutate: async (enabled) => {
      await Promise.all([
        queryClient.cancelQueries({ queryKey: ["settings"] }),
        queryClient.cancelQueries({ queryKey: ["presets"] }),
        queryClient.cancelQueries({ queryKey: ["bootstrap"] }),
      ]);
      const previous = {
        settings: queryClient.getQueryData<Settings>(["settings"]),
        presets: queryClient.getQueryData<PresetsResponse>(["presets"]),
        bootstrap: queryClient.getQueryData<BootstrapResponse>(["bootstrap"]),
      };
      queryClient.setQueryData<Settings>(["settings"], (current) => current ? { ...current, presets_enabled: enabled } : current);
      queryClient.setQueryData<PresetsResponse>(["presets"], (current) => current ? { ...current, presets_enabled: enabled } : current);
      queryClient.setQueryData<BootstrapResponse>(["bootstrap"], (current) => current ? {
        ...current,
        settings: { ...current.settings, presets_enabled: enabled },
        presets: { ...current.presets, presets_enabled: enabled },
      } : current);
      return previous;
    },
    onSuccess: (next) => {
      queryClient.setQueryData<Settings>(["settings"], next);
      queryClient.setQueryData<PresetsResponse>(["presets"], (current) => current
        ? { ...current, presets_enabled: next.presets_enabled }
        : current);
      queryClient.setQueryData<BootstrapResponse>(["bootstrap"], (current) => current ? {
        ...current,
        settings: { ...current.settings, presets_enabled: next.presets_enabled },
        presets: { ...current.presets, presets_enabled: next.presets_enabled },
      } : current);
    },
    onError: (_error, _enabled, previous) => {
      if (previous?.settings) queryClient.setQueryData(["settings"], previous.settings);
      if (previous?.presets) queryClient.setQueryData(["presets"], previous.presets);
      if (previous?.bootstrap) queryClient.setQueryData(["bootstrap"], previous.bootstrap);
    },
    onSettled: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["settings"] }),
        queryClient.invalidateQueries({ queryKey: ["presets"] }),
        queryClient.invalidateQueries({ queryKey: ["bootstrap"] }),
      ]);
    },
  });

  const enabled = settings.data?.presets_enabled ?? false;
  const errorMessage = mutation.error instanceof ApiError && mutation.error.status === 422
    ? fr.presets.activationRequiresChampion
    : mutation.error ? fr.presets.saveFailed : "";

  return {
    enabled,
    ready: Boolean(settings.data),
    pending: mutation.isPending,
    errorMessage,
    toggle: () => mutation.mutate(!enabled),
  };
}

export function PresetAutomationMaster({ enabled, pending, ready, errorMessage = "", onToggle }: {
  enabled: boolean;
  pending: boolean;
  ready: boolean;
  errorMessage?: string;
  onToggle: () => void;
}) {
  return <div className="preset-automation-master">
    <span className="preset-automation-master-icon"><Swords size={16} aria-hidden="true" /></span>
    <div className="preset-automation-master-copy">
      <strong>{presetAutomationCopy.masterLabel}</strong>
      <small>{enabled ? presetAutomationCopy.masterEnabled : presetAutomationCopy.masterDisabled}</small>
    </div>
    <button className="switch" type="button" role="switch" aria-label={presetAutomationCopy.masterLabel} aria-checked={enabled} aria-busy={pending} disabled={!ready || pending} onClick={onToggle}><span aria-hidden="true" /></button>
    {errorMessage && <small className="inline-error" role="alert">{errorMessage}</small>}
  </div>;
}
