import { expect, test } from "../../frontend/node_modules/@playwright/test/index.mjs";
import { startOtpApp } from "./appServer.mjs";

const championDataPath = "/cdn/16.1.1/data/en_US/champion.json";

function championRequests(app) {
  return app.externalFixtureRequests.filter((request) => (
    request.host === "ddragon.leagueoflegends.com" && request.path === championDataPath
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
