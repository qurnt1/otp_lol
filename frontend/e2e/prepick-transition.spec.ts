import type { Page } from "@playwright/test";

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

function requestBody(value: unknown): Record<string, any> {
  return value && typeof value === "object" ? value as Record<string, any> : {};
}

function isMutation(request: { method: string }) {
  return ["POST", "PUT", "PATCH", "DELETE"].includes(request.method);
}

async function enableAutomation(page: Page, label: string, key: string) {
  const toggle = page.getByRole("switch", { name: label });
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", "true");
  await expect.poll(async () => (await readSettings(page))[key]).toBe(true);
}

test("le ban attend la confirmation du pré-pick, puis le pick suit après le ban", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    configured: true,
    phase: "ChampSelect",
    settings: {
      auto_pick_enabled: false,
      auto_ban_enabled: false,
      auto_summoners_enabled: false,
      skin_automation_enabled: false,
    },
    lcuState: {
      pickable_champion_ids: [86],
      rune_pages: [targetRunePage, activeRunePage],
      current_rune_page: activeRunePage,
      session: champSelectSession([]),
    },
  });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#dashboard");
  await eventsConnected;

  await page.locator(".priority-card").first().click();
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await editor.locator(".champion-choice").click();
  const pickPicker = page.getByRole("dialog", { name: "Choisir un champion" });
  await pickPicker.getByRole("textbox", { name: "Rechercher un champion…" }).fill("Garen");
  const pickSave = page.waitForResponse((response) =>
    response.request().method() === "PUT" && new URL(response.url()).pathname === "/api/presets/pick_1",
  );
  await pickPicker.getByRole("option", { name: /Garen/ }).click();
  const pickSaveResponse = await pickSave;
  expect(pickSaveResponse.status()).toBe(200);
  expect(await pickSaveResponse.json()).toMatchObject({ slots: { pick_1: { champion: "Garen" } } });
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.champion).toBe("Garen");
  await editor.getByRole("button", { name: "Fermer" }).last().click();

  await page.locator(".ban-panel").click();
  const banPicker = page.getByRole("dialog", { name: "Champion à bannir" });
  await banPicker.getByRole("textbox", { name: "Rechercher un champion…" }).fill("Annie");
  await banPicker.getByRole("option", { name: /Annie/ }).click();
  await expect.poll(async () => (await readPresets(page)).selected_ban).toBe("Annie");
  await expect(banPicker).toBeHidden();

  await page.getByRole("link", { name: "Réglages", exact: true }).click();
  await expect(page).toHaveURL(/#settings\/general$/);
  const automationsSection = page.getByRole("button", { name: "Automatisations", exact: true });
  await automationsSection.click();
  await expect(page).toHaveURL(/#settings\/automations$/);
  await expect(automationsSection).toHaveAttribute("aria-current", "page");
  await enableAutomation(page, "Auto-Pick", "auto_pick_enabled");
  await enableAutomation(page, "Auto-Ban", "auto_ban_enabled");
  await enableAutomation(page, "Auto-Summs", "auto_summoners_enabled");
  await enableAutomation(page, "Automatisation des skins", "skin_automation_enabled");
  await page.goto("/#dashboard");

  expect(await readSettings(page)).toMatchObject({
    auto_pick_enabled: true,
    auto_ban_enabled: true,
    auto_summoners_enabled: true,
    skin_automation_enabled: true,
  });
  expect(await readPresets(page)).toMatchObject({
    selected_ban: "Annie",
    slots: {
      pick_1: {
        champion: "Garen",
        spell_1: "Flash",
        spell_2: "Ignite",
        skin_mode: "fixed",
        skin_id: 86013,
        rune_page_id: 401,
        rune_auto_apply: true,
      },
    },
  });

  const hoverActionId = 601;
  const banActionId = 602;
  const pickActionId = 603;
  const requestOffset = app.lcuRequests.length;
  const hoverOnlySession = champSelectSession([[
    { actorCellId: 1, type: "pick", id: hoverActionId, isInProgress: false, completed: false, championId: 0 },
    { actorCellId: 1, type: "ban", id: banActionId, isInProgress: true, completed: false, championId: 0 },
  ]]);
  await app.configureLcuState({ session: hoverOnlySession, pickable_champion_ids: [86] });
  const hoverEvent = await app.emitLcuEvent("/lol-champ-select/v1/session", hoverOnlySession);
  await app.waitForLcuEventCompletion(hoverEvent.id);
  await app.waitForChampSelectRetryReady();

  const hoverMutations = app.lcuRequests.slice(requestOffset).filter(isMutation).map(({ method, path, body }) => ({ method, path, body }));
  expect(hoverMutations).toEqual([{
    method: "PATCH",
    path: `/lol-champ-select/v1/session/actions/${hoverActionId}`,
    body: { championId: 86 },
  }]);
  const hoveredState = await app.readLcuState();
  expect(hoveredState.session.actions[0][0]).toMatchObject({ championId: 86, completed: false });
  expect(hoveredState.session.myTeam[0].championId).toBe(0);
  expect(hoveredState.session.actions[0][1]).toMatchObject({ championId: 0, completed: false });

  const confirmedPrepickSession = champSelectSession([[
    { actorCellId: 1, type: "pick", id: hoverActionId, isInProgress: false, completed: false, championId: 86 },
    { actorCellId: 1, type: "ban", id: banActionId, isInProgress: true, completed: false, championId: 0 },
  ]], 86);
  await app.configureLcuState({ session: confirmedPrepickSession, pickable_champion_ids: [86] });
  const confirmationEvent = await app.emitLcuEvent("/lol-champ-select/v1/session", confirmedPrepickSession);
  await app.waitForLcuEventCompletion(confirmationEvent.id);

  await expect.poll(() => app.lcuRequests.slice(requestOffset).some((request) =>
    request.method === "PATCH" && request.path === `/lol-champ-select/v1/session/actions/${banActionId}`
      && requestBody(request.body).completed === true && requestBody(request.body).championId === 1,
  )).toBe(true);
  await expect.poll(() => app.lcuRequests.slice(requestOffset).some((request) =>
    request.method === "PATCH" && request.path === "/lol-champ-select/v1/session/my-selection"
      && requestBody(request.body).spell1Id === 4 && requestBody(request.body).spell2Id === 14,
  )).toBe(true);
  await expect.poll(() => app.lcuRequests.slice(requestOffset).some((request) =>
    request.method === "PATCH" && request.path === "/lol-champ-select/v1/session/my-selection"
      && requestBody(request.body).selectedSkinId === 86013,
  )).toBe(true);
  await expect.poll(() => app.lcuRequests.slice(requestOffset).some((request) =>
    request.method === "PUT" && request.path === "/lol-perks/v1/pages/401"
      && requestBody(request.body).id === 401 && requestBody(request.body).current === true,
  )).toBe(true);

  const stateAfterBan = await app.readLcuState();
  expect(stateAfterBan.session.actions[0][1]).toMatchObject({ completed: true, championId: 1 });
  expect(stateAfterBan.session.bans.myTeamBans).toContain(1);
  expect(stateAfterBan.session.myTeam[0]).toMatchObject({
    championId: 86,
    spell1Id: 4,
    spell2Id: 14,
    selectedSkinId: 86013,
    selectedRunePageId: 401,
  });
  expect(stateAfterBan.current_rune_page.id).toBe(401);

  const pickSession = champSelectSession([[
    { actorCellId: 1, type: "pick", id: hoverActionId, isInProgress: false, completed: true, championId: 86 },
    { actorCellId: 1, type: "ban", id: banActionId, isInProgress: true, completed: true, championId: 1 },
    { actorCellId: 1, type: "pick", id: pickActionId, isInProgress: true, completed: false, championId: 0 },
  ]], 86);
  await app.configureLcuState({ session: pickSession, pickable_champion_ids: [86] });
  const pickEvent = await app.emitLcuEvent("/lol-champ-select/v1/session", pickSession);
  await app.waitForLcuEventCompletion(pickEvent.id);

  await expect.poll(() => app.lcuRequests.slice(requestOffset).some((request) =>
    request.method === "PATCH" && request.path === `/lol-champ-select/v1/session/actions/${pickActionId}`
      && requestBody(request.body).completed === true && requestBody(request.body).championId === 86,
  )).toBe(true);
  await expect.poll(async () => {
    const state = await app.readLcuState();
    const player = state.session.myTeam[0];
    return {
      actionLocked: state.session.actions[0][2].completed,
      championId: player.championId,
      spell1Id: player.spell1Id,
      spell2Id: player.spell2Id,
      skinId: player.selectedSkinId,
      runePageId: player.selectedRunePageId,
      activeRunePageId: state.current_rune_page.id,
    };
  }).toEqual({
    actionLocked: true,
    championId: 86,
    spell1Id: 4,
    spell2Id: 14,
    skinId: 86013,
    runePageId: 401,
    activeRunePageId: 401,
  });

  const historyMessages = (await readHistory(page)).items.map((item) => item.message);
  expect(historyMessages).toContain("Pre-pick sent for Garen.");
  expect(historyMessages).toContain("Automatic ban confirmed on Annie.");
  expect(historyMessages).toContain("Champion automatically locked in: Garen.");
  expect(historyMessages).toContain("Automatic summs applied: Flash + Ignite.");
  expect(historyMessages).toContain("Skin applied automatically: God-King Garen.");
  expect(historyMessages).toContain('Rune page applied: "E2E Top" (id=401).');
});
