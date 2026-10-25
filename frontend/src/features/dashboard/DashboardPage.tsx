import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, AlertTriangle, CheckCircle2, Info } from "lucide-react";

import { api } from "../../api/client";
import { Button } from "../../components/ui/button";
import { fr } from "../../content/fr";
import { queueStatusCopy } from "../../content/queueStatus";
import { cn } from "../../lib/cn";
import { phaseLabel } from "../../domain/runtime";
import { useRuntimeStore } from "../../stores/runtimeStore";
import type { BootstrapResponse, Champion, DashboardAction, RuntimeSnapshot, Settings, SettingsPatch } from "../../types/api";
import { presetSlotKeys, type PresetSlotKey } from "../../domain/presets";
import { PresetAutomationMaster, usePresetAutomationMaster } from "../automation/PresetAutomationMaster";
import { PresetOnboardingBanner } from "../automation/PresetOnboardingBanner";
import { AutomationBar, type AutomationItem } from "./AutomationBar";
import { BanPanel } from "./BanPanel";
import { ChampionPriorityCard } from "./ChampionPriorityCard";
import { QuickActions } from "./QuickActions";

const PresetEditorFlow = lazy(() => import("../presets/PresetEditorFlow").then(({ PresetEditorFlow: flow }) => ({ default: flow })));

const slots = presetSlotKeys;
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

function QueueAutomationStatus({ runtime }: { runtime: RuntimeSnapshot | null }) {
  const copy = queueStatusCopy;
  const knownQueue = Boolean(runtime?.queue_name);
  const queue = runtime?.queue_name || (runtime?.queue_id ? `File ${runtime.queue_id}` : "");
  let title: string = copy.clientMissing;
  let detail: string = copy.clientMissingDetail;
  let state: string = copy.stateWaiting;
  let tone: "warning" | "info" | "success" = "warning";
  let Icon = AlertTriangle;

  if (runtime?.connected && runtime.preset_queue_supported === false) {
    title = copy.unsupported(queue);
    detail = copy.unsupportedDetail;
    state = copy.stateUnsupported;
  } else if (runtime?.connected && runtime.preset_queue_supported === true) {
    if (!runtime.presets_enabled) {
      title = copy.paused(queue);
      detail = copy.pausedDetail;
      state = copy.statePaused;
      tone = "info";
      Icon = Info;
    } else if (runtime.phase === "ChampSelect") {
      title = copy.active(queue);
      detail = copy.activeDetail;
      state = copy.stateActive;
      tone = "success";
      Icon = CheckCircle2;
    } else {
      title = copy.available(queue);
      detail = copy.availableDetail;
      state = copy.stateAvailable;
      tone = "info";
      Icon = Info;
    }
  } else if (runtime?.connected && runtime.phase === "ChampSelect") {
    title = copy.unknownQueue;
    detail = copy.unknownQueueDetail;
    state = copy.stateUnknown;
  } else if (runtime?.connected && !knownQueue) {
    title = copy.waitingQueue;
    detail = copy.waitingQueueDetail;
    state = copy.stateWaiting;
  } else if (runtime?.connected) {
    title = copy.unknownQueue;
    detail = copy.unknownQueueDetail;
    state = copy.stateUnknown;
  }

  return <section className={cn("queue-status-card", `is-${tone}`)} aria-label={copy.label} role="status" aria-live="polite">
    <Icon size={16} aria-hidden="true" />
    <div className="queue-status-copy"><span>{copy.label}</span><strong>{title}</strong><p>{detail}</p></div>
    <span className="queue-status-pill">{state}</span>
  </section>;
}

function DashboardPage({ action, onActionClose }: { action?: DashboardAction; onActionClose: () => void }) {
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
  const [automationErrors, setAutomationErrors] = useState<Record<string, string>>({});
  const [slotOrder, setSlotOrder] = useState<PresetSlotKey[]>([...slots]);
  const [draggingSlot, setDraggingSlot] = useState<PresetSlotKey | null>(null);
  const [dragTargetSlot, setDragTargetSlot] = useState<PresetSlotKey | null>(null);
  const [dragPreviewOffsets, setDragPreviewOffsets] = useState<Partial<Record<PresetSlotKey, { x: number; y: number }>>>({});
  const [reorderCommit, setReorderCommit] = useState(false);
  const [reorderPending, setReorderPending] = useState(false);
  const [reorderMessage, setReorderMessage] = useState("");
  const [reorderError, setReorderError] = useState(false);
  const cardTriggerRefs = useRef<Record<PresetSlotKey, HTMLElement | null>>({ pick_1: null, pick_2: null, pick_3: null });
  const dragOriginOrderRef = useRef<PresetSlotKey[] | null>(null);
  const dragOriginRectsRef = useRef<Map<PresetSlotKey, DOMRect>>(new Map());
  const dragSourceRef = useRef<PresetSlotKey | null>(null);
  const dragTargetSlotRef = useRef<PresetSlotKey | null>(null);
  const banTriggerRef = useRef<HTMLElement | null>(null);
  const activeTriggerRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (action) activeTriggerRef.current = action === "ban" ? banTriggerRef.current : cardTriggerRefs.current[action];
  }, [action]);
  useEffect(() => { performance.mark("otp:t8-dashboard-ready"); }, []);
  const setPending = (key: string, pending: boolean) => setPendingKeys((current) => {
    const next = new Set(current);
    pending ? next.add(key) : next.delete(key);
    return next;
  });

  const persistSlotOrder = async (nextOrder: PresetSlotKey[], rollbackOrder: PresetSlotKey[] = slotOrder) => {
    if (reorderPending || nextOrder.every((key, index) => key === rollbackOrder[index])) return;
    const previousOrder = [...rollbackOrder];
    setSlotOrder(nextOrder);
    setReorderPending(true);
    setReorderMessage("");
    setReorderError(false);
    try {
      const updatedPresets = await api.reorderPresets({ order: nextOrder });
      await queryClient.cancelQueries({ queryKey: ["bootstrap"] });
      queryClient.setQueryData<BootstrapResponse>(["bootstrap"], (current) => {
        if (!current) return current;
        const presetPreviews: NonNullable<BootstrapResponse["preset_previews"]> = {};
        slots.forEach((slotKey, index) => {
          const preview = current.preset_previews?.[nextOrder[index]];
          if (preview) presetPreviews[slotKey] = preview;
        });
        return { ...current, presets: updatedPresets, preset_previews: presetPreviews };
      });
      queryClient.setQueryData(["presets"], updatedPresets);
      setSlotOrder([...slots]);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["presets"] }),
        queryClient.invalidateQueries({ queryKey: ["bootstrap"] }),
      ]);
      setReorderMessage(fr.dashboard.prioritySaved);
    } catch {
      setSlotOrder(previousOrder);
      setReorderMessage(fr.dashboard.prioritySaveFailed);
      setReorderError(true);
    } finally {
      setReorderPending(false);
    }
  };

  const beginCardDrag = (source: PresetSlotKey) => {
    dragOriginOrderRef.current = [...slotOrder];
    dragSourceRef.current = source;
    dragTargetSlotRef.current = null;
    dragOriginRectsRef.current = new Map(slots.flatMap((key) => {
      const card = cardTriggerRefs.current[key]?.closest<HTMLElement>(".priority-card");
      return card ? [[key, card.getBoundingClientRect()] as const] : [];
    }));
    setDragPreviewOffsets({});
    setDragTargetSlot(null);
    setDraggingSlot(source);
  };

  const previewCardDrop = (target: PresetSlotKey | null) => {
    if (target === dragTargetSlotRef.current) return;
    dragTargetSlotRef.current = target;
    setDragTargetSlot(target);

    const originOrder = dragOriginOrderRef.current;
    const source = dragSourceRef.current;
    if (!target || !originOrder || !source || target === source) {
      setDragPreviewOffsets({});
      return;
    }

    const sourceIndex = originOrder.indexOf(source);
    const targetIndex = originOrder.indexOf(target);
    const adjacentKey = originOrder[sourceIndex + (sourceIndex < targetIndex ? 1 : -1)];
    const sourceRect = dragOriginRectsRef.current.get(source);
    const adjacentRect = adjacentKey ? dragOriginRectsRef.current.get(adjacentKey) : undefined;
    if (sourceIndex < 0 || targetIndex < 0 || !sourceRect || !adjacentRect) {
      setDragPreviewOffsets({});
      return;
    }

    const stepX = sourceRect.left - adjacentRect.left;
    const stepY = sourceRect.top - adjacentRect.top;
    const offsets: Partial<Record<PresetSlotKey, { x: number; y: number }>> = {};
    if (sourceIndex < targetIndex) {
      for (let index = sourceIndex + 1; index <= targetIndex; index += 1) {
        offsets[originOrder[index]] = { x: stepX, y: stepY };
      }
    } else {
      for (let index = targetIndex; index < sourceIndex; index += 1) {
        offsets[originOrder[index]] = { x: stepX, y: stepY };
      }
    }
    setDragPreviewOffsets(offsets);
  };

  const cancelCardDrag = () => {
    setDragPreviewOffsets({});
  };

  const finishCardDrag = () => {
    setDraggingSlot(null);
    setDragTargetSlot(null);
    setDragPreviewOffsets({});
    dragOriginOrderRef.current = null;
    dragOriginRectsRef.current.clear();
    dragSourceRef.current = null;
    dragTargetSlotRef.current = null;
  };

  const reorderCard = (source: PresetSlotKey, target: PresetSlotKey) => {
    const originOrder = dragOriginOrderRef.current ?? slotOrder;
    const sourceIndex = originOrder.indexOf(source);
    const targetIndex = originOrder.indexOf(target);
    if (sourceIndex < 0 || targetIndex < 0 || sourceIndex === targetIndex) return;
    const nextOrder = [...originOrder];
    nextOrder.splice(sourceIndex, 1);
    nextOrder.splice(targetIndex, 0, source);
    if (dragSourceRef.current === source) {
      setReorderCommit(true);
      window.requestAnimationFrame(() => setReorderCommit(false));
    }
    void persistSlotOrder(nextOrder, originOrder);
  };

  const moveCard = (source: PresetSlotKey, delta: -1 | 1) => {
    const sourceIndex = slotOrder.indexOf(source);
    const targetIndex = sourceIndex + delta;
    if (sourceIndex < 0 || targetIndex < 0 || targetIndex >= slotOrder.length) return;
    const nextOrder = [...slotOrder];
    nextOrder.splice(sourceIndex, 1);
    nextOrder.splice(targetIndex, 0, source);
    void persistSlotOrder(nextOrder);
  };

  const patchSetting = async (key: string, value: unknown) => {
    const previous = queryClient.getQueryData<Settings>(["settings"]);
    setPending(key, true);
    setAutomationErrors((current) => { const next = { ...current }; delete next[key]; return next; });
    queryClient.setQueryData<Settings>(["settings"], (current) => current ? { ...current, [key]: value } : current);
    try {
      const next = await api.patchSettings({ [key]: value } as SettingsPatch);
      queryClient.setQueryData(["settings"], next);
      if (key === "presets_enabled") await queryClient.invalidateQueries({ queryKey: ["presets"] });
      await queryClient.invalidateQueries({ queryKey: ["bootstrap"] });
    } catch {
      if (previous) queryClient.setQueryData<Settings>(["settings"], (current) => current ? { ...current, [key]: previous[key as keyof Settings] } : previous);
      setAutomationErrors((current) => ({ ...current, [key]: fr.settings.failed }));
    } finally {
      setPending(key, false);
    }
  };

  const toggle = (key: ToggleKey) => {
    if (currentSettings) void patchSetting(key, !currentSettings[key]);
  };

  const automationItems = useMemo<AutomationItem[]>(() => currentSettings ? [
    { id: "auto-accept", label: fr.settings.autoAccept, detail: fr.dashboard.readyCheck, enabled: currentSettings.auto_accept_enabled, pending: pendingKeys.has("auto_accept_enabled"), error: automationErrors.auto_accept_enabled, onToggle: () => toggle("auto_accept_enabled") },
    { id: "auto-pick", label: fr.settings.autoPick, detail: fr.dashboard.prioritizedSlots, enabled: currentSettings.auto_pick_enabled, pending: pendingKeys.has("auto_pick_enabled"), disabledByMaster: !presetMaster.enabled, error: automationErrors.auto_pick_enabled, onToggle: () => toggle("auto_pick_enabled") },
    { id: "auto-ban", label: fr.settings.autoBan, detail: currentPresets?.selected_ban || fr.dashboard.noBan, enabled: currentSettings.auto_ban_enabled, pending: pendingKeys.has("auto_ban_enabled"), disabledByMaster: !presetMaster.enabled, error: automationErrors.auto_ban_enabled, onToggle: () => toggle("auto_ban_enabled") },
    { id: "auto-summoners", label: fr.settings.autoSummoners, detail: fr.dashboard.summonersAndRunes, enabled: currentSettings.auto_summoners_enabled, pending: pendingKeys.has("auto_summoners_enabled"), disabledByMaster: !presetMaster.enabled, error: automationErrors.auto_summoners_enabled, onToggle: () => toggle("auto_summoners_enabled") },
    { id: "auto-skin", label: fr.dashboard.skin, detail: currentSettings.skin_automation_enabled ? fr.dashboard.enabled : fr.dashboard.disabled, enabled: currentSettings.skin_automation_enabled, pending: pendingKeys.has("skin_automation_enabled"), disabledByMaster: !presetMaster.enabled, error: automationErrors.skin_automation_enabled, onToggle: () => void patchSetting("skin_automation_enabled", !currentSettings.skin_automation_enabled) },
    { id: "auto-play-again", label: fr.settings.playAgain, detail: fr.dashboard.returnToLobby, enabled: currentSettings.auto_play_again_enabled, pending: pendingKeys.has("auto_play_again_enabled"), error: automationErrors.auto_play_again_enabled, onToggle: () => toggle("auto_play_again_enabled") },
  ] : [], [automationErrors, currentPresets?.selected_ban, currentSettings, pendingKeys, presetMaster.enabled]);

  if (presets.isPending && !currentPresets) return <div className="page-loading">{fr.common.loading}</div>;
  if (presets.isError && !currentPresets) return <div className="state-error"><strong>{fr.presets.championLoadError}</strong><span>{fr.app.localServerError}</span><Button variant="primary" type="button" onClick={() => void presets.refetch()}>{fr.common.retry}</Button></div>;

  const currentPhase = runtime?.connected ? phaseLabel(runtime.phase) : fr.runtime.notDetected;
  const championFor = (name: string, preview?: { champion_id: number | null }) => championCatalog.data?.items.find((item: Champion) => item.name.toLocaleLowerCase() === name.toLocaleLowerCase()) ?? (preview?.champion_id ? championCatalog.data?.items.find((item: Champion) => item.id === preview.champion_id) : undefined);
  return <div className="dashboard-page">
    <div className="page-heading dashboard-heading"><h1>{fr.dashboard.title}</h1></div>
    <PresetOnboardingBanner />
    <div className="phase-strip" role="status" aria-live="polite"><Activity size={14} aria-hidden="true" /><span>{fr.dashboard.currentPhase}</span><strong>{currentPhase}</strong></div>
    <QueueAutomationStatus runtime={runtime} />
    <AutomationStatus />
    <div className="dashboard-grid">
      <div className="dashboard-main">
        <section className="surface priority-section" aria-labelledby="slots-heading"><div className="section-head"><div><div className="section-label">{fr.dashboard.slots}</div><h2 id="slots-heading">{configuredCount}/3 {fr.dashboard.ready.toLowerCase()}</h2></div><span className="field-hint priority-gesture-hint">{fr.dashboard.priorityHint}</span></div><div className={cn("priority-grid", reorderCommit && "is-reorder-committing")}>{slotOrder.map((slotKey, index) => {
          const slot = currentPresets?.slots[slotKey];
          return <ChampionPriorityCard key={slotKey} slotKey={slotKey} slot={slot} index={index} spells={spells.data?.items ?? []} preview={previews[slotKey]} champion={championFor(slot?.champion || "", previews[slotKey])} isOpen={action === slotKey} triggerRef={(node) => { cardTriggerRefs.current[slotKey] = node; if (node && action === slotKey) activeTriggerRef.current = node; }} reorderDisabled={reorderPending || Boolean(action)} isDragging={draggingSlot === slotKey} isDropTarget={dragTargetSlot === slotKey} previewOffset={dragPreviewOffsets[slotKey]} onMove={moveCard} onDragStart={beginCardDrag} onDragTarget={previewCardDrop} onDragEnd={finishCardDrag} onDragCancel={cancelCardDrag} onDrop={reorderCard} />;
        })}</div>{(reorderPending || reorderMessage) && <p className={cn("priority-reorder-feedback", reorderError && "is-error")} role={reorderError ? "alert" : "status"} aria-live="polite">{reorderPending ? fr.dashboard.prioritySaving : reorderMessage}</p>}</section>
      </div>
      <aside className="dashboard-aside"><BanPanel banName={banName} autoBanEnabled={Boolean(currentSettings?.auto_ban_enabled && presetMaster.enabled)} preview={bootstrap.data?.ban_preview} champion={championFor(banName, bootstrap.data?.ban_preview ?? undefined)} isOpen={action === "ban"} triggerRef={(node) => { banTriggerRef.current = node; if (node && action === "ban") activeTriggerRef.current = node; }} /><QuickActions /></aside>
    </div>
    <AutomationBar items={automationItems} master={<PresetAutomationMaster enabled={presetMaster.enabled} ready={presetMaster.ready} pending={presetMaster.pending} errorMessage={presetMaster.errorMessage} onToggle={presetMaster.toggle} />} />
    {action && <Suspense fallback={null}><PresetEditorFlow action={action} onClose={onActionClose} returnFocusRef={activeTriggerRef} /></Suspense>}
  </div>;
}

export { DashboardPage };
