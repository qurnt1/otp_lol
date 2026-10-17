import { createOtpPage, expect, readPresets, readSettings, test, type OtpApp } from "./helpers";

type RetainedOtpApp = OtpApp & {
  stateDir: string;
  stop(options?: { retainState?: boolean }): Promise<Awaited<ReturnType<OtpApp["stop"]>>>;
};

type AppServerModule = {
  startOtpApp(options: { stateDir: string }): Promise<RetainedOtpApp>;
};

test("a fresh profile shows first-run defaults and keeps a configured preset after restart", async ({ browser, otpApp, page }, testInfo) => {
  const firstApp = otpApp as RetainedOtpApp;
  await page.goto("/#dashboard");

  const initialSettings = await readSettings(page);
  const initialPresets = await readPresets(page);
  expect(initialSettings).toMatchObject({
    onboarding_completed: false,
    presets_enabled: false,
    auto_accept_enabled: false,
    auto_pick_enabled: false,
    auto_ban_enabled: false,
    auto_summoners_enabled: false,
    skin_automation_enabled: false,
    auto_play_again_enabled: false,
    theme: "darkly",
  });
  expect(initialPresets).toMatchObject({
    presets_enabled: false,
    selected_ban: "Teemo",
    slots: {
      pick_1: { champion: "Garen", spell_1: "Flash", spell_2: "Ignite", skin_mode: "none", rune_page_id: 0 },
      pick_2: { champion: "Lux", spell_1: "Flash", spell_2: "Barrier", skin_mode: "none", rune_page_id: 0 },
      pick_3: { champion: "Ashe", spell_1: "Flash", spell_2: "Heal", skin_mode: "none", rune_page_id: 0 },
    },
  });

  await expect(page.getByRole("heading", { name: "Préparation de partie" })).toBeVisible();
  const onboarding = page.getByRole("complementary", { name: "Des exemples sont prêts." });
  await expect(onboarding).toBeVisible();
  const configurePriorities = onboarding.getByRole("link", { name: "Configurer mes priorités" });
  await expect(configurePriorities).toHaveAttribute("href", "#dashboard/pick_1");
  await expect(page.getByRole("switch", { name: "Utiliser les presets en sélection" })).toHaveAttribute("aria-checked", "false");
  await expect(page.locator(".priority-card").nth(0)).toContainText("Garen");

  await configurePriorities.click();
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await expect(page).toHaveURL(/#dashboard\/pick_1$/);
  await editor.locator(".champion-choice").click();
  const picker = page.getByRole("dialog", { name: "Choisir un champion" });
  const savedPreset = page.waitForResponse((response) =>
    response.request().method() === "PUT"
    && new URL(response.url()).pathname === "/api/presets/pick_1"
    && response.status() === 200,
  );
  await picker.getByRole("option", { name: /Annie/ }).click();
  expect((await savedPreset).ok()).toBe(true);
  await expect(editor.locator(".champion-choice")).toContainText("Annie");
  await expect.poll(async () => (await readPresets(page)).slots.pick_1.champion).toBe("Annie");
  await expect.poll(async () => (await readSettings(page)).onboarding_completed).toBe(true);
  await expect(onboarding).toBeHidden();

  await page.getByRole("button", { name: "Fermer" }).last().click();
  await page.goto("/#dashboard");
  await page.reload();
  await expect(page.locator(".priority-card").nth(0)).toContainText("Annie");
  await expect(page.getByRole("complementary", { name: "Des exemples sont prêts." })).toHaveCount(0);

  const profileDir = firstApp.stateDir;
  const firstShutdown = await firstApp.stop({ retainState: true });
  expect(firstShutdown.forced).toBe(false);
  expect(firstShutdown.code).toBe(0);
  expect(firstShutdown.stateRetained).toBe(true);
  expect(firstShutdown.syntheticLeagueStopped).toBe(true);
  expect(firstShutdown.cleanupWarnings).toEqual([]);
  expect(firstShutdown.socketEgressBlocked).toEqual([]);
  expect(firstShutdown.externalRequestsBlocked).toEqual([]);

  const { startOtpApp } = await import("../../scripts/e2e/appServer.mjs") as unknown as AppServerModule;
  const restartedApp = await startOtpApp({ stateDir: profileDir });
  try {
    await restartedApp.waitForLcuRequest("GET", "/lol-chat/v1/me");
    const { context, page: restartedPage } = await createOtpPage(browser, restartedApp, testInfo);
    try {
      await restartedPage.goto("/#dashboard");
      await expect.poll(async () => readSettings(restartedPage)).toMatchObject({
        onboarding_completed: true,
        presets_enabled: false,
      });
      await expect.poll(async () => readPresets(restartedPage)).toMatchObject({
        presets_enabled: false,
        selected_ban: "Teemo",
        slots: { pick_1: { champion: "Annie" } },
      });
      await expect(restartedPage.locator(".priority-card").nth(0)).toContainText("Annie");
      await expect(restartedPage.getByRole("complementary", { name: "Des exemples sont prêts." })).toHaveCount(0);
    } finally {
      await context.close();
    }
  } finally {
    await restartedApp.stop();
  }
});
