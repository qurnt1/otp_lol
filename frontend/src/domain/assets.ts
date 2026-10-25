export function runeAssetUrl(path: string | null | undefined, kind: "perk" | "style"): string | null {
  const value = String(path ?? "").trim();
  if (!value) return null;
  if (value.startsWith("/api/")) return value;
  return `/api/assets/runes/${kind === "style" ? "style" : "perk"}?path=${encodeURIComponent(value)}`;
}

export function safeImageUrl(url: string | null | undefined): string | null {
  const value = String(url ?? "").trim();
  return value.startsWith("/") || value.startsWith("https://") ? value : null;
}
