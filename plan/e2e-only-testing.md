# Plan de migration vers des tests E2E uniquement

## Objectif et périmètre

Remplacer tous les tests unitaires actuels par une suite de tests de bout en bout qui pilote les parcours visibles d’OTP LOL. La suite doit traverser l’interface React, la vraie API FastAPI, la persistance et, quand le parcours le requiert, l’intégration au protocole LCU ou au shell Windows.

Le périmètre couvre l’application desktop, son frontend, son backend et le site de présentation séparé sous website/. Les vérifications statiques et les contrôles de packaging restent en place. Cette migration ne demande ni modification de fonctionnalité produit ni refonte architecturale.

Ce document suit la migration en cours. Les suites unitaires Python (27 modules et leur faux serveur LCU), Vitest (17 fichiers) et le test website `node:test` ont été supprimés du tree local, avec leurs runners et dépendances dédiées. Cette suppression ne démontre pas que chaque ancienne assertion possède un équivalent E2E. Les runs locaux coordonnés ont passé le navigateur **130/130**, les six configs API **23/23**, l’intégration full-stack **1/1** et le website **13/13 dans une copie isolée**. Le runner natif passe le clic Settings puis échoue sur un état Auto-Ban périmé/incohérent entre l’UI et le tray; le cleanup est complet et les scénarios suivants ne tournent pas. L’EXE interactif n’a pas été testé. Les modifications locales restent non commit/non poussées et ne sont pas couvertes par les checks GitHub attachés à `e5e61c7`.

## Statut réel au 2026-09-30

Le harness `scripts/e2e/app_server.py`, `fake_lcu.py` et `appServer.mjs` sert le build React via le vrai FastAPI, isole les chemins utilisateur sous un profil temporaire, et dirige les transports HTTP/TLS/WSS du vrai `lcu-driver` vers un faux client League pilotable. Les requêtes ordinaires des specs navigateur vont au vrai serveur et le WebSocket applicatif n’est pas remplacé. Plusieurs tests utilisent toutefois `page.route` pour injecter explicitement des scénarios de panne/réponse: `/api/network/status`, `/api/history`, `/api/champions`, `/api/presets/pick_1`, `/api/assets/skins/86/86013/splash*` et `/api/settings`. Ces tests valident la réaction UI à une panne ou un rejet et ne prouvent pas que FastAPI émet cette réponse. Les six configs API dédiées, qui démarrent le vrai FastAPI et vérifient ses réponses, sont maintenant regroupées séparément. Les dépendances externes (Data Dragon et GitHub Releases) sont contrôlées au boundary réseau Python.

La fixture `otpApp` vient d’être passée en scope test après avoir confirmé des fuites d’état entre tests (état réseau, catalogues LCU, runes). Chaque test reçoit un serveur/profil isolé; le redémarrage avec le même profil reste dans le test d’intégration dédié. Les états réseau sont configurés avant la première navigation et `/api/network/check` est appelé explicitement. Le coût de cette isolation n’a pas encore été mesuré.

Le run complet courant de la suite navigateur est **130/130 passé**, après correction du sélecteur. Les six configurations API ont passé **23/23** au total, et `scripts/e2e/app.integration.spec.mjs` a passé **1/1**. Ces résultats viennent des exécutions locales coordonnées; ils ne sont pas des checks GitHub du tree non poussé. Les anciens résultats 115/117 et 9/10 décrivent des états historiques du harness.

`scripts/e2e/app.integration.spec.mjs` couvre un scénario full-stack de persistance après restart, WSS/LCU, déconnexion/reconnexion, identité, données statiques, updates et cleanup; le run courant a passé **1/1**. Le workflow local séquence le navigateur, cette intégration et `npm run test:e2e:api`; les modifications locales du workflow n’ont pas encore été exécutées par GitHub Actions.

La couverture native reste incomplète. Au dernier run source Windows, le clic souris ouvre Settings; la lecture depuis le Dashboard confirme `presets_enabled=true` et `auto_ban_enabled=false`, mais l’entrée Auto-Ban du menu pystray reste désactivée et l’assertion échoue. Le cleanup est complet. Les scénarios placés après cette assertion ne tournent pas, donc ce run ne donne aucune preuve de fullscreen, hotkeys, providers, dialogs ou fin du parcours. Le faux client couvre le transport et les mutations après injection d’un lockfile, pas la découverte réelle du processus League.

Le site possède ses specs Playwright et une config `vite preview`; `website/test/content.test.mjs` et le script `test: node --test` ont été supprimés. Dans une copie isolée, le build et les **13 tests E2E** ont passé. Les assertions vérifient le lien releases, les IDs/labels/titres/alt/notes des captures et le chargement des assets dans le site rendu. Une invocation npm a affiché deux workers; `deploy-website.yml` et `website-ci.yml` lancent maintenant directement `npx playwright test --workers=1`. Cette preuve locale n’est pas un check GitHub des workflows non poussés.

### Tests et commandes actuels

| Surface | Fichiers / commande | Ce que cela couvre aujourd’hui |
|---|---|---|
| Python | Aucun `tests/test_*.py`, `tests/fake_lcu_server.py` ni `requirements-test.txt` dans le tree local | Les workflows gardent `compileall` et Ruff comme contrôles statiques; aucune commande pytest/unittest active. Une part des anciens invariants internes n’a pas de parcours observable équivalent. |
| React / TypeScript | Aucun `frontend/src/**/*.test.ts(x)`, Vitest, jsdom ou Testing Library | `npm test`/Vitest retiré; API OpenAPI, typecheck et build restent dans le job statique. Le comportement est couvert seulement lorsqu’une spec E2E actuelle l’exerce. |
| Frontend E2E | `frontend/e2e/`, `scripts/e2e/app.integration.spec.mjs`, `npm run test:e2e`, `npm run test:e2e:api` | Playwright sur build React/FastAPI réel et faux LCU. Run local courant: navigateur 130/130, API 23/23, full-stack 1/1. Le runner natif échoue séparément sur Auto-Ban tray. |
| Website | `website/e2e/site.spec.ts`, `npm run build`, Playwright | Le fichier `website/test/content.test.mjs` et `npm test` sont supprimés; les assertions sont migrées vers Playwright. Build et 13/13 E2E ont passé dans une copie isolée. Les workflows utilisent directement `npx playwright test --workers=1`; aucun check GitHub ne couvre encore les changements locaux. |

Commandes actives dans les workflows locaux :

- Python CI : installation des dépendances runtime, compileall des sources livrées et Ruff; aucun runner de tests.
- Release : typecheck/build, compileall, OpenAPI, Playwright navigateur avec un worker, six suites API avec un worker par config, puis build/signature/self-test/installateur.
- Frontend CI : le job statique exécute `api:check`, typecheck et build. Le job Windows construit le frontend puis exécute Playwright navigateur, le smoke intégré et six configs API de façon sérielle. Le nom de check `Frontend CI / Unit and build` est conservé pour stabilité, bien qu’aucun test unitaire n’y tourne.
- Site : `website-ci.yml` et le workflow Pages exécutent `npm ci`, le build puis Playwright sur `vite preview`; les deux anciennes assertions `node:test` ont été migrées et le script `npm test` supprimé.
- Vérifications statiques existantes : compileall, Ruff, TypeScript, build Vite, génération OpenAPI avec api:check, pip-audit/npm audit, CodeQL et Gitleaks.

`npm run test:e2e:api` exécute dans l’ordre `account-api`, `asset-api`, `diagnostics-api`, `lcu-automation-api`, `datadragon-cache-api`, `api-contract`, chaque configuration avec `--workers=1`. Le navigateur E2E inclut des routes simulées qui forcent certaines pannes/rejets UI; ces scénarios ne doivent pas être confondus avec les tests HTTP E2E sur le FastAPI réel.

### Limites et défauts confirmés

`frontend/e2e/history.spec.ts` sépare trois preuves. Un test normal vérifie le POST réel `ready-check/accept` au faux LCU et que `/api/history` contient `Match automatically accepted.`. Un second monte History avant l’événement et injecte une réponse ciblée via `page.route("**/api/history")` pour l’attendu-échec de mise à jour DOM live; ce test de réaction navigateur ne prouve pas le résultat produit par FastAPI. Le troisième conserve la suppression après confirmation. Le bug de rafraîchissement live après ready-check demeure rapporté, avec `staleTime` de 15 s; il doit être revalidé après le run final de la suite.

`frontend/e2e/ui-smoke.spec.ts` sépare aussi le parcours normal de l’attendu-échec ciblé. Le smoke navigation/pickers/settings/ready-check/history est un test normal qui ignore uniquement la violation CSP connue lorsqu’il vérifie les erreurs console, et échoue sur toute autre erreur, `pageerror` ou requête échouée. Le test distinct ouvre la page, puis marque l’attendu-échec seulement avant de vérifier les flags initialisés par le script inline. La trace montre que le CSP FastAPI `script-src 'self'` bloque ce script dans `frontend/index.html`, qui définit `window.__otpDesktopMode` / `window.__otpNativeBridgeReady`. Ne pas élargir le CSP sans examen produit/sécurité.

Les six snapshots Dashboard précédents ne sont pas encore une preuve d’une régression visuelle : les captures réelles étaient faites client LCU connecté avec placeholders, alors que les baselines étaient hors ligne avec assets chargés et des presets issus d’une fixture historique. Le scénario est maintenant aligné pour charger Data Dragon, vérifier le transport LCU déconnecté avant `page.goto`, et vider l’identité détectée. Reprendre les captures après revue; ne mettre à jour les baselines qu’après comparaison des états et assets.

Un screenshot WebView à 1086×753 a été signalé avec le CTA « Réessayer maintenant » coupé à droite. Le test Playwright géométrique vérifie le bouton et la bannière dans le viewport et a passé le run complet précédent; le défaut n’est donc pas reproduit dans Chromium à ce stade. Vérifier sur WebView/DPI réel avant de conclure à une anomalie native, sans changer le produit dans cette tâche.

Le seam LCU conserve le vrai `Connector`, `Connection`, HTTP/TLS/WSS et le traitement des événements après injection de lockfile synthétique via `lcu_driver.connector._return_ux_process`. Il ne valide pas la découverte réelle de `LeagueClientUx` ni l’extraction des paramètres du processus. La lecture du vrai League, du shell natif, du tray, des raccourcis globaux et des dialogues reste une frontière séparée.

## Architecture cible de test

### 1. Parcours E2E application en CI

1. Installer les dépendances runtime Python et Node prévues, puis compiler `frontend/dist` de production.
2. Chaque test utilise la fixture `otpApp` de `frontend/e2e/helpers.ts` (scope test), qui démarre `scripts/e2e/app_server.py` avec un port loopback et un profil temporaire. La page reçoit l’URL annoncée par le helper; la config Playwright ne démarre pas Vite et ne réutilise pas de serveur préexistant.
3. Piloter le vrai bundle et la vraie API FastAPI via Chromium. Les routes `/api/**` et `/api/events` ne sont pas simulées. Le seul abort navigateur ciblé est `/api/network/status` dans le scénario qui vérifie la panne de transport; les réponses normales proviennent du vrai endpoint.
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

**État du runner natif source : échec avec finding UI confirmé.** Le run passe l’ouverture de Settings par clic souris, relit depuis le Dashboard `presets_enabled=true` et `auto_ban_enabled=false`, puis échoue car l’entrée Auto-Ban du menu pystray reste désactivée. Le cleanup est complet. Les scénarios placés après l’assertion ne s’exécutent pas; fullscreen, hotkeys, providers, dialogs et fin du parcours ne sont donc pas validés par ce run. L’interaction native de l’EXE reste non testée.

Après réussite du spike, lancer l’EXE onedir dans le profil APPDATA/LOCALAPPDATA/TEMP/TMP isolé, piloter sa vraie WebView/native window et vérifier démarrage, contenu servi par FastAPI, navigation, fenêtres provider, tray, raccourcis, dialogues, fermeture et persistance. Utiliser uniquement des données et comptes synthétiques. Ne jamais pointer le test vers le vrai `%APPDATA%\OTP LOL`. Le self-test packagé est un smoke sans UI, il ne remplace aucune action native. Si certains contrôles natifs restent impossibles à automatiser dans l’environnement autorisé, les noter comme couverture E2E incomplète et le signaler comme objectif non atteint; le test manuel ne satisfait pas la demande « E2E uniquement ».

Conserver le self-test packagé actuel comme contrôle des ressources, API embarquée et écriture/lecture temporaire. Il complète le parcours UI Windows, mais ne le remplace pas. Toute validation manuelle documentée peut décrire une limite ou apporter un complément; elle ne valide pas l’objectif E2E et ne transforme pas les parcours natifs non automatisés en couverture réussie.

### 3. Site de présentation

`website/test/content.test.mjs` et son script `npm test` sont supprimés. `website/e2e/site.spec.ts` couvre navigation, skip-link, sélection et descriptions des captures, assets rendus, dialogues, liens sûrs, images/alt et overflow de plusieurs viewports. Le build local et Playwright ont passé 13/13. `deploy-website.yml` et `website-ci.yml` lancent directement `npx playwright test --workers=1` avant l’upload ou la conclusion du job PR. Ces modifications restent locales et les workflows n’ont pas encore été exécutés par GitHub Actions. Le site reste distinct du frontend desktop.

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
| Compte | Basculer auto/manuelle, saisir Riot ID et région, sauvegarder, validation/saisie incorrecte, région-plateforme cohérente, identité LCU connectée, dernier compte complet offline, absence de compte, copier après confirmation, permission/échec clipboard, oublier après confirmation, annuler; les préférences manuelles ne doivent pas être altérées par l’oubli. |
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
| `website/test/content.test.mjs` (supprimé) | Assertions migrées dans `website/e2e/site.spec.ts`: route exacte releases, ordre/identité des captures, descriptions complètes et assets chargés dans le rendu. Build + Playwright 13/13 passent localement. |

Les 13 specs Playwright frontend ont passé le run courant 130/130 après isolation test-scope. Il reste des gaps observables: variantes de recherche/erreur/retry pickers, tous les cas rune/skin selon slot/état, mutations LCU moins courantes, variantes compte/reset/import, erreurs/clipboard/export diagnostics et ouvertures provider/natives dépendant du shell. Les suites API et l’intégration full-stack ont aussi passé 23/23 et 1/1; ces résultats ne remplacent pas les branches internes supprimées sans sortie observable.

## Orchestration, livrables et dépendances

Ce document est le plan directeur. Les quatre inventaires spécialisés restent la source détaillée de leurs domaines et doivent être mis à jour par les agents concernés; ne recopier leurs tables complètes ici.

| Livrable | Périmètre faisant autorité | Dépendance / gate d’intégration |
|---|---|---|
| [Matrice des actions utilisateur](user-action-e2e-matrix.md) | ID de chaque action, états, couverture actuelle, priorité et critère d’acceptation | Base commune de tous les autres plans; chaque scénario E2E livré doit référencer un ou plusieurs ID. |
| [Inventaire frontend](frontend-e2e-migration.md) | Inventaire historique Vitest et mapping vers les specs React Playwright présentes; statut des gaps FE-* | L’ancien Vitest est déjà supprimé localement; maintenir distinction entre assertions migrées, non observables et à confirmer après un run navigateur vert. |
| [Inventaire Python](python-e2e-migration.md) | Inventaire historique des suites Python, contrats HTTP, persistance, LCU, desktop, EXE et checks live | Les anciens tests Python ont été supprimés localement. Les parcours sans UI sont candidats aux six configs API, filesystem isolé, process/EXE ou restent explicitement sans preuve. |
| [Audit CI/CD E2E-only](ci-e2e-only-migration.md) | Jobs, commandes, path filters, dépendances et état des checks GitHub | Décrit le tree local sans runners unitaires et distingue le SHA distant validé de la migration locale qui n’a pas encore tourné sur GitHub. |

Les plans sont des inventaires et propositions; les modifications CI/manifests et suppressions ont été réalisées localement sous autorisation explicite. Leur présence ne prouve pas que la migration de comportement est complète. Un gap, un attendu-échec ou une action native passée en `skip` reste ouvert; le reviewer principal réconcilie les ID et les preuves avant de déclarer l’objectif atteint.

## Phases d’exécution et gates

Les phases 2, 3 et 4 peuvent avancer en parallèle après l’inventaire. La phase 5 précède la validation E2E de l’EXE. Les suppressions et modifications de runners sont déjà présentes localement, mais n’abaissent pas les gates produit ci-dessous.

1. **Inventaire et état initial — livrables présents.** Partir des plans liés et vérifier les changements locaux contre le SHA distant. Les plans et le checkout montrent maintenant la suppression des suites Python/Vitest/website Node et le retrait des runners correspondants. **Gate restante:** rapprocher chaque ancienne responsabilité des actions E2E ou d’une limite explicitement assumée; ne pas utiliser un historique de test supprimé comme preuve courante.
2. **Réconciliation exhaustive — partielle.** Les matrices actives ont été recalées sur les specs présentes; les suppressions ont toutefois précédé une validation E2E finale, donc certains invariants internes/desktop demeurent sans équivalent prouvé. Marquer séparément assertions purement internes, probes live, tests de workflow et cas dépendant d’un runner absent. **Gate:** pas de revendication de couverture exhaustive avant preuves réelles.
3. **E2E navigateur et parcours produit — run courant vert, répétabilité restante.** Le browser a passé 130/130. **Gate:** répéter après gel final, investiguer tout nouvel échec, et maintenir les assertions sur UI + API/LCU + persistance.
4. **E2E API / backend — run courant vert, répétabilité restante.** `npm run test:e2e:api` a passé les six configs en 23/23 au total; elles démarrent le vrai FastAPI et utilisent des dépendances LCU/Data Dragon synthétiques. **Gate:** répéter après changement des specs, harness ou workflow; ces tests ne remplacent pas les gestes UI.
5. **E2E shell natif Windows — gap bloquant.** Faire fonctionner le runner avec un bureau Windows interactif et WebView2; exercer vrai HWND/focus/fermeture, tray, raccourcis globaux, fenêtres providers et dialogs, avec profil jetable, isolation process/port et cleanup vérifiable. Toute action déclarée obligatoire doit échouer si elle est ignorée ou skip. **Gate:** répétition stable sous WebView2 réel et absence de processus zombie; Chromium ou une vérification JavaScript du bridge ne compte pas.
6. **E2E EXE / installateur — dépend de la phase 5.** Construire le vrai onedir EXE/installer puis le lancer dans `%APPDATA%`, `%LOCALAPPDATA%`, TEMP/TMP et ports temporaires; vérifier démarrage/arrêt, API intégrée, ressources, single-instance, navigation WebView2, mutations persistées après relance et raccourcis/tray/dialogs critiques. **Gate:** au moins les parcours P0 natifs prouvés sur l’artefact distribué, plus packaging/signature et logs/artifacts contrôlés. Le self-test `--allow-missing-webview2` reste uniquement un smoke headless et ne passe pas cette gate.
7. **E2E website — validation locale passée, GitHub en attente.** Build et Playwright ont passé 13/13. Les workflows appellent directement le runner Playwright avec un worker; le workflow PR et Pages doivent encore tourner contre un nouveau SHA.
8. **Suppression/runners — modifications locales présentes.** Les tests Python/Vitest/website Node, configs unitaires, dépendances exclusives, commandes et références actives de CI ont été retirés; restent compileall, Ruff, API check, typecheck, builds, security, package smoke et E2E. **Gate de vérification:** recherche globale sans runner unitaire actif et vérification de la cohérence manifest/lock/workflow; cette suppression ne signifie pas que tous les cas anciens ont un successeur E2E.
9. **Validation et publication du SHA final — en attente.** Exécuter les suites complètes et chaque job contre les modifications courantes, inspecter traces/artifacts, puis publier uniquement après autorisation distincte et vérifier les workflows GitHub du nouveau SHA. Les checks verts sur `e5e61c7` ne valident aucune modification locale; toute limite de runner ou feature sans preuve reste explicitement ouverte.

## Garde des frontières de validation

### Navigateur (React)

Le navigateur prouve les gestes DOM, keyboard, rendu, états et erreurs visibles sur le vrai build. Il peut interroger l’API réelle pour vérifier un effet, mais un success uniquement optimiste ne suffit pas. Les tests de layout couvrent les viewports listés plus haut; `deviceScaleFactor` ne prouve pas le DPI Windows.

### API (FastAPI/OpenAPI)

Les parcours ordinaires viennent du navigateur. Les six configs `scripts/e2e/*-api.config.mjs` dédiées couvrent les contrats que toutes les pages n’exposent pas (account, assets, diagnostics, mutations LCU, cache Data Dragon, validation/origines/WebSocket), et démarrent le vrai serveur. Le run local courant a passé 23/23. Garder la génération OpenAPI et comparer `frontend/src/generated/api.ts` avec `npm run api:check`; typecheck/build restent des contrôles statiques, pas des preuves d’intégration.

### Shell natif (source sous Windows)

Tester vrai pywebview/WebView2, HWND, tray, hooks clavier, bridge, processus/enfant, dialogs, URLs externes et géométrie dans un runner Windows interactif. Observer par l’environnement Windows réel, pas par DOM. Egress, lancement shell et fermeture de processus doivent rester isolés. Si runner ou dialogue n’est pas disponible, le comportement correspondant reste non couvert; pas de skip vert.

### EXE / installateur

Distinguer le build produit, le self-test du binaire et le test de parcours dans le binaire. Le test final lance l’EXE/installer construit, avec WebView2 installé et profil isolé; il ne modifie pas le profil réel de l’utilisateur. Exécuter navigation et actions critiques, persistance après fermeture/reprise, single-instance et shutdown; valider aussi chemins/assets depuis `_MEIPASS`/installation et permissions de dossier. Si CI ne peut exécuter la WebView interactive, l’EXE n’a pas passé la gate E2E, même si le self-test headless réussit.

### Website (projet séparé)

Le website possède sa propre dépendance, build, `vite preview` et job CI. Ses assertions ne couvrent aucune route de l’application. Build + 13/13 E2E ont passé localement; les workflows appellent directement `npx playwright test --workers=1` après qu’une invocation npm a lancé deux workers malgré le flag fourni. Vérifier ces jobs sur le prochain SHA. Garder l’egress contrôlé et ne suivre aucun lien qui démarre un vrai téléchargement.

## CI, checks GitHub et portée locale — état au 2026-09-29

La branche est `codex/react-fastapi-webview-migration`, `HEAD` local et `origin/codex/react-fastapi-webview-migration` pointent sur `e5e61c7b39d805656fc56b50391a52c74fa11eae`; `origin/main` est `809d8567ee4755672b812cc63da46488c30a8ce8`. PR #11 a des checks GitHub terminés au SHA `e5e61c7`, tous avec la conclusion **success**: Python CI, Frontend CI Unit and build, Frontend CI Playwright Windows, package smoke, CodeQL Python/JS, dependency audit, secret scan et les jobs Pages retournés. La recherche de checks ne retourne aucun job en échec sur ce SHA, donc aucun échec courant ne peut être expliqué à partir de logs.

Sources des checks pour vérification: [Frontend CI run](https://github.com/qurnt1/otp_lol/actions/runs/36485684899), [Python CI run](https://github.com/qurnt1/otp_lol/actions/runs/36485684762), [package smoke run](https://github.com/qurnt1/otp_lol/actions/runs/36485684826), [Security checks run](https://github.com/qurnt1/otp_lol/actions/runs/36485684843), [Pages run](https://github.com/qurnt1/otp_lol/actions/runs/36485675764). Les jobs antérieurs répertoriés au même SHA sont aussi en succès. Cette preuve décrit seulement le contenu poussé de `e5e61c7`.

Le tree local comporte des modifications non commit non présentes dans ce SHA: workflows frontend/python/release/website, specs/helpers Playwright, scripts de harness, manifests/lockfiles, docs et plans. Le nouveau workflow Website CI n’a donc aucun check GitHub attaché, et aucun changement local n’est validé par les checks listés ci-dessus. Les exécutions locales coordonnées ont passé browser 130/130, API 23/23, full-stack 1/1 et website 13/13; le runner natif échoue sur Auto-Ban tray avec cleanup complet, et les assertions suivantes ne tournent pas. Ces preuves locales ne constituent pas une CI verte du tree complet.

Disposition CI détaillée dans [le plan CI](ci-e2e-only-migration.md): les runners pytest/unittest/Vitest/node:test et leurs dépendances dédiées ne sont plus actifs dans le tree local. Les workflows conservent compilation/Ruff, API check, typecheck, builds, audits sécurité, package smoke et E2E. Le job Windows appelle le navigateur, l’intégration full-stack et les six configs API; les résultats locaux sont respectivement 130/130, 1/1 et 23/23. Le runner natif échoue sur Auto-Ban tray malgré les réglages UI confirmés, cleanup terminé, et les assertions suivantes ne tournent pas; l’EXE interactif reste non validé. Le website a passé build + 13/13 localement, sans check GitHub sur les modifications locales. Les interceptions de pannes navigateur concernent les routes `/api/network/status`, `/api/history`, `/api/champions`, `/api/presets/pick_1`, `/api/assets/skins/86/86013/splash*` et `/api/settings`; elles vérifient les états de récupération UI, et non une réponse d’erreur produite par le vrai FastAPI.

`requirements-test.txt`, `pytest`, Vitest, jsdom et Testing Library ont été retirés après suppression des suites; `httpx` n’est plus épinglé uniquement pour l’ancien test de metadata. `unittest.mock` dans `src/desktop/self_test.py` est une bibliothèque utilisée par le self-test packagé, pas un runner de suite unittest: garder ce fichier, `--self-test`, signing, versions/checksums et package smoke. Les documents d’historique peuvent citer les anciens runners pour décrire le baseline, mais les commandes actives/docs courants doivent refléter les workflows actuels.

## Critères d’acceptation

1. Chaque contrôle visible, route, changement de réglage, dialogue, action native et CTA website dans la matrice renvoie vers au moins un identifiant de test E2E et une assertion sur l’effet utilisateur; aucun scénario produit n’est couvert uniquement en modifiant le store.
2. La suite application charge le vrai frontend compilé et le vrai FastAPI sur loopback. Un runner de processus transmet à Playwright l’URL réellement démarrée via `OTP_E2E_BASE_URL`; aucun Vite sur `4173`, aucune réutilisation d’un serveur étranger, aucun backend faux et aucun WebSocket interne remplacé. Les parcours UI ordinaires appellent le vrai FastAPI; seules les assertions de récupération ciblées interceptent temporairement les routes listées dans le statut afin d’injecter une panne/réponse d’erreur. Elles ne comptent pas comme preuve de réponse serveur et sont complétées par les six suites HTTP API réelles.
3. Les variables `APPDATA`, `LOCALAPPDATA`, `TEMP` et `TMP` sont définies dans le sous-processus avant tout import applicatif; chaque chemin persistant/cache observé pointe dans le profil temporaire dédié. Les scénarios de settings, presets et historique vérifient l’état après une nouvelle requête et une relance; ils ne déduisent pas la persistance d’une réponse optimistic seule.
4. Les scénarios LCU documentent séparément le scan non filtré du PID synthétique, le filtrage de sécurité appliqué au Connector, et le chemin protocolaire. Le faux serveur local reçoit le vrai handshake, requêtes et mutations; événements reviennent via WSS de production. Le filtre `lcu_driver.utils.process_iter` reste isolé au sous-processus et ne prouve pas le choix du bon client sur une machine League réelle.
5. Le spike Windows natif est une gate de migration et aboutit à une preuve automatisée répétable pour fenêtre WebView2 et actions non-DOM demandées. Les parcours impossibles à automatiser restent officiellement incomplets; un gate manuel n’est pas présenté comme satisfaisant l’objectif E2E-only. Les limites matérielles (DPI réel, League réel) et contenu tiers live sont identifiées séparément.
6. La suite E2E régulière ne fait aucun appel public (Data Dragon, CommunityDragon, provider, GitHub ou autre). L’egress public est bloqué, les données synthétiques nécessaires sont en cache/fixtures, et l’absence de requêtes publiques est vérifiée. Les probes live éventuelles restent opt-in et ne portent pas sur un compte utilisateur en CI.
7. Aucun runner de suite unitaire actif ne reste dans les manifests, scripts ou commandes CI du tree local. Les commandes comportementales restantes sont Playwright E2E; les occurrences historiques dans des archives/plans décrivent l’ancien baseline. `unittest.mock` dans le self-test package est un usage runtime, pas un runner de tests. Les dépendances seulement dues aux unités sont retirées; les dépendances E2E sont déclarées. La gate reste incomplète tant que les E2E ne sont pas verts et les parcours natifs/EXE ne sont pas validés.
8. Tous les contrôles statiques restent verts et OpenAPI généré correspond. Le build website est servi sous `vite preview` et ses interactions sont passées par Playwright; l’application packaged EXE passe de vrais parcours Windows/WebView2 avec un profil temporaire, en plus du build, signature et self-test package. Un package smoke headless ne remplace pas le parcours dans l’EXE.
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
