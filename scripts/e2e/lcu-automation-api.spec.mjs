import { expect, test } from "../../frontend/node_modules/@playwright/test/index.mjs";
import { startOtpApp } from "./appServer.mjs";

const actionPath = "/lol-champ-select/v1/session/actions/501";
const runeTarget = {
  id: 401,
  name: "E2E Target",
  primaryStyleId: 8000,
  subStyleId: 8100,
  selectedPerkIds: [8005, 8008, 9101, 8014, 8106, 8120, 5008, 5008, 5011],
  current: false,
  isValid: true,
};
const runeCurrent = { ...runeTarget, id: 402, name: "E2E Current", current: true };

function sameOriginHeaders(app) {
  return { Origin: new URL(app.baseURL).origin };
}

function pickSession() {
  return {
    gameConfig: { queueId: 420, gameMode: "CLASSIC" },
    localPlayerCellId: 1,
    myTeam: [{
      cellId: 1,
      summonerId: 24680135,
      assignedPosition: "TOP",
      championId: 0,
      spell1Id: 0,
      spell2Id: 0,
      selectedRunePageId: runeCurrent.id,
      selectedSkinId: 0,
    }],
    actions: [[{
      actorCellId: 1,
      type: "pick",
      id: 501,
      isInProgress: true,
      completed: false,
      championId: 0,
    }]],
    bans: { myTeamBans: [], theirTeamBans: [] },
  };
}

async function expectConnected(app, request) {
  await expect.poll(async () => {
    const response = await request.get(`${app.baseURL}/api/health`);
    return (await response.json()).lcu_connected;
  }).toBe(true);
  await app.waitForWebSocketSubscription();
}

function captureRuntimeEvents(page) {
  const events = [];
  page.on("websocket", (socket) => {
    if (new URL(socket.url()).pathname !== "/api/events") return;
    socket.on("framereceived", ({ payload }) => {
      try {
        events.push(JSON.parse(typeof payload === "string" ? payload : payload.toString()));
      } catch {
        // Ignore non-JSON WebSocket frames.
      }
    });
  });
  return events;
}

async function enableAutoPick(app, request) {
  const headers = sameOriginHeaders(app);
  const reset = await request.post(`${app.baseURL}/api/presets/reset`, { headers });
  expect(reset.status()).toBe(200);
  const response = await request.patch(`${app.baseURL}/api/settings`, {
    headers,
    data: {
      presets_enabled: true,
      auto_pick_enabled: true,
      auto_summoners_enabled: false,
      skin_automation_enabled: false,
    },
  });
  expect(response.status()).toBe(200);
}

async function activatePick(app, request, pickableIds, state = {}) {
  const session = state.session ?? pickSession();
  await app.configureLcuState({
    static_data_online: true,
    pickable_champion_ids: pickableIds,
    rune_pages: [runeTarget, runeCurrent],
    current_rune_page: runeCurrent,
    phase: "ChampSelect",
    ...state,
    session,
  });
  await app.emitLcuEvent("/lol-gameflow/v1/gameflow-phase", "ChampSelect");
  await expect.poll(async () => {
    const response = await request.get(`${app.baseURL}/api/runtime`);
    return (await response.json()).phase;
  }).toBe("ChampSelect");
  await app.emitLcuEvent("/lol-champ-select/v1/session", session);
}

async function waitForChampion(app, request, championId) {
  await expect.poll(async () => {
    const state = await app.readLcuState();
    const player = state.session.myTeam.find((entry) => entry.cellId === state.session.localPlayerCellId);
    return {
      championId: player?.championId,
      completed: state.session.actions[0][0].completed,
    };
  }).toEqual({ championId, completed: true });
  const runtime = await request.get(`${app.baseURL}/api/runtime`);
  expect(runtime.status()).toBe(200);
}

test("a rejected first champion lock falls through to the next configured pick", async ({ page }) => {
  const app = await startOtpApp();
  try {
    await expectConnected(app, page.request);
    await enableAutoPick(app, page.request);
    await app.configureLcuState({
      mutation_responses: { [`PATCH ${actionPath}`]: [503] },
    });
    await activatePick(app, page.request, [86, 99]);
    await waitForChampion(app, page.request, 99);

    const attempts = app.lcuRequests
      .filter((request) => request.method === "PATCH" && request.path === actionPath)
      .map((request) => ({
        championId: request.body?.championId,
        completed: request.body?.completed ?? false,
      }));
    expect(attempts).toEqual([
      { championId: 86, completed: false },
      { championId: 99, completed: false },
      { championId: 99, completed: true },
    ]);

    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/history?limit=250`);
      const history = await response.json();
      return history.items.map((entry) => entry.message);
    }).toContain("Champion automatically locked in: Lux.");
    const historyResponse = await page.request.get(`${app.baseURL}/api/history?limit=250`);
    const history = await historyResponse.json();
    expect(history.items.map((entry) => entry.message)).not.toContain("Champion automatically locked in: Garen.");
  } finally {
    await app.stop();
  }
});

test("Auto-Pick leaves the active action untouched when no configured champion is pickable", async ({ page }) => {
  const app = await startOtpApp();
  try {
    await expectConnected(app, page.request);
    await enableAutoPick(app, page.request);
    const settings = await page.request.patch(`${app.baseURL}/api/settings`, {
      headers: sameOriginHeaders(app),
      data: { selected_pick_1: "Garen", selected_pick_2: "", selected_pick_3: "" },
    });
    expect(settings.status()).toBe(200);
    const [savedSettingsResponse, savedPresetsResponse] = await Promise.all([
      page.request.get(`${app.baseURL}/api/settings`),
      page.request.get(`${app.baseURL}/api/presets`),
    ]);
    const savedSettings = await savedSettingsResponse.json();
    const savedPresets = await savedPresetsResponse.json();
    expect(savedSettings).toMatchObject({
      presets_enabled: true,
      auto_pick_enabled: true,
      selected_pick_1: "Garen",
      selected_pick_2: "",
      selected_pick_3: "",
    });
    expect(savedPresets).toMatchObject({
      presets_enabled: true,
      slots: {
        pick_1: { champion: "Garen" },
        pick_2: { champion: "" },
        pick_3: { champion: "" },
      },
    });
    const runtimeEvents = captureRuntimeEvents(page);
    await page.goto(app.baseURL, { waitUntil: "domcontentloaded" });
    await expect.poll(() => runtimeEvents.some((event) => event.type === "runtime_snapshot")).toBe(true);
    const eventStart = runtimeEvents.length;

    await activatePick(app, page.request, [99]);
    await expect.poll(() => runtimeEvents.slice(eventStart).some((event) => (
      event.type === "status" && event.data?.action === "no_champion_available"
    ))).toBe(true);

    const state = await app.readLcuState();
    expect(state.session.myTeam[0].championId).toBe(0);
    expect(state.session.actions[0][0]).toMatchObject({ isInProgress: true, completed: false });
    expect(app.lcuRequests.filter((request) => request.method === "PATCH" && request.path === actionPath)).toEqual([]);
    const historyResponse = await page.request.get(`${app.baseURL}/api/history?limit=250`);
    const history = await historyResponse.json();
    expect(history.items.map((entry) => entry.message)).not.toContain("Champion automatically locked in: Garen.");
  } finally {
    await app.stop();
  }
});

test("Auto-Pick does not run in a queue where presets are unsupported", async ({ page }) => {
  const app = await startOtpApp();
  try {
    await expectConnected(app, page.request);
    await enableAutoPick(app, page.request);
    const selectedPickResponse = await page.request.patch(`${app.baseURL}/api/settings`, {
      headers: sameOriginHeaders(app),
      data: { selected_pick_1: "Garen", selected_pick_2: "", selected_pick_3: "" },
    });
    expect(selectedPickResponse.status()).toBe(200);
    const [settingsResponse, presetsResponse] = await Promise.all([
      page.request.get(`${app.baseURL}/api/settings`),
      page.request.get(`${app.baseURL}/api/presets`),
    ]);
    expect(await settingsResponse.json()).toMatchObject({
      presets_enabled: true,
      auto_pick_enabled: true,
      selected_pick_1: "Garen",
      selected_pick_2: "",
      selected_pick_3: "",
    });
    expect(await presetsResponse.json()).toMatchObject({
      presets_enabled: true,
      slots: {
        pick_1: { champion: "Garen" },
        pick_2: { champion: "" },
        pick_3: { champion: "" },
      },
    });
    const runtimeEvents = captureRuntimeEvents(page);
    await page.goto(app.baseURL, { waitUntil: "domcontentloaded" });
    await expect.poll(() => runtimeEvents.some((event) => event.type === "runtime_snapshot")).toBe(true);
    const eventStart = runtimeEvents.length;
    const unsupportedQueueSession = pickSession();
    unsupportedQueueSession.gameConfig.queueId = 450;

    await activatePick(app, page.request, [86], { session: unsupportedQueueSession });
    await expect.poll(() => runtimeEvents.slice(eventStart).some((event) => (
      event.type === "status" && event.data?.action === "presets_disabled"
    ))).toBe(true);

    const state = await app.readLcuState();
    expect(state.session.gameConfig.queueId).toBe(450);
    expect(state.session.myTeam[0].championId).toBe(0);
    expect(state.session.actions[0][0]).toMatchObject({ isInProgress: true, completed: false });
    expect(app.lcuRequests.filter((request) => request.method === "PATCH" && request.path === actionPath)).toEqual([]);
  } finally {
    await app.stop();
  }
});

for (const scenario of [
  { name: "do-nothing rune choice", rune_page_id: 0, rune_auto_apply: true },
  { name: "disabled per-slot rune automation", rune_page_id: runeTarget.id, rune_auto_apply: false },
]) {
  test(`Auto-Pick does not change the active rune page for ${scenario.name}`, async ({ page }) => {
    const app = await startOtpApp();
    try {
      await expectConnected(app, page.request);
      await enableAutoPick(app, page.request);
      const preset = await page.request.put(`${app.baseURL}/api/presets/pick_1`, {
        headers: sameOriginHeaders(app),
        data: {
          rune_page_id: scenario.rune_page_id,
          rune_page_name: scenario.rune_page_id ? runeTarget.name : "",
          rune_keystone_id: scenario.rune_page_id ? 8005 : 0,
          rune_auto_apply: scenario.rune_auto_apply,
        },
      });
      expect(preset.status()).toBe(200);

      await activatePick(app, page.request, [86]);
      await waitForChampion(app, page.request, 86);
      await page.waitForTimeout(300);

      const runeMutations = app.lcuRequests.filter((request) => (
        request.method === "PUT" && request.path.startsWith("/lol-perks/v1/pages/")
      ));
      expect(runeMutations).toEqual([]);
      const state = await app.readLcuState();
      expect(state.current_rune_page.id).toBe(runeCurrent.id);
      expect(state.session.myTeam[0].selectedRunePageId).toBe(runeCurrent.id);
    } finally {
      await app.stop();
    }
  });
}
