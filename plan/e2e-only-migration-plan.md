# Plan de migration vers des tests comportementaux E2E uniquement

Date d’inventaire: 2026-10-02
Branche observée: `codex/react-fastapi-webview-migration`
HEAD observé: `ae4080ad51ffab666ebeb2bae415eefc37d2be90`
Comparaison locale: `origin/main` à `809d8567ee4755672b812cc63da46488c30a8ce8`

## Objectif

Faire de Playwright et des scénarios desktop de bout en bout l’unique forme de test comportemental du produit. Couvrir chaque action utilisateur répertoriée, depuis le geste jusqu’à l’effet visible et, lorsqu’il y a persistance ou intégration, jusqu’à la lecture réelle du backend, du fichier, du processus ou du shell concerné.

Conserver séparément les contrôles qui ne sont pas des tests comportementaux: génération OpenAPI, typage, lint, compilation, builds, audits de dépendances et smoke test du package. Ils restent des gates de qualité nécessaires, sans être comptés comme E2E.

## Faits vérifiés dans le checkout

### Tests unitaires déjà retirés de la branche

Le tree courant ne contient aucun fichier de suite unitaire suivi par Git et les manifestes/workflows observés n’exécutent ni pytest, ni `unittest discover`, ni Vitest, ni `node --test`, ni `npm test`.

Par rapport à `origin/main`, cette branche a déjà supprimé les 16 modules Python suivants:

- `tests/test_champion_picker.py`
- `tests/test_config.py`
- `tests/test_core_champ_select.py`
- `tests/test_datadragon.py`
- `tests/test_game_state.py`
- `tests/test_history.py`
- `tests/test_integration_lcu.py`
- `tests/test_launcher_params.py`
- `tests/test_main_window.py`
- `tests/test_profile_config.py`
- `tests/test_release_metadata.py`
- `tests/test_single_instance.py`
- `tests/test_skin_modes.py`
- `tests/test_skin_picker.py`
- `tests/test_ui_settings.py`
- `tests/test_utils.py`

Les deux fichiers d’accompagnement de cette ancienne suite, `tests/__init__.py` et `tests/fake_lcu_server.py`, sont eux aussi supprimés de la branche. Aucune nouvelle suppression de test unitaire n’est donc nécessaire pour obtenir l’état E2E-only. L’usage de `unittest.mock.patch` dans `src/desktop/self_test.py` appartient au self-test applicatif du package, pas à un runner unitaire; le conserver.

Les mentions de pytest, Vitest ou unittest dans `docs/archive/`, `plan_update.md` et les anciens plans sont historiques. Elles ne déclenchent pas une suite. Ne pas effacer ces archives pour simuler une migration supplémentaire.

### Catégories de tests et de validations présentes

- **E2E navigateur de l’application desktop:** `frontend/e2e/auto-accept-failure.spec.ts`, `dashboard-connected.spec.ts`, `dashboard-disconnected.spec.ts`, `dashboard-mutation-errors.spec.ts`, `diagnostics.spec.ts`, `game-data-refresh.spec.ts`, `history-live-actions.spec.ts`, `history.spec.ts`, `lcu-automation.spec.ts`, `navigation.spec.ts`, `network-gate.spec.ts`, `presets.spec.ts`, `settings-manual-hotkeys.spec.ts`, `settings.spec.ts`, `skin-account-switch.spec.ts`, `statistics.spec.ts`, `ui-smoke.spec.ts` et `window-layout.spec.ts`. Elles sont exécutées depuis `frontend/` par `npx playwright test --workers=1`. Les tests chargent le build React servi par FastAPI et utilisent un profil temporaire. Certains scénarios d’erreur interceptent une réponse avec `page.route`; une telle interception prouve la réaction UI, pas le comportement FastAPI. Les succès de mutation doivent, quand c’est pertinent, être confirmés par une lecture FastAPI réelle.
- **E2E API / intégration FastAPI:** `scripts/e2e/account-api.spec.mjs`, `asset-api.spec.mjs`, `diagnostics-api.spec.mjs`, `lcu-automation-api.spec.mjs`, `datadragon-cache-api.spec.mjs` et `api-contract.spec.mjs`, exécutés en série par `npm run test:e2e:api`. Ils utilisent le vrai serveur et des fixtures contrôlées. Ce sont des scénarios E2E à la frontière HTTP, mais pas des preuves qu’un utilisateur sait réaliser le même changement dans React.
- **E2E full-stack:** `scripts/e2e/app.integration.spec.mjs`, lancé depuis `frontend/` avec `npx playwright test --config ../scripts/e2e/playwright.config.mjs --workers=1`. Il exerce le build React, FastAPI, persistance, le vrai transport LCU via client synthétique et les événements simulés. Il ne valide pas le client Riot installé, pywebview, le tray ou les dialogues Windows.
- **E2E du site marketing séparé:** `website/e2e/site.spec.ts`, par `cd website; npm ci; npm run build; npx playwright test --workers=1`. Le site reste un périmètre séparé de l’application desktop.
- **E2E Windows natif:** un runner et des fixtures existent sous `scripts/e2e/native/`, notamment `run_native_e2e.mjs`, `native_app.py` et `win32_dialog.py`. Ils ne sont pas exécutés par les workflows CI actuels; les documents d’audit décrivent des essais incomplets ou partiels. Ils ne constituent pas encore une gate native complète.
- **Smoke runtime du package:** `src/desktop/self_test.py`, invoqué sur l’EXE par `package-smoke.yml` et `release.yml` avec `--self-test --allow-missing-webview2`. Il inspecte/exerce le package en mode non interactif; il ne prouve pas le lancement et l’usage de l’interface EXE avec WebView2.
- **Validations statiques/build à conserver:** dans `frontend-ci.yml`, `npm run api:check`, `npm run typecheck`, `npm run build`; dans `python-ci.yml`, `python -m compileall -q launcher_web.py src create_exe.py`, `ruff check launcher_web.py src create_exe.py --select E9,F --ignore F401,F541,F841`, le Ruff progressif sur `launcher_web.py`, `src/api/schemas.py`, `src/desktop/self_test.py`, `src/integrations/communitydragon.py`, `src/lcu/runtime.py`, et le `ruff format --check` de ces mêmes couches; dans `security.yml`, `pip-audit` sur les dépendances de build. Les builds du site et du frontend (`npm run build`) et le contrôle de version du tag dans `release.yml` sont aussi des validations statiques/build. Ce ne sont pas des tests comportementaux.

### État connu et gaps

- `plan/user-action-e2e-matrix.md` est l’inventaire opérationnel des gestes. Il recense navigation, Bootstrap, presets, dashboard, historique, statistiques/live, réglages, diagnostics, desktop natif, LCU et site web.
- Résultats exécutés le 2026-10-02 et consignés dans les deux plans: full browser **189/189**, API E2E rerun **47/47**, full-stack rerun **1/1**, website **13/13**; `npm run api:check`, frontend/site typecheck, build Vite site isolé, compileall, Ruff checks/format, et `git diff --check` passent. Pour Website, le build source Vite de `%TEMP%\otp-lol-site-build-audit` est identique au `website/dist` suivi: comparaison de chemins et SHA-256 pour chaque fichier sans différence; Playwright 13/13 a servi ce `dist`, donc il correspond au build source validé. Le build PyInstaller onedir et le self-test isolé de l’EXE terminent avec code 0. Cela ne valide pas une UI EXE windowed ni un vrai client League.
- CI Windows après le commit `843f6dc`: les checks PR et push ont chacun eu un échec d’assertion de route dans `prepick-transition.spec.ts`. L’état API était déjà visible avant que le callback de mutation UI ferme le picker et réinitialise le hash; l’assertion observait donc la transition trop tôt. Le push a aussi eu un échec transitoire dans `settings.spec.ts`: `PATCH` a répondu 200 et l’état du switch était correct, mais le toast « Enregistré » avait disparu au moment de l’assertion. Le diagnostic est celui de synchronisations de tests, pas de défaut produit confirmé. Les deux scénarios corrigés passent isolément et dans le full browser local. Ce run complet a fini à 188/189 à cause d’un `page.goto` échouant avec `net::ERR_NO_BUFFER_SPACE` dans un autre test; relancé seul, ce test passe. L’inspection du teardown n’a révélé aucun serveur E2E ou processus synthétique resté actif. Une nouvelle CI distante est nécessaire pour confirmer les specs corrigées.
- Le red-team a relevé que le helper de sync LCU pouvait rendre l’attente réussie même quand l’événement était annulé ou échouait. `scripts/e2e/appServer.mjs` vérifie maintenant l’issue `completed`/`cancelled`/`failed`, et rejette les attentes `cancelled`/`failed` avec un message générique sans détail de l’événement. Le test d’événement LCU mal formé dans `frontend/e2e/dashboard-connected.spec.ts` vérifie que l’exception du handler fait échouer l’attente et que le payload sensible n’apparaît pas.
- DASH-14 est corrigé dans le checkout testé: le run browser complet inclut la déduplication pendant une requête en vol et le retry après un échec 503. Un E2E ciblé qui vérifie un ACK fautif passe **1/1**, déjà inclus dans les **189/189**. Limite de fidélité du scénario: après l’acceptation, il rejoue un événement `playerResponse=None`; le faux LCU remplace la ressource côté serveur après le POST réussi, mais le test ne relit pas cette ressource après le rejeu. C’est une limite de portée/fidélité du test, pas un défaut produit confirmé. **À confirmer** (`src/core/websocket.py:949-963`): si le POST d’acceptation réussit après que son cycle a été invalidé, historique, status et son peuvent encore être émis. Ce cas dépend d’une réponse LCU tardive et n’a pas été reproduit avec un vrai client. Les anciennes lignes 184/1 et 7/8 dans les passages explicitement historiques décrivent le diagnostic antérieur, pas le résultat courant.
- Le runner natif source WebView2 s’est arrêté avant le tray car Brave/YouTube était foreground et le garde a refusé l’interaction. Le tray/hotkeys restent non vérifiés. La capture 1069×1175 suggère un clipping d’environ 3 px du CTA de retry; le viewport CSS exact manque et le contrôle navigateur à largeur 1069 passe, donc ce point reste **à confirmer**.
- Le workflow `.github/workflows/frontend-ci.yml` possède un job nommé `Frontend CI / Unit and build`, mais ses étapes actuelles sont `api:check`, typecheck et build. Son nom est historique. Vérifier les règles de protection GitHub avant de le renommer.
- `.github/workflows/python-ci.yml` appelle son job `test`, mais ses contrôles sont compileall et Ruff, sans runner comportemental.
- `frontend/playwright.config.ts` permet le parallélisme local par défaut; la CI impose un worker pour la suite navigateur. Les commandes canoniques de migration doivent garder `--workers=1` tant que la stabilité du full run n’est pas démontrée avec davantage de workers.

## Hypothèses et limites à trancher par preuve

- La matrice est le contrat de couverture, mais elle peut manquer un contrôle introduit dans l’UI depuis sa dernière revue. Chaque phase doit comparer ses lignes aux contrôles effectivement rendus dans React, aux commandes bridge et aux menus natifs.
- « Chaque action utilisateur » signifie chaque action distincte visible/accessibile, avec ses états pertinents, et non chaque combinaison théorique de données. Pour chaque action, couvrir succès, annulation, entrée invalide, erreur/réessai et persistance lorsque ces branches existent réellement.
- Une simulation LCU valide le protocole et le comportement avec la fixture, pas la compatibilité d’une version Riot réelle. Le DPI OS, le multi-écran et l’interaction WebView2 nécessitent un hôte Windows interactif. Tant que ces environnements ne sont pas testés, les rows concernés restent explicitement « non vérifiés » et la couverture n’est pas annoncée exhaustive.
- Tout changement produit nécessaire pour rendre un scénario E2E vert reste distinct du travail de test et doit être attribué à un agent d’implémentation puis revu. DASH-14 passe dans le run courant; ne pas le classer encore comme blocker. Les actions natives, l’UI de l’EXE et League réel demeurent des gates à part.

## Plan par étapes

### Étape 0 — Refaire le snapshot et diagnostiquer GitHub

**Fichiers/surfaces:** worktree Git, GitHub Actions, `plan/user-action-e2e-matrix.md`.
**Actions:** figer branche, HEAD, upstream, `origin/main`, fichiers staged/unstaged/untracked; comparer les changements non publiés. Lister les derniers runs de chaque workflow de la branche et inspecter les logs de chaque échec E2E. Séparer les échecs d’unités historiques des échecs de navigateur, API, full-stack, natif et package.

Commandes de départ:

```powershell
git status --short --branch
git branch -vv
git log -1 --oneline --decorate
git log origin/main -1 --oneline --decorate
git diff --stat origin/main...HEAD
git diff --check
gh run list --branch codex/react-fastapi-webview-migration --limit 50
gh run view <run-id> --log-failed
```

**Validation/acceptation:** chaque échec GitHub récent a une cause classée « bug produit », « test E2E flaky/mal conçu », « infrastructure » ou « suite supprimée/historique », avec SHA, workflow, étape et preuve. Aucun résultat d’un ancien SHA n’est présenté comme résultat du worktree courant.

### Étape 1 — Fermer l’inventaire des runners et des suppressions

**Fichiers à inspecter:** les deux `package.json` et lockfiles, `requirements*.txt`, `scripts/e2e/requirements.txt`, `.github/workflows/*.yml`, `src/desktop/self_test.py`, et `git ls-files`.

Commandes:

```powershell
git ls-files | rg '(^|/)(tests?/|[^/]*\.(spec|test)\.(ts|tsx|js|mjs|py)$)'
rg -n -i 'pytest|unittest\.discover|vitest|node --test|npm test' .github frontend/package.json frontend/package-lock.json website/package.json website/package-lock.json requirements*.txt scripts
```

**Actions:** vérifier si un runner unitaire ou une dépendance exclusivement unitaire réapparaît dans le tree réel. Supprimer uniquement les résidus actifs, après recherche des références. Préserver les snapshots Playwright, les fixtures, le harness natif, le self-test packagé et les dépendances requises par Playwright.

**Validation/acceptation:** aucun fichier de suite unitaire actif ni aucune commande CI/manifeste n’exécute un runner unitaire. Les suppressions Python déjà présentes ne sont pas répétées. Les anciennes mentions archivées sont clairement historiques et n’apparaissent pas dans les instructions de commandes actuelles.

### Étape 2 — Rendre la matrice exhaustive et traçable

**Fichiers:** `plan/user-action-e2e-matrix.md`, puis les écrans `frontend/src/features/**`, `frontend/src/app/**`, le bridge `src/desktop/bridge.py`, les surfaces desktop, `website/src/**` et `website/e2e/site.spec.ts` pour détecter les gestes non répertoriés.

**Actions:** pour chaque bouton, lien, champ, menu, raccourci et action clavier/souris, associer un ID stable, le vrai état de départ, le geste, l’effet visible, la preuve de persistance/intégration et le fichier de spec. Ajouter explicitement annulation/Escape/extérieur, désactivation, double activation, refresh/navigation, erreur/réessai, premier lancement, offline et reconnexion uniquement quand le comportement correspondant existe. Marquer chaque ligne `couvert`, `partiel`, `non couvert` ou `bloqué par environnement`, avec le run et le commit qui l’étayent.

**Validation/acceptation:** aucun contrôle visible dans l’application n’est absent de la matrice. Aucune ligne `partiel` n’est comptée comme couverte. Toute ligne sans preuve a une tâche et un critère d’acceptation E2E, pas une conclusion implicite.

### Étape 3 — Compléter les parcours UI de l’application

**Fichiers:** specs existantes dans `frontend/e2e/`; ajouter une spec uniquement si le workflow ne peut pas être placé clairement dans une spec existante. Réutiliser `frontend/e2e/helpers.ts` et le serveur/harness actuel.

**Actions:** prendre les gaps P0 puis P1 de la matrice. Piloter l’application par rôles/labels et gestes utilisateur. Sur une mutation réussie, vérifier l’UI puis relire via FastAPI; sur une erreur, vérifier absence de mutation et affordance de retry. Vérifier clavier et souris pour les contrôles supportés, focus/restauration pour les dialogues, persistance après rechargement et état après changement de compte. Éviter les écritures directes dans le store React comme preuve d’un parcours utilisateur. Utiliser les interceptions réseau pour créer une panne contrôlée; garder des scénarios API séparés pour prouver les erreurs serveur réelles.

Commande de validation itérative:

```powershell
Set-Location frontend
npm ci
npm run build
npx playwright test e2e/<spec-cible>.spec.ts --workers=1
npx playwright test --workers=1
```

**Validation/acceptation:** chaque geste couvert a une assertion d’effet utile, pas seulement un clic ou l’absence de crash. Le run complet passe sans skip injustifié ni attente temporelle arbitraire. DASH-14 et tout échec E2E récurrent sont corrigés dans la couche responsable, puis validés par une reproduction ciblée et le full browser.

### Étape 4 — Garder des contrats API et scénarios full-stack distincts

**Fichiers:** `scripts/e2e/*-api.spec.mjs`, configs correspondantes, `scripts/e2e/app.integration.spec.mjs`, `scripts/e2e/appServer.mjs`, `scripts/e2e/app_server.py`, fixtures LCU/Data Dragon.

**Actions:** garder les six suites API pour validation, sécurité de frontière, persistance, cache et états non exposés par une action UI simple. Étendre le full-stack pour les transitions qui traversent réellement UI → FastAPI → WebSocket/LCU synthétique → retour UI, redémarrage et profil isolé. Pour tout réglage/action utilisateur également testé via API, conserver un scénario UI correspondant.

Commandes:

```powershell
Set-Location frontend
npm run test:e2e:api
npx playwright test --config ../scripts/e2e/playwright.config.mjs --workers=1
```

**Validation/acceptation:** les six configs sont toutes incluses dans la commande et la CI; les fixtures ne remplacent pas FastAPI; le faux LCU est isolé sur loopback; chaque assertion API est classée comme contrat/intégration, jamais comme couverture du geste React. Les tests nettoient le profil et les processus même en échec.

### Étape 5 — Compléter les parcours Windows natifs puis l’EXE

**Fichiers:** `scripts/e2e/native/run_native_e2e.mjs`, `native/native_app.py`, `native/win32_dialog.py`, `native/sitecustomize.py`, puis `.github/workflows/package-smoke.yml` et/ou nouveau workflow Windows interactif après vérification de l’environnement disponible.

**Actions:** exécuter le runner sur un Windows interactif avec WebView2, fenêtre et compte/profile temporaires. Couvrir lancement/arrêt, instance unique, focus, minimisation/restauration, tray, hotkeys et collisions, fullscreen/géométrie, bridge autorisé/interdit, dossiers et dialogues Save/Cancel, provider panel, fermeture et cleanup. Ne pas remplacer les observations HWND/fichier/processus par une assertion DOM. Répéter les parcours critiques avec l’EXE construit, sans `--allow-missing-webview2` pour le gate UI. Préserver le smoke headless de package en gate distincte.

Commande candidate à confirmer sur l’hôte avant de l’inscrire au workflow:

```powershell
node scripts/e2e/native/run_native_e2e.mjs
```

**Validation/acceptation:** chaque action native rend un résultat observable et le runner échoue si l’environnement interactif requis manque ou si une étape obligatoire ne s’exécute pas. Les tests ne quittent aucun processus/fichier/profil après eux. Le même sous-ensemble essentiel passe depuis l’EXE packagé. League réel, DPI physique et multi-écran restent des validations explicitement séparées s’ils ne sont pas disponibles en CI.

### Étape 6 — Vérifier séparément le site web

**Fichiers:** `website/e2e/site.spec.ts`, `website/playwright.config.ts`, `.github/workflows/website-ci.yml`, `.github/workflows/deploy-website.yml`.

**Actions et commande:** couvrir navigation, skip-link, clavier, fenêtres/modales de capture, focus, liens, images, textes alternatifs et débordements aux tailles retenues.

```powershell
Set-Location website
npm ci
npm run build
npx playwright test --workers=1
```

**Validation/acceptation:** suite verte sur le site construit dans son serveur preview. Son résultat est présenté à part de l’application desktop.

### Étape 7 — Aligner CI sans enlever les gates statiques

**Fichiers:** `.github/workflows/frontend-ci.yml`, `python-ci.yml`, `package-smoke.yml`, `website-ci.yml`, `deploy-website.yml`, `release.yml`, `security.yml`; vérifier aussi les règles de protection de branche.

**Actions:** garder les gates E2E browser, API, full-stack, website, native interactif et packaged UI clairement séparées. Contrôler que les `paths` déclenchent les workflows qui possèdent les suites touchées. Vérifier si le check `Frontend CI / Unit and build` est requis avant de changer son nom; il ne lance déjà aucune suite unitaire. Garder génération OpenAPI, typecheck, builds, compileall, Ruff et audits.

**Validation/acceptation:** un pull request qui modifie une spec, un harness, le backend, le frontend ou le packaging déclenche les suites correspondantes. Une défaillance obligatoire rend le check rouge; aucun test requis n’est marqué `skip` parce que l’agent runner n’a pas l’environnement. Les checks obligatoires sont vérifiés depuis l’interface GitHub ou l’API de règles.

### Étape 8 — Gate finale avant commit et push

Depuis la racine, installer et valider les surfaces séparément:

```powershell
Set-Location frontend
npm ci
npm run api:check
npm run typecheck
npm run build
npx playwright test --workers=1
npx playwright test --config ../scripts/e2e/playwright.config.mjs --workers=1
npm run test:e2e:api

Set-Location ../website
npm ci
npm run build
npx playwright test --workers=1

Set-Location ..
python -m compileall -q launcher_web.py src create_exe.py
python -m ruff check launcher_web.py src create_exe.py --select E9,F --ignore F401,F541,F841
python -m ruff check launcher_web.py src/api/schemas.py src/desktop/self_test.py src/integrations/communitydragon.py src/lcu/runtime.py --select E,F,I,UP,B,SIM --ignore E501
python -m ruff format --check launcher_web.py src/api/schemas.py src/desktop/self_test.py src/integrations/communitydragon.py src/lcu/runtime.py
git diff --check
```

Lancer en plus les validations natives et package dès qu’un runner Windows interactif est disponible. Consulter les derniers checks GitHub sur le SHA poussé, attendre leur conclusion puis lire les logs de tout échec.

**Validation/acceptation:** toutes les suites requises passent sur le même contenu. Le full browser ne peut pas être compensé par des ciblages verts. Les limites non exercées sont listées sans revendiquer une couverture totale. Les modifications staged sont exactement les fichiers revus; aucun artifact local, résultat de test, profil ou secret n’est ajouté.

### Étape 9 — Publication et rollback

**Actions:** faire relire les diffs E2E/harness/plan par un agent reviewer distinct. Vérifier l’index avec `git diff --cached --name-status` et `git diff --cached --check`. Après gates vertes, créer un commit thématique E2E, pousser uniquement la branche demandée, puis revérifier le SHA distant et les GitHub Actions de ce SHA.

**Acceptation:** commit sans modification produit non revue; branche distante égale au commit publié; checks obligatoires terminés verts; matrice mise à jour avec les vrais résultats de ce SHA.

**Rollback:** si la suite introduit une instabilité ou si une modification de harness casse d’autres E2E, corriger dans un commit ciblé. Si une réversion devient nécessaire après publication, employer un commit `git revert <sha>` et relancer les checks; ne pas réécrire l’historique partagé. Les tests utilisent les dossiers/profils temporaires de leur harness, donc le rollback du code ne doit pas toucher aux données utilisateur.

## Critères de fin

Le travail E2E-only est terminé uniquement si:

1. aucun runner ou fichier de suite unitaire actif ne reste; les validations statiques/build/runtime sont toujours là;
2. chaque action visible de la matrice pointe vers au moins un scénario navigateur ou natif qui exécute le geste et vérifie le résultat; les actions persistantes sont relues depuis leur source réelle;
3. aucun état `partiel`, `bloqué par environnement` ou `non couvert` n’est masqué dans le rapport. Une action native ou League réelle non disponible empêche de qualifier l’ensemble d’exhaustif;
4. les suites navigateur, API, full-stack et site passent; les suites Windows natif et EXE passent dans l’environnement interactif prévu;
5. les workflows déclenchés, noms de checks requis et résultats sur le SHA poussé sont vérifiés;
6. le diff est limité, revu par un agent, commité et poussé avec un SHA distant confirmé.
