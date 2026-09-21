import { expect, test } from "@playwright/test";

import { mockLocalApi } from "./helpers";

test("offline startup blocks the application on a bundled image", async ({ page }) => {
  let bootstrapRequests = 0;
  page.on("request", (request) => {
    if (request.url().endsWith("/api/bootstrap")) bootstrapRequests += 1;
  });

  await mockLocalApi(page, { networkStatus: "offline" });
  await page.goto("/#dashboard");

  await expect(page.getByRole("heading", { name: "Connexion Internet requise", exact: true })).toBeVisible();
  await expect(page.getByRole("img")).toHaveAttribute("src", "/assets/app/garen.webp");
  await expect(page.getByRole("navigation")).toHaveCount(0);
  expect(bootstrapRequests).toBe(0);
});

test("network gate unlocks after the connection is restored", async ({ page }) => {
  const network = { value: "offline" as const };
  await mockLocalApi(page, { networkStatus: network });
  await page.goto("/#dashboard");

  await expect(page.getByRole("heading", { name: "Connexion Internet requise", exact: true })).toBeVisible();
  network.value = "online";
  await page.getByRole("button", { name: "Réessayer maintenant" }).click();

  await expect(page.getByRole("heading", { name: "Préparation de partie", exact: true })).toBeVisible();
});
