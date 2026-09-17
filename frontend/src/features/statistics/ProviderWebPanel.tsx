import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink, RefreshCw, Settings2 } from "lucide-react";

import { api } from "../../api/client";
import { Button } from "../../components/ui/button";
import { fr } from "../../content/fr";
import { openExternalUrl, openProviderWindow } from "../../domain/external";

export function ProviderWebPanel({ kind }: { kind: "stats" | "live" }) {
  const copy = kind === "stats" ? fr.statistics : fr.live;
  const link = useQuery({
    queryKey: [kind === "stats" ? "stats-link" : "live-stats-link"],
    queryFn: kind === "stats" ? api.getStatsLink : api.getLiveLink,
    staleTime: Infinity,
    retry: false,
  });
  const providers = useQuery({ queryKey: ["providers"], queryFn: api.getProviders, staleTime: Infinity });
  const [frameStatus, setFrameStatus] = useState<"waiting" | "blocked" | "unconfirmed">("waiting");
  const [frameNonce, setFrameNonce] = useState(0);
  const [externalFailed, setExternalFailed] = useState(false);
  const [providerWindowFailed, setProviderWindowFailed] = useState(false);
  const providerOptions = kind === "stats" ? providers.data?.stats : providers.data?.live;
  const providerInfo = providerOptions?.find((option) => option.id === link.data?.site);
  const provider = providerInfo?.label ?? link.data?.site ?? "";
  const linkUrl = link.data?.available ? link.data.url : null;
  const iframeUrl = linkUrl && link.data?.embed_allowed ? linkUrl : null;
  const externalUrl = linkUrl ?? link.data?.homepage_url ?? null;
  const iframeKey = iframeUrl ? `${iframeUrl}:${frameNonce}` : null;

  useEffect(() => {
    setFrameStatus("waiting");
    if (!iframeUrl) return;
    const timeout = window.setTimeout(() => {
      setFrameStatus((current) => current === "waiting" ? "unconfirmed" : current);
    }, 12_000);
    return () => window.clearTimeout(timeout);
  }, [iframeKey, iframeUrl]);

  const refresh = async () => {
    setFrameStatus("waiting");
    setFrameNonce((current) => current + 1);
    await link.refetch();
  };

  const openExternal = async () => {
    setExternalFailed(false);
    if (externalUrl && link.data?.homepage_url && !await openExternalUrl(externalUrl, link.data.homepage_url)) setExternalFailed(true);
  };

  const openInApp = async () => {
    setProviderWindowFailed(false);
    if (!link.data?.site || !await openProviderWindow(link.data.site, kind)) setProviderWindowFailed(true);
  };

  return <div className="statistics-page provider-web-page">
    <div className="page-heading">
      <div><h1>{copy.title}</h1><p>{copy.subtitle}</p></div>
      <Button variant="quiet" type="button" onClick={() => void refresh()} disabled={link.isFetching}>
        <RefreshCw size={14} aria-hidden="true" />{copy.refresh}
      </Button>
    </div>

    {link.isPending && <div className="page-loading" role="status">{copy.loading}</div>}
    {link.isError && <div className="state-error" role="alert">{copy.error}</div>}

    {link.data && <>
      <section className="surface statistics-summary" aria-label={copy.title}>
        <div className="statistics-summary-copy">
          <span className="section-label">{copy.provider}</span>
          <strong className="statistics-provider-value">
            {providerInfo && <img src={providerInfo.logo_url} alt="" aria-hidden="true" />}
            {provider}
          </strong>
        </div>
        {link.data.available && link.data.riot_id && <div className="statistics-summary-copy">
          <span className="section-label">{copy.profile}</span>
          <strong>{link.data.riot_id}</strong>
        </div>}
        {link.data.region && <span className="status-pill">{link.data.region.toUpperCase()}</span>}
        <div className="statistics-summary-actions">
          <a className="button button-secondary" href="#settings/links"><Settings2 size={14} aria-hidden="true" />{copy.chooseProvider}</a>
          {externalUrl && <Button variant="quiet" type="button" onClick={() => void openExternal()}><ExternalLink size={14} aria-hidden="true" />{copy.openExternal}</Button>}
        </div>
      </section>

      {externalFailed && <p className="inline-error" role="alert">{copy.externalFailed}</p>}
      {providerWindowFailed && <p className="inline-error" role="alert">{fr.provider.providerWindowFailed}</p>}

      {link.data.available && iframeUrl && <section className="statistics-embed surface" aria-label={provider}>
        <iframe
          key={iframeKey}
          className="statistics-frame"
          src={iframeUrl}
          data-reload-token={frameNonce}
          title={`${provider} · ${link.data.riot_id ?? copy.profile}`}
          sandbox="allow-scripts allow-same-origin allow-forms"
          referrerPolicy="no-referrer"
          loading="lazy"
          onError={() => setFrameStatus("blocked")}
        />
        {frameStatus === "waiting" && <p className="statistics-frame-message" role="status">{copy.frameHint}</p>}
        {frameStatus !== "waiting" && <div className="statistics-runtime-fallback" role="alert">
          <p>{copy.frameFailed}</p>
          {link.data.site && <Button variant="primary" type="button" onClick={() => void openInApp()}>{fr.provider.openInApp}</Button>}
          {externalUrl && <Button variant="quiet" type="button" onClick={() => void openExternal()}><ExternalLink size={14} aria-hidden="true" />{copy.openExternal}</Button>}
        </div>}
      </section>}

      {link.data.available && linkUrl && !link.data.embed_allowed && <section className="surface statistics-fallback" role="status">
        <p>{copy.blocked}</p>
        {link.data.site && <Button variant="primary" type="button" onClick={() => void openInApp()}>{fr.provider.openInApp}</Button>}
        <Button variant="quiet" type="button" onClick={() => void openExternal()}><ExternalLink size={14} aria-hidden="true" />{copy.openExternal}</Button>
      </section>}

      {!link.data.available && <section className="surface statistics-fallback" aria-labelledby={`${kind}-empty-heading`}>
        <h2 id={`${kind}-empty-heading`}>{copy.noProfile}</h2>
        <p>{copy.noAccount}</p>
        <a className="button button-primary" href="#settings/account"><Settings2 size={14} aria-hidden="true" />{copy.configureAccount}</a>
        {externalUrl && <Button variant="quiet" type="button" onClick={() => void openExternal()}><ExternalLink size={14} aria-hidden="true" />{copy.openExternal}</Button>}
      </section>}
    </>}
  </div>;
}
