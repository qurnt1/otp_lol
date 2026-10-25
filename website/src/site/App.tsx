import { useEffect, useRef, useState } from "react";
import type { MouseEvent } from "react";
import content from "../content.json";
import dashboardImage from "../../../docs/images/portfolio-dashboard-demo.png";
import settingsImage from "../../../docs/images/portfolio-settings-demo.jpg";
import statisticsImage from "../../../docs/images/portfolio-statistics-demo.jpg";
import garenImage from "../../../frontend/public/assets/app/garen.webp";
import { siteCopy } from "./copy";
import type { Locale, ScreenshotCopy } from "./copy";

const screenshotImages = {
  settings: settingsImage,
  statistics: statisticsImage,
};
const contactHref = `mailto:${content.contactEmail}?subject=OTP%20LOL%20contact`;

function preferredLocale(): Locale {
  return typeof navigator !== "undefined" && navigator.language.toLowerCase().startsWith("fr") ? "fr" : "en";
}

export default function App() {
  const [locale, setLocale] = useState<Locale>(preferredLocale);
  const [activeScreenshotId, setActiveScreenshotId] = useState<ScreenshotCopy["id"]>(siteCopy.fr.showcase.screenshots[0].id);
  const [imageAtActualSize, setImageAtActualSize] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const t = siteCopy[locale];
  const activeScreenshot = t.showcase.screenshots.find((shot) => shot.id === activeScreenshotId) ?? t.showcase.screenshots[0];
  const activeImage = screenshotImages[activeScreenshot.id];

  useEffect(() => {
    document.documentElement.lang = locale;
    document.title = t.documentTitle;
    document.querySelector('meta[name="description"]')?.setAttribute("content", t.metaDescription);
    document.querySelector('meta[property="og:title"]')?.setAttribute("content", t.documentTitle);
    document.querySelector('meta[property="og:description"]')?.setAttribute("content", t.metaDescription);
    document.querySelector('meta[property="og:locale"]')?.setAttribute("content", locale === "fr" ? "fr_FR" : "en_US");
    document.querySelector('meta[name="twitter:title"]')?.setAttribute("content", t.documentTitle);
    document.querySelector('meta[name="twitter:description"]')?.setAttribute("content", t.metaDescription);
  }, [locale, t]);

  const closeOnBackdrop = (event: MouseEvent<HTMLDialogElement>) => {
    if (event.target === dialogRef.current) dialogRef.current.close();
  };

  return (
    <div id="top">
      <a className="skip-link" href="#main">{t.skipToContent}</a>
      <header className="site-header">
        <div className="header-inner">
          <a className="brand" href="#top" aria-label={t.home}>
            <img src={garenImage} alt="" width="34" height="34" />
            <span>OTP <strong>LOL</strong></span>
          </a>
          <nav className="main-nav" aria-label={t.navigation}>
            <a href="#fonctionnement">{t.nav.workflow}</a>
            <a href="#captures">{t.nav.app}</a>
            <a href="#installation">{t.nav.installation}</a>
            <a href="#contact">{t.nav.contact}</a>
          </nav>
          <div className="header-actions">
            <div className="language-toggle" role="group" aria-label={t.languageSelector}>
              <button type="button" aria-pressed={locale === "en"} aria-label={t.switchToEnglish} onClick={() => setLocale("en")}>EN</button>
              <button type="button" aria-pressed={locale === "fr"} aria-label={t.switchToFrench} onClick={() => setLocale("fr")}>FR</button>
            </div>
            <a className="button button-small button-primary header-download" href={content.releasesUrl} target="_blank" rel="noreferrer">
              {t.downloads}<span aria-hidden="true">↗</span>
            </a>
          </div>
        </div>
      </header>

      <main id="main">
        <section className="hero section-wrap" aria-labelledby="hero-title">
          <div className="hero-copy">
            <p className="eyebrow">{t.hero.eyebrow}</p>
            <h1 id="hero-title">{t.hero.title[0]}<br />{t.hero.title[1]}</h1>
            <p className="hero-lead">{t.hero.lead}</p>
            <div className="hero-actions">
              <a className="button button-primary" href={content.releasesUrl} target="_blank" rel="noreferrer">
                {t.hero.download}<span aria-hidden="true">↗</span>
              </a>
              <a className="text-link" href="#captures">{t.hero.seeApp}<span aria-hidden="true">↓</span></a>
            </div>
            <p className="requirements">{t.hero.requirements}</p>
          </div>
          <figure className="hero-figure">
            <div className="hero-image-wrap">
              <img src={dashboardImage} alt={t.hero.imageAlt} width="1920" height="1080" fetchPriority="high" />
            </div>
            <figcaption><span>{t.hero.caption}</span><span>{t.hero.captionNote}</span></figcaption>
          </figure>
        </section>

        <section className="workflow" id="fonctionnement" aria-labelledby="workflow-title">
          <div className="section-wrap">
            <div className="section-heading">
              <p className="eyebrow">{t.workflow.eyebrow}</p>
              <h2 id="workflow-title">{t.workflow.title[0]}<br />{t.workflow.title[1]}</h2>
              <p>{t.workflow.intro}</p>
            </div>
            <ol className="workflow-list">
              {t.workflow.steps.map((step, index) => (
                <li key={step.title}>
                  <span className="step-number">0{index + 1}</span>
                  <div><h3>{step.title}</h3><p>{step.body}</p></div>
                  <span className="step-marker" aria-hidden="true">{index === 2 ? "↗" : "↘"}</span>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="showcase section-wrap" id="captures" aria-labelledby="showcase-title">
          <div className="showcase-heading">
            <div>
              <p className="eyebrow">{t.showcase.eyebrow}</p>
              <h2 id="showcase-title">{t.showcase.title[0]}<br />{t.showcase.title[1]}</h2>
            </div>
            <p>{t.showcase.intro}</p>
          </div>
          <div className="shot-selector" role="group" aria-label={t.showcase.selector}>
            {t.showcase.screenshots.map((shot) => (
              <button
                className="shot-tab"
                key={shot.id}
                type="button"
                aria-pressed={activeScreenshotId === shot.id}
                onClick={() => setActiveScreenshotId(shot.id)}
              >
                <span className="shot-tab-label">{shot.label}</span>
                <span className="shot-tab-title">{shot.title}</span>
              </button>
            ))}
          </div>
          <figure className="showcase-frame">
            <img
              key={`${locale}-${activeScreenshot.id}`}
              className="showcase-image"
              src={activeImage}
              alt={activeScreenshot.alt}
              width="1440"
              height="920"
              loading="lazy"
            />
            <figcaption className="showcase-caption">
              <span aria-live="polite">{activeScreenshot.note}</span>
              <button className="text-link expand-button" type="button" aria-haspopup="dialog" onClick={() => { setImageAtActualSize(false); dialogRef.current?.showModal(); }}>
                {t.showcase.enlarge}<span aria-hidden="true">↗</span>
              </button>
            </figcaption>
          </figure>
        </section>

        <section className="features" aria-labelledby="features-title">
          <div className="section-wrap">
            <div className="section-heading feature-heading">
              <p className="eyebrow">{t.features.eyebrow}</p>
              <h2 id="features-title">{t.features.title[0]}<br />{t.features.title[1]}</h2>
            </div>
            <div className="feature-columns">
              <article className="feature-column">
                <h3>{t.features.championSelect}</h3>
                <p>{t.features.championSelectBody}</p>
                <ul>{t.features.championSelectItems.map((item) => <li key={item}>{item}</li>)}</ul>
              </article>
              <article className="feature-column">
                <h3>{t.features.stats}</h3>
                <p>{t.features.statsBody}</p>
                <p className="provider-copy"><strong>{t.features.profile}</strong> OP.GG, DeepLOL, DPM.LOL, League of Graphs<br /><strong>{t.features.live}</strong> Porofessor, DeepLOL, DPM.LOL, OP.GG</p>
              </article>
            </div>
          </div>
        </section>

        <section className="local section-wrap" id="installation" aria-labelledby="local-title">
          <div className="local-intro">
            <p className="eyebrow">{t.installation.eyebrow}</p>
            <h2 id="local-title">{t.installation.title}</h2>
            <p>{t.installation.intro}</p>
            <a className="text-link" href={content.projectUrl} target="_blank" rel="noreferrer">{t.installation.github}<span aria-hidden="true">↗</span></a>
          </div>
          <div className="install-block">
            <h3>{t.installation.start}</h3>
            <ol>
              {t.installation.steps.map((step, index) => <li key={step}><span>{index + 1}</span><p>{step}</p></li>)}
            </ol>
            <a className="button button-light" href={content.releasesUrl} target="_blank" rel="noreferrer">{t.installation.downloads}<span aria-hidden="true">↗</span></a>
          </div>
          <p className="data-note">{t.installation.dataNote}</p>
        </section>

        <section className="faq section-wrap" aria-labelledby="faq-title">
          <div className="faq-heading">
            <p className="eyebrow">{t.faq.eyebrow}</p>
            <h2 id="faq-title">{t.faq.title}</h2>
          </div>
          <div className="faq-list">
            {t.faq.items.map((item) => <details key={item.question}><summary>{item.question}</summary><p>{item.answer}</p></details>)}
          </div>
        </section>

        <section className="contact-section" id="contact" aria-labelledby="contact-title">
          <div className="section-wrap contact-inner">
            <div>
              <p className="eyebrow">{t.contact.eyebrow}</p>
              <h2 id="contact-title">{t.contact.title}</h2>
              <p>{t.contact.body}</p>
            </div>
            <a className="button button-primary" href={contactHref}>{t.contact.email}<span aria-hidden="true">↗</span></a>
          </div>
        </section>

        <section className="closing">
          <div className="section-wrap closing-inner">
            <div>
              <p className="eyebrow">{t.closing.eyebrow}</p>
              <h2>{t.closing.title[0]}<br />{t.closing.title[1]}</h2>
            </div>
            <a className="button button-primary" href={content.releasesUrl} target="_blank" rel="noreferrer">{t.closing.download}<span aria-hidden="true">↗</span></a>
          </div>
        </section>
      </main>

      <footer className="site-footer">
        <div className="section-wrap footer-inner">
          <a className="brand" href="#top" aria-label={t.footer.backToTop}>
            <img src={garenImage} alt="" width="30" height="30" />
            <span>OTP <strong>LOL</strong></span>
          </a>
          <span className="footer-note">{t.footer.note}</span>
          <div className="footer-links">
            <a href={content.projectUrl} target="_blank" rel="noreferrer">GitHub</a>
            <a href={content.releasesUrl} target="_blank" rel="noreferrer">{t.footer.downloads}</a>
            <a href={contactHref}>{t.nav.contact}</a>
          </div>
          <small>{t.footer.disclaimer}</small>
        </div>
      </footer>

      <dialog className="image-dialog" data-size={imageAtActualSize ? "actual" : "fit"} ref={dialogRef} aria-labelledby="dialog-title" onClick={closeOnBackdrop}>
        <div className="dialog-bar">
          <h2 id="dialog-title">{activeScreenshot.label}</h2>
          <div className="dialog-actions">
            <button className="dialog-size" type="button" aria-label={imageAtActualSize ? t.dialog.fit : t.dialog.actual} aria-pressed={imageAtActualSize} onClick={() => setImageAtActualSize((actual) => !actual)}>
              {imageAtActualSize ? (locale === "fr" ? "Ajuster" : "Fit") : (locale === "fr" ? "Taille réelle" : "Actual size")}
            </button>
            <button className="dialog-close" type="button" aria-label={t.dialog.close} onClick={() => dialogRef.current?.close()}>×</button>
          </div>
        </div>
        <img src={activeImage} alt={activeScreenshot.alt} />
      </dialog>
    </div>
  );
}
