export async function openExternalUrl(url: string): Promise<void> {
  const nativeApi = (window as Window & {
    pywebview?: { api?: { open_external_url?: (value: string) => Promise<boolean> } };
  }).pywebview?.api;
  if (nativeApi?.open_external_url) {
    await nativeApi.open_external_url(url);
    return;
  }
  window.open(url, "_blank", "noopener,noreferrer");
}
