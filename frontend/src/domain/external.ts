type NativeDesktopApi = {
  open_external_url?: (value: string) => Promise<boolean>;
  open_provider_window?: (providerId: string, kind: "stats" | "live") => Promise<boolean>;
};

function getNativeDesktopApi(): NativeDesktopApi | undefined {
  return (window as Window & { pywebview?: { api?: NativeDesktopApi } }).pywebview?.api;
}

function isSafeExternalUrl(value: string, homepageUrl: string): boolean {
  try {
    const url = new URL(value);
    const homepage = new URL(homepageUrl);
    return url.protocol === "https:"
      && homepage.protocol === "https:"
      && url.origin === homepage.origin
      && !url.username
      && !url.password
      && !homepage.username
      && !homepage.password
      && (!url.port || url.port === "443")
      && (!homepage.port || homepage.port === "443");
  } catch {
    return false;
  }
}

export async function openExternalUrl(url: string, homepageUrl: string): Promise<boolean> {
  if (!isSafeExternalUrl(url, homepageUrl)) return false;
  const nativeApi = getNativeDesktopApi();
  if (nativeApi?.open_external_url) {
    return nativeApi.open_external_url(url);
  }
  window.open(url, "_blank", "noopener,noreferrer");
  return true;
}

export async function openProviderWindow(providerId: string, kind: "stats" | "live"): Promise<boolean> {
  try {
    return Boolean(await getNativeDesktopApi()?.open_provider_window?.(providerId, kind));
  } catch {
    return false;
  }
}
