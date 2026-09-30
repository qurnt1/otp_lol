import { expect, setupApplication, test } from "./helpers";

test("Data Dragon offline state keeps the application navigable with a warning", async ({ page }) => {
  let bootstrapRequests = 0;
  page.on("request", (request) => {
    if (request.url().endsWith("/api/bootstrap")) bootstrapRequests += 1;
  });

  await setupApplication(page, { networkStatus: "offline" });
  await page.goto("/#dashboard");

  await expect(page.getByRole("heading", { name: "Préparation de partie", exact: true })).toBeVisible();
  await expect(page.locator(".network-warning")).toContainText("Connexion Internet indisponible");
  const warningImage = page.getByRole("img", { name: "Illustration OTP LOL hors connexion" });
  await expect(warningImage).toHaveAttribute("src", "/assets/app/garen.webp");
  await expect.poll(() => warningImage.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true);
  await expect(page.getByRole("navigation")).toBeVisible();
  expect(bootstrapRequests).toBeGreaterThan(0);
});

test("a pending network check shows checking feedback without a retry action", async ({ page }) => {
  await setupApplication(page, { networkStatus: "online" });
  let releaseStatusRequest!: () => void;
  const held = new Promise<void>((resolve) => { releaseStatusRequest = resolve; });
  let heldStatusRequest = false;
  await page.route("**/api/network/status", async (route) => {
    if (route.request().method() === "GET" && !heldStatusRequest) {
      heldStatusRequest = true;
      await held;
    }
    await route.continue();
  });

  await page.goto("/#dashboard");
  const warning = page.locator(".network-warning");
  await expect(warning).toContainText("OTP LOL vérifie si l’ordinateur peut joindre les services nécessaires.");
  await expect(warning.getByRole("button")).toHaveCount(0);
  await expect(page.getByRole("navigation")).toBeVisible();
  releaseStatusRequest();
  await expect(warning).toHaveCount(0);
});

test("offline retry button stays inside the 1086x753 viewport", async ({ page }) => {
  await page.setViewportSize({ width: 1086, height: 753 });
  await setupApplication(page, { networkStatus: "offline" });
  await page.goto("/#dashboard");

  const warning = page.locator(".network-warning");
  const retryButton = page.getByRole("button", { name: "Réessayer maintenant" });
  await expect(warning).toBeVisible();
  await expect(retryButton).toBeVisible();
  const warningBounds = await warning.boundingBox();
  const bounds = await retryButton.boundingBox();
  expect(warningBounds).not.toBeNull();
  expect(bounds).not.toBeNull();
  expect(bounds!.x).toBeGreaterThanOrEqual(0);
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(1086);
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(warningBounds!.x + warningBounds!.width);
});

test("local network-status failure shows recovery and retries the real endpoint", async ({ page }) => {
  let abortedStatusRequest = false;
  let retryRequested = false;
  const failedStatusRequests: string[] = [];
  const successfulStatusResponses: number[] = [];
  await setupApplication(page, { networkStatus: "online" });
  await page.route("**/api/network/status", async (route) => {
    if (!abortedStatusRequest || !retryRequested) {
      abortedStatusRequest = true;
      await route.abort("failed");
      return;
    }
    await route.continue();
  });
  page.on("requestfailed", (request) => {
    if (new URL(request.url()).pathname === "/api/network/status") {
      failedStatusRequests.push(request.failure()?.errorText ?? "unknown failure");
    }
  });
  page.on("response", (response) => {
    if (new URL(response.url()).pathname === "/api/network/status") {
      successfulStatusResponses.push(response.status());
    }
  });
  await page.goto("/#dashboard");

  await expect(page.getByText("Le serveur local ne répond pas.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Réessayer" })).toBeVisible();
  await expect.poll(() => failedStatusRequests.length).toBeGreaterThan(0);
  const retryResponse = page.waitForResponse((response) => new URL(response.url()).pathname === "/api/network/status");
  retryRequested = true;
  await page.getByRole("button", { name: "Réessayer" }).click();
  const response = await retryResponse;
  expect(response.status()).toBe(200);
  await expect.poll(() => successfulStatusResponses).toEqual([200]);
  await expect(page.getByText("Le serveur local ne répond pas.")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Préparation de partie" })).toBeVisible();
  expect(abortedStatusRequest).toBe(true);
});

test("network warning remains during an outage and clears after a real retry", async ({ page }) => {
  const { app } = await setupApplication(page, { networkStatus: "offline" });
  await page.goto("/#dashboard");

  await expect(page.locator(".network-warning")).toBeVisible();
  await page.getByRole("button", { name: "Réessayer maintenant" }).click();
  await expect(page.locator(".network-warning")).toBeVisible();

  await app.configureExternalState({ dataDragon: "online" });
  await page.getByRole("button", { name: "Réessayer maintenant" }).click();

  await expect(page.locator(".network-warning")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Préparation de partie", exact: true })).toBeVisible();
});
