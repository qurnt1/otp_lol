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

test("le payload d’un événement LCU réel reste dans le tiroir JSON", async ({ page }) => {
  await setupApplication(page, { connected: true, phase: "Lobby" });
  await page.goto("/#diagnostics");

  const phaseLog = page.locator(".diagnostics-log-row")
    .filter({ hasText: "/lol-gameflow/v1/gameflow-phase" })
    .filter({ hasText: "UpdateLobby" })
    .first();
  await expect(phaseLog).toBeVisible();
  await expect(page.locator(".diagnostics-log-row pre")).toHaveCount(0);
  await phaseLog.getByRole("button", { name: "Voir JSON" }).click();
  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();
  await expect(drawer.locator("pre")).toContainText('"Lobby"');
  await drawer.getByRole("button", { name: "Fermer" }).click();
  await expect(drawer).toBeHidden();
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
  await dataEvent.getByRole("button", { name: "Voir JSON" }).click();
  await expect(page.getByRole("dialog").locator("pre")).toContainText('"refreshed": false');
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
  await expect(page.locator(".diagnostics-log-row").filter({ hasText: "otp-lol/champion_picked" }).first()).toBeVisible();
  await page.getByRole("button", { name: "WebView", exact: true }).click();
  await expect(page.getByText("Aucune entrée pour ce filtre.")).toBeVisible();
  const diagnostics = await page.request.get(new URL("/api/diagnostics", app.baseURL).href).then((response) => response.json());
  await page.getByRole("button", { name: "Erreurs", exact: true }).click();
  const failedRequests = diagnostics.requests.filter((request: { success: boolean }) => !request.success).length;
  await expect(page.locator(".diagnostics-log-row")).toHaveCount(diagnostics.errors.length + failedRequests);
});
