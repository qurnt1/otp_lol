import { useEffect, useState } from "react";
import {
  ArrowDown,
  ArrowUpRight,
  Check,
  ChevronLeft,
  ChevronRight,
  LockKeyhole,
  Menu,
  MonitorDown,
  X,
} from "lucide-react";

type Locale = "fr" | "en";
type ScreenshotKey = "dashboard" | "settings" | "statistics";
type GalleryScreenshotKey = Exclude<ScreenshotKey, "dashboard">;

const releasesUrl = "https://github.com/qurnt1/otp_lol/releases/latest";
const sourceUrl = "https://github.com/qurnt1/otp_lol";

const copy = {
  fr: {
    nav: ["Comment ça marche", "L’application", "Confidentialité"],
    download: "Télécharger",
    eyebrow: "TON COMPAGNON LOCAL POUR LEAGUE OF LEGENDS",
    title: "Tes choix sont prêts. La partie reste à toi.",
    intro:
      "Prépare tes priorités une fois. Une fois dans le client League, OTP LOL suit les options que tu as activées, jusqu’au retour au lobby.",
    primary: "Télécharger pour Windows",
    secondary: "Voir l’application",
    requirements: "Windows · client League installé",
    heroCaption: "TON TABLEAU DE BORD",
    sequenceEyebrow: "UNE ROUTINE PLUS SIMPLE",
    sequenceTitle: "Tes choix. Dans le bon ordre.",
    sequenceIntro:
      "Configure tes préférences à ton rythme, puis active uniquement les automatismes qui te conviennent.",
    steps: [
      ["LOBBY", "Prépare tes presets", "Rassemble picks prioritaires, ban et équipement par champion."],
      ["FILE", "Lance la file dans League", "Tu démarres la file dans le client. Si activé, OTP LOL accepte le ready-check."],
      ["SÉLECTION", "Suis ton preset", "Pendant la sélection, OTP LOL applique les options activées de ton preset."],
      ["APRÈS-MATCH", "Retourne au lobby", "Active l’option correspondante pour revenir au client après la partie."],
    ],
    galleryEyebrow: "APERÇU DE L’APPLICATION",
    galleryTitle: "Tout est à portée de main.",
    galleryIntro:
      "Un tableau de bord pour les automatismes, des réglages clairs et tes pages de statistiques préférées.",
    tabs: {
      settings: ["Réglages", "Active seulement ce que tu veux automatiser."],
      statistics: ["Statistiques", "Choisis les fournisseurs que tu souhaites consulter."],
    } satisfies Record<GalleryScreenshotKey, [string, string]>,
    privacyEyebrow: "PENSÉ POUR RESTER CHEZ TOI",
    privacyTitle: "Ton setup reste sur ton PC.",
    privacyBody:
      "OTP LOL fonctionne avec le client League installé sur le même ordinateur. Tes réglages et ton historique restent stockés localement, sans compte OTP LOL ni profil hébergé. En ouvrant une page de statistiques, le fournisseur choisi reçoit l’URL du profil consulté.",
    privacyPoints: [
      "Automatismes désactivés au départ",
      "Tu choisis les options à activer",
      "Tu gardes la main sur chaque automatisme",
    ],
    requirementsTitle: "Pour commencer",
    requirementsBody:
      "Un PC Windows avec le client League of Legends. Le runtime Microsoft Edge WebView2 Evergreen est requis pour la fenêtre de l’application.",
    requirementsCta: "Guide d’installation",
    finalEyebrow: "PRÊT POUR TA PROCHAINE FILE ?",
    finalTitle: "Configure une fois. Joue à ta façon.",
    finalCta: "Télécharger OTP LOL",
    source: "Code source",
    independent:
      "Projet communautaire indépendant. Non affilié à Riot Games et non approuvé par Riot Games. League of Legends est une marque de Riot Games.",
    language: "English",
    skip: "Aller au contenu",
    screenshots: {
      dashboard: ["Capture du tableau de bord web d’OTP LOL", "TABLEAU DE BORD"],
      settings: ["Capture des réglages web d’OTP LOL", "RÉGLAGES"],
      statistics: ["Capture de la page statistiques web d’OTP LOL", "STATISTIQUES"],
    } satisfies Record<ScreenshotKey, [string, string]>,
    changeScreenshot: "Changer de capture",
    statsPrivacy: "En ouvrant ce fournisseur, tu lui transmets l’URL du profil consulté.",
  },
  en: {
    nav: ["How it works", "The app", "Privacy"],
    download: "Download",
    eyebrow: "YOUR LOCAL LEAGUE OF LEGENDS COMPANION",
    title: "Your setup is ready. The game stays yours.",
    intro:
      "Set your priorities once. In the League client, OTP LOL follows the options you enabled, through your return to lobby.",
    primary: "Download for Windows",
    secondary: "See the app",
    requirements: "Windows · League client installed",
    heroCaption: "YOUR DASHBOARD",
    sequenceEyebrow: "A SIMPLER ROUTINE",
    sequenceTitle: "Your picks. In the right order.",
    sequenceIntro:
      "Set up your preferences, then enable only the automations you want.",
    steps: [
      ["LOBBY", "Set up your presets", "Keep priority picks, bans, and loadouts together by champion."],
      ["QUEUE", "Start queue in League", "You start queue in the client. OTP LOL can accept ready checks when enabled."],
      ["CHAMP SELECT", "Follow your preset", "During champ select, OTP LOL applies the options enabled in your preset."],
      ["AFTER GAME", "Return to lobby", "Enable the option to return to the client after a game."],
    ],
    galleryEyebrow: "A LOOK INSIDE",
    galleryTitle: "Everything within reach.",
    galleryIntro:
      "One dashboard for your automations, clear settings, and favorite stats pages.",
    tabs: {
      settings: ["Settings", "Enable only what you want to automate."],
      statistics: ["Statistics", "Choose the providers you want to visit."],
    } satisfies Record<GalleryScreenshotKey, [string, string]>,
    privacyEyebrow: "BUILT TO STAY ON YOUR PC",
    privacyTitle: "Your setup stays on your PC.",
    privacyBody:
      "OTP LOL works with the League client installed on the same computer. Your settings and history stay stored locally, with no OTP LOL account or hosted profile. When you open a stats page, the selected provider receives the URL of the profile you view.",
    privacyPoints: [
      "Automations start disabled",
      "You choose what to enable",
      "You stay in control of each automation",
    ],
    requirementsTitle: "What you need",
    requirementsBody:
      "A Windows PC with the League of Legends client. The Microsoft Edge WebView2 Evergreen Runtime is required for the app window.",
    requirementsCta: "Installation guide",
    finalEyebrow: "READY FOR YOUR NEXT QUEUE?",
    finalTitle: "Set it up once. Play your way.",
    finalCta: "Download OTP LOL",
    source: "Source code",
    independent:
      "Independent community project. Not affiliated with or endorsed by Riot Games. League of Legends is a trademark of Riot Games.",
    language: "Français",
    skip: "Skip to content",
    screenshots: {
      dashboard: ["OTP LOL web dashboard screenshot", "DASHBOARD"],
      settings: ["OTP LOL web settings screenshot", "SETTINGS"],
      statistics: ["OTP LOL web statistics screenshot", "STATISTICS"],
    } satisfies Record<ScreenshotKey, [string, string]>,
    changeScreenshot: "Change screenshot",
    statsPrivacy: "Opening this provider sends it the URL of the profile you view.",
  },
} as const;

const galleryScreenshotKeys: GalleryScreenshotKey[] = ["settings", "statistics"];
const assetsBase = `${import.meta.env.BASE_URL}assets/`;
const screenshotSrc: Record<ScreenshotKey, string> = {
  dashboard: `${assetsBase}screenshots/dashboard-web.png`,
  settings: `${assetsBase}screenshots/settings-web.png`,
  statistics: `${assetsBase}screenshots/statistics-web.png`,
};

function getInitialLocale(): Locale {
  return navigator.language.toLowerCase().startsWith("fr") ? "fr" : "en";
}

function App() {
  const [locale, setLocale] = useState<Locale>(getInitialLocale);
  const [activeScreenshot, setActiveScreenshot] = useState<GalleryScreenshotKey>("settings");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const t = copy[locale];
  const activeIndex = galleryScreenshotKeys.indexOf(activeScreenshot);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  function stepScreenshot(direction: -1 | 1) {
    const nextIndex = (activeIndex + direction + galleryScreenshotKeys.length) % galleryScreenshotKeys.length;
    setActiveScreenshot(galleryScreenshotKeys[nextIndex]);
  }

  return (
    <>
      <a className="skip-link" href="#main">
        {t.skip}
      </a>

      <header className="site-header">
        <a className="brand" href="#top" aria-label={locale === "fr" ? "OTP LOL, accueil" : "OTP LOL, home"}>
          <span className="brand-mark">
            <img src={`${assetsBase}app/garen.webp`} alt="" />
          </span>
          <span className="brand-name">OTP <strong>LOL</strong></span>
        </a>

        <nav className={`main-nav${mobileMenuOpen ? " is-open" : ""}`} id="main-navigation" aria-label={locale === "fr" ? "Navigation principale" : "Main navigation"}>
          <a href="#how-it-works" onClick={() => setMobileMenuOpen(false)}>{t.nav[0]}</a>
          <a href="#screenshots" onClick={() => setMobileMenuOpen(false)}>{t.nav[1]}</a>
          <a href="#privacy" onClick={() => setMobileMenuOpen(false)}>{t.nav[2]}</a>
        </nav>

        <div className="header-actions">
          <button
            className="mobile-menu-toggle"
            type="button"
            aria-label={mobileMenuOpen ? (locale === "fr" ? "Fermer le menu" : "Close menu") : (locale === "fr" ? "Ouvrir le menu" : "Open menu")}
            aria-expanded={mobileMenuOpen}
            aria-controls="main-navigation"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            {mobileMenuOpen ? <X size={18} aria-hidden="true" /> : <Menu size={18} aria-hidden="true" />}
          </button>
          <button
            className="language-toggle"
            onClick={() => setLocale(locale === "fr" ? "en" : "fr")}
            aria-label={t.language}
          >
            {locale === "fr" ? "FR" : "EN"}
            <span aria-hidden="true">↗</span>
          </button>
          <a className="button button-small button-ink" href={releasesUrl} target="_blank" rel="noreferrer">
            {t.download} <ArrowUpRight size={15} aria-hidden="true" />
          </a>
        </div>
      </header>

      <main id="main" tabIndex={-1}>
        <section className="hero" id="top">
          <div className="hero-copy">
            <p className="eyebrow"><span className="eyebrow-dot" />{t.eyebrow}</p>
            <h1>{t.title}</h1>
            <p className="hero-intro">{t.intro}</p>
            <div className="hero-actions">
              <a className="button button-primary" href={releasesUrl} target="_blank" rel="noreferrer">
                {t.primary} <ArrowUpRight size={17} aria-hidden="true" />
              </a>
              <a className="text-link" href="#screenshots">
                {t.secondary} <ArrowDown size={16} aria-hidden="true" />
              </a>
            </div>
            <p className="hero-requirement"><MonitorDown size={15} aria-hidden="true" /> {t.requirements}</p>
          </div>

          <figure className="hero-preview">
            <div className="preview-topbar">
              <span className="preview-window-dots" aria-hidden="true"><i /><i /><i /></span>
              <span>{t.heroCaption}</span>
              <span className="preview-mark">OTP LOL</span>
            </div>
            <img
              className="hero-screenshot"
              src={screenshotSrc.dashboard}
              alt={t.screenshots.dashboard[0]}
              fetchPriority="high"
            />
            <figcaption><span>{t.screenshots.dashboard[1]}</span></figcaption>
          </figure>
        </section>

        <section className="sequence section-wrap" id="how-it-works">
          <div className="section-heading sequence-heading">
            <div>
              <p className="eyebrow"><span className="eyebrow-dot" />{t.sequenceEyebrow}</p>
              <h2>{t.sequenceTitle}</h2>
            </div>
            <p className="section-intro">{t.sequenceIntro}</p>
          </div>

          <div className="steps-list">
            {t.steps.map(([phase, title, description]) => (
              <article className="step-row" key={title}>
                <span className="step-phase">{phase}</span>
                <h3>{title}</h3>
                <p>{description}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="gallery" id="screenshots">
          <div className="section-wrap">
            <div className="section-heading gallery-heading">
              <div>
                <p className="eyebrow"><span className="eyebrow-dot" />{t.galleryEyebrow}</p>
                <h2>{t.galleryTitle}</h2>
              </div>
              <p className="section-intro">{t.galleryIntro}</p>
            </div>

            <div className="gallery-controls">
              <div className="screenshot-tabs" role="tablist" aria-label={t.changeScreenshot}>
                {galleryScreenshotKeys.map((key, index) => (
                  <button
                    className={`screenshot-tab${activeScreenshot === key ? " is-active" : ""}`}
                    type="button"
                    role="tab"
                    id={`tab-${key}`}
                    aria-selected={activeScreenshot === key}
                    aria-controls="screenshot-panel"
                    tabIndex={activeScreenshot === key ? 0 : -1}
                    onClick={() => setActiveScreenshot(key)}
                    onKeyDown={(event) => {
                      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
                      event.preventDefault();
                      const direction = event.key === "ArrowRight" ? 1 : -1;
                      const nextIndex = (index + direction + galleryScreenshotKeys.length) % galleryScreenshotKeys.length;
                      const nextKey = galleryScreenshotKeys[nextIndex];
                      setActiveScreenshot(nextKey);
                      event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>("[role='tab']")[nextIndex]?.focus();
                    }}
                    key={key}
                  >
                    <span>0{index + 2}</span>{t.tabs[key][0]}
                  </button>
                ))}
              </div>
              <div className="gallery-arrows">
                <button type="button" onClick={() => stepScreenshot(-1)} aria-label={locale === "fr" ? "Capture précédente" : "Previous screenshot"}>
                  <ChevronLeft size={18} aria-hidden="true" />
                </button>
                <button type="button" onClick={() => stepScreenshot(1)} aria-label={locale === "fr" ? "Capture suivante" : "Next screenshot"}>
                  <ChevronRight size={18} aria-hidden="true" />
                </button>
              </div>
            </div>

            <figure
              className="screenshot-panel"
              id="screenshot-panel"
              role="tabpanel"
              aria-labelledby={`tab-${activeScreenshot}`}
              aria-describedby={activeScreenshot === "statistics" ? "statistics-privacy-note" : undefined}
              tabIndex={0}
            >
              <img src={screenshotSrc[activeScreenshot]} alt={t.screenshots[activeScreenshot][0]} />
              <figcaption>
                <span className="gallery-caption-index">0{activeIndex + 2}</span>
                <span>{t.tabs[activeScreenshot][1]}</span>
                <span className="gallery-caption-name">{t.screenshots[activeScreenshot][1]}</span>
              </figcaption>
            </figure>
            {activeScreenshot === "statistics" && <p className="stats-privacy-note" id="statistics-privacy-note">{t.statsPrivacy}</p>}
          </div>
        </section>

        <section className="trust-section section-wrap" id="privacy">
          <div className="trust-main">
            <p className="eyebrow"><span className="eyebrow-dot" />{t.privacyEyebrow}</p>
            <h2>{t.privacyTitle}</h2>
            <p className="trust-description">{t.privacyBody}</p>
            <ul className="trust-list">
              {t.privacyPoints.map((point) => <li key={point}><Check size={16} aria-hidden="true" />{point}</li>)}
            </ul>
          </div>
          <aside className="requirements-card">
            <LockKeyhole size={20} strokeWidth={1.7} aria-hidden="true" />
            <h3>{t.requirementsTitle}</h3>
            <p>{t.requirementsBody}</p>
            <a href={`${sourceUrl}/blob/codex/react-fastapi-webview-migration/readme.md#what-you-need`} target="_blank" rel="noreferrer">
              {t.requirementsCta} <ArrowUpRight size={15} aria-hidden="true" />
            </a>
          </aside>
        </section>

        <section className="closing-cta">
          <div className="closing-inner">
            <div>
              <p className="eyebrow"><span className="eyebrow-dot" />{t.finalEyebrow}</p>
              <h2>{t.finalTitle}</h2>
            </div>
            <a className="button button-light" href={releasesUrl} target="_blank" rel="noreferrer">
              {t.finalCta} <ArrowUpRight size={17} aria-hidden="true" />
            </a>
          </div>
        </section>
      </main>

      <footer className="site-footer">
        <a className="brand footer-brand" href="#top" aria-label={locale === "fr" ? "OTP LOL, accueil" : "OTP LOL, home"}>
          <span className="brand-mark"><img src={`${assetsBase}app/garen.webp`} alt="" /></span>
          <span className="brand-name">OTP <strong>LOL</strong></span>
        </a>
        <p>{t.independent}</p>
        <a className="footer-source" href={sourceUrl} target="_blank" rel="noreferrer">
          {t.source} <ArrowUpRight size={15} aria-hidden="true" />
        </a>
      </footer>
    </>
  );
}

export default App;
