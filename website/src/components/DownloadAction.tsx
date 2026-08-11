import { useState } from "react";
import type { SiteCopy } from "../content";
import { LATEST_RELEASE_API, LATEST_RELEASE_URL, RELEASES_URL, selectPreferredWindowsAsset, type GitHubReleaseAsset } from "../githubRelease";

type DownloadState = "idle" | "loading" | "fallback";

export function DownloadAction({ copy }: { copy: SiteCopy["download"] }) {
  const [state, setState] = useState<DownloadState>("idle");
  const label = state === "loading" ? copy.loading : state === "fallback" ? copy.fallback : copy.idle;

  async function downloadLatestWindowsBuild() {
    setState("loading");
    try {
      const response = await fetch(LATEST_RELEASE_API, { headers: { Accept: "application/vnd.github+json" } });
      if (!response.ok) throw new Error("GitHub release unavailable");
      const release = (await response.json()) as { assets?: GitHubReleaseAsset[] };
      const windowsAsset = selectPreferredWindowsAsset(release.assets ?? []);
      if (windowsAsset?.browser_download_url) {
        setState("idle");
        window.location.assign(windowsAsset.browser_download_url);
        return;
      }
    } catch { /* The official release page is the safe static-site fallback. */ }
    setState("fallback");
    window.location.assign(LATEST_RELEASE_URL);
  }

  return (
    <div className="download-actions">
      <button className="button button--primary" type="button" data-state={state} disabled={state === "loading"} onClick={downloadLatestWindowsBuild}><span aria-hidden="true">↓</span><span aria-live="polite">{label}</span></button>
      <a className="button button--secondary" href={RELEASES_URL}>{copy.other} <span aria-hidden="true">↗</span></a>
    </div>
  );
}
