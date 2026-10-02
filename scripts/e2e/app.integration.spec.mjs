import { expect, test } from "../../frontend/node_modules/@playwright/test/index.mjs";
import path from "node:path";
import { startOtpApp } from "./appServer.mjs";

function isWithinPath(root, candidate) {
  const relativePath = path.relative(root, candidate);
  return relativePath === ""
    || (!path.isAbsolute(relativePath)
      && relativePath !== ".."
      && !relativePath.startsWith(`..${path.sep}`));
}

test("real UI reconnects to the retained LCU after application restart without replaying mutations", async ({ page }) => {
  test.setTimeout(120_000);
  let app = await startOtpApp();
  let appOrigin = new URL(app.baseURL).origin;
  let firstShutdown;
  let finalProcessExternalFixtures = [];
  let primaryError;
  let hasPrimaryError = false;
  let cleanupError;
  const externalBrowserRequests = new Set();
  const runtimeEvents = [];
  const staticDataPaths = [
    "/lol-patch/v1/game-version",
    "/lol-game-data/assets/v1/champion-summary.json",
    "/lol-game-data/assets/v1/summoner-spells.json",
    "/lol-game-data/assets/v1/perks.json",
    "/lol-game-data/assets/v1/items.json",
    "/lol-game-data/assets/v1/maps.json",
    "/lol-game-data/assets/v1/queues.json",
  ];
  const expectedCatalogueNames = ["champions", "spells", "perks", "items", "maps", "queues"];
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin === appOrigin) {
      await route.continue();
    } else {
      externalBrowserRequests.add(url.href);
      await route.abort("blockedbyclient");
    }
  });
  page.on("request", (request) => {
    if (new URL(request.url()).origin !== appOrigin) externalBrowserRequests.add(request.url());
  });
  page.on("websocket", (socket) => {
    if (new URL(socket.url()).pathname !== "/api/events") return;
    socket.on("framereceived", ({ payload }) => {
      try {
        runtimeEvents.push(JSON.parse(typeof payload === "string" ? payload : payload.toString()));
      } catch {
        // Ignore non-JSON WebSocket frames.
      }
    });
  });
  try {
    await app.configureExternalState({ dataDragon: "offline", updates: "offline" });
    expect(Number.isInteger(app.syntheticLeaguePid)).toBe(true);
    expect(app.processDiscovery).toMatchObject({
      syntheticPid: app.syntheticLeaguePid,
      parsedPort: Number(new URL(app.lcuURL).port),
      networkOpened: false,
      driverProcessFilter: "synthetic PID only",
      filterSymbol: "lcu_driver.utils.process_iter",
    });
    expect(app.pathIsolation.appDataPathNames).toContain("parameters");
    expect(app.pathIsolation.tempPathNames).toContain("lockfile");
    expect(app.pathIsolation.localAppDataIsolated).toBe(true);
    const { resolvedRoots, resolvedPaths } = app.pathIsolation;
    for (const rootName of ["appData", "localAppData", "temp"]) {
      expect(
        isWithinPath(resolvedRoots.state, resolvedRoots[rootName]),
        `${rootName} root escaped the isolated profile: ${resolvedRoots[rootName]}`,
      ).toBe(true);
    }
    for (const [rootName, paths] of Object.entries(resolvedPaths)) {
      for (const [name, resolvedPath] of Object.entries(paths)) {
        expect(
          isWithinPath(resolvedRoots[rootName], resolvedPath),
          `${name} escaped its isolated ${rootName} root: ${resolvedPath}`,
        ).toBe(true);
      }
    }
    expect(app.socketGuardProof).toEqual(["connect", "connect_ex", "sendto"]);
    expect(app.lcuDiscovery).toContain("unfiltered production scan/argument parsing verified without connecting");
    await app.waitForLcuRequest("GET", "/lol-chat/v1/me");
    await app.waitForLcuRequest("GET", staticDataPaths[0]);
    await expect.poll(() => app.websocketSubscription).toMatchObject({
      type: "lcu-websocket-subscribed",
      protocol: "wss",
      host: "127.0.0.1",
      port: Number(new URL(app.lcuURL).port),
    });

    const runtimeEventsSocketPromise = page.waitForEvent(
      "websocket",
      (socket) => new URL(socket.url()).pathname === "/api/events",
    );
    await page.goto(app.baseURL, { waitUntil: "domcontentloaded" });
    const runtimeEventsSocket = await runtimeEventsSocketPromise;
    await runtimeEventsSocket.waitForEvent("framereceived");
    await expect(page.getByRole("heading", { name: "Préparation de partie" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Réessayer maintenant" })).toBeVisible();
    const offlineUpdatesResponse = await page.request.get(`${app.baseURL}/api/updates`);
    expect(await offlineUpdatesResponse.json()).toEqual({ available: false, update: null });
    await expect.poll(() => app.externalFixtureRequests.some((request) =>
      request.host === "api.github.com"
      && request.path === "/repos/qurnt1/otp_lol/releases/latest"
      && request.status === 503
    )).toBe(true);
    await app.configureExternalState({ dataDragon: "online" });
    await page.getByRole("button", { name: "Réessayer maintenant" }).click();
    await expect(page.getByText("Connexion Internet indisponible")).toHaveCount(0);
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/network/status`);
      return (await response.json()).state;
    }).toBe("online");

    await page.locator(".priority-card").first().click();
    const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
    await expect(editor).toBeVisible();
    await editor.locator(".champion-choice").click();
    const championDialog = page.getByRole("dialog", { name: "Choisir un champion" });
    const championSearch = championDialog.getByLabel("Rechercher un champion…");
    await championSearch.fill("Ashe");
    await championDialog.getByRole("button", { name: "Top", exact: true }).click();
    await expect(championDialog.getByText("Aucun résultat.")).toBeVisible();
    await championSearch.fill("Garen");
    await expect(championDialog.getByRole("option", { name: /Garen/ })).toBeVisible();
    await championDialog.getByRole("option", { name: /Garen/ }).click();
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/presets`);
      return (await response.json()).slots.pick_1.champion;
    }).toBe("Garen");

    await editor.getByRole("radio", { name: "Aucun" }).click();
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/presets`);
      return (await response.json()).slots.pick_1.skin_mode;
    }).toBe("none");
    await editor.getByRole("radio", { name: "Fixe" }).click();
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/presets`);
      return (await response.json()).slots.pick_1.skin_mode;
    }).toBe("fixed");
    await editor.getByRole("button", { name: /Galerie des skins/ }).click();
    const skinDialog = page.getByRole("dialog", { name: "Galerie des skins" });
    const commandoSkin = skinDialog.locator(".skin-option").filter({ hasText: "Commando Garen" });
    await expect(commandoSkin).toBeVisible();
    await commandoSkin.getByRole("button", { name: "Choisir" }).click();
    await expect(commandoSkin.getByRole("button", { name: "Sélectionné" })).toBeVisible();
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/presets`);
      const slot = (await response.json()).slots.pick_1;
      return { mode: slot.skin_mode, id: slot.skin_id, name: slot.skin_name };
    }).toEqual({ mode: "fixed", id: 86001, name: "Commando Garen" });
    await page.keyboard.press("Escape");

    await editor.locator(".preset-editor-runes .editor-choice").click();
    const runeDialog = page.getByRole("dialog", { name: "Runes" });
    const e2eRunePage = runeDialog.getByRole("button", { name: /E2E Top/ });
    await expect(e2eRunePage).toBeVisible();
    await e2eRunePage.click();
    await expect(e2eRunePage).toHaveAttribute("aria-pressed", "true");
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/presets`);
      const slot = (await response.json()).slots.pick_1;
      return { id: slot.rune_page_id, name: slot.rune_page_name };
    }).toEqual({ id: 401, name: "E2E Top" });
    await page.keyboard.press("Escape");
    await editor.getByRole("button", { name: "Fermer" }).last().click();
    await expect(editor).toHaveCount(0);

    await page.getByRole("link", { name: "Réglages" }).click();
    await page.getByRole("button", { name: "Général", exact: true }).click();
    const closeOnExit = page.getByRole("switch", { name: "Fermer lorsque League est réellement fermé" });
    await expect(closeOnExit).toHaveAttribute("aria-checked", "true");
    await closeOnExit.click();
    await expect(closeOnExit).toHaveAttribute("aria-checked", "false");
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/settings`);
      return (await response.json()).close_app_on_lol_exit;
    }).toBe(false);

    await page.getByRole("button", { name: "Automatisations", exact: true }).click();

    const autoAccept = page.getByRole("switch", { name: "Auto-Accept" });
    await expect(autoAccept).toHaveAttribute("aria-checked", "false");
    await autoAccept.click();
    await expect(autoAccept).toHaveAttribute("aria-checked", "true");
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/settings`);
      return (await response.json()).auto_accept_enabled;
    }).toBe(true);
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/settings`);
      return (await response.json()).close_app_on_lol_exit;
    }).toBe(false);

    await app.configureLcuState({ region: "NA", platform: "NA1", phase: "Matchmaking" });
    await app.emitLcuEvent("/lol-gameflow/v1/gameflow-phase", "Matchmaking");
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/runtime`);
      return (await response.json()).phase;
    }).toBe("Matchmaking");
    const accountRefresh = await app.emitLcuEvent("/lol-chat/v1/me", {
      gameName: "E2E Player",
      gameTag: "SAFE",
    });
    await app.waitForLcuEventCompletion(accountRefresh.id);
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/account/identity`);
      const identity = await response.json();
      return { riotId: identity.riot_id, region: identity.region, platform: identity.platform_id };
    }).toEqual({ riotId: "E2E Player#SAFE", region: "na", platform: "na1" });
    await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", {
      state: "InProgress",
      playerResponse: "None",
    });
    await app.waitForLcuRequest("POST", "/lol-matchmaking/v1/ready-check/accept");
    await expect.poll(async () => (await app.readLcuState()).ready_check.playerResponse).toBe("Accepted");

    const firstApiPort = Number(new URL(app.baseURL).port);
    const firstLcuPort = Number(new URL(app.lcuURL).port);
    const fakeLeaguePid = app.syntheticLeaguePid;
    const controllerPid = app.controllerPid;
    const acceptCountBeforeApiRestart = app.lcuRequests.filter((request) =>
      request.method === "POST" && request.path === "/lol-matchmaking/v1/ready-check/accept",
    ).length;
    expect(acceptCountBeforeApiRestart).toBe(1);
    const subscriptionsBeforeApiRestart = app.websocketSubscriptions.length;
    const accountReadsBeforeRestart = app.lcuRequests.filter((request) =>
      request.method === "GET" && request.path === "/lol-chat/v1/me",
    ).length;
    await app.configureLcuState({
      account_responses: {
        "/lol-chat/v1/me": {
          status: 200,
          payload: { gameName: "Reloaded User", gameTag: "LIVE", summonerId: 24680135 },
        },
      },
    });
    const applicationGenerationBeforeRestart = app.applicationGeneration;
    const applicationRestart = await app.restartApplication();
    expect(applicationRestart.generation).toBe(applicationGenerationBeforeRestart + 1);
    expect(applicationRestart.controllerPid).toBe(controllerPid);
    expect(applicationRestart.oldContextStopped).toBe(true);
    expect(applicationRestart.contextRecreated).toBe(true);
    expect(applicationRestart.appRecreated).toBe(true);
    expect(applicationRestart.syntheticLeaguePid).toBe(fakeLeaguePid);
    expect(applicationRestart.lcuPort).toBe(firstLcuPort);
    expect(app.syntheticLeaguePid).toBe(fakeLeaguePid);
    const restartedApiPort = Number(new URL(app.baseURL).port);
    appOrigin = new URL(app.baseURL).origin;
    const restartedApiUrl = new URL(app.baseURL);
    const restartedRuntimeEventsSocketPromise = page.waitForEvent(
      "websocket",
      (socket) => new URL(socket.url()).host === restartedApiUrl.host
        && new URL(socket.url()).pathname === "/api/events",
    );
    await page.goto(app.baseURL, { waitUntil: "domcontentloaded" });
    const restartedRuntimeEventsSocket = await restartedRuntimeEventsSocketPromise;
    await restartedRuntimeEventsSocket.waitForEvent("framereceived");
    await expect(page.getByRole("heading", { name: "Préparation de partie" })).toBeVisible();

    const restartedSubscription = await app.waitForWebSocketSubscription(subscriptionsBeforeApiRestart + 1);
    expect(restartedSubscription).toMatchObject({
      protocol: "wss",
      host: "127.0.0.1",
      port: firstLcuPort,
    });
    expect(app.syntheticLeaguePid).toBe(fakeLeaguePid);
    expect(app.websocketSubscriptions).toHaveLength(subscriptionsBeforeApiRestart + 1);
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/runtime`);
      return (await response.json()).connected;
    }).toBe(true);
    await expect.poll(() => app.lcuRequests.filter((request) =>
      request.method === "GET" && request.path === "/lol-chat/v1/me",
    ).length).toBeGreaterThan(accountReadsBeforeRestart);
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/account/identity`);
      const identity = await response.json();
      return { riotId: identity.riot_id, region: identity.region, platform: identity.platform_id };
    }).toEqual({ riotId: "Reloaded User#LIVE", region: "na", platform: "na1" });
    const phaseRefresh = await app.emitLcuEvent("/lol-gameflow/v1/gameflow-phase", "Matchmaking");
    await app.waitForLcuEventCompletion(phaseRefresh.id);
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/runtime`);
      return (await response.json()).phase;
    }).toBe("Matchmaking");
    const restartedSettingsResponse = await page.request.get(`${app.baseURL}/api/settings`);
    expect((await restartedSettingsResponse.json()).auto_accept_enabled).toBe(true);
    await expect(page.getByRole("switch", { name: "Auto-Accept" })).toHaveAttribute("aria-checked", "true");
    await expect(page.locator(".sidebar-runtime")).toHaveAttribute("aria-label", "Client connecté");
    await expect(page.locator(".sidebar-account")).toContainText("Reloaded User#LIVE");
    expect(app.lcuRequests.filter((request) =>
      request.method === "POST" && request.path === "/lol-matchmaking/v1/ready-check/accept",
    )).toHaveLength(acceptCountBeforeApiRestart);
    await expect(page.locator(".phase-strip strong")).toHaveText("Recherche de partie");

    await app.configureLcuState({
      ready_check: { state: "InProgress", playerResponse: "None" },
    });
    const readyCheckPhaseEvent = await app.emitLcuEvent("/lol-gameflow/v1/gameflow-phase", "ReadyCheck");
    await app.waitForLcuEventCompletion(readyCheckPhaseEvent.id);
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/runtime`);
      return (await response.json()).phase;
    }).toBe("ReadyCheck");
    expect(app.lcuRequests.filter((request) =>
      request.method === "POST" && request.path === "/lol-matchmaking/v1/ready-check/accept",
    )).toHaveLength(acceptCountBeforeApiRestart);
    const freshReadyCheckEvent = await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", {
      state: "InProgress",
      playerResponse: "None",
    });
    await app.waitForLcuEventCompletion(freshReadyCheckEvent.id);
    await expect.poll(() => app.lcuRequests.filter((request) =>
      request.method === "POST" && request.path === "/lol-matchmaking/v1/ready-check/accept",
    ).length).toBe(acceptCountBeforeApiRestart + 1);
    await expect.poll(async () => (await app.readLcuState()).ready_check.playerResponse).toBe("Accepted");
    expect(app.lcuRequests.filter((request) =>
      request.method === "POST" && request.path === "/lol-matchmaking/v1/ready-check/accept",
    ).slice(acceptCountBeforeApiRestart)).toHaveLength(1);

    const retainedStateDir = app.stateDir;
    await expect.poll(() => runtimeEvents.some((event) => event.type === "runtime_snapshot")).toBe(true);
    firstShutdown = await app.stop({ retainState: true });
    expect(firstShutdown.forced, firstShutdown.stderr).toBe(false);
    expect(firstShutdown.code, firstShutdown.stderr).toBe(0);
    expect(firstShutdown.stateRetained).toBe(true);
    expect(firstShutdown.syntheticLeagueStopped).toBe(true);
    expect(firstShutdown.cleanupWarnings).toEqual([]);
    expect(firstShutdown.socketEgressBlocked).toEqual([]);
    expect(firstShutdown.socketConnections.length).toBeGreaterThan(0);
    expect(firstShutdown.socketConnections.every((connection) =>
      connection.host === "127.0.0.1"
      && [firstApiPort, restartedApiPort, firstLcuPort].includes(connection.port)
    )).toBe(true);
    expect(firstShutdown.externalRequestsBlocked).toEqual([]);

    app = await startOtpApp({ stateDir: retainedStateDir });
    appOrigin = new URL(app.baseURL).origin;
    await page.goto(app.baseURL, { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Préparation de partie" })).toBeVisible();
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/settings`);
      return (await response.json()).auto_accept_enabled;
    }).toBe(true);
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/settings`);
      return (await response.json()).close_app_on_lol_exit;
    }).toBe(false);
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/presets`);
      const slot = (await response.json()).slots.pick_1;
      return {
        champion: slot.champion,
        skin: slot.skin_name,
        runePage: slot.rune_page_name,
      };
    }).toEqual({ champion: "Garen", skin: "Commando Garen", runePage: "E2E Top" });

    await app.waitForLcuRequest("GET", "/lol-chat/v1/me");
    await expect.poll(() => app.websocketSubscription).toMatchObject({
      type: "lcu-websocket-subscribed",
      protocol: "wss",
      host: "127.0.0.1",
      port: Number(new URL(app.lcuURL).port),
    });

    await app.emitLcuEvent("/lol-gameflow/v1/gameflow-phase", "Matchmaking");
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/runtime`);
      return (await response.json()).phase;
    }).toBe("Matchmaking");

    await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", {
      state: "InProgress",
      playerResponse: "None",
    });
    const accepted = await app.waitForLcuRequest(
      "POST",
      "/lol-matchmaking/v1/ready-check/accept",
    );
    expect(accepted.body).toBeNull();
    expect(accepted.host).toBe("127.0.0.1");
    expect(accepted.port).toBe(Number(new URL(app.lcuURL).port));
    expect((await app.readLcuState()).ready_check.playerResponse).toBe("Accepted");

    const persistedSettings = await page.request.get(`${app.baseURL}/api/settings`);
    expect((await persistedSettings.json()).auto_accept_enabled).toBe(true);

    const firstSyntheticPid = app.syntheticLeaguePid;
    const chatIdentityRequestsBeforeDisconnect = app.lcuRequests.filter(
      (request) => request.method === "GET" && request.path === "/lol-chat/v1/me",
    ).length;
    const routingRequestsBeforeDisconnect = app.lcuRequests.filter(
      (request) => request.method === "GET" && request.path === "/riotclient/region-locale",
    ).length;
    const staticDataRequestCountsBeforeDisconnect = Object.fromEntries(
      staticDataPaths.map((requestPath) => [
        requestPath,
        app.lcuRequests.filter((request) => request.method === "GET" && request.path === requestPath).length,
      ]),
    );
    const offlineState = await app.configureLcuConnection({ online: false });
    expect(offlineState).toMatchObject({ online: false, pid: null, closedWebsockets: 1 });
    expect(app.syntheticLeaguePid).toBeNull();
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/runtime`);
      return (await response.json()).connected;
    }).toBe(false);
    const gameDataEventsBeforeReconnect = runtimeEvents.filter(
      (event) => event.type === "game_data_updated",
    ).length;
    await app.configureLcuState({
      static_data_online: true,
      game_version: "16.1.2",
      region: "NA",
      platform: "NA1",
    });

    const onlineState = await app.configureLcuConnection({ online: true });
    expect(onlineState).toMatchObject({ online: true, alreadyInState: false });
    expect(onlineState.pid).not.toBe(firstSyntheticPid);
    expect(app.syntheticLeaguePid).toBe(onlineState.pid);
    const reconnected = await app.waitForWebSocketSubscription(2);
    expect(reconnected).toMatchObject({
      protocol: "wss",
      host: "127.0.0.1",
      port: Number(new URL(app.lcuURL).port),
    });
    for (const requestPath of staticDataPaths) {
      await expect.poll(() => app.lcuRequests.filter(
        (request) => request.method === "GET" && request.path === requestPath,
      ).length).toBeGreaterThan(staticDataRequestCountsBeforeDisconnect[requestPath]);
    }
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/runtime`);
      return (await response.json()).connected;
    }).toBe(true);
    await expect.poll(() => app.lcuRequests.filter(
      (request) => request.method === "GET" && request.path === "/lol-chat/v1/me",
    ).length).toBeGreaterThan(chatIdentityRequestsBeforeDisconnect);
    await expect.poll(() => app.lcuRequests.filter(
      (request) => request.method === "GET" && request.path === "/riotclient/region-locale",
    ).length).toBeGreaterThan(routingRequestsBeforeDisconnect);
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/account/identity`);
      const identity = await response.json();
      return { riotId: identity.riot_id, region: identity.region, platform: identity.platform_id };
    }).toEqual({ riotId: "E2E Player#SAFE", region: "na", platform: "na1" });
    await expect.poll(() => runtimeEvents.filter(
      (event) => event.type === "game_data_updated",
    ).length).toBeGreaterThan(gameDataEventsBeforeReconnect);
    await expect.poll(() => runtimeEvents.some(
      (event) => event.type === "game_data_updated" && event.data?.game_version === "16.1.2",
    )).toBe(true);
    const staticDataUpdatedEvent = runtimeEvents.findLast(
      (event) => event.type === "game_data_updated" && event.data?.game_version === "16.1.2",
    );
    expect(staticDataUpdatedEvent.data.source).toBe("lcu");
    expect(Object.keys(staticDataUpdatedEvent.data.catalogs).sort()).toEqual(expectedCatalogueNames.slice().sort());
    expect(expectedCatalogueNames.every((name) => staticDataUpdatedEvent.data.catalogs[name]?.available === true)).toBe(true);
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/game-data/status`);
      const status = await response.json();
      return {
        source: status.source,
        gameVersion: status.game_version,
        catalogueNames: Object.keys(status.catalogs).sort(),
        catalogsAvailable: expectedCatalogueNames.every((name) => status.catalogs[name] === true),
      };
    }).toEqual({
      source: "lcu",
      gameVersion: "16.1.2",
      catalogueNames: expectedCatalogueNames.slice().sort(),
      catalogsAvailable: true,
    });

    await app.emitLcuEvent("/lol-gameflow/v1/gameflow-phase", "Lobby");
    await expect.poll(async () => {
      const response = await page.request.get(`${app.baseURL}/api/runtime`);
      return (await response.json()).phase;
    }).toBe("Lobby");
    await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", {
      state: "InProgress",
      playerResponse: "None",
    });
    await expect.poll(() => app.lcuRequests.filter((request) =>
      request.method === "POST" && request.path === "/lol-matchmaking/v1/ready-check/accept"
    ).length).toBe(2);
    expect(app.lcuRequests.at(-1)).toMatchObject({
      method: "POST",
      path: "/lol-matchmaking/v1/ready-check/accept",
      body: null,
      host: "127.0.0.1",
      port: Number(new URL(app.lcuURL).port),
    });
    expect((await app.readLcuState()).ready_check.playerResponse).toBe("Accepted");

    const externalState = await app.configureExternalState({ updates: "available" });
    expect(externalState.state).toMatchObject({ dataDragon: "online", updates: "available" });
    const updatesResponse = await page.request.get(`${app.baseURL}/api/updates`);
    const updatesPayload = await updatesResponse.json();
    expect(updatesResponse.status()).toBe(200);
    expect(updatesPayload).toMatchObject({
      available: true,
      update: { version: "99.0", asset_name: "OTP-LOL-Setup.exe" },
    });
    const releaseFixtureEvent = await app.waitForExternalFixtureRequest(
      "api.github.com",
      "/repos/qurnt1/otp_lol/releases/latest",
      200,
    );
    const releaseFixtureRequests = app.externalFixtureRequests.filter((request) =>
      request.host === "api.github.com"
      && request.path === "/repos/qurnt1/otp_lol/releases/latest"
    );
    expect(releaseFixtureRequests, JSON.stringify({
      externalState,
      updatesStatus: updatesResponse.status(),
      updatesPayload,
      releaseFixtureRequests,
      allFixtureRequests: app.externalFixtureRequests,
    }, null, 2)).toContainEqual(releaseFixtureEvent);
  } catch (error) {
    primaryError = error;
    hasPrimaryError = true;
  } finally {
    finalProcessExternalFixtures = app.externalFixtureRequests;
    try {
      const shutdown = await app.stop();
      expect(shutdown.forced, shutdown.stderr).toBe(false);
      expect(shutdown.code, shutdown.stderr).toBe(0);
      expect(shutdown.syntheticLeagueStopped).toBe(true);
      expect(shutdown.cleanupWarnings).toEqual([]);
      expect([...externalBrowserRequests]).toEqual([]);
      expect(shutdown.socketEgressBlocked).toEqual([]);
      const expectedLocalPorts = [Number(new URL(app.baseURL).port), Number(new URL(app.lcuURL).port)];
      expect(shutdown.socketConnections.length).toBeGreaterThan(0);
      expect(shutdown.socketConnections.every((connection) =>
        connection.host === "127.0.0.1" && expectedLocalPorts.includes(connection.port)
      )).toBe(true);
      const blockedExternalRequests = [
        ...(firstShutdown?.externalRequestsBlocked ?? []),
        ...shutdown.externalRequestsBlocked,
      ];
      expect(blockedExternalRequests).toEqual([]);
      const allExternalFixtures = [
        ...(firstShutdown?.externalFixtureRequests ?? []),
        ...finalProcessExternalFixtures,
        ...shutdown.externalFixtureRequests,
      ];
      expect(allExternalFixtures.some((request) =>
        request.host === "ddragon.leagueoflegends.com"
        && request.path === "/api/versions.json"
        && request.status === 503
      )).toBe(true);
      expect(allExternalFixtures.some((request) =>
        request.host === "ddragon.leagueoflegends.com"
        && request.path === "/api/versions.json"
        && request.status === 200
      ), JSON.stringify(allExternalFixtures, null, 2)).toBe(true);
      expect(allExternalFixtures.some((request) =>
        request.host === "ddragon.leagueoflegends.com"
        && request.path === "/cdn/16.1.1/data/en_US/champion.json"
        && request.status === 200
      )).toBe(true);
      expect(allExternalFixtures.some((request) =>
        request.host === "api.github.com"
        && request.path === "/repos/qurnt1/otp_lol/releases/latest"
        && request.status === 503
      )).toBe(true);
    } catch (error) {
      cleanupError = error;
    }
  }

  if (hasPrimaryError && cleanupError) {
    throw new AggregateError([primaryError, cleanupError], "Full-stack smoke failed and cleanup assertions also failed.");
  }
  if (hasPrimaryError) throw primaryError;
  if (cleanupError) throw cleanupError;
});
