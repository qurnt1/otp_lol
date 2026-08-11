import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { DownloadAction } from "./components/DownloadAction";
import { SiteHeader } from "./components/SiteHeader";
import { content, type Lang } from "./content";
import { RELEASES_URL, REPOSITORY_URL } from "./githubRelease";

const languageStorageKey = "otp-lol-language";
const feedbackMailto = "mailto:chbtquentin@gmail.com?subject=feedback%20OTP%20LOL";
const ideasMailto = "mailto:chbtquentin@gmail.com?subject=ideas%20OTP%20LOL";

function getInitialLanguage(): Lang {
  const storedLanguage = window.localStorage.getItem(languageStorageKey);
  if (storedLanguage === "en" || storedLanguage === "fr") return storedLanguage;
  return window.navigator.language.toLowerCase().startsWith("fr") ? "fr" : "en";
}

function Reveal({ children, className = "", delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const elementRef = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const element = elementRef.current;
    if (!element || window.matchMedia("(prefers-reduced-motion: reduce)").matches || !("IntersectionObserver" in window)) {
      setVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "0px 0px -12% 0px", threshold: 0.08 },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={elementRef}
      className={`reveal ${visible ? "is-visible" : ""} ${className}`.trim()}
      style={{ "--reveal-delay": `${delay}ms` } as CSSProperties}
    >
      {children}
    </div>
  );
}

function App() {
  const [lang, setLang] = useState<Lang>(getInitialLanguage);
  const copy = content[lang];

  useEffect(() => {
    document.documentElement.lang = lang;
    document.title = copy.title;
    document.querySelector('meta[name="description"]')?.setAttribute("content", copy.metaDescription);
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", "#0d131c");
    window.localStorage.setItem(languageStorageKey, lang);
  }, [copy.metaDescription, copy.title, lang]);

  return (
    <>
      <a className="skip-link" href="#main-content">{copy.nav.skip}</a>
      <SiteHeader lang={lang} copy={copy.nav} onLanguageChange={setLang} />

      <main id="main-content">
        <section className="hero" id="top" aria-labelledby="hero-title">
          <div className="hero__ambient" aria-hidden="true" />
          <div className="hero__grid">
            <Reveal className="hero__copy">
              <p className="eyebrow"><span className="eyebrow__dot" aria-hidden="true" />{copy.hero.eyebrow}</p>
              <div className="hero__title-line">
                <h1 id="hero-title">{copy.hero.headline}</h1>
                <span className="hero__index" aria-hidden="true">01<span>/</span>04</span>
              </div>
              <p className="hero__lede">{copy.hero.body}</p>
              <DownloadAction copy={copy.download} />
              <ul className="hero__facts" aria-label={copy.hero.factsLabel}>
                {copy.hero.facts.map((fact) => <li key={fact}><span aria-hidden="true">+</span>{fact}</li>)}
              </ul>
            </Reveal>

            <Reveal className="hero__product" delay={120}>
              <div className="product-stage">
                <div className="product-stage__meta">
                  <span>{copy.hero.previewLabel}</span>
                  <span className="product-stage__signal"><i aria-hidden="true" />{copy.hero.previewStatus}</span>
                </div>
                <figure className="product-stage__capture">
                  <img
                    src="assets/screenshots/main-window.png"
                    alt={copy.hero.previewAlt}
                    width="820"
                    height="760"
                    fetchPriority="high"
                  />
                </figure>
                <div className="product-stage__caption">
                  <span>{copy.hero.previewCaption}</span>
                  <span aria-hidden="true">↗</span>
                </div>
              </div>
              <div className="hero__orbit hero__orbit--one" aria-hidden="true">GAREN</div>
              <div className="hero__orbit hero__orbit--two" aria-hidden="true">LOCAL / LCU</div>
            </Reveal>
          </div>
          <div className="hero__footer">
            <span>{copy.hero.footerNote}</span>
            <a href="#workflow">{copy.hero.footerLink}<span aria-hidden="true"> ↓</span></a>
          </div>
        </section>

        <section className="route-strip" aria-label={copy.route.label}>
          <div className="route-strip__inner">
            {copy.route.steps.map((step, index) => (
              <Reveal className="route-step" delay={index * 55} key={step.label}>
                <span className="route-step__number">0{index + 1}</span>
                <div><strong>{step.label}</strong><span>{step.body}</span></div>
                {index < copy.route.steps.length - 1 && <span className="route-step__arrow" aria-hidden="true">→</span>}
              </Reveal>
            ))}
          </div>
        </section>

        <section className="workflow section" id="workflow" aria-labelledby="workflow-title">
          <Reveal className="section-heading">
            <p className="section-kicker">{copy.workflow.kicker}</p>
            <h2 id="workflow-title">{copy.workflow.title}</h2>
            <p>{copy.workflow.intro}</p>
          </Reveal>
          <ol className="workflow-list">
            {copy.workflow.steps.map((step, index) => (
              <Reveal className="workflow-step" delay={index * 60} key={step.number}>
                <div className="workflow-step__copy">
                  <div className="stage-label"><span>{step.number}</span><span>{step.verb}</span></div>
                  <h3>{step.title}</h3>
                  <p>{step.body}</p>
                  <a className="inline-link" href="#download">{copy.workflow.cta}<span aria-hidden="true"> ↗</span></a>
                </div>
                <figure className="product-capture">
                  <img src={step.image} alt={step.alt} width={step.width} height={step.height} loading="lazy" />
                  <figcaption><span>{copy.workflow.captureNote}</span><span aria-hidden="true">↗</span></figcaption>
                </figure>
              </Reveal>
            ))}
          </ol>
        </section>

        <section className="capabilities section" id="capabilities" aria-labelledby="capabilities-title">
          <Reveal className="section-heading section-heading--split">
            <div><p className="section-kicker">{copy.capabilities.kicker}</p><h2 id="capabilities-title">{copy.capabilities.title}</h2></div>
            <p>{copy.capabilities.intro}</p>
          </Reveal>
          <dl className="capability-ledger">
            {copy.capabilities.items.map((item, index) => (
              <Reveal className="capability-row" delay={index * 45} key={item.title}>
                <dt><span>{item.label}</span><b>0{index + 1}</b></dt>
                <dd><strong>{item.title}</strong><span>{item.body}</span></dd>
              </Reveal>
            ))}
          </dl>
        </section>

        <section className="privacy section" id="privacy" aria-labelledby="privacy-title">
          <Reveal className="section-heading section-heading--split">
            <div><p className="section-kicker">{copy.privacy.kicker}</p><h2 id="privacy-title">{copy.privacy.title}</h2></div>
            <p>{copy.privacy.intro}</p>
          </Reveal>
          <div className="privacy-ledger">
            <Reveal className="privacy-card privacy-card--local">
              <span className="privacy-card__mark" aria-hidden="true">L</span>
              <h3>{copy.privacy.localTitle}</h3>
              <p>{copy.privacy.localBody}</p>
              <span className="privacy-card__code">{copy.privacy.localCode}</span>
            </Reveal>
            <Reveal className="privacy-card privacy-card--network" delay={80}>
              <span className="privacy-card__mark" aria-hidden="true">N</span>
              <h3>{copy.privacy.networkTitle}</h3>
              <p>{copy.privacy.networkBody}</p>
              <span className="privacy-card__code">{copy.privacy.networkCode}</span>
            </Reveal>
          </div>
          <p className="disclaimer">{copy.privacy.disclaimer}</p>
        </section>

        <section className="contact" id="contact" aria-labelledby="contact-title">
          <div className="contact__inner">
            <Reveal>
              <p className="section-kicker section-kicker--light">{copy.contact.kicker}</p>
              <h2 id="contact-title">{copy.contact.title}</h2>
              <p>{copy.contact.body}</p>
            </Reveal>
            <Reveal className="contact__actions" delay={100}>
              <a className="button button--light" id="download" href={RELEASES_URL}>{copy.contact.download}<span aria-hidden="true"> ↗</span></a>
              <a className="text-link text-link--light" href={feedbackMailto}>{copy.contact.feedback}<span aria-hidden="true"> ↗</span></a>
              <a className="text-link text-link--light" href={ideasMailto}>{copy.contact.ideas}<span aria-hidden="true"> ↗</span></a>
            </Reveal>
          </div>
        </section>
      </main>

      <footer className="site-footer">
        <p>{copy.footer.statement}</p>
        <div className="site-footer__meta">
          <strong translate="no">OTP LOL</strong>
          <a href={RELEASES_URL}>{copy.footer.releases}</a>
          <a href={REPOSITORY_URL}>{copy.footer.source}</a>
          <span>{copy.footer.platform}</span>
        </div>
      </footer>
    </>
  );
}

export default App;
