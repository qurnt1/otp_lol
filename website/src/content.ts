export type Lang = "en" | "fr";

type WorkflowStep = { number: string; verb: string; title: string; body: string; image: string; alt: string };
type Capability = { label: string; title: string; body: string };

export type SiteCopy = {
  metaDescription: string;
  nav: { home: string; label: string; workflow: string; capabilities: string; privacy: string; contact: string; menu: string; close: string; language: string; switchToEnglish: string; switchToFrench: string };
  download: { idle: string; loading: string; fallback: string; other: string };
  hero: { utility: string; headline: string; body: string; facts: string[]; sequenceLabel: string; sequence: { title: string; body: string }[] };
  workflow: { title: string; intro: string; captureNote: string; steps: WorkflowStep[] };
  capabilities: { title: string; intro: string; items: Capability[] };
  privacy: { title: string; intro: string; localTitle: string; localBody: string; networkTitle: string; networkBody: string; disclaimer: string };
  contact: { title: string; body: string; feedback: string; ideas: string; source: string };
  footer: { statement: string; releases: string; source: string; platform: string };
};

export const content: Record<Lang, SiteCopy> = {
  en: {
    metaDescription: "OTP LOL is a local Windows assistant for ready checks, champion select presets, skins, runes, and post-game actions.",
    nav: { home: "OTP LOL home", label: "Primary navigation", workflow: "Workflow", capabilities: "Capabilities", privacy: "Privacy", contact: "Contact", menu: "Menu", close: "Close", language: "Language", switchToEnglish: "Switch to English", switchToFrench: "Passer en français" },
    download: { idle: "Download for Windows", loading: "Finding the latest build…", fallback: "Opening GitHub releases…", other: "View every release" },
    hero: {
      utility: "Local Windows assistant",
      headline: "Automate the clicks between queue and game.",
      body: "Configure picks, bans, spells, runes, and skins once. OTP LOL handles the repetitive League Client actions you choose, from ready check to the next lobby.",
      facts: ["Windows only", "Local settings", "No ads"],
      sequenceLabel: "What it can handle",
      sequence: [
        { title: "Ready check", body: "Accept automatically when a match is found." },
        { title: "Champion select", body: "Apply your configured pick, ban, spell, rune, and skin choices." },
        { title: "Post-game", body: "Optionally return to the lobby after the game." },
      ],
    },
    workflow: {
      title: "Set the route once. Keep every stop visible.",
      intro: "OTP LOL stays explicit about what is configured and what the local League Client is doing.",
      captureNote: "PyQt6 desktop preview",
      steps: [
        { number: "01", verb: "Configure", title: "Build the preset you actually play.", body: "Choose champion priorities, bans, summoner spells, runes, and skins for each ordered preset from one settings flow.", image: "assets/screenshots/settings-window.png", alt: "OTP LOL settings for automation, champions, spells, runes, and skins" },
        { number: "02", verb: "Choose", title: "Find the right champion without endless scrolling.", body: "Search by name or narrow the responsive picker by Top, Jungle, Mid, ADC, or Support before assigning a preset.", image: "assets/screenshots/champ-select.png", alt: "Searchable PyQt6 champion picker with role filters" },
        { number: "03", verb: "Control", title: "See the active state without digging.", body: "The compact main window keeps connection and automation controls available, including the optional return-to-lobby action.", image: "assets/screenshots/main-window.png", alt: "OTP LOL main window with local automation controls" },
      ],
    },
    capabilities: {
      title: "The useful parts, stated plainly.",
      intro: "No invented speed claims and no mystery automation. These are the actions currently represented in the product.",
      items: [
        { label: "Queue", title: "Auto Accept", body: "Accept the ready check automatically when the League Client finds a match." },
        { label: "Draft", title: "Pick, ban, and spell presets", body: "Keep ordered champion choices, bans, and summoner spells ready for champion select." },
        { label: "Loadout", title: "Runes and skins", body: "Apply configured rune pages and fixed or randomized skin choices." },
        { label: "Lobby", title: "Optional Play Again", body: "Return to the lobby after a game when the option is enabled." },
      ],
    },
    privacy: {
      title: "Local by design. Honest about the network.",
      intro: "OTP LOL does not need its own account or hosted profile, but local automation still talks to the services required for the product to work.",
      localTitle: "What stays local",
      localBody: "Your OTP LOL configuration stays on your Windows machine. The site contains no advertising scripts or tracking pixels.",
      networkTitle: "What connects",
      networkBody: "The desktop app uses Riot Data Dragon for public League metadata and the local League Client Update interface for runtime events. Downloads and source code are served by GitHub.",
      disclaimer: "OTP LOL is not endorsed by Riot Games. It is a local Windows assistant for your own setup.",
    },
    contact: { title: "Found a rough edge? Send it to the person building it.", body: "OTP LOL is built by a data science student who wanted this tool for everyday play. Feedback and concrete ideas are welcome.", feedback: "Send feedback", ideas: "Share an idea", source: "Read the source" },
    footer: { statement: "Configure once. Keep control.", releases: "GitHub releases", source: "Source code", platform: "Windows only" },
  },
  fr: {
    metaDescription: "OTP LOL est un assistant Windows local pour les ready checks, les presets de champion select, les skins, les runes et l’après-partie.",
    nav: { home: "Accueil OTP LOL", label: "Navigation principale", workflow: "Parcours", capabilities: "Fonctions", privacy: "Vie privée", contact: "Contact", menu: "Menu", close: "Fermer", language: "Langue", switchToEnglish: "Switch to English", switchToFrench: "Passer en français" },
    download: { idle: "Télécharger pour Windows", loading: "Recherche de la dernière version…", fallback: "Ouverture des releases GitHub…", other: "Voir toutes les versions" },
    hero: {
      utility: "Assistant Windows local",
      headline: "Automatise les clics entre la file et la partie.",
      body: "Configure une fois tes picks, bans, sorts, runes et skins. OTP LOL gère les actions répétitives du client League que tu choisis, du ready check au prochain lobby.",
      facts: ["Windows uniquement", "Réglages locaux", "Sans publicité"],
      sequenceLabel: "Ce qu’il peut gérer",
      sequence: [
        { title: "Ready check", body: "Accepter automatiquement lorsqu’une partie est trouvée." },
        { title: "Champion select", body: "Appliquer tes choix de pick, ban, sorts, runes et skins." },
        { title: "Après-partie", body: "Revenir au lobby automatiquement si l’option est activée." },
      ],
    },
    workflow: {
      title: "Trace le parcours une fois. Garde chaque étape visible.",
      intro: "OTP LOL reste explicite sur ce qui est configuré et sur ce que fait le client League local.",
      captureNote: "Aperçu desktop PyQt6",
      steps: [
        { number: "01", verb: "Configurer", title: "Construis le preset que tu joues vraiment.", body: "Choisis les priorités de champions, bans, sorts d’invocateur, runes et skins pour chaque preset ordonné depuis un seul parcours de réglages.", image: "assets/screenshots/settings-window.png", alt: "Réglages OTP LOL pour l’automatisation, les champions, sorts, runes et skins" },
        { number: "02", verb: "Choisir", title: "Trouve le bon champion sans défilement interminable.", body: "Recherche par nom ou filtre la grille responsive par Top, Jungle, Mid, ADC ou Support avant d’assigner un preset.", image: "assets/screenshots/champ-select.png", alt: "Sélecteur de champions PyQt6 avec recherche et filtres de rôle" },
        { number: "03", verb: "Contrôler", title: "Vois l’état actif sans chercher.", body: "La fenêtre principale compacte garde la connexion et les contrôles d’automatisation accessibles, y compris le retour optionnel au lobby.", image: "assets/screenshots/main-window.png", alt: "Fenêtre principale OTP LOL avec les contrôles d’automatisation locale" },
      ],
    },
    capabilities: {
      title: "Les fonctions utiles, sans détour.",
      intro: "Pas de promesse de vitesse inventée et pas d’automatisation mystérieuse. Voici les actions représentées dans le produit actuel.",
      items: [
        { label: "File", title: "Auto Accept", body: "Accepte automatiquement le ready check lorsque le client League trouve une partie." },
        { label: "Draft", title: "Presets de picks, bans et sorts", body: "Garde tes choix ordonnés de champions, bans et sorts prêts pour la champion select." },
        { label: "Équipement", title: "Runes et skins", body: "Applique les pages de runes et les choix de skins fixes ou aléatoires configurés." },
        { label: "Lobby", title: "Play Again optionnel", body: "Reviens au lobby après une partie lorsque l’option est activée." },
      ],
    },
    privacy: {
      title: "Local par conception. Transparent sur le réseau.",
      intro: "OTP LOL n’a pas besoin de compte ou de profil hébergé, mais l’automatisation locale communique avec les services nécessaires au produit.",
      localTitle: "Ce qui reste local",
      localBody: "Ta configuration OTP LOL reste sur ta machine Windows. Le site ne contient ni script publicitaire ni pixel de tracking.",
      networkTitle: "Ce qui se connecte",
      networkBody: "L’application utilise Riot Data Dragon pour les métadonnées publiques de League et l’interface locale League Client Update pour les événements. Les téléchargements et le code source sont servis par GitHub.",
      disclaimer: "OTP LOL n’est pas approuvé par Riot Games. C’est un assistant Windows local pour ton propre setup.",
    },
    contact: { title: "Tu as trouvé un point faible ? Parle directement à la personne qui le développe.", body: "OTP LOL est développé par un étudiant en data science qui voulait cet outil pour jouer au quotidien. Les retours et idées concrètes sont les bienvenus.", feedback: "Envoyer un retour", ideas: "Partager une idée", source: "Lire le code source" },
    footer: { statement: "Configure une fois. Garde le contrôle.", releases: "Releases GitHub", source: "Code source", platform: "Windows uniquement" },
  },
};
