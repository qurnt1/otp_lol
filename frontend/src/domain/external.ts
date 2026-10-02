type NativeDesktopApi = {
  open_external_url?: (value: string) => Promise<boolean>;
  export_diagnostics_report?: (includeRiotId: boolean) => Promise<{ success: boolean; cancelled?: boolean; path?: string; error?: string }>;
  save_diagnostics_report?: (includeRiotId: boolean) => Promise<{ success: boolean; cancelled?: boolean; path?: string; error?: string }>;
  open_local_folder?: (value: string) => Promise<boolean>;
  toggle_fullscreen?: () => Promise<boolean>;
};

type NativeWindow = Window & {
  __otpDesktopMode?: boolean;
  __otpNativeBridgeReady?: boolean;
  pywebview?: { api?: NativeDesktopApi };
};

function isDesktopMode(): boolean {
  if (typeof window === "undefined") return false;
  const current = window as NativeWindow;
  return Boolean(current.__otpDesktopMode || new URLSearchParams(window.location.search).get("desktop") === "1");
}

let bridgeReadyFromEvent = false;
if (typeof window !== "undefined") {
  window.addEventListener("pywebviewready", () => {
    bridgeReadyFromEvent = true;
    (window as Window & { __otpNativeBridgeReady?: boolean }).__otpNativeBridgeReady = true;
  });
}

export function isNativeBridgeReady(): boolean {
  if (typeof window === "undefined") return false;
  const current = window as NativeWindow;
  const desktopMode = isDesktopMode();
  if (!desktopMode && !("pywebview" in window)) return true;
  if (desktopMode) return Boolean(current.__otpNativeBridgeReady || current.pywebview?.api);
  return bridgeReadyFromEvent || Boolean(current.__otpNativeBridgeReady || current.pywebview?.api);
}

export function getNativeDesktopApi(): NativeDesktopApi | undefined {
  if (!isNativeBridgeReady()) return undefined;
  return (window as NativeWindow).pywebview?.api;
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
  if (typeof window !== "undefined" && ("pywebview" in window || isDesktopMode())) return false;
  window.open(url, "_blank", "noopener,noreferrer");
  return true;
}

export async function exportDiagnosticsReport(includeRiotId: boolean): Promise<{ success: boolean; cancelled?: boolean; path?: string; error?: string } | null> {
  try {
    return (await getNativeDesktopApi()?.export_diagnostics_report?.(includeRiotId)) ?? null;
  } catch (error) {
    console.error("[native] export_diagnostics_report failed", error);
    return { success: false, error: "native_export_failed" };
  }
}

export async function openLocalFolder(folder: "logs" | "appdata"): Promise<boolean> {
  try {
    return Boolean(await getNativeDesktopApi()?.open_local_folder?.(folder));
  } catch (error) {
    console.error("[native] open_local_folder failed", error);
    return false;
  }
}

export async function toggleFullscreen(): Promise<boolean> {
  try {
    return Boolean(await getNativeDesktopApi()?.toggle_fullscreen?.());
  } catch (error) {
    console.error("[native] toggle_fullscreen failed", error);
    return false;
  }
}
