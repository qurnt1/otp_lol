export type Locale = "en" | "fr";

export interface ScreenshotCopy {
  id: "settings" | "statistics";
  label: string;
  title: string;
  alt: string;
  note: string;
}

export interface SiteCopy {
  documentTitle: string;
  metaDescription: string;
  skipToContent: string;
  home: string;
  navigation: string;
  nav: { workflow: string; app: string; installation: string; contact: string };
  languageSelector: string;
  switchToEnglish: string;
  switchToFrench: string;
  downloads: string;
  hero: {
    eyebrow: string;
    title: [string, string];
    lead: string;
    download: string;
    seeApp: string;
    requirements: string;
    imageAlt: string;
    caption: string;
    captionNote: string;
  };
  workflow: {
    eyebrow: string;
    title: [string, string];
    intro: string;
    steps: { title: string; body: string }[];
  };
  showcase: {
    eyebrow: string;
    title: [string, string];
    intro: string;
    selector: string;
    enlarge: string;
    screenshots: ScreenshotCopy[];
  };
  features: {
    eyebrow: string;
    title: [string, string];
    championSelect: string;
    championSelectBody: string;
    championSelectItems: [string, string, string];
    stats: string;
    statsBody: string;
    profile: string;
    live: string;
  };
  installation: {
    eyebrow: string;
    title: string;
    intro: string;
    github: string;
    start: string;
    steps: [string, string, string];
    downloads: string;
    dataNote: string;
  };
  faq: {
    eyebrow: string;
    title: string;
    items: { question: string; answer: string }[];
  };
  contact: { eyebrow: string; title: string; body: string; email: string };
  closing: { eyebrow: string; title: [string, string]; download: string };
  footer: { note: string; downloads: string; disclaimer: string; backToTop: string };
  dialog: { fit: string; actual: string; close: string };
}

export const siteCopy: Record<Locale, SiteCopy> = {
  en: {
    documentTitle: "OTP LOL — Your picks, ready before champion select",
    metaDescription: "Set your champion priorities, spells, runes, and skins. OTP LOL applies only the automations you enable on your Windows PC.",
    skipToContent: "Skip to content",
    home: "OTP LOL home",
    navigation: "Main navigation",
    nav: { workflow: "How it works", app: "The app", installation: "Installation", contact: "Contact" },
    languageSelector: "Language selector",
    switchToEnglish: "English",
    switchToFrench: "Français",
    downloads: "Downloads",
    hero: {
      eyebrow: "A League companion for Windows",
      title: ["Your picks, ready", "before champion select."],
      lead: "Set up your champion priorities, spells, runes, and skins. OTP LOL applies only the automations you enable, on your PC.",
      download: "Download for Windows",
      seeApp: "Explore the app",
      requirements: "You need Windows, the League client on the same computer, and the Microsoft Edge WebView2 Runtime.",
      imageAlt: "OTP LOL dashboard demo with three champions and their configured skins; the League client is disconnected.",
      caption: "Dashboard",
      captionNote: "Demo presets · client disconnected",
    },
    workflow: {
      eyebrow: "Your routine, your way",
      title: ["Set it up. Make your picks.", "League keeps going."],
      intro: "OTP LOL prepares actions around your game. You stay in control of what is enabled.",
      steps: [
        { title: "Set up your presets", body: "Rank up to three pick priorities. Configure a ban, spells, runes, and a fixed skin or a random pool." },
        { title: "Enable the actions you want", body: "Auto-Accept waits for the ready check. Auto-Pick moves on when a champion is unavailable or banned. Each automation is configured separately." },
        { title: "Queue in League", body: "OTP LOL follows the local client. After a game, returning to the lobby can be enabled when League allows it." },
      ],
    },
    showcase: {
      eyebrow: "Inside the app",
      title: ["Your settings are visible.", "Your choices stay yours."],
      intro: "Explore the preparation, settings, and statistics screens.",
      selector: "Choose an app screenshot",
      enlarge: "Enlarge screenshot",
      screenshots: [
        { id: "settings", label: "Settings", title: "Enable what suits you", alt: "OTP LOL Advanced settings page showing local files, diagnostics, and configuration actions.", note: "Advanced settings preview. Automations are disabled on first launch." },
        { id: "statistics", label: "Statistics", title: "Choose your providers", alt: "OTP LOL Statistics page showing available providers with no account configured.", note: "Preview with no account configured. Profiles and match data come from the selected third-party provider." },
      ],
    },
    features: {
      eyebrow: "Made for the moments around each game",
      title: ["A visible routine.", "Your strategy stays yours."],
      championSelect: "In champion select",
      championSelectBody: "Set pick priorities, a ban, and preset details. If a champion cannot be picked, OTP LOL moves to the next configured choice.",
      championSelectItems: ["Spells and rune pages", "Fixed skin or random pool", "Automations off on first launch"],
      stats: "For your stats",
      statsBody: "Open your account profile or live match stats with the provider you choose. These pages are provided by third-party services.",
      profile: "Profile",
      live: "Live",
    },
    installation: {
      eyebrow: "On your computer",
      title: "Your settings stay with you.",
      intro: "OTP LOL runs locally alongside the League client on your PC. Your settings and match history stay on your computer. No OTP LOL account or hosted player profile is required.",
      github: "View the project on GitHub",
      start: "Get started",
      steps: ["Download the installer from the releases page.", "Install WebView2 if prompted, then restart the installer.", "Open League and OTP LOL. Set up your presets before enabling an automation."],
      downloads: "Open downloads",
      dataNote: "The app may contact League metadata and update services. When you open a profile, the selected provider receives the corresponding link.",
    },
    faq: {
      eyebrow: "Before you start",
      title: "Practical questions.",
      items: [
        { question: "Does OTP LOL play the game for me?", answer: "No. It does not play the match or choose your strategy. It carries out the client actions you configured during the phases where League allows them." },
        { question: "Are automations enabled by default?", answer: "No. They are disabled on first launch. Set up your presets, then enable each automation separately." },
        { question: "What do I need to install it?", answer: "A Windows PC, the League client installed on that PC, and the Microsoft Edge WebView2 Runtime. If WebView2 is missing, install it from the Microsoft page that opens, then restart the installer." },
        { question: "Where do the statistics come from?", answer: "Profile and match data are provided by the third-party service you select. OTP LOL prepares the link and opens it in a dedicated window, with your browser as a fallback." },
      ],
    },
    contact: { eyebrow: "Get in touch", title: "Have feedback or an idea?", body: "Send a note directly to the developer.", email: "Email chbtquentin@gmail.com" },
    closing: { eyebrow: "OTP LOL for Windows", title: ["Set up your routine.", "Then queue up."], download: "Get the latest version" },
    footer: { note: "Independent project for League of Legends.", downloads: "Downloads", disclaimer: "OTP LOL is not affiliated with or endorsed by Riot Games. League of Legends and its marks are owned by Riot Games.", backToTop: "OTP LOL, back to top" },
    dialog: { fit: "Fit screenshot to window", actual: "Show screenshot at actual size", close: "Close enlarged screenshot" },
  },
  fr: {
    documentTitle: "OTP LOL — Tes choix prêts avant la sélection",
    metaDescription: "Prépare tes priorités, tes sorts, tes runes et tes skins. OTP LOL applique les automatismes que tu choisis, sur ton PC Windows.",
    skipToContent: "Aller au contenu",
    home: "OTP LOL, accueil",
    navigation: "Navigation principale",
    nav: { workflow: "Fonctionnement", app: "L’application", installation: "Installation", contact: "Contact" },
    languageSelector: "Sélecteur de langue",
    switchToEnglish: "English",
    switchToFrench: "Français",
    downloads: "Téléchargements",
    hero: {
      eyebrow: "Compagnon League pour Windows",
      title: ["Tes choix prêts avant", "la sélection."],
      lead: "Prépare tes priorités, tes sorts, tes runes et tes skins. OTP LOL applique uniquement les automatismes que tu actives, sur ton PC.",
      download: "Télécharger pour Windows",
      seeApp: "Voir l’application",
      requirements: "Il te faut Windows, le client League sur le même ordinateur et le runtime Microsoft Edge WebView2.",
      imageAlt: "Capture de démonstration du tableau de bord OTP LOL avec trois champions et leurs skins configurés, client League déconnecté.",
      caption: "Tableau de bord",
      captionNote: "Presets de démonstration · client déconnecté",
    },
    workflow: {
      eyebrow: "La routine, à ta façon",
      title: ["Tu règles. Tu choisis.", "League continue."],
      intro: "OTP LOL prépare les actions autour de la partie. Tu gardes le contrôle de ce qui s’active.",
      steps: [
        { title: "Prépare tes presets", body: "Classe jusqu’à trois picks prioritaires. Configure le ban, les sorts, les runes et un skin fixe ou tiré d’un pool." },
        { title: "Active les actions voulues", body: "Auto-Accept attend le ready-check. Auto-Pick passe aux champions indisponibles ou bannis. Chaque automatisme se règle séparément." },
        { title: "Lance ta file dans League", body: "OTP LOL suit le client local. Après la partie, le retour au lobby peut être activé lorsque League le permet." },
      ],
    },
    showcase: {
      eyebrow: "L’application, en vrai",
      title: ["Les réglages se voient.", "Les choix restent les tiens."],
      intro: "Parcours les écrans de préparation, de réglages et de statistiques.",
      selector: "Choisir une capture de l’application",
      enlarge: "Agrandir la capture",
      screenshots: [
        { id: "settings", label: "Réglages", title: "Active ce qui te convient", alt: "Capture de la page Avancé des réglages OTP LOL, avec les fichiers locaux, les diagnostics et les actions de configuration.", note: "Aperçu de la page Avancé. Les automatismes restent désactivés au premier lancement." },
        { id: "statistics", label: "Statistiques", title: "Choisis tes fournisseurs", alt: "Capture de la page Statistiques OTP LOL avec les fournisseurs disponibles et aucun compte configuré.", note: "Aperçu sans compte configuré. Les profils et données de partie viennent du fournisseur tiers choisi." },
      ],
    },
    features: {
      eyebrow: "Précis quand League en a besoin",
      title: ["Une routine visible.", "Aucune stratégie à ta place."],
      championSelect: "Dans la sélection",
      championSelectBody: "Choisis tes picks par ordre de priorité, ton ban et les éléments de ton preset. Si un champion ne peut pas être pris, OTP LOL passe au suivant configuré.",
      championSelectItems: ["Sorts et pages de runes", "Skin fixe ou pool aléatoire", "Automatismes désactivés au premier lancement"],
      stats: "Pour tes statistiques",
      statsBody: "Ouvre le profil de ton compte ou les statistiques de la partie avec le fournisseur que tu choisis. Ces pages viennent de services tiers.",
      profile: "Profil",
      live: "En direct",
    },
    installation: {
      eyebrow: "Sur ton ordinateur",
      title: "Tes réglages restent chez toi.",
      intro: "OTP LOL fonctionne en local auprès du client League installé sur le même PC. Tes réglages et ton historique restent sur ton ordinateur. Il ne demande pas de compte OTP LOL et n’héberge pas de profil joueur.",
      github: "Voir le projet sur GitHub",
      start: "Pour commencer",
      steps: ["Télécharge l’installateur depuis la page des releases.", "Installe WebView2 si ton PC te le demande, puis relance l’installateur.", "Ouvre League et OTP LOL. Configure tes presets avant d’activer une automatisation."],
      downloads: "Ouvrir les téléchargements",
      dataNote: "L’application peut contacter les services de métadonnées League et de mise à jour. Quand tu ouvres un profil, le fournisseur choisi reçoit le lien correspondant.",
    },
    faq: {
      eyebrow: "Avant de te lancer",
      title: "Questions pratiques.",
      items: [
        { question: "OTP LOL joue-t-il à ma place ?", answer: "Non. Il ne joue pas la partie et ne choisit pas ta stratégie. Il applique les actions de client que tu as configurées, dans les phases où League les autorise." },
        { question: "Les automatismes sont-ils activés d’avance ?", answer: "Non. Ils sont désactivés au premier lancement. Tu peux configurer les presets, puis activer chaque automatisme séparément." },
        { question: "De quoi ai-je besoin pour l’installer ?", answer: "D’un PC Windows, du client League installé sur ce même PC et du runtime Microsoft Edge WebView2. Si WebView2 manque, installe-le depuis la page Microsoft qui s’ouvre, puis relance l’installateur." },
        { question: "D’où viennent les statistiques ?", answer: "Les données de profil et de partie sont fournies par le service tiers que tu sélectionnes. OTP LOL prépare le lien et l’ouvre dans une fenêtre dédiée, avec le navigateur comme solution de repli." },
      ],
    },
    contact: { eyebrow: "Me contacter", title: "Un retour ou une idée ?", body: "Écris directement au développeur.", email: "Écrire à chbtquentin@gmail.com" },
    closing: { eyebrow: "OTP LOL pour Windows", title: ["Configure ta routine.", "Puis lance ta partie."], download: "Voir la dernière version" },
    footer: { note: "Projet indépendant pour League of Legends.", downloads: "Téléchargements", disclaimer: "OTP LOL n’est ni affilié à Riot Games ni approuvé par Riot Games. League of Legends et ses marques appartiennent à Riot Games.", backToTop: "OTP LOL, retour en haut" },
    dialog: { fit: "Ajuster la capture à la fenêtre", actual: "Afficher la capture à sa taille réelle", close: "Fermer la capture agrandie" },
  },
};
