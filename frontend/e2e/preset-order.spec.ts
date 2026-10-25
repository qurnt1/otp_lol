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

async function visibleCardFrames(page: Parameters<typeof setupApplication>[0], frameCount = 12) {
  return page.evaluate(async (count) => {
    const frames: Array<Array<{ champion: string; spells: string[]; rune: string; skin: string; images: Array<string | null>; x: number; y: number }>> = [];
    for (let index = 0; index < count; index += 1) {
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
      frames.push(Array.from(document.querySelectorAll<HTMLElement>(".priority-card"), (card) => {
        const rect = card.getBoundingClientRect();
        return {
          champion: card.querySelector("h3")?.textContent?.trim() ?? "",
          spells: Array.from(card.querySelectorAll<HTMLImageElement>(".summoner-row img"), (image) => image.title),
          rune: card.querySelector(".rune-name")?.textContent?.trim() ?? "",
          skin: card.querySelector(".skin-preview strong")?.textContent?.trim() ?? "",
          images: [
            card.querySelector<HTMLImageElement>(".priority-art img")?.getAttribute("src") ?? null,
            card.querySelector<HTMLImageElement>(".skin-preview img")?.getAttribute("src") ?? null,
          ],
          x: Math.round(rect.x),
          y: Math.round(rect.y),
        };
      }));
    }
    return frames;
  }, frameCount);
}

test("a short click opens the preset, while a held card drag reorders complete presets and keyboard shortcuts remain available", async ({ page }) => {
  const { app } = await setupApplication(page, { configured: true });
  await seedPresets(page, app);
  await page.goto("/#dashboard");

  const cards = page.locator(".priority-card");
  await expect(cards).toHaveCount(3);
  await expect.poll(() => visibleChampionOrder(page)).toEqual(["Garen", "Lux", "Ashe"]);

  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await cards.nth(0).click();
  await expect(editor).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(editor).toHaveCount(0);

  const reorderResponse = page.waitForResponse((response) =>
    response.request().method() === "PUT"
      && new URL(response.url()).pathname === "/api/presets/order"
      && response.status() === 200,
  );
  let delayNextReorder = true;
  await page.route("**/api/presets/order", async (route) => {
    if (delayNextReorder) {
      delayNextReorder = false;
      await new Promise((resolve) => setTimeout(resolve, 300));
    }
    await route.continue();
  });
  const sourceBox = await cards.nth(0).boundingBox();
  const targetBox = await cards.nth(1).boundingBox();
  expect(sourceBox).not.toBeNull();
  expect(targetBox).not.toBeNull();
  await page.mouse.move(sourceBox!.x + sourceBox!.width / 2, sourceBox!.y + sourceBox!.height / 2);
  await page.mouse.down();
  await expect(cards.nth(0)).toHaveClass(/is-press-armed/);
  await page.mouse.move(targetBox!.x + targetBox!.width / 2, targetBox!.y + targetBox!.height / 2, { steps: 5 });
  await expect(cards.nth(0)).toHaveClass(/is-dragging/);
  await expect(cards.nth(1)).toHaveClass(/is-drop-target/);
  await expect(cards.nth(1)).toHaveClass(/is-preview-shifted/);
  await expect.poll(async () => {
    const previewBox = await cards.nth(1).boundingBox();
    return previewBox ? Math.abs(previewBox.x - sourceBox!.x) < 3 : false;
  }).toBe(true);
  const targetPreviewBox = await cards.nth(1).boundingBox();
  expect(targetPreviewBox).not.toBeNull();
  expect(targetPreviewBox!.x).toBeLessThan(targetBox!.x - 3);
  await page.mouse.up();
  const observedCards = await visibleCardFrames(page);
  expect(observedCards.slice(1)).toEqual(Array.from({ length: 11 }, () => observedCards[0]));
  expect(observedCards[0].map((card) => card.champion)).toEqual(["Lux", "Garen", "Ashe"]);
  const response = await reorderResponse;
  const savedCardFrames = await visibleCardFrames(page);
  expect(savedCardFrames.slice(1)).toEqual(Array.from({ length: 11 }, () => savedCardFrames[0]));
  expect(savedCardFrames[0].map((card) => card.champion)).toEqual(["Lux", "Garen", "Ashe"]);
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

  const moveUp = cards.nth(1).locator(".priority-card-link");
  const keyboardReorder = page.waitForResponse((nextResponse) =>
    nextResponse.request().method() === "PUT"
      && new URL(nextResponse.url()).pathname === "/api/presets/order"
      && nextResponse.status() === 200,
  );
  await moveUp.focus();
  await page.keyboard.press("Alt+ArrowUp");
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

  await page.locator(".priority-card-link").first().focus();
  await page.keyboard.press("Alt+ArrowDown");
  await expect(page.getByRole("alert")).toHaveText("Impossible d’enregistrer l’ordre des priorités.");
  await expect.poll(() => visibleChampionOrder(page)).toEqual(["Garen", "Lux", "Ashe"]);
  expect(await readPresets(page)).toEqual(beforePresets);
  expect(await readSettings(page)).toEqual(beforeSettings);
});

test("dragging the second or third preset to the first position shifts siblings right inside the grid", async ({ page }) => {
  const { app } = await setupApplication(page, { configured: true });
  await seedPresets(page, app);
  await page.goto("/#dashboard");

  const cards = page.locator(".priority-card");
  await expect.poll(() => visibleChampionOrder(page)).toEqual(["Garen", "Lux", "Ashe"]);

  for (const sourceIndex of [1, 2]) {
    const originalXs = await cards.evaluateAll((nodes) => nodes.map((node) => (node as HTMLElement).getBoundingClientRect().x));
    const sourceBox = await cards.nth(sourceIndex).boundingBox();
    const targetBox = await cards.nth(0).boundingBox();
    expect(sourceBox).not.toBeNull();
    expect(targetBox).not.toBeNull();

    await page.mouse.move(sourceBox!.x + sourceBox!.width / 2, sourceBox!.y + sourceBox!.height / 2);
    await page.mouse.down();
    await expect(cards.nth(sourceIndex)).toHaveClass(/is-press-armed/);
    await page.mouse.move(targetBox!.x + targetBox!.width / 2, targetBox!.y + targetBox!.height / 2, { steps: 5 });
    await expect(cards.nth(sourceIndex)).toHaveClass(/is-dragging/);
    await expect(cards.nth(0)).toHaveClass(/is-preview-shifted/);

    for (let shiftedIndex = 0; shiftedIndex < sourceIndex; shiftedIndex += 1) {
      await expect.poll(async () => {
        const previewBox = await cards.nth(shiftedIndex).boundingBox();
        return previewBox ? previewBox.x : originalXs[shiftedIndex];
      }).toBeGreaterThan(originalXs[shiftedIndex] + 20);
    }

    const reorderResponse = page.waitForResponse((response) =>
      response.request().method() === "PUT"
        && new URL(response.url()).pathname === "/api/presets/order"
        && response.status() === 200,
    );
    await page.mouse.up();
    await reorderResponse;

    const expectedOrder = sourceIndex === 1 ? ["Lux", "Garen", "Ashe"] : ["Ashe", "Lux", "Garen"];
    await expect.poll(() => visibleChampionOrder(page)).toEqual(expectedOrder);
  }
});

test("dragging outside the priority grid cancels the preview without saving a new order", async ({ page }) => {
  const { app } = await setupApplication(page, { configured: true });
  await seedPresets(page, app);
  await page.goto("/#dashboard");
  let reorderRequests = 0;
  await page.route("**/api/presets/order", async (route) => {
    reorderRequests += 1;
    await route.continue();
  });

  const cards = page.locator(".priority-card");
  const sourceBox = await cards.nth(0).boundingBox();
  const targetBox = await cards.nth(1).boundingBox();
  const gridBox = await page.locator(".priority-grid").boundingBox();
  expect(sourceBox).not.toBeNull();
  expect(targetBox).not.toBeNull();
  expect(gridBox).not.toBeNull();

  await page.mouse.move(sourceBox!.x + sourceBox!.width / 2, sourceBox!.y + sourceBox!.height / 2);
  await page.mouse.down();
  await expect(cards.nth(0)).toHaveClass(/is-press-armed/);
  await page.mouse.move(targetBox!.x + targetBox!.width / 2, targetBox!.y + targetBox!.height / 2, { steps: 4 });
  await expect(cards.nth(0)).toHaveClass(/is-dragging/);
  await expect(cards.nth(1)).toHaveClass(/is-preview-shifted/);

  await page.mouse.move(gridBox!.x + gridBox!.width + 80, gridBox!.y + gridBox!.height + 80);
  await expect(cards.nth(1)).not.toHaveClass(/is-preview-shifted/);
  await page.mouse.up();

  expect(reorderRequests).toBe(0);
  await expect.poll(() => visibleChampionOrder(page)).toEqual(["Garen", "Lux", "Ashe"]);
  expect((await readPresets(page)).slots).toMatchObject({
    pick_1: presetFixtures.pick_1,
    pick_2: presetFixtures.pick_2,
    pick_3: presetFixtures.pick_3,
  });
});

test("a cached skin preview stays with its preset when the bootstrap refresh fails", async ({ page }) => {
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
  await page.locator(".priority-card-link").first().focus();
  await page.keyboard.press("Alt+ArrowDown");
  await reorderResponse;

  await expect.poll(() => visibleChampionOrder(page)).toEqual(["Lux", "Garen", "Ashe"]);
  await expect(page.locator(".priority-reorder-feedback")).toHaveText("Ordre des priorités enregistré.");
  await expect.poll(() => bootstrapReads).toBeGreaterThanOrEqual(2);
  await expect(page.locator(".priority-card").nth(0).locator(".priority-art img[src='/__e2e__/stale-preview.svg']")).toHaveCount(0);
  await expect(page.locator(".priority-card").nth(1).locator(".priority-art img[src='/__e2e__/stale-preview.svg']")).toHaveCount(1);
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
