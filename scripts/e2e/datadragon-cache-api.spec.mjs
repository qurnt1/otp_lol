import { expect, test } from "../../frontend/node_modules/@playwright/test/index.mjs";
import { startOtpApp } from "./appServer.mjs";

const championDataPath = "/cdn/16.1.1/data/en_US/champion.json";
const garenSkinDetailPath = "/cdn/16.1.1/data/en_US/champion/Garen.json";
const garenSkinTileImagePath = "/cdn/img/champion/tiles/Garen_13.jpg";
const garenSkinSplashImagePath = "/cdn/img/champion/splash/Garen_13.jpg";

function championRequests(app) {
  return app.externalFixtureRequests.filter((request) => (
    request.host === "ddragon.leagueoflegends.com" && request.path === championDataPath
  ));
}

function externalRequests(app, host, requestPath) {
  return app.externalFixtureRequests.filter((request) => request.host === host && request.path === requestPath);
}

function communityDragonSkinDetails(app) {
  return app.externalFixtureRequests.filter((request) => (
    request.host === "raw.communitydragon.org"
      && /\/latest\/plugins\/rcp-be-lol-game-data\/global\/default\/v1\/champions\/\d+\.json$/.test(request.path)
  ));
}

test("Data Dragon catalogue is reused within a run and survives a same-profile offline restart", async ({ page }) => {
  let app = await startOtpApp();
  let stateDir;
  try {
    await app.configureExternalState({ dataDragon: "online" });
    const initialResponse = await page.request.get(`${app.baseURL}/api/champions?q=Lux`);
    const initial = await initialResponse.json();
    expect(initialResponse.status()).toBe(200);
    expect(initial.items).toEqual([expect.objectContaining({ id: 99, name: "Lux", slug: "Lux" })]);
    await app.waitForExternalFixtureRequest(
      "ddragon.leagueoflegends.com",
      championDataPath,
      200,
    );
    const fetchCount = championRequests(app).length;
    expect(fetchCount).toBeGreaterThan(0);

    const repeatedResponse = await page.request.get(`${app.baseURL}/api/champions?q=Lux`);
    expect(repeatedResponse.status()).toBe(200);
    expect((await repeatedResponse.json()).items).toEqual(initial.items);
    expect(championRequests(app)).toHaveLength(fetchCount);

    stateDir = app.stateDir;
    await app.stop({ retainState: true });
  } catch (error) {
    await app.stop().catch(() => {});
    throw error;
  }

  app = await startOtpApp({ stateDir });
  try {
    await app.configureExternalState({ dataDragon: "offline" });
    const offlineResponse = await page.request.get(`${app.baseURL}/api/champions?q=Lux`);
    const offline = await offlineResponse.json();
    expect(offlineResponse.status()).toBe(200);
    expect(offline.items).toEqual([expect.objectContaining({ id: 99, name: "Lux", slug: "Lux" })]);
    expect(championRequests(app)).toEqual([]);
  } finally {
    await app.stop();
  }
});

test("skin metadata and thumbnails use Data Dragon only, with versioned immutable responses cached offline", async ({ page }) => {
  let app = await startOtpApp();
  let stateDir;
  let skinImageUrl;
  let splashImageUrl;
  let originalImage;
  let originalSplashImage;
  let originalCatalog;
  try {
    await app.configureExternalState({ dataDragon: "online" });
    const catalogResponse = await page.request.get(`${app.baseURL}/api/skins/86`);
    expect(catalogResponse.status()).toBe(200);
    originalCatalog = await catalogResponse.json();
    const godKingSkin = originalCatalog.catalog.find((skin) => skin.skin_id === 86013);
    expect(godKingSkin).toMatchObject({ champion_id: 86, skin_num: 13, skin_name: "God-King Garen" });
    expect(godKingSkin.tile_url).toContain("/api/assets/skins/86/86013.png?v=16.1.1");
    expect(godKingSkin.splash_url).toBe("https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Garen_13.jpg");
    await app.waitForExternalFixtureRequest("ddragon.leagueoflegends.com", garenSkinDetailPath, 200);
    expect(communityDragonSkinDetails(app)).toEqual([]);

    skinImageUrl = new URL(godKingSkin.tile_url, app.baseURL);
    expect(skinImageUrl.pathname).toBe("/api/assets/skins/86/86013.png");
    expect(skinImageUrl.searchParams.get("v")).toBe("16.1.1");
    const imageResponse = await page.request.get(skinImageUrl.href);
    expect(imageResponse.status()).toBe(200);
    expect(imageResponse.headers()["content-type"]).toContain("image/jpeg");
    expect(imageResponse.headers()["cache-control"]).toBe("public, max-age=31536000, immutable");
    originalImage = await imageResponse.body();
    await app.waitForExternalFixtureRequest("ddragon.leagueoflegends.com", garenSkinTileImagePath, 200);
    expect(externalRequests(app, "ddragon.leagueoflegends.com", garenSkinTileImagePath)).toHaveLength(1);
    expect(communityDragonSkinDetails(app)).toEqual([]);

    splashImageUrl = new URL(
      "/api/assets/skins/86/86013/splash?skin_num=13&v=16.1.1",
      app.baseURL,
    );
    const splashResponse = await page.request.get(splashImageUrl.href);
    expect(splashResponse.status()).toBe(200);
    expect(splashResponse.headers()["content-type"]).toContain("image/jpeg");
    expect(splashResponse.headers()["cache-control"]).toBe("public, max-age=31536000, immutable");
    originalSplashImage = await splashResponse.body();
    expect(originalImage.byteLength).toBeLessThan(originalSplashImage.byteLength);
    await app.waitForExternalFixtureRequest("ddragon.leagueoflegends.com", garenSkinSplashImagePath, 200);
    expect(externalRequests(app, "ddragon.leagueoflegends.com", garenSkinSplashImagePath)).toHaveLength(1);

    const cachedResponse = await page.request.get(skinImageUrl.href);
    expect(cachedResponse.status()).toBe(200);
    expect(cachedResponse.headers()["cache-control"]).toBe("public, max-age=31536000, immutable");
    expect(await cachedResponse.body()).toEqual(originalImage);
    expect(externalRequests(app, "ddragon.leagueoflegends.com", garenSkinTileImagePath)).toHaveLength(1);
    const cachedSplashResponse = await page.request.get(splashImageUrl.href);
    expect(cachedSplashResponse.status()).toBe(200);
    expect(await cachedSplashResponse.body()).toEqual(originalSplashImage);
    expect(externalRequests(app, "ddragon.leagueoflegends.com", garenSkinSplashImagePath)).toHaveLength(1);

    stateDir = app.stateDir;
    await app.stop({ retainState: true });
  } catch (error) {
    await app.stop().catch(() => {});
    throw error;
  }

  app = await startOtpApp({ stateDir });
  try {
    await app.configureExternalState({ dataDragon: "offline" });
    const requestsBeforeOfflineLookup = app.externalFixtureRequests.length;
    const offlineCatalogResponse = await page.request.get(`${app.baseURL}/api/skins/86`);
    expect(offlineCatalogResponse.status()).toBe(200);
    const offlineCatalog = await offlineCatalogResponse.json();
    expect(offlineCatalog.catalog).toEqual(originalCatalog.catalog);
    expect(communityDragonSkinDetails(app)).toEqual([]);
    expect(externalRequests(app, "ddragon.leagueoflegends.com", garenSkinDetailPath)).toEqual([]);

    const offlineImageResponse = await page.request.get(skinImageUrl.href.replace(new URL(skinImageUrl.href).origin, app.baseURL));
    expect(offlineImageResponse.status()).toBe(200);
    expect(offlineImageResponse.headers()["cache-control"]).toBe("public, max-age=31536000, immutable");
    expect(await offlineImageResponse.body()).toEqual(originalImage);
    expect(externalRequests(app, "ddragon.leagueoflegends.com", garenSkinTileImagePath)).toEqual([]);
    const offlineSplashResponse = await page.request.get(
      splashImageUrl.href.replace(new URL(splashImageUrl.href).origin, app.baseURL),
    );
    expect(offlineSplashResponse.status()).toBe(200);
    expect(offlineSplashResponse.headers()["cache-control"]).toBe("public, max-age=31536000, immutable");
    expect(await offlineSplashResponse.body()).toEqual(originalSplashImage);
    expect(externalRequests(app, "ddragon.leagueoflegends.com", garenSkinSplashImagePath)).toEqual([]);
    expect(communityDragonSkinDetails(app)).toEqual([]);
    expect(app.externalFixtureRequests.length).toBe(requestsBeforeOfflineLookup);
  } finally {
    await app.stop();
  }
});

test("a missing Data Dragon skin tile returns 404 without requesting CommunityDragon skin details", async ({ page }) => {
  const app = await startOtpApp();
  try {
    await app.configureExternalState({ dataDragon: "online", skinTile: "missing" });

    const catalogResponse = await page.request.get(`${app.baseURL}/api/skins/86`);
    expect(catalogResponse.status()).toBe(200);
    const catalog = await catalogResponse.json();
    const godKingSkin = catalog.catalog.find((skin) => skin.skin_id === 86013);
    expect(godKingSkin).toBeTruthy();

    const imageResponse = await page.request.get(new URL(godKingSkin.tile_url, app.baseURL).href);
    expect(imageResponse.status()).toBe(404);
    await app.waitForExternalFixtureRequest(
      "ddragon.leagueoflegends.com",
      garenSkinTileImagePath,
      404,
    );
    expect(externalRequests(app, "ddragon.leagueoflegends.com", garenSkinTileImagePath)).toHaveLength(1);
    expect(communityDragonSkinDetails(app)).toEqual([]);
  } finally {
    await app.stop();
  }
});
