import { expect, test } from "@playwright/test";
import { mockLocalApi } from "./helpers";

for (const viewport of [{ width: 1100, height: 760 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }]) {
  test(`layout propre à ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await mockLocalApi(page, { configured: true });
    await page.goto("/#dashboard");
    await expect(page.getByRole("heading", { name: "Préparation de partie" })).toBeVisible();
    await expect(page.locator("body")).toHaveScreenshot(`dashboard-${viewport.width}x${viewport.height}.png`, { animations: "disabled" });
  });
}

for (const viewport of [{ width: 1100, height: 760 }, { width: 800, height: 540 }]) {
  test(`éditeur de preset sans débordement à ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await mockLocalApi(page, { configured: true });
    await page.goto("/#presets");
    await page.locator(".preset-card").first().click();

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
  test(`éditeur de preset sans débordement au scaling ${scale * 100} %`, async ({ browser }) => {
    const context = await browser.newContext({
      viewport: { width: 1100, height: 760 },
      deviceScaleFactor: scale,
    });
    const page = await context.newPage();
    await mockLocalApi(page, { configured: true });
    await page.goto("/#presets");
    await page.locator(".preset-card").first().click();
    const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
    await expect(editor).toBeVisible();
    expect(await editor.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await context.close();
  });
}

test("layout compact reste navigable à 800x540", async ({ page }) => {
  await page.setViewportSize({ width: 800, height: 540 });
  await mockLocalApi(page);
  await page.goto("/#dashboard");
  await expect(page.getByRole("heading", { name: "Préparation de partie" })).toBeVisible();
  await expect(page.locator(".brand-mark strong")).toBeHidden();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

for (const scale of [1.25, 1.5]) {
  test(`layout desktop sans débordement au scaling ${scale * 100} %`, async ({ browser }) => {
    const context = await browser.newContext({
      viewport: { width: 1100, height: 760 },
      deviceScaleFactor: scale,
    });
    const page = await context.newPage();
    await mockLocalApi(page);
    await page.goto("/#dashboard");
    await expect(page.getByRole("heading", { name: "Préparation de partie" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await context.close();
  });
}
