import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, ArrowUpRight, CircleAlert } from "lucide-react";

import { api } from "../../api/client";
import { Button } from "../../components/ui/button";
import { fr } from "../../content/fr";
import { cn } from "../../lib/cn";
import { useRuntimeStore } from "../../stores/runtimeStore";
import type { Champion, Settings, SettingsPatch } from "../../types/api";
import { AutomationBar, type AutomationItem } from "./AutomationBar";
import { BanPanel } from "./BanPanel";
import { ChampionPriorityCard, type MainSkinMode } from "./ChampionPriorityCard";
import { QuickActions } from "./QuickActions";

const slots = ["pick_1", "pick_2", "pick_3"] as const;
type SlotKey = typeof slots[number];
type ToggleKey = "auto_accept_enabled" | "auto_pick_enabled" | "auto_ban_enabled" | "auto_summoners_enabled" | "auto_play_again_enabled";

function DashboardPage() {
  const queryClient = useQueryClient();
  const runtimeStatus = useRuntimeStore((state) => state.status);
  const presets = useQuery({ queryKey: ["presets"], queryFn: api.getPresets, staleTime: Infinity });
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.getSettings, staleTime: Infinity });
  const currentPresets = presets.data;
  const currentSettings = settings.data;
  const slotsData = slots.map((key) => currentPresets?.slots[key]);
  const configuredCount = slotsData.filter((slot) => Boolean(slot?.champion)).length;
  const spells = useQuery({ queryKey: ["spells"], queryFn: api.getSpells, enabled: configuredCount > 0, staleTime: 3_600_000 });
  const bootstrap = useQuery({ queryKey: ["bootstrap"], queryFn: api.getBootstrap, staleTime: Infinity });
  const previews = bootstrap.data?.preset_previews ?? {};
  const banName = currentPresets?.selected_ban || fr.dashboard.noBan;
  const needsChampionCatalog = slots.some((key) => Boolean(currentPresets?.slots[key]?.champion && !previews[key]?.champion_id)) || Boolean(banName !== fr.dashboard.noBan && !bootstrap.data?.ban_preview?.champion_id);
  const championCatalog = useQuery({ queryKey: ["champions", "dashboard"], queryFn: () => api.getChampions(), enabled: needsChampionCatalog, staleTime: 3_600_000 });
  const stats = useQuery({ queryKey: ["stats-link"], queryFn: api.getStatsLink, staleTime: 300_000, retry: false });
  const [pendingKeys, setPendingKeys] = useState<Set<string>>(new Set());
  const overrides = currentSettings?.main_skin_mode_overrides ?? {};

  useEffect(() => { performance.mark("otp:t8-dashboard-ready"); }, []);
  const setPending = (key: string, pending: boolean) => setPendingKeys((current) => {
    const next = new Set(current);
    pending ? next.add(key) : next.delete(key);
    return next;
  });

  const patchSetting = async (key: string, value: unknown) => {
    const previous = queryClient.getQueryData<Settings>(["settings"]);
    setPending(key, true);
    queryClient.setQueryData<Settings>(["settings"], (current) => current ? { ...current, [key]: value } : current);
    try {
      const next = await api.patchSettings({ [key]: value } as SettingsPatch);
      queryClient.setQueryData(["settings"], next);
      if (key === "presets_enabled") await queryClient.invalidateQueries({ queryKey: ["presets"] });
      await queryClient.invalidateQueries({ queryKey: ["bootstrap"] });
    } catch {
      if (previous) queryClient.setQueryData<Settings>(["settings"], (current) => current ? { ...current, [key]: previous[key as keyof Settings] } : previous);
    } finally {
      setPending(key, false);
    }
  };

  const toggle = (key: ToggleKey) => {
    if (currentSettings) void patchSetting(key, !currentSettings[key]);
  };

  const setOverride = (slot: SlotKey, mode: MainSkinMode) => {
    if (!currentSettings) return;
    void patchSetting("main_skin_mode_overrides", { ...overrides, [slot]: mode });
  };

  const automationItems = useMemo<AutomationItem[]>(() => currentSettings ? [
    { id: "auto-accept", label: fr.settings.autoAccept, detail: fr.dashboard.readyCheck, enabled: currentSettings.auto_accept_enabled, pending: pendingKeys.has("auto_accept_enabled"), onToggle: () => toggle("auto_accept_enabled") },
    { id: "auto-pick", label: fr.settings.autoPick, detail: fr.dashboard.prioritizedSlots, enabled: currentSettings.auto_pick_enabled, pending: pendingKeys.has("auto_pick_enabled"), onToggle: () => toggle("auto_pick_enabled") },
    { id: "auto-ban", label: fr.settings.autoBan, detail: currentPresets?.selected_ban || fr.dashboard.noBan, enabled: currentSettings.auto_ban_enabled, pending: pendingKeys.has("auto_ban_enabled"), onToggle: () => toggle("auto_ban_enabled") },
    { id: "auto-summoners", label: fr.settings.autoSummoners, detail: fr.dashboard.summonersAndRunes, enabled: currentSettings.auto_summoners_enabled, pending: pendingKeys.has("auto_summoners_enabled"), onToggle: () => toggle("auto_summoners_enabled") },
    { id: "auto-skin", label: fr.dashboard.skin, detail: currentSettings.skin_automation_enabled ? fr.dashboard.enabled : fr.dashboard.disabled, enabled: currentSettings.skin_automation_enabled, pending: pendingKeys.has("skin_automation_enabled"), onToggle: () => void patchSetting("skin_automation_enabled", !currentSettings.skin_automation_enabled) },
    { id: "auto-play-again", label: fr.settings.playAgain, detail: fr.dashboard.returnToLobby, enabled: currentSettings.auto_play_again_enabled, pending: pendingKeys.has("auto_play_again_enabled"), onToggle: () => toggle("auto_play_again_enabled") },
  ] : [], [currentPresets?.selected_ban, currentSettings, pendingKeys]);

  if (presets.isPending && !currentPresets) return <div className="page-loading">{fr.common.loading}</div>;
  if (presets.isError && !currentPresets) return <div className="state-error"><strong>{fr.presets.championLoadError}</strong><span>{fr.app.localServerError}</span><Button variant="primary" type="button" onClick={() => void presets.refetch()}>{fr.common.retry}</Button></div>;

  const activityIsError = ["ERROR", "WARN"].includes(runtimeStatus.level.toUpperCase());
  const championFor = (name: string, preview?: { champion_id: number | null }) => championCatalog.data?.items.find((item: Champion) => item.name.toLocaleLowerCase() === name.toLocaleLowerCase()) ?? (preview?.champion_id ? championCatalog.data?.items.find((item: Champion) => item.id === preview.champion_id) : undefined);
  return <div className="dashboard-page">
    <div className="page-heading dashboard-heading"><h1>{fr.dashboard.title}</h1></div>
    <div className={cn("activity-strip", activityIsError && "is-error")} role="status" aria-live="polite"><Activity size={14} aria-hidden="true" /><strong>{runtimeStatus.message}</strong>{activityIsError && <CircleAlert size={14} aria-hidden="true" />}</div>
    <div className="dashboard-grid">
      <div className="dashboard-main">
        <section className="surface priority-section" aria-labelledby="slots-heading"><div className="section-head"><div><div className="section-label">{fr.dashboard.slots}</div><h2 id="slots-heading">{configuredCount}/3 {fr.dashboard.ready.toLowerCase()}</h2></div><a className="text-button" href="#presets">{fr.dashboard.edit} <ArrowUpRight size={14} aria-hidden="true" /></a></div><div className="priority-grid">{slotsData.map((slot, index) => <ChampionPriorityCard key={slots[index]} slot={slot} index={index} spells={spells.data?.items ?? []} preview={previews[slots[index]]} champion={championFor(slot?.champion || "", previews[slots[index]])} override={(overrides[slots[index]] as MainSkinMode | undefined) || "inherit"} onOverride={(mode) => setOverride(slots[index], mode)} />)}</div></section>
      </div>
      <aside className="dashboard-aside"><BanPanel banName={banName} autoBanEnabled={Boolean(currentSettings?.auto_ban_enabled)} preview={bootstrap.data?.ban_preview} champion={championFor(banName, bootstrap.data?.ban_preview ?? undefined)} /><QuickActions statsUrl={stats.data?.url} /></aside>
    </div>
    <AutomationBar items={automationItems} />
  </div>;
}

export { DashboardPage };
