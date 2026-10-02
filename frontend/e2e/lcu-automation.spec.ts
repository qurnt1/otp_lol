import { expect, readHistory, readPresets, readRuntime, readSettings, setupApplication, test, waitForRuntimeEvents } from "./helpers";

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

async function disableAutomation(page: import("@playwright/test").Page, label: string, key: string) {
  const toggle = page.getByRole("switch", { name: label });
  await expect(toggle).toHaveAttribute("aria-checked", "true");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  await expect.poll(async () => (await readSettings(page))[key]).toBe(false);
}

test("[FE-LCU-AUTO-PICK-OFF-01] désactiver Auto-Pick empêche le verrouillage d’un pick actif", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    configured: true,
    phase: "ChampSelect",
    autoPick: true,
    lcuState: {
      static_data_online: true,
      pickable_champion_ids: [86],
      session: champSelectSession([]),
    },
  });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#settings/automations");
  await eventsConnected;
  await disableAutomation(page, "Auto-Pick", "auto_pick_enabled");

  const actionId = 610;
  const session = champSelectSession([[{
    actorCellId: 1,
    type: "pick",
    id: actionId,
    isInProgress: true,
    completed: false,
    championId: 0,
  }]]);
  const requestOffset = app.lcuRequests.length;
  await app.configureLcuState({ session, pickable_champion_ids: [86] });
  const event = await app.emitLcuEvent("/lol-champ-select/v1/session", session);
  await app.waitForLcuEventCompletion(event.id);

  const state = await app.readLcuState();
  expect(state.session.actions[0][0]).toMatchObject({ completed: false, championId: 0 });
  expect(app.lcuRequests.slice(requestOffset).some((request) =>
    request.method === "PATCH" && request.path === `/lol-champ-select/v1/session/actions/${actionId}`,
  )).toBe(false);
  expect((await readHistory(page)).items.map((item) => item.message))
    .not.toContain("Champion automatically locked in: Garen.");
});

test("[FE-LCU-AUTO-BAN-OFF-01] désactiver Auto-Ban empêche le verrouillage d’un ban actif", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    configured: true,
    phase: "ChampSelect",
    autoBan: true,
    lcuState: { static_data_online: true, session: champSelectSession([]) },
  });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#settings/automations");
  await eventsConnected;
  await disableAutomation(page, "Auto-Ban", "auto_ban_enabled");

  const actionId = 611;
  const session = champSelectSession([[{
    actorCellId: 1,
    type: "ban",
    id: actionId,
    isInProgress: true,
    completed: false,
    championId: 0,
  }]]);
  const requestOffset = app.lcuRequests.length;
  await app.configureLcuState({ session });
  const event = await app.emitLcuEvent("/lol-champ-select/v1/session", session);
  await app.waitForLcuEventCompletion(event.id);

  const state = await app.readLcuState();
  expect(state.session.actions[0][0]).toMatchObject({ completed: false, championId: 0 });
  expect(state.session.bans.myTeamBans).toEqual([]);
  expect(app.lcuRequests.slice(requestOffset).some((request) =>
    request.method === "PATCH" && request.path === `/lol-champ-select/v1/session/actions/${actionId}`,
  )).toBe(false);
  expect((await readHistory(page)).items.map((item) => item.message))
    .not.toContain("Automatic ban confirmed on Teemo.");
});

test("[FE-LCU-PRESET-MASTER-OFF-01] couper le maître des presets bloque les picks et bans automatiques", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    configured: true,
    phase: "ChampSelect",
    autoPick: true,
    autoBan: true,
    lcuState: { static_data_online: true, pickable_champion_ids: [86], session: champSelectSession([]) },
  });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#dashboard");
  await eventsConnected;
  const master = page.getByRole("switch", { name: "Utiliser les presets en sélection" });
  await expect(master).toHaveAttribute("aria-checked", "true");
  await master.click();
  await expect(master).toHaveAttribute("aria-checked", "false");
  await expect.poll(async () => (await readSettings(page)).presets_enabled).toBe(false);

  const requestOffset = app.lcuRequests.length;
  const pickActionId = 612;
  const pickSession = champSelectSession([[{
    actorCellId: 1,
    type: "pick",
    id: pickActionId,
    isInProgress: true,
    completed: false,
    championId: 0,
  }]]);
  await app.configureLcuState({ session: pickSession, pickable_champion_ids: [86] });
  const pickEvent = await app.emitLcuEvent("/lol-champ-select/v1/session", pickSession);
  await app.waitForLcuEventCompletion(pickEvent.id);

  const banActionId = 613;
  const banSession = champSelectSession([[{
    actorCellId: 1,
    type: "ban",
    id: banActionId,
    isInProgress: true,
    completed: false,
    championId: 0,
  }]]);
  await app.configureLcuState({ session: banSession });
  const banEvent = await app.emitLcuEvent("/lol-champ-select/v1/session", banSession);
  await app.waitForLcuEventCompletion(banEvent.id);

  const state = await app.readLcuState();
  expect(state.session.actions[0][0]).toMatchObject({ completed: false, championId: 0 });
  expect(state.session.bans.myTeamBans).toEqual([]);
  expect(app.lcuRequests.slice(requestOffset).some((request) =>
    request.method === "PATCH" && [pickActionId, banActionId].some((id) => request.path === `/lol-champ-select/v1/session/actions/${id}`),
  )).toBe(false);
  expect((await readHistory(page)).items.map((item) => item.message))
    .not.toContain("Champion automatically locked in: Garen.");
  expect((await readHistory(page)).items.map((item) => item.message))
    .not.toContain("Automatic ban confirmed on Teemo.");
});

test("[FE-LCU-AUTO-SUMMONERS-OFF-01] désactiver Auto-Summs laisse les sorts LCU inchangés après un pick", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    configured: true,
    phase: "ChampSelect",
    autoPick: true,
    autoSummoners: true,
    settings: { skin_automation_enabled: false },
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
  await disableAutomation(page, "Auto-Summs", "auto_summoners_enabled");

  const actionId = 614;
  const session = champSelectSession([[{
    actorCellId: 1,
    type: "pick",
    id: actionId,
    isInProgress: true,
    completed: false,
    championId: 0,
  }]]);
  const requestOffset = app.lcuRequests.length;
  await app.configureLcuState({ session, pickable_champion_ids: [86] });
  const event = await app.emitLcuEvent("/lol-champ-select/v1/session", session);
  await app.waitForLcuEventCompletion(event.id);
  await app.waitForLcuRequest("PUT", "/lol-perks/v1/pages/401");

  const state = await app.readLcuState();
  expect(state.session.actions[0][0]).toMatchObject({ completed: true, championId: 86 });
  expect(state.session.myTeam[0]).toMatchObject({ championId: 86, spell1Id: 0, spell2Id: 0 });
  expect(app.lcuRequests.slice(requestOffset).some((request) =>
    request.method === "PATCH" && request.path === "/lol-champ-select/v1/session/my-selection",
  )).toBe(false);
  expect((await readHistory(page)).items.map((item) => item.message))
    .not.toContain("Automatic summs applied: Flash + Ignite.");
});

test("[FE-LCU-SKIN-OFF-01] désactiver l’automatisation des skins laisse le skin LCU inchangé après un pick", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    configured: true,
    phase: "ChampSelect",
    autoPick: true,
    autoSummoners: false,
    skinAutomation: true,
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
  await disableAutomation(page, "Automatisation des skins", "skin_automation_enabled");

  const actionId = 615;
  const session = champSelectSession([[{
    actorCellId: 1,
    type: "pick",
    id: actionId,
    isInProgress: true,
    completed: false,
    championId: 0,
  }]]);
  const requestOffset = app.lcuRequests.length;
  await app.configureLcuState({ session, pickable_champion_ids: [86] });
  const event = await app.emitLcuEvent("/lol-champ-select/v1/session", session);
  await app.waitForLcuEventCompletion(event.id);
  await app.waitForLcuRequest("PUT", "/lol-perks/v1/pages/401");

  const state = await app.readLcuState();
  expect(state.session.actions[0][0]).toMatchObject({ completed: true, championId: 86 });
  expect(state.session.myTeam[0]).toMatchObject({ championId: 86, selectedSkinId: 0 });
  expect(app.lcuRequests.slice(requestOffset).some((request) =>
    request.method === "PATCH" && request.path === "/lol-champ-select/v1/session/my-selection",
  )).toBe(false);
  expect((await readHistory(page)).items.some((item) => item.message.startsWith("Skin applied automatically:"))).toBe(false);
});

test("[FE-LCU-PLAY-AGAIN-OFF-01] désactiver Auto Play Again empêche le retour automatique au lobby", async ({ page }) => {
  const { app } = await setupApplication(page, { connected: true, phase: "Lobby", autoPlayAgain: true });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#settings/automations");
  await eventsConnected;
  await disableAutomation(page, "Auto Play Again", "auto_play_again_enabled");

  const requestOffset = app.lcuRequests.length;
  await app.configureLcuState({ phase: "WaitingForStats" });
  const event = await app.emitLcuEvent("/lol-gameflow/v1/gameflow-phase", "WaitingForStats");
  await app.waitForLcuEventCompletion(event.id);

  expect((await app.readLcuState()).phase).toBe("WaitingForStats");
  expect(app.lcuRequests.slice(requestOffset).some((request) =>
    request.method === "POST" && request.path === "/lol-lobby/v2/play-again",
  )).toBe(false);
  expect((await readHistory(page)).items.map((item) => item.message))
    .not.toContain("Automatically returned to lobby after the game.");
});

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

test("[FE-LCU-RUNE-OFF-01] Auto-Pick confirme le champion sans modifier la page LCU quand l’application automatique des runes est coupée", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    configured: true,
    phase: "ChampSelect",
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
  await page.goto("/#dashboard");
  await eventsConnected;

  const autoPick = page.getByRole("switch", { name: "Auto-Pick" });
  await autoPick.click();
  await expect(autoPick).toHaveAttribute("aria-checked", "true");
  await expect.poll(async () => (await readSettings(page)).auto_pick_enabled).toBe(true);
  const card = page.locator(".priority-card").first();
  await card.click();
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  const runeToggle = editor.getByRole("checkbox", { name: "Appliquer automatiquement les runes" });
  await expect(runeToggle).toBeChecked();
  await runeToggle.click();
  await expect(runeToggle).not.toBeChecked();
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.rune_auto_apply).toBe(false);
  await editor.getByRole("button", { name: "Fermer" }).last().click();

  const session = champSelectSession([[{
    actorCellId: 1,
    type: "pick",
    id: 511,
    isInProgress: true,
    completed: false,
    championId: 0,
  }]]);
  const requestOffset = app.lcuRequests.length;
  await app.configureLcuState({ session, pickable_champion_ids: [86] });
  const event = await app.emitLcuEvent("/lol-champ-select/v1/session", session);
  await app.waitForLcuEventCompletion(event.id);

  await expect.poll(() => app.lcuRequests.slice(requestOffset).some((request) =>
    request.method === "PATCH" && request.path === "/lol-champ-select/v1/session/actions/511"
      && requestBody(request.body).completed === true && requestBody(request.body).championId === 86
  )).toBe(true);
  await expect.poll(async () => (await app.readLcuState()).session.actions[0][0].completed).toBe(true);
  await expect.poll(async () => (await app.readLcuState()).current_rune_page.id).toBe(402);
  await expect(page.locator(".automation-status-message")).toHaveText("Champion sélectionné : Garen.");

  expect(app.lcuRequests.slice(requestOffset).filter((request) =>
    request.method === "PUT" && request.path === "/lol-perks/v1/pages/401",
  )).toHaveLength(0);
  const history = await readHistory(page);
  expect(history.items.map((item) => item.message)).toContain("Champion automatically locked in: Garen.");
  expect(history.items.some((item) => item.message.startsWith('Rune page applied: "E2E Top"'))).toBe(false);
});

test("[FE-LCU-SKIN-RANDOM-01] le pool aléatoire choisi dans l’éditeur est appliqué et confirmé par le LCU", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    configured: true,
    phase: "ChampSelect",
    settings: { auto_pick_enabled: false, auto_summoners_enabled: false, skin_automation_enabled: true },
    lcuState: {
      static_data_online: true,
      pickable_champion_ids: [86],
      rune_pages: [targetRunePage, activeRunePage],
      current_rune_page: activeRunePage,
      session: champSelectSession([]),
    },
  });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#dashboard");
  await eventsConnected;
  const card = page.locator(".priority-card").first();
  await card.click();
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  const runeToggle = editor.getByRole("checkbox", { name: "Appliquer automatiquement les runes" });
  await runeToggle.click();
  await expect(runeToggle).not.toBeChecked();
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.rune_auto_apply).toBe(false);
  await editor.getByRole("radio", { name: "Aléatoire" }).click();
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.skin_mode).toBe("random");
  await editor.getByRole("button", { name: /Pool aléatoire/ }).click();
  const skinPicker = page.getByRole("dialog", { name: "Galerie des skins" });
  const ownedOnly = skinPicker.getByRole("checkbox", { name: "Possédés uniquement" });
  if (await ownedOnly.isChecked()) await ownedOnly.uncheck();
  await skinPicker.getByRole("button", { name: "Tout effacer" }).click();
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.random_skin_pool).toEqual([]);

  const poolIds = [86001, 86013];
  const commando = skinPicker.getByRole("checkbox", { name: "Commando Garen" });
  const godKing = skinPicker.getByRole("checkbox", { name: "God-King Garen" });
  await expect(commando).toBeVisible();
  await expect(godKing).toBeVisible();
  const commandoPoolUpdate = page.waitForResponse((response) =>
    response.request().method() === "PUT" && new URL(response.url()).pathname === "/api/presets/pick_1",
  );
  await commando.click();
  expect((await commandoPoolUpdate).status()).toBe(200);
  await expect(commando).toBeChecked();
  const godKingPoolUpdate = page.waitForResponse((response) =>
    response.request().method() === "PUT" && new URL(response.url()).pathname === "/api/presets/pick_1",
  );
  await godKing.click();
  expect((await godKingPoolUpdate).status()).toBe(200);
  await expect(godKing).toBeChecked();
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.random_skin_pool.map((skin: { skin_id: number }) => skin.skin_id)).toEqual(poolIds);
  await page.keyboard.press("Escape");
  await editor.getByRole("button", { name: "Fermer" }).last().click();

  const autoPick = page.getByRole("switch", { name: "Auto-Pick" });
  await autoPick.click();
  await expect(autoPick).toHaveAttribute("aria-checked", "true");
  await expect.poll(async () => (await readSettings(page)).auto_pick_enabled).toBe(true);

  const session = champSelectSession([[{
    actorCellId: 1,
    type: "pick",
    id: 512,
    isInProgress: true,
    completed: false,
    championId: 0,
  }]]);
  const requestOffset = app.lcuRequests.length;
  await app.configureLcuState({ session, pickable_champion_ids: [86], pickable_skins: [] });
  const event = await app.emitLcuEvent("/lol-champ-select/v1/session", session);
  await app.waitForLcuEventCompletion(event.id);

  await expect.poll(() => app.lcuRequests.slice(requestOffset).some((request) =>
    request.method === "PATCH" && request.path === "/lol-champ-select/v1/session/actions/512"
      && requestBody(request.body).completed === true && requestBody(request.body).championId === 86
  )).toBe(true);
  await expect.poll(() => app.lcuRequests.slice(requestOffset).some((request) =>
    request.method === "PATCH" && request.path === "/lol-champ-select/v1/session/my-selection"
      && poolIds.includes(requestBody(request.body).selectedSkinId)
  )).toBe(true);
  await expect.poll(async () => poolIds.includes((await app.readLcuState()).session.myTeam[0].selectedSkinId)).toBe(true);
  const selectedSkinId = (await app.readLcuState()).session.myTeam[0].selectedSkinId;
  expect(poolIds).toContain(selectedSkinId);
  const selectedSkinName = selectedSkinId === 86001 ? "Commando Garen" : "God-King Garen";
  const selectedSkinPatch = app.lcuRequests.slice(requestOffset).find((request) =>
    request.method === "PATCH" && request.path === "/lol-champ-select/v1/session/my-selection"
      && requestBody(request.body).selectedSkinId === selectedSkinId
  );
  expect(selectedSkinPatch).toBeDefined();
  await expect(page.locator(".automation-status-message")).toHaveText(`Skin sélectionné : ${selectedSkinName}.`);
  await expect.poll(async () => (await readHistory(page)).items.map((item) => item.message)).toContain(`Skin applied automatically: ${selectedSkinName}.`);
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

test("Auto-Ban retente après un refus LCU et ne confirme qu’une action appliquée", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    configured: true,
    phase: "ChampSelect",
    autoBan: false,
    lcuState: { static_data_online: true, session: champSelectSession([]) },
  });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#settings/automations");
  await eventsConnected;
  await enableAutomation(page, "Auto-Ban", "auto_ban_enabled");
  await page.goto("/#dashboard");

  const actionId = 504;
  const actionPath = `/lol-champ-select/v1/session/actions/${actionId}`;
  await app.configureLcuState({ mutation_responses: { [`PATCH ${actionPath}`]: [503] } });
  const session = champSelectSession([[{
    actorCellId: 1,
    type: "ban",
    id: actionId,
    isInProgress: true,
    completed: false,
    championId: 0,
  }]]);
  await app.configureLcuState({ session });
  await app.emitLcuEvent("/lol-champ-select/v1/session", session);

  const rejected = await app.waitForLcuResponse("PATCH", actionPath, 503);
  expect(rejected.status).toBe(503);
  const rejectedState = await app.readLcuState();
  expect(rejectedState.session.actions[0][0]).toMatchObject({ completed: false, championId: 0 });
  expect(rejectedState.session.bans.myTeamBans).toEqual([]);
  expect((await readHistory(page)).items.map((item) => item.message))
    .not.toContain("Automatic ban confirmed on Teemo.");

  await app.waitForChampSelectRetryReady();
  await app.emitLcuEvent("/lol-champ-select/v1/session", session);
  await expect.poll(async () => {
    const state = await app.readLcuState();
    return { completed: state.session.actions[0][0].completed, bans: state.session.bans.myTeamBans };
  }, { timeout: 12_000 }).toEqual({ completed: true, bans: [17] });
  await expect(page.locator(".automation-status")).toHaveText(/Champion banni : Teemo\./);
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

test("Auto Play Again réessaie après un refus du LCU et ne confirme qu’au retour au lobby", async ({ page }) => {
  const { app } = await setupApplication(page, { connected: true, phase: "WaitingForStats", autoPlayAgain: false });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#settings/automations");
  await eventsConnected;
  await enableAutomation(page, "Auto Play Again", "auto_play_again_enabled");
  await page.goto("/#dashboard");

  const actionPath = "/lol-lobby/v2/play-again";
  await app.configureLcuState({ mutation_responses: { [`POST ${actionPath}`]: [503] } });
  const requestOffset = app.lcuRequests.length;
  await app.emitLcuEvent("/lol-gameflow/v1/gameflow-phase", "WaitingForStats");

  const rejected = await app.waitForLcuResponse("POST", actionPath, 503);
  expect(rejected.status).toBe(503);
  expect((await app.readLcuState()).phase).toBe("WaitingForStats");
  expect((await readHistory(page)).items.map((item) => item.message))
    .not.toContain("Automatically returned to lobby after the game.");

  await expect.poll(() => app.lcuRequests.slice(requestOffset).filter((request) =>
    request.method === "POST" && request.path === actionPath,
  ).length).toBeGreaterThanOrEqual(2);
  await expect.poll(async () => (await app.readLcuState()).phase).toBe("Lobby");
  await app.emitLcuEvent("/lol-gameflow/v1/gameflow-phase", "Lobby");
  await expect.poll(async () => (await readRuntime(page)).phase).toBe("Lobby");
  await expect(page.locator(".phase-strip strong")).toHaveText("Dans le lobby");
  await expect(page.locator(".automation-status")).toContainText("Retour au lobby effectué.");
  expect((await readHistory(page)).items.map((item) => item.message))
    .toContain("Automatically returned to lobby after the game.");
});

test("Auto Play Again s’arrête si League quitte la phase de fin pendant l’attente", async ({ page }) => {
  const { app } = await setupApplication(page, { connected: true, phase: "Lobby", autoPlayAgain: false });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#settings/automations");
  await eventsConnected;
  await enableAutomation(page, "Auto Play Again", "auto_play_again_enabled");
  await page.goto("/#dashboard");

  await app.emitLcuEvent("/lol-gameflow/v1/gameflow-phase", "WaitingForStats");
  await app.emitLcuEvent("/lol-gameflow/v1/gameflow-phase", "Lobby");
  await expect(page.locator(".phase-strip strong")).toHaveText("Dans le lobby");
  await page.waitForTimeout(2_200);

  expect(app.lcuRequests.filter((request) =>
    request.method === "POST" && request.path === "/lol-lobby/v2/play-again",
  )).toEqual([]);
  expect((await readHistory(page)).items.map((item) => item.message))
    .not.toContain("Automatically returned to lobby after the game.");
});

test("Auto-Pick saute la première priorité et verrouille le prochain champion disponible", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    configured: true,
    phase: "ChampSelect",
    lcuState: { static_data_online: true, pickable_champion_ids: [99], session: champSelectSession([]) },
  });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#settings/automations");
  await eventsConnected;

  await expect(await readPresets(page)).toMatchObject({
    slots: { pick_1: { champion: "Garen" }, pick_2: { champion: "Lux" } },
  });
  await enableAutomation(page, "Auto-Pick", "auto_pick_enabled");
  await page.goto("/#dashboard");

  const session = champSelectSession([[{
    actorCellId: 1,
    type: "pick",
    id: 505,
    isInProgress: true,
    completed: false,
    championId: 0,
  }]]);
  const requestOffset = app.lcuRequests.length;
  await app.configureLcuState({ session, pickable_champion_ids: [99] });
  await app.emitLcuEvent("/lol-champ-select/v1/session", session);

  await expect.poll(() => app.lcuRequests.slice(requestOffset).some((request) =>
    request.method === "PATCH" && request.path === "/lol-champ-select/v1/session/actions/505"
      && requestBody(request.body).completed === true && requestBody(request.body).championId === 99
  )).toBe(true);
  const state = await app.readLcuState();
  expect(state.session.actions[0][0]).toMatchObject({ completed: true, championId: 99 });
  expect(state.session.myTeam[0].championId).toBe(99);
  const actionPatches = app.lcuRequests.slice(requestOffset).filter((request) =>
    request.method === "PATCH" && request.path === "/lol-champ-select/v1/session/actions/505",
  );
  expect(actionPatches.length).toBeGreaterThanOrEqual(2);
  expect(actionPatches.every((request) => requestBody(request.body).championId === 99)).toBe(true);
  expect((await readHistory(page)).items.map((item) => item.message))
    .toContain("Champion automatically locked in: Lux.");
  await expect(page.locator(".automation-status")).toHaveText(/Champion sélectionné : Lux\./);
});

test("[DASH-15] Auto-Pick ignore une action dont l’actorCellId n’est pas celui du joueur local", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    configured: true,
    autoPick: true,
    phase: "ChampSelect",
    lcuState: {
      static_data_online: true,
      pickable_champion_ids: [86],
      session: champSelectSession([]),
    },
  });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#dashboard");
  await eventsConnected;

  const session = champSelectSession([[{
    actorCellId: 2,
    type: "pick",
    id: 506,
    isInProgress: true,
    completed: false,
    championId: 0,
  }]]);
  const requestOffset = app.lcuRequests.length;
  await app.configureLcuState({ session, pickable_champion_ids: [86] });
  await app.emitLcuEvent("/lol-champ-select/v1/session", session);
  await expect.poll(() => app.lcuRequests.slice(requestOffset).some((request) =>
    request.method === "GET" && request.path === "/lol-champ-select/v1/session",
  )).toBe(true);
  await app.waitForChampSelectRetryReady();

  const actionPatches = app.lcuRequests.slice(requestOffset).filter((request) =>
    request.method === "PATCH" && request.path === "/lol-champ-select/v1/session/actions/506",
  );
  expect(actionPatches).toEqual([]);
  expect((await app.readLcuState()).session.actions[0][0]).toMatchObject({
    actorCellId: 2,
    completed: false,
    championId: 0,
  });
  expect((await readHistory(page)).items.map((item) => item.message))
    .not.toContain("Champion automatically locked in: Garen.");
});

for (const scenario of [
  {
    name: "un champion configuré indisponible",
    queueId: 420,
    pickableChampionIds: [999],
    status: "Aucun champion configuré n’est disponible.",
  },
  {
    name: "une file sans prise en charge des presets",
    queueId: 450,
    pickableChampionIds: [86],
    status: "Presets désactivés pour ce mode de partie.",
  },
]) {
  test(`Auto-Pick explique ${scenario.name} sans modifier l’action LCU`, async ({ page }) => {
    const { app } = await setupApplication(page, {
      connected: true,
      configured: true,
      phase: "ChampSelect",
      lcuState: { static_data_online: true },
    });
    const eventsConnected = waitForRuntimeEvents(page);
    await page.goto("/#settings/automations");
    await eventsConnected;
    await enableAutomation(page, "Auto-Pick", "auto_pick_enabled");
    await page.goto("/#dashboard");

    const session = champSelectSession([[{
      actorCellId: 1,
      type: "pick",
      id: 503,
      isInProgress: true,
      completed: false,
      championId: 0,
    }]]);
    session.gameConfig.queueId = scenario.queueId;
    const requestOffset = app.lcuRequests.length;
    await app.configureLcuState({ session, pickable_champion_ids: scenario.pickableChampionIds });
    await app.emitLcuEvent("/lol-champ-select/v1/session", session);

    const status = page.locator(".automation-status");
    await expect(status).toContainText(scenario.status);
    expect(await readSettings(page)).toMatchObject({ auto_pick_enabled: true, selected_pick_1: "Garen" });
    expect(await readPresets(page)).toMatchObject({ slots: { pick_1: { champion: "Garen" } } });

    const state = await app.readLcuState();
    expect(state.session.myTeam[0].championId).toBe(0);
    expect(state.session.actions[0][0]).toMatchObject({ isInProgress: true, completed: false, championId: 0 });
    expect(app.lcuRequests.slice(requestOffset).filter((request) =>
      request.method === "PATCH" && request.path === "/lol-champ-select/v1/session/actions/503"
    )).toEqual([]);
    expect((await readHistory(page)).items.map((item) => item.message))
      .not.toContain("Champion automatically locked in: Garen.");
  });
}
