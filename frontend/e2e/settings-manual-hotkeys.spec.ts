import { expect, readSettings, setupApplication, test } from "./helpers";

test("manually editing the window shortcut saves on blur", async ({ page }) => {
  await setupApplication(page);
  await page.goto("/#settings/shortcuts");

  const shortcut = page.getByRole("textbox", { name: "Afficher / masquer la fenêtre" });
  const persistedSettings = await readSettings(page);
  const nextHotkey = "ctrl+shift+f9";
  await shortcut.fill(nextHotkey);
  await page.getByRole("button", { name: "Capturer" }).first().focus();

  await expect.poll(async () => (await readSettings(page)).hotkey_toggle_window).toBe(nextHotkey);
  await expect(shortcut).toHaveValue(nextHotkey);
  expect((await readSettings(page)).hotkey_open_site).toBe(persistedSettings.hotkey_open_site);
});

test("manually editing the live shortcut saves on Enter and survives reload", async ({ page }) => {
  await setupApplication(page);
  await page.goto("/#settings/shortcuts");

  const shortcut = page.getByRole("textbox", { name: "Ouvrir l’onglet En direct" });
  const nextHotkey = "alt+f7";
  await shortcut.fill(nextHotkey);
  await shortcut.press("Enter");

  await expect.poll(async () => (await readSettings(page)).hotkey_open_site).toBe(nextHotkey);
  await expect(shortcut).toHaveValue(nextHotkey);
  await page.reload();
  await expect(shortcut).toHaveValue(nextHotkey);
  expect((await readSettings(page)).hotkey_open_site).toBe(nextHotkey);
});

test("manually entering an unsupported shortcut is rejected without changing the saved setting", async ({ page }) => {
  await setupApplication(page);
  await page.goto("/#settings/shortcuts");

  const shortcut = page.getByRole("textbox", { name: "Afficher / masquer la fenêtre" });
  const savedHotkey = (await readSettings(page)).hotkey_toggle_window;
  await shortcut.fill("not-a-shortcut");
  await shortcut.press("Enter");

  await expect(page.getByRole("alert")).toContainText("Unsupported hotkey modifier: not");
  await expect.poll(async () => (await readSettings(page)).hotkey_toggle_window).toBe(savedHotkey);
  await page.reload();
  await expect(shortcut).toHaveValue(savedHotkey);
  expect((await readSettings(page)).hotkey_toggle_window).toBe(savedHotkey);
});
