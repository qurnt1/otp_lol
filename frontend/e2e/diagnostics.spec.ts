import { expect, test } from "@playwright/test";

import { mockLocalApi } from "./helpers";

test("diagnostics explains the disconnected state and disables live checks when League is offline", async ({ page }) => {
  await mockLocalApi(page, { connected: false });
  await page.goto("/#diagnostics");

  const offlineNotice = page.locator(".diagnostics-note[role='status']");
  await expect(offlineNotice).toBeVisible();
  await expect(offlineNotice).toContainText("League");
  await expect(page.getByRole("button", { name: /Tester les endpoints/ })).toBeDisabled();
  await expect(page.getByRole("button", { name: /Exporter le rapport/ })).toBeEnabled();
});

test("diagnostics is hidden from permanent navigation and reachable from advanced settings", async ({ page }) => {
  await mockLocalApi(page, { connected: true });
  await page.goto("/#settings/advanced");

  await expect(page.getByRole("button", { name: "Diagnostics LCU" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Navigation principale" }).getByRole("link", { name: "Diagnostics LCU" })).toHaveCount(0);
  await page.getByRole("button", { name: "Diagnostics LCU" }).click();

  await expect(page).toHaveURL(/#diagnostics$/);
  await expect(page.getByRole("heading", { name: "Diagnostics LCU" })).toBeVisible();
  await expect(page.getByText("Cache local")).toBeVisible();
  await expect(page.locator(".diagnostics-test-list code").filter({ hasText: "GET /lol-gameflow/v1/gameflow-phase" })).toBeVisible();
});

test("diagnostics runs only fixed checks, filters redacted events, and makes identity export opt-in", async ({ page }) => {
  const exportRequests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname === "/api/diagnostics/export") exportRequests.push(url.searchParams.get("include_riot_id") ?? "missing");
  });
  await mockLocalApi(page, { connected: true });
  await page.goto("/#diagnostics");

  await page.getByRole("button", { name: "Tester les endpoints sûrs" }).click();
  await expect(page.locator(".diagnostics-test-list").getByText("200 · 2.4 ms")).toBeVisible();
  await expect(page.getByText("Game phase")).toBeVisible();
  await page.reload();
  await expect(page.locator(".diagnostics-test-list").getByText("200 · 2.4 ms")).toBeVisible();
  await page.getByRole("searchbox", { name: "Filtrer les journaux" }).fill("gameflow");
  await expect(page.locator(".diagnostics-log-list").getByText("GET /lol-gameflow/v1/gameflow-phase")).toBeVisible();

  const firstDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exporter le rapport" }).click();
  expect((await firstDownload).suggestedFilename()).toBe("otp-lol-diagnostics.json");
  expect(exportRequests).toEqual(["false"]);

  await page.getByRole("checkbox", { name: "Inclure mon Riot ID dans l’export" }).check();
  const optedInDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exporter le rapport" }).click();
  await optedInDownload;
  expect(exportRequests).toEqual(["false", "true"]);
});

test("diagnostic event payload is available only in the JSON drawer", async ({ page }) => {
  await mockLocalApi(page, { connected: true });
  await page.route("**/api/diagnostics", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        runtime: { connected: true, phase: "ChampSelect" },
        account_identity: { riot_id: "Player#EUW", region: "euw", platform_id: "euw1", regional_routing: "europe", routing_source: "platform_config", source: "connected", connected: true },
        game_data: { source: "cache", game_version: "16.18.1", cache_available: true, cache_version: "16.18.1", catalogs: {} },
        requests: [],
        events: [{ timestamp: "2026-09-18T10:00:00Z", topic: "/lol-gameflow/v1/gameflow-phase", event_type: "Update", summary: "Lobby", payload: { phase: "Lobby" }, payload_truncated: false, payload_redacted: false }],
        errors: [],
        endpoint_checks: [],
        endpoint_results: [],
      }),
    });
  });
  await page.goto("/#diagnostics");

  await expect(page.locator(".diagnostics-log-row pre")).toHaveCount(0);
  await page.getByRole("button", { name: "Voir JSON" }).click();
  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();
  await expect(drawer.locator("pre")).toContainText('"phase": "Lobby"');
  await drawer.getByRole("button", { name: "Fermer" }).click();
  await expect(drawer).toBeHidden();
});

test("diagnostics filters include runtime automation, static data, WebView and errors", async ({ page }) => {
  await mockLocalApi(page, { connected: true });
  await page.route("**/api/diagnostics", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        runtime: { connected: true, phase: "ChampSelect" },
        account_identity: { riot_id: "Player#EUW", region: "euw", platform_id: "euw1", regional_routing: "europe", routing_source: "platform_config", source: "connected", connected: true },
        game_data: { source: "lcu", game_version: "16.18.1", cache_available: true, cache_version: "16.18.1" },
        requests: [],
        events: [
          { timestamp: "2026-09-18T10:00:04Z", topic: "/lol-gameflow/v1/gameflow-phase", event_type: "Update", summary: "ChampSelect", payload: {}, payload_truncated: false, payload_redacted: false },
          { timestamp: "2026-09-18T10:00:03Z", topic: "otp-lol/status", event_type: "Update", summary: "ban_confirmed", payload: { action: "ban_confirmed" }, payload_truncated: false, payload_redacted: false },
          { timestamp: "2026-09-18T10:00:02Z", topic: "otp-lol/data/static-data", event_type: "refresh", summary: "refreshed=true", payload: {}, payload_truncated: false, payload_redacted: false },
          { timestamp: "2026-09-18T10:00:01Z", topic: "otp-lol/webview", event_type: "created", summary: "object keys: ", payload: {}, payload_truncated: false, payload_redacted: false },
        ],
        errors: [{ timestamp: "2026-09-18T10:00:00Z", source: "static_data", error: "request_error", method: null, path: null, status: null }],
        endpoint_checks: [],
        endpoint_results: [],
      }),
    });
  });
  await page.goto("/#diagnostics");

  for (const [label, expected] of [
    ["LCU", "/lol-gameflow/v1/gameflow-phase"],
    ["Automation", "otp-lol/status"],
    ["Données", "otp-lol/data/static-data"],
    ["WebView", "otp-lol/webview"],
    ["Erreurs", "static_data"],
  ]) {
    await page.getByRole("button", { name: label, exact: true }).click();
    await expect(page.locator(".diagnostics-log-row").first()).toContainText(expected);
  }
});
