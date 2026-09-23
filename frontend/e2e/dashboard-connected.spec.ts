import { expect, test } from "@playwright/test";
import { mockLocalApi } from "./helpers";

test("dashboard connecté affiche l’identité dans la sidebar et la phase dans le dashboard", async ({ page }) => {
  await mockLocalApi(page, { connected: true, configured: true });
  await page.goto("/#dashboard");
  await expect(page.locator(".sidebar-runtime")).toHaveAttribute("aria-label", "Client connecté");
  await expect(page.locator(".sidebar-account")).toHaveAttribute("title", "Player#EUW");
  await expect(page.locator(".phase-strip strong")).toHaveText("Dans le lobby");
  await expect(page.getByRole("heading", { name: "Garen" })).toBeVisible();

  await expect(page.locator(".priority-mode-select")).toHaveCount(0);

  await expect(page.locator(".skin-preview").first()).toContainText("God-King Garen");
  await page.locator(".priority-card").first().click();
  await page.locator('.preset-editor-dialog button[aria-label="Fermer"]').click();
  await page.getByRole("link", { name: "Dashboard", exact: true }).click();
  await expect(page.locator(".priority-mode-select")).toHaveCount(0);
});

test("dashboard affiche le dernier statut d’automatisation avec sa gravité et son âge", async ({ page }) => {
  await mockLocalApi(page, { connected: true, configured: true });
  await page.goto("/#dashboard");

  await page.evaluate(() => {
    (window as Window & { __otpEmitRuntimeEvent?: (event: unknown) => void }).__otpEmitRuntimeEvent?.({
      type: "status",
      data: { action: "summoners_unconfirmed", level: "WARN", params: {} },
      timestamp: new Date(Date.now() - 2_000).toISOString(),
    });
  });

  const status = page.locator(".automation-status");
  await expect(status).toHaveAttribute("class", /is-warning/);
  await expect(status).toContainText("Les sorts ne sont pas encore confirmés");
  await expect(status).toContainText(/à l’instant|il y a 2 s/);
});

test("le statut du ban reflète le maître des automatisations Presets", async ({ page }) => {
  const state = await mockLocalApi(page, { connected: true, configured: true });
  state.settings.presets_enabled = false;
  state.presets.presets_enabled = false;
  state.settings.auto_ban_enabled = true;
  await page.goto("/#dashboard");

  await expect(page.locator(".ban-visual strong")).toHaveText("Désactivé");
});

test("sidebar keeps long account identifiers contained and the phase row never shows account-sync status", async ({ page }) => {
  await mockLocalApi(page, {
    connected: true,
    riotId: "A-Very-Long-Player-Name-That-Must-Be-Clipped#TAG",
    phase: "WaitingForStats",
  });
  await page.goto("/#dashboard");

  for (const viewport of [{ width: 800, height: 540 }, { width: 1100, height: 760 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }]) {
    await page.setViewportSize(viewport);
    const bounds = await page.locator(".sidebar-account").evaluate((account) => {
      const sidebar = account.closest(".app-sidebar")!;
      return { accountRight: account.getBoundingClientRect().right, sidebarRight: sidebar.getBoundingClientRect().right, textOverflow: getComputedStyle(account.querySelector("span")!).textOverflow };
    });
    expect(bounds.accountRight).toBeLessThanOrEqual(bounds.sidebarRight);
    expect(bounds.textOverflow).toBe("ellipsis");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await expect(page.locator(".phase-strip strong")).toHaveText("Récupération des stats");
    await expect(page.getByText(/Compte synchronisé/)).toHaveCount(0);
    await expect(page.locator(".runtime-topbar")).toHaveCount(0);
  }
});

test("dashboard phase strip localizes every runtime phase and disconnected state", async ({ page }) => {
  const state = await mockLocalApi(page, { connected: true });
  await page.goto("/#dashboard");

  for (const [phase, label] of [
    ["Lobby", "Dans le lobby"],
    ["Matchmaking", "Recherche de partie"],
    ["ReadyCheck", "Partie trouvée"],
    ["ChampSelect", "Sélection des champions"],
    ["InProgress", "En partie"],
    ["WaitingForStats", "Récupération des stats"],
    ["EndOfGame", "Fin de partie"],
  ]) {
    state.runtime.phase = phase;
    await page.evaluate((runtime) => {
      (window as Window & { __otpEmitRuntimeEvent?: (event: unknown) => void }).__otpEmitRuntimeEvent?.({ type: "runtime_snapshot", data: runtime, timestamp: "2026-09-17T12:00:00Z" });
    }, state.runtime);
    await expect(page.locator(".phase-strip strong")).toHaveText(label);
  }

  state.runtime.connected = false;
  await page.evaluate((runtime) => {
    (window as Window & { __otpEmitRuntimeEvent?: (event: unknown) => void }).__otpEmitRuntimeEvent?.({ type: "runtime_snapshot", data: runtime, timestamp: "2026-09-17T12:01:00Z" });
  }, state.runtime);
  await expect(page.locator(".phase-strip strong")).toHaveText("Client non détecté");
  await expect(page.locator(".sidebar-runtime")).toHaveAttribute("aria-label", "Client déconnecté");
});

test("dashboard uses the selected skin splash and falls back to the champion splash when skin mode is off", async ({ page }) => {
  await mockLocalApi(page, { connected: true, configured: true });
  await page.goto("/#dashboard");

  const card = page.locator(".priority-card").first();
  const splash = card.locator(".priority-art img");
  await expect(splash).toHaveAttribute("src", "/api/assets/skins/86/86013/splash?skin_num=13&v=test-version");

  await expect(page.locator(".priority-mode-select")).toHaveCount(0);
});

for (const [index, slot] of ["pick_1", "pick_2", "pick_3"].entries()) {
  const priority = index + 1;
  test(`la carte Dashboard ouvre le preset ${priority} sans ouvrir le sélecteur`, async ({ page }) => {
    await mockLocalApi(page, { connected: true, configured: true });
    await page.goto("/#dashboard");

    const card = page.locator(".priority-card").nth(index);
    await card.click();

    await expect(page).toHaveURL(new RegExp(`#dashboard/${slot}$`));
    const editor = page.getByRole("dialog", { name: `Modifier la priorité ${priority}` });
    await expect(editor).toBeVisible();
    await expect(page.locator(".picker-drawer")).toHaveCount(0);
    await expect(page.locator("#champion-search")).toHaveCount(0);

    await page.locator(".champion-choice").click();
    await expect(page.locator(".picker-drawer")).toBeVisible();
    await expect(page.locator("#champion-search")).toBeFocused();
    await page.locator('.drawer-card button[aria-label="Fermer"]').click();
    await expect(page.locator(".champion-choice")).toBeFocused();
    await page.locator('.preset-editor-dialog button[aria-label="Fermer"]').click();
    await expect(page).toHaveURL(/#dashboard$/);
    await expect(page.locator(".priority-card-link").nth(index)).toBeFocused();
  });
}

test("modifier le ban ouvre son sélecteur directement et revient au Dashboard après validation", async ({ page }) => {
  await mockLocalApi(page, { connected: true, configured: true });
  await page.goto("/#dashboard");

  await page.locator(".ban-panel").click();
  await expect(page).toHaveURL(/#dashboard\/ban$/);
  await expect(page.locator("#champion-search")).toBeFocused();
  await page.locator("#champion-search").fill("Teemo");
  await page.getByRole("option", { name: /Teemo/ }).click();

  await expect(page).toHaveURL(/#dashboard$/);
  await expect(page.getByRole("heading", { name: "Teemo" })).toBeVisible();
  await expect(page.locator("#dashboard-edit-ban")).toBeFocused();
});

test("annuler la sélection du ban ramène au Dashboard et rend le focus au déclencheur", async ({ page }) => {
  await mockLocalApi(page, { connected: true, configured: true });
  await page.goto("/#dashboard");

  await page.locator(".ban-panel").click();
  await page.getByRole("button", { name: "Fermer" }).click();

  await expect(page).toHaveURL(/#dashboard$/);
  await expect(page.locator("#dashboard-edit-ban")).toBeFocused();
});

test("dashboard uses bootstrap previews instead of per-champion catalogs", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  await mockLocalApi(page, { connected: true, configured: true, assignedPosition: "TOP" });
  await page.goto("/#dashboard");

  await expect(page.locator(".priority-card")).toHaveCount(3);
  await expect(page.locator(".priority-role")).toHaveCount(0);
  await expect(page.locator(".ban-visual img")).toHaveAttribute("src", "/assets/app/garen.webp");
  expect(requests.some((url) => /\/api\/(champions|skins)\//.test(url))).toBe(false);
});
