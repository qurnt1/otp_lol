import { expect, test } from "@playwright/test";
import { mockLocalApi } from "./helpers";

test("dashboard déconnecté affiche l’état utile sans charger les catalogues", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  await mockLocalApi(page);
  await page.goto("/#dashboard");
  await expect(page.getByRole("heading", { name: "Préparation de partie" })).toBeVisible();
  await expect(page.getByRole("switch", { name: "Auto-Accept" })).toHaveAttribute("aria-checked", "false");
  expect(requests.some((url) => url.includes("/api/champions") || url.includes("/api/skins/"))).toBe(false);
});

test("le contrôle des mises à jour est différé après le premier rendu", async ({ page }) => {
  await page.clock.install({ time: new Date("2026-01-01T00:00:00Z") });
  await mockLocalApi(page);
  let updateRequests = 0;
  await page.route("**/api/updates", async (route) => {
    updateRequests += 1;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ available: false, update: null }) });
  });

  await page.goto("/#dashboard");
  await expect(page.getByRole("heading", { name: "Préparation de partie" })).toBeVisible();
  await page.clock.fastForward(6_999);
  expect(updateRequests).toBe(0);
  await page.clock.fastForward(1);
  await expect.poll(() => updateRequests).toBe(1);
});
