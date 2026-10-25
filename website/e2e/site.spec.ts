import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
});

test("main navigation moves to the requested sections", async ({ page }) => {
  const destinations = [
    ["Fonctionnement", "#fonctionnement"],
    ["L’application", "#captures"],
    ["Installation", "#installation"],
    ["Contact", "#contact"],
  ] as const;

  for (const [label, hash] of destinations) {
    await page.getByRole("navigation", { name: "Navigation principale" }).getByRole("link", { name: label }).click();
    await expect(page).toHaveURL(new RegExp(`${hash}$`));
    await expect(page.locator(hash)).toBeInViewport();
  }

  await page.getByRole("link", { name: "OTP LOL, accueil" }).click();
  await expect(page).toHaveURL(/#top$/);
});

test("language selector switches page content, screenshot text, and document metadata", async ({ page }) => {
  await expect(page.locator("html")).toHaveAttribute("lang", "fr");
  await expect(page.locator("h1")).toContainText("Tes choix prêts avant");
  await expect(page.locator('meta[property="og:locale"]')).toHaveAttribute("content", "fr_FR");
  await expect(page.locator('meta[name="twitter:title"]')).toHaveAttribute("content", "OTP LOL — Tes choix prêts avant la sélection");
  await expect(page.locator('meta[name="twitter:description"]')).toHaveAttribute("content", /Prépare tes priorités/);

  await page.getByRole("button", { name: "English" }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator("h1")).toContainText("Your picks, ready");
  await expect(page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "How it works" })).toBeVisible();
  await expect(page).toHaveTitle("OTP LOL — Your picks, ready before champion select");
  await expect(page.locator('meta[name="description"]')).toHaveAttribute("content", /Set your champion priorities/);
  await expect(page.locator('meta[property="og:locale"]')).toHaveAttribute("content", "en_US");
  await expect(page.locator('meta[name="twitter:title"]')).toHaveAttribute("content", "OTP LOL — Your picks, ready before champion select");
  await expect(page.locator('meta[name="twitter:description"]')).toHaveAttribute("content", /Set your champion priorities/);
  const englishScreenshots = page.getByRole("group", { name: "Choose an app screenshot" });
  await englishScreenshots.getByRole("button", { name: "Settings Enable what suits you" }).click();
  await expect(page.locator(".showcase-frame img")).toHaveAttribute("alt", "OTP LOL Advanced settings page showing local files, diagnostics, and configuration actions.");
  await expect(page.getByRole("link", { name: "Email chbtquentin@gmail.com" }))
    .toHaveAttribute("href", "mailto:chbtquentin@gmail.com?subject=OTP%20LOL%20contact");
  await page.setViewportSize({ width: 320, height: 740 });
  const englishMobileWidths = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: document.documentElement.clientWidth,
  }));
  expect(englishMobileWidths.documentWidth).toBeLessThanOrEqual(englishMobileWidths.viewportWidth);

  await page.getByRole("button", { name: "Français" }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "fr");
  await expect(page.locator("h1")).toContainText("Tes choix prêts avant");
  await expect(page.locator('meta[property="og:locale"]')).toHaveAttribute("content", "fr_FR");
  await expect(page.locator('meta[name="twitter:title"]')).toHaveAttribute("content", "OTP LOL — Tes choix prêts avant la sélection");
  await expect(page.locator('meta[name="twitter:description"]')).toHaveAttribute("content", /Prépare tes priorités/);
});

test("raw HTML includes crawler metadata and serves its referenced brand assets", async ({ page }) => {
  const response = await page.request.get(page.url());
  expect(response.ok()).toBeTruthy();
  const html = await response.text();

  expect(html).toContain('<meta name="robots" content="index, follow" />');
  expect(html).toContain('<link rel="canonical" href="https://qurnt1.github.io/otp_lol/" />');
  expect(html).toContain('<meta property="og:title" content="OTP LOL — Tes choix prêts avant la sélection" />');
  expect(html).toContain('<meta property="og:description" content="Configure tes préférences League et choisis les automatismes qui t’aident." />');
  expect(html).toContain('<meta property="og:type" content="website" />');
  expect(html).toContain('<meta property="og:site_name" content="OTP LOL" />');
  expect(html).toContain('<meta property="og:url" content="https://qurnt1.github.io/otp_lol/" />');
  expect(html).toContain('<meta property="og:locale" content="fr_FR" />');
  expect(html).toContain('<meta property="og:locale:alternate" content="en_US" />');
  expect(html).toContain('<meta property="og:image" content="https://qurnt1.github.io/otp_lol/assets/app/garen.webp" />');
  expect(html).toContain('<meta property="og:image:alt" content="Icône OTP LOL, compagnon League pour Windows" />');
  expect(html).toContain('<meta property="og:image:type" content="image/webp" />');
  expect(html).toContain('<meta property="og:image:width" content="256" />');
  expect(html).toContain('<meta property="og:image:height" content="256" />');
  expect(html).toContain('<meta name="twitter:card" content="summary" />');
  expect(html).toContain('<meta name="twitter:url" content="https://qurnt1.github.io/otp_lol/" />');
  expect(html).toContain('<meta name="twitter:title" content="OTP LOL — Tes choix prêts avant la sélection" />');
  expect(html).toContain('<meta name="twitter:description" content="Prépare tes priorités, tes sorts, tes runes et tes skins. OTP LOL applique les automatismes que tu choisis, sur ton PC Windows." />');
  expect(html).toContain('<meta name="twitter:image" content="https://qurnt1.github.io/otp_lol/assets/app/garen.webp" />');
  expect(html).toContain('<meta name="twitter:image:alt" content="Icône OTP LOL, compagnon League pour Windows" />');
  expect(html).toContain('<link id="site-favicon" rel="icon" type="image/x-icon" href="./favicon.ico" />');
  expect(html).toContain('<link rel="shortcut icon" href="./favicon.ico" />');

  const favicon = await page.request.get(new URL("./favicon.ico", page.url()).href);
  expect(favicon.ok()).toBeTruthy();
  expect(favicon.headers()["content-type"]).toContain("image/x-icon");

  const socialImage = await page.request.get(new URL("./assets/app/garen.webp", page.url()).href);
  expect(socialImage.ok()).toBeTruthy();
  expect(socialImage.headers()["content-type"]).toContain("image/webp");
});

test("French navigation fits a 305px usable viewport", async ({ page }) => {
  await page.setViewportSize({ width: 305, height: 900 });
  await expect(page.locator("html")).toHaveAttribute("lang", "fr");

  const dimensions = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: document.documentElement.clientWidth,
    contactRight: document.querySelector<HTMLAnchorElement>('.main-nav a[href="#contact"]')!.getBoundingClientRect().right,
  }));

  expect(dimensions.documentWidth).toBeLessThanOrEqual(dimensions.viewportWidth);
  expect(dimensions.contactRight).toBeLessThanOrEqual(dimensions.viewportWidth);
  await expect(page.getByRole("navigation", { name: "Navigation principale" }).getByRole("link", { name: "Contact" })).toBeVisible();
});

test("contact section provides a direct email link", async ({ page }) => {
  const contact = page.locator("#contact");
  await expect(contact).toBeVisible();
  await expect(contact.getByRole("link", { name: "Écrire à chbtquentin@gmail.com" }))
    .toHaveAttribute("href", "mailto:chbtquentin@gmail.com?subject=OTP%20LOL%20contact");
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
      alt: "Capture de la page Avancé des réglages OTP LOL, avec les fichiers locaux, les diagnostics et les actions de configuration.",
      note: "Aperçu de la page Avancé. Les automatismes restent désactivés au premier lancement.",
    },
    {
      id: "statistics",
      label: "Statistiques",
      title: "Choisis tes fournisseurs",
      alt: "Capture de la page Statistiques OTP LOL avec les fournisseurs disponibles et aucun compte configuré.",
      note: "Aperçu sans compte configuré. Les profils et données de partie viennent du fournisseur tiers choisi.",
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
    expect(source).toContain(`portfolio-${screenshot.id}-demo`);
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
  await expect(page.locator(".showcase-caption > span")).toContainText("sans compte configuré");

  await page.getByRole("button", { name: "Agrandir la capture" }).click();
  const dialog = page.getByRole("dialog", { name: "Statistiques" });
  await expect(dialog).toBeVisible();
  await expect(dialog.locator("img")).toHaveAttribute("alt", "Capture de la page Statistiques OTP LOL avec les fournisseurs disponibles et aucun compte configuré.");
});

test("hero uses the current disconnected-client demo screenshot", async ({ page }) => {
  const image = page.locator(".hero-figure img");
  await expect(image).toHaveAttribute("alt", "Capture de démonstration du tableau de bord OTP LOL avec trois champions et leurs skins configurés, client League déconnecté.");
  await expect(image).toHaveAttribute("src", /portfolio-dashboard-demo/);
  await expect(page.locator(".hero-figure figcaption")).toContainText("client déconnecté");
  await expect.poll(() => image.evaluate((element: HTMLImageElement) => element.naturalWidth)).toBeGreaterThan(0);
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

test("mobile body copy remains at least 12px at 390px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const bodyCopy = page.locator([
    ".workflow-list p",
    ".feature-column > p",
    ".feature-column ul",
    ".local-intro > p:not(.eyebrow)",
    ".install-block li p",
    ".faq-list summary",
    ".faq-list details p",
  ].join(", "));

  for (const element of await bodyCopy.all()) {
    const fontSize = await element.evaluate((node) => Number.parseFloat(getComputedStyle(node).fontSize));
    expect(fontSize).toBeGreaterThanOrEqual(12);
  }
});
