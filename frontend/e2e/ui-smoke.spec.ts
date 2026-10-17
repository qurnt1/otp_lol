import { expect, setupApplication, test } from "./helpers";

const isDesktopBridgeCspViolation = (error: string) =>
  error.includes("Executing inline script violates the following Content Security Policy directive")
  && error.includes("script-src 'self'");

test("main views remain navigable with only the known desktop bridge CSP violation", async ({ page }) => {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const failedRequests: string[] = [];
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("requestfailed", (request) => failedRequests.push(`${request.url()}: ${request.failure()?.errorText}`));

  await page.setViewportSize({ width: 1100, height: 760 });
  const { app } = await setupApplication(page, { configured: true, connected: true, autoAccept: true });

  await page.goto("/#dashboard");
  await expect(page.getByRole("heading", { name: "Préparation de partie" })).toBeVisible();

  await page.goto("/#dashboard");
  await page.locator(".priority-card").first().click();
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await expect(editor).toBeVisible();
  await editor.locator(".champion-choice").click();
  const championPicker = page.getByRole("dialog", { name: "Choisir un champion" });
  await expect(championPicker).toBeVisible();
  await championPicker.getByRole("button", { name: "Fermer" }).click();
  await expect(editor).toBeVisible();
  await editor.getByRole("button", { name: /Galerie des skins/ }).click();
  const skinPicker = page.getByRole("dialog", { name: "Galerie des skins" });
  await expect(skinPicker).toBeVisible();
  await skinPicker.getByRole("button", { name: "Fermer" }).click();
  await expect(editor).toBeVisible();
  await editor.getByRole("button", { name: /E2E Top/ }).click();
  const runePicker = page.getByRole("dialog", { name: "Runes" });
  await expect(runePicker).toBeVisible();
  await runePicker.getByRole("button", { name: "Fermer" }).click();
  await expect(editor).toBeVisible();

  await page.goto("/#settings");
  await page.getByRole("button", { name: "Apparence" }).click();
  await page.getByRole("combobox", { name: "Thème" }).click();
  await page.getByRole("option", { name: "Clair" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByRole("button", { name: "Avancé" }).click();
  await expect(page.getByRole("region", { name: "Avancé" })).toBeVisible();

  await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", { state: "InProgress", playerResponse: "None" });
  await app.waitForLcuRequest("POST", "/lol-matchmaking/v1/ready-check/accept");
  await page.goto("/#history");
  await expect(page.getByText("Match automatically accepted.")).toBeVisible();
  expect(consoleErrors.filter((error) => !isDesktopBridgeCspViolation(error))).toEqual([]);
  expect(pageErrors).toEqual([]);
  expect(failedRequests).toEqual([]);
});

test("desktop bridge bootstrap initializes its flags under the FastAPI CSP", async ({ page }) => {
  await setupApplication(page);
  await page.goto("/");

  test.fail(true, "Known product defect: FastAPI CSP script-src 'self' blocks the inline desktop bridge initializer in frontend/index.html.");
  const bridgeFlags = await page.evaluate(() => {
    const current = window as Window & {
      __otpDesktopMode?: boolean;
      __otpNativeBridgeReady?: boolean;
    };
    return {
      desktopMode: current.__otpDesktopMode,
      nativeBridgeReady: current.__otpNativeBridgeReady,
    };
  });
  expect(bridgeFlags).toEqual({ desktopMode: false, nativeBridgeReady: false });
});
