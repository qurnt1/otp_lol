import { expect, test } from "@playwright/test";

import { mockLocalApi } from "./helpers";

const deeplolProfile = {
  available: true,
  site: "deeplol",
  url: "https://www.deeplol.gg/summoner/euw/Player-EUW",
  homepage_url: "https://www.deeplol.gg/",
  riot_id: "Player#EUW",
  region: "euw",
  account_source: "connected" as const,
};

test("statistics use a top-level provider control without an iframe", async ({ page }) => {
  let statsRequests = 0;
  page.on("request", (request) => {
    if (request.url().endsWith("/api/links/stats")) statsRequests += 1;
  });
  await mockLocalApi(page, { connected: true, statsLink: deeplolProfile });
  await page.goto("/#statistics");

  await expect(page.getByRole("heading", { name: "Statistiques", exact: true })).toBeVisible();
  await expect(page.locator(".statistics-frame")).toHaveCount(0);
  await expect(page.locator(".statistics-fallback")).toContainText("fenêtre WebView2");
  await expect(page.locator(".statistics-fallback").getByRole("button", { name: "Ouvrir dans OTP LOL" })).toBeVisible();

  await page.getByRole("button", { name: "Actualiser" }).click();
  await expect.poll(() => statsRequests).toBeGreaterThanOrEqual(2);
});

test("provider status shows a preloaded window and the control requests it", async ({ page }) => {
  let showCalls = 0;
  const showSources: string[] = [];
  await mockLocalApi(page, { connected: true, statsLink: deeplolProfile });
  await page.route("**/api/desktop/providers/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/status")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ windows: { stats: { state: "hidden", provider_id: "deeplol" }, live: { state: "not_created" } } }) });
      return;
    }
    if (url.pathname.endsWith("/show")) {
      showCalls += 1;
      showSources.push(url.searchParams.get("source") ?? "");
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, kind: "stats", state: "visible", reason: "scheduled" }) });
      return;
    }
    await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "not found" }) });
  });
  await page.goto("/#statistics");

  await expect(page.locator(".statistics-fallback").getByRole("button", { name: "Ouvrir dans OTP LOL" })).toBeVisible();
  await expect.poll(() => showCalls).toBe(1);
  await page.locator(".statistics-fallback").getByRole("button", { name: "Ouvrir dans OTP LOL" }).click();
  await expect.poll(() => showCalls).toBe(2);
  expect(showSources).toEqual(["route_enter", "button"]);
  await expect(page.locator(".statistics-frame")).toHaveCount(0);
});

test("entering live automatically requests the live provider window", async ({ page }) => {
  let openCalls = 0;
  await mockLocalApi(page, { connected: true, liveLink: { ...deeplolProfile, url: "https://www.deeplol.gg/summoner/euw/Player-EUW/ingame" } });
  await page.route("**/api/desktop/providers/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/status")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ windows: { stats: { state: "not_created" }, live: { state: "not_created" } } }) });
      return;
    }
    if (url.pathname.endsWith("/open")) {
      openCalls += 1;
      expect(url.searchParams.get("source")).toBe("route_enter");
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, kind: "live", state: "loading", reason: "scheduled" }) });
      return;
    }
    await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "not found" }) });
  });
  await page.goto("/#live");

  await expect(page.getByRole("heading", { name: "En direct", exact: true })).toBeVisible();
  await expect.poll(() => openCalls).toBe(1);
});

test("does not refocus a provider that is already visible on route entry", async ({ page }) => {
  const actions: string[] = [];
  await mockLocalApi(page, { connected: true, statsLink: deeplolProfile });
  await page.route("**/api/desktop/providers/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/status")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ windows: { stats: { state: "visible", provider_id: "deeplol" }, live: { state: "not_created" } } }) });
      return;
    }
    if (url.pathname.endsWith("/show") || url.pathname.endsWith("/open")) {
      actions.push(url.pathname.endsWith("/show") ? "show" : "open");
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, kind: "stats", state: "visible" }) });
      return;
    }
    await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "not found" }) });
  });
  await page.goto("/#statistics");

  await expect(page.getByRole("heading", { name: "Statistiques", exact: true })).toBeVisible();
  await expect.poll(() => actions).toEqual([]);
});

test("changing the provider opens the new provider without revealing a background navigation", async ({ page }) => {
  const actions: string[] = [];
  await mockLocalApi(page, { connected: true, statsLink: deeplolProfile });
  await page.route("**/api/desktop/providers/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/status")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ windows: { stats: { state: "hidden", provider_id: "deeplol" }, live: { state: "not_created" } } }) });
      return;
    }
    if (url.pathname.endsWith("/show")) {
      actions.push(`show:${url.searchParams.get("source")}`);
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, kind: "stats", state: "visible", reason: "scheduled", provider_id: "deeplol" }) });
      return;
    }
    if (url.pathname.endsWith("/open")) {
      actions.push(`open:${url.searchParams.get("source")}`);
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, kind: "stats", state: "loading", reason: "scheduled", provider_id: "opgg" }) });
      return;
    }
    await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "not found" }) });
  });
  await page.goto("/#statistics");
  await expect(page.locator(".statistics-fallback")).toBeVisible();
  await expect.poll(() => actions).toContain("show:route_enter");

  await page.getByRole("radio", { name: "OP.GG" }).click();
  await expect.poll(() => actions).toContain("open:route_enter");
});

test("stats provider selection persists inline without opening Settings", async ({ page }) => {
  const patches: Array<Record<string, unknown>> = [];
  page.on("request", (request) => {
    if (request.method() === "PATCH" && request.url().endsWith("/api/settings")) patches.push(request.postDataJSON() as Record<string, unknown>);
  });
  await mockLocalApi(page, { connected: true, statsLink: deeplolProfile });
  await page.goto("/#statistics");

  await page.getByRole("radio", { name: "OP.GG" }).click();
  await expect.poll(() => patches).toContainEqual({ preferred_stats_site: "opgg" });
  await expect(page.getByRole("radio", { name: "OP.GG" })).toHaveAttribute("aria-checked", "true");
  await expect(page).not.toHaveURL(/#settings/);
});

test("live provider selection persists inline without opening Settings", async ({ page }) => {
  const patches: Array<Record<string, unknown>> = [];
  page.on("request", (request) => {
    if (request.method() === "PATCH" && request.url().endsWith("/api/settings")) patches.push(request.postDataJSON() as Record<string, unknown>);
  });
  await mockLocalApi(page, { connected: true, liveLink: { ...deeplolProfile, url: "https://www.deeplol.gg/summoner/euw/Player-EUW/ingame" } });
  await page.goto("/#live");

  await page.getByRole("radio", { name: "OP.GG" }).click();
  await expect.poll(() => patches).toContainEqual({ preferred_hotkey_site: "opgg" });
  await expect(page.getByRole("radio", { name: "OP.GG" })).toHaveAttribute("aria-checked", "true");
  await expect(page).not.toHaveURL(/#settings/);
});

test("a rejected provider HTTP action shows an external fallback", async ({ page }) => {
  let attempts = 0;
  await mockLocalApi(page, { connected: true, statsLink: deeplolProfile });
  await page.route("**/api/desktop/providers/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/status")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ windows: { stats: { state: "not_created" }, live: { state: "not_created" } } }) });
      return;
    }
    attempts += 1;
    if (attempts === 1) {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "create_failed" }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, kind: "stats", state: "loading", reason: "scheduled" }) });
  });
  await page.goto("/#statistics");

  await expect(page.getByRole("alert")).toBeVisible();
  await page.locator(".statistics-fallback").getByRole("button", { name: "Ouvrir dans OTP LOL" }).click();
  await expect.poll(() => attempts).toBe(2);
  await expect(page.locator(".statistics-fallback").getByRole("button", { name: "Ouvrir dans le navigateur" })).toBeVisible();
});

for (const provider of [
  { site: "opgg", url: "https://op.gg/fr/lol/summoners/euw/Player-EUW", homepage_url: "https://op.gg/" },
  { site: "deeplol", url: deeplolProfile.url, homepage_url: deeplolProfile.homepage_url },
  { site: "dpm", url: "https://dpm.lol/Player-EUW/", homepage_url: "https://dpm.lol/" },
  { site: "leagueofgraphs", url: "https://www.leagueofgraphs.com/fr/summoner/euw/Player-EUW", homepage_url: "https://www.leagueofgraphs.com/" },
]) {
  test(`${provider.site} is rendered as a native provider control`, async ({ page }) => {
    await mockLocalApi(page, {
      connected: true,
      statsLink: { ...provider, available: true, riot_id: "Player#EUW", region: "euw", account_source: "connected" },
    });
    await page.goto("/#statistics");

    await expect(page.locator(".statistics-frame")).toHaveCount(0);
    await expect(page.locator(".statistics-summary")).toContainText(provider.site === "opgg" ? "OP.GG" : provider.site === "deeplol" ? "DeepLOL" : provider.site === "dpm" ? "DPM.LOL" : "League of Graphs");
    await expect(page.locator(".statistics-fallback").getByRole("button", { name: "Ouvrir dans le navigateur" })).toBeVisible();
  });
}

test("statistics without a usable account links directly to account settings", async ({ page }) => {
  await mockLocalApi(page, { manualRiotId: "", statsLink: { available: false, site: "opgg", url: null, riot_id: null, region: null } });
  await page.goto("/#statistics");

  await expect(page.getByText("Aucun compte exploitable pour le moment.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Configurer le compte" })).toHaveAttribute("href", "#settings/account");
});

test("statistics use the locally saved profile while League is closed", async ({ page }) => {
  const offlineProfile = { ...deeplolProfile, url: "https://www.deeplol.gg/summoner/euw/Saved-EUW", riot_id: "Saved#EUW", account_source: "saved" as const };
  await mockLocalApi(page, {
    autoDetectedRiotId: "Saved#EUW",
    autoDetectedRegion: "euw",
    autoDetectedPlatform: "euw1",
    statsLink: offlineProfile,
  });
  await page.goto("/#statistics");

  await expect(page.locator(".statistics-frame")).toHaveCount(0);
  await expect(page.locator(".statistics-summary")).toContainText("Dernier compte enregistré");
  await expect(page.locator(".statistics-summary")).toContainText("Saved#EUW");
});

test("live statistics use the native provider control and a distinct route", async ({ page }) => {
  let liveRequests = 0;
  page.on("request", (request) => {
    if (request.url().endsWith("/api/links/live")) liveRequests += 1;
  });
  const liveProfile = { ...deeplolProfile, url: "https://www.deeplol.gg/summoner/euw/Player-EUW/ingame" };
  await mockLocalApi(page, { connected: true, liveLink: liveProfile });
  await page.goto("/#live");

  await expect(page.getByRole("heading", { name: "En direct", exact: true })).toBeVisible();
  await expect(page.locator(".statistics-frame")).toHaveCount(0);
  await expect(page.locator(".statistics-fallback").getByRole("button", { name: "Ouvrir dans le navigateur" })).toBeVisible();
  expect(liveRequests).toBe(1);
});

for (const provider of [
  { site: "porofessor", label: "Porofessor", url: "https://porofessor.gg/fr/live/euw/Player-EUW/ranked-only", homepage_url: "https://porofessor.gg/" },
  { site: "deeplol", label: "DeepLOL", url: "https://www.deeplol.gg/summoner/euw/Player-EUW/ingame", homepage_url: "https://www.deeplol.gg/" },
  { site: "dpm", label: "DPM.LOL", url: "https://dpm.lol/Player-EUW/live", homepage_url: "https://dpm.lol/" },
  { site: "opgg", label: "OP.GG", url: "https://op.gg/fr/lol/summoners/euw/Player-EUW/ingame", homepage_url: "https://op.gg/" },
]) {
  test(`${provider.site} live view is rendered as a native provider control`, async ({ page }) => {
    await mockLocalApi(page, {
      connected: true,
      liveLink: { ...provider, available: true, riot_id: "Player#EUW", region: "euw", account_source: "connected" },
    });
    await page.goto("/#live");

    await expect(page.locator(".statistics-frame")).toHaveCount(0);
    await expect(page.locator(".statistics-summary")).toContainText(provider.label);
    await expect(page.locator(".statistics-fallback").getByRole("button", { name: "Ouvrir dans le navigateur" })).toBeVisible();
  });
}
