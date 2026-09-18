import { expect, test } from "@playwright/test";

import { mockLocalApi } from "./helpers";

test("settings deep links and browser back-forward restore the selected section", async ({ page }) => {
  await mockLocalApi(page);
  await page.goto("/#settings/links");
  await expect(page.locator(".settings-section h2")).toHaveText("Liens");

  await page.getByRole("button", { name: "Raccourcis" }).click();
  await expect(page).toHaveURL(/#settings\/shortcuts$/);
  await expect(page.locator(".settings-section h2")).toHaveText("Raccourcis");

  await page.goBack();
  await expect(page).toHaveURL(/#settings\/links$/);
  await expect(page.locator(".settings-section h2")).toHaveText("Liens");
  await page.goForward();
  await expect(page).toHaveURL(/#settings\/shortcuts$/);
  await expect(page.locator(".settings-section h2")).toHaveText("Raccourcis");
});

test("dashboard account-statistics action opens the provider profile without native account requests", async ({ page }) => {
  const accountRequests: string[] = [];
  const statsLinkRequests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/account/")) accountRequests.push(url.pathname);
    if (url.pathname === "/api/links/stats") statsLinkRequests.push(url.pathname);
  });
  await mockLocalApi(page);
  await page.goto("/#dashboard");
  await expect(page.getByRole("heading", { name: "Préparation de partie" })).toBeVisible();
  expect(accountRequests).toHaveLength(0);

  await page.getByRole("link", { name: "Ouvrir les statistiques du compte" }).click();
  await expect(page).toHaveURL(/#statistics$/);
  await expect(page.getByRole("heading", { name: "Statistiques" })).toBeVisible();
  await expect.poll(() => statsLinkRequests.length).toBe(1);
  expect(accountRequests).toEqual([]);
});

test("sidebar settings action opens the default settings deep link", async ({ page }) => {
  await mockLocalApi(page);
  await page.goto("/#dashboard");
  await page.getByRole("link", { name: "Réglages" }).click();
  await expect(page).toHaveURL(/#settings\/general$/);
  await expect(page.locator(".settings-section h2")).toHaveText("Général");
});
