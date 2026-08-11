export type Lang = "en" | "fr";

type WorkflowStep = {
  number: string;
  verb: string;
  title: string;
  body: string;
  image: string;
  alt: string;
  width: number;
  height: number;
};

type Capability = { label: string; title: string; body: string };
type RouteStep = { label: string; body: string };

export type SiteCopy = {
  title: string;
  metaDescription: string;
  nav: {
    home: string;
    label: string;
    workflow: string;
    capabilities: string;
    privacy: string;
    contact: string;
    menu: string;
    close: string;
    language: string;
    switchToEnglish: string;
    switchToFrench: string;
    skip: string;
  };
  download: { idle: string; loading: string; fallback: string; other: string };
  hero: {
    eyebrow: string;
    headline: string;
    body: string;
    factsLabel: string;
    facts: string[];
    previewLabel: string;
    previewStatus: string;
    previewAlt: string;
    previewCaption: string;
    footerNote: string;
    footerLink: string;
  };
  route: { label: string; steps: RouteStep[] };
  workflow: { kicker: string; title: string; intro: string; cta: string; captureNote: string; steps: WorkflowStep[] };
  capabilities: { kicker: string; title: string; intro: string; items: Capability[] };
  privacy: {
    kicker: string;
    title: string;
    intro: string;
    localTitle: string;
    localBody: string;
    localCode: string;
    networkTitle: string;
    networkBody: string;
    networkCode: string;
    disclaimer: string;
  };
  contact: { kicker: string; title: string; body: string; download: string; feedback: string; ideas: string };
  footer: { statement: string; releases: string; source: string; platform: string };
};

const sharedSteps = {
  en: [
    { number: "01", verb: "Configure", title: "Build the preset you actually play.", body: "Choose champion priorities, bans, summoner spells, runes, and skins from one settings flow.", image: "assets/screenshots/settings-window.png", alt: "OTP LOL settings for automation, champions, spells, runes, and skins", width: 980, height: 720 },
    { number: "02", verb: "Choose", title: "Find the right champion without the scroll.", body: "Search by name or narrow the picker by role before assigning a champion to a preset.", image: "assets/screenshots/champ-select.png", alt: "Searchable OTP LOL champion picker with role filters", width: 780, height: 720 },
    { number: "03", verb: "Control", title: "See the active state at a glance.", body: "The compact window keeps client status, the active preset, runes, spells, and skins in reach.", image: "assets/screenshots/main-window.png", alt: "OTP LOL main window with local automation controls", width: 820, height: 760 },
  ],
  fr: [
    { number: "01", verb: "Configurer", title: "Construis le preset que tu joues vraiment.", body: "Choisis priorités de champions, bans, sorts, runes et skins depuis un seul parcours de réglages.", image: "assets/screenshots/settings-window.png", alt: "Réglages OTP LOL pour l’automatisation, les champions, sorts, runes et skins", width: 980, height: 720 },
    { number: "02", verb: "Choisir", title: "Trouve le bon champion sans le défilement.", body: "Recherche par nom ou filtre le sélecteur par rôle avant d’assigner un champion à un preset.", image: "assets/screenshots/champ-select.png", alt: "Sélecteur de champions OTP LOL avec recherche et filtres de rôle", width: 780, height: 720 },
    { number: "03", verb: "Contrôler", title: "Vois l’état actif d’un seul regard.", body: "La fenêtre compacte garde la connexion, le preset actif, les runes, les sorts et les skins à portée.", image: "assets/screenshots/main-window.png", alt: "Fenêtre principale OTP LOL avec les contrôles d’automatisation locale", width: 820, height: 760 },
  ],
} satisfies Record<Lang, WorkflowStep[]>;

export const content: Record<Lang, SiteCopy> = {
  en: {
    title: "OTP LOL — Local League companion",
    metaDescription: "OTP LOL is a focused local Windows companion for ready checks, champion select presets, runes, spells, skins, and post-game actions.",
    nav: { home: "OTP LOL home", label: "Primary navigation", workflow: "The route", capabilities: "What it does", privacy: "Local by design", contact: "Download", menu: "Menu", close: "Close", language: "Language", switchToEnglish: "Switch to English", switchToFrench: "Passer en français", skip: "Skip to content" },
    download: { idle: "Download for Windows", loading: "Finding the latest build…", fallback: "Opening GitHub releases…", other: "View every release" },
    hero: {
      eyebrow: "Local Windows assistant",
      headline: "Automate the clicks between queue and game.",
      body: "Configure your picks, bans, spells, runes, and skins once. OTP LOL handles the repetitive League Client actions you choose, while the important state stays visible.",
      factsLabel: "Product facts",
      facts: ["Windows only", "Local settings", "No tracking"],
      previewLabel: "Current desktop direction",
      previewStatus: "Local first",
      previewAlt: "Current OTP LOL desktop dashboard with Garen, champion presets, and client controls",
      previewCaption: "The desktop companion, rebuilt around the active state",
      footerNote: "A calm control surface for the queue between moments",
      footerLink: "See how it works",
    },
    route: {
      label: "The route",
      steps: [
        { label: "Configure", body: "Your choices" },
        { label: "Queue", body: "The client finds a game" },
        { label: "Play", body: "The routine stays out of the way" },
      ],
    },
    workflow: {
      kicker: "01 / The route",
      title: "One setup. Every queue.",
      intro: "The website follows the same logic as the app: make the decision once, then keep the next action obvious.",
      cta: "Get the app",
      captureNote: "Recent PySide6 desktop capture",
      steps: sharedSteps.en,
    },
    capabilities: {
      kicker: "02 / The useful parts",
      title: "Nothing hidden behind a dashboard wall.",
      intro: "No invented speed claims, no mystery automation. These are the local actions OTP LOL is built to make easier.",
      items: [
        { label: "Queue", title: "Auto Accept", body: "Accept the ready check when the League Client finds a match." },
        { label: "Draft", title: "Picks, bans & spells", body: "Keep ordered champion choices, bans, and summoner spells ready for champion select." },
        { label: "Loadout", title: "Runes & skins", body: "Apply configured rune pages and fixed or randomized skin choices." },
        { label: "Lobby", title: "Optional Play Again", body: "Return to the lobby after a game when the option is enabled." },
      ],
    },
    privacy: {
      kicker: "03 / Local by design",
      title: "Your setup stays yours.",
      intro: "OTP LOL has no hosted profile or required account. The desktop app connects only to the local client and the public game data it needs.",
      localTitle: "What stays local",
      localBody: "Your configuration, presets, and useful history stay on your Windows machine. The website contains no advertising scripts or tracking pixels.",
      localCode: "CONFIG / LOCAL MACHINE",
      networkTitle: "What connects",
      networkBody: "The app uses Riot Data Dragon for public League metadata and the local League Client Update interface for runtime events. Downloads and source code are served by GitHub.",
      networkCode: "DATA DRAGON + LOCAL LCU",
      disclaimer: "OTP LOL is not endorsed by Riot Games. It is a local Windows assistant for your own setup.",
    },
    contact: { kicker: "04 / Ready when you are", title: "Set it up once. Keep playing your way.", body: "Download the current Windows build, or send a concrete idea to the person building the tool.", download: "Download the latest build", feedback: "Send feedback", ideas: "Share an idea" },
    footer: { statement: "Configure once. Keep control.", releases: "GitHub releases", source: "Source code", platform: "Windows only" },
  },
  fr: {
    title: "OTP LOL — Assistant League local",
    metaDescription: "OTP LOL est un assistant Windows local et ciblé pour les ready checks, presets de champion select, runes, sorts, skins et actions d’après-partie.",
    nav: { home: "Accueil OTP LOL", label: "Navigation principale", workflow: "Le parcours", capabilities: "Ce que fait l’app", privacy: "Local par conception", contact: "Télécharger", menu: "Menu", close: "Fermer", language: "Langue", switchToEnglish: "Switch to English", switchToFrench: "Passer en français", skip: "Aller au contenu" },
    download: { idle: "Télécharger pour Windows", loading: "Recherche de la dernière version…", fallback: "Ouverture des releases GitHub…", other: "Voir toutes les versions" },
    hero: {
      eyebrow: "Assistant Windows local",
      headline: "Automatise les clics entre la file et la partie.",
      body: "Configure une fois tes picks, bans, sorts, runes et skins. OTP LOL gère les actions répétitives du client League que tu choisis, tout en gardant l’état important visible.",
      factsLabel: "Faits produit",
      facts: ["Windows uniquement", "Réglages locaux", "Sans tracking"],
      previewLabel: "Nouvelle direction desktop",
      previewStatus: "Local d’abord",
      previewAlt: "Dashboard desktop actuel d’OTP LOL avec Garen, presets de champions et contrôles client",
      previewCaption: "Le compagnon desktop, recentré sur l’état actif",
      footerNote: "Une surface de contrôle calme entre deux moments de file",
      footerLink: "Voir le fonctionnement",
    },
    route: {
      label: "Le parcours",
      steps: [
        { label: "Configurer", body: "Tes choix" },
        { label: "Lancer la file", body: "Le client trouve une partie" },
        { label: "Jouer", body: "La routine reste discrète" },
      ],
    },
    workflow: {
      kicker: "01 / Le parcours",
      title: "Un réglage. Chaque partie.",
      intro: "Le site suit la même logique que l’app : tu décides une fois, puis l’action suivante reste évidente.",
      cta: "Obtenir l’app",
      captureNote: "Capture récente du desktop PySide6",
      steps: sharedSteps.fr,
    },
    capabilities: {
      kicker: "02 / Les fonctions utiles",
      title: "Rien de caché derrière un mur de dashboard.",
      intro: "Pas de promesse de vitesse inventée, pas d’automatisation mystérieuse. Voici les actions locales que OTP LOL rend plus simples.",
      items: [
        { label: "File", title: "Auto Accept", body: "Accepte le ready check lorsque le client League trouve une partie." },
        { label: "Draft", title: "Picks, bans & sorts", body: "Garde tes choix ordonnés de champions, bans et sorts prêts pour la champion select." },
        { label: "Loadout", title: "Runes & skins", body: "Applique les pages de runes et les choix de skins fixes ou aléatoires configurés." },
        { label: "Lobby", title: "Play Again optionnel", body: "Reviens au lobby après une partie lorsque l’option est activée." },
      ],
    },
    privacy: {
      kicker: "03 / Local par conception",
      title: "Ton setup reste à toi.",
      intro: "OTP LOL n’a pas de profil hébergé ni de compte obligatoire. L’app se connecte seulement au client local et aux données publiques dont elle a besoin.",
      localTitle: "Ce qui reste local",
      localBody: "Ta configuration, tes presets et ton historique utile restent sur ta machine Windows. Le site ne contient ni publicité ni pixel de tracking.",
      localCode: "CONFIG / MACHINE LOCALE",
      networkTitle: "Ce qui se connecte",
      networkBody: "L’app utilise Riot Data Dragon pour les métadonnées publiques de League et l’interface locale League Client Update pour les événements runtime. Les téléchargements et le code source sont servis par GitHub.",
      networkCode: "DATA DRAGON + LCU LOCAL",
      disclaimer: "OTP LOL n’est pas approuvé par Riot Games. C’est un assistant Windows local pour ton propre setup.",
    },
    contact: { kicker: "04 / Prêt quand tu l’es", title: "Configure une fois. Continue à jouer comme tu veux.", body: "Télécharge la version Windows actuelle ou envoie une idée concrète à la personne qui développe l’outil.", download: "Télécharger la dernière version", feedback: "Envoyer un retour", ideas: "Partager une idée" },
    footer: { statement: "Configure une fois. Garde le contrôle.", releases: "Releases GitHub", source: "Code source", platform: "Windows uniquement" },
  },
};
