# Plan de migration vers des tests E2E uniquement

## Objectif et périmètre

Remplacer tous les tests unitaires actuels par une suite de tests de bout en bout qui pilote les parcours visibles d’OTP LOL. La suite doit traverser l’interface React, la vraie API FastAPI, la persistance et, quand le parcours le requiert, l’intégration au protocole LCU ou au shell Windows.

Le périmètre couvre l’application desktop, son frontend, son backend et le site de présentation séparé sous website/. Les vérifications statiques et les contrôles de packaging restent en place. La migration des suites de tests ne vise pas de refonte produit ou architecturale. Un défaut de compatibilité des réglages MainLoL/`region` confirmé pendant les E2E a toutefois nécessité une correction ciblée et non destructive; cette correction est documentée et couverte par le scénario de migration dédié.

État au 2026-09-30: branche `codex/react-fastapi-webview-migration`, dernier commit de code poussé `205d05d253bc39dff3aea68fcaea52f72cbbc236`, comparé à `origin/main` `809d8567ee4755672b812cc63da46488c30a8ce8`. Le run GitHub du commit documentation-only `89d8ac4` a échoué sur **1/138**, uniquement DIAG-01: Playwright a rejeté `pauseAt(new Date())` avec `Cannot fast-forward to the past`. Le correctif de marge 1 s dans `205d05d` passe DIAG-01 **10/10** localement. Sur GitHub pour `205d05d`, un job Windows Playwright a passé navigateur **138/138**, full-stack **1/1** et API **35/35**; le doublon a passé **137/138** et échoué uniquement à l’assertion de délai du timer updates. Le test recalibré dans le worktree passe **10/10** ciblé et le browser complet **138/138 en 18,2 min**. Les checks non-Playwright de `205d05d` ont réussi. Le package self-test ne valide pas l’interface EXE interactive, un WebView2 réel ni un client League réel. Les paragraphes qui citent d’anciens SHAs décrivent des snapshots historiques.

## Statut réel au 2026-09-30

Le harness `scripts/e2e/app_server.py`, `fake_lcu.py` et `appServer.mjs` sert le build React via le vrai FastAPI, isole les chemins utilisateur sous un profil temporaire, et dirige les transports HTTP/TLS/WSS du vrai `lcu-driver` vers un faux client League pilotable. Les requêtes ordinaires des specs navigateur vont au vrai serveur et le WebSocket applicatif n’est pas remplacé. Plusieurs tests utilisent toutefois `page.route` pour injecter explicitement des scénarios de panne/réponse: `/api/network/status`, `/api/history`, `/api/champions`, `/api/presets/pick_1`, `/api/assets/skins/86/86013/splash*`, `/api/settings`, `/api/settings/last-detected-account`, `/api/presets/reset`, `/api/presets/clear`, `/api/settings/reset`, `/api/diagnostics` et `/api/diagnostics/run`. Ces tests valident la réaction UI à une panne ou un rejet et ne prouvent pas que FastAPI émet cette réponse; les retries de Settings et Diagnostics sont routés vers le FastAPI réel. La suite E2E API complète a passé 35/35 après le patch final, dont le cas où TOML prime sur les deux sources JSON. Les dépendances externes (Data Dragon et GitHub Releases) sont contrôlées au boundary réseau Python.

La fixture `otpApp` vient d’être passée en scope test après avoir confirmé des fuites d’état entre tests (état réseau, catalogues LCU, runes). Chaque test reçoit un serveur/profil isolé; le redémarrage avec le même profil reste dans le test d’intégration dédié. Les états réseau sont configurés avant la première navigation et `/api/network/check` est appelé explicitement. Le coût de cette isolation n’a pas encore été mesuré.

Le dernier browser complet avec le timer recalibré passe **138/138 en 18,2 min**, teardown compris; DIAG-01 et timer passent chacun 10/10 en répétition. La reconnexion LCU a aussi passé 10/10. Le diagnostic antérieur du shutdown Windows reste distinct: après `ConnectionResetError` dans `asyncio.proactor_events._call_connection_lost`, des transports Proactor déjà fermés pouvaient rester dans le listener et Uvicorn attendre `Server.wait_closed()`. Le fallback étroit dans `EmbeddedApiServer.stop()` réveille uniquement ce waiter lorsque le listener est fermé, Uvicorn n’a plus de connexions ni tâches, et tous les transports restants sont déjà en fermeture. Uvicorn poursuit ensuite son shutdown et le lifespan FastAPI. Le risque résiduel est une libération bas niveau différée du socket par asyncio; supprimer ce fallback quand la version Python supportée corrige le détachement des connexions réinitialisées. Références: [issue CPython #93821](https://github.com/python/cpython/issues/93821) et [PR de traitement des resets Proactor #124779](https://github.com/python/cpython/pull/124779). L’API passe 35/35 et l’intégration full-stack 1/1. Le build et `api:check` passent. Sur GitHub, un job Playwright pour `205d05d` a passé toutes ses phases, le doublon a échoué uniquement sur l’ancienne assertion de timer. Aucun test interactif d’EXE/WebView2 ni de client League réel n’a été réalisé.

`scripts/e2e/app.integration.spec.mjs` contient un scénario full-stack de persistance après restart, WSS/LCU, déconnexion/reconnexion, identité, données statiques, updates et cleanup; il a passé 1/1 en local et dans le job CI réussi pour `205d05d`. Le workflow séquence le navigateur, cette intégration et `npm run test:e2e:api`. Le run précédent `89d8ac4` s’est arrêté au browser, sur DIAG-01.

La couverture native reste incomplète. Le run Windows échoue avec `PermissionError [WinError 5]` dans pystray/Win32 lorsque `_on_notify` appelle `GetCursorPos`, après le clic droit synthétique et avant les assertions tray. Les étapes précédentes ont passé et les processus ont été nettoyés. Ce résultat ne confirme pas un bug produit; une reproduction sur desktop interactif déverrouillé reste nécessaire. Le red-team signale seulement une possible course entre `update_menu()` et `TrackPopupMenuEx`, non confirmée. Le faux client couvre le transport et les mutations après injection d’un lockfile, pas la découverte réelle du processus League.

Le site possède ses specs Playwright et une config `vite preview`; `website/test/content.test.mjs` et le script `test: node --test` sont supprimés. Les assertions présentes portent sur le lien releases, les IDs/labels/titres/alt/notes des captures et le chargement des assets dans le site rendu. Build et E2E website 13/13 ont passé lors d’un run antérieur; `Website CI / Build and Playwright` et `deploy` ont aussi réussi sur le SHA actuel.

### Tests et commandes actuels

| Surface | Fichiers / commande | Ce que cela couvre aujourd’hui |
|---|---|---|
| Python | Aucun `tests/test_*.py`, `tests/fake_lcu_server.py` ni `requirements-test.txt` dans le tree local | Les workflows gardent `compileall` et Ruff comme contrôles statiques; aucune commande pytest/unittest active. Une part des anciens invariants internes n’a pas de parcours observable équivalent. |
| React / TypeScript | Aucun `frontend/src/**/*.test.ts(x)`, Vitest, jsdom ou Testing Library | `npm test`/Vitest retiré; API OpenAPI, typecheck et build restent dans le job statique. Le comportement est couvert seulement lorsqu’une spec E2E actuelle l’exerce. |
| Frontend E2E | `frontend/e2e/`, `scripts/e2e/app.integration.spec.mjs`; full UI avec `npx playwright test --workers=1`, API avec `npm run test:e2e:api` | Run local actuel: UI 138/138, API 35/35, intégration full-stack 1/1; timer, reconnexion et DIAG-01 ciblés 10/10 chacun. Sur `205d05d`, un job GitHub a passé UI 138/138, full-stack 1/1 et API 35/35; son doublon a échoué sur le timer à 137/138. Le test timer recalibré passe dans le worktree local. |
| Website | `website/e2e/site.spec.ts`, `npm run build`, Playwright | Le fichier `website/test/content.test.mjs` et `npm test` sont supprimés; les assertions sont migrées vers Playwright. Build et E2E website 13/13 ont passé lors d’un run antérieur; ce résultat n’est pas un run du dernier patch. |

Commandes actives dans les workflows locaux :

- Python CI : installation des dépendances runtime, compileall des sources livrées et Ruff; aucun runner de tests.
- Release : typecheck/build, compileall, OpenAPI, Playwright navigateur avec un worker, six suites API avec un worker par config, puis build/signature/self-test/installateur.
- Frontend CI : le job statique exécute `api:check`, typecheck et build. Le job Windows construit le frontend puis exécute Playwright navigateur, le smoke intégré et six configs API de façon sérielle. Le nom de check `Frontend CI / Unit and build` est conservé pour stabilité, bien qu’aucun test unitaire n’y tourne.
- Site : `website-ci.yml` et le workflow Pages exécutent `npm ci`, le build puis Playwright sur `vite preview`; les deux anciennes assertions `node:test` ont été migrées et le script `npm test` supprimé.
- Vérifications statiques existantes : compileall, Ruff, TypeScript, build Vite, génération OpenAPI avec api:check, pip-audit/npm audit, CodeQL et Gitleaks.

`npm run test:e2e:api` exécute dans l’ordre `account-api`, `asset-api`, `diagnostics-api`, `lcu-automation-api`, `datadragon-cache-api`, `api-contract`, chaque configuration avec `--workers=1`. Le navigateur E2E inclut des routes simulées qui forcent certaines pannes/rejets UI; ces scénarios ne doivent pas être confondus avec les tests HTTP E2E sur le FastAPI réel.

### Limites et défauts confirmés

`frontend/e2e/history.spec.ts` sépare trois preuves. `un ready-check accepté est envoyé au LCU et enregistré dans l’API History` vérifie le POST au faux LCU et l’entrée réelle `/api/history`. `[HIST-01] History filters messages and details from a real automatic summoner-spell event` vérifie recherche dans les messages/détails et filtres. `[HIST-02] an already-mounted History page receives an accepted ready check live` monte History avant l’événement, puis vérifie l’API et le rendu sans navigation; le marqueur `test.fail` a été retiré avec l’invalidation du query dans le worktree. `l’historique chargé peut être effacé après confirmation dans l’application` et les tests voisins couvrent la suppression. Tous ces scénarios passent dans le dernier frontend complet, 138/138.

`frontend/e2e/diagnostics.spec.ts` contient `[DIAG-01] a diagnostics read failure can be retried from the visible error state`, `[DIAG-02] a rejected endpoint check can be retried and its real result survives reload` et `[DIAG-03] log filters combine with text search and clear back to visible entries`. DIAG-03 passe avec la vraie valeur `Lobby`; l’écart initial `UpdateLobby` était une mauvaise cible de test, pas un bug produit confirmé. DIAG-01 fige le temps Playwright après le rendu de l’erreur pour bloquer le polling périodique de 5 s; le clic Retry déclenche alors le vrai FastAPI et persiste le succès. Le dernier frontend complet passe 138/138, dont les scénarios Diagnostics.

Observation UX confirmée par source, sans changement produit dans ce scope: `DiagnosticsPage.tsx` rend le même texte `copy.runFailed` (« Les tests de diagnostic ont échoué. ») pour l’erreur du GET `/api/diagnostics` et le rejet du POST de checks. La première panne peut donc faire croire qu’un test d’endpoint a échoué alors que la page n’a pas chargé; DIAG-01 ne verrouille pas encore le libellé. Un texte distinct et une assertion de récupération lisible sont à planifier.

`frontend/e2e/ui-smoke.spec.ts` sépare aussi le parcours normal de l’attendu-échec ciblé. Le smoke navigation/pickers/settings/ready-check/history est un test normal qui ignore uniquement la violation CSP connue lorsqu’il vérifie les erreurs console, et échoue sur toute autre erreur, `pageerror` ou requête échouée. Le test distinct ouvre la page, puis marque l’attendu-échec seulement avant de vérifier les flags initialisés par le script inline. La trace montre que le CSP FastAPI `script-src 'self'` bloque ce script dans `frontend/index.html`, qui définit `window.__otpDesktopMode` / `window.__otpNativeBridgeReady`. Ne pas élargir le CSP sans examen produit/sécurité.

Les six snapshots Dashboard précédents ne sont pas encore une preuve d’une régression visuelle : les captures réelles étaient faites client LCU connecté avec placeholders, alors que les baselines étaient hors ligne avec assets chargés et des presets issus d’une fixture historique. Le scénario est maintenant aligné pour charger Data Dragon, vérifier le transport LCU déconnecté avant `page.goto`, et vider l’identité détectée. Reprendre les captures après revue; ne mettre à jour les baselines qu’après comparaison des états et assets.

Un screenshot WebView à 1086×753 a été signalé avec le CTA « Réessayer maintenant » coupé à droite. Le dernier run Playwright passe les tests de géométrie aux résolutions et scalings prévus, dont 800×540, 1086×753, 1366×768, 1920×1080, 2560×1440, 2560×1600, 125 % et 150 %. Cela valide Chromium, pas le rendu WebView2/DPI natif; une vérification native reste nécessaire pour conclure.

Le seam LCU conserve le vrai `Connector`, `Connection`, HTTP/TLS/WSS et le traitement des événements après injection de lockfile synthétique via `lcu_driver.connector._return_ux_process`. Il ne valide pas la découverte réelle de `LeagueClientUx` ni l’extraction des paramètres du processus. La lecture du vrai League, du shell natif, du tray, des raccourcis globaux et des dialogues reste une frontière séparée.

## Architecture cible de test

### 1. Parcours E2E application en CI

1. Installer les dépendances runtime Python et Node prévues, puis compiler `frontend/dist` de production.
2. Chaque test utilise la fixture `otpApp` de `frontend/e2e/helpers.ts` (scope test), qui démarre `scripts/e2e/app_server.py` avec un port loopback et un profil temporaire. La page reçoit l’URL annoncée par le helper; la config Playwright ne démarre pas Vite et ne réutilise pas de serveur préexistant.
3. Piloter le vrai bundle et la vraie API FastAPI via Chromium. Les réponses des parcours normaux proviennent des vraies routes `/api/**` et `/api/events`; des `page.route` ciblés injectent les erreurs UI listées dans « Statut réel au 2026-09-30 ». Pour les tests panne-puis-retry, retirer l’interception et vérifier que le retry passe par FastAPI réel.
4. Vérifier les effets par l’interface, les réponses de l’API réelle, les requêtes/post-états du faux LCU et les réponses des fixtures externes contrôlées. La persistance après arrêt/redémarrage est exercée par le smoke d’intégration dédié.
5. Arrêter FastAPI, faux LCU et profil temporaire dans les fixtures même si une assertion échoue; préserver l’erreur primaire si le cleanup échoue aussi.

### Isolation avant import et réseau externe

`src/config/paths.py` calcule au chargement du module les chemins de `parameters.toml`, `history.json`, caches, lockfile et WebView. `src/api/app.py` construit aussi `app = create_app()` à l’import. Le runner doit donc créer les dossiers temporaires et définir `APPDATA`, `LOCALAPPDATA`, `TEMP` et `TMP` **dans l’environnement du sous-processus, avant tout import de `src`, `src.config` ou `src.api.app`**. Le prototype importe `tempfile` dans le petit runner avant l’isolation, puis remet `tempfile.tempdir = None` après les changements d’environnement; garder ce reset (ou définir l’environnement dans un wrapper encore plus précoce) avant tout appel applicatif à `tempfile.gettempdir()`. Il ne suffit pas de changer les variables après l’import de configuration. Un scénario de relance réutilise uniquement le profil temporaire de ce test et vérifie les chemins réellement résolus. Ne jamais modifier le profil Windows de l’utilisateur.

Le harness bloque l’egress de l’application et peut répondre aux dépendances externes à leur frontière HTTP Python. La fixture Data Dragon a des réponses déterministes online/offline; la fixture GitHub Releases a des états offline/available/none. Le faux LCU a les états catalogues contrôlés lors du bootstrap/reconnect. Les specs vérifient les demandes aux fixtures et le statut résultant. Au démarrage, un probe sans ouverture de socket vérifie que `connect`, `connect_ex` et `sendto` refusent chacun une cible publique; le smoke exige la preuve de ces trois contrôles et qu’aucune tentative non autorisée n’a été enregistrée pendant le parcours.

Les providers affichés dans Statistics/Live ne doivent pas charger leurs vrais sites pendant la suite régulière. Vérifier URL validée, nom du provider, demande d’ouverture transmise à la fenêtre native et état de repli. Un smoke manuel en ligne séparé peut contrôler le contenu tiers; il ne compte pas comme couverture E2E déterministe.

### Preuve actuelle du chemin LCU

Le harness lance une copie temporaire de l’interpréteur comme processus League synthétique avec lockfile/arguments. Il vérifie que le scanner de production non filtré trouve son PID et que `Connection` extrait les arguments sans ouvrir le réseau. Avant `Connector.start()`, il filtre `lcu_driver.utils.process_iter` au seul PID synthétique; le `_return_ux_process()` de production et tout le transport HTTP/TLS/WSS restent actifs. Ce test vérifie l’attachement au faux processus contrôlé, pas le choix d’un client League parmi les processus d’une vraie machine avec League installé. Le filtre s’appuie sur un point d’entrée lcu-driver interne à son module `utils`; garder ce seam dans le sous-processus E2E, vérifier sa compatibilité et conserver la limite de découverte réelle explicitement.

`tests/fake_lcu_server.py` n’est pas utilisé comme preuve d’intégration. Le faux LCU dédié reçoit les requêtes/mutations couvertes, et les événements repassent par le WSS de production. Les états client/transport simulés ne démontrent pas toutes les phases d’un vrai client League ni la sélection face à plusieurs LeagueClientUx réels; ces cas restent à valider séparément et sans exposer un compte utilisateur.

Les serveurs externes non contrôlables (Data Dragon, fournisseur de statistiques) peuvent être remplacés par des serveurs HTTP locaux à la frontière réseau de l’application, avec les vrais services et clients de production. N’intercepter ni l’API interne ni le WebSocket interne du produit. Garder une sonde facultative en ligne séparée pour les services Riot tiers.

### 2. Parcours du shell Windows et du paquet

**État du runner natif source : échec avant assertions tray.** pystray `_on_notify` appelle Win32 `GetCursorPos` après un clic droit synthétique; l’appel lève `PermissionError [WinError 5]`. Les étapes précédentes ont passé et les processus ont été nettoyés. Ce n’est pas un bug produit confirmé; reproduction à faire sur un desktop interactif déverrouillé. La possible course `update_menu()`/`TrackPopupMenuEx` reste une hypothèse red-team, non confirmée. L’interaction native de l’EXE reste non testée.

Après réussite du spike, lancer l’EXE onedir dans le profil APPDATA/LOCALAPPDATA/TEMP/TMP isolé, piloter sa vraie WebView/native window et vérifier démarrage, contenu servi par FastAPI, navigation, fenêtres provider, tray, raccourcis, dialogues, fermeture et persistance. Utiliser uniquement des données et comptes synthétiques. Ne jamais pointer le test vers le vrai `%APPDATA%\OTP LOL`. Le self-test packagé est un smoke sans UI, il ne remplace aucune action native. L’EXE n’a pas été construit localement: `build/` et `dist/` préexistaient, et le script de build supprime ces dossiers; le build local a donc été omis pour préserver ces données. Si certains contrôles natifs restent impossibles à automatiser dans l’environnement autorisé, les noter comme couverture E2E incomplète et le signaler comme objectif non atteint; le test manuel ne satisfait pas la demande « E2E uniquement ».

Conserver le self-test packagé actuel comme contrôle des ressources, API embarquée et écriture/lecture temporaire. Il complète le parcours UI Windows, mais ne le remplace pas. Toute validation manuelle documentée peut décrire une limite ou apporter un complément; elle ne valide pas l’objectif E2E et ne transforme pas les parcours natifs non automatisés en couverture réussie.

### 3. Site de présentation

`website/test/content.test.mjs` et son script `npm test` sont supprimés. `website/e2e/site.spec.ts` couvre navigation, skip-link, sélection et descriptions des captures, assets rendus, dialogues, liens sûrs, images/alt et overflow de plusieurs viewports. Build et Playwright 13/13 ont passé dans un run antérieur; `deploy-website.yml` et `website-ci.yml` n’ont pas été relancés sur le SHA local modifié. Le site reste distinct du frontend desktop.

## Matrice d’actions E2E à couvrir

Les tests sont identifiés par une action utilisateur et un résultat observable. Ils doivent couvrir la réussite, l’annulation et au moins un échec réaliste lorsque l’action enregistre, démarre un service ou dépend du réseau.

### Démarrage, navigation et état de l’application

- Premier lancement : création de valeurs par défaut, presets de départ, automatisations désactivées, chargement du Dashboard, messages d’onboarding, absence d’erreur console ou API.
- Arrêt et relance : vérifier que les choix enregistrés réapparaissent depuis le stockage; fermer puis relancer avec le même dossier temporaire.
- Deuxième instance : lancer un second processus et vérifier qu’il quitte sans démarrer un second serveur, et que son arrêt ne supprime pas le verrou de la première instance. Le comportement courant consigne `Another instance is already running. Closing.` puis retourne; il ne focalise pas la première fenêtre et n’affiche aucun message visible à l’utilisateur.
- Client fermé, en démarrage, présent sans session, session connectée; transitions lobby, matchmaking, ready check, champion select, chargement, partie, récupération des statistiques, fin de partie, déconnexion transitoire et reconnexion.
- Ouvrir chacune des six routes (dashboard, statistics, live, history, settings, diagnostics), toutes les sept sections de réglages, chaque deep link, Retour/Avance navigateur, navigation sidebar et actions rapides. Vérifier la route active, son état de retour et le focus au changement de page.
- URL inconnue, réponse bootstrap invalide/indisponible, API arrêtée, rechargement rapide et navigation pendant un chargement : l’application fournit un état d’erreur clair, une récupération possible et aucun contrôle mensonger ou gel permanent.

### Dashboard, automatisations et presets

- Dashboard vierge/configuré, connecté/déconnecté, chaque phase LCU, statut d’automatisation success/warning/error avec âge et gravité.
- Parcours d’onboarding : aller vers le premier preset vide, fermer, modifier un preset, confirmer sa disparition persistée après reload.
- Activer/désactiver le maître Presets depuis Dashboard, preset editor, réglages et tray. Les sous-préférences restent mémorisées lorsque le maître est OFF; Auto-Accept et Auto Play Again restent indépendants. Tester pending, rejet backend, rollback et double clic.
- Ouvrir/modifier/fermer chacun des trois presets, commandes clavier, annuler, sauvegarder et vérifier l’effet après navigation et relance.
- Champion picker : recherche nom/alias, filtre par lane, liste sans résultat, champion indisponible, chargement/erreur/retry, sélectionner, annuler, exclusions des picks/ban déjà assignés et filtre owned sans perdre les entrées du pool aléatoire.
- Ban picker : modifier, rechercher, sélectionner, annuler, enregistrer, état pending/erreur et retour du focus.
- Sorts : choisir chaque sélection proposée, clavier, affichage icône, persistance et erreur de sauvegarde.
- Runes : sélectionner une page existante, « ne rien modifier »/page 0, page sauvegardée absente, cache/LCU indisponible, auto-apply par slot, préserver la page active; vérifier le vrai changement/événement via faux LCU pour chaque slot.
- Skins : aucun skin, skin fixe, mode aléatoire, choix du pool, sélectionner/tout sélectionner/tout vider, possédés seulement, pool vide, champion/changement de catalogue, image indisponible et repli vers l’image de base; vérifier l’application via faux LCU.
- Ban, pick, sorts, runes et skin en champion select : action permise/interdite, préférence désactivée, état LCU modifié en cours d’action, réponse en erreur, retry, résultat confirmé ou échec visible. Vérifier que les états vus dans l’interface correspondent à ceux du faux LCU.
- Actions rapides vers historique/statistiques/réglages/liens; aucun clic ne doit aller vers une destination invalide ou dupliquer une action.

### Réglages (7 sections)

| Section | Interactions E2E requises |
|---|---|
| Général | Masquer après connexion, réafficher, fermer lorsque le processus League est réellement absent, garder l’application ouverte lors d’une déconnexion temporaire ou si League tourne encore. Vérifier au travers de l’application Windows et du faux processus League. |
| Automatisations | Tous les toggles (Presets maître, accept, pick, ban, sorts, skins, rejouer), verrouillage des enfants, persistance et indépendance des automatismes non enfants; API refusée et retour au choix enregistré. |
| Compte | Basculer auto/manuelle, saisir Riot ID et région, sauvegarder, validation/saisie incorrecte, région-plateforme cohérente, identité LCU connectée, dernier compte complet offline, absence de compte, copier l’identité détectée dans les champs manuels après confirmation, annuler, rejet API puis retry; oublier après confirmation/annulation, rejet API puis retry; les préférences manuelles ne doivent pas être altérées par l’oubli. La copie de compte ne sollicite pas le presse-papiers. |
| Liens | Ouvrir les pages Statistics et Live, choisir les fournisseurs, persister séparément le fournisseur de stats et celui de live, réouvrir l’application. Le lien externe est validé et transmis au shell, aucun domaine arbitraire ne doit être ouvert. |
| Raccourcis | Entrer/sauver les deux raccourcis, accepter les combinaisons valides, refuser une touche seule ou modificateur seul, conflits/duplication, cancel/Escape, rétablir l’ancienne valeur après erreur, événement de reconfiguration et déclenchement effectif Alt+C/Alt+P dans le shell Windows. |
| Apparence | Passer clair/sombre, vérifier toutes les pages et dialogs, sauvegarder, naviguer et relancer; échec sauvegarde restaure le thème persistant. |
| Avancé | Ouvrir dossiers logs/AppData via le bridge; action rapport d’incident et validation de l’URL; exporter settings valide et contrôler contenu téléchargé/exclusion de l’identité locale; importer valide, ancien schema, schema futur, JSON malformé, mauvais type, annuler le sélecteur, erreur de lecture, vérifier rejet sans mutation; restaurer presets, vider seulement les presets, reset complet, annuler chaque dialogue, confirmer chacun, vérifier l’état précis des automatismes/compte/theme après reload; basculer plein écran et revenir via le bridge. |
| Diagnostics | Même menu via Réglages > Avancé, état LCU offline, exécuter uniquement les checks GET prédéfinis, résultat et temps, persistance après navigation/reload, filtres LCU/Automation/Données/WebView/Erreurs, texte de recherche sans résultat/effacement, détails JSON uniquement dans le drawer, fermer et focus, exporter par défaut redacted, consentement explicite Riot ID, fichier téléchargé, échec export, copie support/clipboard et échec du bridge. |

### Statistiques, direct et historique

- Statistics : compte connecté, manuel, sauvegardé offline et compte absent; fournisseurs disponibles, changement inline, persistance et erreur sauvegarde; ouvrir dans l’application, rouvrir/afficher, reload, navigateur externe, échec de fenêtre native et fallback; bouton Actualiser, réponse lente/erreur.
- Live : les mêmes contrôles et sources, plus route distincte, entrée automatique à la navigation et par raccourci Alt+P; aucun focus intempestif d’une fenêtre déjà visible.
- Ne pas prétendre valider le contenu ou disponibilité des sites tiers via un fixture statique. Vérifier URL sûre, nom du fournisseur, état natif et fallback utilisateur. Le chargement du contenu tiers réel est un test manuel réseau, sujet au fournisseur.
- History : liste vide/chargée, recherche, chacun des filtres disponibles et combinaison, changer/effacer la recherche, pagination si présente, erreur/timeout/retry, demander la confirmation de suppression, annuler, confirmer, empêcher double submit, vérifier que l’historique supprimé reste vide après relance et que la nouvelle activité s’y ajoute.

### Réseau, assets, diagnostics et données

- Data Dragon disponible, indisponible dès le lancement, perte après chargement puis retour; avertissement, données en cache/offline et rafraîchissement sans bloquer la navigation.
- Erreur de l’API réseau locale distincte d’une panne du serveur d’assets, action de recheck et récupération.
- Data Dragon/LCU/static snapshot : catalogue avec cache, actualisation LCU, invalidation des requêtes visibles, fallback asset/champion/skin/sort/rune, donnée manquante et mauvais content-type; le vrai backend gère ces réponses.
- Traces et exports diagnostics : bornes du buffer, erreurs LCU, identité privée redacted par défaut, révélation seulement par consentement explicite. Les valeurs d’identité de test restent synthétiques.

### Site website/

- Arriver sur la page, liens par ancres Fonctionnement/Application/Installation, skip link clavier, retour en haut et lien projet/download.
- Sélectionner chaque capture et vérifier titre, texte alternatif, note et image valide; ouvrir le dialogue, mode taille ajustée/réelle, fermer par bouton/Escape/backdrop, focus rétabli.
- Valider que les boutons de téléchargement et GitHub pointent au bon dépôt/releases sans réellement lancer le téléchargement.
- Affichage et navigation au minimum sur desktop, tablette et mobile étroit; pas de débordement horizontal, contrôles utilisables au clavier et images chargées.

### Layout, clavier et accessibilité

- Conserver les viewports actuels (800×540, 1100×760, 1366×768, 1440×900, 1920×1080, 2560×1440 et 2560×1600) et scénarios navigateur 125/150 %. Le zoom navigateur ne compte pas comme DPI Windows; automatiser l’échelle d’affichage Windows 100/125/150 % lors du spike natif si le runner le permet. Si ces niveaux ou le multi-écran ne peuvent pas être pilotés et observés automatiquement, indiquer explicitement cette couverture manquante.
- Dashboard, Settings, picker, drawers, dialogs, diagnostics, statistiques, live et historique : aucun scroll horizontal non voulu, contenu clé visible, liens/boutons atteignables, focus visible, Escape/Entrée/Space cohérents, focus trap/restauration.
- Ces tests Playwright simulent le viewport et le zoom navigateur; ils ne prouvent pas la mise à l’échelle DPI native des écrans Windows. Le spike natif doit établir si l’échelle système 100/125/150 % et une configuration multi-écran peuvent être exercées dans le runner. Une checklist manuelle peut compléter le rapport, mais la couverture correspondante reste déclarée incomplète.

## Migration des suites existantes

Avant suppression, maintenir un tableau de traçabilité (ancien module/test → action utilisateur observable → spec E2E nouvelle → preuve). Associer chaque assertion comportementale à une action visible. Un calcul interne sans surface ou conséquence visible n’obtient pas un test d’implémentation déguisé en E2E; ses effets et invariants métier doivent être exercés par les scénarios UI/LCU correspondants.

| Ancienne suite | Destination E2E |
|---|---|
| API, account stats, context, config, profile config, history, network status | Parcours UI via vraie API; persistance temporaire et restart. API invalide/interdite et contrat vu par le navigateur sont des scénarios E2E, pas des appels TestClient. |
| champion picker, presets, skin modes, core champ select, game state, LCU runtime/client/region | Parcours Dashboard/presets/champion select raccordé au faux LCU par le driver réel; transitions et erreurs stateful. |
| LCU API routes, assets, static data, diagnostics, Data Dragon | Actions catalogue/asset/diagnostic depuis l’UI avec faux LCU et serveurs d’assets contrôlés à la frontière externe. |
| desktop, single instance, create_exe, release metadata | EXE Windows + WebView2 E2E pour les chemins utilisateur; conserver le self-test packagé smoke; version/signature/artifact restent des contrôles build/release. |
| datadragon_live, live_provider_audit | Déplacer les véritables probes vers un job manuel/opt-in explicitement nommé E2E Live. Supprimer leurs assertions unitaires ou helper-only; ne jamais solliciter le compte League de l’utilisateur en CI normale. |
| 17 tests Vitest | Remplacer les assertions visibles (Select, dialogs, route, erreurs API, texte, copies, asset fallback) par actions Playwright contre le serveur réel. Regrouper les interactions communes en scénarios par parcours, sans perdre leur comportement couvert. |
| `website/test/content.test.mjs` (supprimé) | Assertions migrées dans `website/e2e/site.spec.ts`: route exacte releases, ordre/identité des captures, descriptions complètes et assets chargés dans le rendu. Build et Playwright 13/13 avaient passé dans un run antérieur; pas de nouvelle preuve GitHub pour le SHA local modifié. |

Le snapshot frontend 137/138 en 18,2 min est antérieur aux derniers correctifs. Le dernier frontend complet passe **138/138 en 18,3 min**, y compris History, Diagnostics, Settings, LCU et layouts; le test Settings précédemment cité échouait uniquement pendant le teardown Windows. Les scénarios SET-05, SET-06, SET-10, SET-11, SET-12, HIST-01/02 et DIAG-01/02/03 sont donc exercés dans ce run. L’API complète passe 35/35 et l’intégration full-stack 1/1. Des gaps restent: variantes de recherche/erreur/retry pickers, cas rune/skin par slot/état, mutations LCU moins courantes, clipboard/export diagnostics en erreur et ouvertures provider/natives dépendant du shell. Le fallback de migration MainLoL est non destructif; la suite API couvre le mauvais champ `region`/`manual_region`. Le finding UX History sur endpoints et IDs bruts est confirmé et recommandé en suivi, sans bloquer cette migration E2E.

## Orchestration, livrables et dépendances

Ce document est le plan directeur. Les quatre inventaires spécialisés restent la source détaillée de leurs domaines et doivent être mis à jour par les agents concernés; ne recopier leurs tables complètes ici.

| Livrable | Périmètre faisant autorité | Dépendance / gate d’intégration |
|---|---|---|
| [Matrice des actions utilisateur](user-action-e2e-matrix.md) | ID de chaque action, états, couverture actuelle, priorité et critère d’acceptation | Base commune de tous les autres plans; chaque scénario E2E livré doit référencer un ou plusieurs ID. |
| [Inventaire frontend](frontend-e2e-migration.md) | Inventaire historique Vitest et mapping vers les specs React Playwright présentes; statut des gaps FE-* | L’ancien Vitest est déjà supprimé localement; maintenir distinction entre assertions migrées, non observables et à confirmer après un run navigateur vert. |
| [Inventaire Python](python-e2e-migration.md) | Inventaire historique des suites Python, contrats HTTP, persistance, LCU, desktop, EXE et checks live | Les anciens tests Python ont été supprimés localement. Les parcours sans UI sont candidats aux six configs API, filesystem isolé, process/EXE ou restent explicitement sans preuve. |
| [Audit CI/CD E2E-only](ci-e2e-only-migration.md) | Jobs, commandes, path filters, dépendances et état des checks GitHub | Suit l’échec DIAG-01 sur `89d8ac4`, puis le doublon CI `205d05d` qui a échoué sur l’ancienne assertion du timer et la correction locale désormais vérifiée par 138 tests. |

Les plans sont des inventaires et propositions; les modifications CI/manifests et suppressions ont été réalisées localement sous autorisation explicite. Leur présence ne prouve pas que la migration de comportement est complète. Un gap, un attendu-échec ou une action native passée en `skip` reste ouvert; le reviewer principal réconcilie les ID et les preuves avant de déclarer l’objectif atteint.

## Phases d’exécution et gates

Les phases 2, 3 et 4 peuvent avancer en parallèle après l’inventaire. La phase 5 précède la validation E2E de l’EXE. Les suppressions et modifications de runners sont déjà présentes localement, mais n’abaissent pas les gates produit ci-dessous.

1. **Inventaire et état initial — livrables présents.** Partir des plans liés et vérifier les changements locaux contre le SHA distant. Les plans et le checkout montrent maintenant la suppression des suites Python/Vitest/website Node et le retrait des runners correspondants. **Gate restante:** rapprocher chaque ancienne responsabilité des actions E2E ou d’une limite explicitement assumée; ne pas utiliser un historique de test supprimé comme preuve courante.
2. **Réconciliation exhaustive — partielle.** Les matrices actives ont été recalées sur les specs présentes; les suppressions ont toutefois précédé une validation E2E finale, donc certains invariants internes/desktop demeurent sans équivalent prouvé. Marquer séparément assertions purement internes, probes live, tests de workflow et cas dépendant d’un runner absent. **Gate:** pas de revendication de couverture exhaustive avant preuves réelles.
3. **E2E navigateur et parcours produit — passé localement.** `npx playwright test --workers=1` a passé 138/138 en 18,2 min; les cas timer, reconnexion et DIAG-01 ont chacun passé 10/10. Sur GitHub, un job pour `205d05d` a passé toutes les phases; son doublon a échoué uniquement sur l’ancienne assertion du timer, corrigée et repassée localement.
4. **E2E API / backend — passé localement.** `npm run test:e2e:api` a passé 35/35; `npx playwright test --config ../scripts/e2e/playwright.config.mjs --workers=1` a passé 1/1. Ces résultats locaux ne remplacent pas les checks GitHub du SHA publié.
5. **E2E shell natif Windows — gap bloquant.** Faire fonctionner le runner avec un bureau Windows interactif et WebView2; exercer vrai HWND/focus/fermeture, tray, raccourcis globaux, fenêtres providers et dialogs, avec profil jetable, isolation process/port et cleanup vérifiable. Toute action déclarée obligatoire doit échouer si elle est ignorée ou skip. **Gate:** répétition stable sous WebView2 réel et absence de processus zombie; Chromium ou une vérification JavaScript du bridge ne compte pas.
6. **E2E EXE / installateur — dépend de la phase 5.** L’EXE n’a pas été construit localement, car `build/` et `dist/` préexistants sont supprimés par le script de build; il a été omis pour ne pas supprimer ces données. Construire le vrai onedir EXE/installer dans un environnement propre puis le lancer dans `%APPDATA%`, `%LOCALAPPDATA%`, TEMP/TMP et ports temporaires; vérifier démarrage/arrêt, API intégrée, ressources, single-instance, navigation WebView2, mutations persistées après relance et raccourcis/tray/dialogs critiques. **Gate:** au moins les parcours P0 natifs prouvés sur l’artefact distribué, plus packaging/signature et logs/artifacts contrôlés. Le self-test `--allow-missing-webview2` reste uniquement un smoke headless et ne passe pas cette gate.
7. **E2E website — résultats distincts.** Build et Playwright 13/13 avaient passé lors d’un run antérieur; sur `89d8ac4`, les checks GitHub `Website CI / Build and Playwright` et `deploy` ont réussi.
8. **Suppression/runners — modifications locales présentes.** Les tests Python/Vitest/website Node, configs unitaires, dépendances exclusives, commandes et références actives de CI ont été retirés; restent compileall, Ruff, API check, typecheck, builds, security, package smoke et E2E. **Gate de vérification:** recherche globale sans runner unitaire actif et vérification de la cohérence manifest/lock/workflow; cette suppression ne signifie pas que tous les cas anciens ont un successeur E2E.
9. **Validation et publication du SHA final — en attente.** Exécuter les suites complètes et chaque job contre les modifications courantes, inspecter traces/artifacts, puis publier uniquement après autorisation distincte et vérifier les workflows GitHub du nouveau SHA. Les jobs Windows Playwright échoués sur `6b5c591` et les anciens checks d’un autre SHA ne valident pas les modifications locales; toute limite de runner ou feature sans preuve reste explicitement ouverte.

## Garde des frontières de validation

### Navigateur (React)

Le navigateur prouve les gestes DOM, keyboard, rendu, états et erreurs visibles sur le vrai build. Il peut interroger l’API réelle pour vérifier un effet, mais un success uniquement optimiste ne suffit pas. Les tests de layout couvrent les viewports listés plus haut; `deviceScaleFactor` ne prouve pas le DPI Windows.

### API (FastAPI/OpenAPI)

Les parcours ordinaires viennent du navigateur. Les six configs `scripts/e2e/*-api.config.mjs` dédiées couvrent les contrats que toutes les pages n’exposent pas (account, assets, diagnostics, mutations LCU, cache Data Dragon, validation/origines/WebSocket), et démarrent le vrai serveur. La dernière suite API passe 35/35 après l’ajout du cas où TOML est prioritaire sur les deux sources JSON. Garder la génération OpenAPI et comparer `frontend/src/generated/api.ts` avec `npm run api:check`; typecheck/build restent des contrôles statiques, pas des preuves d’intégration.

### Shell natif (source sous Windows)

Tester vrai pywebview/WebView2, HWND, tray, hooks clavier, bridge, processus/enfant, dialogs, URLs externes et géométrie dans un runner Windows interactif. Observer par l’environnement Windows réel, pas par DOM. Egress, lancement shell et fermeture de processus doivent rester isolés. Si runner ou dialogue n’est pas disponible, le comportement correspondant reste non couvert; pas de skip vert.

### EXE / installateur

Distinguer le build produit, le self-test du binaire et le test de parcours dans le binaire. Le test final lance l’EXE/installer construit, avec WebView2 installé et profil isolé; il ne modifie pas le profil réel de l’utilisateur. Exécuter navigation et actions critiques, persistance après fermeture/reprise, single-instance et shutdown; valider aussi chemins/assets depuis `_MEIPASS`/installation et permissions de dossier. Si CI ne peut exécuter la WebView interactive, l’EXE n’a pas passé la gate E2E, même si le self-test headless réussit.

### Website (projet séparé)

Le website possède sa propre dépendance, build, `vite preview` et job CI. Ses assertions ne couvrent aucune route de l’application. Build et E2E 13/13 ont passé dans un run antérieur, mais pas le dernier rerun frontend/API; les workflows appellent directement `npx playwright test --workers=1`. Vérifier ces jobs sur le prochain SHA. Garder l’egress contrôlé et ne suivre aucun lien qui démarre un vrai téléchargement.

## CI, checks GitHub et portée locale — état au 2026-09-30

État Git au 2026-09-30: branche `codex/react-fastapi-webview-migration`, dernier commit de code poussé `205d05d253bc39dff3aea68fcaea52f72cbbc236`, `origin/main` à `809d8567ee4755672b812cc63da46488c30a8ce8`. Le browser local passe 138/138 en 18,2 min; l’API 35/35 et full-stack 1/1 passent; timer, reconnexion et DIAG-01 ciblés passent chacun 10/10. Le run CI antérieur sur `89d8ac4` a signalé la course `pauseAt(new Date())`, corrigée dans `205d05d`. Sur ce SHA, un job Windows Playwright a passé toutes les phases et le doublon a échoué uniquement sur l’ancienne assertion timer; la recalibration dans le worktree n’est pas encore publiée. Le self-test package Windows passe en CI, sans validation de l’interface EXE interactive. Le runner natif historique échoue avant assertions tray avec `PermissionError [WinError 5]` dans pystray/Win32 `GetCursorPos`; pas de client League/WebView2 réel testé.


Les deux jobs GitHub Windows historiques ci-dessous échouaient avant les parcours produit, lors de la validation de l’isolation des chemins après le signal `ready` (`The E2E subprocess reported a path outside its isolated temporary profile.`). Le diagnostic Python rapportait la garde socket-egress vérifiée et les chemins isolés; le contrôle JavaScript refusait le résultat. La validation d’isolation a depuis été réparée dans le harness local; ces runs restent des échecs de l’ancien SHA `6b5c591`. Les logs historiques ne donnent pas la paire exacte de chemins divergente. Voir [job GitHub 36649696977](https://github.com/qurnt1/otp_lol/actions/runs/36649696977/job/109680720785) et [job GitHub 36649690569](https://github.com/qurnt1/otp_lol/actions/runs/36649690569/job/109680701069). Le run GitHub `89d8ac4` a échoué à DIAG-01; le correctif `205d05d` passe le browser local 138/138. Sur GitHub `205d05d`, un job Playwright a passé toutes les phases; le doublon a échoué à l’ancienne assertion timer, corrigée localement et repassée 10/10 plus un run complet 138/138. Website CI, deploy et self-test package ont réussi. Le runner natif historique échoue avant assertions tray avec WinError 5; l’EXE interactif et WebView2 réel ne sont pas validés.

Jobs concernés: [Windows Playwright, run 36649696977](https://github.com/qurnt1/otp_lol/actions/runs/36649696977/job/109680720785) et [Windows Playwright, run 36649690569](https://github.com/qurnt1/otp_lol/actions/runs/36649690569/job/109680701069).

Disposition CI détaillée dans [le plan CI](ci-e2e-only-migration.md): le tree courant ne contient plus les runners pytest/unittest/Vitest/node:test ni leurs dépendances dédiées; les workflows conservent compileall/Ruff, API check, typecheck, builds, audits sécurité, package smoke et E2E. Les vérifications locales passent: build frontend, api check, compileall, Ruff du harness, UI 138/138, API 35/35, full-stack 1/1 et DIAG-01/timer/reconnexion répétés 10/10. Le run GitHub de `89d8ac4` a révélé la course DIAG-01, corrigée dans `205d05d`; un des deux jobs Windows Playwright de ce SHA a passé toutes phases, l’autre a échoué à l’ancienne assertion timer. La correction timer locale a repassé le browser complet. Les routes interceptées injectent des pannes pour vérifier la récupération UI; elles ne prouvent pas qu’une réponse d’erreur provient du FastAPI réel.

`requirements-test.txt`, `pytest`, Vitest, jsdom et Testing Library ont été retirés après suppression des suites; `httpx` n’est plus épinglé uniquement pour l’ancien test de metadata. `unittest.mock` dans `src/desktop/self_test.py` est une bibliothèque utilisée par le self-test packagé, pas un runner de suite unittest: garder ce fichier, `--self-test`, signing, versions/checksums et package smoke. Les documents d’historique peuvent citer les anciens runners pour décrire le baseline, mais les commandes actives/docs courants doivent refléter les workflows actuels.

## Critères d’acceptation

1. Chaque contrôle visible, route, changement de réglage, dialogue, action native et CTA website dans la matrice renvoie vers au moins un identifiant de test E2E et une assertion sur l’effet utilisateur; aucun scénario produit n’est couvert uniquement en modifiant le store.
2. La suite application charge le vrai frontend compilé et le vrai FastAPI sur loopback. Un runner de processus transmet à Playwright l’URL réellement démarrée via `OTP_E2E_BASE_URL`; aucun Vite sur `4173`, aucune réutilisation d’un serveur étranger, aucun backend faux et aucun WebSocket interne remplacé. Les parcours UI ordinaires appellent le vrai FastAPI; seules les assertions de récupération ciblées interceptent temporairement les routes listées dans le statut afin d’injecter une panne/réponse d’erreur. Elles ne comptent pas comme preuve de réponse serveur et sont complétées par les six suites HTTP API réelles.
3. Les variables `APPDATA`, `LOCALAPPDATA`, `TEMP` et `TMP` sont définies dans le sous-processus avant tout import applicatif; chaque chemin persistant/cache observé pointe dans le profil temporaire dédié. Les scénarios de settings, presets et historique vérifient l’état après une nouvelle requête et une relance; ils ne déduisent pas la persistance d’une réponse optimistic seule.
4. Les scénarios LCU documentent séparément le scan non filtré du PID synthétique, le filtrage de sécurité appliqué au Connector, et le chemin protocolaire. Le faux serveur local reçoit le vrai handshake, requêtes et mutations; événements reviennent via WSS de production. Le filtre `lcu_driver.utils.process_iter` reste isolé au sous-processus et ne prouve pas le choix du bon client sur une machine League réelle.
5. Le spike Windows natif est une gate de migration et aboutit à une preuve automatisée répétable pour fenêtre WebView2 et actions non-DOM demandées. Les parcours impossibles à automatiser restent officiellement incomplets; un gate manuel n’est pas présenté comme satisfaisant l’objectif E2E-only. Les limites matérielles (DPI réel, League réel) et contenu tiers live sont identifiées séparément.
6. La suite E2E régulière ne fait aucun appel public (Data Dragon, CommunityDragon, provider, GitHub ou autre). L’egress public est bloqué, les données synthétiques nécessaires sont en cache/fixtures, et l’absence de requêtes publiques est vérifiée. Les probes live éventuelles restent opt-in et ne portent pas sur un compte utilisateur en CI.
7. Aucun runner de suite unitaire actif ne reste dans les manifests, scripts ou commandes CI du tree local. Les commandes comportementales restantes sont Playwright E2E; les occurrences historiques dans des archives/plans décrivent l’ancien baseline. `unittest.mock` dans le self-test package est un usage runtime, pas un runner de tests. Les dépendances seulement dues aux unités sont retirées; les dépendances E2E sont déclarées. La gate reste incomplète tant que les E2E ne sont pas verts et les parcours natifs/EXE ne sont pas validés.
8. Exécuter les contrôles statiques et vérifier que l’OpenAPI généré correspond. Servir le build website sous `vite preview` et valider ses interactions avec Playwright. Faire passer de vrais parcours Windows/WebView2 dans l’application EXE empaquetée avec un profil temporaire, en plus du build, de la signature et du self-test package. Un package smoke headless ne remplace pas le parcours dans l’EXE.
9. Une action E2E échoue avec capture/trace, log FastAPI/LCU et identifiant de scénario; tout serveur, certificat, dossier et processus temporaire est nettoyé sans toucher aux données locales.
10. Les agents ne suppriment pas les anciens tests avant leur mapping; ils n’ajoutent pas de fonctions de test à l’API de production sans revue sécurité explicite.
11. Le rapport final indique les lignes de la matrice qui restent sans preuve automatisée. Tant qu’une action demandée ou le spike natif ne passe pas, la migration et l’objectif de couverture exhaustive sont déclarés incomplets.

## Risques et limites à suivre

- **Couverture coûteuse/flaky :** remplacer les assertions de fonction pure par des flows longs peut ralentir les PR. Atténuer avec un fixture full-stack réutilisé, des tests indépendants, peu d’attentes arbitraires, traces d’échec, état isolé et tiers smoke/full/nightly sans omettre les parcours P0.
- **Tests simulés sous étiquette E2E :** si toutes les réponses locales restent interceptées, le problème actuel reste. Seules les dépendances réellement externes et la frontière LCU contrôlée peuvent être simulées.
- **Découverte LCU partielle :** le scanner non filtré trouve le PID de la copie synthétique et `Connection` valide le parsing; le Connector reçoit ensuite une liste de processus filtrée via `lcu_driver.utils.process_iter`. Cela protège du League réel pendant l’E2E et exerce le vrai transport, mais ne prouve pas la sélection du bon client sur une machine où plusieurs candidats League existent.
- **Data Dragon et sorties Internet :** la donnée de catalogue peut rafraîchir après un événement de statut réseau et plusieurs URL sont codées en dur. Précharger les caches synthétiques et bloquer l’egress public au runner; prouver qu’aucun appel ne sort, plutôt que déclarer « pas d’Internet requis » sans inspection.
- **Desktop en CI :** un runner Windows non interactif peut compiler WebView2 mais ne pas fournir un bureau utilisable. C’est le premier spike obligatoire. Distinguer « binaire compile/self-test réussi » de « fenêtre utilisateur réellement pilotée »; si le second manque, objectif demandé non atteint.
- **Variables à l’import :** les chemins AppData/cache sont calculés dès l’import (`src/config/paths.py`) et l’objet FastAPI global est construit à l’import (`src/api/app.py`). Tout isolement qui définit APPDATA/TEMP après ces imports est faux; utiliser le sous-processus et auditer ses chemins résolus.
- **Pointeurs de cache legacy sans `identity_key` — comportement fail-closed délibéré:** les E2E ciblés validés couvrent cache summary et matches après restart, changement de compte et identité provider manuelle distincte. `offline restart does not attribute an unaliased legacy cache pointer to an account` vérifie le refus du pointeur ancien afin de ne pas associer ses données au mauvais compte. Conséquence connue: les anciens stats offline restent indisponibles jusqu’à une lecture connectée qui réécrit un pointeur avec `identity_key`; ce cas reste une limite de compatibilité à documenter pour les utilisateurs.
- **Schémas Settings malformés/futurs — E2E exécutés:** les tests couvrent migration schema 2/3, préservation source pour marqueurs malformés/futurs, import UI sans perte des valeurs actuelles et priorité TOML sur les deux sources JSON. Le frontend complet passe 138/138 et l’API complète 35/35.
- **Compatibilité historique `MainLoL` — correction ciblée vérifiée:** le fallback de migration depuis l’ancien dossier est implémenté sans écraser les données legacy. La suite API passe 35/35 et `startup migrates an isolated MainLoL settings profile and keeps its backup across restart` passe 1/1. Le mismatch `region` vers `manual_region` est corrigé; le test vérifie que `manual_region: "na"` prime sur l’ancien alias `region: "euw"`. L’absence de cette compatibilité sur `origin/main` reste un écart historique; les contrôles statiques et le self-test package de `89d8ac4` sont verts. Le run browser de ce SHA avait un échec distinct DIAG-01, corrigé dans `205d05d`.
- **Détails History bruts — finding UX confirmé, non bloquant:** `frontend/src/features/history/HistoryPage.tsx:50-64` affiche les paires détail clé/valeur; les noms techniques d’endpoint et identifiants bruts sont visibles et recherchables. Recommandation: suivi produit pour présenter des libellés orientés utilisateur et masquer les identifiants inutiles. Cela n’empêche pas le fonctionnement et n’est pas un blocker release.
- **Périmètre E2E-only :** les unités qui valident de nombreuses entrées internes ne gardent plus leurs tests exhaustifs; couvrir les variantes qui correspondent à des actions/états utilisateur. Garder typecheck, Ruff, compileall, schémas Pydantic/OpenAPI et audits comme gardes non comportementaux.
- **Réseau tiers :** ne pas rendre la CI dépendante de Cloudflare, GitHub Releases, Data Dragon ou d’un site provider live. Les probes en ligne ne remplacent pas les scénarios déterministes et ne doivent pas renseigner PII.
- **Site de présentation :** son build et son E2E ne valident aucune route de l’application OTP LOL; les séparer dans CI et la matrice.

## Découpage recommandé pour les agents

1. **Agent harness/backend E2E :** spike démarrage API et vrai flux LCU avec faux client, répertoires temporaires, lifecycle, logs et cleanup. Ne touche pas aux composants UI.
2. **Agent parcours frontend :** migration et complétion des scénarios Dashboard, presets, settings, History, Statistics/Live, diagnostics et réseau sur le harness partagé. Ne touche pas aux workflows ni aux dépendances.
3. **Agent desktop/release :** parcours EXE/WebView2, fenêtre, tray, raccourcis, providers et packaging sous Windows; explicite les gates matériels. Ne touche pas à la suite browser des autres domaines.
4. **Agent website/CI/docs :** E2E du site, suppression coordonnée des runners/dépendances unitaires et adaptation CI/guides, après signal que les scénarios de remplacement sont verts.
5. **Reviewer red team indépendant :** inspecte que les tests locaux ne sont pas interceptés, que les assertions couvrent les effets persistés/LCU et que chaque ligne de matrice a une preuve. Challenger particulièrement reset/import, identité privée, double clic, lifecycle et E2E desktop.

Un agent d’intégration garde la propriété du tableau de traçabilité et arbitre les modifications manifest/workflow partagées pour éviter les conflits entre agents.
