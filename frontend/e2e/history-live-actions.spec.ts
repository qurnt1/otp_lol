import { expect, readHistory, readSettings, setupApplication, test, waitForRuntimeEvents } from "./helpers";

const targetRunePage = {
  id: 401,
  name: "E2E Top",
  primaryStyleId: 8000,
  subStyleId: 8100,
  selectedPerkIds: [8005, 8008, 9101, 8014, 8106, 8120, 5008, 5008, 5011],
  current: false,
  isValid: true,
};
const activeRunePage = { ...targetRunePage, id: 402, name: "Current Page", current: true };

function session(championId = 0, actions: unknown[] = [], selectedRunePageId = 402) {
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
      selectedRunePageId,
      selectedSkinId: 0,
    }],
    actions,
    bans: { myTeamBans: [], theirTeamBans: [] },
  };
}

async function mountEmptyHistory(page: import("@playwright/test").Page) {
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#history");
  await eventsConnected;
  await expect(page.getByText("Aucun événement pour le moment.")).toBeVisible();
}

async function expectLiveHistoryEntry(page: import("@playwright/test").Page, message: string) {
  await expect.poll(async () => (await readHistory(page)).items.some((item) => item.message === message)).toBe(true);
  await expect(page).toHaveURL(/#history$/);
  await expect(page.getByText(message, { exact: true })).toBeVisible({ timeout: 4_000 });
}

test("History mounted receives the automatic skin entry without navigation", async ({ page }) => {
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
      session: session(),
    },
  });
  const origin = new URL(app.baseURL).origin;
  const presetResponse = await page.request.put(new URL("/api/presets/pick_1", app.baseURL).href, {
    data: { rune_auto_apply: false },
    headers: { Origin: origin },
  });
  expect(presetResponse.ok()).toBe(true);
  await mountEmptyHistory(page);

  const champSelect = session(86);
  await app.configureLcuState({ session: champSelect, pickable_champion_ids: [86] });
  await app.emitLcuEvent("/lol-champ-select/v1/session", champSelect);

  await expectLiveHistoryEntry(page, "Skin applied automatically: God-King Garen.");
});

test("History mounted receives the automatic rune entry without navigation", async ({ page }) => {
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
      session: session(),
    },
  });
  await mountEmptyHistory(page);

  const champSelect = session(86);
  await app.configureLcuState({
    session: champSelect,
    pickable_champion_ids: [86],
    rune_pages: [targetRunePage, activeRunePage],
    current_rune_page: activeRunePage,
  });
  await app.emitLcuEvent("/lol-champ-select/v1/session", champSelect);

  await expectLiveHistoryEntry(page, 'Rune page applied: "E2E Top" (id=401).');
});

test("History mounted receives the automatic pre-pick entry without navigation", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    configured: true,
    autoPick: true,
    phase: "ChampSelect",
    settings: { auto_summoners_enabled: false, skin_automation_enabled: false },
    lcuState: { static_data_online: true, pickable_champion_ids: [86], session: session() },
  });
  await mountEmptyHistory(page);

  const champSelect = session(0, [[{
    actorCellId: 1,
    type: "pick",
    id: 701,
    isInProgress: false,
    completed: false,
    championId: 0,
  }]]);
  await app.configureLcuState({ session: champSelect, pickable_champion_ids: [86] });
  await app.emitLcuEvent("/lol-champ-select/v1/session", champSelect);
  await app.waitForLcuRequest("PATCH", "/lol-champ-select/v1/session/actions/701");

  await expectLiveHistoryEntry(page, "Pre-pick sent for Garen.");
});

test("History mounted receives the Auto Play Again entry without navigation", async ({ page }) => {
  const { app } = await setupApplication(page, { connected: true, phase: "Lobby" });
  const eventsConnected = waitForRuntimeEvents(page);
  await page.goto("/#settings/automations");
  await eventsConnected;
  const toggle = page.getByRole("switch", { name: "Auto Play Again" });
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", "true");
  await expect.poll(async () => (await readSettings(page)).auto_play_again_enabled).toBe(true);
  await page.goto("/#history");
  await expect(page.getByText("Aucun événement pour le moment.")).toBeVisible();

  await app.emitLcuEvent("/lol-gameflow/v1/gameflow-phase", "WaitingForStats");
  await app.waitForLcuRequest("POST", "/lol-lobby/v2/play-again");

  await expectLiveHistoryEntry(page, "Automatically returned to lobby after the game.");
});
