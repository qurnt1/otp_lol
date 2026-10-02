import { expect, readRuntime, setupApplication, test, waitForRuntimeEvents } from "./helpers";

test("diagnostics shows the real disconnected transport and disables LCU checks", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    settings: { close_app_on_lol_exit: false },
  });
  await app.configureLcuConnection({ online: false });
  await expect.poll(async () => (await readRuntime(page)).connected).toBe(false);
  await page.goto("/#diagnostics");

  await expect(page.getByText("League n’est pas connecté. Les tests seront réessayés quand le client sera ouvert.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Tester les endpoints sûrs" })).toBeDisabled();
  await expect(page.locator(".diagnostics-account-card")).toContainText("E2E Player#SAFE");
});

test("Diagnostics stays mounted across League disconnect and reconnect", async ({ page }) => {
  const { app } = await setupApplication(page, { connected: true });
  await page.goto("/#diagnostics");
  const runChecks = page.getByRole("button", { name: "Tester les endpoints sûrs" });
  const offlineNote = page.getByText("League n’est pas connecté. Les tests seront réessayés quand le client sera ouvert.");
  await expect(page.getByRole("heading", { name: "Diagnostics LCU" })).toBeVisible();
  await expect(runChecks).toBeEnabled();
  await expect(offlineNote).toHaveCount(0);

  await app.configureLcuConnection({ online: false });
  await expect.poll(async () => (await readRuntime(page)).connected).toBe(false);
  await expect(offlineNote).toBeVisible();
  await expect(runChecks).toBeDisabled();

  const nextSubscription = app.websocketSubscriptions.length + 1;
  await app.configureLcuConnection({ online: true });
  await app.waitForWebSocketSubscription(nextSubscription);
  await expect.poll(async () => (await readRuntime(page)).connected).toBe(true);
  await expect(offlineNote).toHaveCount(0);
  await expect(runChecks).toBeEnabled();
  await expect(page).toHaveURL(/#diagnostics$/);
});

test("[DIAG-01] a diagnostics read failure can be retried from the visible error state", async ({ page }) => {
  await setupApplication(page, { connected: true });
  await page.clock.install();
  let diagnosticsReads = 0;
  await page.route("**/api/diagnostics", async (route) => {
    const request = route.request();
    if (request.method() === "GET" && new URL(request.url()).pathname === "/api/diagnostics") {
      diagnosticsReads += 1;
      if (diagnosticsReads === 1) {
        await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Injected diagnostics read failure" }) });
        return;
      }
    }
    await route.continue();
  });
  await page.goto("/#diagnostics");

  const readError = page.getByRole("alert");
  await expect(readError).toBeVisible();
  await expect(readError).toContainText("Impossible de charger les diagnostics.");
  const retryButton = page.getByRole("button", { name: "Réessayer" });
  await expect(retryButton).toBeVisible();
  expect(diagnosticsReads).toBe(1);
  await page.clock.pauseAt(new Date(Date.now() + 1_000));
  const recoveredResponse = page.waitForResponse((response) =>
    response.request().method() === "GET" && new URL(response.url()).pathname === "/api/diagnostics" && response.status() === 200,
  );
  await retryButton.click();

  const recovered = await recoveredResponse;
  expect(diagnosticsReads).toBe(2);
  expect((await recovered.json()).runtime.connected).toBe(true);
  await page.clock.fastForward(0);
  await expect(readError).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Diagnostics LCU" })).toBeVisible();
  await expect(page.locator(".diagnostics-account-card")).toContainText("E2E Player#SAFE");
});

test("diagnostics is hidden from permanent navigation and reachable from advanced settings", async ({ page }) => {
  await setupApplication(page, { connected: true });
  await page.goto("/#settings/advanced");

  await expect(page.getByRole("button", { name: "Diagnostics LCU" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Navigation principale" }).getByRole("link", { name: "Diagnostics LCU" })).toHaveCount(0);
  await page.getByRole("button", { name: "Diagnostics LCU" }).click();

  await expect(page).toHaveURL(/#diagnostics$/);
  await expect(page.getByRole("heading", { name: "Diagnostics LCU" })).toBeVisible();
  await expect(page.getByText("Cache disponible")).toBeVisible();
  await expect(page.locator("#diagnostics-account-heading")).toHaveText("E2E Player#SAFE");
  await expect(page.locator(".diagnostics-test-list").getByText("GET /lol-gameflow/v1/gameflow-phase", { exact: true })).toBeVisible();
});

test("diagnostics exécute les contrôles LCU fixes et exporte l’identité uniquement après opt-in", async ({ page }) => {
  const exportRequests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname === "/api/diagnostics/export") exportRequests.push(url.searchParams.get("include_riot_id") ?? "missing");
  });
  await setupApplication(page, { connected: true });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#diagnostics");
  await eventsConnected;

  await page.getByRole("button", { name: "Tester les endpoints sûrs" }).click();
  const gamePhaseCheck = page.locator(".diagnostics-test-row").filter({ hasText: "GET /lol-gameflow/v1/gameflow-phase" });
  await expect(gamePhaseCheck.locator("small")).toHaveText(/^200 · [\d.]+ ms$/);
  await expect(page.getByText("Game phase")).toBeVisible();
  await page.reload();
  await expect(page.locator(".diagnostics-test-row").filter({ hasText: "GET /lol-gameflow/v1/gameflow-phase" }).locator("small")).toHaveText(/^200 · [\d.]+ ms$/);
  await page.getByRole("searchbox", { name: "Filtrer les journaux" }).fill("gameflow");
  await expect(page.locator(".diagnostics-log-list").getByText("GET /lol-gameflow/v1/gameflow-phase")).toBeVisible();

  const firstDownloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exporter le rapport" }).click();
  const firstDownload = await firstDownloadPromise;
  expect(firstDownload.suggestedFilename()).toBe("otp-lol-diagnostics.json");
  const firstReport = JSON.parse(await (await import("node:fs/promises")).readFile(await firstDownload.path() as string, "utf8"));
  expect(firstReport.riot_id).toBeUndefined();
  expect(firstReport.account_identity.riot_id).toBeNull();
  expect(exportRequests).toEqual(["false"]);

  await page.context().grantPermissions(["clipboard-read", "clipboard-write"], { origin: new URL(page.url()).origin });
  await page.getByRole("button", { name: "Copier le rapport" }).click();
  await expect(page.getByText("Rapport copié dans le presse-papiers.")).toBeVisible();
  const redactedClipboard = JSON.parse(await page.evaluate(() => navigator.clipboard.readText()));
  expect(redactedClipboard.account_identity.riot_id).toBeNull();
  expect(exportRequests).toEqual(["false", "false"]);

  await page.getByRole("checkbox", { name: "Inclure mon Riot ID dans l’export" }).check();
  const optedInPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exporter le rapport" }).click();
  const optedIn = await optedInPromise;
  const optedInReport = JSON.parse(await (await import("node:fs/promises")).readFile(await optedIn.path() as string, "utf8"));
  expect(optedInReport.account_identity.riot_id).toBe("E2E Player#SAFE");
  expect(exportRequests).toEqual(["false", "false", "true"]);

  await page.getByRole("button", { name: "Copier le rapport" }).click();
  await expect(page.getByText("Rapport copié dans le presse-papiers.")).toBeVisible();
  const optedInClipboard = JSON.parse(await page.evaluate(() => navigator.clipboard.readText()));
  expect(optedInClipboard.account_identity.riot_id).toBe("E2E Player#SAFE");
  expect(exportRequests).toEqual(["false", "false", "true", "true"]);
});

test("a denied clipboard write reports the failure without claiming the report was copied", async ({ page }) => {
  await setupApplication(page, { connected: true });
  await page.goto("/#diagnostics");
  await page.context().grantPermissions([], { origin: new URL(page.url()).origin });

  const exportResponse = page.waitForResponse((response) =>
    response.request().method() === "GET" && new URL(response.url()).pathname === "/api/diagnostics/export" && response.status() === 200,
  );
  await page.getByRole("button", { name: "Copier le rapport" }).click();
  expect((await exportResponse).ok()).toBe(true);
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByText("Rapport copié dans le presse-papiers.")).toHaveCount(0);
});

test("[DIAG-06] a failed diagnostics export can be retried as a real redacted download", async ({ page }) => {
  await setupApplication(page, { connected: true });
  await page.goto("/#diagnostics");
  let exportRequests = 0;
  await page.route((url) => url.pathname === "/api/diagnostics/export", async (route) => {
    if (route.request().method() === "GET" && exportRequests++ === 0) {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Injected diagnostics export failure" }) });
      return;
    }
    await route.continue();
  });
  const downloads: string[] = [];
  page.on("download", (download) => downloads.push(download.suggestedFilename()));

  await page.getByRole("button", { name: "Exporter le rapport" }).click();
  await expect(page.getByRole("alert")).toHaveText("Injected diagnostics export failure");
  expect(downloads).toEqual([]);

  const successfulExport = page.waitForResponse((response) =>
    response.request().method() === "GET"
    && new URL(response.url()).pathname === "/api/diagnostics/export"
    && response.status() === 200,
  );
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exporter le rapport" }).click();
  expect((await successfulExport).ok()).toBe(true);
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("otp-lol-diagnostics.json");
  const report = JSON.parse(await (await import("node:fs/promises")).readFile(await download.path() as string, "utf8"));
  expect(report.account_identity.riot_id).toBeNull();
  await expect(page.getByRole("alert")).toHaveCount(0);
  expect(exportRequests).toBe(2);
});

test("le payload d’un événement LCU réel reste dans le tiroir JSON", async ({ page }) => {
  await setupApplication(page, { connected: true, phase: "Lobby" });
  await page.goto("/#diagnostics");

  const phaseLog = page.locator(".diagnostics-log-row")
    .filter({ hasText: "/lol-gameflow/v1/gameflow-phase" })
    .filter({ hasText: "UpdateLobby" })
    .first();
  await expect(phaseLog).toBeVisible();
  await expect(page.locator(".diagnostics-log-row pre")).toHaveCount(0);
  const jsonButton = phaseLog.getByRole("button", { name: "Voir JSON" });
  await jsonButton.click();
  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();
  await expect(drawer.locator("pre")).toContainText('"Lobby"');
  await drawer.getByRole("button", { name: "Fermer" }).click();
  await expect(drawer).toBeHidden();
  await expect(jsonButton).toBeFocused();

  await jsonButton.click();
  await expect(drawer).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();
  await expect(jsonButton).toBeFocused();

  await jsonButton.click();
  await expect(drawer).toBeVisible();
  await page.mouse.click(4, 4);
  await expect(drawer).toBeHidden();
  await expect(jsonButton).toBeFocused();
});

test("Diagnostics classe le rafraîchissement réel des données de jeu dans le filtre Données", async ({ page }) => {
  const { app } = await setupApplication(page, { connected: true });
  await expect.poll(async () => {
    const response = await page.request.get(new URL("/api/diagnostics", app.baseURL).href);
    const data = await response.json();
    return data.events.some((event: { topic: string; event_type: string }) =>
      event.topic === "otp-lol/data/static-data" && event.event_type === "refresh"
    );
  }).toBe(true);
  await page.goto("/#diagnostics");

  await page.getByRole("button", { name: "Données", exact: true }).click();
  const dataEvent = page.locator(".diagnostics-log-row").filter({ hasText: "otp-lol/data/static-data" }).first();
  await expect(dataEvent).toBeVisible();
  const search = page.getByRole("searchbox", { name: "Filtrer les journaux" });
  await search.fill("static-data");
  await expect(dataEvent).toBeVisible();
  await search.fill("no matching data event");
  await expect(page.getByText("Aucune entrée pour ce filtre.")).toBeVisible();
  await search.fill("");
  await expect(dataEvent).toBeVisible();
  await dataEvent.getByRole("button", { name: "Voir JSON" }).click();
  await expect(page.getByRole("dialog").locator("pre")).toContainText('"refreshed": false');
});

test("[DIAG-03] log filters combine with text search and clear back to visible entries", async ({ page }) => {
  await setupApplication(page, { connected: true, phase: "Lobby" });
  await page.goto("/#diagnostics");

  const phaseEvent = page.locator(".diagnostics-log-row")
    .filter({ hasText: "/lol-gameflow/v1/gameflow-phase" })
    .filter({ hasText: "Lobby" })
    .first();
  await expect(phaseEvent).toBeVisible();

  const lcuFilter = page.getByRole("button", { name: "LCU", exact: true });
  await lcuFilter.click();
  await expect(lcuFilter).toHaveAttribute("aria-pressed", "true");
  await expect(phaseEvent).toBeVisible();

  const search = page.getByRole("searchbox", { name: "Filtrer les journaux" });
  await search.fill("lobby");
  await expect(phaseEvent).toBeVisible();
  await search.fill("no matching diagnostic entry");
  await expect(page.getByText("Aucune entrée pour ce filtre.")).toBeVisible();

  await search.press("Control+A");
  await search.press("Backspace");
  await expect(phaseEvent).toBeVisible();
  await expect(lcuFilter).toHaveAttribute("aria-pressed", "true");

  const webViewFilter = page.getByRole("button", { name: "WebView", exact: true });
  await webViewFilter.click();
  await expect(webViewFilter).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText("Aucune entrée pour ce filtre.")).toBeVisible();
});

test("[DIAG-03] a failed LCU check is searchable in the Errors filter", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    lcuState: {
      account_responses: {
        "/lol-summoner/v1/current-summoner": { status: 503, payload: { detail: "Synthetic LCU response failure" } },
      },
    },
  });
  await page.goto("/#diagnostics");

  const runResponsePromise = page.waitForResponse((response) =>
    response.request().method() === "POST"
    && new URL(response.url()).pathname === "/api/diagnostics/run"
    && response.status() === 200,
  );
  await page.getByRole("button", { name: "Tester les endpoints sûrs" }).click();
  const runResponse = await runResponsePromise;
  const results = (await runResponse.json()).results;
  expect(results).toContainEqual(expect.objectContaining({
    id: "current_summoner",
    status: 503,
    success: false,
  }));
  expect(results).toContainEqual(expect.objectContaining({ id: "gameflow_phase", status: 200, success: true }));

  const failedRequest = page.locator(".diagnostics-log-row")
    .filter({ hasText: "/lol-summoner/v1/current-summoner" })
    .filter({ hasText: "503" })
    .first();
  const successfulRequest = page.locator(".diagnostics-log-row")
    .filter({ hasText: "/lol-gameflow/v1/gameflow-phase" })
    .filter({ hasText: "200" })
    .first();
  await expect(failedRequest).toBeVisible();
  await expect(successfulRequest).toBeVisible();
  const errorsFilter = page.getByRole("button", { name: "Erreurs", exact: true });
  await errorsFilter.click();
  await expect(errorsFilter).toHaveAttribute("aria-pressed", "true");
  await expect(failedRequest).toBeVisible();
  await expect(successfulRequest).toHaveCount(0);

  const search = page.getByRole("searchbox", { name: "Filtrer les journaux" });
  await search.fill("current-summoner");
  await expect(failedRequest).toBeVisible();
  await search.fill("no matching failed request");
  await expect(page.getByText("Aucune entrée pour ce filtre.")).toBeVisible();
  await search.fill("");
  await expect(failedRequest).toBeVisible();
  const diagnostics = await page.request.get(new URL("/api/diagnostics", app.baseURL).href).then((response) => response.json());
  expect(diagnostics.endpoint_results).toContainEqual(expect.objectContaining({ id: "current_summoner", status: 503, success: false }));
});

test("[DIAG-02] a rejected endpoint check can be retried and its real result survives reload", async ({ page }) => {
  await setupApplication(page, { connected: true });
  let failedRun = false;
  await page.route("**/api/diagnostics/run", async (route) => {
    if (route.request().method() === "POST" && !failedRun) {
      failedRun = true;
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Injected diagnostics check failure" }) });
      return;
    }
    await route.continue();
  });
  await page.goto("/#diagnostics");

  const phaseCheck = page.locator(".diagnostics-test-row").filter({ hasText: "GET /lol-gameflow/v1/gameflow-phase" });
  await expect(phaseCheck.locator("small")).toHaveText("—");
  const runButton = page.getByRole("button", { name: "Tester les endpoints sûrs" });
  await runButton.click();
  await expect(page.getByRole("alert")).toHaveText("Injected diagnostics check failure");
  await expect(phaseCheck.locator("small")).toHaveText("—");

  const successfulRun = page.waitForResponse((response) =>
    response.request().method() === "POST" && new URL(response.url()).pathname === "/api/diagnostics/run" && response.status() === 200,
  );
  await runButton.click();
  const runResponse = await successfulRun;
  const runData = await runResponse.json();
  expect(runData.results).toContainEqual(expect.objectContaining({ path: "/lol-gameflow/v1/gameflow-phase", status: 200, success: true }));
  await expect(phaseCheck.locator(".diagnostics-check")).toHaveText("OK");
  await expect(phaseCheck.locator("small")).toHaveText(/^200 · [\d.]+ ms$/);
  await expect(page.getByRole("alert")).toHaveCount(0);

  const refreshedDiagnostics = page.waitForResponse((response) =>
    response.request().method() === "GET" && new URL(response.url()).pathname === "/api/diagnostics" && response.status() === 200,
  );
  await page.reload();
  const snapshot = await (await refreshedDiagnostics).json();
  expect(snapshot.endpoint_results).toContainEqual(expect.objectContaining({ path: "/lol-gameflow/v1/gameflow-phase", status: 200, success: true }));
  await expect(page.locator(".diagnostics-test-row").filter({ hasText: "GET /lol-gameflow/v1/gameflow-phase" }).locator("small")).toHaveText(/^200 · [\d.]+ ms$/);
});

test("les filtres Diagnostics classent les événements LCU et automatisation reçus du client", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    configured: true,
    autoPick: true,
    phase: "ChampSelect",
    lcuState: {
      static_data_online: true,
      pickable_champion_ids: [86],
      session: {
        gameConfig: { queueId: 420, gameMode: "CLASSIC" },
        localPlayerCellId: 1,
        myTeam: [{ cellId: 1, summonerId: 24680135, assignedPosition: "TOP", championId: 0, spell1Id: 0, spell2Id: 0, selectedRunePageId: 0, selectedSkinId: 0 }],
        actions: [[{ actorCellId: 1, type: "pick", id: 201, isInProgress: true, completed: false }]],
        bans: { myTeamBans: [], theirTeamBans: [] },
      },
    },
  });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#diagnostics");
  await eventsConnected;

  const pick = await app.waitForLcuRequest("PATCH", "/lol-champ-select/v1/session/actions/201");
  expect(pick.body).toMatchObject({ championId: 86 });
  await expect.poll(async () => {
    const state = await app.readLcuState();
    return { completed: state.session.actions[0][0].completed, championId: state.session.actions[0][0].championId };
  }).toEqual({ completed: true, championId: 86 });
  await expect.poll(async () => {
    const response = await page.request.get(new URL("/api/diagnostics", app.baseURL).href);
    const data = await response.json();
    return data.events.some((event: { topic: string }) => event.topic === "otp-lol/champion_picked");
  }).toBe(true);

  await page.getByRole("button", { name: "Actualiser" }).click();
  await page.getByRole("button", { name: "LCU", exact: true }).click();
  const sessionEvent = page.locator(".diagnostics-log-row").filter({ hasText: "/lol-champ-select/v1/session" }).first();
  await expect(sessionEvent).toBeVisible();
  await expect(sessionEvent).toContainText("Update");
  await page.getByRole("button", { name: "Automation", exact: true }).click();
  const championPickedEvent = page.locator(".diagnostics-log-row").filter({ hasText: "otp-lol/champion_picked" }).first();
  await expect(championPickedEvent).toBeVisible();
  const search = page.getByRole("searchbox", { name: "Filtrer les journaux" });
  await search.fill("champion_picked");
  await expect(championPickedEvent).toBeVisible();
  await search.fill("no matching automation event");
  await expect(page.getByText("Aucune entrée pour ce filtre.")).toBeVisible();
  await search.fill("");
  await expect(championPickedEvent).toBeVisible();
  await page.getByRole("button", { name: "WebView", exact: true }).click();
  await expect(page.getByText("Aucune entrée pour ce filtre.")).toBeVisible();
  const diagnostics = await page.request.get(new URL("/api/diagnostics", app.baseURL).href).then((response) => response.json());
  await page.getByRole("button", { name: "Erreurs", exact: true }).click();
  const failedRequests = diagnostics.requests.filter((request: { success: boolean }) => !request.success).length;
  await expect(page.locator(".diagnostics-log-row")).toHaveCount(diagnostics.errors.length + failedRequests);
});
