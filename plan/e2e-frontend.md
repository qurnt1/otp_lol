# Plan d’expansion E2E React/TypeScript par action utilisateur

## Périmètre et état vérifié

Plan commencé par un audit read-only de `frontend/src` et `frontend/e2e`, puis étendu sur demande à des specs Playwright uniquement. Les composants produit et workflows restent inchangés. Le dernier résultat global historique consigné avant cette expansion était 189/189; ce n’est pas un résultat actuel.

Le navigateur Playwright utilise le vrai bundle et FastAPI local, un profil temporaire, le WebSocket applicatif et un faux client LCU TLS/WSS (`frontend/e2e/helpers.ts`). Les actions E2E proposées gardent le vrai geste depuis l’interface. Les lectures API après action servent d’oracle de persistance; elles ne remplacent pas le geste. Les scénarios d’erreur peuvent injecter une panne HTTP au navigateur, mais doivent l’indiquer comme panne UI simulée.

Depuis `frontend/`, lancer les commandes ciblées avec `npx playwright test --workers=1 --grep '<ID>'`. Le passage des options via `npm run test:e2e -- ...` n’a pas été fiable dans le PowerShell utilisé; les reruns probants passent les options directement à Playwright. Le harness crée un profil E2E temporaire et démarre le vrai backend. Les specs existantes restent les cibles lorsque cela garde les responsabilités compréhensibles.

Priorités: **P0** protège d’une action LCU incorrecte ou d’une perte de configuration; **P1** couvre un parcours de première importance ou un retour d’erreur; **P2** couvre une action secondaire ou un chemin redondant.

## Couverture actuelle à conserver

Ces parcours ont déjà des interactions UI et des assertions visibles ou persistées dans les specs présentes. Ne pas recréer des tests supplémentaires pour les mêmes scénarios sans changement de comportement:

- Navigation principale, activation clavier, liens rapides, deep-links, hash invalide, Back/Forward de quelques routes, slots `pick_3` et ban: `navigation.spec.ts`.
- Dashboard, état LCU synthétique, automations, ouverture/fermeture des éditeurs, focus, recherche/vide/retry, ban, sorts et runes; choix de skin fixe, pool aléatoire, filtres possédés, mode Aucun et erreur d’asset: `dashboard-connected.spec.ts`, `presets.spec.ts`, `lcu-automation.spec.ts`, `prepick-transition.spec.ts`. Avant cette expansion, le filtre de rôle cliquait Top/Mid seulement; les six filtres sont vérifiés par FE-PICK-ROLE-01.
- Premier lancement et sauvegarde d’un preset à travers reload/restart: `first-launch.spec.ts`.
- Paramètres généraux, six interrupteurs d’automatisation, compte manuel et invalidité Riot ID, compte détecté, copie/oubli avec confirmation, raccourcis UI, thème, import/export/reset et presets d’exemple: `settings.spec.ts`, `settings-manual-hotkeys.spec.ts`.
- Identité absente/enregistrée/connectée, choix de fournisseurs, refresh, URLs attendues, échec/réessai du bridge simulé et navigation de retour au compte: `statistics.spec.ts`. Le CTA vers Compte est maintenant cliqué depuis Statistiques et En direct.
- Catégories History créées par de vrais événements LCU synthétiques, recherche sur message/détails, mise à jour live, effacement/annulation/erreur: `history.spec.ts`, `history-live-actions.spec.ts`.
- Chargement/réessai Diagnostics, checks allowlist, filtres et recherche (dont WebView vide et erreur LCU réelle synthétique), JSON, copie et export: `diagnostics.spec.ts`.
- Vérification réseau en attente/offline, image locale, navigation hors ligne, Retry, warning et reprise: `network-gate.spec.ts`.
- Chargement d’assets, overflow et mesures de fenêtre déjà couvertes par `game-data-refresh.spec.ts` et `window-layout.spec.ts`.

## Scénarios à ajouter ou compléter

### FE-DASH-LOAD-01 — Charger le Dashboard après échec initial du bootstrap

- **Précondition:** les deux lectures initiales de `/api/bootstrap` échouent, puis le retry manuel appelle le vrai FastAPI.
- **Geste:** ouvrir le hash Dashboard, cliquer `Réessayer`, constater le Dashboard, puis consulter les données de Settings.
- **Assertions visibles:** l’erreur de démarrage et le bouton de retry sont visibles; après reprise, les trois cartes et le champion connu du profil apparaissent.
- **Persistance / intégration:** le bootstrap récupéré et `/api/presets` proviennent du vrai FastAPI; le profil est temporaire.
- **Preuve actuelle:** le test existant `settings.spec.ts:26-63` vérifiait bootstrap 503 → retry depuis Settings. Il porte maintenant FE-DASH-LOAD-01 et vérifie le Dashboard après reprise.
- **Spec:** `frontend/e2e/settings.spec.ts`.
- **Priorité:** P1.
- **Commande:** `npx playwright test --workers=1 --grep 'FE-DASH-LOAD-01'`.

**Limite confirmée:** l’erreur propre à `DashboardPage` sur `GET /api/presets` n’est pas atteignable après un bootstrap réussi normal, car `App.tsx:100-101` hydrate le cache React Query avec `bootstrap.data.presets`. Ne pas simuler un bootstrap partiel sans contrat produit/API qui rende cet état valide. Le retry de démarrage est couvert ci-dessus.

### FE-DASH-MANAGE-01 — Lien « Gérer » depuis les automatisations

- **Précondition:** Dashboard chargé et bloc Automatisations visible.
- **Geste:** cliquer `Gérer` dans l’en-tête du bloc.
- **Assertions visibles:** le clic atteint Settings; le titre affiché est Général et la route actuelle est `#settings`.
- **Persistance / intégration:** aucune mutation attendue.
- **À confirmer, hypothèse UX:** le lien rendu par `AutomationBar.tsx:19` a `href="#settings"`. Le vrai clic Playwright atteint `#settings` et rend Général. La destination produit attendue n’est pas confirmée; cette route observée n’est pas classée comme bug certain.
- **Spec visé:** `frontend/e2e/navigation.spec.ts`.
- **Priorité:** P1, à cause du parcours direct de gestion d’une automation.
- **Commande:** `npx playwright test --workers=1 --grep 'FE-DASH-MANAGE-01'`.

### FE-PICK-KEY-01 — Choisir un champion au clavier

- **Précondition:** ouvrir un slot depuis le Dashboard; catalogue de champions chargé; un champion libre correspond à la recherche.
- **Geste:** saisir un nom, parcourir avec Tab jusqu’à l’option correspondante et appuyer sur Entrée. Le test identifie le stop cible par son focus effectif et ne suppose pas un nombre fixe de Tab.
- **Assertions visibles:** le picker enfant se ferme, le champion apparaît dans le bouton du preset, le focus reste gérable dans le dialogue parent.
- **Persistance / intégration:** attendre `PUT /api/presets/{slot}` 200 et relire ce slot via le vrai FastAPI; après fermeture/rechargement, la carte affiche le même champion.
- **Preuve actuelle:** `presets.spec.ts:67` ouvre la carte au clavier et restaure le focus, mais les sélections de champion sont par clic (`:142-158,191-216`). Les options sont des boutons `role="option"` (`ChampionPicker.tsx:17-18`), donc le geste clavier est disponible et testable.
- **Spec visé:** `frontend/e2e/presets.spec.ts`.
- **Priorité:** P1.
- **Commande:** `npx playwright test --workers=1 --grep 'FE-PICK-KEY-01'`.

### FE-PICK-ROLE-01 — Vérifier les six filtres de poste du picker

- **Précondition:** le catalogue Data Dragon synthétique du harness est chargé; slot 2 libre.
- **Geste:** cliquer Tous, Top, Jungle, Mid, ADC et Support dans le groupe des filtres.
- **Assertions visibles:** `aria-pressed` suit chaque clic; la liste visible correspond exactement aux rôles de `/api/champions`, l’état vide est visible lorsqu’aucun champion correspond, et les six ensembles de la fixture sont distincts.
- **Persistance / intégration:** aucune mutation. Le vrai endpoint FastAPI sert d’oracle et l’action reste un clic utilisateur.
- **Challenge indépendant:** le red-team a relevé que l’ancien test ne cliquait que Top/Mid. Après ce challenge, le parcours des six filtres a été validé contre le catalogue du harness. Cela prouve six résultats distincts pour la fixture actuelle de six champions, pas les mêmes cardinalités dans chaque version complète de Data Dragon.
- **Spec:** `frontend/e2e/presets.spec.ts`.
- **Priorité:** P1.
- **Commande:** `npx playwright test --workers=1 --grep 'FE-PICK-ROLE-01'`.

### FE-PRESET-SKIN-MODE-01 — Basculer entre les trois modes de skin

- **Précondition:** slot configuré avec skin fixe.
- **Geste:** choisir `Aucun`, puis `Fixe`, puis `Aléatoire`.
- **Assertions visibles:** la radio active suit chaque clic; le picker est désactivé sous `Aucun` et actif sous Fixe/Aléatoire.
- **Persistance / intégration:** après chaque clic, relire seulement `skin_mode` via `/api/presets/pick_1`. Le test ne suppose ni conservation ni effacement des valeurs de skin précédentes.
- **Preuve actuelle:** `PresetEditorDialog.tsx:123-129` rend les trois radios et désactive le picker en mode Aucun. Les tests actuels exercent le mode aléatoire et le mode Aucun, mais le choix radio Fixe est fourni par le preset de fixture; aucun scénario ne réactive Fixe après Aucun (`presets.spec.ts:432-451,523-590`; fixture `helpers.ts:245-248`).
- **Spec visé:** `frontend/e2e/presets.spec.ts`.
- **Priorité:** P1.
- **Commande:** `npx playwright test --workers=1 --grep 'FE-PRESET-SKIN-MODE-01'`.

### FE-LCU-RUNE-OFF-01 — Ne pas appliquer les runes quand l’option du slot est coupée

- **Précondition:** faux LCU connecté en Champ Select; preset prioritaire avec page de runes 401; état LCU initial sur une autre page (402).
- **Geste:** dans l’éditeur du preset, décocher `Appliquer automatiquement les runes`, attendre l’enregistrement, puis livrer une action pick alliée valide.
- **Assertions visibles:** le champion est confirmé; le statut ne passe pas à un succès de rune.
- **Persistance / intégration:** `/api/presets/pick_1` indique `rune_auto_apply=false`; le faux LCU reçoit le pick mais aucun `PUT /lol-perks/v1/pages/401`; la page active reste 402 et History ne contient pas un événement de rune réussie.
- **Preuve actuelle:** avant l’expansion, `presets.spec.ts:394-410` testait la persistance indépendamment, mais `lcu-automation.spec.ts:71-79` remettait explicitement le toggle à `true` avant Champ Select. Le scénario FE-LCU-RUNE-OFF-01 ferme maintenant ce trou.
- **Spec visé:** `frontend/e2e/lcu-automation.spec.ts`.
- **Priorité:** P0, car c’est une préférence explicite qui doit empêcher une mutation LCU.
- **Commande:** `npx playwright test --workers=1 --grep 'FE-LCU-RUNE-OFF-01'`.

### FE-LCU-AUTO-ACCEPT-OFF-01 — Désactiver Auto-Accept avant un Ready Check

- **Précondition:** faux LCU connecté en phase `None`; Auto-Accept activé; aucun Ready Check n’a encore été livré.
- **Geste:** désactiver Auto-Accept depuis le Dashboard, attendre l’enregistrement, émettre une vraie transition Gameflow `None` → `ReadyCheck`, puis livrer l’événement Ready Check dans le flux WebSocket du faux LCU.
- **Assertions visibles:** aucun état de succès ni message `Ready-check accepté.`; l’entrée de succès est absente de History.
- **Persistance / intégration:** `/api/settings` confirme la valeur false; `/api/runtime` confirme la phase `ReadyCheck`; aucun POST `/lol-matchmaking/v1/ready-check/accept` n’est reçu pendant la transition ni après l’événement Ready Check, et le faux LCU reste `playerResponse=None`.
- **Spec:** `frontend/e2e/auto-accept-failure.spec.ts`.
- **Priorité:** P0, une option désactivée ne doit pas accepter une partie.
- **Commande:** `npx playwright test --workers=1 --grep 'FE-LCU-AUTO-ACCEPT-OFF-01'`.

Le test anti-doublon de `dashboard-connected.spec.ts` relit aussi `ready_check.playerResponse=Accepted` après le déblocage du POST unique et avant de rejouer le même événement. Le faux LCU expose cet état, la preuve est complète dans ce harness.

### INT-APP-RESTART-AUTO-ACCEPT-01 — Reprendre Auto-Accept après recréation de l’application

- **Précondition:** le vrai FastAPI fonctionne avec le faux LCU; Auto-Accept est enregistré à `true` et un premier Ready Check a été accepté avant la recréation du contexte applicatif.
- **Geste:** recréer l’application avec `restartApplication`, attendre le nouvel abonnement WebSocket, remplacer l’ancien état LCU par un nouveau Ready Check `None`, diffuser la transition Gameflow vers `ReadyCheck`, puis diffuser l’événement Ready Check.
- **Assertions visibles:** après redémarrage, le Dashboard affiche Auto-Accept activé; le nouvel événement se termine avec la confirmation de l’état LCU `Accepted`.
- **Persistance / intégration:** FastAPI relit `auto_accept_enabled=true`; le compte et la connexion reviennent; le compteur de POST reste inchangé après le réabonnement (aucun rejeu de l’ancienne mutation), puis augmente exactement d’une seule acceptation après le nouvel événement `None`.
- **Spec:** `scripts/e2e/app.integration.spec.mjs`.
- **Priorité:** P0, couvre la restauration de la préférence et l’absence de mutation dupliquée au redémarrage.
- **Commande:** depuis `frontend/`, `npx playwright test --config ../scripts/e2e/playwright.config.mjs --workers=1` (commande du guide `scripts/e2e/README.md:14`).

### FE-LCU-SKIN-RANDOM-01 — Appliquer une skin du pool aléatoire

- **Précondition:** faux LCU en Champ Select; champion Garen choisi; Auto-Pick et automatisation des skins activées; catalogue fixture contenant les skins connus Commando Garen (86001) et God-King Garen (86013).
- **Geste:** depuis le picker UI, activer le mode Aléatoire, vider le pool, ajouter ces deux skins, puis livrer un pick valide au faux LCU.
- **Assertions visibles:** les deux cases du pool sont cochées; le statut visible confirme la skin après l’observation de l’état LCU.
- **Persistance / intégration:** FastAPI relu confirme le pool `[86001, 86013]`; l’ID du patch LCU et `selectedSkinId` après mutation appartiennent tous deux au pool; statut visible et History nomment la skin effectivement choisie. Cela vérifie l’application d’un élément du pool à deux membres, pas la distribution aléatoire ni la fréquence de chaque résultat.
- **Preuve actuelle:** avant l’expansion, le pool était configuré/effacé/relu dans `presets.spec.ts:523-550` et Auto-Pick ne vérifiait qu’une skin fixe dans `lcu-automation.spec.ts:46-120`; FE-LCU-SKIN-RANDOM-01 part de l’éditeur et va jusqu’au patch et à l’état LCU.
- **Spec visé:** `frontend/e2e/lcu-automation.spec.ts`.
- **Priorité:** P1.
- **Commande:** `npx playwright test --workers=1 --grep 'FE-LCU-SKIN-RANDOM-01'`.

### FE-LCU-REFUSAL-01 — Aucun succès trompeur après refus d’une mutation LCU

- **Précondition:** un sous-scénario Champ Select isolé par effet: action pick, sorts, skin fixe, ou page de runes; injecter une réponse 503 sur le endpoint LCU ciblé, sans remplacer la logique d’application.
- **Geste:** activer dans l’interface l’automatisation et le réglage par slot nécessaires, puis livrer le vrai événement WSS synthétique qui déclenche l’effet.
- **Assertions visibles:** après le refus, aucun statut `success` ni confirmation d’application n’est rendu pour l’effet rejeté; garder visible l’avertissement si le produit en expose un. Les autres effets non rejetés ne doivent pas être comptés comme échec du scénario.
- **Persistance / intégration:** état du faux LCU reste inchangé pour la mutation refusée; aucune entrée History de succès pour elle. Si le code prévoit un retry, attendre sa fin sans délai fixe, puis vérifier l’état réellement appliqué et une seule confirmation. Couvrir séparément les endpoints car pick, sorts/skin et runes n’ont pas tous la même voie LCU.
- **Preuve actuelle:** les E2E vérifient l’Auto-Accept refusé, Auto-Ban refusé et Auto Play Again refusé (`auto-accept-failure.spec.ts`, `lcu-automation.spec.ts:181-225,248-277`). Le scénario d’Auto-Pick et effets secondaires vérifie seulement les réponses réussies (`lcu-automation.spec.ts:46-137`); aucun `mutation_responses` sur l’endpoint pick, spells/skin ou runes n’est présent dans les specs.
- **Spec visé:** étendre `frontend/e2e/lcu-automation.spec.ts`, avec un test par famille de mutation et ID commun ou suffixé.
- **Priorité:** P0 pour le pick; P1 pour les effets secondaires.
- **Commande:** `npx playwright test --workers=1 --grep 'FE-LCU-REFUSAL-01'`.

### FE-SET-NAV-CLICK-01 — Navigation par les sept boutons de section Settings

- **Précondition:** Settings ouvert.
- **Geste:** cliquer successivement sur Général, Automatisations, Compte, Liens, Raccourcis, Apparence et Avancé.
- **Assertions visibles:** chaque clic met à jour hash, `aria-current` et le titre/contenu de section. Back/Forward Liens ↔ Raccourcis reste couvert par le scénario voisin existant.
- **Persistance / intégration:** aucune mutation attendue.
- **Preuve actuelle:** `SettingsPage.tsx:251` rend sept vrais boutons. `navigation.spec.ts:22-45` teste leurs deep-links par `goto`/reload, et `:5-20` teste le clic et Back/Forward seulement pour Liens ↔ Raccourcis.
- **Spec visé:** `frontend/e2e/navigation.spec.ts`.
- **Priorité:** P1.
- **Commande:** `npx playwright test --workers=1 --grep 'FE-SET-NAV-CLICK-01'`.

### FE-ACCOUNT-ENTER-01 — Enregistrer le Riot ID par Entrée

- **Précondition:** mode compte manuel activé; Riot ID et région valides.
- **Geste:** modifier le champ Riot ID et appuyer sur Entrée sans quitter le champ.
- **Assertions visibles:** le champ conserve la valeur acceptée; l’erreur de validation disparaît après une valeur valide.
- **Persistance / intégration:** attendre le PATCH settings 200 puis relire le Riot ID et l’identité effective de `/api/account/identity`; conserver un cas invalide distinct pour confirmer que l’ancienne valeur reste intacte.
- **Preuve actuelle:** le contrôle déclenche `saveManual` sur blur et Enter (`SettingsPage.tsx:260-266`). `settings.spec.ts:251-299` ne valide la saisie du Riot ID qu’en sortant du champ par Tab; l’action Enter est testée sur les raccourcis mais pas sur ce formulaire.
- **Spec visé:** `frontend/e2e/settings.spec.ts`.
- **Priorité:** P2, même mutation que le blur avec un geste de validation différent.
- **Commande:** `npx playwright test --workers=1 --grep 'FE-ACCOUNT-ENTER-01'`.

### FE-STATS-ACCOUNT-CTA-01 — Rejoindre Réglages Compte sans identité

- **Précondition:** aucun compte détecté ou sauvegardé, Riot ID manuel vide; exécuter depuis Statistiques puis séparément depuis En direct.
- **Geste:** cliquer sur `Configurer le compte`.
- **Assertions visibles:** l’URL devient `#settings/account`, le titre Compte et le formulaire sont affichés; depuis les deux pages, la destination est identique.
- **Persistance / intégration:** aucune mutation dans ce parcours. Les tests de saisie manuelle et de construction des liens restent séparés (`settings.spec.ts:251-269`, `statistics.spec.ts:38`).
- **Preuve actuelle:** `ProviderWebPanel.tsx:152` rend ce CTA quand il n’y a pas de profil. FE-STATS-ACCOUNT-CTA-01 le clique depuis Statistiques et En direct et vérifie la même destination.
- **Spec visé:** `frontend/e2e/statistics.spec.ts`.
- **Priorité:** P1, c’est l’issue proposée à une personne sans compte configuré.
- **Commande:** `npx playwright test --workers=1 --grep 'FE-STATS-ACCOUNT-CTA-01'`.

### FE-SHELL-BRAND-01 — Retour au Dashboard par le logo

- **Précondition:** être sur Statistiques puis Historique, sans dialogue ouvert.
- **Geste:** cliquer le lien de marque depuis Statistiques; depuis Historique après rechargement, vérifier le focus naturel du document, parcourir l’ordre Tab réel jusqu’au lien, puis appuyer sur Entrée.
- **Assertions visibles:** URL `#dashboard`, titre Dashboard et `aria-current` Dashboard.
- **Persistance / intégration:** aucune mutation attendue.
- **Preuve actuelle:** `AppShell.tsx:22` rend le lien de marque accessible vers `#dashboard`; l’assertion clavier identifie le lien lorsqu’il reçoit effectivement le focus Tab, sans appeler `focus()`.
- **Spec visé:** `frontend/e2e/navigation.spec.ts`.
- **Priorité:** P2, destination redondante avec le lien Dashboard déjà testé.
- **Commande:** `npx playwright test --workers=1 --grep 'FE-SHELL-BRAND-01'`.

### FE-NATIVE-PROVIDER-01 — Création/réutilisation d’une fenêtre Statistiques/Live

- **Précondition:** Windows interactif, source WebView2 isolée, provider et compte déterministes, egress externe contrôlé, aucun `LeagueClientUx` bloquant le préflight.
- **Geste:** ouvrir la page Statistiques, cliquer `Ouvrir dans OTP LOL`; répéter le clic; masquer/fermer la fenêtre; revenir à la route puis cliquer Actualiser. Rejouer les étapes pour En direct.
- **Assertions visibles:** états création/loading/ready/visible/hidden/closed/error cohérents dans la page et Diagnostics; erreur explicite en cas d’échec.
- **Persistance / intégration:** inspecter l’état du manager et l’URL HTTPS autorisée; second clic montre/réutilise la fenêtre existante; refresh recharge celle-ci; aucune seconde fenêtre ou URL hors allowlist.
- **Preuve actuelle:** le navigateur teste la limite du manager et le fallback externe simulé (`statistics.spec.ts:299-372`). La matrice indique que le runner natif n’a observé que le refus `network_unavailable`; il ne prouve pas une ouverture réussie/réutilisation.
- **Spec visé:** étendre `scripts/e2e/native/run_native_e2e.mjs`; garder le test navigateur existant pour le fallback.
- **Priorité:** P1 pour la fonction « Ouvrir dans OTP LOL ».
- **Commande:** depuis la racine, `node scripts/e2e/native/run_native_e2e.mjs` sur une session Windows interactive avec WebView2 et les préconditions ci-dessus.

## Actions sans nouveau scénario E2E indépendant

- Le filtre History `Erreurs` est cliqué et son état vide est vérifié. Les actions normales parcourues n’écrivent pas d’entrée History de niveau `error`; les automatisations rejetées confirment l’absence d’un succès fictif. Ne pas fabriquer une erreur History avec un `page.request` ou une fixture injectée dans le fichier utilisateur pour remplir artificiellement ce filtre. Reconsidérer quand un geste supporté produit une entrée d’erreur visible.
- Le filtre Diagnostics `WebView` est cliqué et l’état vide est testé. Un résultat non vide nécessite un vrai événement WebView natif; le fabriquer côté React ne validerait pas l’intégration.
- Le retry du bootstrap après 503 est déjà couvert par FE-DASH-LOAD-01. L’état d’erreur propre à `DashboardPage` pour `/api/presets` n’est pas atteignable après un bootstrap valide, qui hydrate déjà la query; le tester demanderait un contrat valide pour un bootstrap partiel.
- Ne pas créer de scénario autour du sort « Aucun » avant clarification de sa sémantique dans le contrat preset/LCU. Le contrôle visible et la valeur persistée doivent être reliés à un comportement utilisateur et à une commande LCU confirmés; aucun attendu ne doit être inventé.
- Les transformations internes pures (formatage d’un détail, filtre d’une liste, mapping d’un hash) ne justifient pas un scénario Playwright séparé sans geste ou rendu distinct. Garder leur comportement observable dans les parcours UI qui utilisent ces données.
- Les réglages individuels partagent les mêmes composants et API. Les valeurs de chaque switch sont déjà sauvegardées par E2E; les erreurs, rollback et clics répétés sont exercés sur au moins un switch par composant. Ajouter un scénario par champ uniquement si un champ possède une validation ou un effet distinct.
- Ne pas ouvrir un site fournisseur public pour vérifier son contenu dans les tests browser: le harness bloque les origines externes. Tester les URLs construites, l’hôte/HTTPS attendu et le retour du bridge; réserver la disponibilité tierce à un contrôle séparé si elle devient un critère produit.

## Limites d’environnement et critères d’acceptation

- Chromium avec `deviceScaleFactor` peut vérifier le layout CSS, le focus, les formulaires et les appels bridge simulés. Il ne prouve pas WebView2 réel, HWND, tray, dialogues Windows, DPI système 125/150 %, multi-écran, raccourcis globaux, lancement/fermeture de l’EXE ou effets de `Masquer à la connexion` / `Fermer lorsque League est réellement fermé`.
- Le faux LCU valide les états et commandes protocolaires contrôlés, pas le lockfile Riot, les droits, le timing, la version du client ni un vrai match League.
- Pour conclure sur une action intégrée: geste accessible depuis la page, état visible avant/après, réponse FastAPI réelle après la suppression de toute interception, relecture persistée; pour LCU, requête au faux serveur et snapshot d’état après action.
- Toute panne simulée doit rester bornée au cas d’échec. Le chemin de récupération réussi doit revenir au vrai FastAPI.
- Les specs doivent cibler un profil temporaire et nettoyer le serveur et le faux LCU. Aucun dossier utilisateur réel, compte personnel ou log local ne doit servir de fixture.

## Journal d’exécution de l’expansion

- Le premier essai via `npm run test:e2e -- ...` a perdu les options Playwright dans le PowerShell courant et a démarré les quatre specs entières, 68 tests à six workers. C’est une exploration non probante; des échecs de test initial et une erreur harness `NoSuchProcess` sous concurrence ont été observés, aucun n’est retenu comme résultat final.
- Rerun UI ciblé avec `npx playwright test --workers=1 --grep "FE-DASH-LOAD-01|FE-PICK-KEY-01|FE-PICK-ROLE-01|FE-PRESET-SKIN-MODE-01|FE-SET-NAV-CLICK-01|FE-SHELL-BRAND-01|FE-DASH-MANAGE-01|FE-STATS-ACCOUNT-CTA-01"`: **8 réussis**, 1,3 min. Cela a été relancé après les ajouts clavier, logo et CTA des deux pages.
- Un précédent rerun groupé des quatre scénarios a été invalidé pendant `browserContext.close` par `ENOENT` sur les traces partagées `test-results/.playwright-artifacts-0`; un autre run Playwright `HIST-03` tournait simultanément. Cette tentative ne constitue pas un verdict produit et précède les runs séquencés ci-dessous.
- Run séquencé des sept specs demandées (`npx playwright test e2e/auto-accept-failure.spec.ts e2e/dashboard-connected.spec.ts e2e/lcu-automation.spec.ts e2e/navigation.spec.ts e2e/presets.spec.ts e2e/settings.spec.ts e2e/statistics.spec.ts --workers=1`, depuis `frontend/`): **135 passés, 1 échoué**, 20,5 min. L’unique échec était FE-LCU-SKIN-RANDOM-01 à `lcu-automation.spec.ts:232`: `.check()` n’a pas changé l’état de la checkbox. Les assertions de cette tentative ne valident pas la version multi-skin ci-dessus.
- Le premier rerun des trois cas red-team a passé Auto-Accept OFF et skin random, mais le lien de marque a échoué parce que le changement de hash conservait le focus du clic précédent. Après rechargement de `/#history` pour repartir du focus naturel, rerun ciblé depuis `frontend/`: `npx playwright test e2e/auto-accept-failure.spec.ts e2e/lcu-automation.spec.ts e2e/navigation.spec.ts --workers=1 --grep "FE-LCU-AUTO-ACCEPT-OFF-01|FE-LCU-SKIN-RANDOM-01|FE-SHELL-BRAND-01"` => **3 réussis**, 28,5 s.
- Scénario restart relancé avec la commande du guide `scripts/e2e/README.md:14`, depuis `frontend/`: `npx playwright test --config ../scripts/e2e/playwright.config.mjs --workers=1` => **1 réussi**, 24,6 s. Un essai initial depuis la racine a échoué avant d’exécuter le test (`test() did not expect test() here`); le mauvais répertoire de travail était la cause, pas un échec applicatif.
- Aucun run global n’est consigné pour cette expansion.
