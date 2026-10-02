import { useRef, useState } from "react";
import type { MouseEvent } from "react";
import content from "../content.json";
import dashboardImage from "../../../docs/images/dashboard-web.png";
import settingsImage from "../../../docs/images/settings-web.png";
import statisticsImage from "../../../docs/images/statistics-web.png";
import garenImage from "../../../frontend/public/assets/app/garen.webp";

const screenshots = content.screenshots;
const screenshotImages = {
  settings: settingsImage,
  statistics: statisticsImage,
};
type ScreenshotId = keyof typeof screenshotImages;

export default function App() {
  const [activeScreenshotId, setActiveScreenshotId] = useState(screenshots[0].id);
  const [imageAtActualSize, setImageAtActualSize] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const activeScreenshot = screenshots.find((shot) => shot.id === activeScreenshotId) ?? screenshots[0];
  const activeImage = screenshotImages[activeScreenshot.id as ScreenshotId];

  const closeOnBackdrop = (event: MouseEvent<HTMLDialogElement>) => {
    if (event.target === dialogRef.current) dialogRef.current.close();
  };

  return (
    <div id="top">
      <a className="skip-link" href="#main">Aller au contenu</a>
      <header className="site-header">
        <div className="header-inner">
          <a className="brand" href="#top" aria-label="OTP LOL, accueil">
            <img src={garenImage} alt="" width="34" height="34" />
            <span>OTP <strong>LOL</strong></span>
          </a>
          <nav className="main-nav" aria-label="Navigation principale">
            <a href="#fonctionnement">Fonctionnement</a>
            <a href="#captures">L’application</a>
            <a href="#installation">Installation</a>
          </nav>
          <a className="button button-small button-primary header-download" href={content.releasesUrl} target="_blank" rel="noreferrer">
            Téléchargements
            <span aria-hidden="true">↗</span>
          </a>
        </div>
      </header>

      <main id="main">
        <section className="hero section-wrap" aria-labelledby="hero-title">
          <div className="hero-copy">
            <p className="eyebrow">Compagnon League pour Windows</p>
            <h1 id="hero-title">Tes choix prêts avant la sélection.</h1>
            <p className="hero-lead">Prépare tes priorités, tes sorts, tes runes et tes skins. OTP LOL applique uniquement les automatismes que tu actives, sur ton PC.</p>
            <div className="hero-actions">
              <a className="button button-primary" href={content.releasesUrl} target="_blank" rel="noreferrer">
                Voir les téléchargements Windows <span aria-hidden="true">↗</span>
              </a>
              <a className="text-link" href="#captures">Voir l’application <span aria-hidden="true">↓</span></a>
            </div>
            <p className="requirements">Il te faut Windows, le client League sur le même ordinateur et le runtime Microsoft Edge WebView2.</p>
          </div>
          <figure className="hero-figure">
            <div className="hero-image-wrap">
              <img
                src={dashboardImage}
                alt="Capture du tableau de bord OTP LOL avec les priorités de champions et les options de partie."
                width="1917"
                height="1002"
                fetchPriority="high"
              />
            </div>
            <figcaption><span>Tableau de bord</span><span>Capture de test avec données simulées</span></figcaption>
          </figure>
        </section>

        <section className="workflow" id="fonctionnement" aria-labelledby="workflow-title">
          <div className="section-wrap">
            <div className="section-heading">
              <p className="eyebrow">La routine, à ta façon</p>
              <h2 id="workflow-title">Tu règles. Tu choisis.<br />League continue.</h2>
              <p>OTP LOL prépare les actions autour de la partie. Tu gardes le contrôle de ce qui s’active.</p>
            </div>
            <ol className="workflow-list">
              <li>
                <span className="step-number">01</span>
                <div><h3>Prépare tes presets</h3><p>Classe jusqu’à trois picks prioritaires. Configure le ban, les sorts, les runes et un skin fixe ou tiré d’un pool.</p></div>
                <span className="step-marker" aria-hidden="true">↘</span>
              </li>
              <li>
                <span className="step-number">02</span>
                <div><h3>Active les actions voulues</h3><p>Auto-Accept attend le ready-check. Auto-Pick passe aux champions indisponibles ou bannis. Chaque automatisme se règle séparément.</p></div>
                <span className="step-marker" aria-hidden="true">↘</span>
              </li>
              <li>
                <span className="step-number">03</span>
                <div><h3>Lance ta file dans League</h3><p>OTP LOL suit le client local. Après la partie, le retour au lobby peut être activé lorsque League le permet.</p></div>
                <span className="step-marker" aria-hidden="true">↗</span>
              </li>
            </ol>
          </div>
        </section>

        <section className="showcase section-wrap" id="captures" aria-labelledby="showcase-title">
          <div className="showcase-heading">
            <div>
              <p className="eyebrow">L’application, en vrai</p>
              <h2 id="showcase-title">Les réglages se voient.<br />Les choix restent les tiens.</h2>
            </div>
            <p>Parcours les écrans de préparation, de réglages et de statistiques.</p>
          </div>
          <div className="shot-selector" role="group" aria-label="Choisir une capture de l’application">
            {screenshots.map((shot) => (
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
              key={activeScreenshot.id}
              className="showcase-image"
              src={activeImage}
              alt={activeScreenshot.alt}
              width="1917"
              height={activeScreenshot.id === "settings" ? "892" : "1002"}
              loading="lazy"
            />
            <figcaption className="showcase-caption">
              <span aria-live="polite">{activeScreenshot.note}</span>
              <button className="text-link expand-button" type="button" aria-haspopup="dialog" onClick={() => { setImageAtActualSize(false); dialogRef.current?.showModal(); }}>
                Agrandir la capture <span aria-hidden="true">↗</span>
              </button>
            </figcaption>
          </figure>
        </section>

        <section className="features" aria-labelledby="features-title">
          <div className="section-wrap">
            <div className="section-heading feature-heading">
              <p className="eyebrow">Précis quand League en a besoin</p>
              <h2 id="features-title">Une routine visible.<br />Aucune stratégie à ta place.</h2>
            </div>
            <div className="feature-columns">
              <article className="feature-column">
                <h3>Dans la sélection</h3>
                <p>Choisis tes picks par ordre de priorité, ton ban et les éléments de ton preset. Si un champion ne peut pas être pris, OTP LOL passe au suivant configuré.</p>
                <ul><li>Sorts et pages de runes</li><li>Skin fixe ou pool aléatoire</li><li>Automatismes désactivés au premier lancement</li></ul>
              </article>
              <article className="feature-column">
                <h3>Pour tes statistiques</h3>
                <p>Ouvre le profil de ton compte ou les statistiques de la partie avec le fournisseur que tu choisis. Ces pages viennent de services tiers.</p>
                <p className="provider-copy"><strong>Profil</strong> OP.GG, DeepLOL, DPM.LOL, League of Graphs<br /><strong>En direct</strong> Porofessor, DeepLOL, DPM.LOL, OP.GG</p>
              </article>
            </div>
          </div>
        </section>

        <section className="local section-wrap" id="installation" aria-labelledby="local-title">
          <div className="local-intro">
            <p className="eyebrow">Sur ton ordinateur</p>
            <h2 id="local-title">Tes réglages restent chez toi.</h2>
            <p>OTP LOL fonctionne en local auprès du client League installé sur le même PC. Tes réglages et ton historique restent sur ton ordinateur. Il ne demande pas de compte OTP LOL et n’héberge pas de profil joueur.</p>
            <a className="text-link" href={content.projectUrl} target="_blank" rel="noreferrer">Voir le projet sur GitHub <span aria-hidden="true">↗</span></a>
          </div>
          <div className="install-block">
            <h3>Pour commencer</h3>
            <ol>
              <li><span>1</span><p>Télécharge l’installateur depuis la page des releases.</p></li>
              <li><span>2</span><p>Installe WebView2 si ton PC te le demande, puis relance l’installateur.</p></li>
              <li><span>3</span><p>Ouvre League et OTP LOL. Configure tes presets avant d’activer une automatisation.</p></li>
            </ol>
            <a className="button button-light" href={content.releasesUrl} target="_blank" rel="noreferrer">Ouvrir les téléchargements <span aria-hidden="true">↗</span></a>
          </div>
          <p className="data-note">L’application peut contacter les services de métadonnées League et de mise à jour. Quand tu ouvres un profil, le fournisseur choisi reçoit le lien correspondant.</p>
        </section>

        <section className="faq section-wrap" aria-labelledby="faq-title">
          <div className="faq-heading">
            <p className="eyebrow">Avant de te lancer</p>
            <h2 id="faq-title">Questions pratiques.</h2>
          </div>
          <div className="faq-list">
            <details>
              <summary>OTP LOL joue-t-il à ma place ?</summary>
              <p>Non. Il ne joue pas la partie et ne choisit pas ta stratégie. Il applique les actions de client que tu as configurées, dans les phases où League les autorise.</p>
            </details>
            <details>
              <summary>Les automatismes sont-ils activés d’avance ?</summary>
              <p>Non. Ils sont désactivés au premier lancement. Tu peux configurer les presets, puis activer chaque automatisme séparément.</p>
            </details>
            <details>
              <summary>De quoi ai-je besoin pour l’installer ?</summary>
              <p>D’un PC Windows, du client League installé sur ce même PC et du runtime Microsoft Edge WebView2. Si WebView2 manque, installe-le depuis la page Microsoft qui s’ouvre, puis relance l’installateur.</p>
            </details>
            <details>
              <summary>D’où viennent les statistiques ?</summary>
              <p>Les données de profil et de partie sont fournies par le service tiers que tu sélectionnes. OTP LOL prépare le lien et l’ouvre dans une fenêtre dédiée, avec le navigateur comme solution de repli.</p>
            </details>
          </div>
        </section>

        <section className="closing">
          <div className="section-wrap closing-inner">
            <div>
              <p className="eyebrow">OTP LOL pour Windows</p>
              <h2>Configure ta routine.<br />Puis lance ta partie.</h2>
            </div>
            <a className="button button-primary" href={content.releasesUrl} target="_blank" rel="noreferrer">Voir la dernière version <span aria-hidden="true">↗</span></a>
          </div>
        </section>
      </main>

      <footer className="site-footer">
        <div className="section-wrap footer-inner">
          <a className="brand" href="#top" aria-label="OTP LOL, retour en haut">
            <img src={garenImage} alt="" width="30" height="30" />
            <span>OTP <strong>LOL</strong></span>
          </a>
          <span className="footer-note">Projet indépendant pour League of Legends.</span>
          <div className="footer-links">
            <a href={content.projectUrl} target="_blank" rel="noreferrer">GitHub</a>
            <a href={content.releasesUrl} target="_blank" rel="noreferrer">Téléchargements</a>
          </div>
          <small>OTP LOL n’est ni affilié à Riot Games ni approuvé par Riot Games. League of Legends et ses marques appartiennent à Riot Games.</small>
        </div>
      </footer>

      <dialog className="image-dialog" data-size={imageAtActualSize ? "actual" : "fit"} ref={dialogRef} aria-labelledby="dialog-title" onClick={closeOnBackdrop}>
        <div className="dialog-bar">
          <h2 id="dialog-title">{activeScreenshot.label}</h2>
          <div className="dialog-actions">
            <button className="dialog-size" type="button" aria-label={imageAtActualSize ? "Ajuster la capture à la fenêtre" : "Afficher la capture à sa taille réelle"} aria-pressed={imageAtActualSize} onClick={() => setImageAtActualSize((actual) => !actual)}>
              {imageAtActualSize ? "Ajuster" : "Taille réelle"}
            </button>
            <button className="dialog-close" type="button" aria-label="Fermer la capture agrandie" onClick={() => dialogRef.current?.close()}>×</button>
          </div>
        </div>
        <img src={activeImage} alt={activeScreenshot.alt} />
      </dialog>
    </div>
  );
}
