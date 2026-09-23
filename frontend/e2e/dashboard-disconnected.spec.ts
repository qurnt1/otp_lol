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
  await page.clock.fastForward(21_600_000 - 1);
  expect(updateRequests).toBe(1);
  await page.clock.fastForward(1);
  await expect.poll(() => updateRequests).toBe(2);
  await page.clock.fastForward(21_600_000);
  await expect.poll(() => updateRequests).toBe(3);
});

test("une mise à jour disponible est visible et peut être ignorée", async ({ page }) => {
  await page.clock.install({ time: new Date("2026-01-01T00:00:00Z") });
  await mockLocalApi(page);
  await page.route("**/api/updates", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ available: true, update: {
        version: "12.0",
        highlights: "Améliorations de stabilité",
        release_url: "https://github.com/qurnt1/otp_lol/releases/tag/v12.0",
        asset_name: "OTP-LOL-Setup.exe",
        asset_url: "https://github.com/qurnt1/otp_lol/releases/download/v12.0/OTP-LOL-Setup.exe",
        checksum_name: "OTP-LOL-Setup.exe.sha256",
        checksum_url: "https://github.com/qurnt1/otp_lol/releases/download/v12.0/OTP-LOL-Setup.exe.sha256",
      } }),
    });
  });

  await page.goto("/#dashboard");
  await page.clock.fastForward(7_000);
  const banner = page.locator(".update-banner");
  await expect(banner).toContainText("OTP LOL 12.0 est disponible");
  await expect(banner.getByRole("link", { name: "Voir les nouveautés" })).toHaveAttribute("href", /releases\/tag\/v12\.0/);
  await expect(banner.getByRole("link", { name: "Télécharger" })).toHaveAttribute("href", /OTP-LOL-Setup\.exe$/);

  await banner.getByRole("button", { name: "Ignorer cette version" }).click();
  await expect(banner).toHaveCount(0);
  await expect(page.locator(".update-banner")).toHaveCount(0);
});
