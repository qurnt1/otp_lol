import { expect, readRuntime, readSettings, setupApplication, test } from "./helpers";

test("sidebar explains that League is offline when no account is available", async ({ page }) => {
  const { app } = await setupApplication(page, { clearDetectedAccount: true });
  await app.configureLcuConnection({ online: false });
  await expect.poll(async () => (await readRuntime(page)).connected).toBe(false);
  await page.goto("/#settings/general");

  await expect(page.locator(".sidebar-runtime")).toHaveAttribute("aria-label", "Client déconnecté");
  await expect(page.locator(".sidebar-account")).toHaveText("Aucun compte connecté");
  await expect(page.locator(".sidebar-account")).toHaveAttribute("title", "Aucun compte connecté");
  await expect(page.locator(".sidebar-version")).toContainText("Version");
  await expect(page.getByRole("navigation").getByRole("link", { name: "Réglages" })).toHaveAttribute("aria-current", "page");
});

test("dashboard au repos reste utile et ne charge les catalogues qu’à la demande", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  await setupApplication(page, { phase: "None" });
  await page.goto("/#dashboard");

  await expect(page.getByRole("heading", { name: "Préparation de partie" })).toBeVisible();
  await expect(page.locator(".sidebar-runtime")).toHaveAttribute("aria-label", "Client connecté");
  await expect(page.locator(".phase-strip strong")).toHaveText("En attente");
  await expect(page.getByRole("switch", { name: "Auto-Accept" })).toHaveAttribute("aria-checked", "false");
  expect(requests.some((url) => url.includes("/api/champions") || url.includes("/api/skins/"))).toBe(false);
});

test("le contrôle des mises à jour est différé puis périodique", async ({ page }) => {
  await setupApplication(page);
  const clockStart = new Date("2026-01-01T00:00:00Z");
  await page.clock.install({ time: clockStart });
  let updateRequests = 0;
  page.on("request", (request) => {
    if (request.url().endsWith("/api/updates")) updateRequests += 1;
  });

  await page.goto("/#dashboard");
  await expect(page.getByRole("heading", { name: "Préparation de partie" })).toBeVisible();
  const elapsed = await page.evaluate((start) => Date.now() - start, clockStart.getTime());
  await page.clock.fastForward(Math.max(0, 6_500 - elapsed));
  expect(updateRequests).toBe(0);
  const firstUpdate = page.waitForResponse((response) => new URL(response.url()).pathname === "/api/updates");
  await page.clock.fastForward(2_000);
  await expect.poll(() => updateRequests).toBe(1);
  await firstUpdate;
  await page.clock.fastForward(21_600_000 - 100);
  expect(updateRequests).toBe(1);
  const secondUpdate = page.waitForResponse((response) => new URL(response.url()).pathname === "/api/updates");
  await page.clock.fastForward(100);
  await expect.poll(() => updateRequests).toBe(2);
  await secondUpdate;
  await page.clock.fastForward(21_600_000 - 100);
  expect(updateRequests).toBe(2);
  const thirdUpdate = page.waitForResponse((response) => new URL(response.url()).pathname === "/api/updates");
  await page.clock.fastForward(100);
  await expect.poll(() => updateRequests).toBe(3);
  await thirdUpdate;
});

test("une panne GitHub ne présente pas un faux bandeau de mise à jour", async ({ page }) => {
  await page.clock.install({ time: new Date("2026-01-01T00:00:00Z") });
  const { app } = await setupApplication(page);
  await page.goto("/#dashboard");
  await page.clock.fastForward(7_000);

  await expect(page.locator(".update-banner")).toHaveCount(0);
  await expect.poll(async () => app.externalFixtureRequests.some((request) =>
    request.host === "api.github.com" && request.path.endsWith("/releases/latest") && request.status === 503
  )).toBe(true);
  await expect.poll(async () => (await page.request.get(new URL("/api/updates", app.baseURL).href).then((response) => response.json())).available).toBe(false);
});

test("une release contrôlée traverse l’API et Ignorer persiste après rechargement", async ({ page }) => {
  await page.clock.install({ time: new Date("2026-01-01T00:00:00Z") });
  const { app } = await setupApplication(page, { updateStatus: "available" });
  await page.goto("/#dashboard");
  await page.clock.fastForward(7_000);

  const banner = page.getByRole("region", { name: "Mise à jour" });
  await expect(banner).toContainText("OTP LOL 99.0 est disponible");
  await expect.poll(() => app.externalFixtureRequests.some((request) =>
    request.host === "api.github.com" && request.path.endsWith("/releases/latest") && request.status === 200
  )).toBe(true);
  await banner.getByRole("button", { name: "Ignorer cette version" }).click();
  await expect(banner).toHaveCount(0);
  await expect.poll(async () => (await readSettings(page)).ignored_update_version).toBe("99.0");

  const updateResponses: number[] = [];
  page.on("response", (response) => {
    if (new URL(response.url()).pathname === "/api/updates") updateResponses.push(response.status());
  });
  await page.reload();
  await page.clock.fastForward(7_000);
  await expect.poll(() => updateResponses.length).toBeGreaterThan(0);
  await expect(page.locator(".update-banner")).toHaveCount(0);
  await expect.poll(async () => (await page.request.get(new URL("/api/updates", app.baseURL).href).then((response) => response.json())).available).toBe(false);
});
