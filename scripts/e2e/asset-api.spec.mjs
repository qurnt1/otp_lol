import { expect, test } from "../../frontend/node_modules/@playwright/test/index.mjs";
import { startOtpApp } from "./appServer.mjs";

const CHAMPION_PATH = "/lol-game-data/assets/v1/champion-icons/86.png";
const CHAMPION_CATALOGUE_PATH = "/lol-game-data/assets/v1/champion-summary.json";
const MAPS_CATALOGUE_PATH = "/lol-game-data/assets/v1/maps.json";
const CATALOGUES = {
  [CHAMPION_CATALOGUE_PATH]: [
    {
      id: 86,
      name: "Garen",
      squarePortraitPath: CHAMPION_PATH,
      skins: [{ skinId: 86013, tilePath: "/lol-game-data/assets/v1/skins/garen-13.png", splashPath: "/lol-game-data/assets/v1/skins/garen-13-splash.png" }],
    },
  ],
  "/lol-game-data/assets/v1/summoner-spells.json": [
    { summonerSpellId: 4, name: "Flash", iconPath: "/lol-game-data/assets/v1/summoner-spells/Flash.png" },
  ],
  "/lol-game-data/assets/v1/perks.json": [
    { id: 8005, name: "Press the Attack", iconPath: "/lol-game-data/assets/v1/perk-images/8005.png" },
  ],
  "/lol-game-data/assets/v1/items.json": [
    { id: 1001, name: "Boots", iconPath: "/lol-game-data/assets/v1/items/1001.png" },
  ],
  [MAPS_CATALOGUE_PATH]: [{ mapId: 11, name: "Summoner's Rift" }],
  "/lol-game-data/assets/v1/queues.json": [{ queueId: 420, name: "Ranked Solo" }],
};

const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAAA3NCSVQICAjb4U/gAAAADUlEQVQIHWP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC",
  "base64",
);
const JPEG = Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00]);
const PNG_V2 = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/3f8AAAAASUVORK5CYII=",
  "base64",
);

async function connected(app, request) {
  await expect.poll(async () => {
    const response = await request.get(`${app.baseURL}/api/account/identity`);
    const identity = await response.json();
    return { connected: identity.connected, source: identity.source };
  }).toEqual({ connected: true, source: "connected" });
}

function binaryResponse(content, contentType) {
  return { status: 200, content_type: contentType, body_base64: content.toString("base64") };
}

async function expectStaticCacheVersion(app, request, version) {
  await expect.poll(async () => {
    const response = await request.get(`${app.baseURL}/api/game-data/status`);
    if (!response.ok()) return null;
    const status = await response.json();
    return {
      source: status.source,
      gameVersion: status.game_version,
      cacheVersion: status.cache_version,
      catalogs: status.catalogs,
    };
  }, { timeout: 15_000 }).toMatchObject({
    source: "lcu",
    gameVersion: version,
    cacheVersion: version,
    catalogs: {
      champions: true,
      spells: true,
      perks: true,
      items: true,
      maps: true,
      queues: true,
    },
  });
}

test("asset API serves validated LCU PNG, JPEG, skin variants and cached bytes", async ({ page }) => {
  const app = await startOtpApp();
  try {
    await connected(app, page.request);
    const assetPaths = [
      CHAMPION_PATH,
      "/lol-game-data/assets/v1/summoner-spells/Flash.png",
      "/lol-game-data/assets/v1/perk-images/8005.png",
      "/lol-game-data/assets/v1/items/1001.png",
      "/lol-game-data/assets/v1/skins/garen-13.png",
      "/lol-game-data/assets/v1/skins/garen-13-splash.png",
    ];
    await app.configureLcuState({
      static_data_online: true,
      static_catalogues: CATALOGUES,
      asset_responses: Object.fromEntries(assetPaths.map((assetPath) => [
        assetPath,
        binaryResponse(assetPath.includes("8005") ? JPEG : PNG, assetPath.includes("8005") ? "image/jpeg" : "image/png"),
      ])),
    });
    await page.request.get(`${app.baseURL}/api/game-data/status`);
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/game-data/status`);
      return (await response.json()).catalogs;
    }).toMatchObject({ champions: true, spells: true, perks: true, items: true });

    const routes = [
      ["/api/assets/champions/86.png", "image/png", PNG.subarray(0, 8), "public, max-age=86400"],
      ["/api/assets/spells/4.png", "image/png", PNG.subarray(0, 8), "public, max-age=86400"],
      ["/api/assets/runes/perk/8005.png", "image/jpeg", JPEG.subarray(0, 3), "public, max-age=86400"],
      ["/api/assets/items/1001.png", "image/png", PNG.subarray(0, 8), "no-cache"],
      ["/api/assets/skins/86/86013.png", "image/png", PNG.subarray(0, 8), "public, max-age=86400"],
      ["/api/assets/skins/86/86013/splash", "image/png", PNG.subarray(0, 8), "public, max-age=86400"],
    ];
    for (const [route, mediaType, signature, cacheControl] of routes) {
      const response = await page.request.get(`${app.baseURL}${route}`);
      expect(response.status(), route).toBe(200);
      expect(response.headers()["content-type"], route).toContain(mediaType);
      expect((await response.body()).subarray(0, signature.length), route).toEqual(signature);
      expect(response.headers()["cache-control"], route).toBe(cacheControl);
      const repeated = await page.request.get(`${app.baseURL}${route}`);
      expect(repeated.status(), `${route} cache read`).toBe(200);
    }

    for (const assetPath of assetPaths) {
      expect(app.lcuRequests.filter(({ method, path }) => method === "GET" && path === assetPath), assetPath).toHaveLength(1);
    }
    expect((await page.request.get(`${app.baseURL}/api/assets/champions/999.png`)).status()).toBe(404);
    expect((await page.request.get(`${app.baseURL}/api/assets/champions/not-a-number.png`)).status()).toBe(422);
    expect(app.lcuRequests.some(({ path }) => path === "/lol-game-data/assets/v1/champion-icons/999.png")).toBe(false);
  } finally {
    await app.stop();
  }
});

test("asset API separates cached bytes when the LCU game version changes", async ({ page }) => {
  const app = await startOtpApp();
  try {
    await connected(app, page.request);
    await app.configureLcuState({
      static_data_online: true,
      game_version: "16.1.1",
      static_catalogues: CATALOGUES,
      asset_responses: { [CHAMPION_PATH]: binaryResponse(PNG, "image/png") },
    });
    await page.request.get(`${app.baseURL}/api/game-data/status`);
    await expectStaticCacheVersion(app, page.request, "16.1.1");

    const firstResponse = await page.request.get(`${app.baseURL}/api/assets/champions/86.png`);
    expect(firstResponse.status()).toBe(200);
    expect(await firstResponse.body()).toEqual(PNG);
    expect(app.lcuRequests.filter(({ method, path }) => method === "GET" && path === CHAMPION_PATH)).toHaveLength(1);

    await app.configureLcuConnection({ online: false });
    await app.configureLcuState({
      game_version: "16.1.2",
      asset_responses: { [CHAMPION_PATH]: binaryResponse(PNG_V2, "image/png") },
    });
    await app.configureLcuConnection({ online: true });
    await app.waitForWebSocketSubscription(2);
    await expectStaticCacheVersion(app, page.request, "16.1.2");

    const updatedResponse = await page.request.get(`${app.baseURL}/api/assets/champions/86.png`);
    expect(updatedResponse.status()).toBe(200);
    expect(await updatedResponse.body()).toEqual(PNG_V2);
    expect(app.lcuRequests.filter(({ method, path }) => method === "GET" && path === CHAMPION_PATH)).toHaveLength(2);

    const cachedResponse = await page.request.get(`${app.baseURL}/api/assets/champions/86.png`);
    expect(cachedResponse.status()).toBe(200);
    expect(await cachedResponse.body()).toEqual(PNG_V2);
    expect(app.lcuRequests.filter(({ method, path }) => method === "GET" && path === CHAMPION_PATH)).toHaveLength(2);
  } finally {
    await app.stop();
  }
});

test("an invalid new LCU catalogue leaves the previous complete snapshot available", async ({ page }) => {
  const app = await startOtpApp();
  try {
    await connected(app, page.request);
    await app.configureLcuState({
      static_data_online: true,
      game_version: "16.1.1",
      static_catalogues: CATALOGUES,
    });
    await page.request.get(`${app.baseURL}/api/game-data/status`);
    await expectStaticCacheVersion(app, page.request, "16.1.1");

    const initialChampions = await page.request.get(`${app.baseURL}/api/champions`);
    expect((await initialChampions.json()).items.map(({ id }) => id)).toEqual([86]);
    const previousMapRequests = app.lcuRequests.filter(
      ({ method, path }) => method === "GET" && path === MAPS_CATALOGUE_PATH,
    ).length;
    const incompleteCatalogues = {
      ...CATALOGUES,
      [CHAMPION_CATALOGUE_PATH]: [
        ...CATALOGUES[CHAMPION_CATALOGUE_PATH],
        { id: 99, name: "Lux", alias: "Lux", squarePortraitPath: "/lol-game-data/assets/v1/champion-icons/99.png" },
      ],
      [MAPS_CATALOGUE_PATH]: [],
    };

    await app.configureLcuConnection({ online: false });
    await app.configureLcuState({
      game_version: "16.1.2",
      static_catalogues: incompleteCatalogues,
    });
    await app.configureLcuConnection({ online: true });
    await app.waitForWebSocketSubscription(2);
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/diagnostics`);
      const diagnostics = await response.json();
      return diagnostics.events.some((event) => (
        event.topic === "otp-lol/data/static-data"
        && event.event_type === "refresh"
        && event.payload?.refreshed === false
        && event.payload?.status?.game_version === "16.1.2"
        && event.payload?.status?.cache_version === "16.1.1"
      ));
    }, { timeout: 15_000 }).toBe(true);
    expect(app.lcuRequests.filter(
      ({ method, path }) => method === "GET" && path === MAPS_CATALOGUE_PATH,
    )).toHaveLength(previousMapRequests + 1);

    const preservedStatus = await page.request.get(`${app.baseURL}/api/game-data/status`);
    expect(await preservedStatus.json()).toMatchObject({
      source: "lcu",
      game_version: "16.1.2",
      cache_version: "16.1.1",
      catalogs: { champions: true, spells: true, perks: true, items: true, maps: true, queues: true },
    });
    const preservedChampions = await page.request.get(`${app.baseURL}/api/champions`);
    const championIds = (await preservedChampions.json()).items.map(({ id }) => id);
    expect(championIds).toContain(86);
    expect(championIds).not.toContain(99);
  } finally {
    await app.stop();
  }
});

test("asset API rejects unsafe catalogue paths before the LCU request and uses Data Dragon fallback", async ({ page }) => {
  const app = await startOtpApp();
  try {
    await connected(app, page.request);
    const maliciousCatalogues = {
      ...CATALOGUES,
      "/lol-game-data/assets/v1/champion-summary.json": [
        { id: 86, name: "Garen", squarePortraitPath: "/lol-game-data/assets/v1/%25252e%25252e/secrets.png" },
      ],
    };
    await app.configureLcuState({
      static_data_online: true,
      static_catalogues: maliciousCatalogues,
    });
    await page.request.get(`${app.baseURL}/api/game-data/status`);
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/game-data/status`);
      return (await response.json()).catalogs.champions;
    }).toBe(true);

    const traversalFallback = await page.request.get(`${app.baseURL}/api/assets/champions/86.png`);
    expect(traversalFallback.status()).toBe(200);
    expect(traversalFallback.headers()["content-type"]).toContain("image/png");
    expect((await traversalFallback.body()).subarray(0, 8)).toEqual(PNG.subarray(0, 8));
    expect(app.lcuRequests.some(({ path }) => path.includes("secrets"))).toBe(false);
    expect(app.lcuRequests.some(({ path }) => path === CHAMPION_PATH)).toBe(false);
    expect(app.externalFixtureRequests.some(({ host, path, status }) => (
      host === "ddragon.leagueoflegends.com" && path.endsWith("/img/champion/Garen.png") && status === 200
    ))).toBe(true);
  } finally {
    await app.stop();
  }
});

test("asset API rejects non-image LCU bytes and returns the Data Dragon image", async ({ page }) => {
  const app = await startOtpApp();
  try {
    await connected(app, page.request);
    await app.configureLcuState({
      static_data_online: true,
      static_catalogues: CATALOGUES,
      asset_responses: {
        [CHAMPION_PATH]: binaryResponse(Buffer.from("<html>private upstream body</html>"), "text/html"),
      },
    });
    await page.request.get(`${app.baseURL}/api/game-data/status`);
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/game-data/status`);
      return (await response.json()).catalogs.champions;
    }).toBe(true);

    const invalidBytesFallback = await page.request.get(`${app.baseURL}/api/assets/champions/86.png`);
    const invalidBytes = await invalidBytesFallback.body();
    expect(invalidBytesFallback.status()).toBe(200);
    expect(invalidBytesFallback.headers()["content-type"]).toContain("image/png");
    expect(invalidBytes.subarray(0, 8)).toEqual(PNG.subarray(0, 8));
    expect(invalidBytes.toString("utf8")).not.toContain("private upstream body");
    expect(app.lcuRequests.filter(({ method, path }) => method === "GET" && path === CHAMPION_PATH)).toHaveLength(1);
    expect(app.externalFixtureRequests.some(({ host, path, status }) => (
      host === "ddragon.leagueoflegends.com" && path.endsWith("/img/champion/Garen.png") && status === 200
    ))).toBe(true);
  } finally {
    await app.stop();
  }
});

test("asset API reads persisted LCU bytes after an offline same-profile restart", async ({ page }) => {
  const first = await startOtpApp();
  let stateDir;
  try {
    await connected(first, page.request);
    await first.configureLcuState({
      static_data_online: true,
      static_catalogues: CATALOGUES,
      asset_responses: { [CHAMPION_PATH]: binaryResponse(PNG, "image/png") },
    });
    await page.request.get(`${first.baseURL}/api/game-data/status`);
    await expect.poll(async () => {
      const response = await page.request.get(`${first.baseURL}/api/game-data/status`);
      return (await response.json()).catalogs.champions;
    }).toBe(true);

    const initial = await page.request.get(`${first.baseURL}/api/assets/champions/86.png`);
    expect(initial.status()).toBe(200);
    expect((await initial.body()).subarray(0, 8)).toEqual(PNG.subarray(0, 8));
    stateDir = first.stateDir;
    await first.stop({ retainState: true });
  } catch (error) {
    await first.stop().catch(() => {});
    throw error;
  }

  const restarted = await startOtpApp({ stateDir });
  try {
    await connected(restarted, page.request);
    const cached = await page.request.get(`${restarted.baseURL}/api/assets/champions/86.png`);
    expect(cached.status()).toBe(200);
    expect(cached.headers()["content-type"]).toContain("image/png");
    expect((await cached.body()).subarray(0, 8)).toEqual(PNG.subarray(0, 8));
    expect(restarted.lcuRequests.some(({ path }) => path === CHAMPION_PATH)).toBe(false);
  } finally {
    await restarted.stop();
  }
});

test("skin catalogue remains available with unknown ownership after League disconnects", async ({ page }) => {
  const app = await startOtpApp();
  try {
    await connected(app, page.request);
    await app.configureExternalState({ dataDragon: "online" });
    await app.configureLcuConnection({ online: false });
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/health`);
      return (await response.json()).lcu_connected;
    }).toBe(false);

    const response = await page.request.get(`${app.baseURL}/api/skins/86`);
    const body = await response.json();
    expect(response.status()).toBe(200);
    expect(body.champion_id).toBe(86);
    expect(body.catalog.map(({ skin_id }) => skin_id)).toEqual([86000, 86001, 86013]);
    expect(body.owned).toMatchObject({ ok: false, owned_skins: [] });
    expect(body.owned.message).toBeTruthy();
    expect(app.lcuRequests.some(({ path }) => path === "/lol-champions/v1/inventories/24680135/champions/86/skins"))
      .toBe(false);
    await app.waitForExternalFixtureRequest(
      "ddragon.leagueoflegends.com",
      "/cdn/16.1.1/data/en_US/champion/Garen.json",
      200,
    );
  } finally {
    await app.stop();
  }
});
