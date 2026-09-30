import { createOtpPage, expect, readRuntime, setupApplication, test } from "./helpers";

for (const viewport of [
  { width: 1100, height: 760 },
  { width: 1366, height: 768 },
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
  { width: 2560, height: 1440 },
  { width: 2560, height: 1600 },
]) {
  test(`layout propre à ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    const { app } = await setupApplication(page, {
      configured: true,
      clearDetectedAccount: true,
      networkStatus: "online",
      settings: { close_app_on_lol_exit: false },
    });
    await app.configureLcuConnection({ online: false });
    await expect.poll(async () => (await readRuntime(page)).connected).toBe(false);
    await page.goto("/#dashboard");
    await expect(page.getByRole("heading", { name: "Préparation de partie" })).toBeVisible();
    const layout = await page.evaluate(() => {
      const bounds = (element: Element) => {
        const rect = element.getBoundingClientRect();
        return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom, width: rect.width, height: rect.height };
      };
      return {
        documentWidth: document.documentElement.scrollWidth,
        dashboard: bounds(document.querySelector(".dashboard-grid")!),
        main: bounds(document.querySelector(".dashboard-main")!),
        aside: bounds(document.querySelector(".dashboard-aside")!),
        cards: Array.from(document.querySelectorAll(".priority-card"), bounds),
      };
    });
    expect(layout.documentWidth).toBeLessThanOrEqual(viewport.width);
    expect(layout.cards).toHaveLength(3);
    expect(layout.main.width).toBeGreaterThan(0);
    expect(layout.aside.width).toBeGreaterThan(0);
    expect(layout.main.right).toBeLessThanOrEqual(layout.aside.left + 1);
    expect(layout.aside.right).toBeLessThanOrEqual(layout.dashboard.right + 1);
    for (const card of layout.cards) {
      expect(card.width).toBeGreaterThan(0);
      expect(card.height).toBeGreaterThan(0);
      expect(card.left).toBeGreaterThanOrEqual(layout.main.left);
      expect(card.right).toBeLessThanOrEqual(layout.main.right + 1);
    }
    for (let index = 1; index < layout.cards.length; index += 1) {
      expect(layout.cards[index].left).toBeGreaterThanOrEqual(layout.cards[index - 1].right);
    }
  });
}

for (const viewport of [{ width: 1100, height: 760 }, { width: 800, height: 540 }]) {
  test(`éditeur de preset sans débordement à ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await setupApplication(page, { configured: true });
    await page.goto("/#dashboard");
    await page.locator(".priority-card").first().click();

    const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
    await expect(editor).toBeVisible();
    await expect(editor.locator(".preset-editor-header")).toBeVisible();
    await expect(editor.locator(".preset-editor-footer")).toBeVisible();
    const dimensions = await editor.evaluate((element) => ({
      width: element.clientWidth,
      scrollWidth: element.scrollWidth,
      bodyOverflowY: getComputedStyle(element.querySelector(".preset-editor-body")!).overflowY,
    }));
    expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.width);
    expect(dimensions.bodyOverflowY).toBe("auto");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}

for (const scale of [1.25, 1.5]) {
  test(`éditeur de preset sans débordement au scaling ${scale * 100} %`, async ({ browser, otpApp }, testInfo) => {
    const { context, page } = await createOtpPage(browser, otpApp, testInfo, {
      viewport: { width: 1100, height: 760 },
      deviceScaleFactor: scale,
    });
    await setupApplication(page, { configured: true });
    await page.goto("/#dashboard");
    await page.locator(".priority-card").first().click();
    const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
    await expect(editor).toBeVisible();
    expect(await editor.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await context.close();
  });
}

test("layout compact reste navigable à 800x540", async ({ page }) => {
  await page.setViewportSize({ width: 800, height: 540 });
  await setupApplication(page);
  await page.goto("/#dashboard");
  await expect(page.getByRole("heading", { name: "Préparation de partie" })).toBeVisible();
  await expect(page.locator(".brand-mark strong")).toBeHidden();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("les écrans principaux restent lisibles et sans débordement aux quatre résolutions cibles", async ({ page }) => {
  await setupApplication(page, { connected: true, configured: true, networkStatus: "online" });
  for (const viewport of [
    { width: 1366, height: 768 },
    { width: 1920, height: 1080 },
    { width: 2560, height: 1440 },
    { width: 2560, height: 1600 },
  ]) {
    await page.setViewportSize(viewport);
    for (const [route, heading] of [
      ["/#dashboard", "Préparation de partie"],
      ["/#history", "Journal de logs"],
      ["/#statistics", "Statistiques"],
      ["/#live", "En direct"],
      ["/#settings/advanced", "Réglages"],
      ["/#diagnostics", "Diagnostics LCU"],
    ]) {
      await page.goto(route);
      await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `${route} at ${viewport.width}x${viewport.height}`).toBe(true);
      const content = await page.locator("main").boundingBox();
      if (!content) throw new Error(`Main content has no bounding box at ${route} (${viewport.width}x${viewport.height}).`);
      expect(content.width).toBeGreaterThan(0);
      expect(content.x + content.width).toBeLessThanOrEqual(viewport.width + 1);
    }
  }
});

for (const scale of [1.25, 1.5]) {
  test(`layout desktop sans débordement au scaling ${scale * 100} %`, async ({ browser, otpApp }, testInfo) => {
    const { context, page } = await createOtpPage(browser, otpApp, testInfo, {
      viewport: { width: 1100, height: 760 },
      deviceScaleFactor: scale,
    });
    await setupApplication(page);
    await page.goto("/#dashboard");
    await expect(page.getByRole("heading", { name: "Préparation de partie" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await context.close();
  });
}
