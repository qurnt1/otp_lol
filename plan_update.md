# Plan d’implémentation actif — release Windows OTP LOL

Ce plan reprend l’audit ci-dessous et sert de checklist d’implémentation. Les changements doivent rester limités au packaging, à l’onboarding WebView2, à la CI/CD, à la documentation et au nettoyage des artefacts explicitement identifiés. Les idées produit P2 ne font pas partie de ce chantier.

La section d’audit conservée plus bas est historique : la checklist ci-dessus fait foi pour l’état après implémentation.

## État initial vérifié

- Branche : `codex/react-fastapi-webview-migration`
- HEAD : `23e3136`
- Branche distante synchronisée, 38 commits devant `origin/main`
- Tests source existants verts sur ce HEAD
- `plan_update.md` était modifié localement avant ce chantier et doit rester préservé

## Checklist d’implémentation

### P0 — prouver le package Windows dans la CI

- [x] Ajouter `.github/workflows/package-smoke.yml` sur Pull Request, `main`, branche de migration et lancement manuel.
- [x] Construire le frontend avec `npm ci` et `npm run build`.
- [x] Construire PyInstaller avec `python create_exe.py --mode onedir --no-shortcut`.
- [x] Vérifier `OTP LOL\OTP LOL.exe`.
- [x] Exécuter le self-test packagé.
- [x] Permettre au smoke packaging headless de fonctionner sans runtime machine, tout en conservant le contrôle WebView2 strict par défaut.
- [x] Ne pas publier d’installateur depuis ce workflow.
- [x] Vérifier le nouveau workflow sur GitHub Actions après push (`f4f0b09`, run `Package Windows smoke #4`, succès).
- [x] Valider localement la syntaxe YAML de tous les workflows.
- [x] Construire localement le package PyInstaller et exécuter `--self-test`.
- [x] Exécuter localement `--headless-smoke` et `--provider-smoke` sur l’exécutable.

### P0 — smoke réel League + WebView2

- [x] Ajouter la checklist de release dans `docs/release.md`.
- [ ] Exécuter la checklist sur l’installateur final signé et le client League réel.
- [ ] Conserver uniquement des preuves redigées, sans cookies, tokens ou données de compte.

### P1 — WebView2 actionnable

- [x] Afficher une erreur native explicite lorsque WebView2 est absent.
- [x] Proposer l’ouverture de la page officielle Microsoft.
- [x] Bloquer l’installation Inno Setup tant que WebView2 n’est pas détecté.
- [x] Documenter le prérequis et le comportement de récupération.
- [x] Ajouter le test de régression du dialogue natif.
- [x] Compiler l’installateur avec Inno Setup et vérifier le script sur Windows.
- [x] Installer silencieusement l’installateur dans un dossier temporaire et vérifier l’exécutable installé.

### P1 — signature Authenticode

- [x] Ajouter les étapes de préparation du certificat PFX dans le job release.
- [x] Signer l’exécutable avant de construire l’installateur.
- [x] Signer l’installateur après sa construction.
- [x] Vérifier les deux signatures avant de calculer le SHA-256.
- [x] Supprimer le certificat temporaire même en cas d’échec.
- [x] Documenter les secrets GitHub Actions nécessaires.
- [ ] Configurer les secrets dans GitHub et exécuter une release taguée.
- [ ] Vérifier les signatures avec `signtool` sur la release signée.

### P1 — maintenance GitHub Actions

- [x] Mettre à jour les actions officielles vers les versions Node.js 24 compatibles vérifiées.
- [x] Vérifier localement la syntaxe YAML après mise à jour.
- [x] Vérifier les workflows CI après mise à jour sur GitHub Actions (`eff2eea`, Frontend, Python et Security en succès).

### P1 — nettoyage du dépôt

- [x] Supprimer les captures générées suivies sous `website/output/playwright/`.
- [x] Supprimer `image.png` à la racine après vérification finale des références.
- [x] Conserver les images documentaires et marketing référencées.
- [x] Conserver les archives de plans qui ont une valeur historique.
- [x] Conserver ce fichier jusqu’à la fin du chantier.

### Validation finale

- [x] Tests Python complets.
- [x] Compilation Python et Ruff.
- [x] Tests Vitest, typecheck, OpenAPI et build Vite.
- [x] Playwright Windows.
- [x] Build PyInstaller et `--self-test` local.
- [x] Build Inno Setup.
- [x] `git diff --check` et revue des fichiers suivis.
- [ ] Smoke réel League/WebView2.
- [ ] Revue finale des secrets et artefacts avant publication.

## Gates externes restant à exécuter

- Le smoke packaging GitHub Actions est validé sur `f4f0b09`; une release taguée reste nécessaire pour valider le job release complet.
- Les secrets de signature Authenticode doivent être configurés par le mainteneur, puis une release taguée doit vérifier l’exécutable et l’installateur avec `signtool`.
- Le smoke League/WebView2 doit être réalisé avec le client League réel et une session de test. Le contrôle Windows disponible dans cet environnement ne permet pas de cibler une fenêtre native OTP LOL, donc cette preuve ne peut pas être fabriquée localement.

## Fichiers modifiés par ce chantier

- `.github/workflows/package-smoke.yml`
- `.github/workflows/release.yml`
- `.github/workflows/frontend-ci.yml`
- `.github/workflows/python-ci.yml`
- `.github/workflows/deploy-website.yml`
- `.github/workflows/security.yml`
- `installer/OTP-LOL.iss`
- `src/desktop/window.py`
- `src/desktop/webview.py`
- `tests/test_desktop.py`
- `tests/test_release_metadata.py`
- `docs/development.md`
- `docs/release.md`
- `README.md`

## Conditions de clôture

Le chantier ne sera considéré comme terminé qu’après validation du workflow package smoke, compilation Inno Setup, configuration des secrets de signature, exécution d’une release signée et smoke manuel avec League Client + WebView2. Une limite d’environnement externe devra être signalée explicitement si elle empêche l’un de ces contrôles.

---

# Audit OTP LOL — `23e3136eaeb53b718717bf5675a51aa3950dd163`

## 1. Résumé exécutif

Branche auditée : `codex/react-fastapi-webview-migration`

HEAD distant :

* SHA : `23e3136eaeb53b718717bf5675a51aa3950dd163`
* auteur : Quentin Chabot
* date : 21 septembre 2026, 23:33:22 UTC
* commit : `feat: persist provider webviews and polish dashboard cards`
* état par rapport à `main` : **38 commits devant, 0 derrière**

### Conclusion

La migration est nettement plus proche d'une release propre que les versions précédemment auditées.

Je ne vois pas dans les éléments vérifiés de bug logiciel critique évident qui justifierait à lui seul de rejeter l'architecture React + FastAPI + WebView.

En particulier, le problème de désynchronisation `FastAPI → OpenAPI → TypeScript` identifié auparavant est désormais corrigé :

* `StatsLinkResponse.account_source` existe côté Pydantic : `src/api/schemas.py:196-203`
* il existe dans le fichier TypeScript généré : `frontend/src/generated/api.ts`
* la CI régénère et compare le contrat ;
* surtout, `frontend-ci.yml` est maintenant déclenché aussi par `src/**/*.py`, donc une modification backend peut faire échouer le contrôle OpenAPI.

C'est une correction importante.

Le HEAD actuel dispose également d'une couverture automatisée sérieuse :

* **354 tests Python** : succès ;
* **40 tests frontend Vitest** : succès ;
* **93 tests Playwright Windows** : succès ;
* compilation Python : succès ;
* Ruff : succès ;
* contrôle OpenAPI généré : succès ;
* TypeScript : succès ;
* build Vite : succès.

Je ne considérerais toutefois pas encore ce SHA comme un binaire public définitivement validé. La raison principale n'est plus la qualité du code applicatif : c'est que le pipeline qui construit réellement le `.exe`, exécute son `--self-test` et construit l'installer Inno Setup ne tourne que lors de la création d'un tag `v*`.

Autrement dit :

> **le code source du HEAD est release-candidate crédible ; le binaire Windows correspondant à ce HEAD n'est pas encore prouvé par CI.**

Pour une distribution à plusieurs vrais utilisateurs, je ferais au minimum un build release de ce SHA et un smoke test réel avec League + WebView2 avant publication.

### État par domaine

| Domaine            | État                                                                                   |
| ------------------ | -------------------------------------------------------------------------------------- |
| Backend            | Solide sur les chemins inspectés                                                       |
| Frontend           | Solide, tests unitaires + E2E verts                                                    |
| Contrat API        | Correctement verrouillé par CI                                                         |
| LCU                | Couverture automatisée importante, mais certaines interactions réelles restent mockées |
| Packaging          | Bien conçu, mais non exécuté sur ce HEAD tant qu'il n'est pas taggé                    |
| Sécurité locale    | Bonne base                                                                             |
| Repository hygiene | Correct, avec quelques artefacts historiques inutiles                                  |
| UX                 | Beaucoup plus cohérente, onboarding/defaults présents                                  |
| Release publique   | Encore une validation Windows réelle à faire                                           |

---

## 2. Blocages avant production

### Le véritable `.exe` du HEAD n'est pas testé à chaque push

**Sévérité : HIGH**

Fichier :
`.github/workflows/release.yml:4-6`, `:121`, `:131`

Problème :

Le pipeline qui effectue réellement :

* le build PyInstaller ;
* l'exécution de `OTP LOL.exe --self-test` ;
* le build Inno Setup ;

ne se déclenche que sur :

```yaml
push:
  tags:
    - "v*"
```

Les CI Python et React du SHA `23e3136e…` sont vertes, mais elles ne garantissent donc pas que **ce HEAD produit effectivement un package Windows fonctionnel**.

Impact utilisateur :

Un problème uniquement lié à PyInstaller, aux hidden imports, aux assets de `frontend/dist`, à WebView2 ou au contexte installé peut échapper aux PR/push checks.

Correction recommandée :

Ajouter un job Windows de packaging « smoke » sur la branche de migration et/ou les PR vers `main`, sans créer de release :

1. `npm ci && npm run build`
2. `python create_exe.py --mode onedir --no-shortcut`
3. `OTP LOL.exe --self-test`

L'installer Inno Setup peut rester réservé aux tags si le temps CI est un problème.

Critère terminé :

Chaque PR destinée à `main` doit prouver qu'un `.exe` lançable peut être construit à partir du commit exact testé.

---

### Il manque encore la validation du scénario réel League + WebView2

**Sévérité : HIGH pour une première release publique ; MEDIUM pour une beta**

Les 93 tests Playwright sont très utiles, mais ils utilisent une API locale mockée et ne constituent pas un test du vrai client League.

La suite Python comporte d'ailleurs explicitement au moins un test live provider ignoré :

`test_current_live_pages_report_redirect_and_frame_policy ... skipped 'requires explicit opt-in; contacts live providers only during an active match'`

Il faut tester au moins une fois sur le package final :

* installation sur Windows ;
* utilisateur non administrateur ;
* WebView2 ;
* League fermé ;
* League au login ;
* connexion LCU ;
* ready check ;
* champion select ;
* preset 1 → fallback 2/3 ;
* summs ;
* runes ;
* skin ;
* fermeture/reconnexion LoL ;
* tray ;
* Alt+C / Alt+P ;
* statistiques externes ;
* fermeture complète sans processus restant.

Ce n'est pas une faiblesse exceptionnelle du code : c'est simplement la frontière de ce que les mocks peuvent prouver.

---

## 3. Bugs et risques non bloquants

### Pas de signature Authenticode

**Sévérité : MEDIUM**

Le README le reconnaît déjà.

L'installer est créé et accompagné d'un SHA-256, ce qui est bien, mais il n'est pas signé.

Conséquence :

Windows SmartScreen / antivirus peuvent rendre l'installation moins rassurante ou générer davantage de faux positifs, ce qui est particulièrement sensible pour une application :

* peu connue ;
* PyInstaller ;
* utilisant global hotkeys ;
* communiquant avec League ;
* démarrant un serveur localhost.

Ce n'est pas nécessaire pour une beta personnelle, mais je le mettrais avant une vraie diffusion publique.

---

### Plusieurs documents de travail très volumineux sont versionnés

**Sévérité : LOW**

Exemples :

* `docs/archive/2026-09-dashboard-presets-refactor-plan.md`
* `docs/archive/2026-09-dashboard-ui-refresh-plan.md`
* `docs/archive/2026-09-plan-update-legacy.md`
* `docs/archive/2026-09-provider-persistence-geometry-card-plan.md`
* `plan_update.md`

Plusieurs font environ 700 à 1 000 lignes.

Ce n'est pas un bug et il n'y a pas de raison de réécrire l'historique Git.

Mais ces documents augmentent le bruit du repository. Les plans qui n'ont plus de valeur documentaire pourraient rester hors du produit à terme.

---

### Des screenshots Playwright du site public restent trackés malgré `output/` dans `.gitignore`

**Sévérité : LOW**

Fichiers encore présents dans le HEAD, par exemple :

* `website/output/playwright/home-1440-scrolled.png`
* `website/output/playwright/home-final.png`
* `website/output/playwright/contact-1440.png`
* etc.

`.gitignore:59` contient bien :

```gitignore
output/
```

mais Git continue évidemment à suivre les fichiers déjà commités.

Ils ne sont pas dangereux, et aucun ne dépasse 1 Mo dans l'arbre actuel.

Action :

Si ces captures ne sont pas utilisées volontairement par le site/documentation, faire simplement :

```bash
git rm -r --cached website/output
```

puis commit.

Pas de purge d'historique nécessaire.

---

### Warning GitHub Actions à anticiper

**Sévérité : LOW**

Les dernières CI affichent :

> Node.js 20 is deprecated ... actions/checkout@v4, actions/setup-node@v4, actions/setup-python@v5

Ce n'est actuellement pas un échec et cela ne touche pas l'application.

Il faudra simplement passer aux versions suivantes de ces actions lorsqu'elles seront recommandées/stables dans votre workflow.

---

## 4. Régressions par rapport à `main`

La branche est 38 commits devant `main` et 0 derrière.

La comparaison montre surtout une substitution complète de l'ancienne UI Python par :

* React ;
* FastAPI ;
* pywebview ;
* nouveaux modules `src/api`, `src/desktop`, `src/domain`, `src/lcu`.

Les anciens éléments de `src/ui/` sont supprimés.

Sur les fonctionnalités documentées et les tests visibles, je ne vois pas de régression majeure avérée.

| Fonctionnalité             | Main                     | Migration                            | Impact          |
| -------------------------- | ------------------------ | ------------------------------------ | --------------- |
| Auto accept                | présente                 | présente                             | parité          |
| Auto pick / priorité 1→2→3 | présente                 | présente                             | parité          |
| Auto ban                   | présente                 | présente                             | parité          |
| Summs                      | présente                 | présente                             | parité          |
| Runes                      | présente                 | présente                             | parité          |
| Skins                      | présente                 | présente                             | parité          |
| Auto play again            | présente                 | présente                             | parité          |
| Hotkeys                    | présente                 | migrée dans `src/desktop/hotkeys.py` | parité          |
| Tray                       | présente                 | migré                                | parité          |
| Historique                 | présente                 | React/API                            | parité          |
| Statistiques externes      | présentes                | gestion par WebViews persistantes    | plutôt amélioré |
| Diagnostics LCU            | absent/moins développé   | présent                              | amélioration    |
| Données LoL locales        | moins structurées        | cache LCU/static data                | amélioration    |
| Reset/presets par défaut   | auparavant problématique | defaults documentés + E2E            | corrigé         |

Je ne vois donc aucune fonctionnalité majeure clairement perdue d'après les sources actuellement accessibles.

---

## 5. Fichiers potentiellement indésirables

L'arbre distant contient **292 fichiers trackés**.

Je n'ai trouvé dans le HEAD distant :

* aucun `.env` ;
* aucune clé PEM/PFX/P12 ;
* aucune DB SQLite utilisateur ;
* aucun `parameters.toml` ;
* aucun `history.json` ;
* aucun `.exe` ;
* aucun wheel ;
* aucun `node_modules`;
* aucun `__pycache__`;
* aucun fichier >1 Mo.

C'est très positif.

Le `.gitignore` couvre correctement :

`.gitignore:30`

```gitignore
*.exe
```

`.gitignore:34`

```gitignore
.env
```

`.gitignore:59`

```gitignore
output/
```

Les principaux éléments discutables sont donc de l'hygiène, pas de la sécurité.

| Élément                       | Problème                                                    | Risque | Action                                              |
| ----------------------------- | ----------------------------------------------------------- | -----: | --------------------------------------------------- |
| `website/output/playwright/*` | artefacts de test déjà trackés                              |    LOW | retirer si inutiles                                 |
| `image.png`                   | nom générique au root, probablement asset temporaire/design |    LOW | vérifier son utilité                                |
| `plan_update.md`              | plan de développement au root                               |    LOW | déplacer/archive/supprimer si terminé               |
| `docs/archive/*plan*.md`      | nombreux documents volumineux                               |    LOW | conserver seulement s'ils ont une valeur historique |

La branche ajoute également un workflow Gitleaks avec `fetch-depth: 0`, ce qui est un bon choix pour rechercher les secrets dans l'historique.

---

## 6. Tests vérifiés

Ces résultats viennent des GitHub Actions exécutées sur **le SHA exact `23e3136e…`**, et non d'une supposition.

### Python CI

Run `35668097992` — succès.

| Vérification                                          | Résultat           |
| ----------------------------------------------------- | ------------------ |
| Installation Python 3.13                              | PASS               |
| Compilation `launcher_web.py src tests create_exe.py` | PASS               |
| `unittest discover`                                   | **354 tests PASS** |
| Ruff E9/F                                             | PASS               |
| Ruff couche migration                                 | PASS               |
| Ruff format                                           | PASS               |

Temps suite Python :

`Ran 354 tests in 8.695s`

Quelques warnings asyncio de tests autour de 175–280 ms existent, mais rien qui indique un problème fonctionnel.

---

### Frontend CI

Run `35668097984` — succès.

| Vérification          | Résultat                        |
| --------------------- | ------------------------------- |
| `npm ci`              | PASS                            |
| Vitest                | **40 tests PASS / 14 fichiers** |
| OpenAPI `api:check`   | PASS                            |
| TypeScript            | PASS                            |
| Vite production build | PASS                            |
| Playwright Windows    | **93 tests PASS**               |

Playwright :

`93 passed (1.2m)`

Build Vite :

`✓ built in 3.13s`

---

## 7. CI/CD

L'ancienne faille importante du pipeline OpenAPI est corrigée.

`.github/workflows/frontend-ci.yml:7` surveille maintenant :

```yaml
- "src/**/*.py"
```

et `.github/workflows/frontend-ci.yml:59` exécute :

```yaml
- name: Check generated API types
```

Il n'est donc plus possible de modifier simplement `src/api/schemas.py` et d'éviter le contrôle frontend.

C'est confirmé concrètement par le HEAD :

`src/api/schemas.py:196-203`

```python
class StatsLinkResponse(BaseModel):
    ...
    account_source: Literal["connected", "saved", "manual", "unavailable"]
```

et `frontend/src/generated/api.ts` contient bien :

```ts
account_source: "connected" | "saved" | "manual" | "unavailable";
```

Le contrat est donc actuellement synchronisé.

### Ce que je changerais encore

La release CI devrait être scindée en deux :

* `package-smoke.yml` sur PR/push important :
  build `.exe` + `--self-test`;
* `release.yml` sur tag :
  installer + checksum + publication GitHub Release.

Cela ferme le principal trou restant entre « CI verte » et « application distribuable ».

---

## 8. Architecture / dette technique

### À corriger maintenant

Principalement :

1. validation automatique du package PyInstaller avant merge/release ;
2. smoke test réel League/WebView2 avant première diffusion large ;
3. signature du binaire si publication publique.

### Acceptable actuellement

Le découpage est cohérent :

* `src/api/` : surface HTTP ;
* `src/domain/` : modèles ;
* `src/lcu/` : intégration League ;
* `src/desktop/` : couche native ;
* `src/core/` : automatisation existante ;
* `src/services/` : services ;
* `frontend/` : React.

Je ne recommande pas de grosse refactorisation.

La couche serveur local est plutôt propre :

`src/desktop/webview.py:27`

```python
_HOST = "127.0.0.1"
```

et :

`src/desktop/webview.py:241`

```python
server = EmbeddedApiServer(api, host=_HOST, port=0)
```

Donc :

* pas d'exposition sur `0.0.0.0`;
* port disponible choisi dynamiquement ;
* pas de conflit avec un port hardcodé.

La fermeture est également centralisée dans un `finally`, avec arrêt des threads/services/server puis :

`src/desktop/webview.py:331`

```python
remove_lockfile()
```

Le design est adapté à ce type d'application desktop.

### À améliorer plus tard

La migration contient encore des fichiers volumineux comme :

* `src/api/context.py`
* `src/api/routes/catalog.py`
* `src/api/routes/runtime.py`
* `frontend/src/styles/globals.css`
* certains E2E

Ils sont assez gros, mais je ne les considérerais pas actuellement comme une raison de refactoriser.

---

## 9. Sécurité

Les choix importants sont bons.

### API locale

FastAPI écoute uniquement sur :

`127.0.0.1`

Le port est dynamique.

C'est exactement ce que je recommanderais pour OTP LOL.

### Mutations

`src/api/app.py:55` valide l'`Origin` pour :

* POST ;
* PUT ;
* PATCH ;
* DELETE.

Cela réduit le risque qu'une page web quelconque déclenche les endpoints locaux.

### CORS

Les origines Vite de développement sont limitées à :

`src/api/app.py:52`

```python
http://127.0.0.1:5173
http://localhost:5173
```

et ne sont pas autorisées en mode frontend compilé sauf activation explicite.

### CSP

Une CSP est appliquée à partir de `src/api/app.py:75`.

### Bridge natif

`DesktopBridge.open_external_url()` ne passe pas directement n'importe quelle URL à `webbrowser.open` :

```python
if not is_allowed_external_url(url):
    return False
```

Et l'ouverture des provider WebViews repose sur un identifiant de provider, pas une URL arbitraire directement injectée par React.

C'est une bonne décision de conception.

### Diagnostics

La CI confirme plusieurs tests dédiés :

* redaction credentials ;
* redaction paths ;
* redaction identifiers ;
* payload cap ;
* export Riot ID uniquement sur opt-in.

Je ne vois pas de risque de sécurité critique évident dans les composants inspectés.

---

## 10. Packaging Windows

Le packaging est cohérent.

`create_exe.py:134` embarque :

```python
frontend/dist
```

et `create_exe.py:160` force :

```python
webview.platforms.edgechromium
```

L'entrypoint est explicitement :

`create_exe.py:166`

```python
launcher_web.py
```

L'installer utilise :

`installer/OTP-LOL.iss:21`

```ini
PrivilegesRequired=lowest
```

Ce qui est pertinent pour une application utilisateur qui ne nécessite pas d'élévation admin.

Le WebView2 Runtime est vérifié avant création de l'application et le self-test existe.

Il reste cependant un manque UX : lorsqu'il manque WebView2, le code déclenche une erreur explicite, mais idéalement l'installer devrait :

* détecter WebView2 ;
* proposer/télécharger le bootstrapper officiel ;
* ou déclarer clairement la dépendance avant lancement.

Cela éviterait que le premier contact avec OTP LOL soit simplement « l'application ne démarre pas ».

---

## 11. UX

Plusieurs problèmes précédemment identifiés semblent corrigés.

### Premier lancement

Le README indique maintenant des presets d'exemple :

* Garen ;
* Lux ;
* Ashe ;
* ban Teemo.

Toutes les automatisations restent désactivées par défaut.

C'est une bonne combinaison : l'utilisateur voit immédiatement ce qu'est un preset sans que l'application ne commence à agir seule sur son client League.

### Reset

Le reset restaure une configuration exploitable, et les cas sont séparés :

* factory reset ;
* restauration des presets d'exemple ;
* suppression uniquement des presets.

Il existe des E2E dédiés aux réglages et aux presets.

### LoL fermé

L'application peut réutiliser une dernière identité sauvegardée pour les statistiques sans faire croire qu'une partie live existe.

La distinction :

* `connected`
* `saved`
* `manual`
* `unavailable`

est maintenant propagée jusque dans le frontend.

### Provider WebViews

Le dernier commit est justement centré sur la persistance des WebViews provider.

C'est préférable à la création/destruction systématique des fenêtres : moins de rechargements et meilleure continuité utilisateur.

---

## 12. Améliorations à forte valeur

Je ne multiplierais pas les features avant la release. Les améliorations les plus intéressantes sont celles qui exploitent davantage ce qui existe déjà.

### Quick wins

#### État de santé visible dans l'application

Problème :

Diagnostics LCU existe, mais reste une fonction avancée.

Fonctionnalité :

Afficher dans le dashboard un petit statut synthétique :

* League connecté ;
* LCU OK ;
* données locales à jour ;
* identité résolue ;
* hotkeys actives.

Valeur :

Permet immédiatement à l'utilisateur de comprendre pourquoi une automatisation ne fonctionne pas.

Difficulté : faible.

Modules :
`src/api/routes/runtime.py`, `frontend/src/features/dashboard/*`.

---

#### Bouton « Tester mon preset »

Avant une vraie champion select, permettre une validation locale :

* champion existe ;
* spells valides ;
* rune page existe ;
* skin accessible si League connecté.

Ne rien appliquer, simplement afficher :

`Preset prêt ✓`

ou la raison exacte.

Difficulté : faible à moyenne.

Valeur : élevée pour éviter de découvrir une mauvaise configuration pendant la sélection.

---

### Améliorations importantes

#### Profils de presets par rôle / queue

Aujourd'hui, 3 priorités constituent un bon workflow simple.

L'étape naturelle serait de conserver cette simplicité mais autoriser :

* Solo/Duo ;
* Flex ;
* ARAM éventuellement ;
* Top/Jungle/Mid/ADC/Support.

Pas besoin d'un moteur de règles complexe.

Exemple :

`Top → Garen / Malphite / Ornn`

`Jungle → Viego / Nocturne / Amumu`

OTP LOL détecte déjà suffisamment de contexte LCU pour aller dans cette direction.

Difficulté : moyenne.

---

#### Timeline des décisions automatiques

Dans l'historique :

> 19:42:11 — Preset 1 Garen indisponible
> 19:42:11 — Preset 2 Lux bannie
> 19:42:12 — Preset 3 Ashe sélectionnée
> 19:42:13 — Summs appliqués
> 19:42:14 — Runes appliquées

Cela transforme les diagnostics techniques en explication utilisateur.

Très utile lorsque l'utilisateur pense que « l'application a fait n'importe quoi ».

Difficulté : moyenne.

---

### Feature différenciante

#### Assistant champion select local basé sur le contexte réel LCU

Sans devenir un « site de stats de plus », OTP LOL pourrait exploiter directement :

* rôle ;
* bans ;
* picks alliés ;
* picks adverses ;
* champions disponibles ;
* presets utilisateur ;
* historique/préférences locales.

Il pourrait alors afficher :

> Preset 1 indisponible → Preset 2 recommandé
> X est déjà pick
> Y est ban
> ton preset Z reste disponible

Puis l'automatisation reste entièrement contrôlée par l'utilisateur.

Cela s'intègre au cœur même d'OTP LOL et différencie davantage le produit d'OP.GG/Porofessor qu'ajouter une page de statistiques supplémentaire.

Difficulté : élevée.

---

## 13. Plan avant release

### P0 — obligatoire

#### P0.1 — Package smoke CI

Objectif :
prouver que chaque release candidate produit réellement un `.exe`.

Modifier :
`.github/workflows/`

Ajouter :

```text
npm ci
npm run build
python create_exe.py --mode onedir --no-shortcut
OTP LOL.exe --self-test
```

Critère :
job Windows vert sur le SHA à merger/tagger.

---

#### P0.2 — Smoke test réel League

Tester l'installer issu du même SHA.

Scénarios obligatoires :

* install user non-admin ;
* lancement ;
* WebView ;
* LoL fermé ;
* LoL connecté ;
* champion select ;
* presets ;
* runes ;
* spells ;
* skins ;
* providers ;
* hotkeys ;
* tray ;
* fermeture ;
* relancement.

Critère :
aucun processus zombie, aucune erreur bloquante et paramètres conservés.

---

### P1 — fortement recommandé

#### P1.1 — Authenticode

Signer :

* installer ;
* idéalement executable principal.

Critère :
signature Windows valide et timestampée.

#### P1.2 — Gestion WebView2

Installer/détecter automatiquement le runtime ou guider clairement l'utilisateur.

#### P1.3 — Nettoyage repo

Retirer les anciens `website/output/playwright/*` si inutiles.

---

### P2 — plus tard

* statut santé simplifié sur Dashboard ;
* validation « Tester mon preset » ;
* timeline explicative des actions ;
* profils par rôle/queue ;
* assistance champion-select contextuelle.

---

# Verdict final

Je ne vois plus de raison technique majeure de remettre en cause la migration React/FastAPI/WebView elle-même.

Les éléments qui étaient auparavant préoccupants — notamment le contrat OpenAPI et la CI susceptible de rester verte après une modification backend — sont maintenant correctement traités.

Le HEAD `23e3136e` passe :

**354 Python + 40 frontend + 93 E2E = 487 tests automatisés réussis**, auxquels s'ajoutent typecheck, build, OpenAPI check et Ruff.

Je ne mergerais donc pas une nouvelle grosse refonte avant release.

La priorité est désormais de **valider le produit empaqueté**, pas de continuer à refactoriser le code.

Pour une beta contrôlée, cette branche est proche du niveau requis.

Pour une release publique, il reste principalement :

1. build/test automatique du vrai `.exe` sur le SHA final ;
2. smoke test avec un vrai client League ;
3. idéalement Authenticode/WebView2 onboarding.

Une fois ces trois points traités et le smoke test réel propre, je ne vois dans cet audit aucun autre blocage évident nécessitant une grosse intervention avant distribution.
