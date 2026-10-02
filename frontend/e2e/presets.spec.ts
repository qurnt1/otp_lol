import { expect, readPresets, readSettings, setupApplication, test } from "./helpers";

test("priority cards show persisted picks, runes and a skin preview", async ({ page }) => {
  await setupApplication(page, { configured: true });
  await page.goto("/#dashboard");

  const cards = page.locator(".priority-card");
  await expect(cards).toHaveCount(3);
  await expect(cards.nth(0).locator(".priority-number")).toHaveText("01");
  await expect(cards.nth(1).locator(".priority-number")).toHaveText("02");
  await expect(cards.nth(2).locator(".priority-number")).toHaveText("03");
  await expect(cards.nth(0).locator(".rune-name")).toContainText("E2E Top");
  await expect(cards.nth(0).locator(".priority-art img")).toHaveAttribute("src", /\/splash\?skin_num=13/);
  await expect(cards.nth(0).locator(".skin-preview img")).toHaveAttribute("src", /\/api\/assets\/champions\/86\.png/);
  await expect(cards.nth(0).locator('[aria-label="Sorts d’invocateur"]')).toBeVisible();
  await expect(cards.nth(0).locator('[aria-label="Runes"]')).toBeVisible();
  await expect(cards.nth(0).locator(".summoner-row img").nth(0)).toHaveAttribute("title", "Flash");
  await expect(cards.nth(0).locator(".summoner-row img").nth(1)).toHaveAttribute("title", "Ignite");
  await expect.poll(() => cards.nth(0).locator(".priority-art img").evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true);
  const runeAssetStyles = await cards.nth(0).locator(".rune-row .rune-asset").first().evaluate((image) => ({ borderWidth: getComputedStyle(image).borderWidth, boxShadow: getComputedStyle(image).boxShadow }));
  expect(runeAssetStyles).toEqual({ borderWidth: "0px", boxShadow: "none" });

  await cards.nth(0).locator(".skin-preview").click();
  await expect(page.getByRole("dialog", { name: "Modifier la priorité 1" })).toBeVisible();
});

test("a failed champion catalogue request does not show a ready subtitle for its pick", async ({ page }) => {
  await setupApplication(page, { configured: true });
  await page.route("**/api/champions?**", (route) => route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Injected catalogue outage" }) }));
  await page.goto("/#dashboard");

  const card = page.locator(".priority-card").first();
  await expect(card.getByRole("heading", { name: "Garen" })).toBeVisible();
  await expect.poll(async () => card.locator(".priority-caption small").count()).toBe(0);
});

test("a failed champion picker catalogue can be retried before saving a champion", async ({ page }) => {
  await setupApplication(page, { configured: true });
  let catalogueReads = 0;
  await page.route("**/api/champions?**", async (route) => {
    catalogueReads += 1;
    if (catalogueReads <= 2) {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Injected champion catalogue outage" }) });
      return;
    }
    await route.continue();
  });
  await page.goto("/#dashboard/pick_1");
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await editor.locator(".champion-choice").click();
  const picker = page.getByRole("dialog", { name: "Choisir un champion" });
  await expect(picker.getByText("Impossible de charger les champions.")).toBeVisible();
  const retry = picker.getByRole("button", { name: "Réessayer" });
  await expect(retry).toBeVisible();
  expect(catalogueReads).toBe(2);

  await page.unroute("**/api/champions?**");
  const catalogueResponse = page.waitForResponse((response) =>
    response.request().method() === "GET" && new URL(response.url()).pathname === "/api/champions" && response.status() === 200,
  );
  await retry.click();
  expect((await catalogueResponse).ok()).toBe(true);
  await picker.getByRole("option", { name: /Annie/ }).click();
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.champion).toBe("Annie");
});

test("Dashboard priority cards open with Enter and restore focus after Escape", async ({ page }) => {
  await setupApplication(page, { configured: true });
  await page.goto("/#dashboard");
  const card = page.locator(".priority-card-link").first();
  await card.focus();
  await page.keyboard.press("Enter");
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await expect(editor).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(editor).toBeHidden();
  await expect(page).toHaveURL(/#dashboard$/);
  await expect(card).toBeFocused();
});

test("clicking an empty priority opens and saves that slot", async ({ page }) => {
  await setupApplication(page, { connected: true });
  await page.goto("/#dashboard");

  const emptySlot = page.locator(".priority-card").nth(1);
  await expect(emptySlot).toHaveClass(/is-empty/);
  await emptySlot.click();
  await expect(page).toHaveURL(/#dashboard\/pick_2$/);

  const editor = page.getByRole("dialog", { name: "Modifier la priorité 2" });
  await expect(editor).toBeVisible();
  await editor.locator(".champion-choice").click();
  const picker = page.getByRole("dialog", { name: "Choisir un champion" });
  await picker.getByRole("option", { name: /Garen/ }).click();

  await expect.poll(async () => (await readPresets(page)).slots.pick_2.champion).toBe("Garen");
  expect(await readPresets(page)).toMatchObject({
    slots: {
      pick_1: { champion: "" },
      pick_2: { champion: "Garen" },
      pick_3: { champion: "" },
    },
  });
  await expect(editor.getByRole("button", { name: /Garen/ })).toBeVisible();
  await editor.getByRole("button", { name: "Fermer" }).last().click();
  await expect(page).toHaveURL(/#dashboard$/);
  await expect(emptySlot).toContainText("Garen");
});

test("nested picker Escape closes only the picker, while outside click closes the editor", async ({ page }) => {
  await setupApplication(page, { configured: true });
  await page.goto("/#dashboard");
  const card = page.locator(".priority-card-link").first();
  await card.click();

  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await editor.locator(".champion-choice").click();
  const picker = page.getByRole("dialog", { name: "Choisir un champion" });
  await expect(picker).toBeVisible();
  await expect(picker.getByRole("textbox", { name: "Rechercher un champion…" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(picker).toBeHidden();
  await expect(editor).toBeVisible();
  await expect(editor.locator(".champion-choice")).toBeFocused();

  await page.mouse.click(4, 4);
  await expect(editor).toBeHidden();
  await expect(card).toBeFocused();
});

test("a direct Dashboard editor route keeps the Dashboard mounted and closes cleanly", async ({ page }) => {
  await setupApplication(page, { configured: true });
  await page.goto("/#dashboard/pick_2");
  await expect(page.locator(".dashboard-page")).toBeVisible();
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 2" });
  await expect(editor).toBeVisible();
  await editor.getByRole("button", { name: "Fermer" }).last().click();
  await expect(page).toHaveURL(/#dashboard$/);
  await expect(page.locator(".priority-card-link").nth(1)).toBeFocused();
});

test("champion picker searches, reports an empty result, and persists a real selection", async ({ page }) => {
  await setupApplication(page, { configured: true });
  await page.goto("/#dashboard");
  await page.locator(".priority-card").nth(1).click();
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 2" });
  await editor.locator(".champion-choice").click();

  const picker = page.getByRole("dialog", { name: "Choisir un champion" });
  const search = picker.getByRole("textbox", { name: "Rechercher un champion…" });
  await search.fill("NotAChampion");
  await expect(picker.getByText("Aucun résultat.")).toBeVisible();
  await search.fill("Ahri");
  await picker.getByRole("option", { name: /Ahri/ }).click();

  await expect(picker).toBeHidden();
  await expect.poll(async () => (await readPresets(page)).slots.pick_2.champion).toBe("Ahri");
  await expect(editor.getByRole("button", { name: /Ahri/ })).toBeVisible();
});

test("a rejected champion save keeps the old pick and lets the user retry", async ({ page }) => {
  await setupApplication(page, { configured: true });
  await page.goto("/#dashboard");
  await page.locator(".priority-card").first().click();
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await editor.locator(".champion-choice").click();
  const picker = page.getByRole("dialog", { name: "Choisir un champion" });

  await page.route("**/api/presets/pick_1", async (route) => {
    if (route.request().method() === "PUT") {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Injected preset outage" }) });
      return;
    }
    await route.continue();
  });
  const failedSave = page.waitForResponse((response) =>
    response.request().method() === "PUT" && new URL(response.url()).pathname === "/api/presets/pick_1",
  );
  await picker.getByRole("option", { name: /Annie/ }).click();
  expect((await failedSave).status()).toBe(503);
  await expect(editor.getByRole("alert")).toBeVisible();
  await expect(picker).toBeVisible();
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.champion).toBe("Garen");

  await page.unroute("**/api/presets/pick_1");
  await picker.getByRole("option", { name: /Annie/ }).click();
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.champion).toBe("Annie");
  await expect(editor.getByRole("button", { name: /Annie/ })).toBeVisible();
});

test("champion role filters match the catalogue and exclude champions already assigned to another pick", async ({ page }) => {
  await setupApplication(page);
  await page.goto("/#dashboard");
  await page.locator(".priority-card").nth(1).click();
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 2" });
  await editor.locator(".champion-choice").click();

  let picker = page.getByRole("dialog", { name: "Choisir un champion" });
  const filters = picker.getByRole("group", { name: "Filtrer les champions par poste" });
  await filters.getByRole("button", { name: "Top", exact: true }).click();
  await expect(picker.getByRole("option", { name: /Garen/ })).toBeVisible();
  await expect(picker.getByRole("option", { name: /Ahri/ })).toHaveCount(0);
  await picker.getByRole("option", { name: /Garen/ }).click();
  await expect.poll(async () => (await readPresets(page)).slots.pick_2.champion).toBe("Garen");
  await editor.getByRole("button", { name: "Fermer" }).last().click();

  await page.locator(".priority-card").nth(2).click();
  const thirdEditor = page.getByRole("dialog", { name: "Modifier la priorité 3" });
  await thirdEditor.locator(".champion-choice").click();
  picker = page.getByRole("dialog", { name: "Choisir un champion" });
  await expect(picker.getByRole("option", { name: /Garen/ })).toHaveCount(0);
  await picker.getByRole("group", { name: "Filtrer les champions par poste" }).getByRole("button", { name: "Mid", exact: true }).click();
  await expect(picker.getByRole("option", { name: /Ahri/ })).toBeVisible();
  await expect(picker.getByRole("option", { name: /Garen/ })).toHaveCount(0);
  await picker.getByRole("option", { name: /Ahri/ }).click();
  await expect.poll(async () => (await readPresets(page)).slots.pick_3.champion).toBe("Ahri");
});

test("the preset master explains why an empty configuration cannot be activated", async ({ page }) => {
  await setupApplication(page);
  await page.goto("/#dashboard");

  const toggle = page.getByRole("switch", { name: "Utiliser les presets en sélection" });
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  await expect(page.getByRole("alert")).toHaveText("Configure au moins un champion avant d’activer les presets.");
  await expect.poll(async () => (await readSettings(page)).presets_enabled).toBe(false);
});

test("the preset master persists changes through the real settings API", async ({ page }) => {
  await setupApplication(page, { configured: true });
  await page.goto("/#dashboard");
  const toggle = page.getByRole("switch", { name: "Utiliser les presets en sélection" });
  await expect(toggle).toHaveAttribute("aria-checked", "true");

  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  await expect.poll(async () => (await readSettings(page)).presets_enabled).toBe(false);
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", "true");
  await expect.poll(async () => (await readSettings(page)).presets_enabled).toBe(true);
});

test("preset master gates dependent automations without erasing saved choices", async ({ page }) => {
  const { settings } = await setupApplication(page, {
    configured: true,
    settings: {
      presets_enabled: false,
      auto_accept_enabled: true,
      auto_pick_enabled: true,
      auto_ban_enabled: true,
      auto_summoners_enabled: true,
      skin_automation_enabled: true,
      auto_play_again_enabled: true,
    },
  });
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
  const saved = await readSettings(page);
  for (const key of ["auto_accept_enabled", "auto_pick_enabled", "auto_ban_enabled", "auto_summoners_enabled", "skin_automation_enabled", "auto_play_again_enabled"]) {
    expect(saved[key]).toBe(true);
  }
  expect(settings.presets_enabled).toBe(false);
});

test("[DASH-04] ban picker excludes configured picks and persists its selected champion", async ({ page }) => {
  await setupApplication(page, { connected: true, configured: true });
  await page.goto("/#dashboard");
  await page.locator(".ban-panel").click();
  const picker = page.getByRole("dialog", { name: "Champion à bannir" });
  await expect(picker.getByRole("option", { name: /Garen/ })).toHaveCount(0);
  await expect(picker.getByRole("option", { name: /Lux/ })).toHaveCount(0);
  await expect(picker.getByRole("option", { name: /Ashe/ })).toHaveCount(0);
  await picker.getByRole("textbox", { name: "Rechercher un champion…" }).fill("Annie");
  await picker.getByRole("option", { name: /Annie/ }).click();

  await expect(picker).toBeHidden();
  await expect.poll(async () => (await readPresets(page)).selected_ban).toBe("Annie");
  await expect(page.locator(".ban-panel")).toContainText("Annie");
});

test("rune page picker offers the connected League page and the do-nothing choice", async ({ page }) => {
  await setupApplication(page, { configured: true });
  await page.goto("/#dashboard");
  const card = page.locator(".priority-card").first();
  await card.click();
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await editor.getByRole("button", { name: /E2E Top/ }).click();
  const picker = page.getByRole("dialog", { name: "Runes" });
  await expect(picker.getByRole("button", { name: /E2E Top/ })).toBeVisible();
  await expect(picker.getByRole("button", { name: /Ne rien faire/ })).toBeVisible();
  await picker.getByRole("button", { name: /Ne rien faire/ }).click();

  await expect.poll(async () => (await readPresets(page)).slots.pick_1.rune_page_id).toBe(0);
  await expect(picker.getByRole("button", { name: /Ne rien faire/ })).toHaveAttribute("aria-pressed", "true");
  await page.keyboard.press("Escape");
  await expect(editor.getByRole("button", { name: /Ne rien faire/ })).toBeVisible();
});

test("rune catalogue loading, failure and retry preserve a real saved selection", async ({ page }) => {
  await setupApplication(page, { configured: true });
  let releaseFirstRead!: () => void;
  let reportFirstRead!: () => void;
  const firstReadGate = new Promise<void>((resolve) => { releaseFirstRead = resolve; });
  const firstReadStarted = new Promise<void>((resolve) => { reportFirstRead = resolve; });
  let runeReads = 0;
  await page.route("**/api/runes", async (route) => {
    runeReads += 1;
    if (runeReads === 1) {
      reportFirstRead();
      await firstReadGate;
    }
    if (runeReads <= 2) {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Injected rune catalogue outage" }) });
      return;
    }
    await route.continue();
  });
  await page.goto("/#dashboard");
  await page.locator(".priority-card").first().click();
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await editor.getByRole("button", { name: /E2E Top/ }).click();
  const picker = page.getByRole("dialog", { name: "Runes" });
  await firstReadStarted;
  await expect(picker.getByText("Chargement…")).toBeVisible();
  releaseFirstRead();
  await expect(picker.getByText("Impossible de charger les pages de runes.")).toBeVisible();
  const retry = picker.getByRole("button", { name: "Réessayer" });
  await expect(retry).toBeVisible();
  expect(runeReads).toBe(2);

  await page.unroute("**/api/runes");
  const recoveredCatalogue = page.waitForResponse((response) =>
    response.request().method() === "GET" && new URL(response.url()).pathname === "/api/runes" && response.status() === 200,
  );
  await retry.click();
  expect((await recoveredCatalogue).ok()).toBe(true);
  await expect(picker.getByRole("button", { name: /E2E Top/ })).toBeVisible();
  await picker.getByRole("button", { name: /Ne rien faire/ }).click();
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.rune_page_id).toBe(0);
});

test("rune picker offers only the do-nothing choice while League is offline", async ({ page }) => {
  const { app } = await setupApplication(page, {
    configured: true,
    settings: { close_app_on_lol_exit: false },
  });
  await app.configureLcuConnection({ online: false });
  await page.goto("/#dashboard");
  await page.locator(".priority-card").first().click();
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await editor.getByRole("button", { name: /E2E Top/ }).click();

  const picker = page.getByRole("dialog", { name: "Runes" });
  await expect(picker.getByRole("button", { name: /Ne rien faire/ })).toBeVisible();
  await expect(picker.getByRole("button", { name: /E2E Top/ })).toHaveCount(0);
  await picker.getByRole("button", { name: /Ne rien faire/ }).click();
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.rune_page_id).toBe(0);
});

test("choosing a real League rune page saves its perks and shows loaded rune assets", async ({ page }) => {
  await setupApplication(page);
  await page.goto("/#dashboard");
  await page.locator(".priority-card").first().click();
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await editor.getByRole("button", { name: /Ne rien faire/ }).click();
  const picker = page.getByRole("dialog", { name: "Runes" });
  const pageOption = picker.getByRole("button", { name: /E2E Top/ });
  await pageOption.click();

  await expect.poll(async () => (await readPresets(page)).slots.pick_1).toMatchObject({ rune_page_id: 401, rune_page_name: "E2E Top", rune_keystone_id: 8005 });
  await expect(pageOption).toHaveAttribute("aria-pressed", "true");
  const perkIcon = picker.locator(".rune-icon-wrap img").first();
  await expect.poll(() => perkIcon.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true);
  await page.keyboard.press("Escape");
  await expect(editor.getByRole("button", { name: /E2E Top/ })).toBeVisible();
});

test("rune auto-apply is saved independently for each priority slot", async ({ page }) => {
  await setupApplication(page, { configured: true });
  await page.goto("/#dashboard");
  await page.locator(".priority-card").nth(1).click();
  let editor = page.getByRole("dialog", { name: "Modifier la priorité 2" });
  const secondSlot = editor.getByRole("checkbox", { name: "Appliquer automatiquement les runes" });
  await expect(secondSlot).toBeChecked();
  await secondSlot.click();
  await expect(secondSlot).not.toBeChecked();
  await expect.poll(async () => (await readPresets(page)).slots.pick_2.rune_auto_apply).toBe(false);
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.rune_auto_apply).toBe(true);

  await editor.getByRole("button", { name: "Fermer" }).last().click();
  await page.locator(".priority-card").first().click();
  editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await expect(editor.getByRole("checkbox", { name: "Appliquer automatiquement les runes" })).toBeChecked();
});

test("a saved rune page missing from League is explained and can be cleared", async ({ page }) => {
  const { app } = await setupApplication(page, { configured: true });
  await app.configureLcuState({ rune_pages: [], current_rune_page: null });
  await page.goto("/#dashboard");
  await page.locator(".priority-card").first().click();
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await editor.getByRole("button", { name: /E2E Top/ }).click();

  const picker = page.getByRole("dialog", { name: "Runes" });
  await expect(picker.getByRole("alert")).toContainText("Page de runes supprimée ou indisponible");
  await expect(picker.getByRole("alert")).toContainText("Choisis une autre page ou conserve la page actuelle");
  await picker.getByRole("button", { name: /Ne rien faire/ }).click();

  await expect.poll(async () => (await readPresets(page)).slots.pick_1.rune_page_id).toBe(0);
  await expect(picker.getByRole("alert")).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(picker).toBeHidden();
  await expect(editor.getByRole("button", { name: /Ne rien faire/ })).toBeVisible();
});

test("fixed skin picker persists an owned Garen skin and updates the preview", async ({ page }) => {
  await setupApplication(page, { configured: true, networkStatus: "online" });
  await page.goto("/#dashboard");
  const card = page.locator(".priority-card").first();
  await expect(card.locator(".priority-art img")).toHaveAttribute("src", /\/splash\?skin_num=13/);
  await card.click();

  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  const skinChoice = editor.getByRole("button", { name: /Galerie des skins/ });
  await expect(skinChoice.locator(".editor-skin-preview")).toHaveAttribute("src", /\/api\/assets\/skins\/86\/86013\/splash\?skin_num=13/);
  await skinChoice.click();
  const picker = page.getByRole("dialog", { name: "Galerie des skins" });
  const commando = picker.locator(".skin-option").filter({ hasText: "Commando Garen" });
  await expect(commando).toBeVisible();
  await commando.getByRole("button", { name: "Choisir" }).click();

  await expect.poll(async () => (await readPresets(page)).slots.pick_1.skin_id).toBe(86001);
  await page.keyboard.press("Escape");
  await expect(skinChoice.locator(".editor-skin-preview")).toHaveAttribute("src", /\/api\/assets\/skins\/86\/86001\/splash/);
});

test("skin catalogue loading, failure and retry preserve a real saved selection", async ({ page }) => {
  await setupApplication(page, { configured: true });
  let releaseFirstRead!: () => void;
  let reportFirstRead!: () => void;
  const firstReadGate = new Promise<void>((resolve) => { releaseFirstRead = resolve; });
  const firstReadStarted = new Promise<void>((resolve) => { reportFirstRead = resolve; });
  let skinReads = 0;
  await page.route("**/api/skins/86", async (route) => {
    skinReads += 1;
    if (skinReads === 1) {
      reportFirstRead();
      await firstReadGate;
    }
    if (skinReads <= 2) {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Injected skin catalogue outage" }) });
      return;
    }
    await route.continue();
  });
  await page.goto("/#dashboard");
  await page.locator(".priority-card").first().click();
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await editor.getByRole("button", { name: /Galerie des skins/ }).click();
  const picker = page.getByRole("dialog", { name: "Galerie des skins" });
  await firstReadStarted;
  await expect(picker.getByText("Chargement…")).toBeVisible();
  releaseFirstRead();
  await expect(picker.getByText("Impossible de charger les skins.")).toBeVisible();
  const retry = picker.getByRole("button", { name: "Réessayer" });
  await expect(retry).toBeVisible();
  expect(skinReads).toBe(2);

  await page.unroute("**/api/skins/86");
  const recoveredCatalogue = page.waitForResponse((response) =>
    response.request().method() === "GET" && new URL(response.url()).pathname === "/api/skins/86" && response.status() === 200,
  );
  await retry.click();
  expect((await recoveredCatalogue).ok()).toBe(true);
  const commando = picker.locator(".skin-option").filter({ hasText: "Commando Garen" });
  await expect(commando).toBeVisible();
  await commando.getByRole("button", { name: "Choisir" }).click();
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.skin_id).toBe(86001);
});

test("a failed skin preview falls back and loads the replacement source after a user selection", async ({ page }) => {
  await setupApplication(page, { configured: true });
  let failedPreviewRequests = 0;
  await page.route("**/api/assets/skins/86/86013/splash*", async (route) => {
    failedPreviewRequests += 1;
    await route.abort("failed");
  });
  await page.goto("/#dashboard");
  await page.locator(".priority-card").first().click();

  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  const failedPreview = editor.locator(".editor-skin-preview");
  await expect(failedPreview).toHaveClass(/asset-fallback/);
  expect(failedPreviewRequests).toBeGreaterThan(0);
  await page.unroute("**/api/assets/skins/86/86013/splash*");

  await editor.getByRole("button", { name: /Galerie des skins/ }).click();
  const picker = page.getByRole("dialog", { name: "Galerie des skins" });
  await picker.locator(".skin-option").filter({ hasText: "Commando Garen" }).getByRole("button", { name: "Choisir" }).click();

  const replacementPreview = editor.locator("img.editor-skin-preview");
  await expect(replacementPreview).toHaveAttribute("src", /\/api\/assets\/skins\/86\/86001\/splash/);
  await expect.poll(() => replacementPreview.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true);
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.skin_id).toBe(86001);
});

test("random skin pool can be selected, cleared and persisted", async ({ page }) => {
  await setupApplication(page, { configured: true });
  await page.goto("/#dashboard");
  await page.locator(".priority-card").first().click();
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await editor.getByRole("radio", { name: "Aléatoire" }).click();
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.skin_mode).toBe("random");
  await editor.getByRole("button", { name: /Pool aléatoire/ }).click();
  const picker = page.getByRole("dialog", { name: "Galerie des skins" });
  const godKing = picker.getByRole("checkbox", { name: "God-King Garen" });
  const poolUpdate = page.waitForResponse((response) =>
    response.request().method() === "PUT" && new URL(response.url()).pathname === "/api/presets/pick_1",
  );
  await godKing.click();
  expect((await poolUpdate).status()).toBe(200);
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.random_skin_pool.map((skin: { skin_id: number }) => skin.skin_id)).toContain(86013);
  await expect(godKing).toBeChecked();
  await page.keyboard.press("Escape");
  await expect(picker).toBeHidden();
  const randomPreview = editor.locator("img.editor-skin-preview");
  await expect(randomPreview).toHaveAttribute("src", /\/api\/assets\/skins\/86\/86013\/splash/);
  await expect.poll(() => randomPreview.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true);
  await editor.getByRole("button", { name: /Pool aléatoire/ }).click();
  await picker.getByRole("button", { name: "Tout sélectionner" }).click();
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.random_skin_pool.length).toBeGreaterThan(1);
  await picker.getByRole("button", { name: "Tout effacer" }).click();
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.random_skin_pool).toEqual([]);
});

test("owned-only filtering hides unavailable skins without dropping selected pool entries", async ({ page }) => {
  const { app } = await setupApplication(page, { configured: true });
  await app.configureLcuState({ inventory_skins: [{ id: 86013, ownershipType: "owned" }] });
  await page.goto("/#dashboard");
  await page.locator(".priority-card").first().click();
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await editor.getByRole("radio", { name: "Aléatoire" }).click();
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.skin_mode).toBe("random");
  await editor.getByRole("button", { name: /Pool aléatoire/ }).click();

  const picker = page.getByRole("dialog", { name: "Galerie des skins" });
  const ownedOnly = picker.getByRole("checkbox", { name: "Possédés uniquement" });
  await expect(ownedOnly).toBeChecked();
  await ownedOnly.uncheck();
  const commando = picker.getByRole("checkbox", { name: "Commando Garen" });
  await commando.click();
  await expect(commando).toBeChecked();
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.random_skin_pool.map((skin: { skin_id: number }) => skin.skin_id)).toContain(86001);

  await ownedOnly.check();
  await expect(commando).toHaveCount(0);
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.random_skin_pool.map((skin: { skin_id: number }) => skin.skin_id)).toContain(86001);
  await ownedOnly.uncheck();
  await expect(commando).toBeChecked();
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.random_skin_pool.map((skin: { skin_id: number }) => skin.skin_id)).toContain(86001);
});

test("disabling skins restores the champion portrait and disables the skin picker", async ({ page }) => {
  await setupApplication(page, { configured: true });
  await page.goto("/#dashboard");
  const card = page.locator(".priority-card").first();
  await card.click();
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await editor.getByRole("radio", { name: "Aucun" }).click();

  await expect.poll(async () => (await readPresets(page)).slots.pick_1.skin_mode).toBe("none");
  await expect(card.locator(".priority-art img")).toHaveAttribute("src", /\/api\/assets\/champions\/86\/splash/);
  await expect(editor.getByRole("button", { name: /Galerie des skins/ })).toBeDisabled();
});

test("spell Select exposes the real catalogue and persists a distinct spell by typeahead", async ({ page }) => {
  await setupApplication(page, { configured: true });
  await page.goto("/#dashboard");
  await page.locator(".priority-card").first().click();

  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  const spellSelect = editor.getByRole("combobox", { name: "Sort 1" });
  const selectedFlash = spellSelect.locator("img.spell-select-icon");
  await expect.poll(() => selectedFlash.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true);
  const selectedIgnite = editor.getByRole("combobox", { name: "Sort 2" }).locator("img.spell-select-icon");
  await expect.poll(() => selectedIgnite.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true);
  await spellSelect.focus();
  await page.keyboard.press("Enter");
  const flashOption = page.getByRole("option", { name: "Flash" });
  const teleportOption = page.getByRole("option", { name: "Teleport" });
  await expect(flashOption).toBeVisible();
  await expect(teleportOption).toBeVisible();
  await expect.poll(() => flashOption.locator("img.spell-select-icon").evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true);
  await page.keyboard.press("Escape");
  await expect(flashOption).toBeHidden();
  await expect(spellSelect).toBeFocused();

  await page.keyboard.press("Enter");
  await page.keyboard.press("t");
  await expect(teleportOption).toBeFocused();
  await page.keyboard.press("Enter");
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.spell_1).toBe("Teleport");
  await expect(spellSelect).toContainText("Teleport");
});

test("both spell fields accept distinct choices and None survives reopening", async ({ page }) => {
  await setupApplication(page, { configured: true });
  await page.goto("/#dashboard");
  await page.locator(".priority-card").first().click();

  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  const firstSpell = editor.getByRole("combobox", { name: "Sort 1" });
  const secondSpell = editor.getByRole("combobox", { name: "Sort 2" });
  await firstSpell.click();
  await page.getByRole("option", { name: "Teleport" }).click();
  await secondSpell.click();
  await page.getByRole("option", { name: "Flash" }).click();

  await expect.poll(async () => (await readPresets(page)).slots.pick_1).toMatchObject({ spell_1: "Teleport", spell_2: "Flash" });
  await secondSpell.click();
  await page.getByRole("option", { name: "Aucun" }).click();
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.spell_2).toBe("(None)");

  await editor.getByRole("button", { name: "Fermer" }).last().click();
  await page.locator(".priority-card").first().click();
  const reopened = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await expect(reopened.getByRole("combobox", { name: "Sort 1" })).toContainText("Teleport");
  await expect(reopened.getByRole("combobox", { name: "Sort 2" })).toContainText("Aucun");
  await expect.poll(async () => (await readPresets(page)).slots.pick_1).toMatchObject({ spell_1: "Teleport", spell_2: "(None)" });
});

test("each Dashboard automation switch persists its own setting", async ({ page }) => {
  await setupApplication(page, {
    configured: true,
    settings: {
      auto_accept_enabled: false,
      auto_pick_enabled: false,
      auto_ban_enabled: false,
      auto_summoners_enabled: false,
      skin_automation_enabled: false,
      auto_play_again_enabled: false,
    },
  });
  await page.goto("/#dashboard");

  for (const [label, key] of [
    ["Auto-Accept", "auto_accept_enabled"],
    ["Auto-Pick", "auto_pick_enabled"],
    ["Auto-Ban", "auto_ban_enabled"],
    ["Auto-Summs", "auto_summoners_enabled"],
    ["Skin", "skin_automation_enabled"],
    ["Auto Play Again", "auto_play_again_enabled"],
  ]) {
    const toggle = page.getByRole("switch", { name: label });
    await expect(toggle).toHaveAttribute("aria-checked", "false");
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-checked", "true");
    await expect.poll(async () => (await readSettings(page))[key]).toBe(true);
  }
});
