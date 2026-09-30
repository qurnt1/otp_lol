import { expect, setupApplication, test } from "./helpers";

test("dashboard previews use bootstrap and defer champion catalogues until a picker opens", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/")) requests.push(url.pathname);
  });
  await setupApplication(page, { connected: true, configured: true, networkStatus: "online" });
  await page.goto("/#dashboard");

  await expect(page.getByRole("heading", { name: "Préparation de partie" })).toBeVisible();
  await expect.poll(() => requests.filter((path) => path === "/api/bootstrap").length).toBe(1);
  await expect.poll(() => requests.filter((path) => path === "/api/spells").length).toBe(1);
  expect(requests.filter((path) => path === "/api/champions")).toHaveLength(0);

  await page.locator(".priority-card").first().click();
  await expect(page.getByRole("dialog", { name: "Modifier la priorité 1" })).toBeVisible();
  await expect.poll(() => requests.filter((path) => path === "/api/champions").length).toBe(1);
});

test("offline champion fallback is replaced by the full catalog after Data Dragon returns", async ({ page }) => {
  const { app } = await setupApplication(page, { configured: true, networkStatus: "offline" });
  await page.goto("/#dashboard");
  await page.locator(".priority-card").first().click();

  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await editor.locator(".champion-choice").click();
  const picker = page.getByRole("dialog", { name: "Choisir un champion" });
  await expect(picker.getByRole("option", { name: /Ahri/ })).toBeVisible();
  const offlineCatalog = await page.request.get(new URL("/api/champions", app.baseURL).href).then((response) => response.json());
  expect(offlineCatalog.items.map((champion: { name: string }) => champion.name)).toContain("Jinx");
  expect(offlineCatalog.items.map((champion: { name: string }) => champion.name)).not.toContain("Annie");

  await picker.locator(".drawer-head").getByRole("button", { name: "Fermer" }).click();
  await expect(picker).toBeHidden();
  await editor.locator(".preset-editor-header").getByRole("button", { name: "Fermer" }).click();
  await expect(editor).toBeHidden();
  await app.configureExternalState({ dataDragon: "online" });
  await page.getByRole("button", { name: "Réessayer maintenant" }).click();
  await expect(page.locator(".network-warning")).toHaveCount(0);
  await expect.poll(async () => {
    const response = await page.request.get(new URL("/api/champions", app.baseURL).href);
    return (await response.json()).items.map((champion: { name: string }) => champion.name);
  }).toContain("Annie");
  await expect.poll(async () => {
    const response = await page.request.get(new URL("/api/champions", app.baseURL).href);
    return (await response.json()).items.map((champion: { name: string }) => champion.name);
  }).not.toContain("Jinx");
  await page.locator(".priority-card").first().click();
  await page.getByRole("dialog", { name: "Modifier la priorité 1" }).locator(".champion-choice").click();
  const onlinePicker = page.getByRole("dialog", { name: "Choisir un champion" });
  await expect(onlinePicker.getByRole("option", { name: /Annie/ })).toBeVisible();
});
