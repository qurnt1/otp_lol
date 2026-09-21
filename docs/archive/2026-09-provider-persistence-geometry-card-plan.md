/goal

Corriger et améliorer quatre points précis dans OTP LOL :

1. Persister correctement les cookies et le stockage des fenêtres Web Statistiques / En direct afin que l’utilisateur n’ait plus à accepter les cookies à chaque lancement.
2. Faire en sorte que les fenêtres Web Statistiques / En direct héritent de la taille, position et état maximisé de la fenêtre principale OTP LOL.
3. Simplifier les cards de presets du Dashboard :
   - supprimer le texte inutile « Prêt » sous le nom du champion ;
   - retirer le cadrillage/background autour des icônes de runes.
4. Supprimer la redondance visuelle liée aux skins :
   - la grande image de card continue d’afficher le splash du skin sélectionné ;
   - la miniature de la ligne SKIN doit afficher l’icône carrée du champion de base et non à nouveau l’image du skin.

Ce chantier doit rester ciblé et ne doit pas modifier la logique métier League/LCU.


/mandatory-first-step

AVANT TOUTE MODIFICATION :

Lis toute la codebase.

Ne pars pas uniquement des recommandations de ce prompt.

Inspecte notamment :

src/desktop/
- webview.py
- window.py
- provider_browser.py
- bridge.py

src/config/
- paths.py
- settings.py
- constants.py

frontend/src/features/dashboard/
- DashboardPage.tsx
- ChampionPriorityCard.tsx
- BanPanel.tsx

frontend/src/styles/globals.css

frontend/src/types/*
frontend/src/domain/*
frontend/src/api/*

tests/test_desktop.py

frontend/src/features/dashboard/*.test.tsx
frontend/e2e/*
docs/architecture.md
docs/performance.md
plan_update.md

Recherche aussi globalement :

webview.start
create_window
private_mode
storage_path
clear_cookies
provider window
maximize
get_size
get_position
resize
move
skin_preview_url
champion_icon_url
rune
priority-card
"Prêt"

La codebase actuelle est la source de vérité.

Avant de coder :
- comprendre comment la fenêtre principale stocke actuellement sa géométrie ;
- comprendre comment ProviderBrowserWindow est créé/préchargé/réaffiché ;
- vérifier si WebView2/pywebview possède déjà un stockage persistant configuré ;
- vérifier comment les previews champion/skin sont construites ;
- vérifier les tests existants avant d’en ajouter.


/agent-workflow

Utilise plusieurs sous-agents.

SUBAGENT A — WebView persistence

Audit :
- pywebview.start ;
- cookies ;
- localStorage ;
- storage path ;
- private mode ;
- lifecycle startup/shutdown.

Objectif :
proposer le changement minimal pour rendre le stockage WebView2 persistant.


SUBAGENT B — Window geometry

Audit :
- fenêtre principale ;
- ProviderBrowserWindow ;
- état maximisé ;
- coordonnées ;
- multi-écran ;
- preload/show.

Objectif :
déterminer comment faire hériter les fenêtres Stats/Live de la géométrie actuelle de la fenêtre principale.


SUBAGENT C — Dashboard cards

Audit :
- ChampionPriorityCard ;
- previews skin/champion ;
- rune icons ;
- CSS.

Objectif :
implémenter les changements visuels sans modifier le comportement métier.


SUBAGENT D — Tests / review

Identifier :
- tests existants impactés ;
- cas de régression ;
- tests à ajouter ;
- documentation à corriger.

Après chaque sous-agent :
1. lire son résultat ;
2. vérifier ses affirmations dans le code ;
3. review son diff ;
4. ne pas accepter une solution inutilement complexe.

À la fin, lancer un reviewer indépendant sur le diff complet.


/1-webview-cookie-persistence

PROBLÈME

Les providers affichés dans Statistiques / En direct redemandent régulièrement le consentement cookies après redémarrage d’OTP LOL.

Vérifier la configuration réelle du `webview.start()`.

Si pywebview fonctionne encore avec son mode privé par défaut, configurer explicitement un stockage persistant.


OBJECTIF

Les WebViews providers doivent partager un profil WebView2 OTP LOL stable entre les lancements.

Conceptuellement :

webview.start(
    ...,
    private_mode=False,
    storage_path=<persistent OTP LOL path>,
)

Ne copie pas aveuglément cet exemple :
utilise l’API exacte de la version pywebview réellement installée.


/storage-path

Utiliser un répertoire stable appartenant à OTP LOL.

Préférer le système de paths existant dans :

src/config/paths.py

Par exemple conceptuellement :

%LOCALAPPDATA%\OTP LOL\webview-data

ou un chemin déjà standardisé par l’application.

Ne PAS utiliser :
- tempfile ;
- dossier dépendant du PID ;
- dossier recréé à chaque lancement ;
- repository local ;
- working directory.


/storage-behavior

Le profil doit permettre aux sites providers de conserver notamment :

- cookies ;
- consentements cookies ;
- localStorage ;
- préférences du provider.

Ne jamais effacer automatiquement ce stockage :
- au shutdown ;
- à la fermeture d’une ProviderWindow ;
- au changement Stats ↔ Live.

Ne pas appeler automatiquement :
clear_cookies()

Ne pas créer un profil par ouverture.

Un profil WebView2 OTP LOL persistant est suffisant sauf contrainte démontrée dans l’API actuelle.


/privacy

Ne logge jamais :
- contenu des cookies ;
- tokens ;
- localStorage ;
- données de session provider.

Les logs peuvent uniquement indiquer :

webview_storage persistent=true path=<safe path>


/cookie-tests

Ajouter un test Python qui vérifie que le lancement pywebview utilise :
- private mode désactivé ;
- storage path stable.

Ne tente pas de simuler le consentement réel OP.GG en unittest.

Prévoir une validation Windows manuelle :

1. lancer OTP LOL ;
2. ouvrir OP.GG ;
3. accepter les cookies ;
4. fermer complètement OTP LOL ;
5. relancer ;
6. ouvrir OP.GG ;
7. vérifier que le consentement est conservé.

Faire également un smoke test avec au moins :
- DeepLOL ;
- Porofessor ou provider Live actuel.


/2-provider-window-geometry

PROBLÈME

Les fenêtres Statistiques / En direct sont actuellement plus petites que la fenêtre principale.

OBJECTIF

Lorsqu’un provider est affiché, sa fenêtre doit adopter la géométrie courante de la fenêtre OTP LOL principale.


/expected-behavior

Cas normal :

OTP LOL :
1280 × 800
position x=100 y=80

→ Stats :
1280 × 800
position équivalente ou intelligemment ajustée.


Cas maximisé :

OTP LOL maximisé
→ Stats maximisé.


Cas Live :

OTP LOL maximisé
→ Alt+P / En direct
→ fenêtre Live maximisée.


Cas redimensionnement :

OTP LOL redimensionné à 1500 × 900
→ ouverture Stats
→ Stats s’ouvre à environ 1500 × 900.


/important-definition

Quand je dis « plein écran », ici je veux reproduire l’état de la fenêtre OTP LOL.

Si OTP LOL est simplement MAXIMISÉ dans Windows :
→ maximiser la fenêtre provider.

Ne transforme pas automatiquement cela en vrai mode fullscreen borderless/F11.

Si l’application possède un véritable état fullscreen distinct, traite-le séparément seulement si le code le supporte déjà proprement.


/geometry-source

Ne duplique pas la logique de lecture de géométrie.

La fenêtre principale possède déjà ou doit posséder une méthode centrale fournissant quelque chose du type :

{
    width,
    height,
    x,
    y,
    maximized
}

Réutiliser cette source de vérité.


/provider-geometry-sync

Créer une méthode centrale claire, par exemple conceptuellement :

sync_with_main_window_geometry()

ou :

apply_main_window_geometry(provider_window)

Elle doit être utilisée pour :
- Stats ;
- Live.

Ne pas coder deux implémentations différentes.


/when-to-sync

Synchroniser AU MOMENT où l’utilisateur demande réellement l’affichage.

Pas uniquement lors du preload.

Pourquoi :

startup :
OTP LOL = 1200x700
provider préchargé

plus tard :
user maximise OTP LOL

puis :
clic Stats

→ Stats doit être maximisé.

Donc :

preload
→ peut utiliser une taille technique raisonnable

show/focus utilisateur
→ récupérer la géométrie ACTUELLE
→ appliquer
→ afficher.


/normal-window

Si main n’est pas maximisée :

1. restaurer la provider window si nécessaire ;
2. resize avec width/height ;
3. positionner correctement ;
4. show ;
5. focus.


/maximized-window

Si main est maximisée :

1. show provider ;
2. maximize provider ;
3. focus.

Vérifier l’ordre le plus fiable avec pywebview/WebView2 réel.


/multi-monitor

Ne crée pas de nouvelle logique complexe si l’application dispose déjà d’une validation multi-écran.

Réutilise `_valid_window_position` ou équivalent si disponible.

Éviter qu’une fenêtre provider réapparaisse :
- hors écran ;
- sur un ancien écran débranché.


/do-not-over-sync

Ne synchronise pas en permanence les deux fenêtres.

Pas besoin que :

resize OTP LOL en temps réel
→ resize OP.GG milliseconde par milliseconde.

Synchronisation à chaque ouverture/show suffit.

C’est plus simple et plus robuste.


/preload-regression

IMPORTANT :

Ne casse pas le système de preload providers actuellement fonctionnel.

Conserver :

startup
→ provider Stats préchargé
→ provider Live préchargé
→ fenêtre cachée
→ clic utilisateur
→ fenêtre déjà chargée
→ geometry sync
→ show/focus

Le changement de géométrie ne doit pas réintroduire :
- double fenêtre ;
- `Main window failed to start` ;
- WebView cachée définitivement ;
- reload complet du site au show.


/3-remove-ready-text

Dans ChampionPriorityCard :

actuellement une card configurée affiche quelque chose comme :

Garen
Prêt

Lux
Prêt

Ashe
Prêt

Supprimer le texte :

Prêt

Il est redondant puisque :
- la section indique déjà `3/3 prêt` ;
- la présence d’un champion configuré est évidente.

Résultat :

Garen

Lux

Ashe

Conserver uniquement un sous-texte s’il apporte une information réellement utile pour un état différent.

Card vide :
« Configurer un champion »
peut évidemment rester.

Ne supprimer aucun indicateur fonctionnel ailleurs dans le Dashboard.


/4-rune-icons-cleanup

PROBLÈME

Les icônes de rune sont actuellement affichées dans des wrappers avec bordure/background donnant un effet de cadrillage.

OBJECTIF

Afficher les runes comme des assets graphiques transparents.


/rune-style

Pour les icônes de rune du Dashboard :

- pas de border ;
- pas de carré autour ;
- pas de background visible ;
- pas de box-shadow ;
- pas d’effet bouton.

Conserver :
- dimensions constantes ;
- alignement ;
- title/alt ;
- rune principale ;
- rune secondaire.

La rune principale peut rester légèrement plus grande que la rune secondaire.


/important-css

Inspecter à la fois :
- `<img>` ;
- wrapper autour de `<img>` ;
- AssetImage ;
- parent `.priority-*`.

Ne te contente pas de :

img {
    border: none;
}

si le carré vient du parent.


/summoners

Ce changement concerne les RUNES.

Ne retire pas automatiquement le style des icônes Summoner si leur présentation actuelle est cohérente.


/5-skin-row-image

PROBLÈME

Lorsqu’un skin fixe est sélectionné :

Grande image :
→ splash God-King Garen

Ligne SKIN :
→ encore une miniature du même skin

C’est redondant.


/expected-skin-layout

Grande zone supérieure :

skin_mode=fixed
→ splash du skin sélectionné.

skin_mode=random
→ comportement actuel de preview random si pertinent.

skin_mode=none
→ splash champion de base.


Ligne SKIN inférieure :

TOUJOURS afficher l’icône carrée du CHAMPION DE BASE.


Exemple :

Grande image :
God-King Garen splash

Ligne :
SKIN
[Garen champion square icon]
God-King Garen


/skin-thumbnail-source

Utiliser prioritairement quelque chose du type :

preview?.champion_icon_url

fallback :

champion?.icon_url

Le nom exact doit être déterminé après inspection de la codebase.


NE PAS utiliser dans la ligne skin :

skin_preview_url

ou un splash.


/asset-format

Je veux une icône carrée comme dans le champion select League.

Donc utiliser :
- champion icon carré Data Dragon/LCU existant ;
- pas champion splash ;
- pas skin splash ;
- pas recadrage CSS artificiel d’un splash si une vraie icône champion existe déjà.


/skin-modes

Le comportement doit être cohérent dans les trois modes :

NONE

Grande image :
→ splash champion base

ligne SKIN :
→ icône champion
→ Aucun


FIXED

Grande image :
→ splash skin fixe

ligne SKIN :
→ icône champion
→ nom du skin


RANDOM

Grande image :
→ preview random actuelle si disponible

ligne SKIN :
→ icône champion
→ Aléatoire / libellé actuel approprié.


/tests-dashboard

Mettre à jour/ajouter les tests ChampionPriorityCard.

Cas obligatoires :

1.
skin_mode=fixed
→ `.priority-art img` utilise `skin_preview_url`.

2.
skin_mode=fixed
→ thumbnail ligne SKIN utilise `champion_icon_url`.

3.
skin_mode=none
→ grande image utilise champion splash.

4.
skin_mode=none
→ thumbnail ligne SKIN utilise quand même champion icon.

5.
champion_icon_url absent
→ fallback `champion.icon_url`.

6.
texte `Prêt`
→ absent d’une card configurée.

7.
rune icon
→ utilise la classe/wrapper non encadré attendu.


/desktop-tests

Ajouter ou adapter les tests dans `tests/test_desktop.py`.

Tester au minimum :

test_webview_uses_persistent_storage

test_provider_window_matches_main_window_size

test_provider_window_matches_main_window_position

test_provider_window_maximizes_when_main_is_maximized

test_provider_window_restores_when_main_is_not_maximized

test_provider_preload_is_not_broken_by_geometry_sync


Utiliser les fakes pywebview existants.

Ne nécessite pas un vrai OP.GG dans les unittests.


/logging

Ajouter des logs utiles pour le debug de géométrie.

Exemple :

provider_geometry_sync kind=stats width=1500 height=900 maximized=False

ou :

provider_geometry_sync kind=live maximized=True

Pas besoin de logs à chaque resize de Windows puisque la sync n’est faite qu’au show.


/plan-update

Avant implémentation :

mettre `plan_update.md` à jour avec une checklist courte.

Exemple :

# Provider persistence + Dashboard card polish

## WebView
[ ] Audit storage
[ ] Persistent WebView profile
[ ] Cookie persistence test

## Provider geometry
[ ] Main geometry source
[ ] Stats geometry sync
[ ] Live geometry sync
[ ] Maximized state
[ ] Multi-monitor safety
[ ] Preload regression

## Dashboard
[ ] Remove Prêt
[ ] Rune icons borderless
[ ] Champion icon in skin row

## Validation
[ ] Python tests
[ ] Frontend tests
[ ] E2E
[ ] Native Windows smoke
[ ] Independent review

Ne recopie pas ce prompt entier dans plan_update.md.


/implementation-order

PHASE 1
Lire la codebase et confirmer les causes exactes.

PHASE 2
Implémenter persistent WebView storage.

PHASE 3
Tests storage.

PHASE 4
Implémenter provider geometry sync.

PHASE 5
Tests geometry + preload.

PHASE 6
Modifier ChampionPriorityCard.

PHASE 7
CSS runes.

PHASE 8
Tests frontend.

PHASE 9
Full validation.

PHASE 10
Reviewer indépendant.


/review-requirements

Après chaque phase :

- relire le diff ;
- vérifier les tests ciblés ;
- vérifier qu’aucune API métier n’a changé ;
- vérifier qu’aucune migration n’a été ajoutée ;
- vérifier qu’aucune nouvelle dépendance n’est nécessaire sans justification.


/independent-final-review

Une fois terminé, lancer un sous-agent reviewer indépendant.

Demande-lui de chercher précisément :

WEBVIEW
- storage réellement persistant ;
- chemin stable ;
- risque de suppression au shutdown ;
- comportement privé accidentel ;
- fuite/logging de données sensibles.

WINDOWS
- provider plus petit que main ;
- maximized non reproduit ;
- mauvais monitor ;
- mauvaise position ;
- preload cassé ;
- changement Stats ↔ Live.

DASHBOARD
- texte Prêt encore présent ;
- rune wrapper encore encadré ;
- skin affiché deux fois ;
- utilisation accidentelle d’un splash dans la miniature skin ;
- régression des cards.

Valider toi-même chaque finding avant correction.


/validation

Exécuter toutes les commandes réelles du repository.

Python :
- compileall
- tests Python concernés puis suite complète
- Ruff selon la CI

Frontend :
- npm run test
- npm run typecheck
- npm run api:check
- npm run build
- npm run test:e2e

Puis :

git diff --check


/manual-windows-validation

Cette partie est OBLIGATOIRE à documenter comme validation manuelle si Codex ne peut pas la réaliser lui-même.


COOKIES

1. Démarrer OTP LOL.
2. Ouvrir Statistiques.
3. Accepter cookies provider.
4. Fermer complètement OTP LOL.
5. Relancer.
6. Rouvrir Statistiques.
7. Consentement doit être conservé.

Tester également Live.


WINDOW SIZE

1. OTP LOL en fenêtre 1200x800.
2. Ouvrir Stats.
3. Stats doit reprendre approximativement taille + position.

4. Maximiser OTP LOL.
5. Ouvrir Live.
6. Live doit être maximisé.

7. Restaurer OTP LOL.
8. Resize.
9. Rouvrir Stats.
10. Stats doit utiliser la nouvelle géométrie.


PRELOAD

Vérifier que :
- les sites continuent à charger en background ;
- le show reste rapide ;
- aucune nouvelle exception pywebview.


DASHBOARD

Vérifier :
- aucun « Prêt » sous Garen/Lux/Ashe ;
- runes sans carrés/bordures ;
- grande image = skin splash ;
- ligne SKIN = icône carrée champion ;
- aucun changement fonctionnel des presets.


/dont-do

NE PAS :

- changer le backend métier League ;
- modifier Champ Select ;
- modifier les routes frontend ;
- modifier le schema settings ;
- ajouter une migration ;
- supprimer les cookies au shutdown ;
- créer un profil navigateur temporaire ;
- créer un profil différent à chaque provider sans raison ;
- synchroniser les dimensions en boucle permanente ;
- transformer maximized en fullscreen F11 par erreur ;
- utiliser le skin splash comme miniature de la ligne SKIN ;
- recadrer artificiellement un splash alors qu’un champion_icon_url existe ;
- modifier la logique des runes ;
- modifier la logique des skins.


/done-definition

La tâche est terminée seulement si :

1. pywebview utilise un stockage persistant ;
2. les cookies peuvent survivre à un restart de l’application ;
3. aucun cookie/token n’est loggé ;
4. Stats reprend la géométrie de la fenêtre principale ;
5. Live reprend la géométrie de la fenêtre principale ;
6. main maximisée → provider maximisé ;
7. main normale → provider normal ;
8. preload providers reste fonctionnel ;
9. aucun « Prêt » inutile sous les champions ;
10. runes sans cadrillage ;
11. grande image fixe = skin sélectionné ;
12. ligne SKIN = champion icon carré ;
13. tests Python passent ;
14. tests frontend passent ;
15. Playwright passe ;
16. reviewer indépendant n’a aucun problème concret non traité.


/final-report

À la fin, fournir :

- cause précise du problème de cookies ;
- configuration WebView avant/après ;
- emplacement du profil WebView persistant ;
- fonctionnement de la synchronisation de géométrie ;
- modifications Dashboard ;
- fichiers modifiés ;
- tests ajoutés/modifiés ;
- résultats chiffrés ;
- résultat de la review indépendante ;
- validations Windows encore nécessaires.

Confirmer explicitement :

- aucune migration ;
- aucun changement de schema ;
- aucun changement du moteur League/LCU ;
- aucun commit/push sauf demande explicite.