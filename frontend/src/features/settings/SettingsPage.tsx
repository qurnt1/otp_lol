import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Database, Download, FileText, FolderOpen, Keyboard, Maximize2, RotateCcw, Upload } from "lucide-react";

import { api } from "../../api/client";
import { Button } from "../../components/ui/button";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { Select } from "../../components/ui/Select";
import { fr } from "../../content/fr";
import { catalogOrFallback } from "../../domain/catalog";
import { cn } from "../../lib/cn";
import type { Settings, SettingsImport, SettingsPatch } from "../../types/api";

const sections = ["general", "automations", "account", "links", "shortcuts", "appearance", "advanced"] as const;
type Section = typeof sections[number];
const sectionLabels: Record<Section, string> = { general: fr.settings.general, automations: fr.settings.automations, account: fr.settings.account, links: fr.settings.links, shortcuts: fr.settings.shortcuts, appearance: fr.settings.appearance, advanced: fr.settings.advanced };
type ManualSettingKey = "manual_summoner_name" | "hotkey_toggle_window" | "hotkey_open_site";

function applyTheme(theme: Settings["theme"]): void {
  document.documentElement.dataset.theme = theme === "flatly" ? "light" : "dark";
}

function ToggleRow({ label, description, checked, pending, error, onChange }: { label: string; description: string; checked: boolean; pending: boolean; error?: string; onChange: (value: boolean) => void }) {
  return <div className="settings-row"><div><strong>{label}</strong><p>{description}</p>{error && <small className="inline-error" role="alert">{error}</small>}</div><button className="switch" type="button" role="switch" aria-label={label} aria-checked={checked} aria-busy={pending} disabled={pending} onClick={() => onChange(!checked)}><span aria-hidden="true" /></button></div>;
}

function SelectRow({ label, description, value, options, pending, error, onChange }: { label: string; description: string; value: string; options: readonly { id: string; label: string }[]; pending: boolean; error?: string; onChange: (value: string) => void }) {
  return <div className="settings-row"><div><strong>{label}</strong><p>{description}</p>{error && <small className="inline-error" role="alert">{error}</small>}</div><Select className="settings-control" label={label} disabled={pending} value={value} options={options} onChange={onChange} /></div>;
}

export function SettingsPage() {
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.getSettings, staleTime: Infinity });
  const providers = useQuery({ queryKey: ["providers"], queryFn: api.getProviders, staleTime: Infinity });
  const [section, setSection] = useState<Section>("general");
  const [local, setLocal] = useState<Settings | null>(null);
  const [pendingKeys, setPendingKeys] = useState<Set<string>>(new Set());
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [feedback, setFeedback] = useState("");
  const [confirmReset, setConfirmReset] = useState(false);
  const [draft, setDraft] = useState<Partial<Settings>>({});
  const importInput = useRef<HTMLInputElement>(null);
  const submittedManualValues = useRef<Partial<Record<ManualSettingKey, string>>>({});
  useEffect(() => { if (settings.data) { setLocal(settings.data); applyTheme(settings.data.theme); setDraft({}); submittedManualValues.current = {}; } }, [settings.data]);

  const setPending = (key: string, pending: boolean) => setPendingKeys((current) => { const next = new Set(current); pending ? next.add(key) : next.delete(key); return next; });
  const save = async (values: SettingsPatch, key: string): Promise<boolean> => {
    if (!local) return false;
    const previousValue = local[key as keyof Settings];
    const optimistic = Object.fromEntries(Object.entries(values).filter(([, value]) => value !== null)) as Partial<Settings>;
    setPending(key, true);
    setErrors((current) => { const next = { ...current }; delete next[key]; return next; });
    setLocal((current) => current ? { ...current, ...optimistic } : current);
    queryClient.setQueryData<Settings>(["settings"], (current) => current ? { ...current, ...optimistic } : current);
    if (key === "theme" && optimistic.theme) applyTheme(optimistic.theme);
    try {
      const next = await api.patchSettings(values);
      setLocal(next);
      queryClient.setQueryData(["settings"], next);
      setFeedback(fr.settings.saved);
      window.setTimeout(() => setFeedback(""), 1800);
      setDraft((current) => { if (!(key in current)) return current; const next = { ...current }; delete next[key as keyof Settings]; return next; });
      return true;
    } catch (error) {
      setLocal((current) => current ? { ...current, [key]: previousValue } : current);
      queryClient.setQueryData<Settings>(["settings"], (current) => current ? { ...current, [key]: previousValue } : current);
      if (key === "theme" && (previousValue === "darkly" || previousValue === "flatly")) applyTheme(previousValue);
      setErrors((current) => ({ ...current, [key]: error instanceof Error ? error.message : fr.settings.failed }));
      return false;
    } finally {
      setPending(key, false);
    }
  };
  const update = <K extends keyof Settings>(key: K, value: Settings[K]) => void save({ [key]: value } as SettingsPatch, String(key));
  const manualUpdate = (key: ManualSettingKey, value: string) => { delete submittedManualValues.current[key]; setDraft((current) => ({ ...current, [key]: value })); setLocal((current) => current ? { ...current, [key]: value } : current); };
  const saveManual = (key: ManualSettingKey) => { const value = draft[key] ?? local?.[key]; if (typeof value !== "string" || pending(key) || submittedManualValues.current[key] === value) return; submittedManualValues.current[key] = value; void save({ [key]: value } as SettingsPatch, key).then((success) => { if (!success) delete submittedManualValues.current[key]; }); };
  const nativeApi = () => (window as Window & { pywebview?: { api?: { open_local_folder?: (value: string) => Promise<boolean>; toggle_fullscreen?: () => Promise<boolean> } } }).pywebview?.api;
  const openNativeFolder = (kind: "logs" | "appdata") => { const bridge = nativeApi(); if (bridge?.open_local_folder) void bridge.open_local_folder(kind); };
  const toggleFullscreen = () => { const bridge = nativeApi(); if (bridge?.toggle_fullscreen) void bridge.toggle_fullscreen(); };
  const downloadExport = async () => { const response = await fetch("/api/settings/export"); if (!response.ok) return; const blob = await response.blob(); const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = "otp-lol-settings.json"; anchor.click(); URL.revokeObjectURL(url); };
  const importFile = async (file: File) => {
    try {
      const payload = JSON.parse(await file.text()) as SettingsImport;
      const next = await api.importSettings(payload);
      setLocal(next);
      queryClient.setQueryData(["settings"], next);
      await queryClient.invalidateQueries({ queryKey: ["bootstrap"] });
      await queryClient.invalidateQueries({ queryKey: ["presets"] });
      applyTheme(next.theme);
      setDraft({});
      submittedManualValues.current = {};
      setErrors((current) => { const rest = { ...current }; delete rest.import; return rest; });
      setFeedback(fr.settings.saved);
    } catch (error) {
      setErrors((current) => ({ ...current, import: error instanceof Error ? error.message : fr.settings.importFailed }));
    }
  };
  const reset = async () => { setConfirmReset(false); setPending("reset", true); try { const next = await api.resetSettings(); setLocal(next); queryClient.setQueryData(["settings"], next); await queryClient.invalidateQueries({ queryKey: ["bootstrap"] }); applyTheme(next.theme); setDraft({}); submittedManualValues.current = {}; setFeedback(fr.settings.saved); } catch (error) { setErrors((current) => ({ ...current, reset: error instanceof Error ? error.message : fr.settings.failed })); } finally { setPending("reset", false); } };
  if (!local) return <div className="page-loading">{fr.common.loading}</div>;
  const statsSites = catalogOrFallback(providers.data, "stats");
  const hotkeySites = catalogOrFallback(providers.data, "hotkey");
  const regions = catalogOrFallback(providers.data, "regions");
  const pending = (key: string) => pendingKeys.has(key);
  return <div className="settings-page">
    <div className="page-heading"><div><h1>{fr.settings.title}</h1><p>{fr.settings.subtitle}</p></div><span className="feedback" role="status" aria-live="polite">{feedback}</span></div>
    <div className="settings-layout"><nav className="settings-nav" aria-label={fr.runtime.settingsSectionsLabel}>{sections.map((key) => <button key={key} className={cn(section === key && "is-active")} type="button" aria-current={section === key ? "page" : undefined} onClick={() => setSection(key)}>{sectionLabels[key]}</button>)}</nav><section className="surface settings-section" aria-labelledby="settings-section-heading"><div className="section-head"><h2 id="settings-section-heading">{sectionLabels[section]}</h2>{pendingKeys.size > 0 && <span className="feedback">{fr.settings.saving}</span>}</div>
      {section === "general" && <><ToggleRow label={fr.settings.autoHide} description={fr.settings.descriptions.autoHide} checked={local.auto_hide_on_connect} pending={pending("auto_hide_on_connect")} error={errors.auto_hide_on_connect} onChange={(value) => update("auto_hide_on_connect", value)} /><ToggleRow label={fr.settings.closeOnExit} description={fr.settings.descriptions.closeOnExit} checked={local.close_app_on_lol_exit} pending={pending("close_app_on_lol_exit")} error={errors.close_app_on_lol_exit} onChange={(value) => update("close_app_on_lol_exit", value)} /></>}
      {section === "automations" && <><ToggleRow label={fr.settings.autoAccept} description={fr.settings.descriptions.autoAccept} checked={local.auto_accept_enabled} pending={pending("auto_accept_enabled")} error={errors.auto_accept_enabled} onChange={(value) => update("auto_accept_enabled", value)} /><ToggleRow label={fr.settings.autoPick} description={fr.settings.descriptions.autoPick} checked={local.auto_pick_enabled} pending={pending("auto_pick_enabled")} error={errors.auto_pick_enabled} onChange={(value) => update("auto_pick_enabled", value)} /><ToggleRow label={fr.settings.autoBan} description={fr.settings.descriptions.autoBan} checked={local.auto_ban_enabled} pending={pending("auto_ban_enabled")} error={errors.auto_ban_enabled} onChange={(value) => update("auto_ban_enabled", value)} /><ToggleRow label={fr.settings.autoSummoners} description={fr.settings.descriptions.autoSummoners} checked={local.auto_summoners_enabled} pending={pending("auto_summoners_enabled")} error={errors.auto_summoners_enabled} onChange={(value) => update("auto_summoners_enabled", value)} /><ToggleRow label={fr.settings.skinAutomation} description={fr.settings.descriptions.skinAutomation} checked={local.skin_automation_enabled} pending={pending("skin_automation_enabled")} error={errors.skin_automation_enabled} onChange={(value) => update("skin_automation_enabled", value)} /><ToggleRow label={fr.settings.playAgain} description={fr.settings.descriptions.playAgain} checked={local.auto_play_again_enabled} pending={pending("auto_play_again_enabled")} error={errors.auto_play_again_enabled} onChange={(value) => update("auto_play_again_enabled", value)} /></>}
      {section === "account" && <><ToggleRow label={fr.settings.manualAccount} description={fr.settings.descriptions.manualAccount} checked={!local.summoner_name_auto_detect} pending={pending("summoner_name_auto_detect")} error={errors.summoner_name_auto_detect} onChange={(value) => update("summoner_name_auto_detect", !value)} /><div className="settings-form"><label><span>{fr.settings.riotId}</span><input className="field-input" value={local.manual_summoner_name} disabled={local.summoner_name_auto_detect || pending("manual_summoner_name")} onChange={(event) => manualUpdate("manual_summoner_name", event.target.value)} onBlur={() => saveManual("manual_summoner_name")} onKeyDown={(event) => { if (event.key === "Enter") saveManual("manual_summoner_name"); }} placeholder={fr.settings.riotIdPlaceholder} />{errors.manual_summoner_name && <small className="inline-error" role="alert">{errors.manual_summoner_name}</small>}</label><label><span>{fr.settings.region}</span><Select className="settings-control" label={fr.settings.region} value={local.manual_region} disabled={local.summoner_name_auto_detect || pending("manual_region")} options={regions} onChange={(value) => update("manual_region", value)} /></label></div></>}
      {section === "links" && <><SelectRow label={fr.settings.statsSite} description={fr.settings.descriptions.statsSite} value={local.preferred_stats_site} options={statsSites} pending={pending("preferred_stats_site")} error={errors.preferred_stats_site} onChange={(value) => update("preferred_stats_site", value)} /><SelectRow label={fr.settings.hotkeySite} description={fr.settings.descriptions.hotkeySite} value={local.preferred_hotkey_site} options={hotkeySites} pending={pending("preferred_hotkey_site")} error={errors.preferred_hotkey_site} onChange={(value) => update("preferred_hotkey_site", value)} /></>}
      {section === "shortcuts" && <div className="settings-form"><label><span><Keyboard size={13} aria-hidden="true" />{fr.settings.toggleHotkey}</span><input className="field-input" value={draft.hotkey_toggle_window ?? local.hotkey_toggle_window} disabled={pending("hotkey_toggle_window")} onChange={(event) => manualUpdate("hotkey_toggle_window", event.target.value)} onBlur={() => saveManual("hotkey_toggle_window")} onKeyDown={(event) => { if (event.key === "Enter") saveManual("hotkey_toggle_window"); }} />{errors.hotkey_toggle_window && <small className="inline-error" role="alert">{errors.hotkey_toggle_window}</small>}</label><label><span><Keyboard size={13} aria-hidden="true" />{fr.settings.statsHotkey}</span><input className="field-input" value={draft.hotkey_open_site ?? local.hotkey_open_site} disabled={pending("hotkey_open_site")} onChange={(event) => manualUpdate("hotkey_open_site", event.target.value)} onBlur={() => saveManual("hotkey_open_site")} onKeyDown={(event) => { if (event.key === "Enter") saveManual("hotkey_open_site"); }} />{errors.hotkey_open_site && <small className="inline-error" role="alert">{errors.hotkey_open_site}</small>}</label></div>}
      {section === "appearance" && <SelectRow label={fr.settings.theme} description={fr.settings.descriptions.theme} value={local.theme} options={[{ id: "darkly", label: fr.settings.dark }, { id: "flatly", label: fr.settings.light }]} pending={pending("theme")} error={errors.theme} onChange={(value) => { document.documentElement.dataset.theme = value === "flatly" ? "light" : "dark"; update("theme", value as Settings["theme"]); }} />}
      {section === "advanced" && <div className="advanced-settings">
        <section className="advanced-group" aria-labelledby="advanced-files-heading">
          <div className="advanced-group-heading"><div className="advanced-group-icon"><Database size={16} aria-hidden="true" /></div><div><h3 id="advanced-files-heading">{fr.settings.advancedFiles}</h3><p>{fr.settings.advancedFilesDescription}</p></div></div>
          <div className="advanced-actions">
            <AdvancedAction icon={<FileText size={15} aria-hidden="true" />} title={fr.settings.logs} description={fr.settings.advancedDescriptions.logs} onClick={() => openNativeFolder("logs")} />
            <AdvancedAction icon={<FolderOpen size={15} aria-hidden="true" />} title={fr.settings.appData} description={fr.settings.advancedDescriptions.appData} onClick={() => openNativeFolder("appdata")} />
          </div>
        </section>
        <section className="advanced-group" aria-labelledby="advanced-config-heading">
          <div className="advanced-group-heading"><div className="advanced-group-icon"><FolderOpen size={16} aria-hidden="true" /></div><div><h3 id="advanced-config-heading">{fr.settings.advancedConfig}</h3><p>{fr.settings.advancedConfigDescription}</p></div></div>
          <div className="advanced-actions">
            <AdvancedAction icon={<Download size={15} aria-hidden="true" />} title={fr.settings.export} description={fr.settings.advancedDescriptions.export} onClick={() => void downloadExport()} />
            <AdvancedAction icon={<Upload size={15} aria-hidden="true" />} title={fr.settings.import} description={fr.settings.advancedDescriptions.import} onClick={() => importInput.current?.click()} />
            <AdvancedAction icon={<RotateCcw size={15} aria-hidden="true" />} title={fr.settings.reset} description={fr.settings.advancedDescriptions.reset} tone="danger" disabled={pending("reset")} onClick={() => setConfirmReset(true)} />
            <input ref={importInput} id="settings-import" className="sr-only" type="file" accept="application/json,.json" aria-label={fr.settings.import} onChange={(event) => { const file = event.target.files?.[0]; if (file) void importFile(file); event.currentTarget.value = ""; }} />
          </div>
          {errors.import && <small className="inline-error" role="alert">{errors.import}</small>}
        </section>
        <section className="advanced-group" aria-labelledby="advanced-window-heading">
          <div className="advanced-group-heading"><div className="advanced-group-icon"><Maximize2 size={16} aria-hidden="true" /></div><div><h3 id="advanced-window-heading">{fr.settings.advancedWindow}</h3><p>{fr.settings.advancedWindowDescription}</p></div></div>
          <div className="advanced-actions"><AdvancedAction icon={<Maximize2 size={15} aria-hidden="true" />} title={fr.settings.fullscreen} description={fr.settings.advancedDescriptions.fullscreen} onClick={toggleFullscreen} /></div>
        </section>
      </div>}
    </section></div>
    <ConfirmDialog open={confirmReset} title={fr.settings.reset} description={fr.settings.resetDescription} confirmLabel={fr.settings.resetConfirm} onCancel={() => setConfirmReset(false)} onConfirm={() => void reset()} />
  </div>;
}

function AdvancedAction({ icon, title, description, tone, disabled = false, onClick }: { icon: ReactNode; title: string; description: string; tone?: "danger"; disabled?: boolean; onClick: () => void }) {
  return <button className={cn("advanced-action", tone === "danger" && "is-danger")} type="button" disabled={disabled} onClick={onClick}><span className="advanced-action-icon">{icon}</span><span className="advanced-action-copy"><strong>{title}</strong><small>{description}</small></span><ChevronRight size={14} aria-hidden="true" /></button>;
}
