Tu reprends la CODEBASE OTP LOL ACTUELLE.

OBJECTIF DE CETTE PASSE

Faire évoluer OTP LOL pour que le League Client local devienne sa source
de données principale, ajouter de vraies statistiques natives de compte,
créer des diagnostics LCU utilisables après les patchs Riot, améliorer
l'onboarding/reset et clarifier définitivement la logique
Presets / Auto-Pick / Auto-Ban.

NE réécris PAS :
- React ;
- FastAPI ;
- pywebview ;
- la logique champion-select existante ;
- le packaging actuel.

Commence par relire toute la codebase actuelle et plan_update.md.

Utilise des sous-agents si disponibles, avec REVIEW systématique du main agent.

==================================================
WORKSTREAMS / SOUS-AGENTS
==================================================

A — LCU static data / assets
B — native account statistics
C — LCU diagnostics
D — settings/reset/presets UX
E — tests/security/review

Le main agent doit relire chaque diff.
Aucun sous-agent n'est considéré comme correct sans review + tests.

==================================================
PHASE 1 — CRÉER UNE VRAIE COUCHE LCU
==================================================

Aujourd'hui plusieurs responsabilités LCU sont encore dispersées dans
runtime.py / websocket.py / champ_select.py.

Créer une petite couche dédiée sans réécrire la logique existante.

Architecture cible :

src/lcu/
    client.py
    runtime.py                 # conserver/adapt existing
    static_data.py
    account_stats.py
    diagnostics.py
    models.py                  # si utile

`LcuClient` devient le wrapper commun pour les requêtes locales.

Il doit :
- réutiliser les credentials déjà détectés par OTP LOL ;
- appeler uniquement 127.0.0.1 / LCU ;
- gérer timeout ;
- gérer erreurs HTTP ;
- gérer déconnexion ;
- mesurer latence ;
- NE JAMAIS logger le password/token LCU.

Ne crée SURTOUT PAS :

/api/lcu/proxy?url=...

ou un proxy HTTP arbitraire depuis le frontend.

Toutes les routes frontend doivent appeler des opérations backend typées
et allowlistées.

==================================================
PHASE 2 — DONNÉES LEAGUE 100 % LOCALES
==================================================

Le League Client fournit localement :

/lol-game-data/assets/v1/champion-summary.json
/lol-game-data/assets/v1/items.json
/lol-game-data/assets/v1/perks.json
/lol-game-data/assets/v1/summoner-spells.json
/lol-game-data/assets/v1/maps.json
/lol-game-data/assets/v1/queues.json

Créer :

LcuStaticDataService

avec :

load_champions()
load_items()
load_perks()
load_summoner_spells()
load_maps()
load_queues()

Récupérer également :

GET /lol-patch/v1/game-version

pour connaître exactement la version installée chez l'utilisateur.

==================================================
STRATÉGIE DE SOURCE
==================================================

Nouvelle priorité :

1. LCU local si client League disponible
2. dernier cache LCU persisted par OTP LOL
3. Data Dragon uniquement comme fallback de secours

Data Dragon ne doit plus être la source de vérité normale.

IMPORTANT :

League peut être fermé lorsque OTP LOL démarre.

Donc ne fais PAS :

LCU fermé
→ plus aucun champion / aucune image

Persist localement le dernier snapshot valide.

Exemple :

AppData/OTP LOL/cache/lcu/
    <game-version>/
        champions.json
        spells.json
        perks.json
        items.json
        maps.json
        queues.json

Conserver seulement un nombre raisonnable de versions.

Lorsqu'un nouveau :

/lol-patch/v1/game-version

est détecté :
- charger les données LCU correspondant au client installé ;
- créer le nouveau cache ;
- invalider les anciennes données mémoire ;
- conserver temporairement le précédent cache comme fallback.

==================================================
PHASE 3 — MIGRER CHAMPIONS / SPELLS / RUNES
==================================================

Remplacer progressivement Data Dragon pour :

- ID champion ;
- nom champion ;
- métadonnées champion ;
- summoner spells ;
- perks/runes ;
- maps ;
- queues ;
- items.

NE fais pas une migration Big Bang.

Ordre :

1. champions
2. summoner spells
3. perks/runes
4. maps/queues
5. items

Après chaque migration :
- tests ;
- vérifier Dashboard ;
- vérifier Presets ;
- vérifier ChampionPicker ;
- vérifier RunePicker.

==================================================
PHASE 4 — ASSETS LOCAUX
==================================================

Auditer les chemins d'assets retournés par les documents LCU.

Utiliser le mécanisme local de plugin asset serving du client lorsque possible.

Créer un service backend typé :

LcuAssetService

qui accepte :
- champion ID ;
- spell ID ;
- perk ID ;
- skin ID ;

PAS un chemin arbitraire fourni par React.

Le frontend continue d'utiliser des URLs OTP LOL comme :

/api/assets/champions/86
/api/assets/spells/4
/api/assets/perks/8010
...

mais le backend résout d'abord l'asset depuis LCU/cache local.

Ne permets pas :

/api/assets/lcu?path=<arbitrary>

pour éviter path traversal et exposition de ressources internes.

Conserver Data Dragon / CommunityDragon uniquement comme fallback
si un asset précis n'existe réellement pas côté LCU/cache.

==================================================
PHASE 5 — STATUT DES SOURCES DE DONNÉES
==================================================

Ajouter :

GET /api/game-data/status

Réponse possible :

{
    "source": "lcu",
    "game_version": "...",
    "connected": true,
    "cache_available": true,
    "cache_version": "...",
    "fallback": null,
    "catalogs": {
        "champions": true,
        "spells": true,
        "perks": true,
        "items": true,
        "maps": true,
        "queues": true
    }
}

Si LCU fermé :

source = "cache"

Si ni LCU ni cache :

source = "datadragon"

Cela sera très utile pour Diagnostics.

==================================================
PHASE 6 — STATS NATIVES DU COMPTE
==================================================

Le LCU actuel expose notamment :

RANKED
/lol-ranked/v1/...

MASTERIES
/lol-champion-mastery/v1/local-player/champion-mastery
/lol-champion-mastery/v1/local-player/champion-mastery-score

CHALLENGES
/lol-challenges/v1/challenges/local-player
/lol-challenges/v1/challenges/category-data

MATCH HISTORY
/lol-match-history/v1/products/lol/current-summoner/matches
/lol-match-history/v1/games/{gameId}
/lol-match-history/v1/game-timelines/{gameId}

Créer :

src/lcu/account_stats.py

et des DTO Pydantic propres.

Ne renvoie PAS les gros objets Riot bruts au frontend.

Normaliser ce dont OTP LOL a besoin.

==================================================
API ACCOUNT
==================================================

Créer par exemple :

GET /api/account/summary
GET /api/account/ranked
GET /api/account/masteries
GET /api/account/challenges
GET /api/account/matches?limit=20
GET /api/account/matches/{game_id}

`summary` doit rester léger.

Les détails match/timeline sont lazy.

Ne charge PAS vingt timelines à l'ouverture de la page.

==================================================
PHASE 7 — NOUVELLE PAGE STATISTIQUES NATIVE
==================================================

La page actuelle "Statistiques" est principalement un wrapper autour
d'OP.GG/DeepLOL/etc.

La faire évoluer en :

STATISTIQUES

[ Vue OTP LOL ] [ Site externe ]

Vue OTP LOL = onglet par défaut.

Exemple :

┌ COMPTE ───────────────────────────────┐
│ MaitreKacaf#6767                     │
│ Niveau ...                            │
└───────────────────────────────────────┘

┌ CLASSÉ ───────────────────────────────┐
│ Solo/Duo          Emerald II · 43 LP │
│ 56 W / 49 L       53.3 %             │
│                                     │
│ Flex              Platinum I ...    │
└───────────────────────────────────────┘

┌ MAÎTRISES ────────────────────────────┐
│ [Garen]  681 423 pts                 │
│ [Darius] 211 833 pts                 │
│ ...                                  │
└───────────────────────────────────────┘

HISTORIQUE

W  [Garen]  8 / 2 / 7  31:22
L  [Lux]    4 / 6 / 3  27:41
...

Chaque match peut être cliqué pour afficher :
- champion ;
- KDA ;
- CS ;
- durée ;
- queue ;
- date ;
- items ;
- participants utiles ;
- résultat.

Les images doivent réutiliser la nouvelle source locale LCU.

==================================================
CHALLENGES
==================================================

Ne surcharge pas l'écran.

Afficher uniquement un résumé dans Stats :

- progression globale pertinente ;
- quelques challenges principaux.

Créer un Dialog/Drawer "Voir tous les challenges".

Chargement lazy.

==================================================
SITES EXTERNES
==================================================

NE supprime pas :
- OP.GG ;
- DeepLOL ;
- DPM ;
- League of Graphs.

Ils deviennent complémentaires.

Conserver :

[ Vue OTP LOL ] [ Site externe ]

ou un bouton :

"Ouvrir les statistiques avancées sur DeepLOL"

La page "En direct" actuelle reste distincte.

==================================================
PHASE 8 — CACHE DES STATS
==================================================

Lorsque League est fermé :

les endpoints LCU ne sont plus accessibles.

Option recommandée :

conserver le dernier snapshot account NON SENSIBLE dans :

AppData/OTP LOL/cache/account/

avec :
- timestamp ;
- Riot ID / PUUID nécessaire ;
- ranked ;
- mastery summary ;
- derniers matchs.

Dans l'UI :

"Dernière synchronisation : il y a 2 h"

NE fais jamais croire que ces valeurs sont live.

Ne persiste pas :
- credentials LCU ;
- tokens ;
- headers auth.

==================================================
PHASE 9 — DIAGNOSTICS LCU
==================================================

Ajouter une vraie feature Diagnostics.

Je préfère :

Réglages
→ Avancé
→ "Diagnostics LCU"
→ bouton "Ouvrir les diagnostics"

route :

#diagnostics

plutôt qu'une nouvelle entrée permanente dans la sidebar destinée à tous
les utilisateurs.

==================================================
UI DIAGNOSTICS
==================================================

Créer :

frontend/src/features/diagnostics/DiagnosticsPage.tsx

Layout :

DIAGNOSTICS LCU

Connexion
● Client connecté
Version League : ...
Phase : Lobby
Source data : LCU local
Latence : 8 ms

ENDPOINTS

✓ gameflow phase       200    4 ms
✓ current summoner     200    6 ms
✓ champions            200   11 ms
✓ ranked               200    9 ms
! match history         503   31 ms

ÉVÉNEMENTS

20:14:03  gameflow     Lobby -> Matchmaking
20:14:31  ready-check  Create
...

ERREURS

20:15:06  GET /... → 404
...

[ Lancer le diagnostic ]
[ Exporter le rapport ]
[ Copier ]

==================================================
DIAGNOSTICS BACKEND
==================================================

Créer :

src/lcu/diagnostics.py

Maintenir des buffers circulaires bornés :

requests : ~200
events   : ~500
errors   : ~100

Chaque request log diagnostique :

{
    timestamp,
    method,
    path,
    status,
    duration_ms,
    success
}

NE JAMAIS stocker :
- Authorization ;
- password LCU ;
- token ;
- cookie sensible.

==================================================
DIAGNOSTIC RUN
==================================================

Ajouter :

POST /api/diagnostics/run

Il exécute uniquement une liste de GET allowlistés.

Exemple :
- gameflow phase ;
- current summoner ;
- patch/game version ;
- static champions ;
- ranked ;
- mastery ;
- match history.

AUCUN PUT/PATCH/POST/DELETE LCU dans un diagnostic.

Retour :

status + durée + erreur normalisée.

==================================================
ENDPOINT EXPLORER
==================================================

Je veux pouvoir diagnostiquer les changements après un patch Riot.

Ajouter un explorateur en mode avancé.

Mais NE PAS créer un proxy LCU arbitraire exposé depuis React.

Mode normal :
- liste les endpoints OTP LOL connus ;
- montre disponibles / cassés ;
- test GET sécurisé.

Mode développeur optionnel :
- éventuellement autoriser un GET manuel vers `/lol-*`
- uniquement loopback LCU ;
- aucun body ;
- aucun header utilisateur ;
- aucun autre host ;
- absolument aucun method write.

Avant d'implémenter le mode GET manuel, review sécurité obligatoire.

==================================================
EVENT EXPLORER
==================================================

OTP LOL possède déjà une connexion événementielle LCU.

NE crée pas une deuxième connexion WebSocket si elle n'est pas nécessaire.

Brancher Diagnostics sur le flux existant.

Afficher :
- topic/URI ;
- event type ;
- timestamp ;
- résumé du payload.

Payload brut :
uniquement dans un drawer "Voir JSON".

Limiter taille et nombre d'événements.

Les primitives LCU Help/Subscribe/Unsubscribe peuvent servir au diagnostic,
mais ne rends pas un shell arbitraire accessible dans la release normale.

==================================================
LOGS
==================================================

Ne lis pas tout un fichier log à chaque refresh.

Créer un buffer applicatif dédié ou lire uniquement les dernières lignes.

Filtres :

Tous
LCU
Automation
Data
WebView
Erreur

Ajouter recherche texte.

==================================================
EXPORT DIAGNOSTIC
==================================================

Créer un rapport JSON/TXT contenant :

- version OTP LOL ;
- version League ;
- version WebView2 si disponible ;
- source game-data ;
- état LCU ;
- résultats endpoint checks ;
- dernières erreurs ;
- derniers events utiles.

REDACT :
- Riot ID par défaut ;
- PUUID ;
- tokens ;
- credentials ;
- paths utilisateur si non nécessaires.

Ajouter une checkbox explicite si l'utilisateur veut inclure son Riot ID.

==================================================
PHASE 10 — RESET / FIRST-LAUNCH ONBOARDING
==================================================

Bug utilisateur :
après "Réinitialiser les réglages", l'interface devient trop vide et
ne permet pas de comprendre immédiatement le fonctionnement d'OTP LOL.

Reproduire d'abord le bug.

Tester :

Settings
→ Reset
→ réponse backend
→ settings cache
→ presets cache
→ bootstrap
→ Dashboard
→ Presets.

Vérifier si la cause est :
A. mauvais defaults backend ;
B. React Query non invalidé ;
C. runtime non resynchronisé ;
D. combinaison de plusieurs causes.

Ne corrige pas uniquement visuellement.

==================================================
SÉPARER DEFAULTS ET STARTER CONFIG
==================================================

Créer explicitement :

FACTORY_DEFAULT_SETTINGS

et :

STARTER_PRESET_CONFIG

Le starter config ne doit faire aucune hypothèse sur :
- skins possédés ;
- rune page IDs ;
- compte Riot.

Exemple recommandé :

PRIORITÉ 1
Garen
Flash + Ignite
Skin : Aucun
Rune : aucune forcée

PRIORITÉ 2
Lux
Flash + Barrier
Skin : Aucun

PRIORITÉ 3
Ashe
Flash + Heal
Skin : Aucun

Ban :
aucun par défaut.

IMPORTANT :

toutes les automatisations doivent être OFF après factory reset.

L'utilisateur doit comprendre le produit sans que OTP LOL effectue
une action automatique surprise.

==================================================
FIRST LAUNCH UX
==================================================

Au premier lancement / reset :

afficher un petit banner :

"Des exemples sont prêts.
Personnalise les trois priorités avant d'activer les automatisations."

[ Modifier mes presets ]

Les trois cards montrent les exemples.

Chaque exemple est une vraie configuration éditable, pas un mock frontend.

Après première modification ou fermeture du banner :
ne pas le montrer constamment.

Ajouter éventuellement :

onboarding_completed

dans les settings.

==================================================
RESET UX
==================================================

Le bouton actuel "Réinitialiser les réglages" doit réellement :

1. restaurer factory settings ;
2. restaurer starter presets ;
3. persister ;
4. publier settings_updated ;
5. resynchroniser runtime ;
6. retourner l'état final.

Frontend doit ensuite invalider au minimum :

["settings"]
["presets"]
["bootstrap"]
["stats-link"]
["live-stats-link"]

et les nouvelles queries account/game-data concernées.

Appliquer immédiatement le thème retourné.

Ajouter test E2E :

config personnalisée
→ Reset
→ Garen/Lux/Ashe visibles
→ automatisations OFF
→ reload de l'application
→ même état toujours présent.

==================================================
OPTION SÉPARÉE
==================================================

Ajouter dans Advanced :

"Effacer uniquement les presets"

pour l'utilisateur qui veut réellement repartir avec trois slots vides.

Cela évite de détourner Factory Reset en une fonction ambiguë.

==================================================
PHASE 11 — CORRIGER LA LOGIQUE PRESETS / AUTOPICK / AUTOBAN
==================================================

Le modèle actuel possède :

presets_enabled
auto_pick_enabled
auto_ban_enabled
auto_summoners_enabled
skin_automation_enabled
rune_auto_apply par slot

Ce n'est PAS nécessairement une erreur.

Le problème est leur présentation et leur relation.

Définir officiellement :

presets_enabled
=
MASTER GATE des automatisations pilotées par les presets.

Il ne signifie PAS :
"les données Presets existent".

On peut toujours éditer les presets lorsque OFF.

==================================================
ENFANTS DU MASTER
==================================================

Les actions suivantes dépendent du master :

Auto-Pick
Auto-Ban
Auto-Summs
Auto-Runes
Auto-Skin

Les actions suivantes restent indépendantes :

Auto-Accept
Auto Play Again

État effectif :

effective_auto_pick =
presets_enabled AND auto_pick_enabled

effective_auto_ban =
presets_enabled AND auto_ban_enabled

effective_auto_summoners =
presets_enabled AND auto_summoners_enabled

effective_skin =
presets_enabled AND skin_automation_enabled

effective_rune_for_slot =
presets_enabled
AND auto_summoners/rune prerequisite appropriée
AND slot.rune_auto_apply

Vérifie la logique métier existante avant de figer la condition exacte des runes.

==================================================
NE PAS ÉCRASER LES CHOIX ENFANTS
==================================================

Si :

Auto-Pick ON
Auto-Ban OFF
Auto-Summs ON

puis master OFF :

les trois valeurs enfants doivent rester :

ON / OFF / ON.

Lorsqu'on remet master ON :
elles redeviennent effectives automatiquement.

INTERDIT :

master OFF
→ mettre auto_pick_enabled=false
→ mettre auto_ban_enabled=false
→ perdre les préférences.

==================================================
UX DASHBOARD
==================================================

Renommer le master.

Éviter :

"Presets actifs"

si cela fait croire qu'on ne peut plus éditer les cards.

Utiliser plutôt :

"AUTOMATISATIONS DES PRESETS"

ou :

"Utiliser les presets en sélection"

[ ON / OFF ]

Sous OFF :

"Tes presets restent configurés mais aucune action automatique liée aux
presets n'est exécutée."

Dans AutomationBar :

Auto-Accept reste cliquable normalement.

Auto-Pick
Auto-Ban
Auto-Summs
Runes
Skin

restent visibles mais :
- apparaissent disabled/dimmed quand master OFF ;
- conservent visuellement leur préférence ;
- tooltip : "Active d'abord les automatisations des presets."

Auto Play Again reste indépendant.

==================================================
UX PAGE PRESETS
==================================================

Le même master switch apparaît en haut de Presets.

IMPORTANT :
Dashboard et Presets doivent modifier LA MÊME donnée.

Pas deux états locaux.

Créer si utile un hook partagé :

usePresetAutomationMaster()

ou simplement réutiliser la même mutation/query.

Un changement Dashboard doit être reflété immédiatement dans Presets,
et inversement.

==================================================
API / RUNTIME
==================================================

Ajouter éventuellement dans RuntimeSnapshot des valeurs dérivées :

presets_enabled
effective_auto_pick
effective_auto_ban
effective_auto_summoners
effective_skin_automation

pour que React n'ait pas à reproduire toute la logique métier.

La logique backend reste la source de vérité.

==================================================
TRAY
==================================================

Le menu tray "Presets" doit uniquement toggle :

presets_enabled

Il ne doit PAS modifier :
auto_pick_enabled
auto_ban_enabled
auto_summoners_enabled.

==================================================
TESTS MASTER
==================================================

Ajouter :

children ON/OFF configuration
→ master OFF
→ aucun auto pick/ban/summs/skin effectué

→ valeurs enfants persistées inchangées

→ master ON
→ anciennes préférences redeviennent actives

Auto-Accept :
→ fonctionne indépendamment du master.

Auto Play Again :
→ fonctionne indépendamment du master.

==================================================
PHASE 12 — TESTS GAME DATA LOCAL
==================================================

Ajouter un fake LCU compatible avec :

/lol-patch/v1/game-version
/lol-game-data/assets/v1/champion-summary.json
/lol-game-data/assets/v1/summoner-spells.json
/lol-game-data/assets/v1/perks.json
/lol-game-data/assets/v1/items.json
/lol-game-data/assets/v1/maps.json
/lol-game-data/assets/v1/queues.json

Tests :

LCU connected
→ LCU source chosen

LCU disconnected + local cache
→ cache source

LCU disconnected + no cache
→ fallback Data Dragon

new game version
→ cache regenerated

malformed LCU response
→ no crash
→ fallback

==================================================
PHASE 13 — TESTS STATS
==================================================

Fake endpoints :

Ranked
Mastery
Challenges
Match history

Tester :
- normalize DTO ;
- empty account ;
- partial endpoint failure ;
- League disconnected ;
- last-known cached data ;
- lazy match detail ;
- no credential exposure.

Une erreur Challenges ne doit pas faire échouer Ranked/History.

Les blocs doivent être indépendants.

==================================================
PHASE 14 — TESTS DIAGNOSTICS
==================================================

Tester :

- credentials never returned ;
- token never logged ;
- only safe GET checks ;
- ring buffers bounded ;
- export redacted ;
- event payload truncation ;
- endpoint error correctly reported ;
- League patch/version displayed ;
- diagnostic page works without LCU.

==================================================
PHASE 15 — PERFORMANCE
==================================================

Ne fais pas régresser le démarrage.

Critical path actuel doit rester léger.

NE charge PAS au startup :
- items complets ;
- challenges ;
- match history ;
- masteries.

Chargement :

Dashboard
→ uniquement bootstrap local nécessaire.

Statistics native page
→ account summary/ranked/matches.

Preset editors
→ catalogs nécessaires.

Diagnostics
→ uniquement quand ouvert.

Le refresh du cache LCU peut se faire après connexion client,
en arrière-plan.

==================================================
PHASE 16 — DOCUMENTATION
==================================================

Mettre à jour :

docs/architecture.md
docs/security.md
docs/V2_PARITY.md
docs/performance.md
docs/SETTINGS_TEST_MATRIX.md
README

Architecture finale à documenter :

LCU local
   ↓
LcuClient
   ├── StaticDataService
   ├── AccountStatsService
   ├── DiagnosticsService
   └── existing automation runtime
        ↓
FastAPI typed endpoints
        ↓
React

Data Dragon :
fallback de secours uniquement.

==================================================
VALIDATION FINALE
==================================================

Exécuter :

python -m unittest discover -s tests -p "test_*.py"
python -m compileall -q launcher_web.py src tests create_exe.py

Frontend :

npm run api:generate
npm run api:check
npm run typecheck
npm run test
npm run build
npm run test:e2e

Puis test réel avec League Client.

Vérifier :

[ ] game version détectée localement
[ ] champions depuis LCU
[ ] spells depuis LCU
[ ] perks depuis LCU
[ ] maps/queues/items depuis LCU
[ ] app fonctionne League fermé grâce au cache
[ ] Ranked natif fonctionne
[ ] Masteries fonctionnent
[ ] Challenges fonctionnent
[ ] Match history fonctionne
[ ] Diagnostics affiche endpoints/events/errors
[ ] aucun secret LCU visible
[ ] Reset restaure starter presets
[ ] Reset visible immédiatement
[ ] Reset persiste après restart
[ ] master Presets cohérent Dashboard/Presets
[ ] master OFF ne détruit pas les child settings
[ ] Auto-Accept reste indépendant
[ ] Play Again reste indépendant
[ ] aucun ralentissement notable au démarrage

Ne termine pas uniquement parce que les tests mock sont verts.

Effectuer également un test réel contre le League Client installé.

Rapport final :
- endpoints LCU réellement utilisés ;
- source de chaque type de donnée ;
- game version détectée ;
- fallback réellement testé ;
- stats natives validées ;
- diagnostics validés ;
- comportement reset ;
- comportement master presets ;
- résultats exacts des tests.