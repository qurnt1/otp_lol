import { expect, test } from "../../frontend/node_modules/@playwright/test/index.mjs";
import { startOtpApp } from "./appServer.mjs";

async function waitForConnectedIdentity(app, request) {
  await expect.poll(async () => {
    const response = await request.get(`${app.baseURL}/api/account/identity`);
    const identity = await response.json();
    return { connected: identity.connected, source: identity.source };
  }).toEqual({ connected: true, source: "connected" });
}

test("diagnostics API exposes safe fixed GET checks and gates Riot ID export on opt-in", async ({ page }) => {
  const app = await startOtpApp();
  try {
    await waitForConnectedIdentity(app, page.request);
    const origin = new URL(app.baseURL).origin;
    const overviewResponse = await page.request.get(`${app.baseURL}/api/diagnostics`);
    const overview = await overviewResponse.json();
    expect(overviewResponse.status()).toBe(200);
    expect(overview.runtime).not.toHaveProperty("riot_id");
    expect(overview.account_identity).toMatchObject({ riot_id: "E2E Player#SAFE", source: "connected" });
    expect(overview.endpoint_checks.length).toBeGreaterThan(0);
    expect(overview.endpoint_checks.every((check) => check.method === "GET" && check.path.startsWith("/lol-"))).toBe(true);

    const rejectedRun = await page.request.post(`${app.baseURL}/api/diagnostics/run`, {
      headers: { Origin: origin },
      data: { endpoint_ids: ["/lol-secret/path"] },
    });
    expect(rejectedRun.status()).toBe(422);
    expect(app.lcuRequests.some(({ path }) => path === "/lol-secret/path")).toBe(false);

    const safeRun = await page.request.post(`${app.baseURL}/api/diagnostics/run`, {
      headers: { Origin: origin },
      data: { endpoint_ids: ["gameflow_phase", "ranked_stats"] },
    });
    const safeRunBody = await safeRun.json();
    expect(safeRun.status()).toBe(200);
    expect(safeRunBody.results).toMatchObject([
      { id: "gameflow_phase", method: "GET", path: "/lol-gameflow/v1/gameflow-phase", success: true, error: null },
      { id: "ranked_stats", method: "GET", path: "/lol-ranked/v1/current-ranked-stats", success: false, error: "http_error" },
    ]);
    expect(JSON.stringify(safeRunBody)).not.toMatch(/otp-lol-e2e-token|PRIVATE|Authorization|PRIVATE_TOKEN/);
    await app.waitForLcuRequest("GET", "/lol-gameflow/v1/gameflow-phase");
    await app.waitForLcuRequest("GET", "/lol-ranked/v1/current-ranked-stats");

    const redactedResponse = await page.request.get(`${app.baseURL}/api/diagnostics/export`);
    const redacted = await redactedResponse.json();
    expect(redactedResponse.status()).toBe(200);
    expect(redactedResponse.headers()["content-disposition"]).toBe('attachment; filename="otp-lol-diagnostics.json"');
    expect(redacted).not.toHaveProperty("riot_id");
    expect(redacted.account_identity.riot_id).toBeNull();
    expect(redacted.endpoint_results).toContainEqual(expect.objectContaining({ id: "gameflow_phase", success: true }));

    const optedInResponse = await page.request.get(`${app.baseURL}/api/diagnostics/export?include_riot_id=true`);
    const optedIn = await optedInResponse.json();
    expect(optedInResponse.status()).toBe(200);
    expect(optedIn.riot_id).toBe("E2E Player#SAFE");
    expect(optedIn.account_identity.riot_id).toBe("E2E Player#SAFE");
  } finally {
    await app.stop();
  }
});

test("running diagnostics without endpoint IDs checks the complete fixed allowlist", async ({ page }) => {
  const app = await startOtpApp();
  try {
    await waitForConnectedIdentity(app, page.request);
    const origin = new URL(app.baseURL).origin;
    const expectedChecks = [
      { id: "gameflow_phase", method: "GET", path: "/lol-gameflow/v1/gameflow-phase" },
      { id: "current_summoner", method: "GET", path: "/lol-summoner/v1/current-summoner" },
      { id: "game_version", method: "GET", path: "/lol-patch/v1/game-version" },
      { id: "champion_summary", method: "GET", path: "/lol-game-data/assets/v1/champion-summary.json" },
      { id: "ranked_stats", method: "GET", path: "/lol-ranked/v1/current-ranked-stats" },
      { id: "masteries", method: "GET", path: "/lol-champion-mastery/v1/local-player/champion-mastery" },
      { id: "match_history", method: "GET", path: "/lol-match-history/v1/products/lol/current-summoner/matches" },
    ];
    const overview = await page.request.get(`${app.baseURL}/api/diagnostics`).then((response) => response.json());
    const checks = overview.endpoint_checks;
    expect(checks.map(({ id, method, path }) => ({ id, method, path }))).toEqual(expectedChecks);
    expect(checks.every((check) => check.method === "GET" && check.path.startsWith("/lol-"))).toBe(true);
    const requestCountsBefore = new Map(expectedChecks.map(({ path }) => [
      path,
      app.lcuRequests.filter((request) => request.method === "GET" && request.path === path).length,
    ]));

    const runResponse = await page.request.post(`${app.baseURL}/api/diagnostics/run`, {
      headers: { Origin: origin },
      data: {},
    });
    const runBody = await runResponse.json();
    expect(runResponse.status()).toBe(200);
    expect(runBody.results).toHaveLength(expectedChecks.length);
    expect(runBody.results.map(({ id, method, path }) => ({ id, method, path }))).toEqual(
      expectedChecks,
    );

    for (const check of expectedChecks) {
      await app.waitForLcuRequest("GET", check.path);
      expect(
        app.lcuRequests.filter((request) => request.method === "GET" && request.path === check.path),
        check.id,
      ).toHaveLength(requestCountsBefore.get(check.path) + 1);
    }

    const persistedResults = await page.request.get(`${app.baseURL}/api/diagnostics`)
      .then(async (response) => {
        expect(response.status()).toBe(200);
        return (await response.json()).endpoint_results;
      });
    expect(persistedResults).toEqual(runBody.results);
  } finally {
    await app.stop();
  }
});

test("diagnostics event storage redacts sensitive values arriving over the real LCU WebSocket", async ({ page }) => {
  const app = await startOtpApp();
  try {
    await waitForConnectedIdentity(app, page.request);
    await app.waitForWebSocketSubscription();
    await app.emitLcuEvent("/lol-champ-select/v1/session", {
      gameConfig: { queueId: 420, gameMode: "CLASSIC" },
      localPlayerCellId: 1,
      myTeam: [{
        cellId: 1,
        summonerId: 24680135,
        assignedPosition: "TOP",
        championId: 0,
        puuid: "PRIVATE_EVENT_PUUID_SENTINEL",
        summonerName: "PRIVATE_EVENT_NAME_SENTINEL",
        Authorization: "PRIVATE_EVENT_TOKEN_SENTINEL",
      }],
      actions: [],
      bans: { myTeamBans: [], theirTeamBans: [] },
    });

    let diagnostics;
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/diagnostics`);
      diagnostics = await response.json();
      return diagnostics.events.some((event) => event.topic === "/lol-champ-select/v1/session");
    }).toBe(true);

    const event = diagnostics.events.find((entry) => entry.topic === "/lol-champ-select/v1/session");
    expect(event.payload_redacted).toBe(true);
    const serialized = JSON.stringify(event);
    for (const secret of [
      "PRIVATE_EVENT_PUUID_SENTINEL",
      "PRIVATE_EVENT_NAME_SENTINEL",
      "PRIVATE_EVENT_TOKEN_SENTINEL",
    ]) {
      expect(serialized).not.toContain(secret);
    }
  } finally {
    await app.stop();
  }
});
