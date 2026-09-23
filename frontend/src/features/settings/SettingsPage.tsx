import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, ChevronRight, Database, Download, Eraser, FileText, FolderOpen, Keyboard, Maximize2, RotateCcw, Upload } from "lucide-react";

import { api } from "../../api/client";
import { Button } from "../../components/ui/button";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { Select } from "../../components/ui/Select";
import { fr } from "../../content/fr";
import { presetAutomationCopy } from "../../content/presetAutomation";
import { diagnosticsCopy } from "../diagnostics/copy";
import { regionOptionsOrFallback } from "../../domain/catalog";
import { cn } from "../../lib/cn";
import { useRuntimeStore } from "../../stores/runtimeStore";
import { openLocalFolder, toggleFullscreen } from "../../domain/external";
import { useNativeBridgeReady } from "../../hooks/useNativeBridgeReady";
import type { Settings, SettingsImport, SettingsPatch, SettingsSection } from "../../types/api";
import { settingsSections } from "../../app/routes";

const sectionLabels: Record<SettingsSection, string> = { general: fr.settings.general, automations: fr.settings.automations, account: fr.settings.account, links: fr.settings.links, shortcuts: fr.settings.shortcuts, appearance: fr.settings.appearance, advanced: fr.settings.advanced };
type ManualSettingKey = "manual_summoner_name" | "hotkey_toggle_window" | "hotkey_open_site";
const accountLinkSettingKeys = new Set(["summoner_name_auto_detect", "manual_summoner_name", "manual_region"]);

function applyTheme(theme: Settings["theme"]): void {
  document.documentElement.dataset.theme = theme === "flatly" ? "light" : "dark";
}

function ToggleRow({ label, description, checked, pending, disabledByMaster = false, error, onChange }: { label: string; description: string; checked: boolean; pending: boolean; disabledByMaster?: boolean; error?: string; onChange: (value: boolean) => void }) {
  return <div className={cn("settings-row", disabledByMaster && "is-master-disabled")}><div><strong>{label}</strong><p>{description}</p>{disabledByMaster && <small className="field-hint">{presetAutomationCopy.masterRequired}</small>}{error && <small className="inline-error" role="alert">{error}</small>}</div><button className="switch" type="button" role="switch" aria-label={label} aria-checked={checked} aria-busy={pending} title={disabledByMaster ? presetAutomationCopy.masterRequired : undefined} disabled={pending || disabledByMaster} onClick={() => onChange(!checked)}><span aria-hidden="true" /></button></div>;
}

function SelectRow({ label, description, value, options, pending, error, onChange }: { label: string; description: string; value: string; options: readonly { id: string; label: string }[]; pending: boolean; error?: string; onChange: (value: string) => void }) {
  return <div className="settings-row"><div><strong>{label}</strong><p>{description}</p>{error && <small className="inline-error" role="alert">{error}</small>}</div><Select className="settings-control" label={label} disabled={pending} value={value} options={options} onChange={onChange} /></div>;
}

export function SettingsPage({ section, onSectionChange }: { section: SettingsSection; onSectionChange: (section: SettingsSection) => void }) {
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.getSettings, staleTime: Infinity });
  const accountIdentity = useQuery({ queryKey: ["account-identity"], queryFn: api.getAccountIdentity, staleTime: Infinity, enabled: section === "account", retry: false });
  const providers = useQuery({ queryKey: ["providers"], queryFn: api.getProviders, staleTime: Infinity });
  const runtime = useRuntimeStore((state) => state.runtime);
  const nativeBridgeReady = useNativeBridgeReady();
  const [local, setLocal] = useState<Settings | null>(null);
  const [pendingKeys, setPendingKeys] = useState<Set<string>>(new Set());
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [feedback, setFeedback] = useState("");
  const [confirmReset, setConfirmReset] = useState(false);
  const [confirmResetPresets, setConfirmResetPresets] = useState(false);
  const [confirmClearPresets, setConfirmClearPresets] = useState(false);
  const [confirmCopyAccount, setConfirmCopyAccount] = useState(false);
  const [confirmForgetAccount, setConfirmForgetAccount] = useState(false);
  const [draft, setDraft] = useState<Partial<Settings>>({});
  const importInput = useRef<HTMLInputElement>(null);
  const submittedManualValues = useRef<Partial<Record<ManualSettingKey, string>>>({});
  useEffect(() => { if (settings.data) { setLocal(settings.data); applyTheme(settings.data.theme); } }, [settings.data]);

  const liveDetectedAccount = runtime?.connected && runtime.riot_id && runtime.region
    ? { riotId: runtime.riot_id, region: runtime.region }
    : null;
  const savedDetectedAccount = local?.auto_detected_account_valid
    ? { riotId: local.auto_detected_riot_id, region: local.auto_detected_region }
    : null;
  const hasSavedDetectedAccount = Boolean(
    local?.auto_detected_riot_id || local?.auto_detected_region || local?.auto_detected_platform,
  );
  const detectedAccount = runtime?.connected ? liveDetectedAccount : savedDetectedAccount;
  const fallbackAccountSource = runtime?.connected ? "connected" : savedDetectedAccount ? "saved" : local?.summoner_name_auto_detect === false ? "manual" : "unavailable";
  const accountSource = accountIdentity.data?.source && accountIdentity.data.source !== "unavailable" ? accountIdentity.data.source : fallbackAccountSource;

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
      if (accountLinkSettingKeys.has(key)) {
        void queryClient.invalidateQueries({ queryKey: ["account-identity"] });
      }
      if (key === "preferred_stats_site" || accountLinkSettingKeys.has(key)) {
        void queryClient.invalidateQueries({ queryKey: ["stats-link"] });
      }
      if (key === "preferred_hotkey_site" || accountLinkSettingKeys.has(key)) {
        void queryClient.invalidateQueries({ queryKey: ["live-stats-link"] });
      }
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
  const copyDetectedAccount = async () => {
    if (!local || !detectedAccount) return;
    setConfirmCopyAccount(false);
    const values: SettingsPatch = {
      manual_summoner_name: detectedAccount.riotId,
      manual_region: detectedAccount.region as SettingsPatch["manual_region"],
    };
    setPending("copy-detected-account", true);
    setErrors((current) => { const next = { ...current }; delete next["copy-detected-account"]; return next; });
    const optimisticValues = {
      manual_summoner_name: detectedAccount.riotId,
      manual_region: detectedAccount.region,
    };
    setLocal((current) => current ? { ...current, ...optimisticValues } : current);
    queryClient.setQueryData<Settings>(["settings"], (current) => current ? { ...current, ...optimisticValues } : current);
    try {
      const next = await api.patchSettings(values);
      setLocal(next);
      queryClient.setQueryData(["settings"], next);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["account-identity"] }),
        queryClient.invalidateQueries({ queryKey: ["stats-link"] }),
        queryClient.invalidateQueries({ queryKey: ["live-stats-link"] }),
      ]);
      setFeedback(fr.settings.saved);
      window.setTimeout(() => setFeedback(""), 1800);
    } catch (error) {
      setLocal((current) => current ? { ...current, manual_summoner_name: local.manual_summoner_name, manual_region: local.manual_region } : current);
      queryClient.setQueryData<Settings>(["settings"], (current) => current ? { ...current, manual_summoner_name: local.manual_summoner_name, manual_region: local.manual_region } : current);
      setErrors((current) => ({ ...current, "copy-detected-account": error instanceof Error ? error.message : fr.account.copyFailed }));
    } finally {
      setPending("copy-detected-account", false);
    }
  };
  const forgetDetectedAccount = async () => {
    setConfirmForgetAccount(false);
    setPending("forget-detected-account", true);
    setErrors((current) => { const next = { ...current }; delete next["forget-detected-account"]; return next; });
    try {
      const next = await api.clearLastDetectedAccount();
      setLocal(next);
      queryClient.setQueryData(["settings"], next);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["account-identity"] }),
        queryClient.invalidateQueries({ queryKey: ["stats-link"] }),
        queryClient.invalidateQueries({ queryKey: ["live-stats-link"] }),
      ]);
      setFeedback(fr.settings.saved);
      window.setTimeout(() => setFeedback(""), 1800);
    } catch (error) {
      setErrors((current) => ({ ...current, "forget-detected-account": error instanceof Error ? error.message : fr.account.forgetFailed }));
    } finally {
      setPending("forget-detected-account", false);
    }
  };
  const requestCopyDetectedAccount = () => {
    if (!detectedAccount) return;
    if (local?.manual_summoner_name.trim() && (
      local.manual_summoner_name !== detectedAccount.riotId || local.manual_region !== detectedAccount.region
    )) {
      setConfirmCopyAccount(true);
    } else {
      void copyDetectedAccount();
    }
  };
  const manualUpdate = (key: ManualSettingKey, value: string) => { delete submittedManualValues.current[key]; setDraft((current) => ({ ...current, [key]: value })); setLocal((current) => current ? { ...current, [key]: value } : current); };
  const saveManual = (key: ManualSettingKey) => { const value = draft[key] ?? local?.[key]; if (typeof value !== "string" || pending(key) || submittedManualValues.current[key] === value) return; submittedManualValues.current[key] = value; void save({ [key]: value } as SettingsPatch, key).then((success) => { if (!success) delete submittedManualValues.current[key]; }); };
  const openNativeFolder = (kind: "logs" | "appdata") => { if (nativeBridgeReady) void openLocalFolder(kind); };
  const toggleNativeFullscreen = () => { if (nativeBridgeReady) void toggleFullscreen(); };
  const downloadExport = async () => {
    setPending("export", true);
    setErrors((current) => { const next = { ...current }; delete next.export; return next; });
    try {
      const response = await fetch("/api/settings/export");
      if (!response.ok) throw new Error("Settings export failed");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "otp-lol-settings.json";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch {
      setErrors((current) => ({ ...current, export: fr.settings.exportFailed }));
    } finally {
      setPending("export", false);
    }
  };
  const importFile = async (file: File) => {
    try {
      const payload = JSON.parse(await file.text()) as SettingsImport;
      const next = await api.importSettings(payload);
      setLocal(next);
      queryClient.setQueryData(["settings"], next);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["account-identity"] }),
        queryClient.invalidateQueries({ queryKey: ["stats-link"] }),
        queryClient.invalidateQueries({ queryKey: ["live-stats-link"] }),
      ]);
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
  const reset = async () => { setConfirmReset(false); setPending("reset", true); try { const next = await api.resetSettings(); setLocal(next); queryClient.setQueryData(["settings"], next); await Promise.all([queryClient.invalidateQueries({ queryKey: ["settings"] }), queryClient.invalidateQueries({ queryKey: ["presets"] }), queryClient.invalidateQueries({ queryKey: ["bootstrap"] }), queryClient.invalidateQueries({ queryKey: ["account-identity"] }), queryClient.invalidateQueries({ queryKey: ["stats-link"] }), queryClient.invalidateQueries({ queryKey: ["live-stats-link"] })]); applyTheme(next.theme); setDraft({}); submittedManualValues.current = {}; setFeedback(fr.settings.saved); } catch (error) { setErrors((current) => ({ ...current, reset: error instanceof Error ? error.message : fr.settings.failed })); } finally { setPending("reset", false); } };
  const resetPresets = async () => { setConfirmResetPresets(false); setPending("reset-presets", true); try { const next = await api.resetPresets(); setLocal(next); queryClient.setQueryData(["settings"], next); await Promise.all([queryClient.invalidateQueries({ queryKey: ["settings"] }), queryClient.invalidateQueries({ queryKey: ["presets"] }), queryClient.invalidateQueries({ queryKey: ["bootstrap"] })]); setErrors((current) => { const rest = { ...current }; delete rest["reset-presets"]; return rest; }); setFeedback(fr.settings.saved); } catch (error) { setErrors((current) => ({ ...current, "reset-presets": error instanceof Error ? error.message : fr.settings.failed })); } finally { setPending("reset-presets", false); } };
  const clearPresets = async () => { setConfirmClearPresets(false); setPending("clear-presets", true); try { const next = await api.clearPresets(); setLocal(next); queryClient.setQueryData(["settings"], next); await Promise.all([queryClient.invalidateQueries({ queryKey: ["settings"] }), queryClient.invalidateQueries({ queryKey: ["presets"] }), queryClient.invalidateQueries({ queryKey: ["bootstrap"] })]); setErrors((current) => { const rest = { ...current }; delete rest["clear-presets"]; return rest; }); setFeedback(fr.settings.saved); } catch (error) { setErrors((current) => ({ ...current, "clear-presets": error instanceof Error ? error.message : fr.settings.failed })); } finally { setPending("clear-presets", false); } };
  if (!local) return <div className="page-loading">{fr.common.loading}</div>;
  const regions = regionOptionsOrFallback(providers.data);
  const pending = (key: string) => pendingKeys.has(key);
  return <div className="settings-page">
    <div className="page-heading"><div><h1>{fr.settings.title}</h1><p>{fr.settings.subtitle}</p></div><span className="feedback" role="status" aria-live="polite">{feedback}</span></div>
    <div className="settings-layout"><nav className="settings-nav" aria-label={fr.runtime.settingsSectionsLabel}>{settingsSections.map((key) => <button key={key} id={`settings-nav-${key}`} className={cn(section === key && "is-active")} type="button" aria-current={section === key ? "page" : undefined} onClick={() => onSectionChange(key)}>{sectionLabels[key]}</button>)}</nav><section className="surface settings-section" aria-labelledby={`settings-nav-${section}`}>
      {(section !== "advanced" || pendingKeys.size > 0) && <div className="section-head">{section !== "advanced" && <h2>{sectionLabels[section]}</h2>}{pendingKeys.size > 0 && <span className="feedback">{fr.settings.saving}</span>}</div>}
      {section === "general" && <><ToggleRow label={fr.settings.autoHide} description={fr.settings.descriptions.autoHide} checked={local.auto_hide_on_connect} pending={pending("auto_hide_on_connect")} error={errors.auto_hide_on_connect} onChange={(value) => update("auto_hide_on_connect", value)} /><ToggleRow label={fr.settings.closeOnExit} description={fr.settings.descriptions.closeOnExit} checked={local.close_app_on_lol_exit} pending={pending("close_app_on_lol_exit")} error={errors.close_app_on_lol_exit} onChange={(value) => update("close_app_on_lol_exit", value)} /></>}
      {section === "automations" && <><ToggleRow label={fr.settings.autoAccept} description={fr.settings.descriptions.autoAccept} checked={local.auto_accept_enabled} pending={pending("auto_accept_enabled")} error={errors.auto_accept_enabled} onChange={(value) => update("auto_accept_enabled", value)} /><ToggleRow label={fr.settings.autoPick} description={fr.settings.descriptions.autoPick} checked={local.auto_pick_enabled} pending={pending("auto_pick_enabled")} disabledByMaster={!local.presets_enabled} error={errors.auto_pick_enabled} onChange={(value) => update("auto_pick_enabled", value)} /><ToggleRow label={fr.settings.autoBan} description={fr.settings.descriptions.autoBan} checked={local.auto_ban_enabled} pending={pending("auto_ban_enabled")} disabledByMaster={!local.presets_enabled} error={errors.auto_ban_enabled} onChange={(value) => update("auto_ban_enabled", value)} /><ToggleRow label={fr.settings.autoSummoners} description={fr.settings.descriptions.autoSummoners} checked={local.auto_summoners_enabled} pending={pending("auto_summoners_enabled")} disabledByMaster={!local.presets_enabled} error={errors.auto_summoners_enabled} onChange={(value) => update("auto_summoners_enabled", value)} /><ToggleRow label={fr.settings.skinAutomation} description={fr.settings.descriptions.skinAutomation} checked={local.skin_automation_enabled} pending={pending("skin_automation_enabled")} disabledByMaster={!local.presets_enabled} error={errors.skin_automation_enabled} onChange={(value) => update("skin_automation_enabled", value)} /><ToggleRow label={fr.settings.playAgain} description={fr.settings.descriptions.playAgain} checked={local.auto_play_again_enabled} pending={pending("auto_play_again_enabled")} error={errors.auto_play_again_enabled} onChange={(value) => update("auto_play_again_enabled", value)} /></>}
      {section === "account" && <>
        <ToggleRow label={fr.settings.manualAccount} description={local.summoner_name_auto_detect ? fr.settings.descriptions.autoDetectAccount : fr.settings.descriptions.manualAccount} checked={local.summoner_name_auto_detect} pending={pending("summoner_name_auto_detect")} error={errors.summoner_name_auto_detect} onChange={(value) => update("summoner_name_auto_detect", value)} />
        <div className="settings-form">
          <label>
            <span>{fr.settings.riotId}</span>
            <input
              className="field-input"
              value={local.summoner_name_auto_detect ? detectedAccount?.riotId ?? "" : draft.manual_summoner_name ?? local.manual_summoner_name}
              disabled={local.summoner_name_auto_detect || pending("manual_summoner_name")}
              onChange={(event) => manualUpdate("manual_summoner_name", event.target.value)}
              onBlur={() => saveManual("manual_summoner_name")}
              onKeyDown={(event) => { if (event.key === "Enter") saveManual("manual_summoner_name"); }}
              placeholder={local.summoner_name_auto_detect ? (runtime?.connected ? fr.account.waitingCurrent : fr.account.noSavedAccount) : fr.settings.riotIdPlaceholder}
            />
            <small className="field-hint" role="status">
              {!local.summoner_name_auto_detect || accountSource === "manual"
                ? fr.account.manualAccount
                : accountSource === "connected"
                  ? liveDetectedAccount ? fr.account.liveAccount(liveDetectedAccount.region.toUpperCase()) : fr.account.waitingCurrent
                  : accountSource === "saved"
                    ? savedDetectedAccount ? fr.account.savedOffline(savedDetectedAccount.region.toUpperCase()) : fr.account.noSavedAccount
                    : fr.account.noSavedAccount}
            </small>
            {errors.manual_summoner_name && <small className="inline-error" role="alert">{errors.manual_summoner_name}</small>}
          </label>
          <label><span>{fr.settings.region}</span><Select className="settings-control" label={fr.settings.region} value={local.summoner_name_auto_detect ? detectedAccount?.region ?? "" : local.manual_region} disabled={local.summoner_name_auto_detect || pending("manual_region")} options={regions} onChange={(value) => update("manual_region", value)} /></label>
        </div>
        {(detectedAccount || hasSavedDetectedAccount) && <div className="settings-account-actions">
          {detectedAccount && !local.summoner_name_auto_detect && <p><strong>{fr.account.manualSavedLabel} :</strong> {detectedAccount.riotId} · {detectedAccount.region.toUpperCase()}</p>}
          {detectedAccount && <Button type="button" disabled={pending("copy-detected-account")} onClick={requestCopyDetectedAccount}>{fr.account.copyDetected}</Button>}
          {hasSavedDetectedAccount && <Button variant="danger" type="button" disabled={pending("forget-detected-account")} onClick={() => setConfirmForgetAccount(true)}>{fr.account.forgetDetected}</Button>}
          {detectedAccount && local.summoner_name_auto_detect && <small className="field-hint">{fr.account.manualCopyHint}</small>}
          {errors["copy-detected-account"] && <small className="inline-error" role="alert">{errors["copy-detected-account"]}</small>}
        </div>}
        {errors["forget-detected-account"] && <small className="inline-error" role="alert">{errors["forget-detected-account"]}</small>}
      </>}
      {section === "links" && <div className="settings-row"><div><strong>{fr.settings.links}</strong><p>{fr.settings.linksHint}</p></div><a className="button button-secondary" href="#statistics">{fr.nav.statistics}</a><a className="button button-secondary" href="#live">{fr.nav.live}</a></div>}
      {section === "shortcuts" && <div className="settings-form"><label><span><Keyboard size={13} aria-hidden="true" />{fr.settings.toggleHotkey}</span><input className="field-input" value={draft.hotkey_toggle_window ?? local.hotkey_toggle_window} disabled={pending("hotkey_toggle_window")} onChange={(event) => manualUpdate("hotkey_toggle_window", event.target.value)} onBlur={() => saveManual("hotkey_toggle_window")} onKeyDown={(event) => { if (event.key === "Enter") saveManual("hotkey_toggle_window"); }} />{errors.hotkey_toggle_window && <small className="inline-error" role="alert">{errors.hotkey_toggle_window}</small>}</label><label><span><Keyboard size={13} aria-hidden="true" />{fr.settings.statsHotkey}</span><input className="field-input" value={draft.hotkey_open_site ?? local.hotkey_open_site} disabled={pending("hotkey_open_site")} onChange={(event) => manualUpdate("hotkey_open_site", event.target.value)} onBlur={() => saveManual("hotkey_open_site")} onKeyDown={(event) => { if (event.key === "Enter") saveManual("hotkey_open_site"); }} />{errors.hotkey_open_site && <small className="inline-error" role="alert">{errors.hotkey_open_site}</small>}</label></div>}
      {section === "appearance" && <SelectRow label={fr.settings.theme} description={fr.settings.descriptions.theme} value={local.theme} options={[{ id: "darkly", label: fr.settings.dark }, { id: "flatly", label: fr.settings.light }]} pending={pending("theme")} error={errors.theme} onChange={(value) => { document.documentElement.dataset.theme = value === "flatly" ? "light" : "dark"; update("theme", value as Settings["theme"]); }} />}
      {section === "advanced" && <div className="advanced-settings">
        <section className="advanced-group" aria-labelledby="advanced-files-heading">
          <div className="advanced-group-heading"><div className="advanced-group-icon"><Database size={16} aria-hidden="true" /></div><div><h3 id="advanced-files-heading">{fr.settings.advancedFiles}</h3><p>{fr.settings.advancedFilesDescription}</p></div></div>
          <div className="advanced-actions">
            <AdvancedAction icon={<FileText size={15} aria-hidden="true" />} title={fr.settings.logs} description={fr.settings.advancedDescriptions.logs} onClick={() => openNativeFolder("logs")} />
            <AdvancedAction icon={<FolderOpen size={15} aria-hidden="true" />} title={fr.settings.appData} description={fr.settings.advancedDescriptions.appData} onClick={() => openNativeFolder("appdata")} />
            <AdvancedAction icon={<Activity size={15} aria-hidden="true" />} title={diagnosticsCopy.title} description={diagnosticsCopy.settingsDescription} onClick={() => { window.location.hash = "#diagnostics"; }} />
          </div>
        </section>
        <section className="advanced-group" aria-labelledby="advanced-config-heading">
          <div className="advanced-group-heading"><div className="advanced-group-icon"><FolderOpen size={16} aria-hidden="true" /></div><div><h3 id="advanced-config-heading">{fr.settings.advancedConfig}</h3><p>{fr.settings.advancedConfigDescription}</p></div></div>
          <div className="advanced-actions">
            <AdvancedAction icon={<Download size={15} aria-hidden="true" />} title={fr.settings.export} description={fr.settings.advancedDescriptions.export} disabled={pending("export")} onClick={() => void downloadExport()} />
            <AdvancedAction icon={<Upload size={15} aria-hidden="true" />} title={fr.settings.import} description={fr.settings.advancedDescriptions.import} onClick={() => importInput.current?.click()} />
            <AdvancedAction icon={<RotateCcw size={15} aria-hidden="true" />} title={presetAutomationCopy.resetPresets} description={presetAutomationCopy.resetPresetsDescription} tone="danger" disabled={pending("reset-presets")} onClick={() => setConfirmResetPresets(true)} />
            <AdvancedAction icon={<Eraser size={15} aria-hidden="true" />} title={presetAutomationCopy.clearPresets} description={presetAutomationCopy.clearPresetsDescription} tone="danger" disabled={pending("clear-presets")} onClick={() => setConfirmClearPresets(true)} />
            <AdvancedAction icon={<RotateCcw size={15} aria-hidden="true" />} title={fr.settings.reset} description={fr.settings.advancedDescriptions.reset} tone="danger" disabled={pending("reset")} onClick={() => setConfirmReset(true)} />
            <input ref={importInput} id="settings-import" className="sr-only" type="file" accept="application/json,.json" aria-label={fr.settings.import} onChange={(event) => { const file = event.target.files?.[0]; if (file) void importFile(file); event.currentTarget.value = ""; }} />
          </div>
          {errors.export && <small className="inline-error" role="alert">{errors.export}</small>}
          {errors.import && <small className="inline-error" role="alert">{errors.import}</small>}
          {errors["reset-presets"] && <small className="inline-error" role="alert">{errors["reset-presets"]}</small>}
          {errors["clear-presets"] && <small className="inline-error" role="alert">{errors["clear-presets"]}</small>}
        </section>
        <section className="advanced-group" aria-labelledby="advanced-window-heading">
          <div className="advanced-group-heading"><div className="advanced-group-icon"><Maximize2 size={16} aria-hidden="true" /></div><div><h3 id="advanced-window-heading">{fr.settings.advancedWindow}</h3><p>{fr.settings.advancedWindowDescription}</p></div></div>
          <div className="advanced-actions"><AdvancedAction icon={<Maximize2 size={15} aria-hidden="true" />} title={fr.settings.fullscreen} description={fr.settings.advancedDescriptions.fullscreen} onClick={toggleNativeFullscreen} /></div>
        </section>
      </div>}
    </section></div>
    <ConfirmDialog open={confirmReset} title={fr.settings.reset} description={fr.settings.resetDescription} confirmLabel={fr.settings.resetConfirm} onCancel={() => setConfirmReset(false)} onConfirm={() => void reset()} />
    <ConfirmDialog open={confirmCopyAccount} title={fr.account.copyDetected} description={fr.account.copyConfirm} confirmLabel={fr.account.copyDetected} onCancel={() => setConfirmCopyAccount(false)} onConfirm={() => void copyDetectedAccount()} />
    <ConfirmDialog open={confirmForgetAccount} title={fr.account.forgetDetected} description={fr.account.forgetConfirm} confirmLabel={fr.account.forgetDetected} onCancel={() => setConfirmForgetAccount(false)} onConfirm={() => void forgetDetectedAccount()} />
    <ConfirmDialog open={confirmResetPresets} title={presetAutomationCopy.resetPresets} description={presetAutomationCopy.resetPresetsConfirmation} confirmLabel={presetAutomationCopy.resetPresetsConfirm} onCancel={() => setConfirmResetPresets(false)} onConfirm={() => void resetPresets()} />
    <ConfirmDialog open={confirmClearPresets} title={presetAutomationCopy.clearPresets} description={presetAutomationCopy.clearPresetsConfirmation} confirmLabel={presetAutomationCopy.clearPresetsConfirm} onCancel={() => setConfirmClearPresets(false)} onConfirm={() => void clearPresets()} />
  </div>;
}

function AdvancedAction({ icon, title, description, tone, disabled = false, onClick }: { icon: ReactNode; title: string; description: string; tone?: "danger"; disabled?: boolean; onClick: () => void }) {
  return <button className={cn("advanced-action", tone === "danger" && "is-danger")} type="button" disabled={disabled} onClick={onClick}><span className="advanced-action-icon">{icon}</span><span className="advanced-action-copy"><strong>{title}</strong><small>{description}</small></span><ChevronRight size={14} aria-hidden="true" /></button>;
}
