import { expect, getOtpApp, readPresets, readSettings, readRuntime, setupApplication, test, waitForRuntimeEvents } from "./helpers";

test("settings persists a toggle across a real page reload", async ({ page }) => {
  await setupApplication(page);
  await page.goto("/#settings/general");
  const closeOnExit = page.getByRole("switch", { name: "Fermer lorsque League est réellement fermé" });
  await expect(closeOnExit).toHaveAttribute("aria-checked", "true");
  await closeOnExit.click();
  await expect(closeOnExit).toHaveAttribute("aria-checked", "false");
  await expect.poll(async () => (await readSettings(page)).close_app_on_lol_exit).toBe(false);

  const toggle = page.getByRole("switch", { name: "Masquer à la connexion" });
  await expect(toggle).toHaveAttribute("aria-checked", "true");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  await expect.poll(async () => (await readSettings(page)).auto_hide_on_connect).toBe(false);
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", "true");
  await expect.poll(async () => (await readSettings(page)).auto_hide_on_connect).toBe(true);
  await page.reload();
  await expect(page.getByRole("switch", { name: "Fermer lorsque League est réellement fermé" })).toHaveAttribute("aria-checked", "false");
  await expect(page.getByRole("switch", { name: "Masquer à la connexion" })).toHaveAttribute("aria-checked", "true");
  await expect.poll(async () => (await readSettings(page)).close_app_on_lol_exit).toBe(false);
});

test("an initial bootstrap read failure leaves a retry path and then loads real settings", async ({ page }) => {
  await setupApplication(page, { connected: true, configured: true });
  let releaseFirstRead!: () => void;
  let reportFirstRead!: () => void;
  const firstReadGate = new Promise<void>((resolve) => { releaseFirstRead = resolve; });
  const firstReadStarted = new Promise<void>((resolve) => { reportFirstRead = resolve; });
  let bootstrapReads = 0;
  await page.route("**/api/bootstrap", async (route) => {
    bootstrapReads += 1;
    if (bootstrapReads <= 2) {
      if (bootstrapReads === 1) {
        reportFirstRead();
        await firstReadGate;
      }
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Injected bootstrap read failure" }) });
      return;
    }
    await route.continue();
  });
  await page.goto("/#settings/general");

  await firstReadStarted;
  await expect(page.getByText("Chargement…")).toBeVisible();
  releaseFirstRead();
  await expect(page.getByText("Le serveur local ne répond pas.")).toBeVisible();
  const retry = page.getByRole("button", { name: "Réessayer" });
  await expect(retry).toBeVisible();
  expect(bootstrapReads).toBe(2);
  await page.unroute("**/api/bootstrap");
  const recoveredResponse = page.waitForResponse((response) =>
    response.request().method() === "GET" && new URL(response.url()).pathname === "/api/bootstrap" && response.status() === 200,
  );
  await retry.click();
  expect((await recoveredResponse).ok()).toBe(true);
  await expect(page.getByRole("heading", { name: "Réglages" })).toBeVisible();
  await expect.poll(async () => (await readSettings(page)).theme).toBe("darkly");
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.champion).toBe("Garen");
});

test("a settings switch cannot submit a second toggle while its first save is pending", async ({ page }) => {
  await setupApplication(page);
  await page.goto("/#settings/general");
  const toggle = page.getByRole("switch", { name: "Masquer à la connexion" });
  let releaseSave!: () => void;
  let reportSaveStarted!: () => void;
  const saveGate = new Promise<void>((resolve) => { releaseSave = resolve; });
  const saveStarted = new Promise<void>((resolve) => { reportSaveStarted = resolve; });
  let patchCount = 0;
  await page.route("**/api/settings", async (route) => {
    if (route.request().method() === "PATCH") {
      patchCount += 1;
      reportSaveStarted();
      await saveGate;
    }
    await route.continue();
  });

  const savedResponse = page.waitForResponse((response) =>
    response.request().method() === "PATCH" && new URL(response.url()).pathname === "/api/settings" && response.status() === 200,
  );
  const toggleBounds = await toggle.boundingBox();
  expect(toggleBounds).not.toBeNull();
  await page.mouse.click(toggleBounds!.x + toggleBounds!.width / 2, toggleBounds!.y + toggleBounds!.height / 2);
  await saveStarted;
  await expect(toggle).toBeDisabled();
  await page.mouse.click(toggleBounds!.x + toggleBounds!.width / 2, toggleBounds!.y + toggleBounds!.height / 2);
  expect(patchCount).toBe(1);
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  releaseSave();
  expect((await savedResponse).ok()).toBe(true);
  await expect.poll(async () => (await readSettings(page)).auto_hide_on_connect).toBe(false);
});

test("a settings transport failure rolls back the toggle and allows a successful retry", async ({ page }) => {
  await setupApplication(page);
  await page.route("**/api/settings", async (route) => {
    if (route.request().method() === "PATCH") {
      await route.abort("failed");
      return;
    }
    await route.continue();
  });
  await page.goto("/#settings/general");

  const closeOnExit = page.getByRole("switch", { name: "Fermer lorsque League est réellement fermé" });
  await expect(closeOnExit).toHaveAttribute("aria-checked", "true");
  await closeOnExit.click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(closeOnExit).toHaveAttribute("aria-checked", "true");
  await expect.poll(async () => (await readSettings(page)).close_app_on_lol_exit).toBe(true);

  await page.unroute("**/api/settings");
  const saved = page.waitForResponse((response) =>
    response.request().method() === "PATCH" && new URL(response.url()).pathname === "/api/settings",
  );
  await closeOnExit.click();
  expect((await saved).status()).toBe(200);
  await expect(closeOnExit).toHaveAttribute("aria-checked", "false");
  await expect.poll(async () => (await readSettings(page)).close_app_on_lol_exit).toBe(false);
});

test("a rejected settings update shows the API detail and preserves the saved value", async ({ page }) => {
  await setupApplication(page);
  await page.route("**/api/settings", async (route) => {
    if (route.request().method() === "PATCH") {
      await route.fulfill({ status: 422, contentType: "text/plain", body: "invalid settings" });
      return;
    }
    await route.continue();
  });
  await page.goto("/#settings/general");

  const closeOnExit = page.getByRole("switch", { name: "Fermer lorsque League est réellement fermé" });
  await closeOnExit.click();

  await expect(page.getByRole("alert")).toHaveText("invalid settings");
  await expect(closeOnExit).toHaveAttribute("aria-checked", "true");
  await expect.poll(async () => (await readSettings(page)).close_app_on_lol_exit).toBe(true);
});

test("custom theme select supports keyboard navigation, Escape and persistence", async ({ page }) => {
  await setupApplication(page);
  await page.goto("/#settings/appearance");

  const theme = page.getByRole("combobox", { name: "Thème" });
  await theme.focus();
  await page.keyboard.press("Enter");
  const light = page.getByRole("option", { name: "Clair" });
  await expect(light).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(light).toBeHidden();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

  await theme.focus();
  await page.keyboard.press("Enter");
  await page.keyboard.press("ArrowDown");
  await expect(light).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect.poll(async () => (await readSettings(page)).theme).toBe("flatly");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});

test("settings advanced actions stay grouped and responsive", async ({ page }) => {
  await page.setViewportSize({ width: 1100, height: 760 });
  await setupApplication(page);
  await page.goto("/#settings/advanced");

  await expect(page.locator(".page-heading .eyebrow")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Avancé", exact: true })).toHaveCount(1);
  await expect(page.getByRole("heading", { name: "Avancé", exact: true })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Avancé" })).toBeVisible();
  await expect(page.locator(".advanced-group")).toHaveCount(3);
  await expect(page.locator(".advanced-action")).toHaveCount(10);
  await expect(page.locator(".settings-section")).toHaveScreenshot("settings-advanced.png", { animations: "disabled" });
  await page.setViewportSize({ width: 800, height: 540 });
  await expect(page.getByRole("region", { name: "Avancé" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("the issue-report action opens its fixed HTTPS destination", async ({ page }) => {
  await setupApplication(page);
  await page.goto("/#settings/advanced");
  const requestedUrls: string[] = [];
  page.context().on("request", (request) => {
    if (request.isNavigationRequest()) requestedUrls.push(request.url());
  });
  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Signaler un problème" }).click();
  const popup = await popupPromise;
  await expect.poll(() => requestedUrls).toContain("https://github.com/qurnt1/otp_lol/issues/new");
  await popup.close();
});

test("automatic account field shows the live LCU Riot ID and preserves the manual fallback", async ({ page }) => {
  await setupApplication(page, { connected: true, manualRiotId: "Saved#Manual" });
  await page.goto("/#settings/account");

  const riotId = page.getByRole("textbox", { name: "Riot ID" });
  const detection = page.getByRole("switch", { name: "Détection automatique du compte" });
  await expect(detection).toHaveAttribute("aria-checked", "true");
  await expect(riotId).toBeDisabled();
  await expect(riotId).toHaveValue("E2E Player#SAFE");

  await detection.click();
  await expect(riotId).toBeEnabled();
  await expect(riotId).toHaveValue("Saved#Manual");
  await detection.click();
  await expect(riotId).toBeDisabled();
  await expect(riotId).toHaveValue("E2E Player#SAFE");
  await expect.poll(async () => (await readSettings(page)).manual_summoner_name).toBe("Saved#Manual");
});

test("manual account mode labels the actual provider identity source", async ({ page }) => {
  await setupApplication(page, { autoDetect: false, manualRiotId: "Manual#EUW", region: "euw" });
  await page.goto("/#settings/account");

  await expect(page.getByText("Compte configuré manuellement")).toBeVisible();
  await expect.poll(async () => (await page.request.get(new URL("/api/account/identity", getOtpApp(page).baseURL).href).then((response) => response.json())).source).toBe("manual");
});

test("account settings keep the live identity when the identity endpoint is unavailable", async ({ page }) => {
  await setupApplication(page, { connected: true });
  await page.route("**/api/account/identity", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Injected identity read failure" }) });
      return;
    }
    await route.continue();
  });
  const failedIdentity = page.waitForResponse((response) =>
    response.request().method() === "GET"
    && new URL(response.url()).pathname === "/api/account/identity"
    && response.status() === 503,
  );
  await page.goto("/#settings/account");
  expect((await failedIdentity).status()).toBe(503);

  await expect(page.getByRole("textbox", { name: "Riot ID" })).toHaveValue("E2E Player#SAFE");
  await expect(page.getByText("Compte League connecté · EUW")).toBeVisible();
  await expect(page.getByRole("switch", { name: "Détection automatique du compte" })).toHaveAttribute("aria-checked", "true");
  expect(await readRuntime(page)).toMatchObject({ connected: true, riot_id: "E2E Player#SAFE", region: "euw" });
});

test("manual Riot ID and region edits persist as the selected provider identity", async ({ page }) => {
  await setupApplication(page, { autoDetect: false, manualRiotId: "Manual#EUW", region: "euw" });
  await page.goto("/#settings/account");

  const riotId = page.getByRole("textbox", { name: "Riot ID" });
  await riotId.fill("Changed Player#TEST");
  await riotId.press("Tab");
  await expect.poll(async () => (await readSettings(page)).manual_summoner_name).toBe("Changed Player#TEST");

  const region = page.getByRole("combobox", { name: "Région" });
  await region.click();
  await page.getByRole("option", { name: "NA", exact: true }).click();
  await expect.poll(async () => (await readSettings(page)).manual_region).toBe("na");
  await expect.poll(async () => (await page.request.get(new URL("/api/account/identity", getOtpApp(page).baseURL).href).then((response) => response.json()))).toMatchObject({
    riot_id: "Changed Player#TEST",
    region: "na",
    source: "manual",
  });
});

test("League close and reconnect update the saved account view through LCU WebSocket", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    manualRiotId: "Manual#NA",
    settings: { close_app_on_lol_exit: false },
  });
  await app.configureLcuConnection({ online: false });
  await expect.poll(async () => (await readRuntime(page)).connected).toBe(false);
  await page.goto("/#settings/account");
  await expect(page.getByText("Dernier compte détecté · EUW · League fermé")).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Riot ID" })).toHaveValue("E2E Player#SAFE");

  await app.configureLcuConnection({ online: true });
  await app.waitForWebSocketSubscription(2);
  await expect.poll(async () => {
    const runtime = await readRuntime(page);
    return { connected: runtime.connected, riot_id: runtime.riot_id, region: runtime.region };
  }).toEqual({ connected: true, riot_id: "E2E Player#SAFE", region: "euw" });
  await expect(page.getByText("Compte League connecté · EUW")).toBeVisible();
});

test("account identity follows a real platform change after LCU reconnect", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    settings: { close_app_on_lol_exit: false },
  });
  const previousChatMeRequests = app.lcuRequests.filter((request) => request.method === "GET" && request.path === "/lol-chat/v1/me").length;
  await app.configureLcuConnection({ online: false });
  await expect.poll(async () => (await readRuntime(page)).connected).toBe(false);
  await app.configureLcuState({ region: "NA", platform: "NA1" });
  const nextSubscription = app.websocketSubscriptions.length + 1;
  await app.configureLcuConnection({ online: true });
  await app.waitForWebSocketSubscription(nextSubscription);
  await expect.poll(() => app.lcuRequests.filter((request) => request.method === "GET" && request.path === "/lol-chat/v1/me").length).toBeGreaterThan(previousChatMeRequests);

  await expect.poll(async () =>
    page.request.get(new URL("/api/account/identity", app.baseURL).href).then((response) => response.json()),
  ).toMatchObject({ riot_id: "E2E Player#SAFE", region: "na", platform_id: "na1", source: "connected" });
  await page.goto("/#settings/account");
  await expect(page.getByText("Compte League connecté · NA")).toBeVisible();
});

test("account copy requires confirmation, and forgetting the saved identity preserves manual values", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    manualRiotId: "Manual#NA",
    settings: { close_app_on_lol_exit: false },
  });
  await app.configureLcuConnection({ online: false });
  await expect.poll(async () => (await readRuntime(page)).connected).toBe(false);
  await page.goto("/#settings/account");

  await page.getByRole("button", { name: "Copier vers les champs manuels" }).click();
  const copyDialog = page.getByRole("alertdialog");
  await expect(copyDialog).toContainText("Remplacer les valeurs manuelles");
  await copyDialog.getByRole("button", { name: "Copier vers les champs manuels" }).click();
  await expect.poll(async () => (await readSettings(page)).manual_summoner_name).toBe("E2E Player#SAFE");

  await page.getByRole("button", { name: "Oublier le dernier compte" }).click();
  const forgetDialog = page.getByRole("alertdialog");
  await expect(forgetDialog).toContainText("Les valeurs manuelles ne seront pas modifiées");
  await forgetDialog.getByRole("button", { name: "Oublier le dernier compte" }).click();
  const saved = await readSettings(page);
  expect(saved.auto_detected_riot_id).toBe("");
  expect(saved.auto_detected_region).toBe("");
  expect(saved.auto_detected_platform).toBe("");
  expect(saved.manual_summoner_name).toBe("E2E Player#SAFE");
  expect(saved.manual_region).toBe("euw");
});

test("[SET-05] account copy cancellation and API failure preserve manual values until retry", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    manualRiotId: "Manual#NA",
    settings: { close_app_on_lol_exit: false, summoner_name_auto_detect: false },
  });
  await app.configureLcuConnection({ online: false });
  await expect.poll(async () => (await readRuntime(page)).connected).toBe(false);
  await page.goto("/#settings/account");

  let copyRequests = 0;
  await page.route("**/api/settings", async (route) => {
    const request = route.request();
    if (request.method() !== "PATCH" || !("manual_summoner_name" in request.postDataJSON())) {
      await route.continue();
      return;
    }
    copyRequests += 1;
    if (copyRequests === 1) {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Injected copy failure" }) });
      return;
    }
    await route.continue();
  });
  const copyButton = page.getByRole("button", { name: "Copier vers les champs manuels" });
  const manualRiotIdInput = page.getByRole("textbox", { name: "Riot ID" });
  await copyButton.click();
  let dialog = page.getByRole("alertdialog");
  await dialog.getByRole("button", { name: "Annuler" }).click();
  await expect(dialog).toBeHidden();
  expect(copyRequests).toBe(0);
  await expect.poll(async () => (await readSettings(page)).manual_summoner_name).toBe("Manual#NA");

  await copyButton.click();
  dialog = page.getByRole("alertdialog");
  await dialog.getByRole("button", { name: "Copier vers les champs manuels" }).click();
  await expect(page.getByRole("alert")).toHaveText("Injected copy failure");
  await expect(manualRiotIdInput).toHaveValue("Manual#NA");
  await expect.poll(async () => (await readSettings(page)).manual_summoner_name).toBe("Manual#NA");

  await copyButton.click();
  dialog = page.getByRole("alertdialog");
  const copySaved = page.waitForResponse((response) =>
    response.request().method() === "PATCH" && new URL(response.url()).pathname === "/api/settings",
  );
  await dialog.getByRole("button", { name: "Copier vers les champs manuels" }).click();
  expect((await copySaved).status()).toBe(200);
  await expect.poll(async () => (await readSettings(page)).manual_summoner_name).toBe("E2E Player#SAFE");
  expect(copyRequests).toBe(2);
});

test("[SET-06] forgetting the saved account can be cancelled and retried without changing manual values", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    manualRiotId: "Manual#NA",
    settings: { close_app_on_lol_exit: false },
  });
  await app.configureLcuConnection({ online: false });
  await expect.poll(async () => (await readRuntime(page)).connected).toBe(false);
  await page.goto("/#settings/account");
  const manualBeforeForget = await readSettings(page);

  let forgetRequests = 0;
  await page.route("**/api/settings/last-detected-account", async (route) => {
    if (route.request().method() !== "DELETE") {
      await route.continue();
      return;
    }
    forgetRequests += 1;
    if (forgetRequests === 1) {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Injected forget failure" }) });
      return;
    }
    await route.continue();
  });
  const forgetButton = page.getByRole("button", { name: "Oublier le dernier compte" });
  await forgetButton.click();
  let dialog = page.getByRole("alertdialog");
  await dialog.getByRole("button", { name: "Annuler" }).click();
  await expect(dialog).toBeHidden();
  expect(forgetRequests).toBe(0);
  await expect.poll(async () => (await readSettings(page))).toMatchObject({
    auto_detected_riot_id: "E2E Player#SAFE",
    manual_summoner_name: manualBeforeForget.manual_summoner_name,
    manual_region: manualBeforeForget.manual_region,
  });

  await forgetButton.click();
  dialog = page.getByRole("alertdialog");
  await dialog.getByRole("button", { name: "Oublier le dernier compte" }).click();
  await expect(page.getByRole("alert")).toHaveText("Injected forget failure");
  await expect.poll(async () => (await readSettings(page))).toMatchObject({
    auto_detected_riot_id: "E2E Player#SAFE",
    manual_summoner_name: manualBeforeForget.manual_summoner_name,
    manual_region: manualBeforeForget.manual_region,
  });

  await forgetButton.click();
  dialog = page.getByRole("alertdialog");
  const forgetSaved = page.waitForResponse((response) =>
    response.request().method() === "DELETE" && new URL(response.url()).pathname === "/api/settings/last-detected-account",
  );
  await dialog.getByRole("button", { name: "Oublier le dernier compte" }).click();
  expect((await forgetSaved).status()).toBe(200);
  await expect.poll(async () => (await readSettings(page))).toMatchObject({
    auto_detected_riot_id: "",
    manual_summoner_name: manualBeforeForget.manual_summoner_name,
    manual_region: manualBeforeForget.manual_region,
  });
  expect(forgetRequests).toBe(2);
});

test("automatic account mode remains empty when League is offline and no identity was saved", async ({ page }) => {
  const { app } = await setupApplication(page, {
    settings: { close_app_on_lol_exit: false },
    clearDetectedAccount: true,
  });
  await app.configureLcuConnection({ online: false });
  await expect.poll(async () => (await readRuntime(page)).connected).toBe(false);
  await page.goto("/#settings/account");

  const riotId = page.getByRole("textbox", { name: "Riot ID" });
  await expect(riotId).toBeDisabled();
  await expect(riotId).toHaveValue("");
  await expect(page.getByText("Aucun dernier compte valide. Ouvre le client League ou saisis un Riot ID manuel.")).toBeVisible();
});

test("capturing a keyboard shortcut persists a valid hotkey", async ({ page }) => {
  await setupApplication(page);
  await page.goto("/#settings/shortcuts");
  const input = page.getByRole("textbox", { name: "Afficher / masquer la fenêtre" });
  const originalShortcut = (await readSettings(page)).hotkey_toggle_window;
  await page.getByRole("button", { name: "Capturer" }).first().click();
  await expect(page.getByText("Appuie sur un raccourci avec une touche modificatrice.")).toBeVisible();
  await page.keyboard.press("K");
  await expect(page.getByRole("alert")).toHaveText("Ajoute au moins une touche modificatrice.");
  await expect.poll(async () => (await readSettings(page)).hotkey_toggle_window).toBe(originalShortcut);
  await page.getByRole("button", { name: "Annuler" }).click();
  await expect(page.getByRole("button", { name: "Capturer" }).first()).toHaveAttribute("aria-pressed", "false");

  await page.getByRole("button", { name: "Capturer" }).first().click();
  await page.keyboard.press("Alt+Shift+K");

  await expect.poll(async () => (await readSettings(page)).hotkey_toggle_window).toBe("alt+shift+k");
  await expect(input).toHaveValue("alt+shift+k");
});

test("capturing a named function key persists the backend-supported shortcut", async ({ page }) => {
  await setupApplication(page);
  await page.goto("/#settings/shortcuts");
  const toggleWindow = page.getByRole("textbox", { name: "Afficher / masquer la fenêtre" });
  await page.getByRole("button", { name: "Capturer" }).first().click();
  await page.keyboard.press("Shift+F8");

  await expect.poll(async () => (await readSettings(page)).hotkey_toggle_window).toBe("shift+f8");
  await expect(toggleWindow).toHaveValue("shift+f8");
  await page.reload();
  await expect(toggleWindow).toHaveValue("shift+f8");
});

test("shortcut validation rejects the same key combination and keeps the saved value", async ({ page }) => {
  await setupApplication(page);
  await page.goto("/#settings/shortcuts");
  const saved = await readSettings(page);
  const openSite = page.getByRole("textbox", { name: "Ouvrir l’onglet En direct" });
  await page.getByRole("button", { name: "Capturer" }).nth(1).click();
  await page.keyboard.press("Alt+C");

  await expect(page.getByRole("alert")).toHaveText("Ce raccourci est déjà utilisé.");
  await expect(openSite).toHaveValue(saved.hotkey_open_site);
  await expect.poll(async () => (await readSettings(page)).hotkey_open_site).toBe(saved.hotkey_open_site);
});

test("import applies a valid theme, export downloads the real persisted settings, and reset restores defaults", async ({ page }) => {
  await setupApplication(page);
  await page.goto("/#settings/advanced");
  await page.getByLabel("Importer une configuration").setInputFiles({
    name: "otp-lol-settings.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({ config_schema_version: 6, theme: "flatly" })),
  });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect.poll(async () => (await readSettings(page)).theme).toBe("flatly");

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: /Exporter la configuration/ }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("otp-lol-settings.json");
  const exportData = JSON.parse(await (await import("node:fs/promises")).readFile(await download.path() as string, "utf8"));
  expect(exportData.theme).toBe("flatly");
  expect(exportData).not.toHaveProperty("auto_detected_riot_id");

  await page.getByRole("button", { name: /Réinitialiser les réglages/ }).click();
  const confirmation = page.getByRole("alertdialog");
  await expect(confirmation).toBeVisible();
  await confirmation.getByRole("button", { name: "Réinitialiser" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  const settings = await readSettings(page);
  expect(settings.theme).toBe("darkly");
  expect(settings.presets_enabled).toBe(false);
  expect(settings.auto_accept_enabled).toBe(false);
  expect(settings.auto_pick_enabled).toBe(false);
  expect(settings.auto_ban_enabled).toBe(false);
});

test("reset restores starter presets and a dismissible first-run message", async ({ page }) => {
  await setupApplication(page);
  const runtimeEvents = waitForRuntimeEvents(page);
  await page.goto("/#settings/advanced");
  const eventSocket = await runtimeEvents;
  await eventSocket.waitForEvent("framereceived");
  await page.getByRole("button", { name: /Réinitialiser les réglages/ }).click();
  const confirmation = page.getByRole("alertdialog");
  await expect(confirmation).toContainText("efface aussi le dernier compte League détecté");
  await confirmation.getByRole("button", { name: "Réinitialiser" }).click();

  const settings = await readSettings(page);
  expect(settings.presets_enabled).toBe(false);
  expect(settings.onboarding_completed).toBe(false);
  expect([settings.selected_pick_1, settings.selected_pick_2, settings.selected_pick_3]).toEqual(["Garen", "Lux", "Ashe"]);
  expect(settings.selected_ban).toBe("Teemo");
  expect(settings.auto_detected_riot_id).toBe("");
  expect(Object.keys(settings.pick_slots).sort()).toEqual(["pick_1", "pick_2", "pick_3"]);
  expect(Object.values(settings.pick_slots).every((slot: any) => slot.skin_mode === "none" && slot.rune_page_id === 0)).toBe(true);

  await page.goto("/#dashboard");
  for (const [index, champion] of ["Garen", "Lux", "Ashe"].entries()) {
    await expect(page.locator(".priority-card").nth(index)).toContainText(champion);
  }
  await expect(page.locator(".ban-panel")).toContainText("Teemo");
  const onboarding = page.getByRole("complementary", { name: "Des exemples sont prêts." });
  await expect(onboarding).toBeVisible();
  await page.getByRole("button", { name: "Masquer le message de bienvenue" }).click();
  await expect(onboarding).toBeHidden();
  await page.reload();
  await expect(onboarding).toBeHidden();
});

test("first-run onboarding closes permanently after a real preset edit", async ({ page }) => {
  await setupApplication(page, { onboardingCompleted: false });
  await page.goto("/#dashboard");
  const onboarding = page.getByRole("complementary", { name: "Des exemples sont prêts." });
  await expect(onboarding).toBeVisible();
  await page.getByRole("link", { name: "Configurer mes priorités" }).click();
  await expect(page).toHaveURL(/#dashboard\/pick_1$/);
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await editor.getByRole("radio", { name: "Fixe" }).click();
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.skin_mode).toBe("fixed");
  await expect.poll(async () => (await readSettings(page)).onboarding_completed).toBe(true);

  await page.goto("/#dashboard");
  await expect(onboarding).toBeHidden();
  await page.reload();
  await expect(onboarding).toBeHidden();
});

test("restoring example presets disables the master while preserving child preferences", async ({ page }) => {
  await setupApplication(page, {
    configured: true,
    settings: {
      presets_enabled: true,
      auto_accept_enabled: true,
      auto_pick_enabled: true,
      auto_ban_enabled: false,
      auto_summoners_enabled: true,
      skin_automation_enabled: true,
      auto_play_again_enabled: true,
      theme: "flatly",
    },
  });
  await page.goto("/#settings/advanced");
  await page.getByRole("button", { name: /Restaurer les presets d'exemple/ }).click();
  const confirmation = page.getByRole("alertdialog");
  await expect(confirmation).toBeVisible();
  await confirmation.getByRole("button").last().click();

  const settings = await readSettings(page);
  expect(settings.presets_enabled).toBe(false);
  expect(settings.auto_accept_enabled).toBe(true);
  expect(settings.auto_pick_enabled).toBe(true);
  expect(settings.auto_ban_enabled).toBe(false);
  expect(settings.auto_summoners_enabled).toBe(true);
  expect(settings.skin_automation_enabled).toBe(true);
  expect(settings.auto_play_again_enabled).toBe(true);
  expect(settings.theme).toBe("flatly");
  expect(settings.onboarding_completed).toBe(false);
  expect([settings.selected_pick_1, settings.selected_pick_2, settings.selected_pick_3]).toEqual(["Garen", "Lux", "Ashe"]);
  expect(settings.selected_ban).toBe("Teemo");
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.champion).toBe("Garen");

  await page.goto("/#dashboard");
  await expect(page.getByRole("switch", { name: "Utiliser les presets en sélection" })).toHaveAttribute("aria-checked", "false");
  await expect(page.getByRole("complementary", { name: "Des exemples sont prêts." })).toBeVisible();
});

test("clearing only presets preserves account and automation settings", async ({ page }) => {
  await setupApplication(page, {
    configured: true,
    manualRiotId: "Manual#EUW",
    autoDetect: false,
    settings: {
      presets_enabled: true,
      auto_accept_enabled: true,
      auto_pick_enabled: true,
      auto_ban_enabled: false,
      auto_summoners_enabled: true,
      skin_automation_enabled: true,
      auto_play_again_enabled: true,
      theme: "flatly",
    },
  });
  await page.goto("/#settings/advanced");
  await page.getByRole("button", { name: /Effacer uniquement les presets/ }).click();
  const confirmation = page.getByRole("alertdialog");
  await expect(confirmation).toContainText("Restaurer les presets d'exemple");
  await confirmation.getByRole("button").last().click();

  const settings = await readSettings(page);
  expect(settings.presets_enabled).toBe(true);
  expect(settings.auto_accept_enabled).toBe(true);
  expect(settings.auto_pick_enabled).toBe(true);
  expect(settings.auto_ban_enabled).toBe(false);
  expect(settings.auto_summoners_enabled).toBe(true);
  expect(settings.skin_automation_enabled).toBe(true);
  expect(settings.auto_play_again_enabled).toBe(true);
  expect(settings.theme).toBe("flatly");
  expect(settings.manual_summoner_name).toBe("Manual#EUW");
  expect([settings.selected_pick_1, settings.selected_pick_2, settings.selected_pick_3]).toEqual(["", "", ""]);
  expect(settings.selected_ban).toBe("");
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.champion).toBe("");
});

test("[SET-10] malformed, old, and future settings imports preserve the current settings", async ({ page }) => {
  await setupApplication(page, {
    configured: true,
    autoDetect: false,
    manualRiotId: "Preserved#EUW",
    settings: { auto_accept_enabled: true, theme: "flatly" },
  });
  await page.goto("/#settings/advanced");
  const before = await readSettings(page);
  const preserved = {
    theme: before.theme,
    auto_accept_enabled: before.auto_accept_enabled,
    manual_summoner_name: before.manual_summoner_name,
    selected_pick_1: before.selected_pick_1,
  };
  const importInput = page.getByLabel("Importer une configuration");

  await importInput.setInputFiles({
    name: "otp-lol-settings-malformed.json",
    mimeType: "application/json",
    buffer: Buffer.from("{not valid json"),
  });
  await expect(page.getByRole("alert")).toBeVisible();
  await expect.poll(async () => (await readSettings(page))).toMatchObject(preserved);
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");

  await page.getByLabel("Importer une configuration").setInputFiles({
    name: "otp-lol-settings-old.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({ config_schema_version: 5, theme: "flatly" })),
  });
  await expect(page.getByRole("alert")).toContainText("unsupported settings schema");
  await expect.poll(async () => (await readSettings(page))).toMatchObject(preserved);

  await importInput.setInputFiles({
    name: "otp-lol-settings-future.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({ config_schema_version: 999, theme: "darkly", auto_accept_enabled: false, selected_pick_1: "Teemo" })),
  });
  await expect(page.getByRole("alert")).toContainText("unsupported settings schema");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect.poll(async () => (await readSettings(page))).toMatchObject(preserved);
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect.poll(async () => (await readSettings(page))).toMatchObject(preserved);
});

test("configuration export can be imported again after intervening UI changes", async ({ page }) => {
  await setupApplication(page, { configured: true });
  await page.goto("/#settings/appearance");
  const theme = page.getByRole("combobox", { name: "Thème" });
  await theme.click();
  await page.getByRole("option", { name: "Clair" }).click();
  await expect.poll(async () => (await readSettings(page)).theme).toBe("flatly");

  await page.goto("/#settings/automations");
  const autoAccept = page.getByRole("switch", { name: "Auto-Accept" });
  await autoAccept.click();
  await expect.poll(async () => (await readSettings(page)).auto_accept_enabled).toBe(true);

  await page.goto("/#settings/advanced");
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: /Exporter la configuration/ }).click();
  const download = await downloadPromise;
  const exported = await (await import("node:fs/promises")).readFile(await download.path() as string);

  await page.goto("/#settings/appearance");
  await theme.click();
  await page.getByRole("option", { name: "Sombre" }).click();
  await page.goto("/#settings/automations");
  await autoAccept.click();
  await expect.poll(async () => (await readSettings(page))).toMatchObject({ theme: "darkly", auto_accept_enabled: false });

  await page.goto("/#settings/advanced");
  await page.getByLabel("Importer une configuration").setInputFiles({
    name: download.suggestedFilename(),
    mimeType: "application/json",
    buffer: exported,
  });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect.poll(async () => (await readSettings(page))).toMatchObject({ theme: "flatly", auto_accept_enabled: true });
});

test("canceling reset and preset actions leaves the configured account and picks unchanged", async ({ page }) => {
  await setupApplication(page, {
    configured: true,
    autoDetect: false,
    manualRiotId: "Manual#EUW",
    settings: { presets_enabled: true, auto_accept_enabled: true },
  });
  await page.goto("/#settings/advanced");

  await page.getByRole("button", { name: /Réinitialiser les réglages/ }).click();
  let confirmation = page.getByRole("alertdialog");
  await confirmation.getByRole("button", { name: "Annuler" }).click();
  await expect.poll(async () => (await readSettings(page))).toMatchObject({ manual_summoner_name: "Manual#EUW", presets_enabled: true, selected_pick_1: "Garen" });

  await page.getByRole("button", { name: /Restaurer les presets d'exemple/ }).click();
  confirmation = page.getByRole("alertdialog");
  await page.keyboard.press("Escape");
  await expect(confirmation).toBeHidden();
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.champion).toBe("Garen");

  await page.getByRole("button", { name: /Effacer uniquement les presets/ }).click();
  confirmation = page.getByRole("alertdialog");
  await confirmation.getByRole("button", { name: "Annuler" }).click();
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.champion).toBe("Garen");
  await expect.poll(async () => (await readSettings(page))).toMatchObject({ manual_summoner_name: "Manual#EUW", presets_enabled: true, auto_accept_enabled: true });
});

test("[SET-12] restoring example presets preserves settings on failure and retries through FastAPI", async ({ page }) => {
  await setupApplication(page, {
    configured: true,
    autoDetect: false,
    manualRiotId: "Manual#EUW",
    settings: { presets_enabled: true, auto_accept_enabled: true, theme: "flatly" },
  });
  await page.goto("/#settings/advanced");

  let restoreRequests = 0;
  await page.route("**/api/presets/reset", async (route) => {
    if (route.request().method() === "POST" && restoreRequests++ === 0) {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Injected preset restore failure" }) });
      return;
    }
    await route.continue();
  });
  const beforeRestore = await readSettings(page);
  const presetsBeforeRestore = await readPresets(page);
  await page.getByRole("button", { name: /Restaurer les presets d'exemple/ }).click();
  let dialog = page.getByRole("alertdialog");
  await dialog.getByRole("button").last().click();
  await expect(page.getByRole("alert")).toHaveText("Injected preset restore failure");
  await expect.poll(async () => (await readSettings(page))).toMatchObject({
    manual_summoner_name: beforeRestore.manual_summoner_name,
    presets_enabled: beforeRestore.presets_enabled,
    auto_accept_enabled: beforeRestore.auto_accept_enabled,
  });
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.champion).toBe(presetsBeforeRestore.slots.pick_1.champion);

  await page.getByRole("button", { name: /Restaurer les presets d'exemple/ }).click();
  dialog = page.getByRole("alertdialog");
  const restoreSaved = page.waitForResponse((response) =>
    response.request().method() === "POST" && new URL(response.url()).pathname === "/api/presets/reset",
  );
  await dialog.getByRole("button").last().click();
  expect((await restoreSaved).status()).toBe(200);
  await expect.poll(async () => (await readSettings(page))).toMatchObject({
    manual_summoner_name: "Manual#EUW",
    presets_enabled: false,
    auto_accept_enabled: true,
    selected_pick_1: "Garen",
  });
  await expect(page.getByRole("alert")).toHaveCount(0);
  expect(restoreRequests).toBe(2);
});

test("[SET-12] clearing presets preserves account and automation settings on failure and retry", async ({ page }) => {
  await setupApplication(page, {
    configured: true,
    autoDetect: false,
    manualRiotId: "Manual#EUW",
    settings: { presets_enabled: true, auto_accept_enabled: true, theme: "flatly" },
  });
  await page.goto("/#settings/advanced");

  let clearRequests = 0;
  await page.route("**/api/presets/clear", async (route) => {
    if (route.request().method() === "POST" && clearRequests++ === 0) {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Injected clear failure" }) });
      return;
    }
    await route.continue();
  });
  const beforeClear = await readSettings(page);
  await page.getByRole("button", { name: /Effacer uniquement les presets/ }).click();
  let dialog = page.getByRole("alertdialog");
  await dialog.getByRole("button").last().click();
  await expect(page.getByRole("alert")).toHaveText("Injected clear failure");
  await expect.poll(async () => (await readSettings(page))).toMatchObject({
    manual_summoner_name: beforeClear.manual_summoner_name,
    presets_enabled: beforeClear.presets_enabled,
    auto_accept_enabled: beforeClear.auto_accept_enabled,
    selected_pick_1: beforeClear.selected_pick_1,
  });

  await page.getByRole("button", { name: /Effacer uniquement les presets/ }).click();
  dialog = page.getByRole("alertdialog");
  const clearSaved = page.waitForResponse((response) =>
    response.request().method() === "POST" && new URL(response.url()).pathname === "/api/presets/clear",
  );
  await dialog.getByRole("button").last().click();
  expect((await clearSaved).status()).toBe(200);
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.champion).toBe("");
  await expect.poll(async () => (await readSettings(page))).toMatchObject({
    manual_summoner_name: "Manual#EUW",
    presets_enabled: true,
    auto_accept_enabled: true,
    selected_pick_1: "",
  });
  await expect(page.getByRole("alert")).toHaveCount(0);
  expect(clearRequests).toBe(2);
});

test("[SET-11] full settings reset preserves state on failure and retries through FastAPI", async ({ page }) => {
  await setupApplication(page, {
    configured: true,
    autoDetect: false,
    manualRiotId: "Manual#EUW",
    settings: { presets_enabled: true, auto_accept_enabled: true, theme: "flatly" },
  });
  await page.goto("/#settings/advanced");

  let resetRequests = 0;
  await page.route("**/api/settings/reset", async (route) => {
    if (route.request().method() === "POST" && resetRequests++ === 0) {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Injected reset failure" }) });
      return;
    }
    await route.continue();
  });
  const beforeReset = await readSettings(page);
  await page.getByRole("button", { name: /Réinitialiser les réglages/ }).click();
  let dialog = page.getByRole("alertdialog");
  await dialog.getByRole("button", { name: "Réinitialiser" }).click();
  await expect(page.getByRole("alert")).toHaveText("Injected reset failure");
  await expect.poll(async () => (await readSettings(page))).toMatchObject({
    manual_summoner_name: beforeReset.manual_summoner_name,
    presets_enabled: beforeReset.presets_enabled,
    auto_accept_enabled: beforeReset.auto_accept_enabled,
    selected_pick_1: beforeReset.selected_pick_1,
  });

  await page.getByRole("button", { name: /Réinitialiser les réglages/ }).click();
  dialog = page.getByRole("alertdialog");
  const resetSaved = page.waitForResponse((response) =>
    response.request().method() === "POST" && new URL(response.url()).pathname === "/api/settings/reset",
  );
  await dialog.getByRole("button", { name: "Réinitialiser" }).click();
  expect((await resetSaved).status()).toBe(200);
  await expect.poll(async () => (await readSettings(page))).toMatchObject({
    manual_summoner_name: "",
    presets_enabled: false,
    auto_accept_enabled: false,
    selected_pick_1: "Garen",
  });
  await expect(page.getByRole("alert")).toHaveCount(0);
  expect(resetRequests).toBe(2);
});

test("each automation switch persists its setting through FastAPI", async ({ page }) => {
  await setupApplication(page, {
    configured: true,
    settings: {
      auto_accept_enabled: false,
      auto_pick_enabled: false,
      auto_ban_enabled: false,
      auto_summoners_enabled: false,
      skin_automation_enabled: false,
      auto_play_again_enabled: false,
    },
  });
  await page.goto("/#settings/automations");

  for (const [label, key] of [
    ["Auto-Accept", "auto_accept_enabled"],
    ["Auto-Pick", "auto_pick_enabled"],
    ["Auto-Ban", "auto_ban_enabled"],
    ["Auto-Summs", "auto_summoners_enabled"],
    ["Automatisation des skins", "skin_automation_enabled"],
    ["Auto Play Again", "auto_play_again_enabled"],
  ]) {
    const toggle = page.getByRole("switch", { name: label });
    await expect(toggle).toHaveAttribute("aria-checked", "false");
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-checked", "true");
    await expect.poll(async () => (await readSettings(page))[key]).toBe(true);
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-checked", "false");
    await expect.poll(async () => (await readSettings(page))[key]).toBe(false);
  }
});

test("[SET-03] an automation setting rolls back after a rejected save and persists on retry", async ({ page }) => {
  await setupApplication(page, { configured: true, settings: { presets_enabled: true, auto_pick_enabled: false } });
  await page.goto("/#settings/automations");

  let autoPickPatchCount = 0;
  await page.route("**/api/settings", async (route) => {
    const request = route.request();
    if (request.method() === "PATCH" && request.postDataJSON()?.auto_pick_enabled === true && autoPickPatchCount++ === 0) {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Injected automation settings failure" }) });
      return;
    }
    await route.continue();
  });

  const autoPick = page.getByRole("switch", { name: "Auto-Pick" });
  await expect(autoPick).toBeEnabled();
  await autoPick.click();
  await expect(page.getByRole("alert")).toHaveText("Injected automation settings failure");
  await expect(autoPick).toHaveAttribute("aria-checked", "false");
  await expect.poll(async () => (await readSettings(page)).auto_pick_enabled).toBe(false);

  const savedResponse = page.waitForResponse((response) =>
    response.request().method() === "PATCH"
    && new URL(response.url()).pathname === "/api/settings"
    && response.status() === 200,
  );
  await autoPick.click();
  expect((await savedResponse).ok()).toBe(true);
  await expect(autoPick).toHaveAttribute("aria-checked", "true");
  await expect(page.getByText("Enregistré", { exact: true })).toBeVisible();
  await expect.poll(async () => (await readSettings(page)).auto_pick_enabled).toBe(true);
  await page.reload();
  await expect(page.getByRole("switch", { name: "Auto-Pick" })).toHaveAttribute("aria-checked", "true");
  expect(autoPickPatchCount).toBe(2);
});

test("[SET-04] account identity recovers on a settings change after its read endpoint returns 503", async ({ page }) => {
  await setupApplication(page, { connected: true });
  let identityReads = 0;
  await page.route("**/api/account/identity", async (route) => {
    if (route.request().method() === "GET" && identityReads++ === 0) {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Injected identity read failure" }) });
      return;
    }
    await route.continue();
  });
  const failedIdentity = page.waitForResponse((response) =>
    response.request().method() === "GET"
    && new URL(response.url()).pathname === "/api/account/identity"
    && response.status() === 503,
  );
  await page.goto("/#settings/account");
  expect((await failedIdentity).status()).toBe(503);
  await expect(page.getByRole("textbox", { name: "Riot ID" })).toHaveValue("E2E Player#SAFE");
  await expect(page.getByText("Compte League connecté · EUW")).toBeVisible();

  const detection = page.getByRole("switch", { name: "Détection automatique du compte" });
  const manualIdentity = page.waitForResponse((response) =>
    response.request().method() === "GET"
    && new URL(response.url()).pathname === "/api/account/identity"
    && response.status() === 200,
  );
  await detection.click();
  const manualIdentityResponse = await manualIdentity;
  expect((await manualIdentityResponse.json()).source).toBe("manual");
  await expect(detection).toHaveAttribute("aria-checked", "false");
  await expect(page.getByText("Compte configuré manuellement")).toBeVisible();

  const connectedIdentity = page.waitForResponse((response) =>
    response.request().method() === "GET"
    && new URL(response.url()).pathname === "/api/account/identity"
    && response.status() === 200,
  );
  await detection.click();
  const connectedIdentityResponse = await connectedIdentity;
  expect((await connectedIdentityResponse.json())).toMatchObject({ source: "connected", riot_id: "E2E Player#SAFE", region: "euw" });
  await expect(detection).toHaveAttribute("aria-checked", "true");
  await expect(page.getByRole("textbox", { name: "Riot ID" })).toHaveValue("E2E Player#SAFE");
  expect(await readSettings(page)).toMatchObject({ summoner_name_auto_detect: true });
});

test("[SET-09] a failed configuration export shows recovery feedback and retries as a real download", async ({ page }) => {
  await setupApplication(page, { configured: true, manualRiotId: "Private#EUW" });
  await page.goto("/#settings/advanced");
  let exportRequests = 0;
  await page.route("**/api/settings/export", async (route) => {
    if (route.request().method() === "GET" && exportRequests++ === 0) {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Injected configuration export failure" }) });
      return;
    }
    await route.continue();
  });
  const downloads: string[] = [];
  page.on("download", (download) => downloads.push(download.suggestedFilename()));

  await page.getByRole("button", { name: /Exporter la configuration/ }).click();
  await expect(page.getByRole("alert")).toHaveText("Impossible de télécharger la configuration. Vérifie que l’application répond, puis réessaie.");
  expect(downloads).toEqual([]);

  const successfulExport = page.waitForResponse((response) =>
    response.request().method() === "GET"
    && new URL(response.url()).pathname === "/api/settings/export"
    && response.status() === 200,
  );
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: /Exporter la configuration/ }).click();
  expect((await successfulExport).ok()).toBe(true);
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("otp-lol-settings.json");
  const exported = JSON.parse(await (await import("node:fs/promises")).readFile(await download.path() as string, "utf8"));
  expect(exported).toMatchObject({ config_schema_version: 6, theme: "darkly" });
  expect(exported).not.toHaveProperty("auto_detected_riot_id");
  expect(exported.manual_summoner_name).toBe("Private#EUW");
  expect(exportRequests).toBe(2);
});
