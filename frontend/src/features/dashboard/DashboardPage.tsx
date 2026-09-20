import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, AlertTriangle, ArrowUpRight, CheckCircle2, Info } from "lucide-react";

import { api } from "../../api/client";
import { Button } from "../../components/ui/button";
import { fr } from "../../content/fr";
import { cn } from "../../lib/cn";
import { phaseLabel } from "../../domain/runtime";
import { useRuntimeStore } from "../../stores/runtimeStore";
import type { Champion, PresetsResponse, Settings, SettingsPatch } from "../../types/api";
import { PresetAutomationMaster, usePresetAutomationMaster } from "../automation/PresetAutomationMaster";
import { PresetOnboardingBanner } from "../automation/PresetOnboardingBanner";
import { AutomationBar, type AutomationItem } from "./AutomationBar";
import { BanPanel } from "./BanPanel";
import { ChampionPriorityCard, type SkinMode } from "./ChampionPriorityCard";
import { QuickActions } from "./QuickActions";

const slots = ["pick_1", "pick_2", "pick_3"] as const;
type SlotKey = typeof slots[number];
type ToggleKey = "auto_accept_enabled" | "auto_pick_enabled" | "auto_ban_enabled" | "auto_summoners_enabled" | "auto_play_again_enabled";

function relativeStatusTime(timestamp: string, now: number): string {
  const parsed = Date.parse(timestamp);
  if (!Number.isFinite(parsed)) return "";
  const seconds = Math.max(0, Math.floor((now - parsed) / 1000));
  if (seconds < 5) return "à l’instant";
  if (seconds < 60) return `il y a ${seconds} s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `il y a ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  return `il y a ${hours} h`;
}

function AutomationStatus() {
  const status = useRuntimeStore((state) => state.status);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!status.timestamp) return;
    const timer = window.setInterval(() => setNow(Date.now()), 5_000);
    return () => window.clearInterval(timer);
  }, [status.timestamp]);
  if (!status.timestamp) return null;
  const tone = status.tone;
  const Icon = tone === "warning" ? AlertTriangle : tone === "success" ? CheckCircle2 : Info;
  const relative = relativeStatusTime(status.timestamp, now);
  return <section className={cn("automation-status", `is-${tone}`)} role="status" aria-live="polite">
    <Icon size={14} aria-hidden="true" />
    <span className="automation-status-message">{status.message}</span>
    {relative && <time dateTime={status.timestamp}>{relative}</time>}
  </section>;
}

function DashboardPage() {
  const queryClient = useQueryClient();
  const runtime = useRuntimeStore((state) => state.runtime);
  const presets = useQuery({ queryKey: ["presets"], queryFn: api.getPresets, staleTime: Infinity });
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.getSettings, staleTime: Infinity });
  const presetMaster = usePresetAutomationMaster();
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
  const [pendingKeys, setPendingKeys] = useState<Set<string>>(new Set());
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

  const setSkinMode = async (slot: SlotKey, mode: SkinMode) => {
    const pendingKey = `skin_mode_${slot}`;
    await queryClient.cancelQueries({ queryKey: ["presets"] });
    const previous = queryClient.getQueryData<PresetsResponse>(["presets"]);
    setPending(pendingKey, true);
    queryClient.setQueryData<PresetsResponse>(["presets"], (current) => current ? {
      ...current,
      slots: { ...current.slots, [slot]: { ...current.slots[slot], skin_mode: mode } },
    } : current);
    try {
      const next = await api.patchPreset(slot, { skin_mode: mode });
      queryClient.setQueryData(["presets"], next);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["settings"] }),
        queryClient.invalidateQueries({ queryKey: ["bootstrap"] }),
      ]);
    } catch {
      if (previous) queryClient.setQueryData(["presets"], previous);
    } finally {
      setPending(pendingKey, false);
    }
  };

  const automationItems = useMemo<AutomationItem[]>(() => currentSettings ? [
    { id: "auto-accept", label: fr.settings.autoAccept, detail: fr.dashboard.readyCheck, enabled: currentSettings.auto_accept_enabled, pending: pendingKeys.has("auto_accept_enabled"), onToggle: () => toggle("auto_accept_enabled") },
    { id: "auto-pick", label: fr.settings.autoPick, detail: fr.dashboard.prioritizedSlots, enabled: currentSettings.auto_pick_enabled, pending: pendingKeys.has("auto_pick_enabled"), disabledByMaster: !presetMaster.enabled, onToggle: () => toggle("auto_pick_enabled") },
    { id: "auto-ban", label: fr.settings.autoBan, detail: currentPresets?.selected_ban || fr.dashboard.noBan, enabled: currentSettings.auto_ban_enabled, pending: pendingKeys.has("auto_ban_enabled"), disabledByMaster: !presetMaster.enabled, onToggle: () => toggle("auto_ban_enabled") },
    { id: "auto-summoners", label: fr.settings.autoSummoners, detail: fr.dashboard.summonersAndRunes, enabled: currentSettings.auto_summoners_enabled, pending: pendingKeys.has("auto_summoners_enabled"), disabledByMaster: !presetMaster.enabled, onToggle: () => toggle("auto_summoners_enabled") },
    { id: "auto-skin", label: fr.dashboard.skin, detail: currentSettings.skin_automation_enabled ? fr.dashboard.enabled : fr.dashboard.disabled, enabled: currentSettings.skin_automation_enabled, pending: pendingKeys.has("skin_automation_enabled"), disabledByMaster: !presetMaster.enabled, onToggle: () => void patchSetting("skin_automation_enabled", !currentSettings.skin_automation_enabled) },
    { id: "auto-play-again", label: fr.settings.playAgain, detail: fr.dashboard.returnToLobby, enabled: currentSettings.auto_play_again_enabled, pending: pendingKeys.has("auto_play_again_enabled"), onToggle: () => toggle("auto_play_again_enabled") },
  ] : [], [currentPresets?.selected_ban, currentSettings, pendingKeys, presetMaster.enabled]);

  if (presets.isPending && !currentPresets) return <div className="page-loading">{fr.common.loading}</div>;
  if (presets.isError && !currentPresets) return <div className="state-error"><strong>{fr.presets.championLoadError}</strong><span>{fr.app.localServerError}</span><Button variant="primary" type="button" onClick={() => void presets.refetch()}>{fr.common.retry}</Button></div>;

  const currentPhase = runtime?.connected ? phaseLabel(runtime.phase) : fr.runtime.notDetected;
  const championFor = (name: string, preview?: { champion_id: number | null }) => championCatalog.data?.items.find((item: Champion) => item.name.toLocaleLowerCase() === name.toLocaleLowerCase()) ?? (preview?.champion_id ? championCatalog.data?.items.find((item: Champion) => item.id === preview.champion_id) : undefined);
  return <div className="dashboard-page">
    <div className="page-heading dashboard-heading"><h1>{fr.dashboard.title}</h1></div>
    <PresetOnboardingBanner />
    <div className="phase-strip" role="status" aria-live="polite"><Activity size={14} aria-hidden="true" /><span>{fr.dashboard.currentPhase}</span><strong>{currentPhase}</strong></div>
    <AutomationStatus />
    <div className="dashboard-grid">
      <div className="dashboard-main">
        <section className="surface priority-section" aria-labelledby="slots-heading"><div className="section-head"><div><div className="section-label">{fr.dashboard.slots}</div><h2 id="slots-heading">{configuredCount}/3 {fr.dashboard.ready.toLowerCase()}</h2></div><a className="text-button" href="#presets">{fr.dashboard.edit} <ArrowUpRight size={14} aria-hidden="true" /></a></div><div className="priority-grid">{slotsData.map((slot, index) => <ChampionPriorityCard key={slots[index]} slotKey={slots[index]} slot={slot} index={index} spells={spells.data?.items ?? []} preview={previews[slots[index]]} champion={championFor(slot?.champion || "", previews[slots[index]])} onSkinModeChange={(mode) => void setSkinMode(slots[index], mode)} pending={pendingKeys.has(`skin_mode_${slots[index]}`)} />)}</div></section>
      </div>
      <aside className="dashboard-aside"><BanPanel banName={banName} autoBanEnabled={Boolean(currentSettings?.auto_ban_enabled && presetMaster.enabled)} preview={bootstrap.data?.ban_preview} champion={championFor(banName, bootstrap.data?.ban_preview ?? undefined)} /><QuickActions /></aside>
    </div>
    <AutomationBar items={automationItems} master={<PresetAutomationMaster enabled={presetMaster.enabled} ready={presetMaster.ready} pending={presetMaster.pending} errorMessage={presetMaster.errorMessage} onToggle={presetMaster.toggle} />} />
  </div>;
}

export { DashboardPage };
