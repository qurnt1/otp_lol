import { expect, readHistory, readPresets, readSettings, setupApplication, test, waitForRuntimeEvents } from "./helpers";

const runePerks = [8005, 8008, 9101, 8014, 8106, 8120, 5008, 5008, 5011];
const targetRunePage = {
  id: 401,
  name: "E2E Top",
  primaryStyleId: 8000,
  subStyleId: 8100,
  selectedPerkIds: runePerks,
  current: false,
  isValid: true,
};
const activeRunePage = { ...targetRunePage, id: 402, name: "Current Page", current: true };

function requestBody(value: unknown): Record<string, any> {
  return value && typeof value === "object" ? value as Record<string, any> : {};
}

function champSelectSession(actions: unknown[], championId = 0) {
  return {
    gameConfig: { queueId: 420, gameMode: "CLASSIC" },
    localPlayerCellId: 1,
    myTeam: [{
      cellId: 1,
      summonerId: 24680135,
      assignedPosition: "TOP",
      championId,
      spell1Id: 0,
      spell2Id: 0,
      selectedRunePageId: 402,
      selectedSkinId: 0,
    }],
    actions,
    bans: { myTeamBans: [], theirTeamBans: [] },
  };
}

async function enableAutomation(page: import("@playwright/test").Page, label: string, key: string) {
  const toggle = page.getByRole("switch", { name: label });
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", "true");
  await expect.poll(async () => (await readSettings(page))[key]).toBe(true);
}

test("Auto-Pick applique le champion, sorts, skin et page de runes via le vrai LCU", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    configured: true,
    phase: "ChampSelect",
    networkStatus: "online",
    settings: { auto_pick_enabled: false, auto_summoners_enabled: false, skin_automation_enabled: false },
    lcuState: {
      static_data_online: true,
      pickable_champion_ids: [86],
      rune_pages: [targetRunePage, activeRunePage],
      current_rune_page: activeRunePage,
      session: champSelectSession([]),
    },
  });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#settings/automations");
  await eventsConnected;
  await enableAutomation(page, "Auto-Pick", "auto_pick_enabled");
  await enableAutomation(page, "Auto-Summs", "auto_summoners_enabled");
  await enableAutomation(page, "Automatisation des skins", "skin_automation_enabled");

  await page.goto("/#dashboard");
  await page.locator(".priority-card").first().click();
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  const runeToggle = editor.getByRole("checkbox", { name: "Appliquer automatiquement les runes" });
  await expect(runeToggle).toBeChecked();
  await runeToggle.click();
  await expect(runeToggle).not.toBeChecked();
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.rune_auto_apply).toBe(false);
  await runeToggle.click();
  await expect(runeToggle).toBeChecked();
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.rune_auto_apply).toBe(true);
  await editor.getByRole("button", { name: "Fermer" }).last().click();

  const session = champSelectSession([[{
    actorCellId: 1,
    type: "pick",
    id: 501,
    isInProgress: true,
    completed: false,
    championId: 0,
  }]]);
  const requestOffset = app.lcuRequests.length;
  await app.configureLcuState({ session, pickable_champion_ids: [86] });
  await app.emitLcuEvent("/lol-champ-select/v1/session", session);

  await expect.poll(() => app.lcuRequests.slice(requestOffset).some((request) =>
    request.method === "PATCH" && request.path === "/lol-champ-select/v1/session/actions/501"
      && requestBody(request.body).completed === true && requestBody(request.body).championId === 86
  )).toBe(true);
  await expect.poll(() => app.lcuRequests.slice(requestOffset).some((request) =>
    request.method === "PATCH" && request.path === "/lol-champ-select/v1/session/my-selection"
      && requestBody(request.body).spell1Id === 4 && requestBody(request.body).spell2Id === 14
  )).toBe(true);
  await expect.poll(() => app.lcuRequests.slice(requestOffset).some((request) =>
    request.method === "PATCH" && request.path === "/lol-champ-select/v1/session/my-selection"
      && requestBody(request.body).selectedSkinId === 86013
  )).toBe(true);
  await expect.poll(() => app.lcuRequests.slice(requestOffset).some((request) =>
    request.method === "PUT" && request.path === "/lol-perks/v1/pages/401"
      && requestBody(request.body).id === 401 && requestBody(request.body).current === true
  )).toBe(true);

  await expect.poll(async () => {
    const state = await app.readLcuState();
    const player = state.session.myTeam[0];
    return {
      actionLocked: state.session.actions[0][0].completed,
      championId: player.championId,
      spell1Id: player.spell1Id,
      spell2Id: player.spell2Id,
      skinId: player.selectedSkinId,
      runePageId: player.selectedRunePageId,
      activeRunePageId: state.current_rune_page.id,
    };
  }).toEqual({ actionLocked: true, championId: 86, spell1Id: 4, spell2Id: 14, skinId: 86013, runePageId: 401, activeRunePageId: 401 });

  const expectedHistory = [
    "Champion automatically locked in: Garen.",
    "Automatic summs applied: Flash + Ignite.",
    "Skin applied automatically: God-King Garen.",
    'Rune page applied: "E2E Top" (id=401).',
  ];
  await expect.poll(async () => {
    const messages = (await readHistory(page)).items.map((item) => item.message);
    return expectedHistory.every((message) => messages.includes(message));
  }).toBe(true);
  const status = page.locator(".automation-status");
  await expect(status).toHaveText(/Runes configurées : E2E Top\./);
  await expect(status).toHaveClass(/is-success/);
});

test("Auto-Ban verrouille le champion choisi et confirme l’état LCU", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    configured: true,
    phase: "ChampSelect",
    networkStatus: "online",
    autoBan: false,
    lcuState: { static_data_online: true, session: champSelectSession([]) },
  });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#settings/automations");
  await eventsConnected;
  await enableAutomation(page, "Auto-Ban", "auto_ban_enabled");

  await page.goto("/#dashboard");
  await expect.poll(async () => (await readPresets(page)).selected_ban).toBe("Teemo");

  const session = champSelectSession([[{
    actorCellId: 1,
    type: "ban",
    id: 502,
    isInProgress: true,
    completed: false,
    championId: 0,
  }]]);
  const requestOffset = app.lcuRequests.length;
  await app.configureLcuState({ session });
  await app.emitLcuEvent("/lol-champ-select/v1/session", session);

  await expect.poll(() => app.lcuRequests.slice(requestOffset).some((request) =>
    request.method === "PATCH" && request.path === "/lol-champ-select/v1/session/actions/502"
      && requestBody(request.body).completed === true && requestBody(request.body).championId === 17
  )).toBe(true);
  await expect.poll(async () => {
    const state = await app.readLcuState();
    return { completed: state.session.actions[0][0].completed, bans: state.session.bans.myTeamBans };
  }).toEqual({ completed: true, bans: [17] });
  await expect(page.locator(".automation-status")).toHaveText(/Champion banni : Teemo\./);
  await expect(page.locator(".automation-status")).toHaveClass(/is-success/);
  expect((await readHistory(page)).items.map((item) => item.message)).toContain("Automatic ban confirmed on Teemo.");
});

test("Auto Play Again envoie la commande LCU et revient au lobby", async ({ page }) => {
  const { app } = await setupApplication(page, { connected: true, phase: "WaitingForStats", autoPlayAgain: false });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#settings/automations");
  await eventsConnected;
  await enableAutomation(page, "Auto Play Again", "auto_play_again_enabled");
  await page.goto("/#dashboard");

  const requestOffset = app.lcuRequests.length;
  await app.emitLcuEvent("/lol-gameflow/v1/gameflow-phase", "WaitingForStats");
  await expect.poll(() => app.lcuRequests.slice(requestOffset).some((request) =>
    request.method === "POST" && request.path === "/lol-lobby/v2/play-again" && request.body === null
  ), { timeout: 12_000 }).toBe(true);
  await expect.poll(async () => (await app.readLcuState()).phase).toBe("Lobby");
  await app.emitLcuEvent("/lol-gameflow/v1/gameflow-phase", "Lobby");

  await expect(page.locator(".phase-strip strong")).toHaveText("Dans le lobby");
  await expect(page.locator(".automation-status")).toContainText("Retour au lobby effectué.");
  expect((await readHistory(page)).items.map((item) => item.message)).toContain("Automatically returned to lobby after the game.");
});
