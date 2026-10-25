import { readFile, readdir, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import path from "node:path";
import { expect, test } from "../../frontend/node_modules/@playwright/test/index.mjs";
import { startOtpApp } from "./appServer.mjs";

const accountPaths = {
  summary: "/lol-summoner/v1/current-summoner",
  ranked: "/lol-ranked/v1/current-ranked-stats",
  masteries: "/lol-champion-mastery/v1/local-player/champion-mastery",
  masteryScore: "/lol-champion-mastery/v1/local-player/champion-mastery-score",
  challenges: "/lol-challenges/v1/challenges/local-player",
  categories: "/lol-challenges/v1/challenges/category-data",
  matches: "/lol-match-history/v1/products/lol/current-summoner/matches",
};

async function waitForConnectedLcu(app, request) {
  await expect.poll(async () => {
    const response = await request.get(`${app.baseURL}/api/health`);
    return (await response.json()).lcu_connected;
  }).toBe(true);
  await expect.poll(async () => {
    const response = await request.get(`${app.baseURL}/api/account/identity`);
    return (await response.json()).source;
  }).toBe("connected");
}

function accountFixture() {
  return {
    [accountPaths.summary]: {
      status: 200,
      payload: {
        summonerLevel: 321,
        profileIconId: 42,
        xpSinceLastLevel: 900,
        xpUntilNextLevel: 100,
        displayName: "PRIVATE_RIOT_ID_SENTINEL",
        puuid: "PRIVATE_PUUID_SENTINEL",
        token: "PRIVATE_TOKEN_SENTINEL",
        unexpected: "PRIVATE_UNKNOWN_SENTINEL",
      },
    },
    [accountPaths.ranked]: {
      status: 200,
      payload: {
        queueMap: {
          RANKED_SOLO_5x5: {
            tier: "gold",
            division: "II",
            leaguePoints: 23,
            wins: 14,
            losses: 9,
            puuid: "PRIVATE_PUUID_SENTINEL",
          },
          RANKED_FLEX_SR: { tier: "UNRANKED", division: "NA" },
        },
        futureField: "PRIVATE_UNKNOWN_SENTINEL",
      },
    },
    [accountPaths.masteries]: {
      status: 200,
      payload: Array.from({ length: 15 }, (_, index) => ({
        championId: index + 1,
        championLevel: 7,
        championPoints: (index + 1) * 100,
        lastPlayTime: 1234,
        chestGranted: true,
        puuid: "PRIVATE_PUUID_SENTINEL",
        unknown: "PRIVATE_UNKNOWN_SENTINEL",
      })),
    },
    [accountPaths.masteryScore]: {
      status: 503,
      payload: { token: "PRIVATE_TOKEN_SENTINEL" },
    },
    [accountPaths.challenges]: {
      status: 200,
      payload: {
        challenges: Array.from({ length: 10 }, (_, challengeId) => ({
          challengeId,
          value: 5,
          level: "GOLD",
          percentile: 12.5,
        })),
        totalPoints: { current: 765 },
        accountId: "PRIVATE_ACCOUNT_SENTINEL",
      },
    },
    [accountPaths.categories]: {
      status: 503,
      payload: { credential: "PRIVATE_TOKEN_SENTINEL" },
    },
    [accountPaths.matches]: {
      status: 200,
      payload: {
        games: {
          gameCount: 29,
          games: Array.from({ length: 25 }, (_, index) => ({
            gameId: 100 + index,
            gameCreation: 1_700_000_000_000,
            gameDuration: 1200,
            queueId: 420,
            participantIdentities: [{
              participantId: 1,
              player: {
                puuid: "otp-lol-e2e-puuid",
                summonerName: "PRIVATE_PLAYER_SENTINEL",
              },
            }],
            participants: [{
              participantId: 1,
              championId: 86,
              stats: {
                win: true,
                kills: 4,
                deaths: 2,
                assists: 7,
                unknown: "PRIVATE_UNKNOWN_SENTINEL",
              },
            }],
            rawCredential: "PRIVATE_CREDENTIAL_SENTINEL",
          })),
        },
      },
    },
  };
}

test("account API normalizes independent LCU sections and rejects private upstream fields", async ({ page }) => {
  const app = await startOtpApp();
  try {
    await waitForConnectedLcu(app, page.request);
    await app.configureLcuState({ account_responses: accountFixture() });

    const [summaryResponse, rankedResponse, masteriesResponse, challengesResponse, matchesResponse] = await Promise.all([
      page.request.get(`${app.baseURL}/api/account/summary`),
      page.request.get(`${app.baseURL}/api/account/ranked`),
      page.request.get(`${app.baseURL}/api/account/masteries`),
      page.request.get(`${app.baseURL}/api/account/challenges`),
      page.request.get(`${app.baseURL}/api/account/matches`),
    ]);
    expect([summaryResponse.status(), rankedResponse.status(), masteriesResponse.status(), challengesResponse.status(), matchesResponse.status()])
      .toEqual([200, 200, 200, 200, 200]);

    const summary = await summaryResponse.json();
    const ranked = await rankedResponse.json();
    const masteries = await masteriesResponse.json();
    const challenges = await challengesResponse.json();
    const matches = await matchesResponse.json();

    expect(summary).toMatchObject({
      data: { level: 321, profile_icon_id: 42, xp_since_last_level: 900, xp_until_next_level: 100 },
      available: true,
      stale: false,
      source: "lcu",
    });
    expect(ranked.data.queues).toEqual([
      { queue_type: "RANKED_SOLO_5x5", tier: "GOLD", division: "II", league_points: 23, wins: 14, losses: 9 },
      { queue_type: "RANKED_FLEX_SR", tier: "UNRANKED", division: "NA", league_points: null, wins: null, losses: null },
    ]);
    expect(masteries.data.champions).toHaveLength(10);
    expect(masteries.data.champions[0]).toMatchObject({ champion_id: 1, level: 7, points: 100 });
    expect(masteries).toMatchObject({ error: "partial_failure", errors: { score: "http_error" } });
    expect(challenges.data.challenges.challenges).toHaveLength(3);
    expect(challenges.data.challenges.total_points).toBe(765);
    expect(challenges.data.categories).toEqual([]);
    expect(challenges).toMatchObject({ error: "partial_failure", errors: { categories: "http_error" } });
    expect(matches.data).toMatchObject({ offset: 0, total: 29 });
    expect(matches.data.matches).toHaveLength(20);
    expect(matches.data.matches[0]).toMatchObject({ game_id: "100", champion_id: 86, win: true, kills: 4, deaths: 2, assists: 7 });

    const serialized = JSON.stringify([summary, ranked, masteries, challenges, matches]);
    for (const privateValue of [
      "PRIVATE_RIOT_ID_SENTINEL",
      "PRIVATE_PUUID_SENTINEL",
      "PRIVATE_TOKEN_SENTINEL",
      "PRIVATE_ACCOUNT_SENTINEL",
      "PRIVATE_PLAYER_SENTINEL",
      "PRIVATE_CREDENTIAL_SENTINEL",
      "PRIVATE_UNKNOWN_SENTINEL",
    ]) {
      expect(serialized).not.toContain(privateValue);
    }
    for (const path of Object.values(accountPaths)) {
      await app.waitForLcuRequest("GET", path);
    }
  } finally {
    await app.stop();
  }
});

test("a failed summary request does not make the independent ranked section unavailable", async ({ page }) => {
  const app = await startOtpApp();
  try {
    await waitForConnectedLcu(app, page.request);
    await app.configureLcuState({
      account_responses: {
        [accountPaths.summary]: { status: 503, payload: { detail: "PRIVATE_UPSTREAM_ERROR_SENTINEL" } },
        [accountPaths.ranked]: { status: 200, payload: { queueMap: {} } },
      },
    });
    const [summaryResponse, rankedResponse] = await Promise.all([
      page.request.get(`${app.baseURL}/api/account/summary`),
      page.request.get(`${app.baseURL}/api/account/ranked`),
    ]);
    const summary = await summaryResponse.json();
    const ranked = await rankedResponse.json();
    expect(summaryResponse.status()).toBe(200);
    expect(summary).toMatchObject({ data: null, available: false, stale: false, source: "unavailable", error: "http_error" });
    expect(JSON.stringify(summary)).not.toContain("PRIVATE_UPSTREAM_ERROR_SENTINEL");
    expect(rankedResponse.status()).toBe(200);
    expect(ranked).toMatchObject({ data: { queues: [] }, available: true, source: "lcu" });
  } finally {
    await app.stop();
  }
});

test("match detail and timeline are fetched only on their explicit API requests", async ({ page }) => {
  const app = await startOtpApp();
  const detailPath = "/lol-match-history/v1/games/4242";
  const timelinePath = "/lol-match-history/v1/game-timelines/4242";
  try {
    await waitForConnectedLcu(app, page.request);
    await app.configureLcuState({
      account_responses: {
        ...accountFixture(),
        [detailPath]: {
          status: 200,
          payload: {
            gameId: 4242,
            gameCreation: 1_700_000_000_000,
            gameDuration: 1400,
            queueId: 420,
            participants: [{
              championId: 86,
              teamId: 100,
              puuid: "PRIVATE_PUUID_SENTINEL",
              summonerName: "PRIVATE_NAME_SENTINEL",
              stats: { win: true, kills: 2, deaths: 3, assists: 4, goldEarned: 9000, item0: 1055, item1: 0, item6: 3400 },
            }],
            headers: { Authorization: "PRIVATE_HEADER_SENTINEL" },
          },
        },
        [timelinePath]: {
          status: 200,
          payload: {
            gameId: 4242,
            frames: [{ timestamp: 60000, events: [{
              type: "CHAMPION_KILL",
              timestamp: 65000,
              killerId: 2,
              victimId: 7,
              assistingParticipantIds: [3, "bad"],
              puuid: "PRIVATE_PUUID_SENTINEL",
              summonerName: "PRIVATE_NAME_SENTINEL",
            }, { type: "UNKNOWN_EVENT", timestamp: 66000, secret: "PRIVATE_UNKNOWN_SENTINEL" }] }],
          },
        },
      },
    });

    const matchesResponse = await page.request.get(`${app.baseURL}/api/account/matches`);
    expect(matchesResponse.status()).toBe(200);
    expect(app.lcuRequests.some(({ path }) => path.includes("/games/") || path.includes("game-timelines"))).toBe(false);

    const detailResponse = await page.request.get(`${app.baseURL}/api/account/matches/4242`);
    expect(detailResponse.status()).toBe(200);
    const detail = await detailResponse.json();
    expect(detail.data).toMatchObject({
      game_id: "4242",
      participants: [{ champion_id: 86, team_id: 100, win: true, kills: 2, deaths: 3, assists: 4, gold_earned: 9000, items: [1055, 3400] }],
    });
    expect(JSON.stringify(detail)).not.toMatch(/PRIVATE_(?:PUUID|NAME|HEADER|UNKNOWN)_SENTINEL/);
    await app.waitForLcuRequest("GET", detailPath);
    expect(app.lcuRequests.some(({ path }) => path.includes("game-timelines"))).toBe(false);

    const timelineResponse = await page.request.get(`${app.baseURL}/api/account/matches/4242/timeline`);
    expect(timelineResponse.status()).toBe(200);
    const timeline = await timelineResponse.json();
    expect(timeline.data).toMatchObject({
      game_id: "4242",
      events: [{ type: "CHAMPION_KILL", timestamp: 65000, killer_id: 2, victim_id: 7, assisting_participant_ids: [3] }],
    });
    expect(JSON.stringify(timeline)).not.toMatch(/PRIVATE_(?:PUUID|NAME|UNKNOWN)_SENTINEL/);
    await app.waitForLcuRequest("GET", timelinePath);
  } finally {
    await app.stop();
  }
});

test("match routes enrich queue, map, and item IDs from real cached LCU catalogues", async ({ page }) => {
  const app = await startOtpApp();
  try {
    await waitForConnectedLcu(app, page.request);
    await app.configureLcuState({
      static_data_online: true,
      account_responses: {
        ...accountFixture(),
        "/lol-match-history/v1/games/4242": {
          status: 200,
          payload: {
            gameId: 4242,
            gameCreation: 1_700_000_000_000,
            gameDuration: 1400,
            queueId: 420,
            participants: [{
              championId: 86,
              teamId: 100,
              stats: { win: true, kills: 2, deaths: 3, assists: 4, item0: 1001, item6: 0 },
            }],
          },
        },
      },
    });

    const catalogueResponse = await page.request.get(`${app.baseURL}/api/game-data/status`);
    expect(catalogueResponse.status()).toBe(200);
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/game-data/status`);
      return (await response.json()).catalogs;
    }).toMatchObject({ queues: true, maps: true, items: true });

    const detailResponse = await page.request.get(`${app.baseURL}/api/account/matches/4242`);
    expect(detailResponse.status()).toBe(200);
    const detail = await detailResponse.json();
    expect(detail.data).toMatchObject({
      queue_name: "Ranked Solo",
      map_name: "Summoner's Rift",
      item_names: { "1001": "Boots" },
      participants: [{ items: [1001] }],
    });
    await app.waitForLcuRequest("GET", "/lol-game-data/assets/v1/queues.json");
  } finally {
    await app.stop();
  }
});

test("account API rejects out-of-range limits and invalid game IDs before querying the LCU", async ({ page }) => {
  const app = await startOtpApp();
  try {
    await waitForConnectedLcu(app, page.request);
    const rejectedRequests = [
      "/api/account/masteries?limit=21",
      "/api/account/challenges?limit=51",
      "/api/account/matches?limit=21",
      "/api/account/matches/0",
      "/api/account/matches/18446744073709551616",
    ];
    for (const apiPath of rejectedRequests) {
      const response = await page.request.get(`${app.baseURL}${apiPath}`);
      expect(response.status(), apiPath).toBe(422);
    }

    expect(app.lcuRequests.some(({ path }) => (
      path.includes("champion-mastery")
      || path.includes("lol-challenges")
      || path.includes("current-summoner/matches")
      || path.includes("/games/")
    ))).toBe(false);
  } finally {
    await app.stop();
  }
});

test("corrupt account cache is reported without returning stored or upstream secrets", async ({ page }) => {
  const app = await startOtpApp();
  try {
    await waitForConnectedLcu(app, page.request);
    const responsePayloads = accountFixture();
    responsePayloads[accountPaths.summary] = {
      status: 200,
      payload: { summonerLevel: 88, puuid: "PRIVATE_PUUID_SENTINEL" },
    };
    await app.configureLcuState({ account_responses: responsePayloads });
    const freshResponse = await page.request.get(`${app.baseURL}/api/account/summary`);
    expect(await freshResponse.json()).toMatchObject({ data: { level: 88 }, source: "lcu" });

    const accountCacheDir = path.join(app.appDataDir, "OTP LOL", "cache", "account");
    const cacheFiles = await readdir(accountCacheDir);
    const accountCacheFile = cacheFiles.find((name) => /^account-[a-f0-9]{64}\.json$/.test(name));
    expect(accountCacheFile).toBeTruthy();
    await writeFile(path.join(accountCacheDir, accountCacheFile), "{broken cache", "utf8");

    responsePayloads[accountPaths.summary] = {
      status: 503,
      payload: { detail: "PRIVATE_UPSTREAM_ERROR_SENTINEL" },
    };
    await app.configureLcuState({ account_responses: responsePayloads });
    const corruptedResponse = await page.request.get(`${app.baseURL}/api/account/summary`);
    const corruptedBody = await corruptedResponse.json();
    expect(corruptedResponse.status()).toBe(200);
    expect(corruptedBody).toMatchObject({
      data: null,
      available: false,
      stale: false,
      source: "unavailable",
      error: "http_error",
      errors: { summary: "http_error", cache: "cache_corrupt" },
    });
    expect(JSON.stringify(corruptedBody)).not.toContain("PRIVATE_UPSTREAM_ERROR_SENTINEL");
    expect((await readdir(accountCacheDir)).filter((name) => name.endsWith(".tmp"))).toEqual([]);
  } finally {
    await app.stop();
  }
});

test("account cache files stay scoped to each PUUID across a League account switch", async ({ page }) => {
  const app = await startOtpApp();
  try {
    await waitForConnectedLcu(app, page.request);
    await app.configureLcuState({
      account_responses: {
        [accountPaths.summary]: { status: 200, payload: { summonerLevel: 20 } },
      },
    });
    const firstResponse = await page.request.get(`${app.baseURL}/api/account/summary`);
    expect(await firstResponse.json()).toMatchObject({ data: { level: 20 }, source: "lcu" });
    await app.waitForWebSocketSubscription();

    await app.configureLcuConnection({ online: false });
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/health`);
      return (await response.json()).lcu_connected;
    }).toBe(false);
    await app.configureLcuState({
      account_responses: {
        "/lol-chat/v1/me": {
          status: 200,
          payload: {
            gameName: "Another E2E Player",
            gameTag: "OTHER",
            summonerId: 13579246,
            puuid: "SECOND_ACCOUNT_PUUID_SENTINEL",
          },
        },
        [accountPaths.summary]: { status: 200, payload: { summonerLevel: 40 } },
      },
    });
    await app.configureLcuConnection({ online: true });
    await waitForConnectedLcu(app, page.request);
    await app.waitForWebSocketSubscription(2);

    const secondResponse = await page.request.get(`${app.baseURL}/api/account/summary`);
    expect(await secondResponse.json()).toMatchObject({ data: { level: 40 }, source: "lcu" });
    const accountCacheDir = path.join(app.appDataDir, "OTP LOL", "cache", "account");
    const accountFiles = (await readdir(accountCacheDir))
      .filter((name) => /^account-[a-f0-9]{64}\.json$/.test(name));
    expect(accountFiles).toHaveLength(2);
    const cachedLevels = await Promise.all(accountFiles.map(async (name) => {
      const document = JSON.parse(await readFile(path.join(accountCacheDir, name), "utf8"));
      return document.sections.summary.data.level;
    }));
    expect(cachedLevels.sort((left, right) => left - right)).toEqual([20, 40]);
    const allCacheText = await Promise.all(accountFiles.map((name) => readFile(path.join(accountCacheDir, name), "utf8")));
    expect(allCacheText.join("\n")).not.toContain("SECOND_ACCOUNT_PUUID_SENTINEL");

    await app.configureLcuConnection({ online: false });
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/health`);
      return (await response.json()).lcu_connected;
    }).toBe(false);
    const offlineResponse = await page.request.get(`${app.baseURL}/api/account/summary`);
    expect(await offlineResponse.json()).toMatchObject({
      data: { level: 40 },
      available: true,
      stale: true,
      source: "cache",
      errors: { summary: "disconnected" },
    });

    const identityChange = await page.request.patch(`${app.baseURL}/api/settings`, {
      headers: { Origin: new URL(app.baseURL).origin },
      data: {
        summoner_name_auto_detect: false,
        manual_summoner_name: "Unrelated Player#9999",
        manual_region: "na",
      },
    });
    expect(identityChange.status()).toBe(200);
    expect(await (await page.request.get(`${app.baseURL}/api/account/identity`)).json()).toMatchObject({
      riot_id: "Unrelated Player#9999",
      source: "manual",
      connected: false,
    });
    expect(await (await page.request.get(`${app.baseURL}/api/account/summary`)).json()).toMatchObject({
      data: { level: 40 },
      available: true,
      stale: true,
      source: "cache",
      errors: { summary: "disconnected" },
    });
  } finally {
    await app.stop();
  }
});

test("account stats cache stays tied to LCU identity when manual provider identity differs", async ({ page }) => {
  let app = await startOtpApp();
  try {
    await waitForConnectedLcu(app, page.request);
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/settings`);
      return (await response.json()).auto_detected_account_valid;
    }).toBe(true);
    const accountIdentity = await (await page.request.get(`${app.baseURL}/api/account/identity`)).json();
    expect(accountIdentity).toMatchObject({ source: "connected", connected: true });
    const responsePayloads = accountFixture();
    await app.configureLcuState({ account_responses: responsePayloads });

    const firstSummary = await (await page.request.get(`${app.baseURL}/api/account/summary`)).json();
    expect(firstSummary).toMatchObject({ data: { level: 321 }, source: "lcu", stale: false });
    const accountCacheDir = path.join(app.appDataDir, "OTP LOL", "cache", "account");
    const pointerPath = path.join(accountCacheDir, "last-account.json");
    const lcuPointer = JSON.parse(await readFile(pointerPath, "utf8"));
    expect(lcuPointer.identity_key).toMatch(/^[a-f0-9]{64}$/);

    const manualRiotId = "Manual Account#9999";
    const manualRegion = "na";
    const identityChange = await page.request.patch(`${app.baseURL}/api/settings`, {
      headers: { Origin: new URL(app.baseURL).origin },
      data: {
        summoner_name_auto_detect: false,
        manual_summoner_name: manualRiotId,
        manual_region: manualRegion,
      },
    });
    expect(identityChange.status()).toBe(200);
    expect(await (await page.request.get(`${app.baseURL}/api/account/identity`)).json()).toMatchObject({
      riot_id: manualRiotId,
      source: "manual",
    });

    const [summary, matches] = await Promise.all([
      page.request.get(`${app.baseURL}/api/account/summary`),
      page.request.get(`${app.baseURL}/api/account/matches`),
    ]);
    expect(await summary.json()).toMatchObject({ data: { level: 321 }, source: "lcu", stale: false });
    expect(await matches.json()).toMatchObject({ data: { total: 29 }, source: "lcu", stale: false });
    const manualIdentityKey = createHash("sha256")
      .update(`${manualRegion}|${manualRiotId.toLowerCase()}`)
      .digest("hex");
    expect(JSON.parse(await readFile(pointerPath, "utf8"))).toEqual(lcuPointer);
    expect(lcuPointer.identity_key).not.toBe(manualIdentityKey);

    const retainedStateDir = app.stateDir;
    await app.stop({ retainState: true });
    app = await startOtpApp({ stateDir: retainedStateDir });
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/health`);
      return (await response.json()).lcu_connected;
    }).toBe(true);
    await app.waitForWebSocketSubscription();
    await app.configureLcuConnection({ online: false });
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/health`);
      return (await response.json()).lcu_connected;
    }).toBe(false);

    expect(await (await page.request.get(`${app.baseURL}/api/account/identity`)).json()).toMatchObject({
      riot_id: manualRiotId,
      source: "manual",
      connected: false,
    });
    const [offlineSummary, offlineMatches] = await Promise.all([
      page.request.get(`${app.baseURL}/api/account/summary`),
      page.request.get(`${app.baseURL}/api/account/matches`),
    ]);
    expect(await offlineSummary.json()).toMatchObject({
      data: { level: 321 },
      available: true,
      stale: true,
      source: "cache",
    });
    expect(await offlineMatches.json()).toMatchObject({
      data: { total: 29 },
      available: true,
      stale: true,
      source: "cache",
    });
    expect(JSON.parse(await readFile(pointerPath, "utf8"))).toEqual(lcuPointer);
  } finally {
    await app.stop();
  }
});

test("offline stats stay unavailable when the profile has no saved account identity", async ({ page }) => {
  const app = await startOtpApp();
  try {
    await waitForConnectedLcu(app, page.request);
    await app.configureLcuState({
      account_responses: {
        [accountPaths.summary]: { status: 200, payload: { summonerLevel: 73 } },
      },
    });
    expect(await (await page.request.get(`${app.baseURL}/api/account/summary`)).json()).toMatchObject({
      data: { level: 73 },
      source: "lcu",
      stale: false,
    });

    await app.configureLcuConnection({ online: false });
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/health`);
      return (await response.json()).lcu_connected;
    }).toBe(false);
    const clearedIdentity = await page.request.delete(`${app.baseURL}/api/settings/last-detected-account`, {
      headers: { Origin: new URL(app.baseURL).origin },
    });
    expect(clearedIdentity.status()).toBe(200);
    expect(await (await page.request.get(`${app.baseURL}/api/account/identity`)).json()).toMatchObject({
      riot_id: null,
      source: "unavailable",
    });

    expect(await (await page.request.get(`${app.baseURL}/api/account/summary`)).json()).toMatchObject({
      data: null,
      available: false,
      stale: false,
      source: "unavailable",
      errors: { summary: "disconnected" },
    });
  } finally {
    await app.stop();
  }
});

test("same-profile restart serves the previous account cache while disconnected", async ({ page }) => {
  let app = await startOtpApp();
  let shutdown;
  try {
    await waitForConnectedLcu(app, page.request);
    const responsePayloads = accountFixture();
    responsePayloads[accountPaths.summary] = {
      status: 200,
      payload: {
        summonerLevel: 88,
        puuid: "PRIVATE_PUUID_SENTINEL",
        displayName: "PRIVATE_RIOT_ID_SENTINEL",
        rawCredential: "PRIVATE_CREDENTIAL_SENTINEL",
      },
    };
    await app.configureLcuState({ account_responses: responsePayloads });

    const freshResponse = await page.request.get(`${app.baseURL}/api/account/summary`);
    expect(freshResponse.status()).toBe(200);
    expect(await freshResponse.json()).toMatchObject({ data: { level: 88 }, source: "lcu", stale: false });

    const accountCacheDir = path.join(app.appDataDir, "OTP LOL", "cache", "account");
    const cacheFiles = await readdir(accountCacheDir);
    const accountCacheFile = cacheFiles.find((name) => /^account-[a-f0-9]{64}\.json$/.test(name));
    expect(accountCacheFile).toBeTruthy();
    const cacheText = await readFile(path.join(accountCacheDir, accountCacheFile), "utf8");
    const identityPointer = await readFile(path.join(accountCacheDir, "last-account.json"), "utf8");
    expect(JSON.parse(identityPointer).identity_key).toMatch(/^[a-f0-9]{64}$/);
    for (const privateValue of ["PRIVATE_PUUID_SENTINEL", "PRIVATE_RIOT_ID_SENTINEL"]) {
      expect(cacheText).not.toContain(privateValue);
      expect(identityPointer).not.toContain(privateValue);
    }

    responsePayloads[accountPaths.summary] = {
      status: 503,
      payload: { detail: "PRIVATE_UPSTREAM_ERROR_SENTINEL" },
    };
    await app.configureLcuState({ account_responses: responsePayloads });
    const fallbackResponse = await page.request.get(`${app.baseURL}/api/account/summary`);
    const fallbackBody = await fallbackResponse.json();
    expect(fallbackBody).toMatchObject({
      data: { level: 88 },
      available: true,
      stale: true,
      source: "cache",
      errors: { summary: "http_error" },
    });
    expect(JSON.stringify(fallbackBody)).not.toContain("PRIVATE_UPSTREAM_ERROR_SENTINEL");

    const retainedStateDir = app.stateDir;
    shutdown = await app.stop({ retainState: true });
    expect(shutdown.forced).toBe(false);
    app = await startOtpApp({ stateDir: retainedStateDir });
    await waitForConnectedLcu(app, page.request);
    await app.waitForWebSocketSubscription();
    await app.configureLcuConnection({ online: false });
    await expect.poll(async () => {
      const health = await page.request.get(`${app.baseURL}/api/health`);
      return (await health.json()).lcu_connected;
    }).toBe(false);

    const offlineResponse = await page.request.get(`${app.baseURL}/api/account/summary`);
    expect(offlineResponse.status()).toBe(200);
    expect(await offlineResponse.json()).toMatchObject({
      data: { level: 88 },
      available: true,
      stale: true,
      source: "cache",
      errors: { summary: "disconnected" },
    });
  } finally {
    await app.stop();
  }
});

test("same-profile restart serves cached matches while disconnected", async ({ page }) => {
  let app = await startOtpApp();
  try {
    await waitForConnectedLcu(app, page.request);
    await app.configureLcuState({ account_responses: accountFixture() });
    const freshResponse = await page.request.get(`${app.baseURL}/api/account/matches`);
    expect(freshResponse.status()).toBe(200);
    const freshBody = await freshResponse.json();
    expect(freshBody).toMatchObject({
      data: { offset: 0, total: 29 },
      source: "lcu",
      stale: false,
    });
    expect(freshBody.data.matches[0]).toMatchObject({ game_id: "100", champion_id: 86 });

    const retainedStateDir = app.stateDir;
    await app.stop({ retainState: true });
    app = await startOtpApp({ stateDir: retainedStateDir });
    await waitForConnectedLcu(app, page.request);
    await app.waitForWebSocketSubscription();
    await app.configureLcuConnection({ online: false });
    await expect.poll(async () => {
      const health = await page.request.get(`${app.baseURL}/api/health`);
      return (await health.json()).lcu_connected;
    }).toBe(false);

    const offlineResponse = await page.request.get(`${app.baseURL}/api/account/matches`);
    expect(offlineResponse.status()).toBe(200);
    const offlineBody = await offlineResponse.json();
    expect(offlineBody).toMatchObject({
      data: { offset: 0, total: 29 },
      available: true,
      stale: true,
      source: "cache",
      errors: { matches: "disconnected" },
    });
    expect(offlineBody.data.matches[0]).toMatchObject({ game_id: "100", champion_id: 86 });
  } finally {
    await app.stop();
  }
});

test("offline restart does not attribute an unaliased legacy cache pointer to an account", async ({ page }) => {
  let app = await startOtpApp();
  try {
    await waitForConnectedLcu(app, page.request);
    const responsePayloads = accountFixture();
    responsePayloads[accountPaths.summary] = {
      status: 200,
      payload: { summonerLevel: 61, puuid: "LEGACY_POINTER_PUUID_SENTINEL" },
    };
    await app.configureLcuState({ account_responses: responsePayloads });
    expect(await (await page.request.get(`${app.baseURL}/api/account/summary`)).json()).toMatchObject({
      data: { level: 61 },
      source: "lcu",
    });

    const accountCacheDir = path.join(app.appDataDir, "OTP LOL", "cache", "account");
    const pointerPath = path.join(accountCacheDir, "last-account.json");
    const pointer = JSON.parse(await readFile(pointerPath, "utf8"));
    delete pointer.identity_key;
    await writeFile(pointerPath, JSON.stringify(pointer));

    const retainedStateDir = app.stateDir;
    await app.stop({ retainState: true });
    app = await startOtpApp({ stateDir: retainedStateDir });
    await waitForConnectedLcu(app, page.request);
    await app.waitForWebSocketSubscription();
    await app.configureLcuConnection({ online: false });
    await expect.poll(async () => {
      const health = await page.request.get(`${app.baseURL}/api/health`);
      return (await health.json()).lcu_connected;
    }).toBe(false);

    expect(await (await page.request.get(`${app.baseURL}/api/account/summary`)).json()).toMatchObject({
      data: null,
      available: false,
      stale: false,
      source: "unavailable",
      errors: { summary: "disconnected" },
    });
  } finally {
    await app.stop();
  }
});
