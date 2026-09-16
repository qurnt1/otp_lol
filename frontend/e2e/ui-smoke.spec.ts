import { expect, test } from "@playwright/test";

import { mockLocalApi } from "./helpers";

test("main views and preset pickers render without browser or network errors", async ({ page }) => {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const failedRequests: string[] = [];
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("requestfailed", (request) => failedRequests.push(`${request.url()}: ${request.failure()?.errorText}`));

  await page.setViewportSize({ width: 1100, height: 760 });
  await mockLocalApi(page, { configured: true, historyItems: [{ timestamp: "2026-09-15T20:00:00Z", type: "toast", level: "info", category: "Connection", action: "connected", message: "Client connecté", details: {} }] });

  await page.goto("/#dashboard");
  await expect(page.getByRole("heading", { name: "Préparation de partie" })).toBeVisible();

  await page.goto("/#presets");
  await page.locator(".preset-card").first().click();
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await expect(editor).toBeVisible();
  await editor.getByRole("button", { name: "Garen La Force de Demacia", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Choisir un champion" })).toBeVisible();
  await page.keyboard.press("Escape");
  await editor.getByRole("button", { name: /Galerie des skins/ }).click();
  await expect(page.getByRole("dialog", { name: "Galerie des skins" })).toBeVisible();
  await page.keyboard.press("Escape");
  await editor.getByRole("button", { name: /Ma page Top/ }).click();
  await expect(page.getByRole("dialog", { name: "Runes" })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");

  await page.goto("/#settings");
  await page.getByRole("button", { name: "Apparence" }).click();
  await page.getByRole("combobox", { name: "Thème" }).click();
  await page.getByRole("option", { name: "Clair" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByRole("button", { name: "Avancé" }).click();
  await expect(page.locator(".settings-section .section-head h2")).toBeVisible();

  await page.goto("/#history");
  await expect(page.getByText("Client connecté")).toBeVisible();
  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
  expect(failedRequests).toEqual([]);
});
