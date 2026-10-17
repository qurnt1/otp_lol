import { connect } from "node:net";
import { randomBytes } from "node:crypto";
import { lstat, mkdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { expect, test } from "../../frontend/node_modules/@playwright/test/index.mjs";
import { startOtpApp } from "./appServer.mjs";

async function readSettings(app, request) {
  const response = await request.get(`${app.baseURL}/api/settings`);
  expect(response.status()).toBe(200);
  return response.json();
}

async function waitForDetectedAccount(app, request) {
  await app.waitForLcuRequest("GET", "/lol-chat/v1/me");
  await expect.poll(async () => (await readSettings(app, request)).auto_detected_account_valid).toBe(true);
}

function webSocketUpgradeStatus(baseURL, origin) {
  const url = new URL(baseURL);
  const websocketHandshakeKey = randomBytes(16).toString("base64");
  return new Promise((resolve, reject) => {
    const socket = connect({ host: url.hostname, port: Number(url.port) });
    let response = "";
    let settled = false;
    const timer = setTimeout(() => {
      finish(new Error("The FastAPI WebSocket handshake did not return an HTTP response."));
    }, 5_000);

    function finish(error, statusLine) {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      socket.destroy();
      if (error) reject(error);
      else resolve(statusLine);
    }

    socket.once("error", (error) => finish(error));
    socket.once("connect", () => {
      socket.write([
        "GET /api/events HTTP/1.1",
        `Host: ${url.host}`,
        "Upgrade: websocket",
        "Connection: Upgrade",
        `Sec-WebSocket-Key: ${websocketHandshakeKey}`,
        "Sec-WebSocket-Version: 13",
        `Origin: ${origin}`,
        "",
        "",
      ].join("\r\n"));
    });
    socket.on("data", (chunk) => {
      response += chunk.toString("latin1");
      if (response.includes("\r\n\r\n")) {
        finish(null, response.split("\r\n", 1)[0]);
      }
    });
  });
}

test("settings API rejects unknown, null, invalid and colliding values without changing configuration", async ({ page }) => {
  const app = await startOtpApp();
  try {
    const origin = new URL(app.baseURL).origin;
    await waitForDetectedAccount(app, page.request);
    const before = await readSettings(app, page.request);
    const invalidPatches = [
      { unknown_setting: true },
      { theme: null },
      { window_width: 100 },
      { manual_region: "not-a-region" },
      { hotkey_toggle_window: before.hotkey_open_site },
    ];

    for (const patch of invalidPatches) {
      const response = await page.request.patch(`${app.baseURL}/api/settings`, {
        headers: { Origin: origin },
        data: patch,
      });
      expect(response.status(), JSON.stringify(patch)).toBe(422);
      expect(await readSettings(app, page.request), JSON.stringify(patch)).toEqual(before);
    }

    const nullPreset = await page.request.put(`${app.baseURL}/api/presets/pick_1`, {
      headers: { Origin: origin },
      data: { rune_auto_apply: null },
    });
    expect(nullPreset.status()).toBe(422);
    expect(await readSettings(app, page.request)).toEqual(before);
  } finally {
    await app.stop();
  }
});

test("startup migrates a legacy JSON-only profile to current TOML and keeps an exact backup", async ({ page }) => {
  const legacySettings = {
    config_version: "11.1",
    config_schema_version: 3,
    auto_accept_enabled: true,
    auto_pick_enabled: true,
    presets_enabled: true,
    selected_pick_1: "Ahri",
    selected_pick_2: "Lux",
    selected_pick_3: "Ashe",
    selected_ban: "Teemo",
    theme: "flatly",
    summoner_name_auto_detect: false,
    manual_summoner_name: "Legacy Player#1234",
    region: "na",
    preferred_stats_site: "dpm",
    hotkey_toggle_window: "alt+shift+c",
    hotkey_open_site: "shift+f8",
    pick_slots: {
      pick_1: {
        spell_1: "Flash",
        spell_2: "Ignite",
        skin_mode: "fixed",
        skin_id: 103005,
        skin_name: "Midnight Ahri",
        skin_num: 5,
        rune_page_id: 17,
        rune_page_name: "Legacy Runes",
      },
    },
  };
  const legacyJson = `${JSON.stringify(legacySettings, null, 2)}\n`;
  let app = await startOtpApp({ legacySettingsJson: legacyJson });

  try {
    const legacyPath = path.join(app.appDataDir, "OTP LOL", "parameters.json");
    const tomlPath = path.join(app.appDataDir, "OTP LOL", "parameters.toml");
    const settings = await readSettings(app, page.request);
    expect(settings).toMatchObject({
      config_schema_version: 6,
      auto_accept_enabled: true,
      auto_pick_enabled: true,
      presets_enabled: true,
      selected_pick_1: "Ahri",
      selected_pick_2: "Lux",
      selected_pick_3: "Ashe",
      selected_ban: "Teemo",
      theme: "flatly",
      summoner_name_auto_detect: false,
      manual_summoner_name: "Legacy Player#1234",
      manual_region: "na",
      preferred_stats_site: "dpm",
      hotkey_toggle_window: "alt+shift+c",
      hotkey_open_site: "shift+f8",
      pick_slots: {
        pick_1: {
          spell_1: "Flash",
          spell_2: "Ignite",
          skin_mode: "fixed",
          skin_id: 103005,
          skin_name: "Midnight Ahri",
          skin_num: 5,
          rune_page_id: 17,
          rune_page_name: "Legacy Runes",
        },
      },
    });

    const migratedToml = await readFile(tomlPath, "utf8");
    expect(migratedToml).toContain("config_schema_version = 6");
    expect(migratedToml).toContain('manual_region = "na"');
    expect(await readFile(`${legacyPath}.bak`, "utf8")).toBe(legacyJson);
    expect(await readFile(legacyPath, "utf8").catch((error) => error.code)).toBe("ENOENT");
    expect(await lstat(path.join(app.appDataDir, "MainLoL")).catch((error) => error.code)).toBe("ENOENT");

    const stateDir = app.stateDir;
    await app.stop({ retainState: true });
    app = null;
    app = await startOtpApp({ stateDir });
    expect(await readSettings(app, page.request)).toMatchObject({
      config_schema_version: 6,
      selected_pick_1: "Ahri",
      manual_summoner_name: "Legacy Player#1234",
      theme: "flatly",
      pick_slots: {
        pick_1: { spell_1: "Flash", spell_2: "Ignite", rune_page_id: 17 },
      },
    });
    expect(await readFile(`${legacyPath}.bak`, "utf8")).toBe(legacyJson);
  } finally {
    if (app) await app.stop();
  }
});

test("startup migrates an isolated MainLoL settings profile and keeps its backup across restart", async ({ page }) => {
  const legacySettings = {
    config_version: "11.1",
    config_schema_version: 3,
    manual_summoner_name: "MainLoL Legacy#SAFE",
    manual_region: "na",
    region: "euw",
  };
  const legacyJson = `${JSON.stringify(legacySettings, null, 2)}\n`;
  let app = await startOtpApp({ legacySettingsJson: legacyJson, legacySettingsFolder: "MainLoL" });

  try {
    const legacyPath = path.join(app.appDataDir, "MainLoL", "parameters.json");
    const legacyBackupPath = `${legacyPath}.bak`;
    const tomlPath = path.join(app.appDataDir, "OTP LOL", "parameters.toml");
    expect(app.pathIsolation.appDataPathNames).toContain("legacyMainParameters");
    expect(app.pathIsolation.resolvedPaths.appData.legacyMainParameters).toBe(legacyPath);
    expect(await readSettings(app, page.request)).toMatchObject({
      manual_summoner_name: "MainLoL Legacy#SAFE",
      manual_region: "na",
    });
    expect(await readFile(legacyBackupPath, "utf8")).toBe(legacyJson);
    expect(await readFile(legacyPath, "utf8").catch((error) => error.code)).toBe("ENOENT");
    expect(await readFile(tomlPath, "utf8")).toContain('manual_summoner_name = "MainLoL Legacy#SAFE"');

    const stateDir = app.stateDir;
    await app.stop({ retainState: true });
    app = null;
    app = await startOtpApp({ stateDir });
    expect(await readSettings(app, page.request)).toMatchObject({
      manual_summoner_name: "MainLoL Legacy#SAFE",
      manual_region: "na",
    });
    expect(await readFile(legacyBackupPath, "utf8")).toBe(legacyJson);
  } finally {
    if (app) await app.stop();
  }
});

test("startup prefers OTP LOL JSON when both current and MainLoL profiles exist", async ({ page }) => {
  const currentSettings = {
    config_schema_version: 3,
    manual_summoner_name: "Current OTP Profile#SAFE",
  };
  const oldSettings = {
    config_schema_version: 3,
    manual_summoner_name: "Old MainLoL Profile#SAFE",
  };
  const currentJson = `${JSON.stringify(currentSettings, null, 2)}\n`;
  const oldJson = `${JSON.stringify(oldSettings, null, 2)}\n`;
  const app = await startOtpApp({
    legacySettingsJson: currentJson,
    legacyMainSettingsJson: oldJson,
  });

  try {
    expect(await readSettings(app, page.request)).toMatchObject({
      manual_summoner_name: "Current OTP Profile#SAFE",
    });
    expect(await readFile(path.join(app.appDataDir, "OTP LOL", "parameters.json.bak"), "utf8")).toBe(currentJson);
    expect(await readFile(path.join(app.appDataDir, "MainLoL", "parameters.json"), "utf8")).toBe(oldJson);
    expect(await readFile(path.join(app.appDataDir, "MainLoL", "parameters.json.bak")).catch((error) => error.code)).toBe("ENOENT");
  } finally {
    await app.stop();
  }
});

test("startup keeps TOML settings when both legacy JSON profiles also exist", async ({ page }) => {
  const settingsToml = [
    "config_schema_version = 6",
    'manual_summoner_name = "Current TOML Profile#SAFE"',
    'manual_region = "na"',
    "",
  ].join("\n");
  const currentJson = `${JSON.stringify({
    config_schema_version: 3,
    manual_summoner_name: "Stale OTP JSON#SAFE",
  }, null, 2)}\n`;
  const oldJson = `${JSON.stringify({
    config_schema_version: 3,
    manual_summoner_name: "Old MainLoL JSON#SAFE",
  }, null, 2)}\n`;
  const app = await startOtpApp({
    settingsToml,
    legacySettingsJson: currentJson,
    legacyMainSettingsJson: oldJson,
  });

  try {
    expect(await readSettings(app, page.request)).toMatchObject({
      manual_summoner_name: "Current TOML Profile#SAFE",
      manual_region: "na",
    });
    const persistedToml = await readFile(path.join(app.appDataDir, "OTP LOL", "parameters.toml"), "utf8");
    expect(persistedToml).toContain('manual_summoner_name = "Current TOML Profile#SAFE"');
    expect(persistedToml).toContain('manual_region = "na"');
    expect(persistedToml).not.toContain("Stale OTP JSON#SAFE");
    expect(await readFile(path.join(app.appDataDir, "OTP LOL", "parameters.json"), "utf8")).toBe(currentJson);
    expect(await readFile(path.join(app.appDataDir, "MainLoL", "parameters.json"), "utf8")).toBe(oldJson);
    expect(await readFile(path.join(app.appDataDir, "OTP LOL", "parameters.json.bak")).catch((error) => error.code))
      .toBe("ENOENT");
    expect(await readFile(path.join(app.appDataDir, "MainLoL", "parameters.json.bak")).catch((error) => error.code))
      .toBe("ENOENT");
  } finally {
    await app.stop();
  }
});

test("MainLoL JSON migration does not overwrite an existing backup", async ({ page }) => {
  const legacySettings = {
    config_schema_version: 3,
    manual_summoner_name: "MainLoL Legacy#BACKUP",
  };
  const legacyJson = `${JSON.stringify(legacySettings, null, 2)}\n`;
  const existingBackup = "preserve existing backup\n";
  const app = await startOtpApp({
    legacySettingsJson: legacyJson,
    legacySettingsFolder: "MainLoL",
    legacySettingsBackupJson: existingBackup,
  });

  try {
    expect(await readSettings(app, page.request)).toMatchObject({
      manual_summoner_name: "MainLoL Legacy#BACKUP",
    });
    expect(await readFile(path.join(app.appDataDir, "MainLoL", "parameters.json.bak"), "utf8")).toBe(existingBackup);
    expect(await readFile(path.join(app.appDataDir, "MainLoL", "parameters.json"), "utf8")).toBe(legacyJson);
    expect(await readFile(path.join(app.appDataDir, "OTP LOL", "parameters.toml"), "utf8"))
      .toContain('manual_summoner_name = "MainLoL Legacy#BACKUP"');
  } finally {
    await app.stop();
  }
});

test("startup migration preserves schema 2 global summoner spells across pick slots", async ({ page }) => {
  const legacySettings = {
    config_version: "8.0",
    config_schema_version: 2,
    global_spell_1: "Flash",
    global_spell_2: "Teleport",
  };
  const legacyJson = `${JSON.stringify(legacySettings, null, 2)}\n`;
  const app = await startOtpApp({ legacySettingsJson: legacyJson });

  try {
    const settings = await readSettings(app, page.request);
    expect(settings.config_schema_version).toBe(6);
    for (const slot of ["pick_1", "pick_2", "pick_3"]) {
      expect(settings.pick_slots[slot]).toMatchObject({ spell_1: "Flash", spell_2: "Teleport" });
    }
    expect(await readFile(path.join(app.appDataDir, "OTP LOL", "parameters.json.bak"), "utf8")).toBe(legacyJson);
  } finally {
    await app.stop();
  }
});

for (const [label, schemaMarker] of [["future", 999], ["malformed", "not-a-schema"]]) {
  test(`startup preserves ${label} JSON schema source without archiving it as current`, async ({ page }) => {
    const legacySettings = {
      config_schema_version: schemaMarker,
      selected_pick_1: "UNSUPPORTED_SCHEMA_CHAMPION_SENTINEL",
      future_setting: "UNSUPPORTED_SCHEMA_VALUE_SENTINEL",
    };
    const legacyJson = `${JSON.stringify(legacySettings, null, 2)}\n`;
    const app = await startOtpApp({ legacySettingsJson: legacyJson });

    try {
      const legacyPath = path.join(app.appDataDir, "OTP LOL", "parameters.json");
      const settings = await readSettings(app, page.request);
      expect(settings.config_schema_version).toBe(6);
      expect(settings.selected_pick_1).not.toBe("UNSUPPORTED_SCHEMA_CHAMPION_SENTINEL");
      expect(await readFile(legacyPath, "utf8")).toBe(legacyJson);
      expect(await readFile(`${legacyPath}.bak`, "utf8").catch((error) => error.code)).toBe("ENOENT");
      const toml = await readFile(path.join(app.appDataDir, "OTP LOL", "parameters.toml"), "utf8");
      expect(toml).toContain("config_schema_version = 6");
      expect(toml).not.toContain("UNSUPPORTED_SCHEMA_CHAMPION_SENTINEL");
    } finally {
      await app.stop();
    }
  });
}

test("startup backs up invalid TOML before exposing first-launch settings", async ({ page }) => {
  const invalidToml = [
    "config_schema_version = 6",
    'selected_pick_1 = "INVALID_TOML_PROFILE_SENTINEL"',
    'manual_summoner_name = "Invalid TOML Player#SAFE"',
    "broken = [",
    "",
  ].join("\n");
  const app = await startOtpApp({ settingsToml: invalidToml });

  try {
    const response = await page.request.get(`${app.baseURL}/api/health`);
    expect(response.status()).toBe(200);

    const settings = await readSettings(app, page.request);
    expect(settings.config_schema_version).toBe(6);
    expect(settings.selected_pick_1).not.toBe("INVALID_TOML_PROFILE_SENTINEL");
    expect(settings.manual_summoner_name).not.toBe("Invalid TOML Player#SAFE");

    const settingsPath = path.join(app.appDataDir, "OTP LOL", "parameters.toml");
    expect(await readFile(`${settingsPath}.bak`, "utf8")).toBe(invalidToml);
    const recoveredToml = await readFile(settingsPath, "utf8");
    expect(recoveredToml).toContain("config_schema_version = 6");
    expect(recoveredToml).not.toContain("INVALID_TOML_PROFILE_SENTINEL");
  } finally {
    await app.stop();
  }
});

test("startup recovers an older TOML schema and keeps the recovered settings across restart", async ({ page }) => {
  const olderToml = [
    "config_schema_version = 5",
    'selected_pick_1 = "OLDER_TOML_PROFILE_SENTINEL"',
    'manual_summoner_name = "Older TOML Player#SAFE"',
    "",
  ].join("\n");
  let app = await startOtpApp({ settingsToml: olderToml });

  try {
    const initialHealth = await page.request.get(`${app.baseURL}/api/health`);
    expect(initialHealth.status()).toBe(200);
    const recoveredSettings = await readSettings(app, page.request);
    expect(recoveredSettings.config_schema_version).toBe(6);
    const recoveredProfileState = {
      config_schema_version: recoveredSettings.config_schema_version,
      selected_pick_1: recoveredSettings.selected_pick_1,
      manual_summoner_name: recoveredSettings.manual_summoner_name,
      manual_region: recoveredSettings.manual_region,
      pick_slots: recoveredSettings.pick_slots,
    };

    const stateDir = app.stateDir;
    await app.stop({ retainState: true });
    app = null;
    app = await startOtpApp({ stateDir });

    const restartedHealth = await page.request.get(`${app.baseURL}/api/health`);
    expect(restartedHealth.status()).toBe(200);
    const restartedSettings = await readSettings(app, page.request);
    expect(restartedSettings.config_schema_version).toBe(6);
    expect(restartedSettings).toMatchObject(recoveredProfileState);
  } finally {
    if (app) await app.stop();
  }
});

test("startup backs up a future TOML schema before falling back to current settings", async ({ page }) => {
  const futureToml = [
    "config_schema_version = 999",
    'selected_pick_1 = "FUTURE_TOML_PROFILE_SENTINEL"',
    'manual_summoner_name = "Future TOML Player#SAFE"',
    'future_setting = "UNSUPPORTED_TOML_VALUE"',
    "",
  ].join("\n");
  const app = await startOtpApp({ settingsToml: futureToml });

  try {
    const response = await page.request.get(`${app.baseURL}/api/health`);
    expect(response.status()).toBe(200);

    const settings = await readSettings(app, page.request);
    expect(settings.config_schema_version).toBe(6);
    expect(settings.selected_pick_1).not.toBe("FUTURE_TOML_PROFILE_SENTINEL");
    expect(settings.manual_summoner_name).not.toBe("Future TOML Player#SAFE");

    const settingsPath = path.join(app.appDataDir, "OTP LOL", "parameters.toml");
    expect(await readFile(`${settingsPath}.bak`, "utf8")).toBe(futureToml);
    const recoveredToml = await readFile(settingsPath, "utf8");
    expect(recoveredToml).toContain("config_schema_version = 6");
    expect(recoveredToml).not.toContain("FUTURE_TOML_PROFILE_SENTINEL");
    expect(recoveredToml).not.toContain("UNSUPPORTED_TOML_VALUE");
  } finally {
    await app.stop();
  }
});

test("successful settings API updates survive a same-profile restart", async ({ page }) => {
  let app = await startOtpApp();
  try {
    const origin = new URL(app.baseURL).origin;
    const response = await page.request.patch(`${app.baseURL}/api/settings`, {
      headers: { Origin: origin },
      data: { auto_accept_enabled: true },
    });
    expect(response.status()).toBe(200);
    expect(await readSettings(app, page.request)).toMatchObject({ auto_accept_enabled: true });

    const stateDir = app.stateDir;
    await app.stop({ retainState: true });
    app = null;
    app = await startOtpApp({ stateDir });

    expect(await readSettings(app, page.request)).toMatchObject({ auto_accept_enabled: true });
  } finally {
    if (app) await app.stop();
  }
});

test("settings export omits detected League identity and import preserves current identity on disk", async ({ page }) => {
  const app = await startOtpApp();
  try {
    await waitForDetectedAccount(app, page.request);
    const before = await readSettings(app, page.request);
    const exportedResponse = await page.request.get(`${app.baseURL}/api/settings/export`);
    expect(exportedResponse.status()).toBe(200);
    expect(exportedResponse.headers()["content-disposition"]).toContain('filename="otp-lol-settings.json"');
    const exported = await exportedResponse.json();
    expect(exported.config_schema_version).toBe(before.config_schema_version);
    for (const key of ["auto_detected_riot_id", "auto_detected_region", "auto_detected_platform"]) {
      expect(exported).not.toHaveProperty(key);
    }

    const theme = before.theme === "flatly" ? "darkly" : "flatly";
    const importedResponse = await page.request.post(`${app.baseURL}/api/settings/import`, {
      headers: { Origin: new URL(app.baseURL).origin },
      data: {
        config_schema_version: before.config_schema_version,
        theme,
        auto_detected_riot_id: "Imported Account#NA",
        auto_detected_region: "na",
        auto_detected_platform: "NA1",
      },
    });
    expect(importedResponse.status()).toBe(200);
    expect(await importedResponse.json()).toMatchObject({
      theme,
      auto_detected_riot_id: before.auto_detected_riot_id,
      auto_detected_region: before.auto_detected_region,
      auto_detected_platform: before.auto_detected_platform,
    });

    const persistedToml = await readFile(path.join(app.appDataDir, "OTP LOL", "parameters.toml"), "utf8");
    const detectedAccount = {
      auto_detected_riot_id: before.auto_detected_riot_id,
      auto_detected_region: before.auto_detected_region,
      auto_detected_platform: before.auto_detected_platform,
    };
    for (const [key, value] of Object.entries(detectedAccount)) {
      expect(persistedToml).toContain(`${key} = ${JSON.stringify(value)}`);
    }
    for (const [key, value] of Object.entries({
      auto_detected_riot_id: "Imported Account#NA",
      auto_detected_region: "na",
      auto_detected_platform: "NA1",
    })) {
      expect(persistedToml).not.toContain(`${key} = ${JSON.stringify(value)}`);
    }

  } finally {
    await app.stop();
  }
});

test("history append enforces its retention limit, ordering, API limit, and restart persistence", async ({ page }) => {
  let app = await startOtpApp();
  try {
    await app.waitForWebSocketSubscription();
    const historyPath = path.join(app.appDataDir, "OTP LOL", "history.json");
    const seededEntries = Array.from({ length: 260 }, (_, index) => ({
      timestamp: "2026-09-30T12:00:00+00:00",
      type: "pick",
      level: "success",
      category: "Champion Select",
      action: "pick",
      message: `retained-event-${index}`,
      details: {},
    }));
    await writeFile(historyPath, JSON.stringify(seededEntries));

    const patch = await page.request.patch(`${app.baseURL}/api/settings`, {
      headers: { Origin: new URL(app.baseURL).origin },
      data: { auto_accept_enabled: true },
    });
    expect(patch.status()).toBe(200);
    await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", { state: "InProgress", playerResponse: "None" });
    await app.waitForLcuRequest("POST", "/lol-matchmaking/v1/ready-check/accept");

    const historyUrl = `${app.baseURL}/api/history`;
    await expect.poll(async () => {
      const response = await page.request.get(`${historyUrl}?limit=999`);
      return (await response.json()).items[0]?.message;
    }).toBe("Match automatically accepted.");

    const oversized = await page.request.get(`${historyUrl}?limit=999`);
    expect(oversized.status()).toBe(200);
    const boundedHistory = await oversized.json();
    expect(boundedHistory.count).toBe(250);
    expect(boundedHistory.items.map(({ message }) => message)).toEqual([
      "Match automatically accepted.",
      ...Array.from({ length: 249 }, (_, index) => `retained-event-${259 - index}`),
    ]);
    const smallHistory = await page.request.get(`${historyUrl}?limit=2`);
    expect((await smallHistory.json()).items).toEqual(boundedHistory.items.slice(0, 2));

    const stateDir = app.stateDir;
    await app.stop({ retainState: true });
    app = null;
    app = await startOtpApp({ stateDir });
    const restartedHistory = await page.request.get(`${app.baseURL}/api/history?limit=250`);
    expect(restartedHistory.status()).toBe(200);
    const restartedPayload = await restartedHistory.json();
    expect(restartedPayload.count).toBe(250);
    expect(restartedPayload.items.map(({ message }) => message)).toContain("Match automatically accepted.");
    expect(restartedPayload.items.map(({ message }) => message)).toContain("retained-event-259");
  } finally {
    if (app) await app.stop();
  }
});

test("history API tolerates unreadable JSON and persists subsequent events", async ({ page }) => {
  let app = await startOtpApp();
  try {
    await app.waitForWebSocketSubscription();
    const historyPath = path.join(app.appDataDir, "OTP LOL", "history.json");
    await writeFile(historyPath, "[corrupt history fixture");

    const before = await page.request.get(`${app.baseURL}/api/history`);
    expect(before.status()).toBe(200);
    expect(await before.json()).toEqual({ items: [], count: 0 });

    const patch = await page.request.patch(`${app.baseURL}/api/settings`, {
      headers: { Origin: new URL(app.baseURL).origin },
      data: { auto_accept_enabled: true },
    });
    expect(patch.status()).toBe(200);
    await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", { state: "InProgress", playerResponse: "None" });
    await app.waitForLcuRequest("POST", "/lol-matchmaking/v1/ready-check/accept");

    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/history`);
      const history = await response.json();
      return history.items.some((entry) => entry.message === "Match automatically accepted.");
    }).toBe(true);
    expect(JSON.parse(await readFile(historyPath, "utf8"))).toMatchObject([
      { message: "Match automatically accepted.", type: "ready_check" },
    ]);

    const recovered = await page.request.get(`${app.baseURL}/api/history`);
    const recoveredPayload = await recovered.json();
    const acceptedEvent = recoveredPayload.items.find(
      (entry) => entry.message === "Match automatically accepted." && entry.type === "ready_check",
    );
    expect(acceptedEvent).toBeDefined();

    const disableAutoAccept = await page.request.patch(`${app.baseURL}/api/settings`, {
      headers: { Origin: new URL(app.baseURL).origin },
      data: { auto_accept_enabled: false },
    });
    expect(disableAutoAccept.status()).toBe(200);
    const stateDir = app.stateDir;
    await app.stop({ retainState: true });
    app = null;
    app = await startOtpApp({ stateDir });

    const restarted = await page.request.get(`${app.baseURL}/api/history?limit=250`);
    expect(restarted.status()).toBe(200);
    const restartedHistory = await restarted.json();
    expect(restartedHistory.items).toEqual(expect.arrayContaining([acceptedEvent]));
    expect(restartedHistory.count).toBe(restartedHistory.items.length);
    const persistedHistory = JSON.parse(await readFile(historyPath, "utf8"));
    expect(persistedHistory).toEqual(expect.arrayContaining([acceptedEvent]));
    expect(restartedHistory.items).toEqual([...persistedHistory].reverse());
  } finally {
    if (app) await app.stop();
  }
});

test("preset API exposes the slot-specific effective profile through FastAPI", async ({ page }) => {
  const app = await startOtpApp();
  try {
    const origin = new URL(app.baseURL).origin;
    const slots = [
      {
        slot: "pick_1",
        champion: "Garen",
        spell_1: "Ghost",
        spell_2: "Flash",
        skin_mode: "fixed",
        skin_id: 86013,
        rune_page_id: 123,
      },
      {
        slot: "pick_2",
        champion: "Lux",
        spell_1: "Heal",
        spell_2: "Teleport",
        skin_mode: "random",
        random_skin_id: 99007,
        rune_page_id: 456,
      },
      {
        slot: "pick_3",
        champion: "Ashe",
        spell_1: "Barrier",
        spell_2: "Ignite",
        skin_mode: "none",
        rune_page_id: 789,
      },
    ];

    for (const { slot, ...settings } of slots) {
      const response = await page.request.put(`${app.baseURL}/api/presets/${slot}`, {
        headers: { Origin: origin },
        data: settings,
      });
      expect(response.status(), slot).toBe(200);
    }

    const response = await page.request.get(`${app.baseURL}/api/presets`);
    expect(response.status()).toBe(200);
    const presets = await response.json();
    for (const { slot, ...expected } of slots) {
      expect(presets.slots[slot]).toMatchObject(expected);
    }
  } finally {
    await app.stop();
  }
});

test("a failed settings-file replacement returns an error and keeps the prior settings", async ({ page }) => {
  const app = await startOtpApp();
  const parametersPath = path.join(app.appDataDir, "OTP LOL", "parameters.toml");
  const heldParametersPath = `${parametersPath}.api-contract-held`;
  let originalFileHeld = false;

  try {
    const origin = new URL(app.baseURL).origin;
    const before = await readSettings(app, page.request);
    const originalBytes = await readFile(parametersPath);

    await rename(parametersPath, heldParametersPath);
    originalFileHeld = true;
    await mkdir(parametersPath);
    await writeFile(path.join(parametersPath, "occupied"), "prevent replacing this directory");

    const response = await page.request.patch(`${app.baseURL}/api/settings`, {
      headers: { Origin: origin },
      data: { theme: before.theme === "flatly" ? "darkly" : "flatly" },
    });
    expect(response.status()).toBe(500);
    expect(await readSettings(app, page.request)).toEqual(before);
    expect(await readFile(heldParametersPath)).toEqual(originalBytes);
  } finally {
    if (originalFileHeld) {
      await rm(parametersPath, { recursive: true, force: true });
      await rename(heldParametersPath, parametersPath);
    }
    await app.stop();
  }
});

test("FastAPI rejects hostile HTTP origins and hosts and returns its local security headers", async ({ page }) => {
  const app = await startOtpApp();
  try {
    const hostileOrigin = "https://evil.example";
    await waitForDetectedAccount(app, page.request);
    const before = await readSettings(app, page.request);

    const health = await page.request.get(`${app.baseURL}/api/health`);
    expect(health.status()).toBe(200);
    expect(health.headers()["x-content-type-options"]).toBe("nosniff");
    expect(health.headers()["referrer-policy"]).toBe("no-referrer");
    expect(health.headers()["content-security-policy"]).toContain("frame-ancestors 'none'");

    const hostileRead = await page.request.get(`${app.baseURL}/api/health`, {
      headers: { Origin: hostileOrigin },
    });
    expect(hostileRead.status()).toBe(200);
    expect(hostileRead.headers()["access-control-allow-origin"]).toBeUndefined();

    const preflight = await page.request.fetch(`${app.baseURL}/api/settings`, {
      method: "OPTIONS",
      headers: {
        Origin: hostileOrigin,
        "Access-Control-Request-Method": "PATCH",
        "Access-Control-Request-Headers": "content-type",
      },
    });
    expect(preflight.status()).toBe(400);
    expect(preflight.headers()["access-control-allow-origin"]).toBeUndefined();

    const deniedMutation = await page.request.post(`${app.baseURL}/api/settings/reset`, {
      headers: { Origin: hostileOrigin },
    });
    expect(deniedMutation.status()).toBe(403);
    expect(await deniedMutation.json()).toEqual({ detail: "Untrusted request origin" });
    expect(await readSettings(app, page.request)).toEqual(before);

    const deniedHost = await page.request.get(`${app.baseURL}/api/health`, {
      headers: { Host: "evil.example" },
    });
    expect(deniedHost.status()).toBe(400);
  } finally {
    await app.stop();
  }
});

test("events WebSocket rejects a hostile Origin during the real HTTP upgrade", async () => {
  const app = await startOtpApp();
  try {
    const statusLine = await webSocketUpgradeStatus(app.baseURL, "https://evil.example");
    expect(statusLine).toMatch(/^HTTP\/1\.1 403\b/);
  } finally {
    await app.stop();
  }
});
