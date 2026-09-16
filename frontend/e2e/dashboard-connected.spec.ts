import { expect, test } from "@playwright/test";
import { mockLocalApi } from "./helpers";

test("dashboard connecté concentre l’identité et la phase dans la barre supérieure", async ({ page }) => {
  await mockLocalApi(page, { connected: true, configured: true });
  await page.goto("/#dashboard");
  await expect(page.getByText("Player#EUW")).toBeVisible();
  await expect(page.getByText("Dans le lobby")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Garen" })).toBeVisible();

  const request = page.waitForRequest((candidate) => candidate.url().endsWith("/api/settings") && candidate.method() === "PATCH");
  await page.getByRole("combobox", { name: "Mode de skin du slot 1" }).selectOption("random");
  expect((await request).postDataJSON().main_skin_mode_overrides.pick_1).toBe("random");
});

test("dashboard uses bootstrap previews instead of per-champion catalogs", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  await mockLocalApi(page, { connected: true, configured: true, assignedPosition: "TOP" });
  await page.goto("/#dashboard");

  await expect(page.locator(".priority-card")).toHaveCount(3);
  await expect(page.locator(".priority-role")).toHaveCount(0);
  await expect(page.locator(".ban-visual img")).toHaveAttribute("src", "/assets/app/garen.webp");
  expect(requests.some((url) => /\/api\/(champions|skins)\//.test(url))).toBe(false);
});
