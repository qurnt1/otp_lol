import { expect, test } from "@playwright/test";

import { mockLocalApi } from "./helpers";

const deeplolProfile = {
  available: true,
  site: "deeplol",
  url: "https://www.deeplol.gg/summoner/euw/Player-EUW",
  homepage_url: "https://www.deeplol.gg/",
  riot_id: "Player#EUW",
  region: "euw",
  embed_allowed: true,
};

test("statistics embeds only the backend profile URL with a bounded sandbox and refresh remounts it", async ({ page }) => {
  let statsRequests = 0;
  page.on("request", (request) => {
    if (request.url().endsWith("/api/links/stats")) statsRequests += 1;
  });
  await mockLocalApi(page, { connected: true, statsLink: deeplolProfile });
  await page.goto("/#statistics");

  const frame = page.locator(".statistics-frame");
  await expect(frame).toHaveAttribute("src", deeplolProfile.url);
  await expect(frame).toHaveAttribute("sandbox", "allow-scripts allow-same-origin allow-forms");
  await expect(frame).toHaveAttribute("referrerpolicy", "no-referrer");
  await expect(frame).not.toHaveAttribute("sandbox", /allow-top-navigation|allow-popups/);
  await expect(page.getByRole("link", { name: "Modifier le site" })).toHaveAttribute("href", "#settings/links");
  const oldFrame = await frame.elementHandle();
  await page.getByRole("button", { name: "Actualiser" }).click();
  await expect(frame).toHaveAttribute("data-reload-token", "1");
  await expect.poll(() => oldFrame?.evaluate((element) => element.isConnected)).toBe(false);
  expect(statsRequests).toBeGreaterThanOrEqual(2);
});

test("statistics shows an explicit external fallback when the embedded frame cannot be confirmed", async ({ page }) => {
  await page.clock.install();
  await mockLocalApi(page, { connected: true, statsLink: deeplolProfile });
  await page.goto("/#statistics");

  const frame = page.locator(".statistics-frame");
  await expect(frame).toBeVisible();
  await page.clock.fastForward(12_000);
  const fallback = page.locator(".statistics-runtime-fallback");
  await expect(fallback).toBeVisible();
  await expect(fallback.getByText(/bloqué|confirmé/i)).toBeVisible();
  await expect(fallback.getByRole("button", { name: "Ouvrir dans le navigateur" })).toBeVisible();
});

for (const provider of [
  { site: "opgg", url: "https://op.gg/fr/lol/summoners/euw/Player-EUW", homepage_url: "https://op.gg/" },
  { site: "dpm", url: "https://dpm.lol/Player-EUW/", homepage_url: "https://dpm.lol/" },
  { site: "leagueofgraphs", url: "https://www.leagueofgraphs.com/fr/summoner/euw/Player-EUW", homepage_url: "https://www.leagueofgraphs.com/" },
]) {
  test(`${provider.site} probe fallback never creates an iframe`, async ({ page }) => {
    await mockLocalApi(page, {
      connected: true,
      statsLink: { ...provider, available: true, riot_id: "Player#EUW", region: "euw", embed_allowed: false },
    });
    await page.goto("/#statistics");

    await expect(page.locator(".statistics-frame")).toHaveCount(0);
    await expect(page.getByText("Ce fournisseur ne permet pas l’affichage intégré.")).toBeVisible();
    await expect(page.locator(".statistics-fallback").getByRole("button", { name: "Ouvrir dans le navigateur" })).toBeVisible();
  });
}

test("statistics without a usable account links directly to account settings", async ({ page }) => {
  await mockLocalApi(page, { manualRiotId: "", statsLink: { available: false, site: "opgg", url: null, riot_id: null, region: null } });
  await page.goto("/#statistics");

  await expect(page.getByText("Aucun compte exploitable pour le moment.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Configurer le compte" })).toHaveAttribute("href", "#settings/account");
});

test("an iframe-incompatible provider offers an in-app window without accepting a frontend URL", async ({ page }) => {
  await mockLocalApi(page, {
    connected: true,
    statsLink: {
      available: true,
      site: "opgg",
      url: "https://op.gg/fr/lol/summoners/euw/Player-EUW",
      homepage_url: "https://op.gg/",
      riot_id: "Player#EUW",
      region: "euw",
      embed_allowed: false,
    },
  });
  await page.addInitScript(() => {
    const current = window as Window & {
      __providerWindowCalls?: Array<[string, "stats" | "live"]>;
      pywebview?: { api?: { open_provider_window?: (provider: string, kind: "stats" | "live") => Promise<boolean> } };
    };
    current.__providerWindowCalls = [];
    current.pywebview = {
      api: {
        open_provider_window: async (provider, kind) => {
          current.__providerWindowCalls?.push([provider, kind]);
          return true;
        },
      },
    };
  });
  await page.goto("/#statistics");

  await page.getByRole("button", { name: "Ouvrir dans OTP LOL" }).click();
  await expect.poll(() => page.evaluate(() => (window as Window & { __providerWindowCalls?: unknown[] }).__providerWindowCalls)).toEqual([["opgg", "stats"]]);
  await expect(page.locator(".statistics-frame")).toHaveCount(0);
  await expect(page.locator(".statistics-fallback").getByRole("button", { name: "Ouvrir dans le navigateur" })).toBeVisible();
});

test("a rejected in-app provider window shows a retryable error", async ({ page }) => {
  await mockLocalApi(page, {
    connected: true,
    statsLink: {
      available: true,
      site: "opgg",
      url: "https://op.gg/fr/lol/summoners/euw/Player-EUW",
      homepage_url: "https://op.gg/",
      riot_id: "Player#EUW",
      region: "euw",
      embed_allowed: false,
    },
  });
  await page.addInitScript(() => {
    const current = window as Window & {
      pywebview?: { api?: { open_provider_window?: () => Promise<boolean> } };
    };
    current.pywebview = { api: { open_provider_window: async () => { throw new Error("window failed"); } } };
  });
  await page.goto("/#statistics");

  await page.getByRole("button", { name: "Ouvrir dans OTP LOL" }).click();
  await expect(page.getByRole("alert")).toContainText("Impossible d’ouvrir la fenêtre du fournisseur dans OTP LOL.");
  await expect(page.locator(".statistics-fallback").getByRole("button", { name: "Ouvrir dans le navigateur" })).toBeVisible();
});

test("live statistics use a distinct route, provider URL and safe external fallback", async ({ page }) => {
  let liveRequests = 0;
  page.on("request", (request) => {
    if (request.url().endsWith("/api/links/live")) liveRequests += 1;
  });
  const liveProfile = {
    available: true,
    site: "dpm",
    url: "https://dpm.lol/Player-EUW/live",
    homepage_url: "https://dpm.lol/",
    riot_id: "Player#EUW",
    region: "euw",
    embed_allowed: false,
  };
  await mockLocalApi(page, { connected: true, liveLink: liveProfile });
  await page.goto("/#dashboard");
  expect(liveRequests).toBe(0);
  await page.getByRole("link", { name: "Ouvrir les statistiques en direct" }).click();

  await expect(page).toHaveURL(/#live$/);
  await expect(page.getByRole("heading", { name: "En direct", exact: true })).toBeVisible();
  await expect(page.locator(".statistics-frame")).toHaveCount(0);
  await expect(page.locator(".statistics-summary")).toContainText("DPM.LOL");
  await expect(page.locator(".statistics-fallback").getByRole("button", { name: "Ouvrir dans le navigateur" })).toBeVisible();
  expect(liveRequests).toBe(1);
});

test("live embeds only a backend-approved provider URL with a bounded sandbox", async ({ page }) => {
  const liveProfile = {
    available: true,
    site: "deeplol",
    url: "https://www.deeplol.gg/summoner/euw/Player-EUW/ingame",
    homepage_url: "https://www.deeplol.gg/",
    riot_id: "Player#EUW",
    region: "euw",
    embed_allowed: true,
  };
  await mockLocalApi(page, { connected: true, liveLink: liveProfile });
  await page.goto("/#live");

  const frame = page.locator(".statistics-frame");
  await expect(frame).toHaveAttribute("src", liveProfile.url);
  await expect(frame).toHaveAttribute("sandbox", "allow-scripts allow-same-origin allow-forms");
  await expect(frame).toHaveAttribute("referrerpolicy", "no-referrer");
  await expect(frame).not.toHaveAttribute("sandbox", /allow-top-navigation|allow-popups/);
});

test("changing a provider invalidates only its own account or live link", async ({ page }) => {
  let statsRequests = 0;
  let liveRequests = 0;
  page.on("request", (request) => {
    if (request.url().endsWith("/api/links/stats")) statsRequests += 1;
    if (request.url().endsWith("/api/links/live")) liveRequests += 1;
  });
  await mockLocalApi(page, { connected: true });
  await page.goto("/#statistics");
  await expect(page.getByRole("heading", { name: "Statistiques" })).toBeVisible();
  await page.getByRole("link", { name: "En direct" }).click();
  await expect(page.getByRole("heading", { name: "En direct", exact: true })).toBeVisible();
  expect(statsRequests).toBe(1);
  expect(liveRequests).toBe(1);

  await page.getByRole("link", { name: "Réglages" }).click();
  await page.getByRole("button", { name: "Liens" }).click();
  const statsProvider = page.getByRole("combobox", { name: "Site de statistiques du compte" });
  await expect(statsProvider.locator("img")).toHaveAttribute("src", "/api/assets/providers/opgg");
  await statsProvider.click();
  await expect(page.getByRole("option", { name: "DeepLOL" }).locator("img")).toHaveAttribute("src", "/api/assets/providers/deeplol");
  await page.getByRole("option", { name: "DeepLOL" }).click();

  await page.getByRole("link", { name: "Statistiques" }).click();
  await expect.poll(() => statsRequests).toBe(2);
  await page.getByRole("link", { name: "En direct" }).click();
  await expect(page.getByRole("heading", { name: "En direct", exact: true })).toBeVisible();
  expect(liveRequests).toBe(1);

  await page.getByRole("link", { name: "Réglages" }).click();
  await page.getByRole("button", { name: "Liens" }).click();
  const liveProvider = page.getByRole("combobox", { name: "Site de statistiques en direct" });
  await liveProvider.click();
  await page.getByRole("option", { name: "DPM.LOL" }).click();
  await page.getByRole("link", { name: "Statistiques" }).click();
  await expect(page.getByRole("heading", { name: "Statistiques" })).toBeVisible();
  expect(statsRequests).toBe(2);
  await page.getByRole("link", { name: "En direct" }).click();
  await expect.poll(() => liveRequests).toBe(2);
});

test("import and reset invalidate both account and live links", async ({ page }) => {
  let statsRequests = 0;
  let liveRequests = 0;
  page.on("request", (request) => {
    if (request.url().endsWith("/api/links/stats")) statsRequests += 1;
    if (request.url().endsWith("/api/links/live")) liveRequests += 1;
  });
  await mockLocalApi(page, { connected: true });
  await page.goto("/#statistics");
  await expect(page.getByRole("heading", { name: "Statistiques", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "En direct" }).click();
  await expect(page.getByRole("heading", { name: "En direct", exact: true })).toBeVisible();

  await page.getByRole("link", { name: "Réglages" }).click();
  await page.getByRole("button", { name: "Avancé" }).click();
  await page.getByLabel("Importer une configuration").setInputFiles({
    name: "otp-lol-current.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({ config_schema_version: 6, preferred_stats_site: "deeplol" })),
  });
  await page.getByRole("link", { name: "Statistiques" }).click();
  await expect.poll(() => statsRequests).toBe(2);
  await page.getByRole("link", { name: "En direct" }).click();
  await expect.poll(() => liveRequests).toBe(2);

  await page.getByRole("link", { name: "Réglages" }).click();
  await page.getByRole("button", { name: "Avancé" }).click();
  await page.getByRole("button", { name: /Réinitialiser les réglages/ }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Réinitialiser" }).click();
  await page.getByRole("link", { name: "Statistiques" }).click();
  await expect.poll(() => statsRequests).toBe(3);
  await page.getByRole("link", { name: "En direct" }).click();
  await expect.poll(() => liveRequests).toBe(3);
});
