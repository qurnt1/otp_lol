import { expect, test } from "../../frontend/node_modules/@playwright/test/index.mjs";
import { mkdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { startOtpApp } from "./appServer.mjs";

const slots = ["pick_1", "pick_2", "pick_3"];
const actionPath = "/lol-champ-select/v1/session/actions/501";
const fixtures = {
  pick_1: {
    champion: "Garen",
    spell_1: "Ghost",
    spell_2: "Flash",
    skin_mode: "fixed",
    skin_id: 86013,
    skin_name: "God-King Garen",
    skin_num: 13,
    rune_page_id: 401,
    rune_page_name: "Garen Precision",
    rune_auto_apply: true,
    rune_keystone_id: 8005,
    rune_keystone_path: "8000/8005.png",
    rune_sub_style_icon_path: "8100.png",
  },
  pick_2: {
    champion: "Lux",
    spell_1: "Heal",
    spell_2: "Teleport",
    skin_mode: "fixed",
    skin_id: 99010,
    skin_name: "Battle Academia Lux",
    skin_num: 10,
    rune_page_id: 402,
    rune_page_name: "Lux Sorcery",
    rune_auto_apply: false,
    rune_keystone_id: 8229,
    rune_keystone_path: "8200/8229.png",
    rune_sub_style_icon_path: "8300.png",
  },
  pick_3: {
    champion: "Ashe",
    spell_1: "Barrier",
    spell_2: "Cleanse",
    skin_mode: "fixed",
    skin_id: 22004,
    skin_name: "Queen Ashe",
    skin_num: 4,
    rune_page_id: 403,
    rune_page_name: "Ashe Precision",
    rune_auto_apply: true,
    rune_keystone_id: 8008,
    rune_keystone_path: "8000/8008.png",
    rune_sub_style_icon_path: "8300.png",
  },
};

function sameOriginHeaders(app) {
  return { Origin: new URL(app.baseURL).origin };
}

async function getPresets(app, request) {
  const response = await request.get(`${app.baseURL}/api/presets`);
  expect(response.status()).toBe(200);
  return response.json();
}

async function seedPresets(app, request) {
  for (const slot of slots) {
    const response = await request.put(`${app.baseURL}/api/presets/${slot}`, {
      headers: sameOriginHeaders(app),
      data: fixtures[slot],
    });
    expect(response.status(), `seed ${slot}`).toBe(200);
  }
  return getPresets(app, request);
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
      selectedRunePageId: 0,
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

test("preset reorder moves complete configurations, updates pick priority, and survives restart", async ({ page }) => {
  let app = await startOtpApp();
  try {
    await app.waitForWebSocketSubscription();
    const initial = await seedPresets(app, page.request);
    expect(initial.slots).toMatchObject(fixtures);

    const response = await page.request.put(`${app.baseURL}/api/presets/order`, {
      headers: sameOriginHeaders(app),
      // The source slots fill destinations pick_1, pick_2, pick_3 in this order.
      data: { order: ["pick_2", "pick_1", "pick_3"] },
    });
    expect(response.status()).toBe(200);
    const reordered = await response.json();
    expect(reordered).toMatchObject({
      slots: {
        pick_1: fixtures.pick_2,
        pick_2: fixtures.pick_1,
        pick_3: fixtures.pick_3,
      },
    });

    const settingsResponse = await page.request.get(`${app.baseURL}/api/settings`);
    expect(settingsResponse.status()).toBe(200);
    expect(await settingsResponse.json()).toMatchObject({
      selected_pick_1: "Lux",
      selected_pick_2: "Garen",
      selected_pick_3: "Ashe",
    });

    const stateDir = app.stateDir;
    await app.stop({ retainState: true });
    app = null;
    app = await startOtpApp({ stateDir });
    await app.waitForWebSocketSubscription();
    expect(await getPresets(app, page.request)).toMatchObject({
      slots: {
        pick_1: fixtures.pick_2,
        pick_2: fixtures.pick_1,
        pick_3: fixtures.pick_3,
      },
    });
    const restartedSettings = await page.request.get(`${app.baseURL}/api/settings`);
    expect(await restartedSettings.json()).toMatchObject({
      selected_pick_1: "Lux",
      selected_pick_2: "Garen",
      selected_pick_3: "Ashe",
    });

    const enabledAutomation = await page.request.patch(`${app.baseURL}/api/settings`, {
      headers: sameOriginHeaders(app),
      data: {
        presets_enabled: true,
        auto_pick_enabled: true,
        auto_summoners_enabled: false,
        skin_automation_enabled: false,
      },
    });
    expect(enabledAutomation.status()).toBe(200);
    const session = pickSession();
    await app.configureLcuState({
      phase: "ChampSelect",
      static_data_online: true,
      pickable_champion_ids: [86, 99],
      session,
    });
    await app.emitLcuEvent("/lol-gameflow/v1/gameflow-phase", "ChampSelect");
    await expect.poll(async () => {
      const runtime = await page.request.get(`${app.baseURL}/api/runtime`);
      return (await runtime.json()).phase;
    }).toBe("ChampSelect");
    await app.emitLcuEvent("/lol-champ-select/v1/session", session);
    const firstPickAttempt = await app.waitForLcuRequest("PATCH", actionPath);
    expect(firstPickAttempt.body).toMatchObject({ championId: 99 });
    await expect.poll(async () => {
      const state = await app.readLcuState();
      return state.session.myTeam[0].championId;
    }).toBe(99);
  } finally {
    if (app) await app.stop();
  }
});

test("invalid preset orders are rejected without changing memory or persisted settings", async ({ page }) => {
  const app = await startOtpApp();
  try {
    await app.waitForWebSocketSubscription();
    await seedPresets(app, page.request);
    const settingsPath = path.join(app.appDataDir, "OTP LOL", "parameters.toml");
    const beforePresets = await getPresets(app, page.request);
    const beforeBytes = await readFile(settingsPath);
    const invalidOrders = [
      ["pick_1", "pick_1", "pick_3"],
      ["pick_1", "pick_2"],
      ["pick_1", "pick_2", "pick_3", "pick_1"],
      ["pick_1", "pick_2", "unknown"],
    ];

    for (const order of invalidOrders) {
      const response = await page.request.put(`${app.baseURL}/api/presets/order`, {
        headers: sameOriginHeaders(app),
        data: { order },
      });
      expect(response.status(), JSON.stringify(order)).toBe(422);
      expect(await getPresets(app, page.request), JSON.stringify(order)).toEqual(beforePresets);
      expect(await readFile(settingsPath), JSON.stringify(order)).toEqual(beforeBytes);
    }
  } finally {
    await app.stop();
  }
});

test("a failed settings-file replacement returns 500 and keeps preset order unchanged in memory and on disk", async ({ page }) => {
  const app = await startOtpApp();
  const settingsPath = path.join(app.appDataDir, "OTP LOL", "parameters.toml");
  const heldSettingsPath = `${settingsPath}.preset-order-held`;
  let originalFileHeld = false;

  try {
    await app.waitForWebSocketSubscription();
    await seedPresets(app, page.request);
    const origin = new URL(app.baseURL).origin;
    const beforePresets = await getPresets(app, page.request);
    const beforeSettingsResponse = await page.request.get(`${app.baseURL}/api/settings`);
    expect(beforeSettingsResponse.status()).toBe(200);
    const beforeSettings = await beforeSettingsResponse.json();
    const originalBytes = await readFile(settingsPath);

    // Replacing a directory with the atomic TOML temp file fails on Windows and POSIX.
    await rename(settingsPath, heldSettingsPath);
    originalFileHeld = true;
    await mkdir(settingsPath);
    const occupiedBytes = Buffer.from("prevent replacing this directory");
    await writeFile(path.join(settingsPath, "occupied"), occupiedBytes);

    const response = await page.request.put(`${app.baseURL}/api/presets/order`, {
      headers: sameOriginHeaders(app),
      data: { order: ["pick_2", "pick_1", "pick_3"] },
    });
    expect(response.status()).toBe(500);
    expect(await getPresets(app, page.request)).toEqual(beforePresets);

    const afterSettingsResponse = await page.request.get(`${app.baseURL}/api/settings`);
    expect(afterSettingsResponse.status()).toBe(200);
    expect(await afterSettingsResponse.json()).toEqual(beforeSettings);
    expect(await readFile(heldSettingsPath)).toEqual(originalBytes);
    expect(await readFile(path.join(settingsPath, "occupied"))).toEqual(occupiedBytes);
  } finally {
    if (originalFileHeld) {
      await rm(settingsPath, { recursive: true, force: true });
      await rename(heldSettingsPath, settingsPath);
    }
    await app.stop();
  }
});

test("preset reorder preserves legacy duplicate summoner spells", async ({ page }) => {
  let app = await startOtpApp({
    settingsToml: [
      "config_schema_version = 6",
      'selected_pick_1 = "Garen"',
      'selected_pick_2 = "Lux"',
      'selected_pick_3 = "Ashe"',
      'selected_ban = "Teemo"',
      "[pick_slots.pick_1]",
      'spell_1 = "Flash"',
      'spell_2 = "Flash"',
    ].join("\n"),
  });
  try {
    await app.waitForWebSocketSubscription();
    const before = await getPresets(app, page.request);
    expect(before.slots.pick_1).toMatchObject({
      champion: "Garen",
      spell_1: "Flash",
      spell_2: "Flash",
    });

    const response = await page.request.put(`${app.baseURL}/api/presets/order`, {
      headers: sameOriginHeaders(app),
      data: { order: ["pick_2", "pick_1", "pick_3"] },
    });
    expect(response.status()).toBe(200);
    expect(await response.json()).toMatchObject({
      slots: {
        pick_1: { champion: "Lux" },
        pick_2: { champion: "Garen", spell_1: "Flash", spell_2: "Flash" },
        pick_3: { champion: "Ashe" },
      },
    });
    expect(await getPresets(app, page.request)).toMatchObject({
      slots: {
        pick_2: { champion: "Garen", spell_1: "Flash", spell_2: "Flash" },
      },
    });

    const stateDir = app.stateDir;
    await app.stop({ retainState: true });
    app = await startOtpApp({ stateDir });
    await app.waitForWebSocketSubscription();
    expect(await getPresets(app, page.request)).toMatchObject({
      slots: {
        pick_2: { champion: "Garen", spell_1: "Flash", spell_2: "Flash" },
      },
    });
  } finally {
    await app.stop();
  }
});
