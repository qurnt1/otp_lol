import { useEffect, useState } from "react";
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

function App() {
  const [lang, setLang] = useState<Lang>(getInitialLanguage);
  const copy = content[lang];

  useEffect(() => {
    document.documentElement.lang = lang;
    document.title = "OTP LOL — Local Windows assistant";
    document.querySelector('meta[name="description"]')?.setAttribute("content", copy.metaDescription);
    window.localStorage.setItem(languageStorageKey, lang);
  }, [copy.metaDescription, lang]);

  return (
    <>
      <a className="skip-link" href="#main-content">{lang === "fr" ? "Aller au contenu" : "Skip to content"}</a>
      <SiteHeader lang={lang} copy={copy.nav} onLanguageChange={setLang} />

      <main id="main-content">
        <section className="hero" id="top" aria-labelledby="hero-title">
          <div className="hero__copy">
            <p className="utility-label">{copy.hero.utility}</p>
            <h1 id="hero-title">{copy.hero.headline}</h1>
            <p className="hero__lede">{copy.hero.body}</p>
            <DownloadAction copy={copy.download} />
            <ul className="fact-line" aria-label="Product facts">{copy.hero.facts.map((fact) => <li key={fact}>{fact}</li>)}</ul>
          </div>

          <aside className="signal-board" aria-label={copy.hero.sequenceLabel}>
            <div className="signal-board__heading"><span>{copy.hero.sequenceLabel}</span><span aria-hidden="true">01—03</span></div>
            <ol>{copy.hero.sequence.map((step, index) => (
              <li key={step.title}>
                <span className="signal-board__stop" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
                <div><h2>{step.title}</h2><p>{step.body}</p></div>
              </li>
            ))}</ol>
          </aside>
        </section>

        <section className="workflow section" id="workflow">
          <header className="section-heading"><h2>{copy.workflow.title}</h2><p>{copy.workflow.intro}</p></header>
          <ol className="workflow-list">{copy.workflow.steps.map((step) => (
            <li className="workflow-step" key={step.number}>
              <div className="workflow-step__copy">
                <div className="stage-label"><span>{step.number}</span><span>{step.verb}</span></div>
                <h3>{step.title}</h3><p>{step.body}</p>
              </div>
              <figure className="product-capture">
                <img src={step.image} alt={step.alt} loading="lazy" />
                <figcaption><span>{copy.workflow.captureNote}</span><span aria-hidden="true">↗</span></figcaption>
              </figure>
            </li>
          ))}</ol>
        </section>

        <section className="capabilities section" id="capabilities">
          <header className="section-heading section-heading--split"><h2>{copy.capabilities.title}</h2><p>{copy.capabilities.intro}</p></header>
          <dl className="capability-ledger">{copy.capabilities.items.map((item) => (
            <div className="capability-row" key={item.title}><dt>{item.label}</dt><dd><strong>{item.title}</strong><span>{item.body}</span></dd></div>
          ))}</dl>
        </section>

        <section className="privacy section" id="privacy">
          <header className="section-heading section-heading--split"><h2>{copy.privacy.title}</h2><p>{copy.privacy.intro}</p></header>
          <div className="privacy-ledger">
            <article><span className="privacy-ledger__mark" aria-hidden="true">L</span><h3>{copy.privacy.localTitle}</h3><p>{copy.privacy.localBody}</p></article>
            <article><span className="privacy-ledger__mark" aria-hidden="true">N</span><h3>{copy.privacy.networkTitle}</h3><p>{copy.privacy.networkBody}</p></article>
          </div>
          <p className="disclaimer">{copy.privacy.disclaimer}</p>
        </section>

        <section className="contact" id="contact">
          <div className="contact__inner">
            <div><h2>{copy.contact.title}</h2><p>{copy.contact.body}</p></div>
            <div className="contact__actions">
              <a className="button button--light" href={feedbackMailto}>{copy.contact.feedback} <span aria-hidden="true">↗</span></a>
              <a className="text-link text-link--light" href={ideasMailto}>{copy.contact.ideas} <span aria-hidden="true">↗</span></a>
              <a className="text-link text-link--light" href={REPOSITORY_URL}>{copy.contact.source} <span aria-hidden="true">↗</span></a>
            </div>
          </div>
        </section>
      </main>

      <footer className="site-footer">
        <p>{copy.footer.statement}</p>
        <div className="site-footer__meta">
          <strong>OTP LOL</strong><a href={RELEASES_URL}>{copy.footer.releases}</a><a href={REPOSITORY_URL}>{copy.footer.source}</a><span>{copy.footer.platform}</span>
        </div>
      </footer>
    </>
  );
}

export default App;
