import { expect, test } from "@playwright/test";

import { applyFactoryDefaults, mockLocalApi } from "./helpers";

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
  await expect(page.locator(".advanced-action")).toHaveCount(9);
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
  const detection = page.getByRole("switch", { name: "Détection automatique du compte" });
  await expect(detection).toHaveAttribute("aria-checked", "true");
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

test("manual account mode identifies the manual link source", async ({ page }) => {
  await mockLocalApi(page, { autoDetect: false, manualRiotId: "Manual#EUW", region: "euw" });
  await page.goto("/#settings/account");

  await expect(page.getByText("Compte configuré manuellement")).toBeVisible();
});

test("automatic account input follows the live account, then uses its complete saved identity offline", async ({ page }) => {
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
  state.settings.auto_detected_riot_id = "Fresh#EUW";
  state.settings.auto_detected_region = "euw";
  state.settings.auto_detected_platform = "euw1";
  await page.evaluate((runtime) => {
    const emit = (window as Window & { __otpEmitRuntimeEvent?: (event: unknown) => void }).__otpEmitRuntimeEvent;
    emit?.({ type: "disconnected", data: {}, timestamp: "2026-09-16T12:01:00Z" });
    emit?.({ type: "runtime_snapshot", data: runtime, timestamp: "2026-09-16T12:01:00Z" });
  }, state.runtime);
  await expect(riotId).toBeDisabled();
  await expect(riotId).toHaveValue("Fresh#EUW");
  await expect(page.getByText("Dernier compte détecté · EUW · League fermé")).toBeVisible();
  expect(state.settings.manual_summoner_name).toBe("Saved#Manual");
});

test("automatic account field does not present a stale stored ID before live detection", async ({ page }) => {
  await mockLocalApi(page, { connected: true, autoDetectedRiotId: "Stale#Tag", riotId: "" });
  await page.goto("/#settings/account");

  const riotId = page.getByRole("textbox", { name: "Riot ID" });
  await expect(riotId).toBeDisabled();
  await expect(riotId).toHaveValue("");
  await expect(page.getByRole("combobox", { name: "Région" })).toHaveText("");
});

test("offline saved account can be copied explicitly and forgotten without changing manual settings", async ({ page }) => {
  const state = await mockLocalApi(page, {
    autoDetectedRiotId: "Saved#EUW",
    autoDetectedRegion: "euw",
    autoDetectedPlatform: "euw1",
    manualRiotId: "Manual#NA",
  });
  await page.goto("/#settings/account");

  const riotId = page.getByRole("textbox", { name: "Riot ID" });
  await expect(riotId).toBeDisabled();
  await expect(riotId).toHaveValue("Saved#EUW");
  await expect(page.getByText("Dernier compte détecté · EUW · League fermé")).toBeVisible();
  await page.getByRole("button", { name: "Copier vers les champs manuels" }).click();
  const overwrite = page.getByRole("alertdialog");
  await expect(overwrite).toBeVisible();
  await overwrite.getByRole("button", { name: "Copier vers les champs manuels" }).click();
  await expect(riotId).toHaveValue("Saved#EUW");
  expect(state.settings.manual_summoner_name).toBe("Saved#EUW");
  expect(state.settings.manual_region).toBe("euw");
  expect(state.settings.summoner_name_auto_detect).toBe(true);

  await page.getByRole("switch", { name: "Détection automatique du compte" }).click();
  await expect(riotId).toBeEnabled();
  await page.getByRole("button", { name: "Oublier le dernier compte" }).click();
  const forget = page.getByRole("alertdialog");
  await expect(forget).toBeVisible();
  await forget.getByRole("button", { name: "Oublier le dernier compte" }).click();
  expect(state.settings.auto_detected_riot_id).toBe("");
  expect(state.settings.auto_detected_region).toBe("");
  expect(state.settings.auto_detected_platform).toBe("");
  expect(state.settings.manual_summoner_name).toBe("Saved#EUW");
});

test("settings do not show or copy a saved account with a mismatched platform, but can forget it", async ({ page }) => {
  const state = await mockLocalApi(page, {
    autoDetectedRiotId: "Stale#EUW",
    autoDetectedRegion: "euw",
    autoDetectedPlatform: "na1",
  });
  await page.goto("/#settings/account");

  await expect(page.getByRole("textbox", { name: "Riot ID" })).toHaveValue("");
  await expect(page.getByRole("button", { name: "Copier vers les champs manuels" })).toHaveCount(0);
  await page.getByRole("button", { name: "Oublier le dernier compte" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Oublier le dernier compte" }).click();
  expect(state.settings.auto_detected_riot_id).toBe("");
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
  const state = await mockLocalApi(page);
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
  expect([state.settings.selected_pick_1, state.settings.selected_pick_2, state.settings.selected_pick_3]).toEqual(["Garen", "Lux", "Ashe"]);
  expect(state.settings.presets_enabled).toBe(false);
  for (const key of ["auto_accept_enabled", "auto_pick_enabled", "auto_ban_enabled", "auto_summoners_enabled", "skin_automation_enabled", "auto_play_again_enabled"] as const) {
    expect(state.settings[key]).toBe(false);
  }
});

test("reset writes the starter presets and shows a dismissible first-run message", async ({ page }) => {
  const state = await mockLocalApi(page, { autoDetectedRiotId: "Saved#EUW", autoDetectedRegion: "euw", autoDetectedPlatform: "euw1" });
  await page.goto("/#settings/advanced");
  await page.getByRole("button", { name: /Réinitialiser les réglages/ }).click();
  const confirmation = page.getByRole("alertdialog");
  await expect(confirmation).toBeVisible();
  await expect(confirmation).toContainText("efface aussi le dernier compte League détecté");
  await confirmation.getByRole("button").last().click();

  expect(state.settings.presets_enabled).toBe(false);
  expect(state.settings.onboarding_completed).toBe(false);
  expect(state.settings.selected_pick_1).toBe("Garen");
  expect(state.settings.selected_pick_2).toBe("Lux");
  expect(state.settings.selected_pick_3).toBe("Ashe");
  expect(state.settings.selected_ban).toBe("Teemo");
  expect(state.settings.auto_detected_riot_id).toBe("");
  expect(state.settings.auto_detected_region).toBe("");
  expect(state.settings.auto_detected_platform).toBe("");
  expect(state.settings.pick_slots.pick_1.spell_2).toBe("Ignite");
  expect(state.settings.pick_slots.pick_2.spell_2).toBe("Barrier");
  expect(state.settings.pick_slots.pick_3.spell_2).toBe("Heal");
  for (const slot of Object.values(state.settings.pick_slots)) {
    expect(slot.skin_mode).toBe("none");
    expect(slot.rune_page_id).toBe(0);
    expect(slot.rune_keystone_id).toBe(0);
  }
  for (const key of ["auto_accept_enabled", "auto_pick_enabled", "auto_ban_enabled", "auto_summoners_enabled", "skin_automation_enabled", "auto_play_again_enabled"] as const) {
    expect(state.settings[key]).toBe(false);
  }

  await page.goto("/#dashboard");
  for (const [index, champion] of ["Garen", "Lux", "Ashe"].entries()) {
    await expect(page.locator(".priority-card").nth(index)).toContainText(champion);
  }
  await expect(page.locator(".ban-panel")).toContainText("Teemo");
  const onboarding = page.getByRole("complementary", { name: "Des exemples sont prêts." });
  await expect(onboarding).toBeVisible();
  await page.reload();
  await expect(onboarding).toBeVisible();
  await page.getByRole("button", { name: "Masquer le message de bienvenue" }).click();
  await expect(onboarding).toBeHidden();
  await page.reload();
  await expect(onboarding).toBeHidden();
});

test("first-run onboarding closes permanently after editing a preset", async ({ page }) => {
  const state = await mockLocalApi(page, { onboardingCompleted: false });
  applyFactoryDefaults(state);
  await page.goto("/#dashboard");
  await expect(page.getByRole("complementary", { name: "Des exemples sont prêts." })).toBeVisible();
  await page.getByRole("link", { name: "Configurer mes priorités" }).click();
  await expect(page).toHaveURL(/#dashboard\/pick_1$/);
  await expect(page.getByRole("dialog", { name: "Modifier la priorité 1" })).toBeVisible();
  const editRequest = page.waitForRequest((request) => request.url().endsWith("/api/presets/pick_1") && request.method() === "PUT");
  await page.locator('.skin-mode-options input[value="fixed"]').click();
  await editRequest;
  expect(state.settings.onboarding_completed).toBe(true);

  await page.goto("/#dashboard");
  await expect(page.getByRole("complementary", { name: "Des exemples sont prêts." })).toBeHidden();
  await page.reload();
  await expect(page.getByRole("complementary", { name: "Des exemples sont prêts." })).toBeHidden();
});

test("first-run onboarding targets the first empty priority", async ({ page }) => {
  const state = await mockLocalApi(page, { configured: true, onboardingCompleted: false });
  state.presets.slots.pick_2.champion = "";
  state.settings.pick_slots.pick_2.champion = "";
  state.settings.selected_pick_2 = "";
  await page.goto("/#dashboard");
  await page.getByRole("link", { name: "Configurer mes priorités" }).click();
  await expect(page).toHaveURL(/#dashboard\/pick_2$/);
  await expect(page.getByRole("dialog", { name: "Modifier la priorité 2" })).toBeVisible();
});

test("preset reset restores examples, disables the master and preserves child preferences", async ({ page }) => {
  const state = await mockLocalApi(page, { configured: true });
  Object.assign(state.settings, {
    presets_enabled: true,
    auto_accept_enabled: true,
    auto_pick_enabled: true,
    auto_ban_enabled: false,
    auto_summoners_enabled: true,
    skin_automation_enabled: true,
    auto_play_again_enabled: true,
    theme: "flatly",
  });
  state.presets.presets_enabled = true;
  state.runtime.presets_enabled = true;
  await page.goto("/#settings/advanced");
  await page.getByRole("button", { name: /Restaurer les presets d'exemple/ }).click();
  const confirmation = page.getByRole("alertdialog");
  await expect(confirmation).toBeVisible();
  await confirmation.getByRole("button").last().click();

  expect(state.settings.presets_enabled).toBe(false);
  expect(state.settings.auto_accept_enabled).toBe(true);
  expect(state.settings.auto_pick_enabled).toBe(true);
  expect(state.settings.auto_ban_enabled).toBe(false);
  expect(state.settings.auto_summoners_enabled).toBe(true);
  expect(state.settings.skin_automation_enabled).toBe(true);
  expect(state.settings.auto_play_again_enabled).toBe(true);
  expect(state.settings.theme).toBe("flatly");
  expect(state.settings.onboarding_completed).toBe(false);
  expect([state.settings.selected_pick_1, state.settings.selected_pick_2, state.settings.selected_pick_3]).toEqual(["Garen", "Lux", "Ashe"]);
  expect(state.settings.selected_ban).toBe("Teemo");
  expect(Object.values(state.settings.pick_slots).map((slot) => slot.spell_2)).toEqual(["Ignite", "Barrier", "Heal"]);
  expect(Object.values(state.settings.pick_slots).every((slot) => slot.skin_mode === "none" && slot.rune_page_id === 0 && slot.rune_keystone_id === 0)).toBe(true);

  await page.goto("/#dashboard");
  await expect(page.getByRole("switch", { name: "Utiliser les presets en sélection" })).toHaveAttribute("aria-checked", "false");
  for (const [index, champion] of ["Garen", "Lux", "Ashe"].entries()) {
    await expect(page.locator(".priority-card").nth(index)).toContainText(champion);
  }
  await expect(page.locator(".ban-panel")).toContainText("Teemo");
  await expect(page.getByRole("complementary", { name: "Des exemples sont prêts." })).toBeVisible();
});

test("clearing presets leaves the rest of the user's settings unchanged", async ({ page }) => {
  const state = await mockLocalApi(page, { configured: true });
  Object.assign(state.settings, {
    presets_enabled: true,
    auto_accept_enabled: true,
    auto_pick_enabled: true,
    auto_ban_enabled: false,
    auto_summoners_enabled: true,
    skin_automation_enabled: true,
    auto_play_again_enabled: true,
    theme: "flatly",
  });
  state.presets.presets_enabled = true;
  state.runtime.presets_enabled = true;
  await page.goto("/#settings/advanced");
  await page.getByRole("button", { name: /Effacer uniquement les presets/ }).click();
  const confirmation = page.getByRole("alertdialog");
  await expect(confirmation).toContainText("Restaurer les presets d'exemple");
  await confirmation.getByRole("button").last().click();

  expect(state.settings.presets_enabled).toBe(true);
  expect(state.settings.auto_accept_enabled).toBe(true);
  expect(state.settings.auto_pick_enabled).toBe(true);
  expect(state.settings.auto_ban_enabled).toBe(false);
  expect(state.settings.auto_summoners_enabled).toBe(true);
  expect(state.settings.skin_automation_enabled).toBe(true);
  expect(state.settings.auto_play_again_enabled).toBe(true);
  expect(state.settings.theme).toBe("flatly");
  expect([state.settings.selected_pick_1, state.settings.selected_pick_2, state.settings.selected_pick_3]).toEqual(["", "", ""]);
  expect(state.settings.selected_ban).toBe("");
  expect(Object.values(state.settings.pick_slots).every((slot) => slot.champion === "")).toBe(true);
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
  const state = await mockLocalApi(page);
  state.settings.presets_enabled = true;
  state.presets.presets_enabled = true;
  state.runtime.presets_enabled = true;
  await page.goto("/#settings");
  await page.getByRole("button", { name: "Automatisations" }).click();
  const toggle = page.getByRole("switch", { name: "Automatisation des skins" });
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", "true");
});
