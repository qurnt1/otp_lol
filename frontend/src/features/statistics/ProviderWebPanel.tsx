import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, RefreshCw, Settings2 } from "lucide-react";

import { ApiError, api } from "../../api/client";
import { Button } from "../../components/ui/button";
import { fr } from "../../content/fr";
import { openExternalUrl } from "../../domain/external";
import { useRuntimeStore } from "../../stores/runtimeStore";

export function ProviderWebPanel({ kind }: { kind: "stats" | "live" }) {
  const copy = kind === "stats" ? fr.statistics : fr.live;
  const settingKey = kind === "stats" ? "preferred_stats_site" : "preferred_hotkey_site";
  const link = useQuery({ queryKey: [kind === "stats" ? "stats-link" : "live-stats-link"], queryFn: kind === "stats" ? api.getStatsLink : api.getLiveLink, staleTime: 0, retry: false });
  const providers = useQuery({ queryKey: ["providers"], queryFn: api.getProviders, staleTime: Infinity });
  const runtime = useRuntimeStore((state) => state.runtime);
  const queryClient = useQueryClient();
  const [externalFailed, setExternalFailed] = useState(false);
  const [providerWindowFailed, setProviderWindowFailed] = useState(false);
  const [providerState, setProviderState] = useState("not_created");
  const [savingProvider, setSavingProvider] = useState(false);
  const visibilityRequestRef = useRef<string | null>(null);
  const providerStatus = useQuery({ queryKey: ["provider-window-status", kind], queryFn: api.getProviderWindowStatus, enabled: Boolean(link.data?.available), staleTime: 0, retry: false });
  const providerOptions = kind === "stats" ? providers.data?.stats : providers.data?.live;
  const providerInfo = providerOptions?.find((option) => option.id === link.data?.site);
  const provider = providerInfo?.label ?? link.data?.site ?? "";
  const linkUrl = link.data?.available ? link.data.url : null;
  const externalUrl = linkUrl ?? link.data?.homepage_url ?? null;

  useEffect(() => {
    setProviderWindowFailed(false);
    setProviderState("not_created");
    visibilityRequestRef.current = null;
  }, [kind]);

  useEffect(() => {
    const state = providerStatus.data?.windows?.[kind]?.state;
    if (state) setProviderState(state);
  }, [kind, providerStatus.data]);

  useEffect(() => {
    const currentLink = link.data;
    const current = providerStatus.data?.windows?.[kind];
    if (!currentLink?.available || !currentLink.url || !current) return;
    const requestKey = `${kind}:${currentLink.site}:${currentLink.url}`;
    if (visibilityRequestRef.current === requestKey) return;
    visibilityRequestRef.current = requestKey;
    if (current.provider_id === currentLink.site && current.state === "visible") {
      setProviderState("visible");
      return;
    }
    setProviderWindowFailed(false);
    const sameProvider = current.provider_id === currentLink.site;
    const request = sameProvider && ["creating", "loading", "ready", "hidden", "visible"].includes(current.state)
      ? api.showProviderWindow(kind, "route_enter")
      : api.openProviderWindow(kind, "route_enter");
    void request.then((result) => {
      setProviderState(result.state ?? (result.ok ? "loading" : "error"));
      if (!result.ok) {
        visibilityRequestRef.current = null;
        setProviderWindowFailed(true);
      }
      return providerStatus.refetch();
    }).catch(() => {
      visibilityRequestRef.current = null;
      setProviderWindowFailed(true);
      setProviderState("error");
    });
  }, [kind, link.data?.available, link.data?.site, link.data?.url, providerStatus.data, providerStatus.refetch]);

  const refresh = async () => {
    setProviderState("loading");
    try {
      const current = (await providerStatus.refetch()).data?.windows?.[kind];
      if (current && !["not_created", "closed", "error"].includes(current.state)) {
        await api.reloadProviderWindow(kind);
      } else {
        await link.refetch();
      }
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 503) setProviderWindowFailed(true);
      await link.refetch();
    }
    await providerStatus.refetch();
  };

  const chooseProvider = async (providerId: string) => {
    if (providerId === link.data?.site || savingProvider) return;
    setSavingProvider(true);
    setProviderWindowFailed(false);
    try {
      await api.patchSettings({ [settingKey]: providerId });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["settings"] }),
        queryClient.invalidateQueries({ queryKey: [kind === "stats" ? "stats-link" : "live-stats-link"] }),
      ]);
    } finally {
      setSavingProvider(false);
    }
  };

  const openExternal = async () => {
    setExternalFailed(false);
    if (externalUrl && link.data?.homepage_url && !await openExternalUrl(externalUrl, link.data.homepage_url)) setExternalFailed(true);
  };

  const openInApp = async () => {
    setProviderWindowFailed(false);
    visibilityRequestRef.current = link.data?.available && link.data.url ? `${kind}:${link.data.site}:${link.data.url}` : null;
    try {
      const current = (await providerStatus.refetch()).data?.windows?.[kind];
      const sameProvider = current?.provider_id === link.data?.site;
      const result = sameProvider && (current?.state === "ready" || current?.state === "hidden" || current?.state === "visible")
        ? await api.showProviderWindow(kind, "button")
        : sameProvider && (current?.state === "loading" || current?.state === "creating")
          ? await api.showProviderWindow(kind, "button")
          : await api.openProviderWindow(kind, "button");
      setProviderState(result.state ?? (result.ok ? "loading" : "error"));
      if (!result.ok) {
        visibilityRequestRef.current = null;
        setProviderWindowFailed(true);
      }
      await providerStatus.refetch();
    } catch (error) {
      visibilityRequestRef.current = null;
      setProviderWindowFailed(true);
      setProviderState(error instanceof ApiError && error.status === 503 ? "not_created" : "error");
    }
  };

  return <div className="statistics-page provider-web-page">
    <div className="page-heading"><div><h1>{copy.title}</h1><p>{copy.subtitle}</p></div><Button variant="quiet" type="button" onClick={() => void refresh()} disabled={link.isFetching || savingProvider}><RefreshCw size={14} aria-hidden="true" />{copy.refresh}</Button></div>
    {link.isPending && <div className="page-loading" role="status">{copy.loading}</div>}
    {link.isError && <div className="state-error" role="alert">{copy.error}</div>}
    {link.data && <>
      {kind === "live" && !runtime?.connected && link.data.account_source === "saved" && <p className="statistics-note" role="status">{fr.live.offlineSavedProfile}</p>}
      <section className="surface statistics-summary" aria-label={copy.title}>
        <div className="statistics-summary-copy"><span className="section-label">{copy.provider}</span><div className="provider-choice-list" role="radiogroup" aria-label={copy.provider}>
          {providerOptions?.map((option) => <button key={option.id} className={`provider-choice ${option.id === link.data?.site ? "is-selected" : ""}`} type="button" role="radio" aria-checked={option.id === link.data?.site} disabled={savingProvider} onClick={() => void chooseProvider(option.id)}><img src={option.logo_url} alt="" aria-hidden="true" />{option.label}</button>)}
        </div></div>
        <div className="statistics-summary-copy"><span className="section-label">{copy.account}</span><strong>{copy.accountSource[link.data.account_source]}</strong></div>
        {link.data.available && link.data.riot_id && <div className="statistics-summary-copy"><span className="section-label">{copy.profile}</span><strong>{link.data.riot_id}</strong></div>}
        {link.data.region && <span className="status-pill">{link.data.region.toUpperCase()}</span>}
      </section>
      {externalFailed && <p className="inline-error" role="alert">{copy.externalFailed}</p>}
      {providerWindowFailed && <p className="inline-error" role="alert">{fr.provider.providerWindowFailed}</p>}
      {link.data.available && linkUrl && <section className="surface statistics-fallback" role="status" aria-labelledby={`${kind}-provider-heading`}><h2 id={`${kind}-provider-heading`}>{provider}</h2><p><strong>{providerState === "loading" || providerState === "creating" ? copy.loadingState : providerState === "error" ? copy.errorState : providerState === "ready" || providerState === "hidden" || providerState === "visible" ? copy.readyState : copy.notCreatedState}</strong> · {copy.nativeHint}</p><Button variant="primary" type="button" onClick={() => void openInApp()}>{copy.openInApp}</Button><Button variant="quiet" type="button" onClick={() => void openExternal()}><ExternalLink size={14} aria-hidden="true" />{copy.openExternal}</Button></section>}
      {!link.data.available && <section className="surface statistics-fallback" aria-labelledby={`${kind}-empty-heading`}><h2 id={`${kind}-empty-heading`}>{copy.noProfile}</h2><p>{copy.noAccount}</p><a className="button button-primary" href="#settings/account"><Settings2 size={14} aria-hidden="true" />{copy.configureAccount}</a>{externalUrl && <Button variant="quiet" type="button" onClick={() => void openExternal()}><ExternalLink size={14} aria-hidden="true" />{copy.openExternal}</Button>}</section>}
    </>}
  </div>;
}
