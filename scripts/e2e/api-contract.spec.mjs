import { connect } from "node:net";
import { mkdir, readFile, rename, rm, writeFile } from "node:fs/promises";
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
        "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==",
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
