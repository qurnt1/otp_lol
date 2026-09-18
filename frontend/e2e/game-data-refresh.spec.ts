import { expect, test } from "@playwright/test";

import { mockLocalApi } from "./helpers";

test("game data refresh invalidates active catalogues and dashboard previews", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/")) requests.push(url.pathname);
  });
  await mockLocalApi(page, { connected: true, configured: true });
  await page.goto("/#dashboard");

  await expect(page.getByRole("heading", { name: "Préparation de partie" })).toBeVisible();
  await expect.poll(() => requests.filter((path) => path === "/api/bootstrap").length).toBe(1);
  await expect.poll(() => requests.filter((path) => path === "/api/spells").length).toBe(1);

  await page.evaluate(() => {
    const emit = (window as Window & { __otpEmitRuntimeEvent?: (event: unknown) => void }).__otpEmitRuntimeEvent;
    emit?.({ type: "game_data_updated" });
  });

  await expect.poll(() => requests.filter((path) => path === "/api/bootstrap").length).toBe(2);
  await expect.poll(() => requests.filter((path) => path === "/api/spells").length).toBe(2);
});
