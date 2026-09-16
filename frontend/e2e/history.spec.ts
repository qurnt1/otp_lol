import { expect, test } from "@playwright/test";

import { mockLocalApi } from "./helpers";

test("historique demande une confirmation avant la suppression locale", async ({ page }) => {
  let nativeDialogOpened = false;
  page.on("dialog", () => { nativeDialogOpened = true; });
  await mockLocalApi(page, { historyItems: [{ timestamp: "2026-09-15T20:00:00Z", type: "toast", level: "info", category: "Connection", action: "connected", message: "Client connecté", details: {} }] });
  await page.goto("/#history");
  await expect(page.getByText("Client connecté")).toBeVisible();
  await page.getByRole("button", { name: "Effacer l’historique" }).click();
  await expect(page.getByRole("alertdialog")).toBeVisible();
  expect(nativeDialogOpened).toBe(false);
  await page.getByRole("alertdialog").getByRole("button", { name: "Effacer l’historique" }).click();
  await expect(page.getByText("Aucun événement pour le moment.")).toBeVisible();
});
