# Plan de migration vers des tests comportementaux E2E uniquement

Date d’inventaire: 2026-10-02
Branche observée: `codex/react-fastapi-webview-migration`
HEAD observé: `08fea9e8558686caeabb06733d183a505e81b57a`
Comparaison locale: `origin/main` à `809d8567ee4755672b812cc63da46488c30a8ce8`
État Git au snapshot du commit: worktree propre; branche distante alignée sur ce HEAD. Le tree de travail a depuis reçu un scénario E2E UI additionnel dans `frontend/e2e/settings.spec.ts`, des modifications du runner natif sous `scripts/e2e/native/` et ces mises à jour documentaires; ces extensions ne sont pas incluses dans le SHA ni dans les runs CI cités. Seul le nouveau scénario UI change le décompte Playwright.

## Objectif

Faire de Playwright et des scénarios desktop de bout en bout la suite E2E des actions utilisateur. Couvrir chaque action répertoriée, depuis le geste jusqu’à l’effet visible et, lorsqu’il y a persistance ou intégration, jusqu’à la lecture réelle du backend, du fichier, du processus ou du shell concerné. Les autres contrôles comportementaux restent explicitement classés selon leur portée, sans être comptés comme parcours UI E2E.

Conserver deux gates hors de la suite E2E des actions UI. Les validations statiques/build couvrent génération OpenAPI, typage, lint, compilation, builds et audits de dépendances. Le smoke de packaging/intégration `src/desktop/self_test.py --self-test` exerce réellement assets, fichiers et HTTP dans le package en mode non interactif; c’est un contrôle comportemental d’intégration, pas un test unitaire et pas une preuve de parcours UI E2E. Garder ce gate dans `package-smoke.yml` et `release.yml`, car il détecte des défauts propres à l’assemblage/runtime du package. Sa limite: il ne vérifie pas l’usage interactif de l’EXE, WebView2 présent/affichant l’interface, ni un client League réel.

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

- **Specs Playwright suivies par Git:** 20 fichiers navigateur `frontend/e2e/*.spec.ts`, 6 fichiers API `scripts/e2e/*-api.spec.mjs` / `api-contract.spec.mjs`, 1 fichier full-stack `scripts/e2e/app.integration.spec.mjs` et 1 fichier site `website/e2e/site.spec.ts`. Ces 28 fichiers contiennent plusieurs scénarios chacun; leur nombre de fichiers ne doit pas être confondu avec les cas collectés.
- **Cas Playwright collectés au commit `08fea9e`:** 271 au total, soit 207 navigateur, 48 API, 1 full-stack et 15 site. Depuis, le scénario `[FE-API-WRITE-01]` a été ajouté dans `frontend/e2e/settings.spec.ts`: le tree de travail compte 272 cas (208 browser, 48 API, 1 full-stack, 15 site). « Collecté » décrit le décompte Playwright, pas une preuve d’exécution. L’ID API-C-03 reste réservé au contrat API direct dans `api-contract.spec.mjs`.
- **E2E navigateur de l’application desktop:** les 20 specs sont lancées depuis `frontend/` par `npx playwright test --workers=1`. Elles chargent le build React servi par FastAPI et utilisent un profil temporaire. Certains scénarios d’erreur interceptent une réponse avec `page.route`; cela prouve le feedback UI, pas que FastAPI a émis l’erreur. Les succès de mutation sont relus via FastAPI lorsqu’une persistance est pertinente.
- **E2E API / intégration FastAPI:** les six specs sous `scripts/e2e/` sont exécutées en série par `npm run test:e2e:api`. Elles utilisent le vrai serveur et des fixtures contrôlées. Elles valident des contrats HTTP, mais ne prouvent pas le geste utilisateur dans React.
- **E2E full-stack:** `scripts/e2e/app.integration.spec.mjs` exerce le build React, FastAPI, la persistance et le transport LCU avec client synthétique. Il ne valide pas l’installation Riot réelle ni toute la fenêtre native.
- **E2E du site marketing séparé:** `website/e2e/site.spec.ts` teste le site Vite, pas l’application desktop.
- **Runner Windows natif:** `scripts/e2e/native/run_native_e2e.mjs` et ses helpers exercent maintenant les imports UI, les exports Settings/Diagnostics, les filtres Diagnostics WebView et le dialogue Save. L’import invalide compare l’objet complet avant/après (422, inchangé); l’import valide relit `parameters.toml` et confirme le thème persistant (200). L’export Settings téléchargé est schema 6 et omet l’identité détectée. Pour DIAG-03, un POST de précondition vers `/api/diagnostics/run` sur un endpoint fixe autorisé crée une entrée LCU non-WebView au statut `disconnected` sans client League; l’UI confirme ensuite que le bouton de lancement des checks reste désactivé, actualise les données et vérifie les gestes UI de filtre WebView, recherche, absence de résultat et état vide. Ce bouton n’a donc pas exécuté les checks. Le runner a également vérifié l’export Diagnostics et l’annulation du vrai dialogue Win32 Save. Les imports ont utilisé le filechooser CDP, pas une sélection réussie du dialogue Win32; les exports Settings/Diagnostics étaient des téléchargements Chromium/API, et le Save Win32 n’a été qu’annulé. Le run entier sort avec code 1 au premier contrôle tray car le garde de foreground refuse Brave PID 86532; il n’a tué aucun processus et le nettoyage rapporté est réussi. Aucun workflow CI ne l’appelle; il reste hors des 271 cas du commit et des 272 cas Playwright du tree.
- **Smoke packaging/intégration non interactif:** `src/desktop/self_test.py`, invoqué sur l’EXE par `package-smoke.yml` et `release.yml` avec `--self-test --allow-missing-webview2`. Il exerce assets, fichiers et HTTP dans le package assemblé et reste un gate utile contre les défauts de packaging/runtime. Ce n’est ni un test unitaire ni un parcours E2E d’action UI. `--allow-missing-webview2` et l’absence d’interaction signifient qu’il ne prouve pas une fenêtre EXE utilisable avec WebView2.
- **Validations statiques/build à conserver:** dans `frontend-ci.yml`, `npm run api:check`, `npm run typecheck`, `npm run build`; dans `python-ci.yml`, `python -m compileall -q launcher_web.py src create_exe.py`, `ruff check launcher_web.py src create_exe.py --select E9,F --ignore F401,F541,F841`, le Ruff progressif sur `launcher_web.py`, `src/api/schemas.py`, `src/desktop/self_test.py`, `src/integrations/communitydragon.py`, `src/lcu/runtime.py`, et le `ruff format --check` de ces mêmes couches; dans `security.yml`, `pip-audit` sur les dépendances de build. Les builds du site et du frontend (`npm run build`) et le contrôle de version du tag dans `release.yml` sont aussi des validations statiques/build; ils ne sont pas des tests d’intégration runtime.

### État connu et gaps au HEAD 08fea9e

- **Échec E2E antérieur sur le SHA `0766444`**, run [36961639513](https://github.com/qurnt1/otp_lol/actions/runs/36961639513): `[HIST-03] History clear double activation preserves data on failure and can be retried`, 188 pass / 1 fail. GitHub renvoie 403 pour les logs et aucun artefact exploitable n’est disponible; la cause exacte reste **à confirmer**. Aucun diff de cette spec entre le SHA en échec et `08fea9e` n’a été trouvé. Sur `08fea9e`, `[HIST-03]` a ensuite été rejoué avec `--repeat-each=5` et passe 5/5 en 48,3 s. Cette répétition confirme le résultat sur ces cinq exécutions, mais n’explique pas l’échec historique sans stacktrace ni artefact.
- `plan/user-action-e2e-matrix.md` est l’inventaire opérationnel des gestes. Il recense navigation, Bootstrap, presets, dashboard, historique, statistiques/live, réglages, diagnostics, desktop natif, LCU et site web.
- **Exécution locale:** au commit `08fea9e`, navigateur 207/207, API 48/48 et site 15/15. Après l’ajout non commité de `[FE-API-WRITE-01]` dans `settings.spec.ts`, le scénario ciblé est rapporté passé 1/1; le full browser à 208 cas n’est pas encore attesté. L’exécution locale du scénario full-stack 1/1 n’est pas établie. Les anciens résultats 189/189, 47/47 et 13/13, ainsi que les validations statiques/build/package décrites ci-dessous dans leur contexte historique, ne sont pas des runs de ce HEAD.
- **CI attestée pour `08fea9e`:** les workflows Frontend CI du push [36980998215](https://github.com/qurnt1/otp_lol/actions/runs/36980998215) et du PR [36980993102](https://github.com/qurnt1/otp_lol/actions/runs/36980993102) sont verts: 207 browser, 1 full-stack et 48 API. Website push [36980998150](https://github.com/qurnt1/otp_lol/actions/runs/36980998150) passe 15/15. Les comptes CI ne sont pas un résultat de lancement local. Ces runs ne testent ni l’EXE interactif, ni League réel, ni le runner natif interactif.
- CI Windows sur `6528770ac516b8be70c7fac1ad4441dc4f834349`: le run PR [36958311219](https://github.com/qurnt1/otp_lol/actions/runs/36958311219) réussit `Unit and build` et `Playwright Windows` (189 browser, full-stack/LCU, suites API). Le run push [36958305028](https://github.com/qurnt1/otp_lol/actions/runs/36958305028) échoue après 188/189 browser: le seul échec est `page.goto` dans `presets.spec.ts:83` avec `net::ERR_NO_BUFFER_SPACE`, sans assertion applicative. Le même SHA passe tous les jobs côté PR; l’origine de l’erreur isolée reste indéterminée.
- CI Windows après le commit `843f6dc`: les checks PR et push ont chacun eu un échec d’assertion de route dans `prepick-transition.spec.ts`. L’état API était déjà visible avant que le callback de mutation UI ferme le picker et réinitialise le hash; l’assertion observait donc la transition trop tôt. Le push a aussi eu un échec transitoire dans `settings.spec.ts`: `PATCH` a répondu 200 et l’état du switch était correct, mais le toast « Enregistré » avait disparu au moment de l’assertion. Le diagnostic est celui de synchronisations de tests, pas de défaut produit confirmé. Les deux scénarios corrigés passent isolément et dans le full browser local. Ce run complet a fini à 188/189 à cause d’un `page.goto` échouant avec `net::ERR_NO_BUFFER_SPACE` dans un autre test; relancé seul, ce test passe. L’inspection du teardown n’a révélé aucun serveur E2E ou processus synthétique resté actif. Une nouvelle CI distante est nécessaire pour confirmer les specs corrigées.
- CI Windows après le commit `adafea8`: le run PR passe le navigateur et le smoke full-stack/LCU; le run push échoue à l’assertion finale de `prepick-transition.spec.ts`. Le scénario recrée une session LCU avec rune `402` et skin `0` après avoir vérifié `401`/`86013`, puis lit l’état juste après le verrouillage alors que skins et runes partent en tâches asynchrones (`src/core/champ_select.py`). Cela confirme une course dans l’assertion, pas un défaut produit. L’assertion finale attend désormais l’état convergé avec `expect.poll`; trois répétitions locales du scénario passent. Le push et une nouvelle CI après cette correction restent à valider.
- CI Windows sur `2859b06`: le run push a signalé une seule fois le libellé de phase Dashboard resté « En attente » après que l’API runtime est passée à `ChampSelect`; le run PR avait dépassé ce scénario et les suites complètes n’étaient pas terminées. Deux audits indépendants ont trouvé que le spec ne synchronisait pas le WebSocket navigateur `/api/events`. Il attend maintenant ce canal avant les transitions; le scénario ciblé passe 5/5 localement et la suite complète passe dans le run PR du commit `6528770`. Cela confirme le correctif de synchronisation de test, sans défaut produit établi. Une réponse REST ancienne qui écraserait un snapshot WebSocket n’a pas été reproduite après cette correction et reste une hypothèse non confirmée.
- Le red-team a relevé que le helper de sync LCU pouvait rendre l’attente réussie même quand l’événement était annulé ou échouait. `scripts/e2e/appServer.mjs` vérifie maintenant l’issue `completed`/`cancelled`/`failed`, et rejette les attentes `cancelled`/`failed` avec un message générique sans détail de l’événement. Le test d’événement LCU mal formé dans `frontend/e2e/dashboard-connected.spec.ts` vérifie que l’exception du handler fait échouer l’attente et que le payload sensible n’apparaît pas.
- DASH-14: la suite full browser actuelle du SHA `08fea9e` passe 207/207, y compris la déduplication pendant un POST suspendu et le retry contrôlé après 503. Un ancien ciblage ACK fautif avait passé 1/1. Limite de fidélité du scénario: après l’acceptation, il rejoue un événement `playerResponse=None`; le faux LCU remplace la ressource côté serveur après le POST réussi, mais le test ne relit pas cette ressource après le rejeu. C’est une limite de portée du test, pas un défaut produit confirmé. **À confirmer** (`src/core/websocket.py:949-963`): si le POST d’acceptation réussit après que son cycle a été invalidé, historique, status et son peuvent encore être émis. Ce cas dépend d’une réponse LCU tardive et n’a pas été reproduit avec un vrai client. Les anciennes lignes 184/1 et 7/8 dans les passages explicitement historiques décrivent le diagnostic antérieur, pas le résultat courant.
- Le runner natif a validé un sous-ensemble sur sa vraie fenêtre: import invalide 422 avec comparaison de l’objet complet inchangé; import valide 200 puis relecture du thème dans `parameters.toml`; export Settings schema 6 sans identité détectée; export Diagnostics parsé avec champs sensibles omis; filtre/recherche/absence de résultat/état vide pour l’événement réel `otp-lol/webview · created`; annulation du vrai dialogue Win32 Save. Pour obtenir l’entrée LCU de DIAG-03, un unique POST API `/api/diagnostics/run` a utilisé un endpoint fixe autorisé et produit le statut `disconnected` sans client League. L’UI a vérifié que le bouton lancer les checks est désactivé, puis a actualisé et filtré/recherché l’événement WebView; le bouton disabled n’a pas déclenché ces checks. Le run entier sort avec code 1 au premier contrôle tray: `_foreground_menu_state` refuse Brave PID 86532; le garde reste intact, aucun processus n’a été tué et le nettoyage tree/helpers/profil est rapporté réussi. Le Save Win32 réussi, la sélection par vrai dialogue Open et l’effet shell Explorer/navigateur restent non prouvés; les ouvertures shell sont interceptées. La CI ne lance pas le runner. Le succès du provider dans sa WebView reste à couvrir.
- Les réglages `auto_hide_on_connect` et `close_app_on_lol_exit` sont exercés côté UI/API, mais leurs effets sur HWND/processus lors des transitions LCU ne sont pas validés par un parcours natif complet.
- Le runner natif et l’EXE interactif n’ont pas de résultat complet attesté; aucun workflow CI ne les exécute. Aucun League réel n’a été testé.
- La capture 1069×1175 suggère un clipping d’environ 3 px du CTA de retry; le viewport CSS exact manque et le contrôle navigateur à largeur 1069 passe, donc ce point reste **à confirmer**.
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

### Étape 5 — Fermer les gaps natifs dans un ordre vérifiable

Le runner contient déjà des assertions pour plusieurs actions natives. Le dernier run a atteint le premier contrôle du menu tray puis a échoué au garde de foreground, qui a refusé l’entrée clavier car Brave PID 86532 était actif. Le garde n’a pas été contourné et aucun processus n’a été tué. Reprendre sur un poste Windows interactif isolé et exécuter le runner jusqu’à son état terminal; une assertion écrite ou un scénario collecté ne compte pas comme vérifié. Aucun workflow CI ne lance ce runner.

#### P1-a — Obtenir un parcours provider positif

**Fichiers/surfaces:** `scripts/e2e/native/run_native_e2e.mjs`, `scripts/e2e/native/native_app.py`, `src/desktop/provider_browser.py`, `src/desktop/bridge.py`, `frontend/src/features/statistics/ProviderWebPanel.tsx` et les endpoints desktop associés.

**Scénario E2E:** démarrer avec une identité synthétique dans le profil temporaire; ouvrir un provider autorisé depuis l’UI; vérifier la réponse bridge/API, la création d’une seule fenêtre native, son URL validée, son état visible puis ready, et le réemploi à une deuxième activation. Couvrir ensuite hide/show, reload, fermeture et erreur de chargement. Le harness doit fournir un contenu déterministe sans assouplir l’allowlist de production ni envoyer une identité réelle.

**Acceptation:** une seule fenêtre de la bonne catégorie existe; statut et HWND concordent avec le résultat UI; l’URL demeure dans l’allowlist; deuxième activation réutilise et montre la fenêtre; erreur/réessai donne un état fidèle. Si le contenu tiers ne peut pas être stabilisé, limiter l’assertion à la création/lifecycle avec une réponse contrôlée et consigner séparément la disponibilité du site fournisseur.

#### P1-b — Vérifier les effets des options selon l’état League

**Fichiers/surfaces:** `scripts/e2e/native/run_native_e2e.mjs`, fixture LCU `scripts/e2e/app_server.py`, `frontend/e2e/settings.spec.ts`, `src/lcu/runtime.py` et le gestionnaire de fenêtre/arrêt appelé par `launcher_web.py`.

**Scénario E2E:** par l’UI régler chaque option `auto_hide_on_connect` et `close_app_on_lol_exit` sur ON puis OFF; conduire le faux client de fermé/déconnecté à connecté puis à la sortie de League. Observer indépendamment la visibilité HWND, la durée de vie du PID, le port API et l’état persisted. Faire les transitions dans un sous-processus supervisé pour que le test puisse encore observer l’application après qu’elle se masque ou se ferme.

**Acceptation:** ON/OFF ont chacun l’effet spécifié aux transitions correspondantes; les deux options restent indépendantes; masquer ne termine pas le serveur; fermer termine le processus et libère le port; un événement LCU tardif ne ferme pas une nouvelle session. LCU réel n’est pas couvert par cette fixture.

#### P1-c — Faire terminer le runner natif existant

**Fichiers/surfaces:** `scripts/e2e/native/run_native_e2e.mjs`, `scripts/e2e/native/win32_dialog.py`, `scripts/e2e/native/native_app.py`.

**Scénario E2E:** relancer sur un desktop Windows contrôlé où le runner peut garder le foreground. Les derniers résultats partiels couvrent imports via filechooser CDP, export Settings via téléchargement Chromium, Diagnostics WebView et Cancel du vrai dialogue Save, mais pas les sélections réussies des dialogues natifs. Le runner termine actuellement exit 1 au menu tray car `_foreground_menu_state` protège le clavier lorsque Brave PID 86532 est foreground. Exécuter jusqu’au résultat `status=passed`, vérifier `skippedActions=[]`, puis inspecter menu tray, WM_CLOSE/Quit, fullscreen/restauration du rectangle exact, Alt+C/Alt+P quand leur backend est actif et cleanup; ne pas neutraliser le garde en envoyant des frappes dans une autre application.

**Acceptation:** tous les checks applicables sont observés dans une exécution complète, aucun required action n’est sauté, le processus/profile temporaire est nettoyé. Si l’environnement n’a pas un backend hotkey actif, le résultat doit garder cette limite explicite; une navigation via UI ne compte pas comme un hotkey passé.

#### P1-d — Vérifier les dialogues Windows et effets shell réels

**Fichiers/surfaces:** `scripts/e2e/native/run_native_e2e.mjs`, `scripts/e2e/native/win32_dialog.py`, `scripts/e2e/native/sitecustomize.py`, `src/desktop/bridge.py`.

**Scénario E2E:** le runner vérifie l’import UI invalide par comparaison complète de l’objet Settings avant/après (422) et l’import valide par relecture de `parameters.toml` (200, thème persistant), via filechooser CDP. Pour DIAG-03, un unique POST API de précondition crée une entrée LCU non-WebView (`disconnected`, endpoint fixe autorisé, sans client League); l’UI vérifie le bouton de checks désactivé, actualise les données, puis filtre/recherche l’entrée WebView réelle et vérifie le no-match/empty state. Le bouton désactivé n’a pas lancé les checks. Les exports Settings et Diagnostics sont vérifiés; le vrai dialogue Win32 Save a été annulé. Compléter par la sélection réussie de fichiers dans les dialogues Win32 Open/Save et par Save réussi vers un rapport temporaire parseable; l’import CDP ne prouve pas le picker Windows, et Cancel ne prouve pas l’écriture Save. Pour `open_folder` et `external_url`, le payload isolé est observé mais le lancement est intercepté; utiliser un shell contrôlé (dossier temporaire et navigateur/handler de test) pour confirmer la délégation OS sans accès à des comptes ni navigation non contrôlée.

**Acceptation:** les dialogues affichés sont des dialogues OS, Save/Import produisent l’effet disque attendu, Cancel ne mute rien et ne prétend pas réussir; les settings restent inchangés après 422 et l’export sauvegardé est parseable/rédigé. Chaque action shell cible exclusivement la ressource du test et son lancement réel est distingué de l’appel bridge. Le harness actuel intercepte les actions shell et ne prouve donc que l’appel demandé, pas l’ouverture d’Explorer ou du navigateur.

#### P1-e — Exécuter les mêmes parcours critiques sur l’EXE

**Fichiers/surfaces:** `create_exe.py`, spec PyInstaller, `scripts/e2e/native/run_native_e2e.mjs` et helpers, `.github/workflows/package-smoke.yml` (ou un workflow interactif distinct si un runner approprié existe).

**Scénario E2E:** produire l’EXE onedir dans la CI Windows; lancer l’EXE windowed avec WebView2 disponible et `APPDATA`, `LOCALAPPDATA`, `TEMP`, `TMP`, port et profil isolés. Réutiliser les observations HWND, FastAPI health, première écriture config, fermeture et cleanup; ajouter les parcours provider/dialogue après stabilisation du runner source. Garder le self-test package headless séparé.

**Acceptation:** l’EXE rend l’écran Dashboard, répond par FastAPI, écrit uniquement dans le profil temporaire, accomplit le sous-ensemble natif convenu puis termine sans enfant/port résiduel. Le test échoue si WebView2 ou l’environnement interactif requis manque; il ne doit pas transformer `--allow-missing-webview2` en preuve d’UI.

#### P1-f — Valider une installation réelle de League avant release

**Fichiers/surfaces:** pas de suite CI déterministe actuellement; utiliser `scripts/e2e/native/` et les E2E LCU existants comme base pour un protocole manuel sur une machine de validation avec League installé.

**Scénario:** consigner la version du client et observer fermé, démarrage, ouvert sans session, connecté, lobby, champion select, loading, partie, fin, déconnexion et reconnexion; vérifier source d’identité, Gameflow, WebSocket, presets/runes/sorts et fermeture configurée, sans automatiser une action en partie réelle.

**Acceptation:** les états sont cohérents avec les écrans/événements observés et aucun état synthétique périmé n’est montré après disconnect/reconnect; garder le résultat daté et versionné. Un fake LCU ne peut pas satisfaire cette acceptation et aucun vrai compte ne doit être utilisé en CI.

**Contrainte CI:** les workflows actuels n’appellent pas le runner natif interactif. Ne l’ajouter en gate que si un runner Windows avec session desktop, WebView2 et isolation appropriée est disponible et stable. Jusque-là, conserver ces lignes comme non exécutées en CI et organiser la validation interactive avant release.

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
