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

  const heading = page.locator(".settings-section .section-head");
  await expect(page.locator(".page-heading .eyebrow")).toHaveCount(0);
  await expect(heading.getByRole("heading", { name: "Avancé", exact: true })).toHaveCount(1);
  await expect(page.locator(".advanced-group")).toHaveCount(3);
  await expect(page.locator(".advanced-action")).toHaveCount(6);
  await expect(page.locator(".advanced-actions").first()).toHaveCSS("grid-template-columns", /\d+(\.\d+)?px \d+(\.\d+)?px/);
  await page.getByRole("button", { name: "Apparence" }).click();
  await page.getByRole("combobox", { name: "Thème" }).click();
  await page.getByRole("option", { name: "Clair" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByRole("button", { name: "Avancé" }).click();
  await page.setViewportSize({ width: 800, height: 540 });
  await expect(heading).toBeVisible();
  await expect(page.locator(".advanced-group")).toHaveCount(3);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("settings applies the saved theme", async ({ page }) => {
  await mockLocalApi(page);
  await page.goto("/#settings");
  await page.getByRole("button", { name: "Apparence" }).click();
  const theme = page.getByRole("combobox", { name: "Thème" });
  await theme.focus();
  await page.keyboard.press("Enter");
  await page.keyboard.press("ArrowDown");
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
    buffer: Buffer.from(JSON.stringify({ theme: "flatly" })),
  });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");

  await page.getByRole("button", { name: /Réinitialiser les réglages/ }).click();
  const confirmation = page.getByRole("alertdialog");
  await expect(confirmation).toBeVisible();
  await confirmation.getByRole("button", { name: "Réinitialiser" }).click();
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
