import { expect, test } from "@playwright/test";

import { mockLocalApi } from "./helpers";

test("priority cards summarize a preset and open its editor from anywhere on the card", async ({ page }) => {
  await mockLocalApi(page, { configured: true });
  await page.goto("/#presets");
  await expect(page.locator(".page-heading .eyebrow")).toHaveCount(0);

  const cards = page.locator(".preset-card");
  await expect(cards).toHaveCount(3);
  await expect(cards.nth(0).locator(".preset-priority")).toHaveText("Priorité 1");
  await expect(cards.nth(1).locator(".preset-priority")).toHaveText("Priorité 2");
  await expect(cards.nth(2).locator(".preset-priority")).toHaveText("Priorité 3");
  await expect(cards.nth(0).locator(".preset-summary-runes")).toContainText("Ma page Top · Auto");
  await expect(cards.nth(0).locator(".preset-summary-runes").getByText("Runes", { exact: true })).toHaveCount(1);
  await expect(cards.nth(0).locator(".preset-card-art img")).toHaveAttribute("src", /\/splash\?skin_num=13/);

  await cards.nth(0).locator(".preset-summary-skin").click();
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await expect(editor).toBeVisible();
  await expect(editor.locator(".eyebrow")).toHaveText("Priorité 1");
});

test("preset cards open with Enter and Space and restore focus after Escape", async ({ page }) => {
  await mockLocalApi(page, { configured: true });
  await page.goto("/#presets");
  const card = page.locator(".preset-card").first();
  await card.focus();
  await page.keyboard.press("Enter");
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await expect(editor).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(editor).toBeHidden();
  await expect(card).toBeFocused();

  await page.keyboard.press("Space");
  await expect(editor).toBeVisible();
  await page.keyboard.press("Escape");
});

test("the champion base portrait opens the Champion Picker from the preset editor", async ({ page }) => {
  await mockLocalApi(page, { configured: true });
  await page.goto("/#presets");
  await page.locator(".preset-card").first().click();

  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await editor.getByRole("button", { name: "Garen La Force de Demacia", exact: true }).click();
  const picker = page.getByRole("dialog", { name: "Choisir un champion" });
  await expect(picker).toBeVisible();
  await picker.getByRole("option", { name: /Lux/ }).click();

  await expect(editor.getByRole("button", { name: /Lux/ })).toBeVisible();
  await expect(picker).toBeHidden();
  await page.keyboard.press("Escape");
  await expect(editor).toBeHidden();
  await expect(page.locator(".preset-card").first()).toBeFocused();
});

test("the global preset switch rolls back and explains a rejected activation", async ({ page }) => {
  await mockLocalApi(page, { rejectPresetActivation: true });
  await page.goto("/#presets");

  const toggle = page.getByRole("switch", { name: "Presets actifs" });
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  await expect(page.getByRole("alert")).toHaveText("Configure au moins un champion avant d’activer les presets.");
});

test("the preset switch updates immediately and exposes its pending state", async ({ page }) => {
  await mockLocalApi(page, { configured: true });
  await page.goto("/#presets");
  const toggle = page.getByRole("switch", { name: "Presets actifs" });
  await expect(toggle).toHaveAttribute("aria-checked", "true");
  await page.route("**/api/settings", async (route) => {
    if (route.request().method() === "PATCH") await page.waitForTimeout(250);
    await route.fallback();
  });
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-busy", "true");
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  await expect(toggle).toHaveAttribute("aria-busy", "false");
});

test("rune page and auto mode stay together when League is unavailable", async ({ page }) => {
  await mockLocalApi(page, { configured: true });
  await page.goto("/#presets");
  const card = page.locator(".preset-card").first();
  await card.click();
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  const autoApply = editor.getByRole("switch", { name: "Appliquer automatiquement" });
  await expect(autoApply).toHaveAttribute("aria-checked", "true");
  await expect(editor).toContainText("Ma page Top");
  await expect(editor).toContainText("Ta page enregistrée est conservée");

  await editor.getByRole("button", { name: /Ma page Top/ }).click();
  const runePicker = page.getByRole("dialog", { name: "Runes" });
  await expect(runePicker).toContainText("Pages de runes indisponibles");
  await page.keyboard.press("Escape");
  await expect(editor).toBeVisible();
  await autoApply.click();
  await expect(autoApply).toHaveAttribute("aria-checked", "false");
  await expect(card.locator(".preset-summary-runes")).toContainText("Ma page Top · Manuel");
});

test("skin selection uses a splash preview and retains a base-splash fallback", async ({ page }) => {
  await mockLocalApi(page, { configured: true });
  await page.goto("/#presets");
  const card = page.locator(".preset-card").first();
  await expect(card.locator(".preset-card-art img")).toHaveAttribute("src", /\/splash\?skin_num=13/);
  await card.click();

  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await editor.getByRole("radio", { name: "Aucun" }).click();
  await expect(card.locator(".preset-card-art img")).toHaveAttribute("src", "/assets/app/garen.webp");
  await expect(editor.getByRole("button", { name: /Galerie des skins/ })).toBeDisabled();

  await editor.getByRole("radio", { name: "Fixe" }).click();
  await editor.getByRole("button", { name: /God-King Garen/ }).click();
  const skinPicker = page.getByRole("dialog", { name: "Galerie des skins" });
  await expect(skinPicker.getByText("God-King Garen").first()).toBeVisible();
});
