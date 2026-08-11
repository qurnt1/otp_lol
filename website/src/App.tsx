import {
  BadgeCheck,
  Download,
  ExternalLink,
  EyeOff,
  Github,
  HardDrive,
  Languages,
  Lightbulb,
  Lock,
  Mail,
  MonitorDown,
  Radio,
  Repeat,
  Swords,
  WandSparkles,
  Zap,
} from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";

const repo = "qurnt1/otp_lol";
const repoUrl = `https://github.com/${repo}`;
const releasesUrl = `${repoUrl}/releases`;
const latestReleaseApi = `https://api.github.com/repos/${repo}/releases/latest`;
const latestReleaseUrl = `${repoUrl}/releases/latest`;
const windowsAssetName = "OTP LOL.exe";
const feedbackMailto =
  "mailto:chbtquentin@gmail.com?subject=feedback%20OTP%20LOL";
const ideasMailto =
  "mailto:chbtquentin@gmail.com?subject=ideas%20OTP%20LOL";

type DownloadState = "idle" | "loading" | "fallback";
type Lang = "en" | "fr";

const copy = {
  en: {
    nav: {
      features: "Features",
      screenshots: "Screenshots",
      privacy: "Privacy",
      contact: "Contact",
    },
    download: {
      idle: "Download Latest Version",
      loading: "Finding latest .exe…",
      fallback: "Opening releases…",
      other: "Other Versions",
    },
    accessibility: {
      skipToContent: "Skip to content",
      mainNavigation: "Main navigation",
      languageSelector: "Language selector",
      switchToEnglish: "Switch to English",
      switchToFrench: "Switch to French",
      home: "OTP LOL home",
    },
    hero: {
      kicker: "Windows League of Legends assistant",
      headline: "Automate tasks on League of Legends.",
      body:
        "Designed by an OTP, for OTPs. OTP LOL helps automate queue and champion select actions while keeping everything local, transparent, and ad-free.",
      author:
        "Created by a third-year data science student building the tool he wanted to use every day. Feedback and ideas are welcome.",
    },
    features: {
      kicker: "Features",
      title: "Focused on the actions you repeat every game.",
      items: [
        {
          icon: Zap,
          title: "Auto Accept",
          body: "Accept ready checks automatically when the League client finds a match.",
        },
        {
          icon: Swords,
          title: "Champion Select",
          body: "Use presets for pick priority, bans, and summoner spells.",
        },
        {
          icon: WandSparkles,
          title: "Skins",
          body: "Apply fixed or randomized skin choices from your local configuration.",
        },
        {
          icon: Repeat,
          title: "Play Again",
          body: "Optionally return to lobby faster after the game ends.",
        },
      ],
    },
    screenshots: {
      kicker: "Screenshots",
      title: "Small interface, quick configuration.",
      labels: ["Main Window", "Settings", "Champion Select"],
    },
    privacy: {
      kicker: "Privacy",
      title: "No ads. No OTP LOL account. No cloud dependency.",
      items: [
        {
          icon: EyeOff,
          title: "No ads",
          body: "No advertising scripts, banners, or tracking pixels.",
        },
        {
          icon: HardDrive,
          title: "Local settings",
          body: "Your configuration stays on your Windows machine.",
        },
        {
          icon: Lock,
          title: "No OTP LOL account",
          body: "No cloud dashboard and no hosted profile to sign into.",
        },
      ],
    },
    trust: {
      kicker: "Transparent APIs",
      title: "Riot public data and local client events.",
      body:
        "OTP LOL uses Riot Data Dragon for public League metadata like champions, icons, summoner spells, and version data. Runtime automation is driven by the local League Client Update interface on your own PC.",
      note:
        "OTP LOL is not endorsed by Riot Games. It is a local Windows assistant for your own setup.",
    },
    contact: {
      kicker: "Contact",
      title: "Help improve OTP LOL.",
      feedback: "Send Feedback",
      ideas: "Give Ideas To Dev",
      source: "View Source",
    },
    footer: {
      releases: "GitHub releases",
      source: "Source code",
      windows: "Windows only",
    },
  },
  fr: {
    nav: {
      features: "Fonctions",
      screenshots: "Captures",
      privacy: "Vie privée",
      contact: "Contact",
    },
    download: {
      idle: "Télécharger la dernière version",
      loading: "Recherche du dernier .exe…",
      fallback: "Ouverture des releases…",
      other: "Autres versions",
    },
    accessibility: {
      skipToContent: "Aller au contenu",
      mainNavigation: "Navigation principale",
      languageSelector: "Sélecteur de langue",
      switchToEnglish: "Passer en anglais",
      switchToFrench: "Passer en français",
      home: "Accueil OTP LOL",
    },
    hero: {
      kicker: "Assistant Windows pour League of Legends",
      headline: "Automatise tes actions sur League of Legends.",
      body:
        "Pensé par un OTP, pour les OTPs. OTP LOL aide à automatiser la queue et la champion select tout en gardant tout local, transparent et sans publicité.",
      author:
        "Créé par un étudiant en troisième année de data science qui construit l'outil qu'il voulait utiliser chaque jour. Les retours et idées sont bienvenus.",
    },
    features: {
      kicker: "Fonctions",
      title: "Concentré sur les actions que tu répètes à chaque game.",
      items: [
        {
          icon: Zap,
          title: "Auto Accept",
          body: "Accepte automatiquement le ready check quand le client League trouve une partie.",
        },
        {
          icon: Swords,
          title: "Champion Select",
          body: "Utilise tes presets pour les picks, bans et summoner spells.",
        },
        {
          icon: WandSparkles,
          title: "Skins",
          body: "Applique des skins fixes ou aléatoires depuis ta configuration locale.",
        },
        {
          icon: Repeat,
          title: "Play Again",
          body: "Permet de revenir plus vite en lobby après la fin d'une partie.",
        },
      ],
    },
    screenshots: {
      kicker: "Captures",
      title: "Une interface compacte, une configuration rapide.",
      labels: ["Fenêtre principale", "Paramètres", "Champion Select"],
    },
    privacy: {
      kicker: "Vie privée",
      title: "Pas de pubs. Pas de compte OTP LOL. Pas de dépendance cloud.",
      items: [
        {
          icon: EyeOff,
          title: "Pas de pubs",
          body: "Aucun script publicitaire, bannière ou pixel de tracking.",
        },
        {
          icon: HardDrive,
          title: "Réglages locaux",
          body: "Ta configuration reste sur ta machine Windows.",
        },
        {
          icon: Lock,
          title: "Pas de compte OTP LOL",
          body: "Pas de dashboard cloud et pas de profil hébergé à créer.",
        },
      ],
    },
    trust: {
      kicker: "APIs transparentes",
      title: "Données publiques Riot et événements locaux du client.",
      body:
        "OTP LOL utilise Riot Data Dragon pour les métadonnées publiques de League comme les champions, icônes, summoner spells et versions. L'automatisation fonctionne via l'interface locale League Client Update sur ton propre PC.",
      note:
        "OTP LOL n'est pas approuvé par Riot Games. C'est un assistant Windows local pour ton propre setup.",
    },
    contact: {
      kicker: "Contact",
      title: "Aide à améliorer OTP LOL.",
      feedback: "Envoyer un feedback",
      ideas: "Donner des idées au dev",
      source: "Voir le code",
    },
    footer: {
      releases: "Releases GitHub",
      source: "Code source",
      windows: "Windows uniquement",
    },
  },
};

const screenshotSources = [
  { src: "assets/screenshots/main-window.png", width: 420, height: 283 },
  { src: "assets/screenshots/settings-window.png", width: 982, height: 850 },
  { src: "assets/screenshots/champ-select.png", width: 758, height: 736 },
];

function App() {
  const [downloadState, setDownloadState] = useState<DownloadState>("idle");
  const [lang, setLang] = useState<Lang>("en");
  const shouldReduceMotion = useReducedMotion();
  const t = copy[lang];

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const releaseLabel = useMemo(() => {
    if (downloadState === "loading") return t.download.loading;
    if (downloadState === "fallback") return t.download.fallback;
    return t.download.idle;
  }, [downloadState, t.download.fallback, t.download.idle, t.download.loading]);

  async function downloadLatestWindowsBuild() {
    setDownloadState("loading");

    try {
      const response = await fetch(latestReleaseApi, {
        headers: { Accept: "application/vnd.github+json" },
      });

      if (!response.ok) throw new Error("GitHub release unavailable");

      const release = await response.json();
      const windowsAsset = release.assets?.find(
        (asset: { name?: string }) => asset.name === windowsAssetName,
      );

      if (windowsAsset?.browser_download_url) {
        window.location.href = windowsAsset.browser_download_url;
        setDownloadState("idle");
        return;
      }
    } catch {
      // GitHub Pages has no backend: when the API fails, send users to the official release page.
    }

    setDownloadState("fallback");
    window.location.href = latestReleaseUrl;
  }

  return (
    <main className="site-shell">
      <a className="skip-link" href="#top">
        {t.accessibility.skipToContent}
      </a>
      <header className="topbar">
        <a className="brand-mark" href="#top" aria-label={t.accessibility.home}>
          <img src="assets/app/garen.webp" alt="" width="34" height="34" />
          <span>OTP LOL</span>
        </a>
        <div className="topbar-actions">
          <nav className="nav-links" aria-label={t.accessibility.mainNavigation}>
            <a href="#features">{t.nav.features}</a>
            <a href="#screenshots">{t.nav.screenshots}</a>
            <a href="#privacy">{t.nav.privacy}</a>
            <a href="#contact">{t.nav.contact}</a>
          </nav>
          <div className="language-toggle" role="group" aria-label={t.accessibility.languageSelector}>
            <Languages size={17} aria-hidden="true" />
            <button
              type="button"
              className={lang === "en" ? "active" : ""}
              onClick={() => setLang("en")}
              aria-pressed={lang === "en"}
              aria-label={t.accessibility.switchToEnglish}
            >
              EN
            </button>
            <button
              type="button"
              className={lang === "fr" ? "active" : ""}
              onClick={() => setLang("fr")}
              aria-pressed={lang === "fr"}
              aria-label={t.accessibility.switchToFrench}
            >
              FR
            </button>
          </div>
        </div>
      </header>

      <section className="hero" id="top">
        <div className="hero-product">
          <img
            className="hero-logo"
            src="assets/app/garen.webp"
            alt="OTP LOL logo"
            width="256"
            height="256"
            fetchPriority="high"
          />
          <h1>OTP LOL</h1>
        </div>

        <div className="hero-copy">
          <span className="section-kicker">{t.hero.kicker}</span>
          <h2>{t.hero.headline}</h2>
          <div className="hero-actions">
            <button
              className="button primary hero-download"
              type="button"
              onClick={downloadLatestWindowsBuild}
              disabled={downloadState === "loading"}
              aria-busy={downloadState === "loading"}
            >
              <Download size={20} aria-hidden="true" />
              <span aria-live="polite">{releaseLabel}</span>
            </button>
            <a className="button secondary" href={releasesUrl}>
              <MonitorDown size={20} aria-hidden="true" />
              {t.download.other}
            </a>
          </div>
        </div>
      </section>

      <section className="story-section">
        <p>{t.hero.body}</p>
        <p className="author-note">{t.hero.author}</p>
      </section>

      <section className="section split" id="features" aria-labelledby="features-title">
        <div className="section-heading">
          <span className="section-kicker">{t.features.kicker}</span>
          <h2 id="features-title">{t.features.title}</h2>
        </div>

        <div className="feature-grid">
          {t.features.items.map((feature, index) => (
            <motion.article
              className="feature-card"
              key={feature.title}
              initial={shouldReduceMotion ? false : { opacity: 0, y: 14 }}
              whileInView={shouldReduceMotion ? undefined : { opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={
                shouldReduceMotion ? undefined : { duration: 0.32, delay: index * 0.04 }
              }
            >
              <feature.icon size={23} aria-hidden="true" />
              <h3>{feature.title}</h3>
              <p>{feature.body}</p>
            </motion.article>
          ))}
        </div>
      </section>

      <section className="section" id="screenshots" aria-labelledby="screenshots-title">
        <div className="section-heading compact">
          <span className="section-kicker">{t.screenshots.kicker}</span>
          <h2 id="screenshots-title">{t.screenshots.title}</h2>
        </div>

        <div className="showcase">
          {screenshotSources.map((screenshot, index) => (
            <figure className="screenshot-card" key={screenshot.src}>
              <img
                src={screenshot.src}
                alt={`OTP LOL ${t.screenshots.labels[index]} screenshot`}
                width={screenshot.width}
                height={screenshot.height}
                loading="lazy"
                decoding="async"
              />
              <figcaption>{t.screenshots.labels[index]}</figcaption>
            </figure>
          ))}
        </div>
      </section>

      <section
        className="section privacy-section"
        id="privacy"
        aria-labelledby="privacy-title"
      >
        <div className="section-heading compact">
          <span className="section-kicker">{t.privacy.kicker}</span>
          <h2 id="privacy-title">{t.privacy.title}</h2>
        </div>

        <div className="privacy-grid">
          {t.privacy.items.map((item) => (
            <article className="privacy-card" key={item.title}>
              <item.icon size={24} aria-hidden="true" />
              <h3>{item.title}</h3>
              <p>{item.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="trust-section" aria-labelledby="trust-title">
        <div className="trust-card">
          <div className="trust-icon" aria-hidden="true">
            <Radio size={26} aria-hidden="true" />
          </div>
          <div>
            <span className="section-kicker">{t.trust.kicker}</span>
            <h2 id="trust-title">{t.trust.title}</h2>
            <p>{t.trust.body}</p>
            <p className="small-note">{t.trust.note}</p>
          </div>
        </div>
      </section>

      <section className="contact-section" id="contact" aria-labelledby="contact-title">
        <div>
          <span className="section-kicker">{t.contact.kicker}</span>
          <h2 id="contact-title">{t.contact.title}</h2>
        </div>
        <div className="contact-actions">
          <a className="button secondary" href={feedbackMailto}>
            <Mail size={20} aria-hidden="true" />
            {t.contact.feedback}
          </a>
          <a className="button secondary" href={ideasMailto}>
            <Lightbulb size={20} aria-hidden="true" />
            {t.contact.ideas}
          </a>
          <a className="button ghost" href={repoUrl}>
            <Github size={20} aria-hidden="true" />
            {t.contact.source}
          </a>
        </div>
      </section>

      <footer className="footer">
        <div>
          <img src="assets/app/garen.webp" alt="" width="34" height="34" />
          <span>OTP LOL</span>
        </div>
        <a href={releasesUrl}>
          {t.footer.releases} <ExternalLink size={16} aria-hidden="true" />
        </a>
        <a href={repoUrl}>
          {t.footer.source} <Github size={16} aria-hidden="true" />
        </a>
        <span>
          <BadgeCheck size={16} aria-hidden="true" />
          {t.footer.windows}
        </span>
      </footer>
    </main>
  );
}

export default App;
