# Mission

Travaille sur la branche :

`codex/react-fastapi-webview-migration`

L’objectif est de stabiliser la migration React/FastAPI/WebView avant fusion dans `main`.

Le cœur fonctionnel actuel ne doit pas être réécrit inutilement. Les automatisations League/LCU déjà fonctionnelles doivent conserver leur comportement.

Le travail doit porter sur :

1. simplification définitive de la gestion des paramètres ;
2. correction de Python CI ;
3. correction de Frontend CI / Playwright ;
4. transformation du blocage Data Dragon en avertissement non bloquant ;
5. suppression de la race condition sur le port FastAPI local ;
6. ajout/renforcement des tests desktop ;
7. validation complète CI/release ;
8. protection contre les régressions futures.

---

# 0. Règles générales

Avant toute modification :

* inspecter le code actuel de la branche ;
* inspecter les tests déjà existants ;
* ne pas créer de tests redondants si un équivalent existe déjà ;
* privilégier une modification minimale et robuste ;
* ne pas modifier le comportement métier LCU sauf nécessité démontrée ;
* ne pas réintroduire de logique de migration des anciennes configurations ;
* ne pas masquer un test en échec simplement pour rendre la CI verte ;
* ne pas supprimer un test pertinent sans le remplacer par une validation équivalente ;
* ne pas désactiver les screenshots Playwright pour contourner les erreurs ;
* conserver FastAPI exclusivement sur `127.0.0.1`.

À la fin, fournir la liste exacte des fichiers modifiés, les tests ajoutés/modifiés, les commandes exécutées et leurs résultats.

---

# 1. Simplifier définitivement la gestion des paramètres

## Décision produit

OTP LOL n'a actuellement qu'un seul utilisateur réel.

Il n'est donc PAS nécessaire de conserver une compatibilité avec les anciens schémas de paramètres.

Le comportement voulu est désormais :

```text
schéma courant valide
→ charger normalement

schéma absent / ancien / futur / invalide
→ sauvegarder le fichier existant en .bak
→ générer directement les paramètres du schéma courant
```

Aucune migration `3 → 4 → 5 → 6`.

Aucune chaîne de migrations.

Aucun convertisseur de paramètres historiques.

## Fichiers principaux

Inspecter notamment :

`src/config/settings.py`

`src/config/constants.py`

`tests/test_config.py`

et les exports éventuels dans :

`src/config/__init__.py`

## À supprimer

Supprimer toute logique qui n'existe que pour transformer un ancien schéma vers le schéma actuel.

Cela inclut les anciennes fonctions de migration si elles existent encore.

Inspecter également les compatibilités legacy intégrées à la normalisation.

Par exemple, le code actuel gère encore :

`rune_auto_apply`

dans `_build_normalized_pick_slots()`.

Si ce champ n'appartient plus au schéma courant, supprimer cette compatibilité.

Supprimer également le test correspondant :

`test_legacy_rune_auto_apply_false_clears_page_and_true_preserves_it`

et toute logique similaire destinée uniquement aux anciennes versions.

Ne pas confondre avec le support d'import/export JSON/TOML : celui-ci peut rester si les fichiers importés utilisent le **schéma actuel**.

## Comportement à conserver

Un fichier current-schema incomplet peut continuer à être normalisé avec les valeurs par défaut lorsque c'est volontairement supporté.

La règle stricte porte sur :

`config_schema_version`

Il doit être exactement égal à :

`CONFIG_SCHEMA_VERSION`

Sinon :

1. `.bak`;
2. factory/default configuration actuelle;
3. aucun essai de migration.

## Tests attendus

Ajouter ou adapter des tests de ce type :

`test_old_schema_is_backed_up_and_reset_to_current_defaults`

`test_future_schema_is_backed_up_and_reset_to_current_defaults`

`test_invalid_schema_is_backed_up_and_reset_to_current_defaults`

`test_current_schema_is_loaded_without_backup`

`test_current_schema_normalization_preserves_supported_values`

`test_current_schema_import_export_round_trip`

`test_legacy_fields_are_not_interpreted`

Le premier test doit par exemple écrire un fichier :

```text
config_schema_version = 3
```

avec des valeurs volontairement reconnaissables, puis vérifier :

* création du `.bak`;
* contenu original intact dans `.bak`;
* nouveau fichier en schema courant ;
* absence des anciennes valeurs ;
* retour de `FIRST_LAUNCH_PARAMS` ou de l'équivalent actuel.

Il ne faut donc PAS créer les anciens tests proposés précédemment :

`test_schema_3_from_main_is_migrated_to_schema_6_without_losing_presets`

`test_schema_3_migration_preserves_hotkeys_and_provider_preferences`

`test_schema_3_migration_preserves_auto_accept_and_play_again`

`test_import_of_main_v11_settings_is_supported`

Ils sont désormais contraires au comportement voulu.

---

# 2. Corriger Python CI / FastAPI TestClient

## Problème actuel confirmé

Le commit actuel échoue dans GitHub Actions sur :

`test_api`

et :

`test_lcu_api_routes`

avec :

```text
RuntimeError:
The starlette.testclient module requires
the httpx2 package to be installed.
```

La branche utilise actuellement :

`fastapi==0.135.1`

et la version de Starlette installée avec cette combinaison utilise désormais `httpx2` pour `TestClient`.

Starlette documente actuellement `httpx2` comme dépendance optionnelle de son `TestClient`.

## Objectif

Ne pas polluer inutilement les dépendances runtime si `httpx2` n'est requis que pour les tests.

## Implémentation recommandée

Créer une séparation claire entre :

* dépendances runtime ;
* dépendances de test ;
* dépendances de build.

Par exemple :

`requirements.txt`

→ runtime uniquement.

Créer :

`requirements-test.txt`

contenant idéalement :

```text
-r requirements.txt
httpx2~=...
```

avec une version contrôlée dans :

`requirements-constraints.txt`

Le choix précis de la version doit être validé avec la version de Starlette réellement résolue par `fastapi==0.135.1`.

Ne pas mettre une version au hasard.

## Adapter Python CI

Dans :

`.github/workflows/python-ci.yml`

remplacer l'installation runtime seule par l'installation des dépendances de test.

Exemple conceptuel :

```text
pip install -c requirements-constraints.txt -r requirements-test.txt
```

## Adapter Release CI

Le job `validate` de :

`.github/workflows/release.yml`

exécute également les tests Python.

Il doit donc lui aussi installer les dépendances de test avant :

```text
python -m unittest discover -s tests -v
```

Le job de packaging ne doit en revanche pas embarquer `httpx2` si ce package n'est pas utilisé par le runtime.

`requirements-build.txt` doit continuer à représenter les dépendances nécessaires au programme final et à PyInstaller.

## Tests / validation

Faire passer :

```text
python -m compileall -q launcher_web.py src tests create_exe.py
python -m unittest discover -s tests -v
```

Objectif :

* aucune erreur d'import `TestClient`;
* aucun test perdu ;
* nombre de tests >= nombre actuel sauf suppression documentée de tests legacy devenus volontairement inutiles.

---

# 3. Corriger Frontend CI et les screenshots Playwright

## Problème actuel

Les tests fonctionnels sont majoritairement corrects :

```text
79 passed
```

mais quatre tests échouent parce que la CI tourne sous Linux tandis que seuls des snapshots Windows sont présents :

```text
settings-advanced-win32.png

dashboard-1100x760-win32.png
dashboard-1440x900-win32.png
dashboard-1920x1080-win32.png
```

Playwright recherche alors :

```text
*-linux.png
```

## Décision

OTP LOL est une application desktop Windows utilisant WebView2.

Les screenshots de référence doivent donc être testés sur Windows.

## Modification recommandée

Modifier :

`.github/workflows/frontend-ci.yml`

afin que le job contenant les screenshots Playwright soit exécuté sous :

`windows-latest`

La solution la plus simple peut être de passer tout le job frontend sur Windows si cela reste suffisamment rapide.

Alternative acceptable :

* conserver build/typecheck/Vitest sur Ubuntu ;
* créer un job `playwright-windows` dédié à `windows-latest`.

La deuxième approche est préférable si elle reste simple :

```text
frontend-unit
    Ubuntu
    npm ci
    npm test
    api:check
    build

frontend-e2e-windows
    Windows
    npm ci
    Playwright Chromium
    test:e2e
```

Éviter cependant une architecture CI inutilement complexe.

## Ne pas faire

Ne pas :

* supprimer `toHaveScreenshot`;
* ajouter `--update-snapshots` automatiquement dans la CI ;
* ignorer les quatre tests ;
* générer automatiquement de nouveaux snapshots Linux sans raison produit.

Les snapshots doivent rester volontairement validés.

## Test demandé

Garantir explicitement :

`visual_snapshots_run_on_same_os_as_committed_references`

Cela peut être vérifié par la structure du workflow plutôt que par un unittest artificiel.

---

# 4. Transformer le NetworkGate Data Dragon en avertissement non bloquant

## Décision produit

Le check Data Dragon est utile.

Si Data Dragon ne répond pas, certaines images ou données distantes peuvent effectivement ne pas fonctionner.

Mais OTP LOL ne doit plus être complètement bloqué.

## Comportement voulu

### Cas 1 — FastAPI local inaccessible

C'est un vrai problème critique.

Conserver un écran bloquant du type :

```text
OTP LOL n'arrive pas à communiquer avec son service local.
Réessayer.
```

### Cas 2 — FastAPI fonctionne mais Data Dragon est inaccessible

L'application doit continuer son démarrage.

Le bootstrap doit être exécuté.

Le dashboard et la navigation doivent être accessibles.

Afficher une alerte non modale.

Texte recommandé :

```text
Connexion à Data Dragon impossible.

OTP LOL reste utilisable, mais certaines images ou données peuvent ne pas
s'afficher correctement tant que la connexion n'est pas rétablie.
```

Actions possibles :

`Réessayer`

et éventuellement :

`Fermer`

L'alerte peut être :

* un banner dans `AppShell`;
* un toast persistant ;
* une petite notification non modale.

Ne pas utiliser une modal qui empêche les interactions.

## Fichiers principaux

`frontend/src/App.tsx`

`frontend/src/features/network/NetworkGate.tsx`

`frontend/src/features/network/NetworkGate.test.tsx`

`frontend/src/content/fr.ts`

`frontend/src/styles/globals.css`

Possiblement renommer `NetworkGate` puisque le composant ne doit plus « gate » l'application.

Un nom comme :

`NetworkWarning`

ou :

`DataDragonWarning`

serait plus fidèle.

## Modification de `App.tsx`

Aujourd'hui :

```text
bootstrap.enabled = network.data?.online === true
```

Cette dépendance doit disparaître.

Le bootstrap local doit pouvoir démarrer indépendamment du résultat Data Dragon.

Conceptuellement :

```text
FastAPI disponible
    ↓
bootstrap
    ↓
interface

en parallèle :
check Data Dragon
    ↓
online → rien
offline → warning non bloquant
```

Ne pas laisser un délai réseau de 3 secondes retarder inutilement le premier rendu.

## Service backend

`NetworkStatusService` peut être conservé.

Il représente en réalité plus précisément :

`Data Dragon availability`

que :

`general Internet availability`

Profiter du refactor pour clarifier les noms lorsque cela améliore la compréhension sans provoquer une cascade inutile.

Par exemple, conserver le contrat API existant si renommer casserait trop de code, mais documenter clairement que :

```text
source = "ddragon"
```

signifie que le probe ne garantit pas l'état global d'Internet.

## Tests demandés

Backend :

`test_ddragon_failure_does_not_block_local_lcu_features`

Vérifier qu'une panne du probe externe n'empêche pas :

* runtime local ;
* paramètres ;
* presets ;
* LCU si connecté.

Frontend :

`test_network_status_offline_does_not_block_bootstrap`

`test_ddragon_warning_is_visible_while_app_remains_navigable`

`test_network_retry_can_clear_warning`

`test_local_api_failure_still_blocks_the_app`

`test_network_gate_distinguishes_local_server_failure_from_ddragon_failure`

Mettre également à jour l'ancien test :

```text
shows a local image and blocks the app while offline
```

puisqu'il ne correspondra plus au comportement produit.

---

# 5. Supprimer la race condition sur le port FastAPI local

## Problème actuel

Dans :

`src/desktop/webview.py`

le code fait approximativement :

```python
with socket.socket(...) as probe:
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]

# socket fermée

server = EmbeddedApiServer(..., port=port)
server.start()
```

Entre les deux étapes, un autre processus peut prendre le port.

C'est une TOCTOU réelle, même si peu probable.

## Architecture cible

Ne plus :

```text
chercher un port
fermer la socket
réouvrir le même port
```

Faire :

```text
créer socket
↓
bind 127.0.0.1:0
↓
conserver la socket ouverte
↓
récupérer le port
↓
passer CETTE MÊME socket à Uvicorn
```

## Implémentation recommandée

Déplacer la responsabilité d'allocation du socket dans :

`src/desktop/server.py`

afin que `EmbeddedApiServer` possède entièrement :

* socket ;
* port ;
* serveur Uvicorn ;
* thread ;
* fermeture.

API souhaitable conceptuellement :

```python
server = EmbeddedApiServer(api, host="127.0.0.1", port=0)

server.start()

port = server.port
```

Lors de `start()` :

1. créer un socket ;
2. `bind((host, 0))`;
3. conserver le socket ;
4. récupérer son port ;
5. lancer Uvicorn en utilisant la socket déjà réservée.

Vérifier l'API exacte de la version Uvicorn pinée et utiliser la méthode supportée par cette version pour transmettre une socket pré-bindée.

Ne pas implémenter une solution fragile fondée sur `sleep`.

## `webview.py`

Supprimer `_find_free_port()` s'il devient inutile.

Faire ensuite :

```text
server.start()
_wait_for_server(server.port)
```

## Shutdown

`EmbeddedApiServer.stop()` doit :

1. demander l'arrêt Uvicorn ;
2. attendre le thread ;
3. fermer la socket ;
4. nettoyer les références.

Même après exception de startup, la socket doit être fermée.

Utiliser `finally` lorsque nécessaire.

## Tests

Ajouter dans `tests/test_desktop.py`, ou un fichier plus ciblé si cela devient plus lisible :

`test_embedded_server_uses_prebound_socket_without_port_release_window`

`test_embedded_server_port_is_available_after_stop`

`test_embedded_server_start_stop_can_be_repeated`

`test_embedded_server_exposes_actual_ephemeral_port`

`test_embedded_server_health_endpoint_responds_on_reserved_port`

Éviter les ports fixes.

---

# 6. Tests desktop Provider WebViews

Ces tests doivent être ajoutés uniquement s'ils ne sont pas déjà couverts correctement.

Utiliser autant que possible les fakes/mocks existants dans :

`tests/test_desktop.py`

et éviter de nécessiter un vrai OP.GG ou un vrai compte League pour les tests unitaires.

## 6.1 Provider survive disconnect/reconnect

Ajouter :

`provider_window_survives_lcu_disconnect_reconnect`

Scénario :

```text
provider Stats créé
↓
LCU connecté
↓
fenêtre provider disponible
↓
LCU disconnected
↓
application reste stable
↓
LCU reconnect
↓
identity actualisée
↓
provider toujours contrôlable ou proprement recréé
```

Assertions :

* aucune exception ;
* pas de deuxième fenêtre zombie ;
* état manager cohérent ;
* URL actualisable après reconnexion.

---

## 6.2 Changement de compte

Ajouter :

`provider_window_refreshes_after_account_change`

Scénario :

```text
Compte A
→ fenêtre OP.GG / provider créée

account_identity_updated vers Compte B

→ ancienne identité ne doit plus être utilisée
→ URL provider doit correspondre au compte B
```

Tester :

* invalidation ;
* refresh/recreation appropriée ;
* aucune duplication de fenêtre.

---

## 6.3 Shutdown

Ajouter :

`shutdown_closes_all_provider_webviews`

Créer :

* une fenêtre stats ;
* une fenêtre live ;

puis appeler le shutdown.

Vérifier :

* les deux fenêtres reçoivent `destroy/close`;
* timers de preload annulés ;
* thread preload arrêté ;
* références nettoyées ;
* aucune opération tardive après shutdown.

---

## 6.4 Instance unique

Ajouter :

`second_instance_does_not_leave_orphan_process`

Il peut être pertinent de séparer :

### unittest

Tester le service `single_instance` avec lockfile simulé.

### integration Windows

Lancer réellement :

```text
OTP LOL instance A
OTP LOL instance B
```

et vérifier :

* B sort immédiatement avec le comportement attendu ;
* A continue ;
* aucun troisième processus persistant ;
* après fermeture de A, une nouvelle instance C peut démarrer ;
* aucun lockfile orphelin ne bloque C.

Si ce test est trop lourd pour chaque push, créer un smoke test Windows dédié pouvant être exécuté dans le workflow release ou manuellement.

---

# 7. Renforcer le self-test desktop

Inspecter :

`src/desktop/self_test.py`

Ajouter uniquement ce qui apporte une validation réelle au package.

Le self-test packagé devrait au minimum confirmer :

* frontend `dist` présent ;
* assets critiques présents ;
* FastAPI démarre ;
* port local obtenu correctement ;
* `/api/health` répond ;
* bootstrap local répond ;
* serveur s'arrête proprement ;
* aucune dépendance développement nécessaire.

Ne pas faire dépendre ce self-test :

* d'un vrai League Client ;
* d'Internet ;
* de Data Dragon ;
* d'un compte Riot.

L'échec Data Dragon doit être un warning, pas faire échouer le self-test du binaire.

---

# 8. CI/CD

## Python CI

Doit valider :

```text
install test dependencies
compileall
unittest
ruff fatal checks
ruff progressive checks
ruff format
```

Tout doit passer.

---

## Frontend CI

Doit valider :

```text
npm ci
Vitest
OpenAPI generated types consistency
TypeScript
Vite build
Playwright
visual snapshots Windows
```

Vérifier qu'un changement dans :

```text
src/**/*.py
```

continue bien de déclencher le contrôle OpenAPI frontend.

Conserver les triggers actuels utiles.

---

## Release CI

Le workflow doit conserver :

```text
frontend tests
frontend build
Python tests
OpenAPI check
Playwright
version/tag validation
PyInstaller onedir
packaged self-test
Inno Setup
SHA-256
GitHub Release
```

Après les changements de dépendances, vérifier surtout que :

* le job `validate` installe les dépendances de test ;
* le job `package` n'embarque pas inutilement les dépendances uniquement destinées aux tests ;
* le self-test du `.exe` fonctionne sans environnement Node/Python installé sur la machine finale.

---

# 9. Protection de branche GitHub

La branche n'a actuellement pas de protection obligatoire.

Une fois les workflows stabilisés, configurer `main` pour empêcher un merge lorsque les checks essentiels sont rouges.

Checks à exiger au minimum :

`Python CI`

`Frontend CI`

ou les noms exacts des jobs si les workflows sont séparés.

Ne pas obliger des workflows qui ne se déclenchent pas sur toutes les PR concernées.

Si Codex n'a pas les permissions GitHub nécessaires pour modifier les branch rules :

* ne pas contourner ;
* fournir précisément les réglages à effectuer manuellement dans GitHub.

---

# 10. Validation complète finale

Avant de considérer la tâche terminée, exécuter tout ce qui est possible.

## Python

```text
python -m compileall -q launcher_web.py src tests create_exe.py
python -m unittest discover -s tests -v
```

Puis Ruff selon les workflows.

## Frontend

```text
cd frontend
npm ci
npm run api:check
npm run typecheck
npm run test
npm run build
npm run test:e2e
```

Tous doivent être verts.

## GitHub Actions

Après push :

```text
Python CI → SUCCESS
Frontend CI → SUCCESS
Security checks → SUCCESS
```

Ne pas considérer la mission terminée tant que Python CI et Frontend CI sont rouges.

---

# 11. Validation Windows réelle

Lorsque l'environnement le permet, faire aussi les validations suivantes.

### Lancement

* OTP LOL sans League lancé ;
* lancer League après OTP LOL ;
* fermer League ;
* relancer League ;
* fermer OTP LOL pendant une reconnexion.

### Local API

* port différent selon les lancements ;
* aucun conflit de port ;
* aucune fenêtre de race détectable ;
* FastAPI inaccessible depuis le réseau externe ;
* uniquement `127.0.0.1`.

### Réseau

Simuler Data Dragon indisponible.

Résultat attendu :

```text
OTP LOL démarre
navigation utilisable
presets utilisables
LCU local utilisable
warning Data Dragon visible
certaines images peuvent avoir un fallback
```

Puis rétablir Data Dragon.

Résultat attendu :

```text
warning disparaît après refresh
assets/données se remettent à fonctionner
aucun reload complet obligatoire
```

### Providers

Tester au minimum :

* OP.GG ;
* DeepLOL ;
* DPM ;
* LeagueOfGraphs ;
* Porofessor Live.

Pour chacun :

* ouverture ;
* fermeture ;
* reopen ;
* refresh ;
* compte changé ;
* League fermé ;
* League reconnecté.

### Instance unique

Tester deux lancements consécutifs.

Aucun processus orphelin ne doit rester.

### EXE

Construire réellement :

```text
React
→ FastAPI
→ pywebview
→ PyInstaller onedir
→ Inno Setup
```

Installer sur Windows.

Vérifier qu'OTP LOL fonctionne sans :

* Node ;
* npm ;
* Python ;
* dépôt Git local.

---

# 12. Critères d'acceptation

La tâche est terminée seulement si :

* aucune fonction de migration d'ancien schéma n'est conservée ;
* le code ne tente pas d'interpréter des paramètres legacy ;
* ancien schéma → `.bak` + reset propre ;
* Python CI est verte ;
* `TestClient` fonctionne ;
* les dépendances de test sont séparées proprement des dépendances runtime ;
* Frontend CI est verte ;
* les screenshots Playwright sont exécutés sur le même OS que leurs références ;
* Data Dragon indisponible ne bloque plus l'application ;
* une alerte claire indique que certaines images/données peuvent manquer ;
* une panne du serveur FastAPI local reste bloquante ;
* la race d'allocation du port est supprimée par conservation de la socket ;
* les tests provider reconnect/account/shutdown existent et passent ;
* l'instance unique est couverte ;
* le workflow release peut atteindre le packaging ;
* le packaged self-test passe ;
* aucun comportement métier LCU existant n'a régressé.

---

# 13. Rapport attendu de Codex

À la fin, ne réponds pas simplement « terminé ».

Donne :

### Modifications

Pour chaque fichier modifié :

```text
fichier
changement
raison
```

### Tests

Liste exacte :

```text
tests ajoutés
tests supprimés
tests renommés
tests modifiés
```

### Résultats

Donne les résultats chiffrés :

```text
Python: X passed / X skipped / 0 failed
Vitest: X passed
Playwright: X passed / 0 failed
TypeScript: success
Build React: success
OpenAPI check: success
```

### CI

Indique l'état réel des workflows GitHub après push.

### Validation manuelle restante

Sépare clairement ce qui n'a pas pu être vérifié automatiquement, notamment :

* vrai League Client ;
* WebView2 réel ;
* providers tiers ;
* installer sur une machine propre.

### Important

Ne masque aucun problème découvert pendant l'implémentation.

Si une hypothèse de ce plan est incorrecte après inspection du code, adapte l'implémentation et explique précisément pourquoi.
