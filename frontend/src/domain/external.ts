const allowedExternalHosts = new Set([
  "op.gg",
  "porofessor.gg",
  "www.deeplol.gg",
  "dpm.lol",
  "www.leagueofgraphs.com",
]);

function isSafeExternalUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "https:"
      && allowedExternalHosts.has(url.hostname.toLowerCase())
      && !url.username
      && !url.password
      && (!url.port || url.port === "443");
  } catch {
    return false;
  }
}

export async function openExternalUrl(url: string): Promise<boolean> {
  if (!isSafeExternalUrl(url)) return false;
  const nativeApi = (window as Window & {
    pywebview?: { api?: { open_external_url?: (value: string) => Promise<boolean> } };
  }).pywebview?.api;
  if (nativeApi?.open_external_url) {
    return nativeApi.open_external_url(url);
  }
  window.open(url, "_blank", "noopener,noreferrer");
  return true;
}
