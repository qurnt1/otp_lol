import { expect, readPresets, readSettings, setupApplication, test } from "./helpers";

const presetFixtures = {
  pick_1: {
    champion: "Garen",
    spell_1: "Ghost",
    spell_2: "Flash",
    skin_mode: "fixed",
    skin_id: 86013,
    skin_name: "God-King Garen",
    skin_num: 13,
    rune_page_id: 401,
    rune_page_name: "Garen Precision",
    rune_auto_apply: true,
    rune_keystone_id: 8005,
    rune_keystone_path: "8000/8005.png",
    rune_sub_style_icon_path: "8100.png",
  },
  pick_2: {
    champion: "Lux",
    spell_1: "Heal",
    spell_2: "Teleport",
    skin_mode: "fixed",
    skin_id: 99010,
    skin_name: "Battle Academia Lux",
    skin_num: 10,
    rune_page_id: 402,
    rune_page_name: "Lux Sorcery",
    rune_auto_apply: false,
    rune_keystone_id: 8229,
    rune_keystone_path: "8200/8229.png",
    rune_sub_style_icon_path: "8300.png",
  },
  pick_3: {
    champion: "Ashe",
    spell_1: "Barrier",
    spell_2: "Cleanse",
    skin_mode: "fixed",
    skin_id: 22004,
    skin_name: "Queen Ashe",
    skin_num: 4,
    rune_page_id: 403,
    rune_page_name: "Ashe Precision",
    rune_auto_apply: true,
    rune_keystone_id: 8008,
    rune_keystone_path: "8000/8008.png",
    rune_sub_style_icon_path: "8300.png",
  },
};

async function seedPresets(page: Parameters<typeof setupApplication>[0], app: { baseURL: string }) {
  const origin = new URL(app.baseURL).origin;
  for (const [slot, preset] of Object.entries(presetFixtures)) {
    const response = await page.request.put(new URL(`/api/presets/${slot}`, origin).href, {
      headers: { Origin: origin },
      data: preset,
    });
    expect(response.status(), `seed ${slot}`).toBe(200);
  }
}

async function visibleChampionOrder(page: Parameters<typeof setupApplication>[0]) {
  return page.locator(".priority-card h3").allTextContents();
}

test("priority cards can be dragged, moved by keyboard, and keep the complete preset blocks after reload", async ({ page }) => {
  const { app } = await setupApplication(page, { configured: true });
  await seedPresets(page, app);
  await page.goto("/#dashboard");

  const cards = page.locator(".priority-card");
  await expect(cards).toHaveCount(3);
  await expect.poll(() => visibleChampionOrder(page)).toEqual(["Garen", "Lux", "Ashe"]);

  const reorderResponse = page.waitForResponse((response) =>
    response.request().method() === "PUT"
      && new URL(response.url()).pathname === "/api/presets/order"
      && response.status() === 200,
  );
  await cards.nth(0).getByRole("button", { name: /Faire glisser pour réordonner/ }).dragTo(cards.nth(1));
  const response = await reorderResponse;
  expect(response.request().postDataJSON()).toEqual({ order: ["pick_2", "pick_1", "pick_3"] });
  await expect.poll(() => visibleChampionOrder(page)).toEqual(["Lux", "Garen", "Ashe"]);
  await expect.poll(async () => (await readPresets(page)).slots).toMatchObject({
    pick_1: presetFixtures.pick_2,
    pick_2: presetFixtures.pick_1,
    pick_3: presetFixtures.pick_3,
  });
  await expect.poll(async () => {
    const settings = await readSettings(page);
    return [settings.selected_pick_1, settings.selected_pick_2, settings.selected_pick_3];
  }).toEqual(["Lux", "Garen", "Ashe"]);

  await page.reload();
  await expect.poll(() => visibleChampionOrder(page)).toEqual(["Lux", "Garen", "Ashe"]);

  const moveUp = cards.nth(1).getByRole("button", { name: /Monter dans les priorités.*Garen/ });
  await expect(moveUp).toBeEnabled();
  const keyboardReorder = page.waitForResponse((nextResponse) =>
    nextResponse.request().method() === "PUT"
      && new URL(nextResponse.url()).pathname === "/api/presets/order"
      && nextResponse.status() === 200,
  );
  await moveUp.focus();
  await page.keyboard.press("Enter");
  expect((await keyboardReorder).request().postDataJSON()).toEqual({ order: ["pick_2", "pick_1", "pick_3"] });
  await expect.poll(() => visibleChampionOrder(page)).toEqual(["Garen", "Lux", "Ashe"]);
  await expect.poll(async () => (await readPresets(page)).slots).toMatchObject({
    pick_1: presetFixtures.pick_1,
    pick_2: presetFixtures.pick_2,
    pick_3: presetFixtures.pick_3,
  });
});

test("a failed preset reorder restores the previous card order and leaves saved settings unchanged", async ({ page }) => {
  const { app } = await setupApplication(page, { configured: true });
  await seedPresets(page, app);
  await page.goto("/#dashboard");
  const beforePresets = await readPresets(page);
  const beforeSettings = await readSettings(page);
  await page.route("**/api/presets/order", (route) => route.fulfill({
    status: 503,
    contentType: "application/json",
    body: JSON.stringify({ detail: "Injected preset-order outage" }),
  }));

  await page.locator(".priority-card").first().getByRole("button", { name: /Descendre dans les priorités.*Garen/ }).click();
  await expect(page.getByRole("alert")).toHaveText("Impossible d’enregistrer l’ordre des priorités.");
  await expect.poll(() => visibleChampionOrder(page)).toEqual(["Garen", "Lux", "Ashe"]);
  expect(await readPresets(page)).toEqual(beforePresets);
  expect(await readSettings(page)).toEqual(beforeSettings);
});

test("a failed bootstrap refresh after reorder never reuses the previous slot preview", async ({ page }) => {
  const { app } = await setupApplication(page, { configured: true });
  await seedPresets(page, app);
  let bootstrapReads = 0;
  await page.route("**/__e2e__/stale-preview.svg", (route) => route.fulfill({
    status: 200,
    contentType: "image/svg+xml",
    body: "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"2\" height=\"2\"><rect width=\"2\" height=\"2\" fill=\"#f00\"/></svg>",
  }));
  await page.route("**/api/bootstrap", async (route) => {
    bootstrapReads += 1;
    if (bootstrapReads > 1) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Injected bootstrap refresh failure" }),
      });
      return;
    }
    const response = await route.fetch();
    const bootstrap = await response.json() as {
      preset_previews?: Record<string, Record<string, unknown>>;
    };
    bootstrap.preset_previews = {
      ...bootstrap.preset_previews,
      pick_1: {
        ...bootstrap.preset_previews?.pick_1,
        champion_id: 86,
        champion_name: "Garen",
        skin_preview_url: "/__e2e__/stale-preview.svg",
      },
    };
    await route.fulfill({ response, body: JSON.stringify(bootstrap) });
  });

  await page.goto("/#dashboard");
  await expect.poll(() => bootstrapReads).toBe(1);
  await expect(page.locator(".priority-card .priority-art img[src='/__e2e__/stale-preview.svg']")).toHaveCount(1);

  const reorderResponse = page.waitForResponse((response) =>
    response.request().method() === "PUT"
      && new URL(response.url()).pathname === "/api/presets/order"
      && response.status() === 200,
  );
  await page.locator(".priority-card").first().getByRole("button", { name: /Descendre dans les priorités.*Garen/ }).click();
  await reorderResponse;

  await expect.poll(() => visibleChampionOrder(page)).toEqual(["Lux", "Garen", "Ashe"]);
  await expect(page.locator(".priority-reorder-feedback")).toHaveText("Ordre des priorités enregistré.");
  await expect.poll(() => bootstrapReads).toBeGreaterThanOrEqual(2);
  await expect(page.locator(".priority-card .priority-art img[src='/__e2e__/stale-preview.svg']")).toHaveCount(0);
});

test("Quick Actions has one accessible title", async ({ page }) => {
  await setupApplication(page, { configured: true });
  await page.goto("/#dashboard");

  const quickActions = page.locator(".quick-panel");
  const quickLinks = quickActions.locator("a.quick-link");
  await expect(quickActions).toHaveAttribute("aria-labelledby", "quick-heading");
  await expect(quickActions.getByRole("heading", { name: "Accès rapides", exact: true })).toHaveCount(1);
  await expect(quickActions.locator(".section-label")).toHaveCount(0);
  await expect(quickLinks).toHaveCount(5);
  expect(await quickLinks.evaluateAll((links) => links.map((link) => link.getAttribute("href")))).toEqual([
    "#statistics",
    "#live",
    "#history",
    "#diagnostics",
    "#settings/shortcuts",
  ]);
  const content = await quickActions.innerText();
  expect(content.match(/Accès rapides/g)).toHaveLength(1);
});

test("skin catalogue thumbnails defer offscreen requests until the user scrolls to them", async ({ page }) => {
  const { app } = await setupApplication(page, { configured: true, networkStatus: "online" });
  await page.setViewportSize({ width: 1280, height: 720 });

  const requestedSkinIds = new Set<number>();
  await page.route("**/api/skins/86", async (route) => {
    const response = await route.fetch();
    const body = await response.json() as {
      catalog: Array<Record<string, unknown>>;
      owned: Record<string, unknown>;
    };
    expect(body.catalog.length).toBeGreaterThan(0);
    const template = body.catalog[0];
    const catalog = Array.from({ length: 300 }, (_, index) => {
      const skinId = 86_000 + index;
      return {
        ...template,
        skin_id: skinId,
        skin_name: `Fixture Skin ${index}`,
        skin_num: index,
        tile_url: `/api/assets/skins/86/${skinId}.png?v=16.1.1`,
      };
    });
    await route.fulfill({
      response,
      body: JSON.stringify({
        ...body,
        catalog,
        owned: { ok: false, owned_skins: [], message: "League client unavailable in fixture." },
      }),
    });
  });
  await page.route(/\/api\/assets\/skins\/86\/(\d+)\.png(?:\?.*)?$/, async (route) => {
    const imagePath = new URL(route.request().url()).pathname;
    const skinId = Number(/\/(\d+)\.png$/.exec(imagePath)?.[1]);
    requestedSkinIds.add(skinId);
    await route.fulfill({
      status: 200,
      contentType: "image/svg+xml",
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2"><rect width="2" height="2" fill="#345"/></svg>',
    });
  });

  await page.goto("/#dashboard");
  await page.locator(".priority-card").first().click();

  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await editor.getByRole("button", { name: /Galerie des skins/ }).click();
  const picker = page.getByRole("dialog", { name: "Galerie des skins" });
  const thumbnails = picker.locator(".skin-option img");
  await expect(thumbnails).toHaveCount(300);
  await expect(thumbnails.first()).toBeVisible();
  await expect(thumbnails.first()).toHaveAttribute("loading", "lazy");
  await expect(thumbnails.first()).toHaveAttribute("decoding", "async");
  await expect(thumbnails.first()).toHaveJSProperty("fetchPriority", "auto");
  await expect(thumbnails.nth(13)).toHaveJSProperty("fetchPriority", "high");
  expect(await thumbnails.evaluateAll((images) => images.filter((image) => (
    (image as HTMLImageElement).fetchPriority === "high"
  )).length)).toBe(1);

  const lastThumbnail = thumbnails.last();
  const lastThumbnailUrl = await lastThumbnail.getAttribute("src");
  expect(lastThumbnailUrl).toBeTruthy();
  const lastThumbnailPath = new URL(lastThumbnailUrl!, app.baseURL).pathname;
  const lastSkinId = Number(/\/(\d+)\.png$/.exec(lastThumbnailPath)?.[1]);
  expect(Number.isInteger(lastSkinId)).toBe(true);
  await expect(lastThumbnail).not.toBeInViewport();
  await expect.poll(() => requestedSkinIds.size).toBeGreaterThan(0);
  await expect.poll(() => thumbnails.first().evaluate((image: HTMLImageElement) => (
    image.complete && image.naturalWidth > 0
  ))).toBe(true);
  await page.evaluate(() => new Promise<void>((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
  }));
  expect(requestedSkinIds.has(lastSkinId)).toBe(false);

  const lastThumbnailRequest = page.waitForRequest((request) => (
    new URL(request.url()).pathname === lastThumbnailPath
  ));
  await lastThumbnail.scrollIntoViewIfNeeded();
  await lastThumbnailRequest;
  await expect.poll(() => requestedSkinIds.has(lastSkinId)).toBe(true);
});

test("a missing skin thumbnail shows the SKIN fallback", async ({ page }) => {
  await setupApplication(page, { configured: true, networkStatus: "online" });
  let failedTileRequests = 0;
  await page.route(/\/api\/assets\/skins\/86\/\d+\.png(?:\?.*)?$/, async (route) => {
    failedTileRequests += 1;
    await route.abort("failed");
  });

  await page.goto("/#dashboard");
  await page.locator(".priority-card").first().click();

  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await editor.getByRole("button", { name: /Galerie des skins/ }).click();
  const picker = page.getByRole("dialog", { name: "Galerie des skins" });
  const failedThumbnail = picker.locator(".skin-option").first();
  await expect(failedThumbnail.locator(".asset-fallback")).toHaveText("SKIN");
  await expect(failedThumbnail.locator(".skin-thumbnail-placeholder")).toHaveCount(0);
  expect(failedTileRequests).toBeGreaterThan(0);
});
