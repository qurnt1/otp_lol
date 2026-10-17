/goal

Refondre OTP LOL pour supprimer complètement l’onglet/page frontend « Presets » et faire du Dashboard l’unique surface de consultation ET de modification des presets.

Le résultat final doit être plus simple pour l’utilisateur :

- le Dashboard reste la vue principale ;
- les 3 cartes de presets sont visibles sur le Dashboard comme actuellement ;
- cliquer sur une carte ouvre directement son éditeur au-dessus du Dashboard ;
- cliquer sur la carte de ban ouvre directement son picker au-dessus du Dashboard ;
- il n’existe plus de page/onglet Presets séparé ;
- il ne doit plus rester de navigation active vers `#presets`;
- le concept métier de preset reste intégralement conservé côté backend/configuration/champ select ;
- AUCUNE migration de données ou de settings n’est souhaitée.

L’objectif est de supprimer une duplication d’interface, pas de refondre le moteur métier des presets.


/context

OTP LOL est actuellement une application desktop :

- backend Python / FastAPI ;
- frontend React / TypeScript / Vite ;
- pywebview / WebView2 côté desktop ;
- intégration League Client / LCU ;
- React Query pour le frontend.

Aujourd’hui, le Dashboard affiche déjà :

- les trois priorités de champions ;
- sorts ;
- runes ;
- skins ;
- ban ;
- état des automatisations ;
- previews des presets ;
- accès rapides.

Mais une page `PresetsPage` séparée existe encore et répète une grande partie de cette présentation uniquement pour fournir les workflows d’édition.

Le but est de conserver la qualité des éditeurs existants (`PresetEditorDialog`, ChampionPicker, RunePicker, SkinPicker, PickerDialog, etc.) tout en supprimant leur page dédiée.

IMPORTANT :
ne pars pas du principe que ce prompt décrit parfaitement l’état actuel du repo.

La codebase fournie est la seule source de vérité.


/mandatory-first-step

AVANT TOUTE MODIFICATION :

1. Lis l’intégralité de la codebase.

Je veux réellement une lecture complète du repository avant modification, pas seulement les fichiers qui semblent directement concernés.

Inspecte au minimum, mais sans te limiter à :

- frontend/src/App.tsx
- frontend/src/app/*
- frontend/src/features/dashboard/*
- frontend/src/features/presets/*
- frontend/src/features/automation/*
- frontend/src/features/settings/*
- frontend/src/content/*
- frontend/src/types/*
- frontend/src/api/*
- frontend/src/styles/*
- frontend/e2e/*
- tests/*
- src/api/*
- src/config/*
- src/core/*
- src/services/*
- docs/*
- README / PRODUCT / DESIGN / plan_update / track_updates

2. Recherche globalement toutes les occurrences et dépendances de :

- presets
- PresetsPage
- PresetCard
- PresetsAction
- PresetSlotKey
- #presets
- page === "presets"
- nav.presets
- returnTo
- reviewSequence
- onboarding vers Presets

3. Identifie avant modification :

- ce qui appartient réellement au concept métier « preset » et doit rester ;
- ce qui appartient uniquement à l’ancienne page UI « Presets » et doit disparaître ;
- les tests affectés ;
- les docs affectées ;
- les routes profondes affectées ;
- les styles devenus morts ;
- les imports devenus morts.

4. Fais un résumé interne de l’architecture et du plan avant de toucher au code.

Ne commence PAS par supprimer `PresetsPage` puis réparer les erreurs une par une.


/agent-workflow

Utilise des sous-agents pour analyser et implémenter ce chantier.

Le sous-agent principal ne doit jamais être considéré comme fiable par défaut.

Tu restes responsable de l’intégration finale.

Organisation suggérée :

SUBAGENT A — Architecture / Routing
- inspecte App.tsx, routes.ts, useHashRoute, AppShell, types ;
- recense tous les liens vers #presets ;
- propose le nouveau contrat de routing Dashboard ;
- analyse les conséquences navigation/back/forward/deep links.

SUBAGENT B — Preset editing workflow
- inspecte complètement PresetsPage et tous ses enfants ;
- identifie exactement quelle logique doit être extraite/réutilisée ;
- vérifie mutations, optimistic updates, focus, dialogs, pickers, loading/error states ;
- propose un composant d’orchestration réutilisable depuis Dashboard.

SUBAGENT C — Dashboard / UX
- inspecte DashboardPage, ChampionPriorityCard, BanPanel, QuickActions, onboarding ;
- détermine comment intégrer l’édition sans dupliquer l’état ni les queries ;
- vérifie responsive/accessibility/focus.

SUBAGENT D — Tests / cleanup / documentation
- inspecte Vitest, Playwright, Python, docs et styles ;
- liste tous les tests à migrer ;
- recherche le code mort après suppression de PresetsPage ;
- identifie les docs devenues fausses.

Après chaque sous-agent :

1. Lis réellement son résultat.
2. Vérifie toi-même ses affirmations dans le code.
3. Refuse toute suggestion qui :
   - ajoute une migration inutile ;
   - change le backend sans nécessité ;
   - duplique la logique existante ;
   - introduit une abstraction sans utilité ;
   - casse une fonctionnalité existante.
4. Ne merge/intègre son code que si tu l’as relu.
5. Passe `git diff` sur son travail.
6. Corrige toi-même ce qui est incorrect.

Si plusieurs sous-agents écrivent du code :
- évite qu’ils modifient simultanément les mêmes fichiers ;
- travaille par scopes disjoints ou séquentiellement ;
- fais une revue d’intégration après chaque lot.

À la fin, lance un DERNIER sous-agent reviewer indépendant.

Ce reviewer doit :
- lire le diff final ;
- chercher des régressions ;
- chercher des routes mortes ;
- chercher des imports/CSS/textes morts ;
- vérifier les parcours utilisateurs ;
- vérifier que le backend n’a pas été modifié inutilement ;
- vérifier l’accessibilité ;
- vérifier les tests.

Ensuite :
- relis toi-même le rapport du reviewer ;
- ne corrige que les problèmes concrets et justifiés ;
- ne crée pas de faux problèmes pour satisfaire la revue.


/target-architecture

Architecture UX cible :

Dashboard
│
├── informations runtime
├── automatisations
├── priorités
│   ├── Preset 1 → éditeur
│   ├── Preset 2 → éditeur
│   └── Preset 3 → éditeur
├── Ban → picker
├── accès rapides
└── barre d’automatisation

Le Dashboard doit devenir simultanément :

- vue de synthèse ;
- point d’entrée de configuration des presets.

Il ne doit plus exister :

Dashboard
→ page Presets
→ éditeur

mais :

Dashboard
→ clic card
→ éditeur par-dessus Dashboard.


/routing

Remplace la page dédiée Presets par des sous-routes du Dashboard.

Architecture attendue :

#dashboard
#dashboard/pick_1
#dashboard/pick_2
#dashboard/pick_3
#dashboard/ban

Les types devraient conceptuellement converger vers quelque chose comme :

DashboardAction =
- pick_1
- pick_2
- pick_3
- ban

PageId ne doit plus contenir `presets`.

AppRoute doit pouvoir représenter :

- dashboard sans action ;
- dashboard + action ;
- settings + section ;
- autres pages normales.

Supprime complètement :

- page UI `presets`;
- `PresetsAction` si uniquement utilisé par l’ancien routing ;
- `returnTo`;
- logique `?return=dashboard`;
- traitement spécial `#presets`;
- génération de hash `#presets/...`.

IMPORTANT :
ne crée PAS de route legacy ou de migration automatique :

#presets → #dashboard

Ce n’est pas demandé.

Un ancien `#presets` peut simplement devenir une route invalide et utiliser le fallback normal du routeur.


/dashboard-integration

Le Dashboard actuel doit rester visuellement la base.

Ne remplace pas son UI par celle de PresetsPage.

Les `ChampionPriorityCard` doivent devenir les déclencheurs des éditeurs.

Exemple :

Preset 1
→ clic n’importe où sur la card
→ #dashboard/pick_1
→ PresetEditorDialog

Preset 2
→ #dashboard/pick_2

Preset 3
→ #dashboard/pick_3

Toute la card doit rester cliquable.

Conserver :
- previews actuelles ;
- champion ;
- spells ;
- rune ;
- skin ;
- style actuel ;
- états empty/configured.

Adapter aria-label et accessibilité si nécessaire.

Le lien global « Modifier » / « Edit » dans le header des priorités devient probablement redondant.

S’il ne sert plus :
- le supprimer ;
- ou le remplacer par une aide textuelle légère du type « Cliquez sur une priorité pour la modifier ».

Ne crée pas une deuxième méthode concurrente d’édition.


/preset-editor-refactor

NE COPIE PAS le contenu entier de `PresetsPage.tsx` dans `DashboardPage.tsx`.

Je ne veux pas transformer DashboardPage en composant de 500–800 lignes.

Extrais le workflow d’édition dans un contrôleur dédié.

Architecture suggérée, à adapter après lecture réelle :

frontend/src/features/presets/
    PresetEditorFlow.tsx
    PresetEditorDialog.tsx
    ChampionPicker.tsx
    PickerDialog.tsx
    RunePicker.tsx
    SkinPicker.tsx
    picker-utils.ts

`PresetEditorFlow` doit récupérer/réutiliser la logique actuellement utile de PresetsPage :

- editing slot ;
- picker state ;
- optimistic update preset ;
- update settings ;
- champion selection ;
- rune selection ;
- skin selection ;
- spell changes ;
- feedback save/error ;
- loading states ;
- selected ban ;
- focus restoration ;
- dialog lifecycle.

Il doit recevoir quelque chose du style :

action?: DashboardAction
onClose()
trigger refs si nécessaires

Il ne doit rendre aucune nouvelle page.

Il doit seulement rendre :
- PresetEditorDialog pour un slot ;
- PickerDialog pour le ban ;
- pickers enfants nécessaires.


/performance

Ne dégrade pas le temps de démarrage du Dashboard.

Le Dashboard normal ne doit pas charger inutilement :

- catalogue champions complet ;
- skins ;
- runes ;
- logique de picker ;
- éditeur complet.

Si approprié, lazy-load `PresetEditorFlow` uniquement lorsqu’une action Dashboard existe.

Les données lourdes doivent rester conditionnelles :

RunePicker ouvert
→ fetch runes

SkinPicker ouvert
→ fetch skins

Champion picker / éditeur nécessaire
→ catalogue champions si nécessaire

Ne transforme pas le Dashboard en écran qui fetch tout au démarrage.


/ban

`BanPanel` doit fonctionner exactement comme les cards :

clic BanPanel
→ #dashboard/ban
→ picker ban

Supprimer :

#presets/ban?return=dashboard

Supprimer toute logique `returnTo`.

Après fermeture :
→ #dashboard

Après modification :
- la valeur affichée sur Dashboard doit se mettre à jour ;
- bootstrap/previews nécessaires doivent être invalidés comme aujourd’hui.


/focus-accessibility

Préserve ou améliore le comportement clavier existant.

Cas à garantir :

- clic/Enter sur card Preset 1 → dialog ;
- Escape / fermer → retour du focus sur Card 1 ;
- Card 2 → retour Card 2 ;
- Card 3 → retour Card 3 ;
- Ban → retour BanPanel ;
- RunePicker fermé → retour sur bouton Rune ;
- SkinPicker fermé → retour sur bouton Skin ;
- ChampionPicker fermé → retour sur bouton Champion.

Comme les triggers Dashboard peuvent être des `<a>`, évite les types trop spécifiques comme :

HTMLButtonElement

si le besoin réel est :

HTMLElement.

Utilise les primitives accessibles déjà présentes.

Ne remplace pas une vraie navigation profonde par des divs `onClick` non accessibles.


/sidebar

Supprime complètement l’entrée Presets de la sidebar.

Navigation finale attendue :

- Dashboard
- Statistiques
- En direct
- Journal de logs
- Réglages

Diagnostics peut conserver son mode d’accès existant si c’est actuellement le comportement voulu.

Nettoie :
- import d’icône devenu inutile ;
- `fr.nav.presets` si plus utilisé ;
- types associés.


/quick-actions

Revois les accès rapides du Dashboard.

Actuellement certaines actions deviennent redondantes.

Je veux éviter :
- « revoir les presets » alors que les presets sont juste au-dessus ;
- « choisir site stats dans Settings » si le choix se fait déjà directement dans la page Statistiques/Live.

Proposition :

- Statistiques → #statistics
- En direct → #live
- Journal de logs → #history
- Diagnostics LCU → #diagnostics
- Raccourcis clavier → #settings/shortcuts

Adapte en fonction de la codebase réelle après lecture.

Ne garde aucun lien vers #presets.


/onboarding

Le CTA de l’onboarding ne doit plus envoyer vers Presets.

Nouvelle logique :

« Configurer mes priorités »

→ ouvre directement un slot sur Dashboard.

Idéalement :

- premier slot vide ;
- sinon pick_1.

Exemple :

pick_1 configuré
pick_2 vide
→ CTA = #dashboard/pick_2

Si les trois existent :
→ #dashboard/pick_1

Ne modifie pas la donnée `onboarding_completed` ni son stockage.


/backend

IMPORTANT — NE PAS REFACTORER LE BACKEND POUR CE CHANTIER.

Conserver intégralement le concept métier « presets ».

Ne pas supprimer/renommer :

- `/api/presets`
- `/api/presets/{slot_key}`
- `/api/presets/reset`
- `/api/presets/clear`
- `PresetsResponse`
- `PresetSlotPatch`
- `presets_enabled`
- selected_pick_1
- selected_pick_2
- selected_pick_3
- selected_ban
- profile_config
- champ_select
- logique d’automatisation
- import/export settings.

La disparition de la page frontend Presets ne doit pas changer le contrat métier.

Je ne veux PAS d’un renommage massif :

preset → priority

Les « presets » restent le nom technique du concept.

Seule la navigation et la page UI Presets disparaissent.


/no-migration

AUCUNE migration.

Ne change pas :

- CONFIG_SCHEMA_VERSION ;
- format settings ;
- JSON utilisateur ;
- presets persistés ;
- format import/export.

N’ajoute pas :
- migrate_vX_to_vY ;
- legacy compatibility ;
- route redirect pour #presets ;
- conversion de données.

Si tu estimes qu’une migration est nécessaire :
ARRÊTE et démontre précisément pourquoi avant de l’implémenter.

Dans le contexte de cette demande, elle ne devrait pas être nécessaire.


/types-cleanup

Si `PresetSlotKey` est actuellement défini dans un composant UI destiné à être supprimé, déplace ce type dans un emplacement neutre.

Par exemple :

frontend/src/domain/presets.ts

avec :

presetSlotKeys = ["pick_1", "pick_2", "pick_3"]

PresetSlotKey = union dérivée.

Évite les définitions dupliquées de :

pick_1 | pick_2 | pick_3

dans plusieurs composants.


/delete-dead-ui

Une fois Dashboard opérationnel, supprimer réellement l’ancienne page.

Candidats probables :

- PresetsPage.tsx
- PresetCard.tsx
- tests uniquement liés à PresetCard

Mais ne supprime un fichier qu’après avoir vérifié qu’aucun autre flux utile n’en dépend.

Conserver les composants d’édition encore utilisés.


/css-cleanup

Après suppression de l’ancienne page, rechercher tous les sélecteurs devenus morts.

Supprimer uniquement les CSS propres à l’ancienne présentation Presets.

Probables candidats :
- preset-grid
- preset-card*
- preset-summary*
- ban-editor

mais vérifie chaque utilisation.

NE SUPPRIME PAS les styles encore utilisés par :
- PresetEditorDialog
- PickerDialog
- ChampionPicker
- RunePicker
- SkinPicker
- PresetAutomationMaster
- PresetOnboardingBanner.

Faire une recherche globale avant toute suppression.


/copy-cleanup

Rechercher tous les textes utilisateurs parlant d’une page Presets dédiée.

Mettre à jour les formulations.

Exemples :

« Aller dans Presets »
→ supprimer.

« Modifier mes presets »
→ éventuellement « Configurer mes priorités ».

« Revoir la séquence »
→ supprimer des accès rapides.

Ne change pas inutilement le terme métier « preset » dans les textes où il reste pertinent.


/tests

Les tests de l’ancienne page ne doivent pas simplement être supprimés.

Ils doivent être transférés vers le nouveau parcours Dashboard.

Créer/adapter une couverture complète.

ROUTING

- #dashboard valide.
- #dashboard/pick_1 valide.
- #dashboard/pick_2 valide.
- #dashboard/pick_3 valide.
- #dashboard/ban valide.
- #dashboard/foo invalide.
- #presets invalide.
- #presets/pick_1 invalide.
- routeToHash Dashboard correcte.

SIDEBAR

- aucun item Presets.
- Dashboard actif pour #dashboard/pick_1.
- aucune navigation vers #presets.

DASHBOARD

- les 3 cards sont visibles.
- clic Preset 1 ouvre l’éditeur.
- clic Preset 2 ouvre l’éditeur.
- clic Preset 3 ouvre l’éditeur.
- clic ban ouvre picker.
- Dashboard reste monté/visible derrière le dialog.

EDITIONS

- changer champion met à jour la card.
- changer spell 1.
- changer spell 2.
- changer rune.
- « Ne rien faire » pour runes.
- changer skin fixed.
- random skin.
- aucun skin.
- erreur API → rollback / feedback.
- sauvegarde → cache mis à jour.
- bootstrap invalidé lorsque nécessaire.

BAN

- changement ban.
- suppression/absence éventuelle.
- focus restitué.

NAVIGATION

- ouvrir #dashboard/pick_1 directement.
- fermer → #dashboard.
- bouton Back ferme le dialog correctement.
- Forward le réouvre si pertinent.
- passer vers Stats pendant éditeur ouvert.
- revenir Dashboard : aucun état zombie.

ONBOARDING

- premier slot vide choisi.
- aucune route #presets.

QUICK ACTIONS

- tous les liens pointent vers des destinations valides.
- aucun #presets.

REGRESSION

- reset presets.
- clear presets.
- presets_enabled.
- auto pick.
- auto ban.
- summoners/runes.
- skin automation.
- champ select backend non affecté.


/search-before-finish

Avant de considérer le chantier terminé, lance des recherches globales.

Je veux explicitement vérifier :

1. `#presets`
→ aucune occurrence active.

2. `PresetsPage`
→ aucune occurrence.

3. `page: "presets"`
→ aucune occurrence.

4. `page === "presets"`
→ aucune occurrence.

5. `PresetsAction`
→ aucune occurrence si ce type n’a plus d’utilité.

6. `returnTo`
→ aucune occurrence liée à Presets.

7. `PresetCard`
→ aucune occurrence si ce composant est supprimé.

8. `fr.nav.presets`
→ aucune occurrence si supprimé.

Les archives historiques peuvent évidemment conserver d’anciennes références.


/docs

Mettre à jour les documents actifs qui décrivent encore une page Presets séparée :

- README/readme
- PRODUCT.md
- DESIGN.md si concerné
- docs/architecture.md
- docs/V2_PARITY.md
- docs/SETTINGS_TEST_MATRIX.md
- docs/development.md si concerné.

Nouvelle source de vérité :

« Le Dashboard est la surface centrale d’OTP LOL. Les presets y sont affichés et configurés directement via leurs cartes. »

Ne réécris pas les fichiers d’archive historique pour faire croire que l’ancien design n’a jamais existé.


/plan-update

Avant de coder :
- mets `plan_update.md` à jour avec une checklist concise.

Pendant l’implémentation :
- coche uniquement les éléments réellement terminés.

Si un ancien plan détaillé encombre le fichier :
- archive-le dans `docs/archive/`.

Ne mets pas 500 lignes de prompt dans plan_update.md.


/validation

À la fin, lancer la validation complète applicable au repository.

Au minimum :

PYTHON
- suite pytest complète ;
- Ruff ;
- format/check si configuré ;
- compile/check Python ;
- git diff --check.

FRONTEND
- npm tests / Vitest ;
- typecheck ;
- build ;
- api:check ;
- Playwright complet.

Si des commandes sont définies dans package.json / CI, utilise les commandes réelles de la codebase plutôt que d’en inventer.


/manual-ux-review

Après les tests automatisés, faire une revue UX du diff.

Vérifier notamment :

- Dashboard pas surchargé ;
- aucun flash de la page Presets ;
- aucun chargement lourd ajouté au startup ;
- dialogs bien centrés ;
- responsive ;
- fenêtre minimum supportée ;
- clavier ;
- Escape ;
- focus ;
- animations ;
- textes français ;
- cartes entièrement cliquables ;
- aucune double source de vérité.


/independent-final-review

Une fois toute l’implémentation terminée :

1. lance un sous-agent reviewer indépendant ;
2. donne-lui le diff complet et l’état final du repo ;
3. demande-lui explicitement de chercher :
   - régressions ;
   - fonctionnalités perdues de PresetsPage ;
   - routes mortes ;
   - code mort ;
   - CSS mort ;
   - erreurs de cache React Query ;
   - problèmes de focus/accessibilité ;
   - surcharge du Dashboard ;
   - fetchs inutiles ;
   - modifications backend inutiles ;
   - migrations accidentelles ;
   - docs/tests obsolètes.

Ensuite :
- vérifie chacune de ses observations dans le code ;
- corrige uniquement les constats réellement justifiés ;
- rerun les tests ciblés après chaque correction ;
- puis rerun la suite complète finale.


/dont-do

Ne fais PAS :

- une migration de settings ;
- un bump de schema ;
- une nouvelle API backend inutile ;
- un renommage massif preset → priority ;
- une copie brute de PresetsPage dans DashboardPage ;
- un énorme DashboardPage monolithique ;
- une compatibilité legacy #presets ;
- une seconde UI différente pour modifier les mêmes presets ;
- un changement du moteur Champ Select sans raison ;
- une suppression de tests sans remplacement ;
- une validation « tout est bon » uniquement parce que les tests actuels passent.


/done-definition

Le chantier n’est terminé que si :

1. la sidebar ne contient plus Presets ;
2. la page Presets n’existe plus ;
3. #presets n’existe plus dans le code actif ;
4. les trois cards Dashboard ouvrent leurs éditeurs ;
5. le ban s’édite depuis Dashboard ;
6. toutes les fonctionnalités d’édition existantes sont conservées ;
7. fermer l’éditeur laisse l’utilisateur sur Dashboard ;
8. le focus revient correctement ;
9. Quick Actions et onboarding sont cohérents ;
10. aucun changement de schéma/migration n’a été ajouté ;
11. backend preset/champ-select reste fonctionnel ;
12. aucun CSS/import/composant mort évident ne reste ;
13. tests complets passent ;
14. reviewer indépendant n’a plus de problème concret non traité.


/final-report

À la fin, fournis un rapport court et factuel contenant :

- architecture finale ;
- fichiers principaux modifiés ;
- fichiers supprimés ;
- routes supprimées/ajoutées ;
- éventuels choix techniques importants ;
- tests exécutés avec résultats chiffrés ;
- résultats du reviewer indépendant ;
- éventuelles limites qui nécessitent encore une validation manuelle ;
- confirmation explicite :
  - aucune migration ajoutée ;
  - schema settings inchangé ;
  - backend métier presets inchangé sauf nécessité démontrée ;
  - aucun commit/push effectué sauf demande explicite.

Ne dis pas simplement « terminé ».

Explique ce qui a réellement été vérifié.