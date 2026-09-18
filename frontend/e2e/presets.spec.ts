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

  const toggle = page.getByRole("switch", { name: "Utiliser les presets en sélection" });
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  await expect(page.getByRole("alert")).toHaveText("Configure au moins un champion avant d’activer les presets.");
});

test("the preset switch updates immediately and exposes its pending state", async ({ page }) => {
  await mockLocalApi(page, { configured: true });
  await page.goto("/#presets");
  const toggle = page.getByRole("switch", { name: "Utiliser les presets en sélection" });
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

test("master gates preset children across Dashboard and Presets without clearing their choices", async ({ page }) => {
  const state = await mockLocalApi(page, { configured: true });
  Object.assign(state.settings, {
    presets_enabled: false,
    auto_accept_enabled: true,
    auto_pick_enabled: true,
    auto_ban_enabled: true,
    auto_summoners_enabled: true,
    skin_automation_enabled: true,
    auto_play_again_enabled: true,
  });
  state.presets.presets_enabled = false;
  state.runtime.presets_enabled = false;
  await page.goto("/#dashboard");

  const master = page.getByRole("switch", { name: "Utiliser les presets en sélection" });
  await expect(master).toHaveAttribute("aria-checked", "false");
  const automationItems = page.locator(".automation-item");
  for (const index of [1, 2, 3, 4]) {
    const child = automationItems.nth(index).getByRole("switch");
    await expect(child).toBeDisabled();
    await expect(child).toHaveAttribute("aria-checked", "true");
  }
  await expect(automationItems.nth(0).getByRole("switch")).toBeEnabled();
  await expect(automationItems.nth(5).getByRole("switch")).toBeEnabled();

  await master.click();
  await expect(master).toHaveAttribute("aria-checked", "true");
  await expect(automationItems.nth(1).getByRole("switch")).toBeEnabled();
  for (const key of ["auto_accept_enabled", "auto_pick_enabled", "auto_ban_enabled", "auto_summoners_enabled", "skin_automation_enabled", "auto_play_again_enabled"] as const) {
    expect(state.settings[key]).toBe(true);
  }

  await page.goto("/#presets");
  const presetsMaster = page.getByRole("switch", { name: "Utiliser les presets en sélection" });
  await expect(presetsMaster).toHaveAttribute("aria-checked", "true");
  await presetsMaster.click();
  await expect(presetsMaster).toHaveAttribute("aria-checked", "false");
  await page.locator(".preset-card").first().click();
  const runeAuto = page.getByRole("dialog").getByRole("switch", { name: "Appliquer automatiquement" });
  await expect(runeAuto).toBeDisabled();
  await expect(runeAuto).toHaveAttribute("aria-checked", "true");
  for (const key of ["auto_accept_enabled", "auto_pick_enabled", "auto_ban_enabled", "auto_summoners_enabled", "skin_automation_enabled", "auto_play_again_enabled"] as const) {
    expect(state.settings[key]).toBe(true);
  }
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
  const skinChoice = editor.getByRole("button", { name: /Galerie des skins/ });
  await expect(skinChoice.locator(".editor-skin-preview")).toHaveAttribute("src", "/api/assets/skins/86/86013/splash?skin_num=13&v=test-version");
  const bootstrapRefresh = page.waitForRequest((request) => request.url().endsWith("/api/bootstrap"));
  await editor.getByRole("radio", { name: "Aucun" }).click();
  await bootstrapRefresh;
  await expect(skinChoice.locator(".editor-skin-preview")).toHaveAttribute("src", "/assets/app/garen.webp");
  await expect(card.locator(".preset-card-art img")).toHaveAttribute("src", "/assets/app/garen.webp");
  await expect(skinChoice).toBeDisabled();

  await editor.getByRole("radio", { name: "Fixe" }).click();
  await editor.getByRole("button", { name: /God-King Garen/ }).click();
  const skinPicker = page.getByRole("dialog", { name: "Galerie des skins" });
  await expect(skinPicker.getByText("God-King Garen").first()).toBeVisible();
});

test("random skin preview is shown in the editor without loading another catalog", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  await mockLocalApi(page, { configured: true, randomSkinPreview: true });
  await page.goto("/#presets");
  await page.locator(".preset-card").first().click();

  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await expect(editor.getByRole("button", { name: /Pool aléatoire/ }).locator(".editor-skin-preview"))
    .toHaveAttribute("src", "/api/assets/skins/86/86013/splash?skin_num=13&v=test-version");
  expect(requests.some((url) => /\/api\/skins\//.test(url))).toBe(false);
});

test("the editor skin thumbnail refreshes after selecting another fixed skin", async ({ page }) => {
  await mockLocalApi(page, { configured: true, alternateSkin: true });
  await page.goto("/#presets");
  await page.locator(".preset-card").first().click();

  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await editor.getByRole("button", { name: /Galerie des skins/ }).click();
  const picker = page.getByRole("dialog", { name: "Galerie des skins" });
  const alternateSkin = picker.locator(".skin-option").filter({ hasText: "Steel Legion Garen" });
  await alternateSkin.getByRole("button", { name: "Choisir" }).click();
  await page.keyboard.press("Escape");

  await expect(editor.getByRole("button", { name: /Galerie des skins/ }).locator(".editor-skin-preview"))
    .toHaveAttribute("src", "/api/assets/skins/86/86014/splash?skin_num=14&v=test-version");
});

test("spell Select shows option and selected icons while preserving Radix keyboard behavior", async ({ page }) => {
  await mockLocalApi(page, { configured: true });
  await page.goto("/#presets");
  await page.locator(".preset-card").first().click();

  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  const spellSelect = editor.getByRole("combobox", { name: "Sort 1" });
  await expect(spellSelect.locator(".spell-select-icon")).toHaveAttribute("src", "/assets/app/garen.webp");

  await spellSelect.focus();
  await page.keyboard.press("Enter");
  const flashOption = page.getByRole("option", { name: "Flash" });
  await expect(flashOption).toBeVisible();
  await expect(flashOption).toHaveText("Flash");
  await expect(flashOption.locator(".spell-select-icon")).toHaveAttribute("src", "/assets/app/garen.webp");
  const igniteOption = page.getByRole("option", { name: "Ignite" });
  await expect(igniteOption).toHaveText("Ignite");
  await expect(igniteOption.locator(".spell-select-icon"))
    .toHaveAttribute("src", "/assets/app/garen.webp");
  await expect(page.getByRole("option", { name: "Aucun" }).locator(".spell-select-icon svg")).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(flashOption).toBeHidden();
  await expect(spellSelect).toBeFocused();

  await page.keyboard.press("Enter");
  await expect(igniteOption).toBeVisible();
  await page.keyboard.press("ArrowDown");
  await expect(igniteOption).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(spellSelect).toContainText("Ignite");
  await expect(spellSelect.locator(".spell-select-icon")).toHaveAttribute("src", "/assets/app/garen.webp");
});
