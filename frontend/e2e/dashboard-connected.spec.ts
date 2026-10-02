import { expect, readHistory, readPresets, readRuntime, readSettings, setupApplication, test, waitForRuntimeEvents } from "./helpers";

test("dashboard connecté affiche l’identité et la phase LCU sans compte synchronisé dans la barre de phase", async ({ page }) => {
  await setupApplication(page, { connected: true, configured: true, phase: "Lobby" });
  await page.goto("/#dashboard");

  await expect(page.locator(".sidebar-runtime")).toHaveAttribute("aria-label", "Client connecté");
  await expect(page.locator(".sidebar-account")).toContainText("E2E Player#SAFE");
  await expect(page.locator(".phase-strip strong")).toHaveText("Dans le lobby");
  await expect(page.getByRole("heading", { name: "Garen" })).toBeVisible();
  await expect(page.locator(".phase-strip")).not.toContainText("Compte synchronisé");
  await expect(page.locator(".priority-mode-select")).toHaveCount(0);

  await page.locator(".priority-card").first().click();
  await page.locator('.preset-editor-dialog button[aria-label="Fermer"]').click();
  await page.getByRole("link", { name: "Dashboard", exact: true }).click();
  await expect(page.locator(".priority-mode-select")).toHaveCount(0);
});

test("le statut Ready Check provient de l’événement LCU et affiche sa gravité", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    phase: "ReadyCheck",
    autoAccept: true,
  });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#dashboard");
  await eventsConnected;
  const requestOffset = app.lcuRequests.length;
  await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", { state: "InProgress", playerResponse: "None" });
  await app.waitForLcuRequest("POST", "/lol-matchmaking/v1/ready-check/accept");
  await expect.poll(() => app.lcuRequests.slice(requestOffset).some((request) =>
    request.method === "POST" && request.path === "/lol-matchmaking/v1/ready-check/accept" && request.body === null
  )).toBe(true);
  await expect.poll(async () => (await app.readLcuState()).ready_check.playerResponse).toBe("Accepted");

  const status = page.locator(".automation-status");
  await expect(status).toHaveAttribute("class", /is-success/);
  await expect(status).toContainText("Ready-check accepté.");
  await expect(status.locator("time")).toBeVisible();
});

test("[DASH-14] répéter le même événement Ready Check ne répète pas l’acceptation ni son historique", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    autoAccept: true,
    settings: { close_app_on_lol_exit: false },
  });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#dashboard");
  await eventsConnected;
  const requestOffset = app.lcuRequests.length;
  const readyCheck = { state: "InProgress", playerResponse: "None" };

  await app.configureLcuState({ ready_check_accept_paused: true });
  let firstEventId = "";
  try {
    const firstEvent = await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", readyCheck);
    firstEventId = firstEvent.id;
    await app.waitForLcuRequest("POST", "/lol-matchmaking/v1/ready-check/accept");

    const concurrentDuplicate = await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", readyCheck);
    await app.waitForLcuEventCompletion(concurrentDuplicate.id);
    expect(app.lcuRequests.slice(requestOffset).filter((request) =>
      request.method === "POST" && request.path === "/lol-matchmaking/v1/ready-check/accept",
    )).toHaveLength(1);
    expect((await app.readLcuState()).ready_check.playerResponse).toBe("None");
  } finally {
    await app.configureLcuState({ ready_check_accept_paused: false });
  }
  expect(firstEventId).not.toBe("");
  await app.waitForLcuEventCompletion(firstEventId);
  await expect.poll(async () => (await readHistory(page)).items.filter((item) =>
    item.message === "Match automatically accepted.",
  ).length).toBe(1);

  const repeatedEvent = await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", readyCheck);
  await app.waitForLcuEventCompletion(repeatedEvent.id);
  const repeatedEventEffects = {
    acceptRequests: app.lcuRequests.slice(requestOffset).filter((request) =>
      request.method === "POST" && request.path === "/lol-matchmaking/v1/ready-check/accept",
    ).length,
    historyEntries: (await readHistory(page)).items.filter((item) =>
      item.message === "Match automatically accepted.",
    ).length,
  };
  expect(repeatedEventEffects).toEqual({ acceptRequests: 1, historyEntries: 1 });

  const matchmakingEvent = await app.emitLcuEvent("/lol-gameflow/v1/gameflow-phase", "Matchmaking");
  await app.waitForLcuEventCompletion(matchmakingEvent.id);
  const nextCycleEvent = await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", readyCheck);
  await app.waitForLcuEventCompletion(nextCycleEvent.id);
  expect(app.lcuRequests.slice(requestOffset).filter((request) =>
    request.method === "POST" && request.path === "/lol-matchmaking/v1/ready-check/accept",
  )).toHaveLength(2);
  await expect.poll(async () => (await app.readLcuState()).ready_check.playerResponse).toBe("Accepted");
  await expect.poll(async () => (await readHistory(page)).items.filter((item) =>
    item.message === "Match automatically accepted.",
  ).length).toBe(2);

  const reconnectSubscription = app.websocketSubscriptions.length + 1;
  await app.configureLcuConnection({ online: false });
  await expect.poll(async () => (await readRuntime(page)).connected).toBe(false);
  await app.configureLcuConnection({ online: true });
  await app.waitForWebSocketSubscription(reconnectSubscription);
  await expect.poll(async () => (await readRuntime(page)).connected).toBe(true);

  const reconnectedCycleEvent = await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", readyCheck);
  await app.waitForLcuEventCompletion(reconnectedCycleEvent.id);
  expect(app.lcuRequests.slice(requestOffset).filter((request) =>
    request.method === "POST" && request.path === "/lol-matchmaking/v1/ready-check/accept",
  )).toHaveLength(3);
  await expect.poll(async () => (await app.readLcuState()).ready_check.playerResponse).toBe("Accepted");
  await expect.poll(async () => (await readHistory(page)).items.filter((item) =>
    item.message === "Match automatically accepted.",
  ).length).toBe(3);
});

test("l’attente d’un événement LCU échoue si son handler lève une exception", async ({ page }) => {
  const { app } = await setupApplication(page, { connected: true });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#dashboard");
  await eventsConnected;

  const malformedLoginEvent = await app.emitLcuEvent("/lol-login/v1/session", ["private-marker"]);
  let completionError: unknown;
  try {
    await app.waitForLcuEventCompletion(malformedLoginEvent.id);
  } catch (error) {
    completionError = error;
  }

  expect(completionError).toBeInstanceOf(Error);
  expect((completionError as Error).message)
    .toBe(`LCU WebSocket event handler ${malformedLoginEvent.id} failed.`);
  expect((completionError as Error).message).not.toContain("private-marker");
});

test("le Dashboard affiche l’avertissement réel si aucun champion configuré n’est pickable", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    configured: true,
    autoPick: true,
    phase: "ChampSelect",
  });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#dashboard");
  await eventsConnected;
  const session = {
    gameConfig: { queueId: 420, gameMode: "CLASSIC" },
    localPlayerCellId: 1,
    myTeam: [{ cellId: 1, summonerId: 24680135, assignedPosition: "TOP", championId: 0, spell1Id: 0, spell2Id: 0, selectedRunePageId: 0, selectedSkinId: 0 }],
    actions: [[{ actorCellId: 1, type: "pick", id: 101, isInProgress: true, completed: false }]],
    bans: { myTeamBans: [], theirTeamBans: [] },
  };
  await app.configureLcuState({ session, pickable_champion_ids: [] });
  await app.emitLcuEvent("/lol-champ-select/v1/session", session);

  const status = page.locator(".automation-status");
  await expect(status).toHaveAttribute("class", /is-warning/);
  await expect(status).toContainText("Aucun champion configuré n’est disponible.");
  await expect(status.locator("time")).toBeVisible();
});

test("le statut de poste détecté est localisé et présenté comme une information", async ({ page }) => {
  const emptyRoleSession = {
    gameConfig: { queueId: 420, gameMode: "CLASSIC" },
    localPlayerCellId: 1,
    myTeam: [{ cellId: 1, summonerId: 24680135, assignedPosition: "", championId: 0, spell1Id: 0, spell2Id: 0, selectedRunePageId: 0, selectedSkinId: 0 }],
    actions: [],
    bans: { myTeamBans: [], theirTeamBans: [] },
  };
  const { app } = await setupApplication(page, { connected: true, configured: true, phase: "ChampSelect", lcuState: { session: emptyRoleSession } });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#dashboard");
  await eventsConnected;

  const roleSession = { ...emptyRoleSession, myTeam: [{ ...emptyRoleSession.myTeam[0], assignedPosition: "TOP" }] };
  await app.configureLcuState({ session: roleSession });
  await app.emitLcuEvent("/lol-champ-select/v1/session", roleSession);

  const status = page.locator(".automation-status");
  await expect(status).toHaveText(/Rôle détecté : Top\./);
  await expect(status).toHaveClass(/is-info/);
});

test("le statut du ban reflète le maître des automatisations Presets", async ({ page }) => {
  await setupApplication(page, {
    connected: true,
    settings: { presets_enabled: false, auto_ban_enabled: true },
  });
  await page.goto("/#dashboard");

  await expect(page.locator(".ban-visual strong")).toHaveText("Désactivé");
});

test("la sidebar contient un identifiant manuel long sur plusieurs résolutions", async ({ page }) => {
  await setupApplication(page, {
    connected: true,
    autoDetect: false,
    manualRiotId: "A-Very-Long-Player-Name-That-Must-Be-Clipped#TAG",
    phase: "WaitingForStats",
  });
  await page.goto("/#dashboard");
  await expect(page.locator(".sidebar-account")).toHaveAttribute("title", "E2E Player#SAFE");

  for (const viewport of [{ width: 800, height: 540 }, { width: 1100, height: 760 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }]) {
    await page.setViewportSize(viewport);
    const bounds = await page.locator(".sidebar-account").evaluate((account) => {
      const sidebar = account.closest(".app-sidebar")!;
      return { accountRight: account.getBoundingClientRect().right, sidebarRight: sidebar.getBoundingClientRect().right, textOverflow: getComputedStyle(account.querySelector("span")!).textOverflow };
    });
    expect(bounds.accountRight).toBeLessThanOrEqual(bounds.sidebarRight);
    expect(bounds.textOverflow).toBe("ellipsis");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await expect(page.locator(".phase-strip strong")).toHaveText("Récupération des stats");
    await expect(page.getByText(/Compte synchronisé/)).toHaveCount(0);
    await expect(page.locator(".runtime-topbar")).toHaveCount(0);
  }
});

test("les phases reçues par le WebSocket LCU sont localisées", async ({ page }) => {
  const { app } = await setupApplication(page, { connected: true, phase: "Lobby" });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#dashboard");
  await eventsConnected;

  for (const [phase, label] of [
    ["Lobby", "Dans le lobby"],
    ["Matchmaking", "Recherche de partie"],
    ["ReadyCheck", "Partie trouvée"],
    ["ChampSelect", "Sélection des champions"],
    ["InProgress", "En partie"],
    ["WaitingForStats", "Récupération des stats"],
    ["EndOfGame", "Fin de partie"],
    ["None", "En attente"],
  ]) {
    await app.configureLcuState({ phase });
    await app.emitLcuEvent("/lol-gameflow/v1/gameflow-phase", phase);
    await expect(page.locator(".phase-strip strong")).toHaveText(label);
  }
  await expect(page.locator(".sidebar-runtime")).toHaveAttribute("aria-label", "Client connecté");
});

test("Dashboard suit la fermeture réelle du client puis une reconnexion LCU", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    phase: "Lobby",
    settings: { close_app_on_lol_exit: false },
  });
  await page.goto("/#dashboard");
  await expect(page.locator(".sidebar-runtime")).toHaveAttribute("aria-label", "Client connecté");

  await app.configureLcuConnection({ online: false });
  await expect.poll(async () => (await readRuntime(page)).connected).toBe(false);
  await expect(page.locator(".sidebar-runtime")).toHaveAttribute("aria-label", "Client déconnecté");

  await app.configureLcuConnection({ online: true });
  await app.waitForWebSocketSubscription(2);
  await expect.poll(async () => (await readRuntime(page)).connected).toBe(true);
  await app.emitLcuEvent("/lol-gameflow/v1/gameflow-phase", "ChampSelect");
  await expect.poll(async () => (await readRuntime(page)).phase).toBe("ChampSelect");
  await expect(page.locator(".sidebar-runtime")).toHaveAttribute("aria-label", "Client connecté");
  await expect(page.locator(".phase-strip strong")).toHaveText("Sélection des champions");
});

test("le Dashboard suit League fermé, démarrage sans session, les phases de partie et la reconnexion", async ({ page }) => {
  const { app } = await setupApplication(page, {
    clearDetectedAccount: true,
    settings: { close_app_on_lol_exit: false },
  });
  await app.configureLcuConnection({ online: false });
  await expect.poll(async () => (await readRuntime(page)).connected).toBe(false);
  await page.goto("/#dashboard");
  await expect(page.locator(".sidebar-runtime")).toHaveAttribute("aria-label", "Client déconnecté");
  await expect(page.locator(".sidebar-account")).toHaveText("Aucun compte connecté");

  const nextSubscription = app.websocketSubscriptions.length + 1;
  await app.configureLcuConnection({ online: true });
  await app.waitForWebSocketSubscription(nextSubscription);
  await expect.poll(async () => (await readRuntime(page)).connected).toBe(true);
  await expect(page.locator(".phase-strip strong")).toHaveText("En attente");

  for (const [phase, label] of [
    ["Lobby", "Dans le lobby"],
    ["Matchmaking", "Recherche de partie"],
    ["ReadyCheck", "Partie trouvée"],
    ["ChampSelect", "Sélection des champions"],
    ["InProgress", "En partie"],
    ["WaitingForStats", "Récupération des stats"],
    ["EndOfGame", "Fin de partie"],
    ["None", "En attente"],
  ]) {
    await app.configureLcuState({ phase });
    await app.emitLcuEvent("/lol-gameflow/v1/gameflow-phase", phase);
    await expect(page.locator(".phase-strip strong")).toHaveText(label);
  }

  await app.configureLcuConnection({ online: false });
  await expect.poll(async () => (await readRuntime(page)).connected).toBe(false);
  await expect(page.locator(".sidebar-runtime")).toHaveAttribute("aria-label", "Client déconnecté");
  const reconnectSubscription = app.websocketSubscriptions.length + 1;
  await app.configureLcuConnection({ online: true });
  await app.waitForWebSocketSubscription(reconnectSubscription);
  await expect.poll(async () => (await readRuntime(page)).connected).toBe(true);
  await expect(page.locator(".sidebar-runtime")).toHaveAttribute("aria-label", "Client connecté");
});

test("[DASH-12] la sidebar efface le compte hors ligne puis suit le nouveau compte connecté", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    phase: "Lobby",
    settings: { close_app_on_lol_exit: false },
  });
  await page.goto("/#dashboard");
  const account = page.locator(".sidebar-account");
  await expect(account).toHaveText("E2E Player#SAFE");

  await app.configureLcuConnection({ online: false });
  await expect.poll(async () => (await readRuntime(page)).connected).toBe(false);
  await expect(account).toHaveText("Aucun compte connecté");

  const nextAccount = {
    gameName: "Dashboard Player B",
    gameTag: "BBBB",
    summonerId: 22222222,
    name: "Dashboard Player B",
    puuid: "otp-lol-e2e-dashboard-b",
  };
  await app.configureLcuState({
    account_responses: { "/lol-chat/v1/me": { status: 200, payload: nextAccount } },
  });
  const nextSubscription = app.websocketSubscriptions.length + 1;
  await app.configureLcuConnection({ online: true });
  await app.waitForWebSocketSubscription(nextSubscription);
  await app.emitLcuEvent("/lol-chat/v1/me", nextAccount);

  await expect.poll(async () => (await readRuntime(page)).riot_id).toBe("Dashboard Player B#BBBB");
  await expect(account).toHaveText("Dashboard Player B#BBBB");
});

test("Dashboard affiche le skin choisi et retombe sur le portrait du champion si le skin est désactivé", async ({ page }) => {
  await setupApplication(page, { connected: true, configured: true, networkStatus: "online" });
  await page.goto("/#dashboard");

  const card = page.locator(".priority-card").first();
  const splash = card.locator(".priority-art img");
  const skinLabel = card.locator(".skin-preview strong");
  await expect(skinLabel).toHaveText("God-King Garen");
  await page.locator(".priority-card").first().click();
  await page.getByRole("dialog", { name: "Modifier la priorité 1" }).getByRole("radio", { name: "Aucun" }).click();
  await expect(skinLabel).toHaveText("Aucun");
  await expect(splash).toHaveAttribute("src", /\/api\/assets\/champions\/86\/splash/);
});

for (const [index, slot] of ["pick_1", "pick_2", "pick_3"].entries()) {
  const priority = index + 1;
  test(`la carte Dashboard ouvre le preset ${priority} sans ouvrir le sélecteur`, async ({ page }) => {
    await setupApplication(page, { connected: true, configured: true });
    await page.goto("/#dashboard");

    const card = page.locator(".priority-card").nth(index);
    await card.click();

    await expect(page).toHaveURL(new RegExp(`#dashboard/${slot}$`));
    const editor = page.getByRole("dialog", { name: `Modifier la priorité ${priority}` });
    await expect(editor).toBeVisible();
    await expect(page.locator(".picker-drawer")).toHaveCount(0);
    await expect(page.locator("#champion-search")).toHaveCount(0);

    await page.locator(".champion-choice").click();
    await expect(page.locator(".picker-drawer")).toBeVisible();
    await expect(page.locator("#champion-search")).toBeFocused();
    await page.locator('.drawer-card button[aria-label="Fermer"]').click();
    await expect(page.locator(".champion-choice")).toBeFocused();
    await page.locator('.preset-editor-dialog button[aria-label="Fermer"]').click();
    await expect(page).toHaveURL(/#dashboard$/);
    await expect(page.locator(".priority-card-link").nth(index)).toBeFocused();
  });
}

test("modifier le ban choisit réellement un champion puis revient au Dashboard", async ({ page }) => {
  await setupApplication(page, { connected: true, configured: true });
  await page.goto("/#dashboard");

  await page.locator(".ban-panel").click();
  await expect(page).toHaveURL(/#dashboard\/ban$/);
  await expect(page.locator("#champion-search")).toBeFocused();
  await page.locator("#champion-search").fill("Teemo");
  await page.getByRole("option", { name: /Teemo/ }).click();

  await expect(page).toHaveURL(/#dashboard$/);
  await expect(page.getByRole("heading", { name: "Teemo" })).toBeVisible();
  await expect(page.locator("#dashboard-edit-ban")).toBeFocused();
  await expect(await readPresets(page)).toMatchObject({ selected_ban: "Teemo" });
});

test("[DASH-04] annuler la sélection du ban garde la configuration puis rend le focus au déclencheur", async ({ page }) => {
  await setupApplication(page, { connected: true, configured: true });
  await page.goto("/#dashboard");
  const selectedBanBefore = (await readPresets(page)).selected_ban;

  await page.locator(".ban-panel").click();
  await page.getByRole("button", { name: "Fermer" }).click();

  await expect(page).toHaveURL(/#dashboard$/);
  await expect(page.locator("#dashboard-edit-ban")).toBeFocused();
  await expect.poll(async () => (await readPresets(page)).selected_ban).toBe(selectedBanBefore);
});

test("les aperçus bootstrap n’ajoutent pas de requêtes de catalogue à l’affichage des cartes", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  await setupApplication(page, { connected: true, configured: true, assignedPosition: "TOP" });
  await page.goto("/#dashboard");

  await expect(page.locator(".priority-card")).toHaveCount(3);
  await expect(page.locator(".priority-role")).toHaveCount(0);
  await expect(page.locator(".ban-visual img")).toHaveAttribute("src", /\/api\/assets\/(champions|app)\//);
  expect(requests.some((url) => /\/api\/(champions|skins)\//.test(url))).toBe(false);
  expect(await readSettings(page)).toMatchObject({ selected_pick_1: "Garen", selected_pick_2: "Lux", selected_pick_3: "Ashe" });
});
