import { expect, test as playwrightTest, type Browser, type BrowserContext, type Page, type TestInfo } from "@playwright/test";

type ExternalState = { dataDragon?: "online" | "offline"; updates?: "offline" | "available" | "none" };

export interface OtpApp {
  baseURL: string;
  appDataDir: string;
  syntheticLeaguePid: number | null;
  lcuRequests: Array<{ method: string; path: string; body: unknown }>;
  websocketSubscriptions: unknown[];
  externalRequestsBlocked: Array<{ host: string; port: number | null; path: string }>;
  externalFixtureRequests: Array<{ host: string; port: number | null; path: string; status: number }>;
  configureLcuState(state: Record<string, unknown>): Promise<void>;
  readLcuState(): Promise<Record<string, any>>;
  configureLcuConnection(state: { online: boolean }): Promise<void>;
  configureExternalState(state: ExternalState): Promise<{ state: ExternalState }>;
  waitForWebSocketSubscription(count: number): Promise<unknown>;
  emitLcuEvent(uri: string, data: unknown): Promise<void>;
  waitForLcuRequest(method: string, path: string): Promise<{ method: string; path: string; body: unknown }>;
  waitForLcuResponse(method: string, path: string, status: number): Promise<{
    method: string;
    path: string;
    status: number;
    body: unknown;
    complete: true;
  }>;
  stop(): Promise<{
    forced: boolean;
    code: number | null;
    stderr: string;
    syntheticLeagueStopped: boolean;
    cleanupWarnings: unknown[];
    socketEgressBlocked: unknown[];
    socketConnections: Array<{ host: string; port: number }>;
    externalRequestsBlocked: Array<{ host: string; port: number | null; path: string }>;
  }>;
}

type AppServerModule = { startOtpApp(): Promise<OtpApp> };
type OtpFixtures = { otpApp: OtpApp };
const appByPage = new WeakMap<Page, OtpApp>();

export const test = playwrightTest.extend<OtpFixtures>({
  otpApp: async ({}, use) => {
    const { startOtpApp } = await import("../../scripts/e2e/appServer.mjs") as AppServerModule;
    const app = await startOtpApp();
    let primaryError: unknown;
    let hasPrimaryError = false;
    try {
      await app.waitForLcuRequest("GET", "/lol-chat/v1/me");
      await use(app);
    } catch (error) {
      primaryError = error;
      hasPrimaryError = true;
    }

    let cleanupError: unknown;
    let hasCleanupError = false;
    try {
      const shutdown = await app.stop();
      if (
        shutdown.forced
        || shutdown.code !== 0
        || !shutdown.syntheticLeagueStopped
        || shutdown.cleanupWarnings.length
        || shutdown.socketEgressBlocked.length
        || shutdown.externalRequestsBlocked.length
      ) {
        throw new Error(`Full-stack E2E cleanup failed: ${JSON.stringify(shutdown)}`);
      }
    } catch (error) {
      cleanupError = error;
      hasCleanupError = true;
    }

    if (hasPrimaryError && hasCleanupError) {
      throw new AggregateError([primaryError, cleanupError], "Full-stack E2E failed and cleanup also reported an error.");
    }
    if (hasPrimaryError) {
      throw primaryError;
    }
    if (hasCleanupError) {
      throw cleanupError;
    }
  },
  page: async ({ browser, otpApp }, use, testInfo) => {
    const context = await createOtpContext(browser, otpApp, testInfo);
    const page = await context.newPage();
    appByPage.set(page, otpApp);
    await use(page);
    await context.close();
  },
});

export { expect };

export async function createOtpContext(
  browser: Browser,
  app: OtpApp,
  testInfo: TestInfo,
  options: { viewport?: { width: number; height: number }; deviceScaleFactor?: number } = {},
): Promise<BrowserContext> {
  const projectUse = testInfo.project.use as { viewport?: { width: number; height: number } | null; deviceScaleFactor?: number };
  const context = await browser.newContext({
    baseURL: app.baseURL,
    acceptDownloads: true,
    viewport: options.viewport ?? projectUse.viewport ?? { width: 1280, height: 720 },
    deviceScaleFactor: options.deviceScaleFactor ?? projectUse.deviceScaleFactor ?? 1,
  });
  const origin = new URL(app.baseURL).origin;
  await context.route("**/*", async (route) => {
    if (new URL(route.request().url()).origin === origin) await route.continue();
    else await route.abort("blockedbyclient");
  });
  return context;
}

export async function createOtpPage(
  browser: Browser,
  app: OtpApp,
  testInfo: TestInfo,
  options: { viewport?: { width: number; height: number }; deviceScaleFactor?: number } = {},
): Promise<{ context: BrowserContext; page: Page }> {
  const context = await createOtpContext(browser, app, testInfo, options);
  const page = await context.newPage();
  appByPage.set(page, app);
  return { context, page };
}

export function getOtpApp(page: Page): OtpApp {
  const app = appByPage.get(page);
  if (!app) throw new Error("The current Playwright page is not backed by the full-stack OTP LOL fixture.");
  return app;
}

export function waitForRuntimeEvents(page: Page) {
  return page.waitForEvent("websocket", (socket) => new URL(socket.url()).pathname === "/api/events");
}

type SetupOptions = {
  // `connected` selects a League gameflow phase. The synthetic LCU transport is
  // connected for every test unless a test explicitly changes it via the app helper.
  connected?: boolean;
  configured?: boolean;
  onboardingCompleted?: boolean;
  assignedPosition?: string;
  phase?: string;
  autoDetect?: boolean;
  manualRiotId?: string;
  region?: string;
  autoAccept?: boolean;
  autoPick?: boolean;
  autoBan?: boolean;
  autoSummoners?: boolean;
  autoPlayAgain?: boolean;
  skinAutomation?: boolean;
  networkStatus?: "online" | "offline";
  updateStatus?: "offline" | "available" | "none";
  ignoredUpdateVersion?: string;
  clearDetectedAccount?: boolean;
  settings?: Record<string, unknown>;
  lcuState?: Record<string, unknown>;
};

async function api<T>(page: Page, method: string, path: string, data?: unknown): Promise<T> {
  const origin = new URL(getOtpApp(page).baseURL).origin;
  const response = await page.request.fetch(new URL(path, origin).href, {
    method,
    data,
    headers: { Origin: origin },
  });
  if (!response.ok()) {
    throw new Error(`${method} ${path} failed with ${response.status()}: ${await response.text()}`);
  }
  return await response.json() as T;
}

export async function readSettings(page: Page): Promise<Record<string, any>> {
  return api(page, "GET", "/api/settings");
}

export async function readPresets(page: Page): Promise<Record<string, any>> {
  return api(page, "GET", "/api/presets");
}

export async function readRuntime(page: Page): Promise<Record<string, any>> {
  return api(page, "GET", "/api/runtime");
}

export async function readHistory(page: Page): Promise<{ items: Array<Record<string, any>>; count: number }> {
  return api(page, "GET", "/api/history?limit=250");
}

export async function setupApplication(page: Page, options: SetupOptions = {}): Promise<{
  app: OtpApp;
  settings: Record<string, any>;
  presets: Record<string, any>;
  runtime: Record<string, any>;
}> {
  const app = getOtpApp(page);
  const connected = options.connected ?? false;
  const phase = options.phase ?? (connected ? "Lobby" : "None");
  const initialRunePage = {
    id: 401,
    name: "E2E Top",
    primaryStyleId: 8000,
    subStyleId: 8100,
    selectedPerkIds: [8005, 8008, 9101, 8014, 8106, 8120, 5008, 5008, 5011],
    current: true,
    isValid: true,
  };

  const reconnecting = app.syntheticLeaguePid === null;
  await app.configureLcuConnection({ online: true });
  const subscriptionNumber = reconnecting ? app.websocketSubscriptions.length + 1 : 1;
  await app.waitForWebSocketSubscription(subscriptionNumber);
  await app.configureLcuState({
    static_data_online: false,
    game_version: "16.1.1",
    region: options.lcuState?.region ?? "EUW",
    platform: options.lcuState?.platform ?? "EUW1",
    ready_check: { state: "InProgress", playerResponse: "None" },
    pickable_champion_ids: [],
    pickable_skins: [],
    rune_pages: [initialRunePage],
    current_rune_page: initialRunePage,
  });
  await app.configureExternalState({
    dataDragon: options.networkStatus ?? "online",
    updates: options.updateStatus ?? "offline",
  });
  await api(page, "POST", "/api/settings/reset");
  await api(page, "DELETE", "/api/history");
  await app.emitLcuEvent("/lol-chat/v1/me", {});
  await expect.poll(async () => (await readSettings(page)).auto_detected_riot_id).toBe("E2E Player#SAFE");
  if (options.configured || options.onboardingCompleted === false) {
    await api(page, "POST", "/api/presets/reset");
  } else {
    await api(page, "POST", "/api/presets/clear");
  }

  if (options.configured) {
    await api(page, "PUT", "/api/presets/pick_1", {
      champion: "Garen", spell_1: "Flash", spell_2: "Ignite", skin_mode: "fixed",
      skin_id: 86013, skin_name: "God-King Garen", skin_num: 13,
      rune_page_id: 401, rune_page_name: "E2E Top", rune_auto_apply: true,
    });
  }

  const settings: Record<string, unknown> = {
    onboarding_completed: options.onboardingCompleted ?? true,
    presets_enabled: Boolean(options.configured),
    skin_automation_enabled: Boolean(options.configured),
    auto_accept_enabled: options.autoAccept ?? false,
    auto_pick_enabled: options.autoPick ?? false,
    auto_ban_enabled: options.autoBan ?? false,
    auto_summoners_enabled: options.autoSummoners ?? false,
    auto_play_again_enabled: options.autoPlayAgain ?? false,
    ignored_update_version: options.ignoredUpdateVersion ?? "",
    ...options.settings,
  };
  if (options.autoDetect === false) {
    settings.summoner_name_auto_detect = false;
    settings.manual_summoner_name = options.manualRiotId ?? "Manual#EUW";
    settings.manual_region = options.region ?? "euw";
  } else if (options.manualRiotId) {
    settings.manual_summoner_name = options.manualRiotId;
  }
  await api(page, "PATCH", "/api/settings", settings);
  if (options.clearDetectedAccount) await api(page, "DELETE", "/api/settings/last-detected-account");

  const networkStatus = options.networkStatus ?? "online";
  await api(page, "POST", "/api/network/check");
  if (networkStatus === "online") await api(page, "GET", "/api/game-data/status");

  const session = {
    gameConfig: { queueId: 420, gameMode: "CLASSIC" },
    localPlayerCellId: 1,
    myTeam: [{ cellId: 1, summonerId: 24680135, assignedPosition: options.assignedPosition ?? "TOP", championId: 0, spell1Id: 0, spell2Id: 0, selectedRunePageId: 0, selectedSkinId: 0 }],
    actions: [],
    bans: { myTeamBans: [], theirTeamBans: [] },
    ...(options.lcuState?.session as Record<string, unknown> | undefined),
  };
  await app.configureLcuState({ ...options.lcuState, phase, session });
  await app.emitLcuEvent("/lol-gameflow/v1/gameflow-phase", phase);
  if (phase === "ChampSelect") await app.emitLcuEvent("/lol-champ-select/v1/session", session);
  return {
    app,
    settings: await readSettings(page),
    presets: await readPresets(page),
    runtime: await api(page, "GET", "/api/runtime"),
  };
}
