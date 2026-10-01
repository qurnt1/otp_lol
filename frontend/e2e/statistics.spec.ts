import { expect, readSettings, setupApplication, test } from "./helpers";

test("statistics loads the real provider profile without an iframe", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/links/")) requests.push(url.pathname);
  });
  const { app } = await setupApplication(page, { connected: true });
  await page.goto("/#statistics");

  await expect(page.getByRole("heading", { name: "Statistiques", exact: true })).toBeVisible();
  await expect(page.locator(".statistics-frame")).toHaveCount(0);
  await expect(page.locator(".statistics-summary")).toContainText("E2E Player#SAFE");
  await expect(page.locator(".statistics-summary")).toContainText("League connecté");
  await expect.poll(() => requests.filter((path) => path === "/api/links/stats").length).toBe(1);
  const profile = await page.request.get(new URL("/api/links/stats", app.baseURL).href).then((response) => response.json());
  expect(profile).toMatchObject({ available: true, account_source: "connected", riot_id: "E2E Player#SAFE" });
  const providerLabels = await page.getByRole("radiogroup", { name: "Fournisseur" }).getByRole("radio").allTextContents();
  expect(providerLabels.some((label) => label.toLowerCase().replace(/[^a-z]/g, "") === profile.site)).toBe(true);
});

test("live statistics has a distinct route and loads its real account link", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/links/")) requests.push(url.pathname);
  });
  await setupApplication(page, { connected: true });
  await page.goto("/#live");

  await expect(page.getByRole("heading", { name: "En direct", exact: true })).toBeVisible();
  await expect(page.locator(".statistics-frame")).toHaveCount(0);
  await expect(page.locator(".statistics-summary")).toContainText("E2E Player#SAFE");
  await expect.poll(() => requests.filter((path) => path === "/api/links/live").length).toBe(1);
});

test("statistics and live links follow a connected account and region change", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    settings: { close_app_on_lol_exit: false },
  });
  await page.goto("/#statistics");
  await expect(page.locator(".statistics-summary")).toContainText("E2E Player#SAFE");
  await expect(page.locator(".statistics-summary .status-pill")).toHaveText("EUW");

  const nextAccount = {
    gameName: "Second Player",
    gameTag: "NA",
    summonerId: 13579246,
    name: "Second Player",
    puuid: "SECOND_ACCOUNT_PUUID_SENTINEL",
  };
  await app.configureLcuState({
    region: "NA",
    platform: "NA1",
    account_responses: { "/lol-chat/v1/me": { status: 200, payload: nextAccount } },
  });
  await app.emitLcuEvent("/lol-chat/v1/me", nextAccount);

  await expect(page.locator(".statistics-summary")).toContainText("Second Player#NA");
  await expect(page.locator(".statistics-summary .status-pill")).toHaveText("NA");
  const statsLink = await page.request.get(new URL("/api/links/stats", app.baseURL).href).then((response) => response.json());
  expect(statsLink).toMatchObject({
    available: true,
    account_source: "connected",
    riot_id: "Second Player#NA",
    region: "na",
    url: "https://op.gg/fr/lol/summoners/na/Second%20Player-NA",
  });

  await page.goto("/#live");
  await expect(page.locator(".statistics-summary")).toContainText("Second Player#NA");
  await expect(page.locator(".statistics-summary .status-pill")).toHaveText("NA");
  const liveLink = await page.request.get(new URL("/api/links/live", app.baseURL).href).then((response) => response.json());
  expect(liveLink).toMatchObject({
    available: true,
    account_source: "connected",
    riot_id: "Second Player#NA",
    region: "na",
    url: "https://porofessor.gg/fr/live/na/Second%20Player-NA/ranked-only",
  });
});

test("initial statistics and live link failures recover through their real refresh endpoints", async ({ page }) => {
  const { app } = await setupApplication(page, { connected: true });
  const failedLinks = new Set<string>();
  await page.route("**/api/links/*", async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    if (request.method() === "GET" && ["/api/links/stats", "/api/links/live"].includes(pathname) && !failedLinks.has(pathname)) {
      failedLinks.add(pathname);
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Injected profile link failure" }) });
      return;
    }
    await route.continue();
  });

  for (const [route, endpoint, heading] of [
    ["/#statistics", "/api/links/stats", "Statistiques"],
    ["/#live", "/api/links/live", "En direct"],
  ] as const) {
    await page.goto(route);
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
    await expect(page.getByRole("alert")).toBeVisible();
    const refreshedLink = page.waitForResponse((response) =>
      response.request().method() === "GET" && new URL(response.url()).pathname === endpoint && response.status() === 200,
    );
    await page.getByRole("button", { name: "Actualiser" }).click();
    const response = await refreshedLink;
    expect((await response.json()).account_source).toBe("connected");
    await expect(page.getByRole("alert")).toHaveCount(0);
    await expect(page.locator(".statistics-summary")).toContainText("E2E Player#SAFE");
    const persistedLink = await page.request.get(new URL(endpoint, app.baseURL).href).then((result) => result.json());
    expect(persistedLink).toMatchObject({ available: true, account_source: "connected", riot_id: "E2E Player#SAFE" });
  }
});

test("changing the statistics provider persists through FastAPI and rebuilds the profile URL", async ({ page }) => {
  await setupApplication(page, { connected: true });
  await page.goto("/#statistics");

  await page.getByRole("radio", { name: "DeepLOL" }).click();
  await expect(page.getByRole("radio", { name: "DeepLOL" })).toHaveAttribute("aria-checked", "true");
  await expect(page.locator(".statistics-fallback")).toContainText("DeepLOL");
  await expect.poll(async () => (await readSettings(page)).preferred_stats_site).toBe("deeplol");
  await expect(page).not.toHaveURL(/#settings/);
});

test("changing the live provider persists without leaving the live route", async ({ page }) => {
  await setupApplication(page, { connected: true });
  await page.goto("/#live");

  await page.getByRole("radio", { name: "DeepLOL" }).click();
  await expect(page.getByRole("radio", { name: "DeepLOL" })).toHaveAttribute("aria-checked", "true");
  await expect(page.locator(".statistics-fallback")).toContainText("DeepLOL");
  await expect.poll(async () => (await readSettings(page)).preferred_hotkey_site).toBe("deeplol");
  await expect(page).toHaveURL(/#live$/);
});

test("each visible statistics provider choice is saved by FastAPI", async ({ page }) => {
  const { app } = await setupApplication(page, { connected: true });
  await page.goto("/#statistics");
  const expectedHosts: Record<string, string> = {
    opgg: "op.gg",
    deeplol: "www.deeplol.gg",
    dpm: "dpm.lol",
    leagueofgraphs: "www.leagueofgraphs.com",
  };

  const choices = page.getByRole("radiogroup", { name: "Fournisseur" }).getByRole("radio");
  await expect.poll(() => choices.count()).toBeGreaterThan(1);
  const labels = await choices.allTextContents();
  expect(labels.length).toBeGreaterThan(1);
  for (const label of labels.map((value) => value.trim())) {
    const choice = page.getByRole("radio", { name: label });
    await choice.click();
    await expect(choice).toHaveAttribute("aria-checked", "true");
    const settings = await readSettings(page);
    const link = await page.request.get(new URL("/api/links/stats", app.baseURL).href).then((response) => response.json());
    expect(settings.preferred_stats_site).toBe(link.site);
    expect(new URL(link.url).hostname).toBe(expectedHosts[link.site]);
    expect(decodeURIComponent(new URL(link.url).pathname)).toContain("E2E Player-SAFE");
  }
});

test("an injected provider settings 503 keeps the previous provider and allows retry", async ({ page }) => {
  const { app } = await setupApplication(page, { connected: true });
  await page.goto("/#statistics");
  const currentLink = await page.request.get(new URL("/api/links/stats", app.baseURL).href).then((response) => response.json());
  const choices = page.getByRole("radiogroup", { name: "Fournisseur" }).getByRole("radio");
  await expect.poll(() => choices.count()).toBeGreaterThan(1);
  const optionStates = await Promise.all((await choices.all()).map(async (choice) => ({
    label: (await choice.innerText()).trim(),
    selected: await choice.getAttribute("aria-checked"),
  })));
  const targetLabel = optionStates.find((option) => option.selected === "false")?.label;
  expect(targetLabel).toBeTruthy();
  const target = page.getByRole("radio", { name: targetLabel! });

  await page.route("**/api/settings", async (route) => {
    if (route.request().method() === "PATCH") {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Injected provider settings failure" }) });
      return;
    }
    await route.continue();
  });
  await target.click();
  await expect(page.getByRole("alert")).toHaveText("Impossible d’enregistrer ce réglage.");
  await expect(target).toHaveAttribute("aria-checked", "false");
  await expect.poll(async () => (await readSettings(page)).preferred_stats_site).toBe(currentLink.site);
  await expect.poll(async () => (await page.request.get(new URL("/api/links/stats", app.baseURL).href).then((response) => response.json())).site).toBe(currentLink.site);

  await page.unroute("**/api/settings");
  await page.getByRole("radio", { name: targetLabel }).click();
  await expect.poll(async () => (await readSettings(page)).preferred_stats_site).not.toBe(currentLink.site);
});

test("Actualiser refait les liens API de Statistiques et En direct", async ({ page }) => {
  const { app } = await setupApplication(page, { connected: true });
  for (const [route, endpoint, heading] of [
    ["/#statistics", "/api/links/stats", "Statistiques"],
    ["/#live", "/api/links/live", "En direct"],
  ]) {
    await page.goto(route);
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
    const before = await page.request.get(new URL(endpoint, app.baseURL).href).then((response) => response.json());
    const refreshResponse = page.waitForResponse((response) =>
      response.request().method() === "GET" && new URL(response.url()).pathname === endpoint,
    );
    await page.getByRole("button", { name: "Actualiser" }).click();
    expect((await refreshResponse).ok()).toBe(true);
    await expect(page.locator(".statistics-summary")).toContainText("E2E Player#SAFE");
    const refreshed = await page.request.get(new URL(endpoint, app.baseURL).href).then((response) => response.json());
    expect(refreshed).toMatchObject({ site: before.site, riot_id: before.riot_id, region: before.region });
  }
});

test("provider window controls show the actual native-manager limitation and keep browser fallback available", async ({ page }) => {
  const providerStatusResponses: number[] = [];
  page.on("response", (response) => {
    if (new URL(response.url()).pathname === "/api/desktop/providers/status") {
      providerStatusResponses.push(response.status());
    }
  });
  const { app } = await setupApplication(page, { connected: true });
  await page.goto("/#statistics");

  await expect(page.locator(".statistics-fallback").getByRole("button", { name: "Ouvrir dans OTP LOL" })).toBeVisible();
  await expect(page.locator(".statistics-fallback").getByRole("button", { name: "Ouvrir dans le navigateur" })).toBeVisible();
  await expect.poll(() => providerStatusResponses).toContain(503);
  const fallback = page.locator(".statistics-fallback");
  await fallback.getByRole("button", { name: "Ouvrir dans OTP LOL" }).click();
  await expect(page.getByRole("alert")).toHaveText("Impossible d’ouvrir la fenêtre du fournisseur dans OTP LOL.");
  await expect(fallback).toBeVisible();

  const profile = await page.request.get(new URL("/api/links/stats", app.baseURL).href).then((response) => response.json());
  const popupPromise = page.waitForEvent("popup");
  const externalRequest = page.context().waitForEvent("request", (request) => request.url() === profile.url);
  await fallback.getByRole("button", { name: "Ouvrir dans le navigateur" }).click();
  const popup = await popupPromise;
  await expect(await externalRequest).toBeTruthy();
  await popup.close();
});

test("external provider home is used without an account and native shell failure can be retried", async ({ page }) => {
  await page.addInitScript(() => {
    const calls: string[] = [];
    const resolvers: Array<(opened: boolean) => void> = [];
    const current = window as Window & {
      __otpExternalCalls: string[];
      __otpResolveExternalCall: (index: number, opened: boolean) => void;
    };
    Object.defineProperty(current, "__otpDesktopMode", { value: true });
    Object.defineProperty(current, "__otpExternalCalls", { value: calls });
    Object.defineProperty(current, "__otpResolveExternalCall", {
      value: (index: number, opened: boolean) => resolvers[index](opened),
    });
    Object.defineProperty(current, "pywebview", {
      value: {
        api: {
          open_external_url: (url: string) => new Promise<boolean>((resolve) => {
            calls.push(url);
            resolvers.push(resolve);
          }),
        },
      },
    });
  });
  const { app } = await setupApplication(page, { autoDetect: false, manualRiotId: "", clearDetectedAccount: true });
  await page.goto("/#statistics");
  await expect(page.getByText("Aucun compte exploitable pour le moment.")).toBeVisible();
  const link = await page.request.get(new URL("/api/links/stats", app.baseURL).href).then((response) => response.json());
  expect(link).toMatchObject({ available: false, riot_id: null, region: null, homepage_url: "https://op.gg/" });
  const openExternal = page.locator(".statistics-fallback").getByRole("button", { name: "Ouvrir dans le navigateur" });

  await openExternal.click();
  await expect.poll(() => page.evaluate(() => (window as Window & { __otpExternalCalls: string[] }).__otpExternalCalls.length)).toBe(1);
  await page.evaluate(() => (window as Window & { __otpResolveExternalCall: (index: number, opened: boolean) => void }).__otpResolveExternalCall(0, false));
  await expect(page.getByRole("alert")).toHaveText("Impossible d’ouvrir le lien externe.");
  await openExternal.click();
  await expect.poll(() => page.evaluate(() => (window as Window & { __otpExternalCalls: string[] }).__otpExternalCalls.length)).toBe(2);
  await page.evaluate(() => new Promise<void>((resolve) => {
    (window as Window & { __otpResolveExternalCall: (index: number, opened: boolean) => void }).__otpResolveExternalCall(1, true);
    requestAnimationFrame(() => resolve());
  }));
  await expect(page.getByRole("alert")).toHaveCount(0);
  expect(await page.evaluate(() => (window as Window & { __otpExternalCalls: string[] }).__otpExternalCalls)).toEqual([
    link.homepage_url,
    link.homepage_url,
  ]);
});

test("statistics offers account settings when neither a live nor saved identity is available", async ({ page }) => {
  await setupApplication(page, { autoDetect: false, manualRiotId: "", clearDetectedAccount: true });
  await page.goto("/#statistics");

  await expect(page.getByText("Aucun compte exploitable pour le moment.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Configurer le compte" })).toHaveAttribute("href", "#settings/account");
  await page.goto("/#live");
  await expect(page.getByRole("heading", { name: "En direct", exact: true })).toBeVisible();
  await expect(page.getByText("Aucun compte exploitable pour le moment.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Configurer le compte" })).toHaveAttribute("href", "#settings/account");
});

test("statistics uses the persisted account after a real LCU disconnect", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    settings: { close_app_on_lol_exit: false },
  });
  await app.configureLcuConnection({ online: false });
  await expect.poll(async () => (await page.request.get(new URL("/api/runtime", app.baseURL).href).then((response) => response.json())).connected).toBe(false);
  await page.goto("/#statistics");

  await expect(page.locator(".statistics-summary")).toContainText("Dernier compte enregistré");
  await expect(page.locator(".statistics-summary")).toContainText("E2E Player#SAFE");
  await expect(page.locator(".statistics-fallback")).toBeVisible();
});

test("live page explains which information is unavailable when using the saved account offline", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    settings: { close_app_on_lol_exit: false },
  });
  await app.configureLcuConnection({ online: false });
  await expect.poll(async () => (await page.request.get(new URL("/api/runtime", app.baseURL).href).then((response) => response.json())).connected).toBe(false);
  await page.goto("/#live");

  await expect(page.locator(".statistics-note")).toContainText("Les informations de partie en direct seront disponibles lorsque League sera lancé");
  await expect(page.locator(".statistics-summary")).toContainText("E2E Player#SAFE");
});
