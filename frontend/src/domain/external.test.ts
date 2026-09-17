import { afterEach, describe, expect, it, vi } from "vitest";

import { openExternalUrl, openProviderWindow } from "./external";

afterEach(() => {
  vi.restoreAllMocks();
  delete (window as Window & { pywebview?: unknown }).pywebview;
});

describe("external provider links", () => {
  it("rejects non-provider and unsafe URLs before opening", async () => {
    const open = vi.spyOn(window, "open").mockReturnValue(null);

    expect(await openExternalUrl("https://example.com/profile", "https://op.gg/")).toBe(false);
    expect(await openExternalUrl("https://op.gg:444/profile", "https://op.gg/")).toBe(false);
    expect(await openExternalUrl("https://user@op.gg/profile", "https://op.gg/")).toBe(false);
    expect(open).not.toHaveBeenCalled();
  });

  it("opens only a known HTTPS provider URL in the browser when no native bridge exists", async () => {
    const open = vi.spyOn(window, "open").mockReturnValue(null);

    expect(await openExternalUrl("https://www.deeplol.gg/summoner/euw/Player-Tag", "https://www.deeplol.gg/")).toBe(true);
    expect(await openExternalUrl("https://porofessor.gg/fr/live/euw/Player-Tag/ranked-only", "https://porofessor.gg/")).toBe(true);
    expect(open).toHaveBeenCalledWith("https://www.deeplol.gg/summoner/euw/Player-Tag", "_blank", "noopener,noreferrer");
    expect(open).toHaveBeenCalledWith("https://porofessor.gg/fr/live/euw/Player-Tag/ranked-only", "_blank", "noopener,noreferrer");
  });

  it("delegates a validated provider URL to the native opener", async () => {
    const openExternal = vi.fn().mockResolvedValue(true);
    Object.defineProperty(window, "pywebview", {
      configurable: true,
      value: { api: { open_external_url: openExternal } },
    });

    expect(await openExternalUrl("https://dpm.lol/Player-Tag/", "https://dpm.lol/")).toBe(true);
    expect(openExternal).toHaveBeenCalledWith("https://dpm.lol/Player-Tag/");
  });

  it("requests an in-app provider window by provider and page kind, never by URL", async () => {
    const openProvider = vi.fn().mockResolvedValue(true);
    Object.defineProperty(window, "pywebview", {
      configurable: true,
      value: { api: { open_provider_window: openProvider } },
    });

    expect(await openProviderWindow("deeplol", "live")).toBe(true);
    expect(openProvider).toHaveBeenCalledWith("deeplol", "live");
  });

  it("returns a failure result when the native provider window rejects", async () => {
    Object.defineProperty(window, "pywebview", {
      configurable: true,
      value: { api: { open_provider_window: vi.fn().mockRejectedValue(new Error("window failed")) } },
    });

    expect(await openProviderWindow("opgg", "stats")).toBe(false);
  });
});
