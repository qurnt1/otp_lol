import { expect, test } from "./helpers";

import { setupApplication } from "./helpers";

test("settings deep links and browser back-forward restore the selected section", async ({ page }) => {
  await setupApplication(page);
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

test("every settings section can be opened directly from its hash", async ({ page }) => {
  await setupApplication(page);

  for (const [section, label] of [
    ["general", "Général"],
    ["automations", "Automatisations"],
    ["account", "Compte"],
    ["links", "Liens"],
    ["shortcuts", "Raccourcis"],
    ["appearance", "Apparence"],
    ["advanced", "Avancé"],
  ] as const) {
    await page.goto(`/#settings/${section}`);
    await page.reload();

    const sectionNav = page.getByRole("navigation", { name: "Sections des réglages" });
    await expect(page).toHaveURL(new RegExp(`#settings/${section}$`));
    await expect(sectionNav.getByRole("button", { name: label, exact: true })).toHaveAttribute("aria-current", "page");
    if (section === "advanced") {
      await expect(page.getByRole("heading", { name: "Fichiers et diagnostics" })).toBeVisible();
    } else {
      await expect(page.locator(".settings-section h2")).toHaveText(label);
    }
  }
});

test("the Settings deep link without a section opens General", async ({ page }) => {
  await setupApplication(page);
  await page.goto("/#settings");

  await expect(page.locator(".settings-section h2")).toHaveText("Général");
  await expect(page.getByRole("navigation").getByRole("link", { name: "Réglages", exact: true }))
    .toHaveAttribute("aria-current", "page");
});

test("an invalid initial hash falls back to the usable Dashboard route", async ({ page }) => {
  await setupApplication(page);
  await page.goto("/#settings/not-a-section");

  await expect(page).toHaveURL(/#dashboard$/);
  await expect(page.getByRole("heading", { name: "Préparation de partie", exact: true })).toBeVisible();
  await expect(page.getByRole("navigation").getByRole("link", { name: "Dashboard" })).toHaveAttribute("aria-current", "page");
});

test("pick_3 and ban deep links open the matching Dashboard action", async ({ page }) => {
  await setupApplication(page, { configured: true });

  await page.goto("/#dashboard/pick_3");
  await expect(page).toHaveURL(/#dashboard\/pick_3$/);
  await expect(page.getByRole("dialog", { name: "Modifier la priorité 3" })).toBeVisible();
  await page.getByRole("button", { name: "Fermer" }).last().click();
  await expect(page).toHaveURL(/#dashboard$/);

  await page.goto("/#dashboard/ban");
  await expect(page).toHaveURL(/#dashboard\/ban$/);
  await expect(page.getByRole("dialog", { name: "Champion à bannir" })).toBeVisible();
});

test("dashboard account-statistics action opens the provider profile without native account requests", async ({ page }) => {
  const accountRequests: string[] = [];
  const statsLinkRequests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/account/")) accountRequests.push(url.pathname);
    if (url.pathname === "/api/links/stats") statsLinkRequests.push(url.pathname);
  });
  await setupApplication(page);
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
  await setupApplication(page);
  await page.goto("/#dashboard");
  await page.getByRole("link", { name: "Réglages" }).click();
  await expect(page).toHaveURL(/#settings\/general$/);
  await expect(page.locator(".settings-section h2")).toHaveText("Général");
});

test("sidebar navigation exposes every main page and marks the current destination", async ({ page }) => {
  await setupApplication(page);
  await page.goto("/#dashboard");
  const navigation = page.getByRole("navigation");

  for (const [label, route, heading] of [
    ["Dashboard", /#dashboard$/, "Préparation de partie"],
    ["Statistiques", /#statistics$/, "Statistiques"],
    ["En direct", /#live$/, "En direct"],
    ["Journal de logs", /#history$/, "Journal de logs"],
    ["Réglages", /#settings\/general$/, "Général"],
  ] as const) {
    const link = navigation.getByRole("link", { name: label, exact: true });
    await link.click();
    await expect(page).toHaveURL(route);
    await expect(link).toHaveAttribute("aria-current", "page");
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
  }
  await expect(navigation.getByRole("link", { name: "Presets" })).toHaveCount(0);
});

test("[NAV-01] chaque lien de navigation principale s’active au clavier", async ({ page }) => {
  await setupApplication(page);
  await page.goto("/#diagnostics");
  const navigation = page.getByRole("navigation");

  for (const [label, route, heading] of [
    ["Dashboard", /#dashboard$/, "Préparation de partie"],
    ["Statistiques", /#statistics$/, "Statistiques"],
    ["En direct", /#live$/, "En direct"],
    ["Journal de logs", /#history$/, "Journal de logs"],
    ["Réglages", /#settings\/general$/, "Général"],
  ] as const) {
    const link = navigation.getByRole("link", { name: label, exact: true });
    await link.focus();
    await expect(link).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(route);
    await expect(link).toHaveAttribute("aria-current", "page");
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
  }
});

test("settings Links shortcuts navigate to both provider pages", async ({ page }) => {
  await setupApplication(page, { connected: true });
  await page.goto("/#settings/links");

  const section = page.locator(".settings-section");
  await section.getByRole("link", { name: "Statistiques" }).click();
  await expect(page).toHaveURL(/#statistics$/);
  await expect(page.getByRole("heading", { name: "Statistiques", exact: true })).toBeVisible();

  await page.goto("/#settings/links");
  await section.getByRole("link", { name: "En direct" }).click();
  await expect(page).toHaveURL(/#live$/);
  await expect(page.getByRole("heading", { name: "En direct", exact: true })).toBeVisible();
});

test("Dashboard editor actions participate in browser back-forward history", async ({ page }) => {
  await setupApplication(page, { configured: true });
  await page.goto("/#dashboard");
  await page.locator(".priority-card-link").first().click();
  await expect(page).toHaveURL(/#dashboard\/pick_1$/);
  await expect(page.getByRole("dialog", { name: "Modifier la priorité 1" })).toBeVisible();

  await page.goBack();
  await expect(page).toHaveURL(/#dashboard$/);
  await expect(page.getByRole("dialog", { name: "Modifier la priorité 1" })).toBeHidden();

  await page.goForward();
  await expect(page).toHaveURL(/#dashboard\/pick_1$/);
  await expect(page.getByRole("dialog", { name: "Modifier la priorité 1" })).toBeVisible();
});

test("Dashboard quick actions expose only valid destinations", async ({ page }) => {
  await setupApplication(page, { configured: true });
  await page.goto("/#dashboard");
  const quickActions = page.locator(".quick-panel");
  for (const [label, route, heading] of [
    ["Ouvrir les statistiques du compte", "#statistics", "Statistiques"],
    ["Ouvrir les statistiques en direct", "#live", "En direct"],
    ["Ouvrir le journal de logs", "#history", "Journal de logs"],
    ["Ouvrir les diagnostics LCU", "#diagnostics", "Diagnostics LCU"],
    ["Raccourcis clavier", "#settings/shortcuts", "Raccourcis"],
  ] as const) {
    const link = quickActions.getByRole("link", { name: label });
    await expect(link).toHaveAttribute("href", route);
    await link.click();
    await expect(page).toHaveURL(new RegExp(`${route}$`));
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
    await page.goBack();
    await expect(page).toHaveURL(/#dashboard$/);
    await expect(page.getByRole("heading", { name: "Préparation de partie", exact: true })).toBeVisible();
  }
  await expect(quickActions.getByRole("link", { name: /presets/i })).toHaveCount(0);
});
