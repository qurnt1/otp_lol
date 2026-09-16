Tu reprends le projet OTP LOL dans son ÉTAT ACTUEL.

IMPORTANT :
- lis la codebase actuelle avant de modifier quoi que ce soit ;
- lis intégralement `plan_update.md` ;
- considère `plan_update.md` comme un contrat d'implémentation ;
- compare CHAQUE exigence du plan au code actuel et aux tests actuels ;
- ne te fie pas à un ancien compte-rendu ou à une conversation précédente.

L'objectif de cette passe est :
1. corriger les bugs réels encore présents ;
2. terminer à 100 % `plan_update.md` ;
3. ajouter proprement la nouvelle page Statistiques ;
4. ne pas casser la logique métier LCU existante.

==================================================
MODE DE TRAVAIL OBLIGATOIRE : SOUS-AGENTS + REVIEW
==================================================

Utilise des sous-agents lorsque l'environnement le permet.

Découpe au minimum le travail en workstreams indépendants :

SOUS-AGENT A — Data Dragon / offline / cache
Responsable principalement de :
- src/core/datadragon.py
- routes/assets concernées
- tests Data Dragon/API.

SOUS-AGENT B — Presets / images / sorts
Responsable principalement de :
- PresetEditorDialog
- PresetCard
- SkinPicker
- Select si nécessaire
- tests Presets.

SOUS-AGENT C — Navigation / Statistiques / Topbar / hotkey
Responsable principalement de :
- AppShell
- routes/useHashRoute
- RuntimeTopBar
- QuickActions
- nouvelle StatisticsPage
- desktop window/hotkey
- CSP.

SOUS-AGENT D — Vérification du plan et tests
Responsable de :
- comparer les 20 sections de plan_update.md au résultat final ;
- identifier toute exigence encore incomplète ;
- renforcer Vitest/Playwright/Python ;
- vérifier parité V2.

RÈGLE CRITIQUE :
ne considère JAMAIS le résultat d'un sous-agent comme validé automatiquement.

Après chaque sous-agent :
1. lis son diff ;
2. vérifie que sa solution respecte l'architecture actuelle ;
3. recherche les régressions ;
4. exécute ses tests ciblés ;
5. corrige toi-même les erreurs avant intégration.

Le main agent reste responsable du résultat global.

Les sous-agents ne doivent pas effectuer simultanément des modifications contradictoires sur les mêmes fichiers.

==================================================
CHECKLIST PLAN_UPDATE OBLIGATOIRE
==================================================

Avant le développement, transforme les 20 sections de `plan_update.md` en checklist.

Pour chacune :

[ ] implémentée
[ ] testée
[ ] validée visuellement si UI

Ne t'arrête pas tant que toutes les exigences encore pertinentes du plan sont à 100 %.

ATTENTION :
la nouvelle exigence Statistiques ci-dessous REMPLACE le comportement historique de la section 1 concernant l'ouverture directe du site par le hotkey.

Le principe reste :
le raccourci doit fonctionner même sans League.

Mais désormais :

HOTKEY STATS
→ ouvre OTP LOL
→ ouvre l'onglet Statistiques

et NON plus :
→ ouvre directement le navigateur système.

Toutes les autres exigences de plan_update.md restent à vérifier et à terminer.

==================================================
P0 — CORRIGER DATADRAGON HORS LIGNE
==================================================

Bug observé :

DataDragon charge correctement :

DataDragon: Loaded local cache (version 16.18.1)

puis lorsque le DNS / Internet est indisponible :

Unable to fetch online version
Champion detail download error ... Garen.json
Champion detail download error ... Garen.json
Champion detail download error ... Lux.json
etc.

Le problème n'est PAS qu'une vérification réseau échoue.

Le problème est que plusieurs composants/endpoints refont des requêtes distantes inutiles alors qu'un cache local exploitable existe.

Audite précisément tous les chemins réseau de DataDragon.

CORRECTIONS OBLIGATOIRES :

1. `get_champion_splash()`

Il ne doit PAS télécharger `champion/{champion}.json` simplement pour connaître le slug.

Utiliser d'abord :

self.by_id[champion_id]["id"]

qui est déjà présent dans le catalogue champion en cache.

Uniquement si le slug est réellement absent, envisager un fallback.

Une simple demande d'image ne doit pas déclencher le téléchargement du détail complet du champion.

2. Endpoint skin splash

Actuellement `/api/assets/skins/{champion_id}/{skin_id}/splash`
appelle d'abord `get_skin_catalog()`.

Cela peut déclencher :
- champion detail Data Dragon ;
- CommunityDragon detail ;
- puis seulement l'image.

Refactoriser.

Principe :

UN ENDPOINT D'IMAGE NE DOIT PAS DÉCLENCHER UN CATALOGUE DISTANT COMPLET.

Si les métadonnées skin sont déjà en cache :
- centered splash
- uncentered splash
- DataDragon splash
- tile fallback

Sinon et si `skin_num` est connu :
- utiliser immédiatement `get_skin_preview(champion_id, skin_num)`.

Ne télécharger le catalogue complet que lorsque l'utilisateur ouvre réellement le Skin Picker.

3. Ajouter un backoff réseau.

Lorsqu'une erreur réseau de type :
- DNS ;
- ConnectionError ;
- Timeout ;

est détectée, définir un cooldown global Data Dragon.

Exemple :
30 à 60 secondes.

Pendant ce cooldown :
- ne pas refaire immédiatement `versions.json` ;
- ne pas spammer les champion detail ;
- servir cache/fallback local.

4. Negative cache.

Mémoriser temporairement l'échec d'une récupération de champion detail.

Exemple :
champion 86 inaccessible à T0
→ ne pas retenter son détail pendant 30–60 s.

5. Dédupliquer les téléchargements concurrents.

Si deux requêtes demandent Garen au même moment :
→ un seul fetch distant doit être réalisé.

6. Stale-while-revalidate.

Si une image locale existe mais que son marqueur de version n'est plus considéré frais :
- utiliser quand même l'image locale immédiatement ;
- tenter éventuellement sa mise à jour en arrière-plan.

Ne pas transformer un cache légèrement ancien en écran sans image simplement parce qu'Internet est coupé.

7. Cache catalogues skin/detail.

Quand un catalogue/détail a déjà été récupéré avec succès, envisager sa persistence locale par version/champion afin que le Skin Picker reste exploitable hors connexion lors d'un lancement ultérieur.

8. Logs.

Une panne Internet ne doit pas générer 20 warnings identiques.

Premier échec :
WARNING lisible.

Échecs identiques pendant le cooldown :
DEBUG ou silencieux.

TESTS :
- cache valide + DNS indisponible ;
- splash champion sans appel champion detail ;
- splash skin avec skin_num sans appel catalogue ;
- deux appels concurrents même champion → un seul fetch ;
- negative cache ;
- expiration du cooldown ;
- stale image locale utilisée hors ligne.

==================================================
P0 — IMAGE DU SKIN FIXE DANS L'ÉDITEUR PRESET
==================================================

Bug actuel :

dans le Dialog d'édition du preset :

SKIN
Aucun | Fixe | Aléatoire

puis le bouton en dessous affiche actuellement seulement :
- Sparkles/Dices ;
- texte God-King Garen.

Lorsque `skin_mode === "fixed"` et qu'un skin est sélectionné, je veux voir sa vraie image.

Exemple :

[IMAGE GOD-KING GAREN]  God-King Garen      >

Pour RANDOM :
[IMAGE DU RANDOM PREVIEW] Pool aléatoire     >

Pour NONE :
fallback visuel propre.

NE recharge pas le catalogue simplement pour cette image.

Passe au `PresetEditorDialog` le `PresetPreview` correspondant déjà présent dans `/api/bootstrap`.

Utiliser :
preview.skin_preview_url

fallback :
champion image / icône appropriée.

Après changement de skin :
- invalider/rafraîchir bootstrap correctement ;
- la miniature doit changer immédiatement ou dès la réponse serveur.

Ajouter test E2E.

==================================================
P0 — SORTS AVEC IMAGES DANS L'ÉDITEUR
==================================================

Bug actuel :

les deux sélecteurs de sorts affichent uniquement :

Flash
Ignite

Je veux :

[icône Flash] Flash
[icône Ignite] Ignite

dans :
- le contrôle actuellement sélectionné ;
- chaque item du dropdown.

Ne reviens PAS à un `<select>` natif.

Conserver Radix.

Étendre le composant générique `Select` proprement, par exemple avec :
- `iconUrl?`
ou
- un mécanisme générique `renderOption/renderValue`.

Évite de rendre le composant UI dépendant directement du domaine League si possible.

Pour `(None)` :
fallback/icône neutre.

Navigation clavier, focus, Escape et Enter doivent rester corrects.

Ajouter tests.

==================================================
P0 — DASHBOARD : SPLASH DU SKIN SÉLECTIONNÉ
==================================================

Bug confirmé :

la page Presets utilise bien le skin sélectionné en grande image.

Le Dashboard utilise encore :

champion_splash_url

comme image principale.

Corriger `ChampionPriorityCard`.

Ordre attendu :

preview.skin_preview_url
→ preview.champion_splash_url
→ champion.splash_url
→ fallback

Le bootstrap connaît déjà le skin sélectionné.

NE charge aucun catalogue supplémentaire.

Cas :
FIXED → splash du skin fixe.
RANDOM → splash du random preview.
NONE / pas de skin → splash du champion de base.

Ajouter un E2E Dashboard vérifiant précisément le `src` du splash.

==================================================
P1 — DEEP LINKS SETTINGS
==================================================

Actuellement QuickActions contient :

Raccourcis clavier → #settings

Je veux :

Raccourcis clavier → #settings/shortcuts

Et :

Choisir/modifier le site de statistiques → #settings/links

Refactoriser le hash router pour supporter des sous-routes propres.

Exemples :

#dashboard
#presets
#statistics
#history
#settings/general
#settings/automations
#settings/account
#settings/links
#settings/shortcuts
#settings/appearance
#settings/advanced

Ne duplique pas un deuxième router.

Créer un parser de route correctement typé.

`SettingsPage` doit ouvrir directement la section demandée.

Back/forward navigateur doit rester cohérent.

==================================================
P1 — RUNTIME TOP BAR
==================================================

Refaire uniquement son layout, pas toute l'UI.

Problème :

la largeur de la phase varie et comprime/décale les informations vers la droite.

Je veux approximativement :

[Compte........................] [Région] [Phase.............................] [● Client connecté] [⚙]

Le statut de connexion doit être TOUT À DROITE, juste avant Settings.

Le bloc Phase doit disposer d'un espace flexible important.

Proposition :

runtime-topbar
  left/facts → flex:1 / grid
  right-actions → auto

runtime-facts :
  account : minmax(...)
  region  : compact
  phase   : minmax(200px, 1fr)

Utiliser :
min-width: 0
overflow
text-overflow: ellipsis
white-space: nowrap

si nécessaire.

Mais les textes doivent utiliser l'espace disponible avant d'être tronqués.

Tester notamment :
- "Dans le lobby"
- "Sélection des champions"
- "Récupération des statistiques"
- client non détecté
- Riot ID long.

Tester 800×540, 1100×760, 1440×900 et 1920×1080.

==================================================
P1 — SELECT NATIF RESTANT SUR LE DASHBOARD
==================================================

Settings utilise maintenant Radix correctement.

Mais le contrôle INHERIT / OFF / FIXED / RANDOM de ChampionPriorityCard utilise encore un `<select>` HTML.

Le remplacer lui aussi par le composant `Select` moderne.

Pas de popup Windows rectangulaire.

==================================================
NOUVELLE FEATURE — ONGLET STATISTIQUES
==================================================

Ajouter dans la sidebar, JUSTE SOUS Presets :

Dashboard
Presets
Statistiques
Historique
Réglages

Utiliser une icône cohérente de type :
ChartNoAxesCombined / BarChart3.

Ajouter :

frontend/src/features/statistics/StatisticsPage.tsx

et intégrer la nouvelle route au lazy loading actuel.

==================================================
STATISTICS PAGE — UX
==================================================

Objectif :

ne plus ouvrir le site de statistiques dans le navigateur système par défaut.

Afficher le site préféré directement dans OTP LOL.

Layout :

STATISTIQUES

[OP.GG] [Player#EUW] [EUW]

[Modifier le site préféré] [Rafraîchir] [Ouvrir dans le navigateur]

┌──────────────────────────────────────────────┐
│                                              │
│      CONTENU DU SITE DE STATISTIQUES         │
│                                              │
└──────────────────────────────────────────────┘

"Modifier le site préféré"
→ #settings/links

La source de vérité doit être :
preferred_stats_site

et `/api/links/stats`.

Ne construis pas l'URL manuellement dans plusieurs composants.

Lorsque Riot ID/région/site changent :
→ la page doit rafraîchir son URL.

Lorsque League n'est pas connecté mais qu'un compte manuel est configuré :
→ utiliser le compte manuel.

Lorsque ni compte auto ni compte manuel exploitable n'existe :
→ afficher un empty state clair ;
→ proposer d'aller dans Réglages > Compte ;
→ éventuellement afficher la homepage du fournisseur si cela est cohérent.

==================================================
IMPORTANT — IFRAME / WEBVIEW / SÉCURITÉ
==================================================

Avant de considérer l'intégration terminée, vérifie réellement si les fournisseurs supportés autorisent l'affichage dans une iframe WebView2.

Les fournisseurs peuvent utiliser :
- X-Frame-Options ;
- CSP frame-ancestors.

NE CONTOURNE PAS ces protections.

INTERDIT :
- reverse proxy destiné à supprimer les headers X-Frame-Options ;
- réécriture du site distant ;
- bypass CSP.

Si un fournisseur refuse l'intégration :
afficher dans StatisticsPage :

"Ce fournisseur ne permet pas l'affichage intégré."

et proposer :
[Ouvrir dans le navigateur]

L'application doit rester fonctionnelle.

==================================================
CSP
==================================================

Le CSP actuel possède :

default-src 'self'

et ne possède pas `frame-src`.

Une iframe externe sera donc bloquée par notre propre CSP.

Ajouter un `frame-src` EXPLICITE limité aux fournisseurs de statistiques autorisés.

Ne mets jamais :

frame-src *

Réutiliser la source de vérité des hosts/provider autant que raisonnablement possible.

Exemples d'origines autorisées selon les URLs réellement utilisées :
https://op.gg
https://www.op.gg
https://www.deeplol.gg
https://dpm.lol
https://www.leagueofgraphs.com

Vérifier les redirects réels.

==================================================
BRIDGE PYWEBVIEW — TEST DE SÉCURITÉ OBLIGATOIRE
==================================================

Nous allons maintenant charger une page tierce à l'intérieur du WebView OTP LOL.

Vérifie sur un vrai WebView2 si un document cross-origin chargé dans l'iframe peut accéder à :

window.pywebview
window.pywebview.api

Le site externe NE DOIT JAMAIS pouvoir appeler :
- open_local_folder ;
- toggle_fullscreen ;
- open_external_url ;
- resize_window ;
- ou toute autre API native.

Si le bridge est injecté dans les sous-frames :
STOPPE l'intégration iframe telle quelle
et isole d'abord le bridge.

Ne livre pas une iframe externe ayant accès aux API natives.

Utiliser également un iframe avec restrictions raisonnables :

- pas de top-navigation ;
- referrerPolicy no-referrer ;
- sandbox minimal compatible avec le fournisseur.

Tester le comportement réel dans WebView2.

==================================================
RACCOURCI STATS : NOUVEAU COMPORTEMENT
==================================================

Le comportement actuel appelle `webbrowser.open()`.

Le supprimer pour le raccourci principal.

Nouveau comportement Alt+P :

1. si OTP LOL est caché :
   → afficher/restaurer la fenêtre ;
2. naviguer vers :
   #statistics
3. donner le focus à l'application.

Cela doit fonctionner :
- League connecté ;
- League fermé ;
- compte manuel ;
- aucun compte.

Créer une méthode native générique :

WebViewWindow.open_route(route)

par exemple.

`open_settings()` peut éventuellement déléguer à cette méthode.

Ne pas multiplier les `load_url` codés en dur.

==================================================
SIMPLIFIER LES SETTINGS STATS
==================================================

Puisque le hotkey ouvre désormais l'onglet Statistiques :

`preferred_stats_site`
devient la source unique du fournisseur affiché.

`preferred_hotkey_site` n'a plus de vraie utilité utilisateur.

Ne casse PAS les anciennes configurations.

Approche recommandée :

- conserver `preferred_hotkey_site` dans le schéma/persistence pour compatibilité durant cette version ;
- retirer son contrôle de l'interface Settings ;
- ne plus l'utiliser pour le nouveau hotkey ;
- documenter qu'il s'agit d'une clé legacy ;
- éventuellement prévoir sa suppression lors d'une future migration de schéma.

Conserver la clé technique :

hotkey_open_site

si la renommer impose une migration inutile.

Mais changer son libellé UI en :

"Ouvrir Statistiques"

La combinaison configurée continue de fonctionner.

==================================================
DASHBOARD QUICK ACTIONS
==================================================

Modifier :

"Ouvrir les statistiques"

Actuellement :
→ navigateur externe.

Nouveau comportement :
→ #statistics.

Cela permet également de supprimer la requête `/api/links/stats` du critical path Dashboard si elle n'est plus nécessaire à cet écran.

Résultat :
Dashboard plus rapide et responsabilité mieux séparée.

"Raccourcis clavier"
→ #settings/shortcuts

"Modifier le site de statistiques"
→ #settings/links.

==================================================
API STATS
==================================================

Auditer `/api/links/stats`.

Le résultat devrait fournir suffisamment d'information pour StatisticsPage, par exemple :

{
  available: true/false,
  site: "opgg",
  url: "...",
  homepage_url: "..."
}

Si nécessaire, étendre proprement `StatsLinkResponse`.

Ne jamais accepter une URL arbitraire fournie par le frontend.

Toutes les URLs statistiques doivent être produites côté backend à partir :
- d'un provider connu ;
- d'une région valide ;
- d'un Riot ID validé.

Conserver l'allowlist HTTPS actuelle.

==================================================
P0/P1 — TESTS MANQUANTS À AJOUTER
==================================================

Ajouter au minimum :

DATADRAGON
- offline cache ;
- no duplicate remote champion details ;
- splash champion sans champion-detail fetch ;
- splash skin fast path avec skin_num ;
- backoff réseau.

PRESETS
- fixed skin → miniature présente dans le bouton Skin ;
- random → preview présente ;
- spell dropdown affiche les icônes ;
- selected spell affiche son icône.

DASHBOARD
- selected fixed skin utilisé comme grand splash ;
- fallback base splash ;
- quick stats → #statistics ;
- shortcuts → #settings/shortcuts.

SETTINGS
- #settings/shortcuts ouvre directement Raccourcis ;
- #settings/links ouvre directement Liens.

TOPBAR
- phase longue ne provoque pas overflow ;
- connexion située dans le groupe droit.

STATISTICS
- route #statistics ;
- sidebar active ;
- preferred provider utilisé ;
- URL valide rendue ;
- no account state ;
- settings link ;
- reload ;
- external fallback ;
- CSP only allows known provider origins.

DESKTOP
- hotkey stats montre la fenêtre ;
- hotkey stats charge #statistics ;
- fonctionne sans LCU.

==================================================
PLAN_UPDATE — 100 % OBLIGATOIRE
==================================================

Après toutes les modifications :

RELIRE `plan_update.md` DEPUIS LE DÉBUT.

Pour CHACUNE des 20 sections :
- retrouver le code correspondant ;
- retrouver au moins un test lorsque demandé ;
- vérifier le comportement.

Ne te contente pas d'un document déclarant "Couvert".

Une fonctionnalité n'est couverte que si le code réel correspond.

Mettre à jour :
- docs/V2_PARITY.md
- docs/architecture.md
- docs/performance.md si nécessaire
- plan_update.md uniquement si le nouveau comportement Statistiques rend une ancienne exigence obsolète.

Le nouveau hotkey interne `#statistics` remplace explicitement l'ancienne exigence d'ouverture externe.

==================================================
REVUE FINALE DES SOUS-AGENTS
==================================================

Une fois tous les sous-agents terminés :

1. le main agent relit TOUS leurs changements ;
2. recherche les duplications ;
3. recherche les appels réseau ajoutés ;
4. vérifie que le cache/offline fonctionne ;
5. vérifie la sécurité de l'iframe ;
6. vérifie les types OpenAPI ;
7. vérifie les imports morts ;
8. vérifie console React ;
9. vérifie les warnings Python ;
10. corrige directement tout problème trouvé.

Ne t'arrête PAS au rapport des sous-agents.

==================================================
VALIDATION OBLIGATOIRE
==================================================

Backend :

python -m unittest discover -s tests -p "test_*.py"
python -m compileall -q launcher_web.py src tests create_exe.py

Ruff sur tous les fichiers modifiés.

Frontend :

cd frontend
npm run api:generate
npm run api:check
npm run typecheck
npm run test
npm run build
npm run test:e2e

Puis test réel source :

python launcher_web.py

Vérifier les logs pendant au moins une minute :
- aucun spam Data Dragon ;
- pas de répétition de champion detail ;
- pas d'exception WebView ;
- hotkeys actifs.

Test WebView2 réel :
- Dashboard ;
- Presets ;
- éditeur Preset ;
- skin fixe ;
- spell dropdown ;
- Dashboard skin splash ;
- #settings/shortcuts ;
- #settings/links ;
- Statistiques ;
- hotkey stats fenêtre cachée ;
- mode League fermé.

==================================================
DEFINITION OF DONE
==================================================

Ne termine PAS tant que :

[ ] 100 % du plan_update encore pertinent est implémenté
[ ] DataDragon offline ne spamme plus le réseau
[ ] aucune demande de splash base ne télécharge champion detail
[ ] skin fixe visible dans le bouton de l'éditeur
[ ] sorts visibles avec leurs icônes
[ ] Dashboard utilise le skin sélectionné
[ ] Quick Action raccourcis ouvre directement Raccourcis
[ ] topbar ne saute plus selon la phase
[ ] indicateur client est à droite
[ ] Select natif Dashboard supprimé
[ ] onglet Statistiques existe sous Presets
[ ] site préféré est affiché dans cet onglet lorsqu'autorisé
[ ] iframe n'expose pas le bridge natif
[ ] CSP frame-src est strict
[ ] fallback propre si fournisseur refuse iframe
[ ] Alt+P ouvre OTP LOL sur Statistiques
[ ] Alt+P fonctionne sans League
[ ] Dashboard n'ouvre plus automatiquement le navigateur stats
[ ] API/types OpenAPI synchronisés
[ ] tests Python verts
[ ] tests frontend verts
[ ] Playwright vert
[ ] build vert
[ ] test réel WebView2 effectué

Si une contrainte EXTERNE empêche réellement l'intégration d'un fournisseur
(X-Frame-Options / frame-ancestors),
ce n'est pas une raison pour bricoler un bypass.

Implémente le fallback sécurisé,
documente précisément quel fournisseur bloque,
puis continue tous les autres points.

==================================================
RAPPORT FINAL
==================================================

À la fin seulement, donne :

- checklist plan_update 20/20 avec preuve fichier/test ;
- bugs utilisateur corrigés ;
- changements Statistiques ;
- résultats des sous-agents + review effectuée ;
- résultats exacts des commandes de test ;
- résultat du test WebView2 réel ;
- fournisseurs stats intégrables/non intégrables ;
- éventuelles limitations strictement externes restantes.

Aucun "reste à faire" pour une tâche raisonnablement corrigeable dans ce périmètre.