import { expect, test } from "@playwright/test";

import { mockLocalApi } from "./helpers";

test("Data Dragon offline state keeps the application navigable with a warning", async ({ page }) => {
  let bootstrapRequests = 0;
  page.on("request", (request) => {
    if (request.url().endsWith("/api/bootstrap")) bootstrapRequests += 1;
  });

  await mockLocalApi(page, { networkStatus: "offline" });
  await page.goto("/#dashboard");

  await expect(page.getByRole("heading", { name: "Préparation de partie", exact: true })).toBeVisible();
  await expect(page.locator(".network-warning")).toContainText("Connexion Internet indisponible");
  await expect(page.getByRole("navigation")).toBeVisible();
  expect(bootstrapRequests).toBeGreaterThan(0);
});

test("network warning clears after the connection is restored", async ({ page }) => {
  const network = { value: "offline" as const };
  await mockLocalApi(page, { networkStatus: network });
  await page.goto("/#dashboard");

  await expect(page.locator(".network-warning")).toBeVisible();
  network.value = "online";
  await page.getByRole("button", { name: "Réessayer maintenant" }).click();

  await expect(page.locator(".network-warning")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Préparation de partie", exact: true })).toBeVisible();
});

test("a local network API failure still blocks the application", async ({ page }) => {
  await mockLocalApi(page, { networkStatus: "online" });
  await page.route("**/api/network/status", (route) => route.abort());
  await page.goto("/#dashboard");

  await expect(page.getByText("Le serveur local ne répond pas.", { exact: true })).toBeVisible();
  await expect(page.getByRole("navigation")).toHaveCount(0);
});
