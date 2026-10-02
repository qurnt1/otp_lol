import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
});

test("main navigation moves to the requested sections", async ({ page }) => {
  const destinations = [
    ["Fonctionnement", "#fonctionnement"],
    ["L’application", "#captures"],
    ["Installation", "#installation"],
  ] as const;

  for (const [label, hash] of destinations) {
    await page.getByRole("navigation", { name: "Navigation principale" }).getByRole("link", { name: label }).click();
    await expect(page).toHaveURL(new RegExp(`${hash}$`));
    await expect(page.locator(hash)).toBeInViewport();
  }

  await page.getByRole("link", { name: "OTP LOL, accueil" }).click();
  await expect(page).toHaveURL(/#top$/);
});

test("keyboard skip link focuses the main content destination", async ({ page }) => {
  await page.keyboard.press("Tab");
  const skipLink = page.getByRole("link", { name: "Aller au contenu" });
  await expect(skipLink).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#main$/);
  await expect(page.locator("#main")).toBeInViewport();
});

test("screenshot selector preserves each content id, description, and loaded asset", async ({ page }) => {
  const selector = page.getByRole("group", { name: "Choisir une capture de l’application" });
  const screenshots = [
    {
      id: "settings",
      label: "Réglages",
      title: "Active ce qui te convient",
      alt: "Capture des réglages OTP LOL pour les automatismes, les fichiers locaux et la configuration.",
      note: "Aperçu des réglages. Les automatismes sont désactivés par défaut au premier lancement.",
    },
    {
      id: "statistics",
      label: "Statistiques",
      title: "Choisis tes fournisseurs",
      alt: "Capture des statistiques OTP LOL avec le choix d’un fournisseur et l’ouverture de son profil.",
      note: "Capture de test avec données simulées et profil fictif. Les profils et données de partie viennent de services tiers.",
    },
  ] as const;

  const buttons = selector.getByRole("button");
  await expect(buttons).toHaveCount(screenshots.length);

  for (const [index, screenshot] of screenshots.entries()) {
    const button = buttons.nth(index);
    await expect(button).toHaveAccessibleName(`${screenshot.label} ${screenshot.title}`);
    await button.click();
    await expect(button).toHaveAttribute("aria-pressed", "true");

    const image = page.locator(".showcase-frame .showcase-image");
    await expect(image).toHaveAttribute("alt", screenshot.alt);
    const source = await image.getAttribute("src");
    expect(source).toContain(`${screenshot.id}-web`);
    await expect(page.locator(".showcase-caption > span")).toHaveText(screenshot.note);
    await expect.poll(() => image.evaluate((element: HTMLImageElement) => element.naturalWidth)).toBeGreaterThan(0);
  }

  await expect(buttons.nth(0)).toHaveAttribute("aria-pressed", "false");
});

test("screenshot selector works from the keyboard and opens the selected screenshot", async ({ page }) => {
  const selector = page.getByRole("group", { name: "Choisir une capture de l’application" });
  const statisticsButton = selector.getByRole("button", { name: "Statistiques Choisis tes fournisseurs" });

  await statisticsButton.focus();
  await page.keyboard.press("Enter");
  await expect(statisticsButton).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".showcase-caption > span")).toContainText("profil fictif");

  await page.getByRole("button", { name: "Agrandir la capture" }).click();
  const dialog = page.getByRole("dialog", { name: "Statistiques" });
  await expect(dialog).toBeVisible();
  await expect(dialog.locator("img")).toHaveAttribute("alt", "Capture des statistiques OTP LOL avec le choix d’un fournisseur et l’ouverture de son profil.");
});

test("FAQ answers expand and collapse by mouse and keyboard", async ({ page }) => {
  const questions = page.locator(".faq-list summary");
  await expect(questions).toHaveCount(4);

  const firstQuestion = questions.nth(0);
  await firstQuestion.focus();
  await page.keyboard.press("Enter");
  const firstItem = firstQuestion.locator("xpath=..");
  await expect(firstItem).toHaveAttribute("open", "");
  await expect(firstItem.locator("p")).toBeVisible();
  await page.keyboard.press("Enter");
  await expect(firstItem).not.toHaveAttribute("open", "");

  for (let index = 1; index < 4; index += 1) {
    const question = questions.nth(index);
    const item = question.locator("xpath=..");
    await question.click();
    await expect(item).toHaveAttribute("open", "");
    await expect(item.locator("p")).toBeVisible();
    await question.click();
    await expect(item).not.toHaveAttribute("open", "");
  }
});

test("screenshot dialog changes display size, closes, and restores focus", async ({ page }) => {
  const openButton = page.getByRole("button", { name: "Agrandir la capture" });
  const dialog = page.getByRole("dialog", { name: "Réglages" });

  await openButton.click();
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Afficher la capture à sa taille réelle" }).click();
  const fitButton = dialog.getByRole("button", { name: "Ajuster la capture à la fenêtre" });
  await expect(fitButton).toHaveAttribute("aria-pressed", "true");
  await expect(dialog).toHaveAttribute("data-size", "actual");
  await fitButton.click();
  await expect(dialog).toHaveAttribute("data-size", "fit");
  await dialog.getByRole("button", { name: "Fermer la capture agrandie" }).click();
  await expect(dialog).not.toBeVisible();
  await expect(openButton).toBeFocused();
});

test("Escape closes the screenshot dialog and restores focus", async ({ page }) => {
  const openButton = page.getByRole("button", { name: "Agrandir la capture" });
  await openButton.click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(openButton).toBeFocused();
});

test("clicking the screenshot dialog backdrop closes it and restores focus", async ({ page }) => {
  const openButton = page.getByRole("button", { name: "Agrandir la capture" });
  await openButton.click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.mouse.click(4, 4);
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(openButton).toBeFocused();
});

test("release links point to the latest project release and GitHub links use safe new-tab targets", async ({ page }) => {
  const links = await page.locator('a[href^="https://github.com/qurnt1/otp_lol"]').evaluateAll((anchors) =>
    anchors.map((anchor) => ({
      href: (anchor as HTMLAnchorElement).href,
      target: (anchor as HTMLAnchorElement).target,
      rel: (anchor as HTMLAnchorElement).rel.split(/\s+/),
    })),
  );

  const releaseLinks = links.filter((link) => link.href === "https://github.com/qurnt1/otp_lol/releases/latest");
  expect(releaseLinks).toHaveLength(5);
  for (const link of releaseLinks) {
    const release = new URL(link.href);
    expect(release.hostname).toBe("github.com");
    expect(release.pathname).toBe("/qurnt1/otp_lol/releases/latest");
  }

  expect(links.filter((link) => link.href === "https://github.com/qurnt1/otp_lol")).toHaveLength(2);
  for (const link of links) {
    expect(link.target).toBe("_blank");
    expect(link.rel).toContain("noreferrer");
  }
});

test("content images load and have descriptive alternative text", async ({ page }) => {
  const images = page.locator("main img");
  const count = await images.count();
  expect(count).toBeGreaterThan(0);

  for (let index = 0; index < count; index += 1) {
    const image = images.nth(index);
    await image.scrollIntoViewIfNeeded();
    await expect(image).toHaveAttribute("alt", /\S+/);
    await expect.poll(() => image.evaluate((element: HTMLImageElement) => element.naturalWidth)).toBeGreaterThan(0);
  }
});

for (const viewport of [
  { width: 320, height: 740 },
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
  { width: 1366, height: 768 },
  { width: 1920, height: 1080 },
]) {
  test(`layout has no horizontal overflow at ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    const dimensions = await page.evaluate(() => ({
      documentWidth: document.documentElement.scrollWidth,
      viewportWidth: document.documentElement.clientWidth,
    }));
    expect(dimensions.documentWidth).toBeLessThanOrEqual(dimensions.viewportWidth);
  });
}
