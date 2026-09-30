import { expect, readHistory, setupApplication, test, waitForRuntimeEvents } from "./helpers";

test("an initial History read failure can be retried into real persisted events", async ({ page }) => {
  const { app } = await setupApplication(page, { connected: true, autoAccept: true });
  await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", { state: "InProgress", playerResponse: "None" });
  await app.waitForLcuRequest("POST", "/lol-matchmaking/v1/ready-check/accept");
  await expect.poll(async () => (await readHistory(page)).count).toBeGreaterThan(0);

  let historyReads = 0;
  await page.route("**/api/history?*", async (route) => {
    if (route.request().method() === "GET") {
      historyReads += 1;
      if (historyReads <= 2) {
        await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Injected History read failure" }) });
        return;
      }
    }
    await route.continue();
  });
  await page.goto("/#history");

  await expect(page.getByText("Impossible de charger l’historique.")).toBeVisible();
  expect(historyReads).toBe(2);
  await page.unroute("**/api/history?*");
  const recoveredResponse = page.waitForResponse((response) =>
    response.request().method() === "GET" && new URL(response.url()).pathname === "/api/history" && response.status() === 200,
  );
  await page.getByRole("button", { name: "Réessayer" }).click();
  expect((await recoveredResponse).ok()).toBe(true);
  await expect(page.getByText("Match automatically accepted.")).toBeVisible();
  await expect.poll(async () => (await readHistory(page)).count).toBeGreaterThan(0);
});

test("[HIST-01] History filters messages and details from a real automatic summoner-spell event", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    configured: true,
    phase: "ChampSelect",
    settings: { auto_pick_enabled: true, auto_summoners_enabled: true, skin_automation_enabled: false },
    lcuState: {
      static_data_online: true,
      pickable_champion_ids: [86],
      session: {
        gameConfig: { queueId: 420, gameMode: "CLASSIC" },
        localPlayerCellId: 1,
        myTeam: [{ cellId: 1, summonerId: 24680135, assignedPosition: "TOP", championId: 0, spell1Id: 0, spell2Id: 0, selectedRunePageId: 0, selectedSkinId: 0 }],
        actions: [],
        bans: { myTeamBans: [], theirTeamBans: [] },
      },
    },
  });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#history");
  await eventsConnected;
  const session = {
    gameConfig: { queueId: 420, gameMode: "CLASSIC" },
    localPlayerCellId: 1,
    myTeam: [{ cellId: 1, summonerId: 24680135, assignedPosition: "TOP", championId: 0, spell1Id: 0, spell2Id: 0, selectedRunePageId: 0, selectedSkinId: 0 }],
    actions: [[{ actorCellId: 1, type: "pick", id: 701, isInProgress: true, completed: false, championId: 0 }]],
    bans: { myTeamBans: [], theirTeamBans: [] },
  };
  await app.configureLcuState({ session, pickable_champion_ids: [86] });
  await app.emitLcuEvent("/lol-champ-select/v1/session", session);
  await expect.poll(async () => (await readHistory(page)).items.some((item) => item.message === "Automatic summs applied: Flash + Ignite.")).toBe(true);

  await page.getByRole("button", { name: "Sorts", exact: true }).click();
  const summonerEvent = page.locator(".history-table tbody tr").filter({ hasText: "Automatic summs applied: Flash + Ignite." });
  await expect(summonerEvent).toContainText("spell 1: Flash");
  await expect(summonerEvent).toContainText("spell 2: Ignite");
  await expect(summonerEvent).toContainText("role: GLOBAL");
  await expect(page.getByRole("button", { name: "Sorts", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("textbox", { name: "Rechercher dans le journal…" }).fill("Flash");
  await expect(summonerEvent).toBeVisible();
  await page.getByRole("textbox", { name: "Rechercher dans le journal…" }).fill("GLOBAL");
  await expect(summonerEvent).toBeVisible();
  await page.getByRole("textbox", { name: "Rechercher dans le journal…" }).fill("not in this log");
  await expect(page.getByText("Aucun événement pour le moment.")).toBeVisible();
  await expect.poll(async () => (await readHistory(page)).count).toBeGreaterThan(0);
});

test("History category filters separate real champion, spell, skin, rune and ready-check events", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    configured: true,
    autoAccept: true,
    autoPick: true,
    autoSummoners: true,
    skinAutomation: true,
    phase: "ChampSelect",
    lcuState: {
      static_data_online: true,
      pickable_champion_ids: [86],
      session: {
        gameConfig: { queueId: 420, gameMode: "CLASSIC" },
        localPlayerCellId: 1,
        myTeam: [{ cellId: 1, summonerId: 24680135, assignedPosition: "TOP", championId: 0, spell1Id: 0, spell2Id: 0, selectedRunePageId: 0, selectedSkinId: 0 }],
        actions: [],
        bans: { myTeamBans: [], theirTeamBans: [] },
      },
    },
  });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#dashboard");
  await eventsConnected;

  const session = {
    gameConfig: { queueId: 420, gameMode: "CLASSIC" },
    localPlayerCellId: 1,
    myTeam: [{ cellId: 1, summonerId: 24680135, assignedPosition: "TOP", championId: 0, spell1Id: 0, spell2Id: 0, selectedRunePageId: 402, selectedSkinId: 0 }],
    actions: [[{ actorCellId: 1, type: "pick", id: 701, isInProgress: true, completed: false, championId: 0 }]],
    bans: { myTeamBans: [], theirTeamBans: [] },
  };
  await app.configureLcuState({
    session,
    pickable_champion_ids: [86],
    rune_pages: [
      { id: 401, name: "E2E Top", primaryStyleId: 8000, subStyleId: 8100, selectedPerkIds: [8005, 8008, 9101, 8014, 8106, 8120, 5008, 5008, 5011], current: false, isValid: true },
      { id: 402, name: "Current Page", primaryStyleId: 8000, subStyleId: 8100, selectedPerkIds: [8005, 8008, 9101, 8014, 8106, 8120, 5008, 5008, 5011], current: true, isValid: true },
    ],
    current_rune_page: { id: 402, name: "Current Page", current: true, isValid: true },
  });
  await app.emitLcuEvent("/lol-champ-select/v1/session", session);
  await app.waitForLcuRequest("PATCH", "/lol-champ-select/v1/session/actions/701");
  await app.waitForLcuRequest("PATCH", "/lol-champ-select/v1/session/my-selection");
  await app.waitForLcuRequest("PUT", "/lol-perks/v1/pages/401");
  await expect.poll(async () => (await readHistory(page)).items.length).toBeGreaterThanOrEqual(4);

  await app.configureLcuState({ phase: "ReadyCheck" });
  await app.emitLcuEvent("/lol-gameflow/v1/gameflow-phase", "ReadyCheck");
  await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", { state: "InProgress", playerResponse: "None" });
  await app.waitForLcuRequest("POST", "/lol-matchmaking/v1/ready-check/accept");

  await app.configureLcuConnection({ online: false });
  await expect.poll(async () => (await readHistory(page)).items.some((item) => item.type === "connection" && item.action === "disconnected")).toBe(true);
  await page.goto("/#history");
  await expect.poll(async () => {
    const items = (await readHistory(page)).items;
    return [
      "LoL client connection lost, trying to reconnect.",
      "Champion automatically locked in: Garen.",
      "Automatic summs applied: Flash + Ignite.",
      "Skin applied automatically: God-King Garen.",
      'Rune page applied: "E2E Top" (id=401).',
      "Match automatically accepted.",
    ].every((message) => items.some((item) => item.message === message));
  }).toBe(true);
  for (const [label, message] of [
    ["Connexion", "LoL client connection lost, trying to reconnect."],
    ["Sélection des champions", "Champion automatically locked in: Garen."],
    ["Sorts", "Automatic summs applied: Flash + Ignite."],
    ["Skins", "Skin applied automatically: God-King Garen."],
    ["Runes", 'Rune page applied: "E2E Top" (id=401).'],
    ["Ready Check", "Match automatically accepted."],
  ]) {
    await page.getByRole("button", { name: label, exact: true }).click();
    await expect(page.getByRole("button", { name: label, exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByText(message)).toBeVisible();
    await expect(page.locator(".history-table tbody tr")).toHaveCount(1);
  }
  await page.getByRole("button", { name: "Tout", exact: true }).click();
  await expect(page.locator(".history-table tbody tr")).toHaveCount((await readHistory(page)).items.length);
  await page.getByRole("button", { name: "Erreurs", exact: true }).click();
  await expect(page.getByText("Aucun événement pour le moment.")).toBeVisible();
});

test("un ready-check accepté est envoyé au LCU et enregistré dans l’API History", async ({ page }) => {
  const { app } = await setupApplication(page, { connected: true, autoAccept: true });
  await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", { state: "InProgress", playerResponse: "None" });
  expect(await app.waitForLcuRequest("POST", "/lol-matchmaking/v1/ready-check/accept")).toMatchObject({
    method: "POST",
    path: "/lol-matchmaking/v1/ready-check/accept",
  });
  await expect.poll(async () => (await readHistory(page)).items.some((item) => item.message === "Match automatically accepted.")).toBe(true);
});

test("[HIST-02] an already-mounted History page receives an accepted ready check live", async ({ page }) => {
  const { app } = await setupApplication(page, { connected: true, autoAccept: true });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#history");
  await eventsConnected;

  await expect(page.getByText("Aucun événement pour le moment.")).toBeVisible();
  await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", { state: "InProgress", playerResponse: "None" });
  await app.waitForLcuRequest("POST", "/lol-matchmaking/v1/ready-check/accept");
  await expect.poll(async () => (await readHistory(page)).items.some((item) => item.message === "Match automatically accepted.")).toBe(true);

  await expect(page.getByText("Match automatically accepted.")).toBeVisible();
});

test("l’historique chargé peut être effacé après confirmation dans l’application", async ({ page }) => {
  const { app } = await setupApplication(page, { connected: true, autoAccept: true });
  await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", { state: "InProgress", playerResponse: "None" });
  await app.waitForLcuRequest("POST", "/lol-matchmaking/v1/ready-check/accept");
  await expect.poll(async () => (await readHistory(page)).count).toBeGreaterThan(0);

  let nativeDialogOpened = false;
  page.on("dialog", () => { nativeDialogOpened = true; });
  await page.goto("/#history");
  await expect(page.getByText("Match automatically accepted.")).toBeVisible();
  await page.getByRole("button", { name: "Effacer l’historique" }).click();
  await expect(page.getByRole("alertdialog")).toBeVisible();
  expect(nativeDialogOpened).toBe(false);
  await page.getByRole("alertdialog").getByRole("button", { name: "Effacer l’historique" }).click();
  await expect(page.getByText("Aucun événement pour le moment.")).toBeVisible();
  await expect.poll(async () => (await readHistory(page)).count).toBe(0);
});

test("canceling history clear and confirming with Escape preserve existing entries", async ({ page }) => {
  const { app } = await setupApplication(page, { connected: true, autoAccept: true });
  await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", { state: "InProgress", playerResponse: "None" });
  await app.waitForLcuRequest("POST", "/lol-matchmaking/v1/ready-check/accept");
  await expect.poll(async () => (await readHistory(page)).count).toBeGreaterThan(0);
  await page.goto("/#history");

  await page.getByRole("button", { name: "Effacer l’historique" }).click();
  let dialog = page.getByRole("alertdialog");
  await dialog.getByRole("button", { name: "Annuler" }).click();
  await expect(dialog).toBeHidden();
  await expect.poll(async () => (await readHistory(page)).count).toBeGreaterThan(0);

  await page.getByRole("button", { name: "Effacer l’historique" }).click();
  dialog = page.getByRole("alertdialog");
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect.poll(async () => (await readHistory(page)).count).toBeGreaterThan(0);
});

test("History clear failure keeps data, prevents duplicate pending submits, and can be retried", async ({ page }) => {
  const { app } = await setupApplication(page, { connected: true, autoAccept: true });
  await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", { state: "InProgress", playerResponse: "None" });
  await app.waitForLcuRequest("POST", "/lol-matchmaking/v1/ready-check/accept");
  await expect.poll(async () => (await readHistory(page)).count).toBeGreaterThan(0);
  await page.goto("/#history");

  let releaseDelete!: () => void;
  let reportDeleteRequest!: () => void;
  const deleteGate = new Promise<void>((resolve) => { releaseDelete = resolve; });
  const deleteStarted = new Promise<void>((resolve) => { reportDeleteRequest = resolve; });
  let deleteCount = 0;
  await page.route("**/api/history", async (route) => {
    if (route.request().method() !== "DELETE") {
      await route.continue();
      return;
    }
    deleteCount += 1;
    if (deleteCount === 1) {
      reportDeleteRequest();
      await deleteGate;
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Injected E2E failure" }) });
      return;
    }
    await route.continue();
  });

  await page.getByRole("button", { name: "Effacer l’historique" }).click();
  const dialog = page.getByRole("alertdialog");
  const confirm = dialog.getByRole("button", { name: "Effacer l’historique" });
  await confirm.click();
  await deleteStarted;
  await expect(confirm).toBeDisabled();
  expect(deleteCount).toBe(1);
  releaseDelete();
  await expect(dialog.getByRole("alert")).toHaveText("Impossible d’effacer l’historique.");
  await expect.poll(async () => (await readHistory(page)).count).toBeGreaterThan(0);

  await page.unroute("**/api/history");
  await dialog.getByRole("button", { name: "Effacer l’historique" }).click();
  await expect(page.getByText("Aucun événement pour le moment.")).toBeVisible();
  await expect.poll(async () => (await readHistory(page)).count).toBe(0);
});
