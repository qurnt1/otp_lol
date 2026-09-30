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
