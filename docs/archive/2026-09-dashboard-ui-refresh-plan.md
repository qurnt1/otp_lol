/goal

Faire un refresh UI ciblé du Dashboard et de la Sidebar d’OTP LOL afin d’améliorer l’équilibre visuel, les espacements et la lisibilité, SANS modifier le comportement métier de l’application.

Le résultat final doit :

- rendre la sidebar moins tassée en haut et mieux répartie verticalement ;
- mieux aligner visuellement la hauteur du bloc principal « Priorité de sélection » avec la colonne « Ban automatique + Accès rapides » ;
- ajouter davantage d’espace entre la zone principale du Dashboard et le bloc « Automatisations » ;
- réorganiser les informations des cards de presets :
  - summoner spells sur une première ligne ;
  - runes + nom de la page de runes sur une deuxième ligne en dessous ;
  - skin sur sa propre ligne comme actuellement ;
- augmenter légèrement la hauteur des cards pour améliorer l’équilibre avec la colonne de droite ;
- conserver exactement les interactions, routes et comportements existants.

Ce chantier doit être frontend-only.


/context

OTP LOL est une application desktop Windows composée notamment de :

- frontend React / TypeScript / Vite ;
- FastAPI / Python côté backend ;
- pywebview / WebView2 ;
- React Query ;
- intégration LCU.

Le Dashboard vient d’être refactoré pour devenir la surface centrale de configuration des presets.

La page Presets dédiée n’existe plus.

Les trois cards de priorités du Dashboard sont maintenant directement cliquables et ouvrent leur éditeur via :

#dashboard/pick_1
#dashboard/pick_2
#dashboard/pick_3

Le ban est édité via :

#dashboard/ban

IMPORTANT :

Ce chantier ne doit PAS remettre en question cette architecture.

L’objectif est uniquement d’améliorer la présentation visuelle actuelle.


/visual-reference

Utilise la capture d’écran fournie par l’utilisateur comme référence de l’état actuel.

Les problèmes principaux visibles sont :

1. Sidebar trop concentrée vers le haut.
2. Les items Dashboard / Statistiques / En direct / Journal de logs / Réglages sont assez rapprochés.
3. Beaucoup d’espace vide sous la navigation alors que la partie haute paraît tassée.
4. Le bloc « Priorité de sélection » n’a pas exactement le même équilibre vertical que :
   - Ban automatique
   - Accès rapides
5. Le bloc Automatisations est trop proche de la zone supérieure, particulièrement sous Accès rapides.
6. Dans les cards :
   - sorts d’invocateur ;
   - runes ;
   - nom de page de runes ;
   sont actuellement trop regroupés horizontalement.
7. La hauteur des cards pourrait être légèrement augmentée pour mieux équilibrer la page.


/mandatory-first-step

AVANT DE MODIFIER QUOI QUE CE SOIT :

Lis toute la codebase.

Je ne veux pas que tu modifies uniquement `globals.css` après avoir regardé la capture.

Inspecte au minimum :

frontend/src/App.tsx

frontend/src/app/*
- AppShell.tsx
- routes.ts
- etc.

frontend/src/features/dashboard/*
- DashboardPage.tsx
- ChampionPriorityCard.tsx
- BanPanel.tsx
- QuickActions.tsx
- AutomationBar.tsx

frontend/src/features/automation/*
- PresetAutomationMaster.tsx
- PresetOnboardingBanner.tsx

frontend/src/features/presets/*
pour comprendre les interactions des cards et dialogs.

frontend/src/styles/globals.css

frontend/e2e/*
notamment :
- dashboard-connected.spec.ts
- dashboard-disconnected.spec.ts
- presets.spec.ts
- navigation.spec.ts
- ui-smoke.spec.ts
- window-layout.spec.ts

frontend/src/**/*.test.tsx

DESIGN.md
PRODUCT.md
docs/* pertinents.

Lis aussi le reste du repository suffisamment pour confirmer qu’aucun comportement métier ne dépend du markup/CSS que tu modifies.

La codebase réelle est la source de vérité.

Si le code actuel diffère de ce prompt, adapte le plan à l’état réel.


/agent-workflow

Utilise plusieurs sous-agents.

Je veux une vraie organisation analyse → implémentation → review.

SUBAGENT A — Dashboard layout audit

Mission :
- inspecter DashboardPage ;
- inspecter la grille principale ;
- inspecter la colonne principale et l’aside ;
- analyser les hauteurs actuelles ;
- identifier exactement pourquoi :
  - Presets ;
  - Ban automatique ;
  - Accès rapides ;
  - Automatisations ;
  ne s’alignent pas parfaitement.

Il doit proposer une modification minimale de layout.

Il ne doit pas écrire du code métier.


SUBAGENT B — Preset card UI

Mission :
- inspecter ChampionPriorityCard ;
- inspecter ses styles ;
- analyser la structure actuelle :
  - splash ;
  - champion ;
  - summoners ;
  - runes ;
  - rune page name ;
  - skin.

Il doit proposer le nouveau layout interne sans casser :
- lien sur toute la card ;
- focus clavier ;
- hover ;
- aria ;
- images ;
- fallbacks.


SUBAGENT C — Sidebar / responsive

Mission :
- inspecter AppShell et styles sidebar ;
- vérifier padding/gaps/footer ;
- proposer une sidebar plus aérée sans utiliser de dimensions rigides fragiles ;
- vérifier les petites tailles de fenêtre ;
- vérifier la position du footer.


SUBAGENT D — tests / regression review

Mission :
- identifier les tests visuels et fonctionnels concernés ;
- analyser les snapshots éventuels ;
- identifier les sélecteurs CSS/E2E qui vont casser ;
- proposer uniquement les adaptations nécessaires.


IMPORTANT :

Après chaque sous-agent :

1. Lis son rapport.
2. Vérifie ses affirmations directement dans le code.
3. Ne copie pas aveuglément sa proposition.
4. Refuse toute modification inutile.
5. Review le diff produit.
6. Corrige les problèmes toi-même si nécessaire.

À la fin :

lance un reviewer indépendant qui lit tout le diff final.

Le reviewer doit chercher :
- régression fonctionnelle ;
- problème responsive ;
- overflow ;
- mauvaise hauteur fixe ;
- duplication CSS ;
- problèmes clavier/focus ;
- markup inutile ;
- mauvais alignement ;
- changement métier accidentel.


/scope

Ce chantier doit rester frontend-only.

Fichiers probablement concernés :

frontend/src/app/AppShell.tsx
frontend/src/features/dashboard/DashboardPage.tsx
frontend/src/features/dashboard/ChampionPriorityCard.tsx
frontend/src/features/dashboard/BanPanel.tsx
frontend/src/features/dashboard/QuickActions.tsx
frontend/src/features/dashboard/AutomationBar.tsx
frontend/src/styles/globals.css

tests frontend associés.

Ne modifie d’autres fichiers que si une raison directe et démontrable existe.


/do-not-touch

NE PAS modifier :

- backend Python ;
- FastAPI ;
- endpoints ;
- LCU ;
- configuration persistée ;
- settings schema ;
- migrations ;
- routing ;
- routes Dashboard ;
- logique presets ;
- logique de champ select ;
- logique des providers Stats/Live ;
- hotkeys ;
- WebView ;
- installer ;
- CI/CD ;
- version de l’application.

Aucune migration.

Aucun changement API.

Aucun refactor backend.


/sidebar

Objectif :

La sidebar actuelle paraît trop tassée dans sa partie supérieure.

Je veux une navigation plus aérée.

État cible :

LOGO


Dashboard


Statistiques


En direct


Journal de logs


Réglages



[ espace flexible ]

Client connecté
Compte

Pas forcément autant d’espace que dans cet exemple ASCII, mais il faut clairement augmenter la respiration.


À faire :

1. Augmenter légèrement l’espace entre le logo et la navigation.

2. Augmenter le gap vertical entre les liens.

3. Si nécessaire, augmenter légèrement leur hauteur/padding vertical.

4. Conserver une largeur cohérente.

5. Conserver le footer en bas de sidebar.

6. Ne pas déplacer arbitrairement les items avec des `margin-top` individuels.

Préférer une structure claire :

sidebar
    header / brand
    nav
    spacer/flex
    footer

Si cette structure existe déjà, utiliser correctement flexbox au lieu d’empiler des margins.

La sidebar doit utiliser intelligemment la hauteur disponible.

Ne pas répartir les liens sur toute la hauteur de la sidebar non plus :
ils doivent rester regroupés, mais moins tassés.


/dashboard-layout

La zone principale actuelle est conceptuellement :

dashboard-grid

    dashboard-main
        Priority section

    dashboard-aside
        Ban
        Quick Actions

puis :

AutomationBar


Je veux améliorer l’équilibre vertical.


Objectif visuel :

┌────────────────────────────────────┬──────────────────┐
│                                    │ Ban automatique  │
│ Priorités de sélection             ├──────────────────┤
│                                    │ Accès rapides    │
│                                    │                  │
└────────────────────────────────────┴──────────────────┘


             ESPACE VERTICAL


┌───────────────────────────────────────────────────────┐
│ Automatisations                                       │
└───────────────────────────────────────────────────────┘


La somme :

BanPanel + gap + QuickActions

doit être visuellement proche de la hauteur de :

Priority section

sans utiliser de hauteur fixe ultra fragile.


/dashboard-grid-implementation

Inspecte le CSS existant avant modification.

Préférer :

display: grid
align-items: stretch

ou une combinaison Grid/Flex cohérente.

La colonne droite peut être :

display: flex;
flex-direction: column;

avec :

BanPanel
QuickActions

et QuickActions peut éventuellement utiliser :

flex: 1

si cela produit le meilleur équilibre.

Ne force pas artificiellement :

height: 412px

ou autres valeurs rigides sauf nécessité démontrée.

Le layout doit rester robuste si :
- le texte change légèrement ;
- un nom de rune est long ;
- la fenêtre est plus petite ;
- le scaling Windows change.


/preset-card-layout

C’est la modification UI principale.


Structure actuelle approximative :

Champion splash

Summoner 1 | Summoner 2 | Rune 1 | Rune 2 | Rune page name

Skin


Structure cible :

Champion splash

┌─────────────────────────────────┐
│ SUMMONERS                       │
│ [Flash] [Ignite]                │
├─────────────────────────────────┤
│ RUNES                           │
│ [Keystone] [Secondary] Nom page │
├─────────────────────────────────┤
│ SKIN                            │
│ [image] God-King Garen          │
└─────────────────────────────────┘


Ne mets pas obligatoirement le texte "SUMMONERS" / "RUNES" si cela surcharge l’interface.

La capture actuelle est déjà minimaliste.

L’objectif principal est la séparation verticale.


/summoner-row

Première ligne dédiée :

[spell 1] [spell 2]

Les icônes doivent conserver :
- mêmes assets ;
- mêmes tailles approximatives ;
- mêmes fallbacks ;
- mêmes tooltips/alt.

Cette ligne peut rester compacte.


/rune-row

Nouvelle ligne en dessous.

Contenu :

[rune principale] [style secondaire éventuel]
Nom de la page

Exemples :

[Conquérant] [Volonté]
Garen - Conquérant

ou :

[icône désactivée]
Conserver ma page actuelle


Le nom doit avoir plus de place qu’aujourd’hui.

Il ne doit plus être compressé sur la même ligne que les summoners.

Gérer les textes longs proprement :
- ellipsis si nécessaire ;
- title natif ou tooltip existant ;
- pas de débordement horizontal.


/skin-row

Conserver la ligne skin existante.

Elle reste sous les runes.

Éviter de changer son comportement si ce n’est pas nécessaire.


/card-height

Le nouveau layout doit naturellement faire gagner un peu de hauteur aux cards.

C’est souhaité.

Ne pas simplement ajouter :

min-height: +80px

pour tricher.

La hauteur supplémentaire doit principalement venir de :

summoner row
+
rune row
+
skin row

avec des gaps/paddings cohérents.


/cards-consistency

Les trois cards doivent rester exactement de même hauteur.

Même si :
- une page de rune est vide ;
- une autre a un long nom ;
- une card utilise un skin ;
- une autre aucun skin.

Utiliser une structure CSS stable.

Éviter que chaque card change de hauteur selon son contenu.


/spacing-before-automations

Le bloc Automatisations est actuellement trop proche de la grille supérieure.

Ajouter un véritable espace visuel.

Je veux une séparation claire entre :

Priority/Ban/Quick Actions

et :

Automatisations.


Ne mets pas seulement 4px supplémentaires.

Utiliser le système de spacing déjà présent dans le design.

Par exemple conceptuellement :

dashboard-grid
margin-bottom: var(--space-lg)

ou gérer via :

dashboard-page
gap: ...

Le choix exact doit suivre les tokens actuels.


/automation-section

Ne change pas le fonctionnement des toggles.

Ne change pas leur ordre.

Ne change pas :
- master preset switch ;
- Auto Accept ;
- Auto Pick ;
- Auto Ban ;
- Auto Summs ;
- Skin ;
- Auto Play Again.

Uniquement positionnement/spacing si nécessaire.


/visual-hierarchy

Conserver l’identité actuelle :

- dark UI ;
- bleu ;
- jaune/orange pour certaines sections ;
- cartes légèrement bordées ;
- faible rayon de bordure ;
- style compact desktop.

Je ne veux PAS une refonte graphique totale.

Pas de :
- glassmorphism excessif ;
- gros gradients ;
- animations inutiles ;
- énormes border-radius ;
- composants façon mobile ;
- gros effets glow.

Il s’agit d’un polish UI, pas d’une nouvelle DA.


/responsive

Tester les tailles supportées par l’application.

Au minimum :

800x540 ou minimum réel défini dans le projet

1100x760

1440x900

1920x1080

et approximativement :
- Windows scaling 100%
- 125%
- 150%

À petite largeur :

la grille peut repasser en une colonne si le comportement actuel le prévoit.

Dans ce cas :

Priority
Ban
Quick Actions
Automatisations

doivent avoir des gaps cohérents.

Ne jamais provoquer :
- horizontal scrollbar ;
- card coupée ;
- texte inaccessible ;
- sidebar écrasée.


/accessibility

Ne casse pas :

ChampionPriorityCard :
- `<a>`
- Enter
- focus visible
- aria-haspopup
- aria-expanded

BanPanel :
- navigation clavier
- aria

Sidebar :
- `aria-current`

Les modifications de markup doivent rester sémantiques.


/css-quality

Avant d’ajouter du CSS :

inspecte les règles existantes.

Réutilise :
- tokens spacing ;
- variables ;
- patterns flex/grid ;
- classes existantes.

Évite :
- !important ;
- duplication de règles ;
- valeurs magiques répétées ;
- CSS très spécifique inutile ;
- hacks dépendant exactement de cette résolution.


/tests

Adapter uniquement les tests nécessaires.

Vitest :
- ChampionPriorityCard
- AppShell/shell
- éventuels tests Dashboard affectés.

Playwright :
- dashboard-connected
- dashboard-disconnected
- presets/dashboard editor
- navigation
- ui-smoke
- window-layout

Ajouter si utile un test structurel pour vérifier :

- les summoners et runes sont dans deux containers distincts ;
- les cards restent cliquables ;
- la sidebar conserve les routes actuelles.


/visual-tests

Si le projet utilise des screenshots Playwright :

mettre à jour les snapshots UNIQUEMENT après avoir vérifié manuellement que le nouveau rendu est correct.

Ne jamais exécuter aveuglément :

--update-snapshots

puis considérer les tests comme valides.

Comparer l’ancien et le nouveau rendu.

Les screenshots doivent servir de contrôle visuel réel.


/implementation-order

Implémente dans cet ordre :

PHASE 1 — Audit
- lire codebase ;
- inspecter composants ;
- inspecter CSS ;
- inspecter tests ;
- écrire checklist plan_update.

PHASE 2 — Sidebar
- spacing logo/nav ;
- spacing items ;
- layout footer ;
- responsive.

PHASE 3 — Cards
- séparer summoner row ;
- créer rune row ;
- conserver skin row ;
- ajuster gaps/paddings ;
- assurer hauteur cohérente.

PHASE 4 — Dashboard grid
- aligner Priority avec Aside ;
- ajuster Ban/QuickActions ;
- stretch cohérent.

PHASE 5 — Automatisations
- ajouter respiration verticale ;
- vérifier équilibre général.

PHASE 6 — Responsive
- petites tailles ;
- largeur normale ;
- grande fenêtre.

PHASE 7 — Tests
- Vitest ;
- Playwright ;
- screenshots si nécessaires.

PHASE 8 — Review indépendante.


/plan-update

Avant de commencer, mettre à jour `plan_update.md` avec une checklist courte du chantier.

Exemple :

# Dashboard UI polish

## Audit
[ ] Inspecter Dashboard
[ ] Inspecter Sidebar
[ ] Inspecter cards
[ ] Inspecter responsive/tests

## Sidebar
[ ] Espacement navigation
[ ] Layout vertical
[ ] Footer

## Dashboard
[ ] Alignement grille haute
[ ] Card summoners/runes
[ ] Espacement Automatisations

## Validation
[ ] Vitest
[ ] Typecheck
[ ] Build
[ ] Playwright
[ ] Review visuelle

Archiver un ancien plan si nécessaire.

Ne colle pas ce prompt complet dans plan_update.md.


/review-after-each-step

Après chaque phase :

1. regarde `git diff`;
2. vérifie qu’aucun autre comportement n’est modifié ;
3. lance les tests ciblés ;
4. vérifie les sélecteurs CSS supprimés/modifiés ;
5. ne passe à la phase suivante que si la précédente est propre.


/independent-final-review

À la fin, lance un sous-agent reviewer n’ayant pas participé à l’implémentation.

Demande-lui de lire :

- tout le diff ;
- les composants finaux ;
- le CSS final ;
- les tests modifiés.

Il doit chercher spécifiquement :

- cards de hauteurs incohérentes ;
- layout fragile ;
- hacks CSS ;
- overflow ;
- mauvaise taille minimum ;
- duplication CSS ;
- sidebar trop espacée ou trop tassée ;
- automatisations encore trop proches ;
- rune names tronqués ;
- interactions cassées ;
- responsive cassé ;
- régression focus/accessibility.

Vérifie toi-même chaque finding.

Ne corrige pas les faux positifs.


/validation

Exécuter les commandes réelles définies dans le projet.

Au minimum frontend :

npm run test
npm run typecheck
npm run build
npm run api:check
npm run test:e2e

Si une commande diffère dans package.json, utiliser la commande réelle.

Exécuter aussi :

git diff --check

Aucun test backend complet n’est nécessaire si absolument aucun fichier backend n’a été touché, mais ne modifie pas le backend pour éviter cela.


/manual-review

Avant de déclarer terminé :

ouvre visuellement le Dashboard.

Vérifier :

SIDEBAR
- logo correctement positionné ;
- plus d’air avant navigation ;
- plus d’espace entre les entrées ;
- footer toujours en bas ;
- sidebar pas vide de manière absurde.

DASHBOARD
- Priority section équilibrée avec la colonne droite ;
- Ban auto correctement aligné ;
- Quick Actions correctement aligné ;
- pas de gros espace artificiel.

PRESET CARDS
- summoners première ligne ;
- runes deuxième ligne ;
- rune page lisible ;
- skin troisième ligne ;
- toutes les cards même hauteur ;
- clic fonctionne sur toute la card.

AUTOMATISATIONS
- espace net au-dessus ;
- aucune collision avec QuickActions ;
- toggles inchangés.

RESPONSIVE
- pas de scrollbar horizontale ;
- pas d’overflow.


/done-definition

Le chantier est terminé seulement si :

1. la sidebar est sensiblement plus aérée ;
2. la navigation ne paraît plus tassée en haut ;
3. le footer sidebar reste correctement positionné ;
4. les cards Preset conservent leurs interactions ;
5. summoners et runes sont sur deux lignes distinctes ;
6. le nom de rune est lisible ;
7. les trois cards ont une hauteur cohérente ;
8. Priority section et Aside sont mieux équilibrés ;
9. Automatisations possède davantage d’espace au-dessus ;
10. responsive inchangé ou amélioré ;
11. aucun backend/routing/API n’a été modifié ;
12. aucun hack CSS évident ;
13. tous les tests frontend passent ;
14. le reviewer indépendant n’a plus de finding concret non résolu.


/final-report

À la fin, donne un rapport factuel :

1. fichiers modifiés ;
2. changements Sidebar ;
3. changements Dashboard ;
4. changements cards ;
5. changements responsive ;
6. tests modifiés ;
7. résultats chiffrés des tests ;
8. résultat du reviewer indépendant ;
9. éventuels points restant à vérifier manuellement.

Confirme explicitement :

- backend inchangé ;
- API inchangée ;
- routing inchangé ;
- settings inchangés ;
- aucune migration ;
- aucun commit/push sauf demande explicite.