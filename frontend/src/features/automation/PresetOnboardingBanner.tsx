import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";

import { api } from "../../api/client";
import { Button } from "../../components/ui/button";
import { fr } from "../../content/fr";
import { presetAutomationCopy } from "../../content/presetAutomation";
import type { Settings } from "../../types/api";

export function PresetOnboardingBanner() {
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.getSettings, staleTime: Infinity });
  const dismiss = useMutation({
    mutationFn: () => api.patchSettings({ onboarding_completed: true }),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: ["settings"] });
      const previous = queryClient.getQueryData<Settings>(["settings"]);
      queryClient.setQueryData<Settings>(["settings"], (current) => current ? { ...current, onboarding_completed: true } : current);
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) queryClient.setQueryData(["settings"], context.previous);
    },
    onSuccess: (next) => queryClient.setQueryData(["settings"], next),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["settings"] }),
  });

  if (settings.data?.onboarding_completed !== false) return null;

  return <aside className="preset-onboarding-banner" aria-label={presetAutomationCopy.onboardingTitle}>
    <div><strong>{presetAutomationCopy.onboardingTitle}</strong><p>{presetAutomationCopy.onboardingMessage}</p></div>
    <a className="button button-primary" href="#presets">{presetAutomationCopy.onboardingAction}</a>
    <Button className="icon-button" type="button" aria-label={presetAutomationCopy.dismissOnboarding} title={presetAutomationCopy.dismissOnboarding} disabled={dismiss.isPending} onClick={() => dismiss.mutate()}><X size={15} aria-hidden="true" /></Button>
    {dismiss.isError && <small className="inline-error" role="alert">{fr.settings.failed}</small>}
  </aside>;
}
