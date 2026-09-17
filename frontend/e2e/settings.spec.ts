import { expect, test } from "@playwright/test";

import { mockLocalApi } from "./helpers";

test("settings persists an accessible toggle", async ({ page }) => {
  await mockLocalApi(page);
  await page.goto("/#settings");
  const toggle = page.getByRole("switch", { name: "Masquer à la connexion" });
  await expect(toggle).toHaveAttribute("aria-checked", "true");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", "false");
});

test("custom settings select supports keyboard navigation and Escape", async ({ page }) => {
  await mockLocalApi(page);
  await page.goto("/#settings");
  await page.getByRole("button", { name: "Apparence" }).click();

  const theme = page.getByRole("combobox", { name: "Thème" });
  await theme.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("option", { name: "Clair" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("option", { name: "Clair" })).toBeHidden();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

  await theme.focus();
  await page.keyboard.press("Enter");
  const lightOption = page.getByRole("option", { name: "Clair" });
  await expect(lightOption).toBeVisible();
  await page.keyboard.press("ArrowDown");
  await expect(lightOption).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await theme.click();
  await expect(page.getByRole("option", { name: "Sombre" })).toBeVisible();
  await page.keyboard.press("Escape");
});

test("settings advanced actions are grouped and the section title is not duplicated", async ({ page }) => {
  await page.setViewportSize({ width: 1100, height: 760 });
  await mockLocalApi(page);
  await page.goto("/#settings");
  await page.getByRole("button", { name: "Avancé" }).click();

  await expect(page.locator(".page-heading .eyebrow")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Avancé", exact: true })).toHaveCount(1);
  await expect(page.getByRole("heading", { name: "Avancé", exact: true })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Avancé" })).toBeVisible();
  await expect(page.locator(".advanced-group")).toHaveCount(3);
  await expect(page.locator(".advanced-action")).toHaveCount(6);
  await expect(page.locator(".settings-section")).toHaveScreenshot("settings-advanced.png", { animations: "disabled" });
  await expect(page.locator(".advanced-actions").first()).toHaveCSS("grid-template-columns", /\d+(\.\d+)?px \d+(\.\d+)?px/);
  const firstRowBounds = await page.locator(".advanced-actions").first().locator(".advanced-action").evaluateAll((actions) => actions.slice(0, 2).map((action) => {
    const { x, y, width } = action.getBoundingClientRect();
    return { x, y, width };
  }));
  expect(Math.abs(firstRowBounds[0].y - firstRowBounds[1].y)).toBeLessThan(1);
  expect(Math.abs(firstRowBounds[0].width - firstRowBounds[1].width)).toBeLessThan(1);
  await page.getByRole("button", { name: "Apparence" }).click();
  await page.getByRole("combobox", { name: "Thème" }).click();
  await page.getByRole("option", { name: "Clair" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByRole("button", { name: "Avancé" }).click();
  await page.setViewportSize({ width: 800, height: 540 });
  await expect(page.getByRole("region", { name: "Avancé" })).toBeVisible();
  await expect(page.locator(".advanced-group")).toHaveCount(3);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("automatic account field shows the live Riot ID and preserves the saved manual value", async ({ page }) => {
  const state = await mockLocalApi(page, {
    connected: true,
    autoDetect: true,
    autoDetectedRiotId: "Detected#Live",
    riotId: "Detected#Live",
    manualRiotId: "Saved#Manual",
  });
  await page.goto("/#settings/account");

  const riotId = page.getByRole("textbox", { name: "Riot ID" });
  const detection = page.getByRole("switch", { name: "Utiliser un Riot ID manuel" });
  await expect(detection).toHaveAttribute("aria-checked", "false");
  await expect(riotId).toBeDisabled();
  await expect(riotId).toHaveValue("Detected#Live");

  await detection.click();
  await expect(riotId).toBeEnabled();
  await expect(riotId).toHaveValue("Saved#Manual");
  await detection.click();
  await expect(riotId).toBeDisabled();
  await expect(riotId).toHaveValue("Detected#Live");
  expect(state.settings.manual_summoner_name).toBe("Saved#Manual");
});

test("automatic account input follows a new live runtime snapshot and never shows the saved manual ID offline", async ({ page }) => {
  const state = await mockLocalApi(page, { connected: true, riotId: "Old#Tag", autoDetectedRiotId: "Old#Tag", manualRiotId: "Saved#Manual" });
  await page.goto("/#settings/account");
  const riotId = page.getByRole("textbox", { name: "Riot ID" });
  await expect(riotId).toHaveValue("Old#Tag");

  state.settings.auto_detected_riot_id = "Stale#Tag";
  state.runtime.riot_id = "Fresh#Tag";
  await page.evaluate((runtime) => {
    const emit = (window as Window & { __otpEmitRuntimeEvent?: (event: unknown) => void }).__otpEmitRuntimeEvent;
    emit?.({ type: "summoner_update", data: {}, timestamp: "2026-09-16T12:00:00Z" });
    emit?.({ type: "runtime_snapshot", data: runtime, timestamp: "2026-09-16T12:00:00Z" });
  }, state.runtime);
  await expect(riotId).toHaveValue("Fresh#Tag");

  state.runtime.connected = false;
  state.runtime.riot_id = "";
  await page.evaluate((runtime) => {
    const emit = (window as Window & { __otpEmitRuntimeEvent?: (event: unknown) => void }).__otpEmitRuntimeEvent;
    emit?.({ type: "disconnected", data: {}, timestamp: "2026-09-16T12:01:00Z" });
    emit?.({ type: "runtime_snapshot", data: runtime, timestamp: "2026-09-16T12:01:00Z" });
  }, state.runtime);
  await expect(riotId).toBeDisabled();
  await expect(riotId).toHaveValue("");
  expect(state.settings.manual_summoner_name).toBe("Saved#Manual");
});

test("automatic account field does not present a stale stored ID before live detection", async ({ page }) => {
  await mockLocalApi(page, { connected: true, autoDetectedRiotId: "Stale#Tag", riotId: "" });
  await page.goto("/#settings/account");

  const riotId = page.getByRole("textbox", { name: "Riot ID" });
  await expect(riotId).toBeDisabled();
  await expect(riotId).toHaveValue("");
});

test("settings applies the saved theme", async ({ page }) => {
  await mockLocalApi(page);
  await page.goto("/#settings");
  await page.getByRole("button", { name: "Apparence" }).click();
  const theme = page.getByRole("combobox", { name: "Thème" });
  await theme.focus();
  await page.keyboard.press("Enter");
  const lightOption = page.getByRole("option", { name: "Clair" });
  await expect(lightOption).toBeVisible();
  await page.keyboard.press("ArrowDown");
  await expect(lightOption).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});

test("settings restores the theme after a failed save", async ({ page }) => {
  await mockLocalApi(page);
  await page.goto("/#settings");
  await page.getByRole("button", { name: "Apparence" }).click();
  await page.route("**/api/settings", async (route) => {
    if (route.request().method() === "PATCH" && route.request().postDataJSON()?.theme === "flatly") {
      await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "save failed" }) });
      return;
    }
    await route.fallback();
  });

  await page.getByRole("combobox", { name: "Thème" }).click();
  await page.getByRole("option", { name: "Clair" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByRole("alert")).toBeVisible();
});

test("import and reset reapply the theme to the whole interface", async ({ page }) => {
  await mockLocalApi(page);
  await page.goto("/#settings");
  await page.getByRole("button", { name: "Avancé" }).click();
  await page.getByLabel("Importer une configuration").setInputFiles({
    name: "otp-lol-settings.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({ config_schema_version: 6, theme: "flatly" })),
  });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");

  await page.getByRole("button", { name: /Réinitialiser les réglages/ }).click();
  const confirmation = page.getByRole("alertdialog");
  await expect(confirmation).toBeVisible();
  await confirmation.getByRole("button", { name: "Réinitialiser" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

test("import rejects a settings file from an older schema without applying it", async ({ page }) => {
  await mockLocalApi(page);
  await page.goto("/#settings/advanced");
  await page.getByLabel("Importer une configuration").setInputFiles({
    name: "otp-lol-settings-old.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({ config_schema_version: 5, theme: "flatly" })),
  });

  await expect(page.getByRole("alert")).toContainText("Unsupported settings schema");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

test("settings exposes the global skin automation switch", async ({ page }) => {
  await mockLocalApi(page);
  await page.goto("/#settings");
  await page.getByRole("button", { name: "Automatisations" }).click();
  const toggle = page.getByRole("switch", { name: "Automatisation des skins" });
  await expect(toggle).toHaveAttribute("aria-checked", "true");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", "false");
});
