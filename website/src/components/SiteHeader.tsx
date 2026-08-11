import { useEffect, useState } from "react";
import type { Lang, SiteCopy } from "../content";
import { REPOSITORY_URL } from "../githubRelease";

type SiteHeaderProps = { lang: Lang; copy: SiteCopy["nav"]; onLanguageChange: (lang: Lang) => void };
const destinations = [["workflow", "workflow"], ["capabilities", "capabilities"], ["privacy", "privacy"], ["contact", "contact"]] as const;

export function SiteHeader({ lang, copy, onLanguageChange }: SiteHeaderProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!menuOpen) return;
    function closeOnEscape(event: KeyboardEvent) { if (event.key === "Escape") setMenuOpen(false); }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [menuOpen]);

  const navLinks = destinations.map(([id, label]) => <a key={id} href={`#${id}`} onClick={() => setMenuOpen(false)}>{copy[label]}</a>);

  return (
    <header className="site-header">
      <a className="brand" href="#top" aria-label={copy.home}>
        <img className="brand__mark" src="assets/app/garen.webp" alt="" width="40" height="40" />
        <span translate="no">OTP LOL</span>
      </a>
      <nav className="desktop-nav" aria-label={copy.label}>{navLinks}</nav>
      <div className="header-actions">
        <div className="language-switch" role="group" aria-label={copy.language}>
          <button type="button" aria-label={copy.switchToEnglish} aria-pressed={lang === "en"} onClick={() => onLanguageChange("en")}>EN</button>
          <button type="button" aria-label={copy.switchToFrench} aria-pressed={lang === "fr"} onClick={() => onLanguageChange("fr")}>FR</button>
        </div>
        <a className="header-source" href={REPOSITORY_URL}>GitHub <span aria-hidden="true">↗</span></a>
        <button className="menu-toggle" type="button" aria-expanded={menuOpen} aria-controls="mobile-navigation" onClick={() => setMenuOpen((open) => !open)}>{menuOpen ? copy.close : copy.menu}</button>
      </div>
      <nav className="mobile-nav" id="mobile-navigation" aria-label={copy.label} hidden={!menuOpen}>{navLinks}</nav>
    </header>
  );
}

