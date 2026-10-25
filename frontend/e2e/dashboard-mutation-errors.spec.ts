import type { Page, Route } from "@playwright/test";

import { expect, readSettings, setupApplication, test } from "./helpers";

type SettingsKey = "presets_enabled" | "auto_accept_enabled";

function interceptFirstSettingsPatch(page: Page, key: SettingsKey, status: number) {
  let release!: () => void;
  let reportStarted!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  const started = new Promise<void>((resolve) => { reportStarted = resolve; });
  let matchingPatches = 0;

  const routeHandler = async (route: Route) => {
    const request = route.request();
    if (request.method() === "PATCH" && Object.hasOwn(request.postDataJSON(), key)) {
      matchingPatches += 1;
      if (matchingPatches === 1) {
        reportStarted();
        await gate;
        await route.fulfill({ status, contentType: "application/json", body: JSON.stringify({ detail: "Injected Dashboard settings failure" }) });
        return;
      }
    }
    await route.continue();
  };

  return {
    install: () => page.route("**/api/settings", routeHandler),
    started,
    release,
    get matchingPatches() { return matchingPatches; },
  };
}

function holdSettingsPatch(page: Page, key: SettingsKey) {
  let release!: () => void;
  let reportStarted!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  const started = new Promise<void>((resolve) => { reportStarted = resolve; });
  let matchingPatches = 0;

  const routeHandler = async (route: Route) => {
    const request = route.request();
    if (request.method() === "PATCH" && Object.hasOwn(request.postDataJSON(), key)) {
      matchingPatches += 1;
      if (matchingPatches === 1) {
        reportStarted();
        await gate;
      }
    }
    await route.continue();
  };

  return {
    install: () => page.route("**/api/settings", routeHandler),
    started,
    release,
    get matchingPatches() { return matchingPatches; },
  };
}

test("Dashboard master rolls back a rejected PATCH and can be retried", async ({ page }) => {
  await setupApplication(page, { configured: true, settings: { presets_enabled: false } });
  await page.goto("/#dashboard");

  const master = page.getByRole("switch", { name: "Utiliser les presets en sélection" });
  await expect(master).toHaveAttribute("aria-checked", "false");
  const failure = interceptFirstSettingsPatch(page, "presets_enabled", 503);
  await failure.install();

  const rejected = page.waitForResponse((response) =>
    response.request().method() === "PATCH"
      && new URL(response.url()).pathname === "/api/settings"
      && response.status() === 503,
  );
  await master.click();
  await failure.started;
  await expect(master).toHaveAttribute("aria-checked", "true");
  await expect(master).toHaveAttribute("aria-busy", "true");
  await expect(master).toBeDisabled();
  failure.release();
  expect((await rejected).status()).toBe(503);

  await expect(master).toHaveAttribute("aria-checked", "false");
  await expect(master).toHaveAttribute("aria-busy", "false");
  await expect(master).toBeEnabled();
  await expect(page.getByRole("alert")).toHaveText("Impossible d’enregistrer la modification.");
  await expect.poll(async () => (await readSettings(page)).presets_enabled).toBe(false);
  expect(failure.matchingPatches).toBe(1);

  await page.unroute("**/api/settings");
  const saved = page.waitForResponse((response) =>
    response.request().method() === "PATCH"
      && new URL(response.url()).pathname === "/api/settings"
      && response.status() === 200,
  );
  await master.click();
  expect((await saved).status()).toBe(200);
  await expect(master).toHaveAttribute("aria-checked", "true");
  await expect.poll(async () => (await readSettings(page)).presets_enabled).toBe(true);
});

test("Dashboard child switch rolls back a rejected PATCH and can be retried", async ({ page }) => {
  await setupApplication(page, { configured: true, autoAccept: false });
  await page.goto("/#dashboard");

  const child = page.getByRole("switch", { name: "Auto-Accept" });
  await expect(child).toHaveAttribute("aria-checked", "false");
  const failure = interceptFirstSettingsPatch(page, "auto_accept_enabled", 503);
  await failure.install();

  const rejected = page.waitForResponse((response) =>
    response.request().method() === "PATCH"
      && new URL(response.url()).pathname === "/api/settings"
      && response.status() === 503,
  );
  await child.click();
  await failure.started;
  await expect(child).toHaveAttribute("aria-checked", "true");
  await expect(child).toHaveAttribute("aria-busy", "true");
  await expect(child).toBeDisabled();
  failure.release();
  expect((await rejected).status()).toBe(503);

  await expect(child).toHaveAttribute("aria-checked", "false");
  await expect(child).toHaveAttribute("aria-busy", "false");
  await expect(child).toBeEnabled();
  await expect(page.getByRole("alert")).toHaveText("Impossible d’enregistrer ce réglage.");
  await expect.poll(async () => (await readSettings(page)).auto_accept_enabled).toBe(false);
  expect(failure.matchingPatches).toBe(1);

  await page.unroute("**/api/settings");
  const saved = page.waitForResponse((response) =>
    response.request().method() === "PATCH"
      && new URL(response.url()).pathname === "/api/settings"
      && response.status() === 200,
  );
  await child.click();
  expect((await saved).status()).toBe(200);
  await expect(child).toHaveAttribute("aria-checked", "true");
  await expect.poll(async () => (await readSettings(page)).auto_accept_enabled).toBe(true);
});

test("Dashboard master and child switches ignore a second click while PATCH is pending", async ({ page }) => {
  await setupApplication(page, { configured: true, settings: { presets_enabled: false }, autoAccept: false });
  await page.goto("/#dashboard");

  const master = page.getByRole("switch", { name: "Utiliser les presets en sélection" });
  await expect(master).toBeEnabled();
  const masterPatch = holdSettingsPatch(page, "presets_enabled");
  await masterPatch.install();
  const masterSaved = page.waitForResponse((response) =>
    response.request().method() === "PATCH"
      && new URL(response.url()).pathname === "/api/settings"
      && response.status() === 200,
  );
  await master.click();
  await expect.poll(() => masterPatch.matchingPatches).toBe(1);
  await masterPatch.started;
  await expect(master).toHaveAttribute("aria-busy", "true");
  await expect(master).toBeDisabled();
  let bounds = await master.boundingBox();
  expect(bounds).not.toBeNull();
  await page.mouse.dblclick(bounds!.x + bounds!.width / 2, bounds!.y + bounds!.height / 2);
  expect(masterPatch.matchingPatches).toBe(1);
  masterPatch.release();
  expect((await masterSaved).status()).toBe(200);
  await expect.poll(async () => (await readSettings(page)).presets_enabled).toBe(true);
  expect(masterPatch.matchingPatches).toBe(1);
  await page.unroute("**/api/settings");

  const child = page.getByRole("switch", { name: "Auto-Accept" });
  await expect(child).toBeEnabled();
  const childPatch = holdSettingsPatch(page, "auto_accept_enabled");
  await childPatch.install();
  const childSaved = page.waitForResponse((response) =>
    response.request().method() === "PATCH"
      && new URL(response.url()).pathname === "/api/settings"
      && response.status() === 200,
  );
  await child.click();
  await expect.poll(() => childPatch.matchingPatches).toBe(1);
  await childPatch.started;
  await expect(child).toHaveAttribute("aria-busy", "true");
  await expect(child).toBeDisabled();
  bounds = await child.boundingBox();
  expect(bounds).not.toBeNull();
  await page.mouse.dblclick(bounds!.x + bounds!.width / 2, bounds!.y + bounds!.height / 2);
  expect(childPatch.matchingPatches).toBe(1);
  childPatch.release();
  expect((await childSaved).status()).toBe(200);
  await expect.poll(async () => (await readSettings(page)).auto_accept_enabled).toBe(true);
  expect(childPatch.matchingPatches).toBe(1);
});
