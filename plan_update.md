Tu reprends le working tree ACTUEL après la dernière implémentation.
NE repars PAS du plan précédent et NE réimplémente PAS ce qui fonctionne déjà.

Avant toute modification :
- lis entièrement le diff actuel ;
- relis les fichiers concernés ;
- considère les constats ci-dessous comme des bugs/régressions à corriger ;
- ne valide pas une fonctionnalité uniquement parce qu'un test existant est vert :
  plusieurs tests actuels codifient eux-mêmes un mauvais comportement.

==================================================
P0 — DASHBOARD CARD : OUVRIR LE PRESET, PAS LE CHAMPION PICKER
==================================================

Bug actuel confirmé.

ChampionPriorityCard navigue vers :

#presets/pick_1
#presets/pick_2
#presets/pick_3

C'est correct.

Mais PresetsPage interprète actuellement cette action en faisant à la fois :

setEditingSlot(action)
setPicker({ kind: "champion", slot: action })

C'est incorrect.

COMPORTEMENT ATTENDU :

Clic card Dashboard slot 1
→ navigation #presets/pick_1
→ ouverture du PresetEditorDialog "Modifier la priorité 1"
→ NE PAS ouvrir ChampionPicker
→ aucun drawer supplémentaire
→ aucun focus sur #champion-search

Le sélecteur Champion doit s'ouvrir UNIQUEMENT lorsque l'utilisateur
clique ensuite sur le contrôle Champion dans PresetEditorDialog.

Même comportement pour pick_2 et pick_3.

Modifier le useEffect de PresetsPage :

pour action pick_N :
- setEditingSlot(action)
- setPicker(null)

Conserver le deep-link.

CORRIGER LE TEST EXISTANT.

Le test actuel :

"la carte complète ouvre directement l’éditeur du preset 3 et focalise la recherche"

encode le mauvais comportement.

Le remplacer par :

"la carte Dashboard ouvre le preset sans ouvrir le sélecteur de champion"

Assertions :
- URL #presets/pick_3
- PresetEditorDialog visible
- titre "Modifier la priorité 3"
- aucun ChampionPicker ouvert
- #champion-search absent/non visible
- puis clic sur le contrôle Champion
- alors seulement ChampionPicker apparaît
- alors seulement #champion-search reçoit le focus

==================================================
P0 — NE PAS PERDRE LES SETTINGS LORS DU PASSAGE SCHEMA 5 → 6
==================================================

Audit obligatoire de src/config/settings.py.

Le diff actuel :
- passe CONFIG_SCHEMA_VERSION de 5 à 6 ;
- supprime les migrations ;
- rejette tout fichier dont schema != 6 ;
- sauvegarde puis reset un fichier schema 5.

C'est une régression.

Une mise à jour OTP LOL ne doit PAS effacer :
- presets ;
- champions ;
- sorts ;
- runes ;
- skins ;
- providers ;
- Riot ID manuel ;
- région ;
- hotkeys ;
- automatisations ;
- thème ;
- géométrie de fenêtre.

Restaurer une migration explicite :

schema 5 → schema 6

La migration doit :
- conserver toutes les valeurs encore supportées ;
- convertir/supprimer seulement les anciennes clés devenues inutiles ;
- notamment traiter proprement main_skin_mode_override /
  main_skin_mode_overrides ;
- conserver les skin_mode des pick_slots ;
- fixer config_schema_version = 6.

Ajouter test réel :

schema 5 complet
→ load_parameters()
→ schema 6
→ mêmes presets et préférences importantes.

Ne considère PAS "backup + reset" comme une migration acceptable.

==================================================
P0 — AUDIT DATADRAGON / IMAGES OBSOLÈTES
==================================================

Symptôme réel :
les champions et Summoner Spells affichent parfois d'anciens artworks.

Les URLs Riot de base sont correctes.

La version actuelle doit être obtenue dynamiquement via :

https://ddragon.leagueoflegends.com/api/versions.json

Ne hardcode PAS 16.18.1.

AUDITER LE CACHE.

Problèmes identifiés :

1.
Les fichiers images sont stockés sous des chemins non versionnés :

ICONS_CACHE_DIR/<filename>
SPELLS_CACHE_DIR/<filename>

2.
Les clés mémoire ne contiennent pas la version :

champ_<id>
spell_<name>

3.
Un unique :

dd_version.txt

marque actuellement tout un dossier comme frais.

Une seule image téléchargée peut donc marquer tout le répertoire
comme appartenant à la nouvelle version alors que d'autres PNG sont anciens.

4.
Les routes locales renvoient :

Cache-Control: public, max-age=86400

avec des URLs stables comme :

/api/assets/champions/86.png
/api/assets/spells?name=Flash

WebView2 peut donc garder un ancien asset pendant 24 h.

CORRECTION RECOMMANDÉE :

Versionner le cache disque :

cache/icons/<dd_version>/<filename>
cache/spells/<dd_version>/<filename>

et si pertinent les autres assets Data Dragon.

Versionner aussi les clés mémoire :

champ:<version>:<champion_id>
spell:<version>:<spell_name>
champion_splash:<version>:<id>
skin_preview:<version>:<id>:<skin_num>

Quand Data Dragon passe de version A à B :
- ne jamais considérer les fichiers de A comme frais pour B ;
- ne jamais utiliser une clé mémoire de A comme celle de B ;
- conserver A comme fallback offline éventuel ;
- tenter B normalement.

SUPPRIMER ou revoir la logique directory-wide dd_version.txt.
Le téléchargement d'une seule image ne doit jamais valider toutes les autres.

VERSIONNER AUSSI LES URLs FRONTEND/API.

Exemple :

/api/assets/champions/86.png?v=16.18.1
/api/assets/champions/86/splash?v=16.18.1
/api/assets/spells?name=Flash&v=16.18.1

ou intégrer la version directement dans le path.

Ensuite le navigateur peut recevoir :

Cache-Control: public, max-age=31536000, immutable

SI l'URL elle-même contient la version.

Sinon conserver un cache court/no-cache.

Ne garde PAS max-age=86400 sur une URL non versionnée.

Ajouter `data_dragon_version` dans /api/metadata ou diagnostics
afin de pouvoir vérifier visuellement quelle version est chargée.

==================================================
AUDIT NOMS CHAMPIONS / SUMMONER SPELLS
==================================================

Créer un test qui charge le Data Dragon courant et vérifie :

Champion :
- id ;
- name ;
- slug ;
- image.full ;
- icon URL ;
- splash URL.

Summoner Spells :
- comparer SUMMONER_SPELL_MAP au summoner.json courant ;
- vérifier le numeric key ;
- vérifier image.full ;
- vérifier que chaque sort réellement supporté possède un asset.

Ne remplace pas aveuglément la logique métier par toutes les entrées
summoner.json :
certains spells Riot ne doivent probablement pas être proposés
dans les presets normaux.

Mais détecter automatiquement en test :
- ID incorrect ;
- nom supprimé/renommé ;
- fichier d'image manquant.

Ajouter un test de changement de version :

version A en cache
→ version B disponible
→ première réponse B ne doit pas renvoyer silencieusement une image A
  marquée fraîche.

Ajouter un test :

rafraîchir Garen en version B
→ ne doit PAS considérer automatiquement Flash/Lux/etc. comme frais en B.

==================================================
P0/P1 — NAVIGATEURS INTÉGRÉS : AUDIT RÉEL
==================================================

CONSTAt ACTUEL :

STATS_FRAME_ORIGINS contient uniquement DeepLOL.

LIVE_FRAME_ORIGINS est VIDE.

Donc actuellement :
- DeepLOL profil peut être intégré ;
- OP.GG / DPM / LeagueOfGraphs profil → fallback ;
- aucun fournisseur Live ne peut être intégré, par définition.

Ce n'est pas un bug React :
le backend renvoie embed_allowed=false pour TOUS les providers Live.

==================================================
NE PAS UTILISER LE TEST FAKE RIOT ID COMME PREUVE
==================================================

Le précédent audit Live a utilisé un Riot ID inexistant.

Ce test ne permet PAS de savoir si une vraie page in-game est intégrable.

Le test frontend qui mock :

embed_allowed: true

pour DeepLOL prouve uniquement que ProviderWebPanel sait afficher une iframe.
Il ne valide PAS DeepLOL réel.

Utilise des sous-agents pour cette investigation.

SOUS-AGENT A — URLS FOURNISSEURS

Pour chacun :
- DeepLOL
- Porofessor
- DPM.LOL
- OP.GG

Vérifier les URL builders actuels.

Pendant qu'un vrai compte est réellement en partie :
- générer l'URL live exacte ;
- tester dans navigateur normal ;
- tester en navigation WebView2 top-level ;
- tester en iframe dans OTP LOL ;
- relever redirect final ;
- relever status ;
- relever X-Frame-Options ;
- relever CSP frame-ancestors ;
- noter Cloudflare/challenge éventuel.

Ne faire aucune conclusion à partir d'un Riot ID inexistant.

Si aucun compte en partie n'est disponible au moment du test :
NE PAS INVENTER LE RÉSULTAT.
Préparer le harness automatisé et indiquer précisément le test humain restant.

SOUS-AGENT B — DEEPLOL LIVE

Tester particulièrement :

https://www.deeplol.gg/summoner/<region>/<riot-id>/ingame

avec un joueur réellement en game.

Si la vraie page fonctionne dans l'iframe WebView2
et ne pose pas de nouvelle contrainte de sécurité :

ajouter seulement :

LIVE_FRAME_ORIGINS["deeplol"] = "https://www.deeplol.gg"

Puis effectuer le test WebView2 final.

Ne l'ajoute PAS uniquement parce que le frontend mock passe.

==================================================
ALTERNATIVE SÛRE POUR LES SITES QUI REFUSENT LES IFRAMES
==================================================

Ne reverse-proxy pas les sites.
Ne retire pas leurs headers.
Ne modifie pas leur CSP.

Implémenter/prototyper plutôt un :

ProviderBrowserWindow

Il s'agit d'une SECONDE fenêtre pywebview/WebView2.

Elle charge l'URL fournisseur directement en TOP-LEVEL,
pas dans une iframe.

Architecture :

OTP LOL React
    ↓
bridge.open_provider_window(provider/kind)
    ↓
backend génère lui-même l'URL allowlistée
    ↓
webview.create_window(...)
    ↓
page OP.GG / Porofessor / DPM / DeepLOL

EXIGENCES SÉCURITÉ :

- js_api=None
- aucune méthode DesktopBridge exposée
- ne jamais appeler window.expose() sur cette fenêtre
- URL calculée côté Python depuis provider + Riot ID + région
- aucun URL arbitraire fourni par le frontend
- HTTPS uniquement
- host allowlisté
- bloquer ou externaliser les navigations vers hosts non approuvés si faisable
- fenêtre séparée du WebView principal
- aucune connexion à l'API native privilégiée OTP LOL

UX :

Pour provider iframe-compatible :
→ afficher directement dans l'onglet.

Pour provider iframe-incompatible :
→ afficher dans l'onglet un bouton principal :

"Ouvrir dans OTP LOL"

qui ouvre ProviderBrowserWindow.

Conserver aussi :

"Ouvrir dans le navigateur"

comme fallback secondaire.

Cela permet de garder une expérience intégrée à l'application
sans contourner X-Frame-Options.

==================================================
NE PAS UTILISER AdditionalAllowedFrameAncestors PAR DÉFAUT
==================================================

WebView2 possède une API nommée :

AdditionalAllowedFrameAncestors

Elle peut permettre d'afficher un site malgré X-Frame-Options /
frame-ancestors.

NE L'UTILISE PAS dans l'implémentation normale.

Microsoft prévient que ce mécanisme peut exposer le site à du clickjacking
et il revient à outrepasser la politique d'embedding du fournisseur.

On conserve donc la politique OTP LOL :

- iframe seulement si naturellement autorisée ;
- sinon top-level ProviderBrowserWindow ;
- sinon navigateur système.

==================================================
SI JE VEUX ABSOLUMENT LE SITE DANS LE MÊME ONGLET
==================================================

Lance un sous-agent architecture pour déterminer si un SECOND contrôle
WebView2 natif peut être hébergé dans la zone de contenu de la fenêtre
actuelle sans réécrire entièrement l'application.

Comparer :
A. architecture pywebview actuelle ;
B. WebView2 natif WinForms/WPF/WinUI ;
C. autre mécanisme raisonnable.

Ne migre rien avant d'avoir produit :
- complexité ;
- implications packaging ;
- bridge/security ;
- maintenance ;
- gain UX.

==================================================
P1 — PROVIDER REGISTRY
==================================================

Le diff actuel redéfinit :
- labels providers ;
- fichiers logos ;
- listes Stats/Live

dans catalog.py,
alors que les URLs/providers sont définis dans services/urls.py.

Éviter deux sources de vérité.

Créer une registry cohérente ou au minimum centraliser :
- id ;
- label ;
- logo filename ;
- homepage ;
- support profile/live ;
- iframe account/live.

Ne laisse pas deux fichiers pouvoir diverger silencieusement.

==================================================
P1 — VÉRIFIER LE CHANGEMENT SKIN MODE
==================================================

Le diff a également changé la sémantique Dashboard :

avant :
mode d'affichage/override

maintenant :
le Select du Dashboard modifie directement
`pick_slots[pick_N].skin_mode` via PUT /api/presets/pick_N.

Confirme que ce changement est volontaire.

Si oui :
- documenter ;
- garder les tests.

Sinon :
- restaurer la distinction entre preview Dashboard et config du preset.

Ne laisse pas ce changement fonctionnel passer comme simple refactor UI.

==================================================
VALIDATION FINALE
==================================================

Une fois les corrections réalisées :

1. exécuter tous les tests Python ;
2. typecheck ;
3. Vitest ;
4. build ;
5. Playwright ;
6. lancer réellement launcher_web.py ;
7. vérifier un vrai client League ;
8. tester images champions/sorts ;
9. comparer la version affichée à la dernière version Data Dragon ;
10. tester Dashboard → preset ;
11. tester ChampionPicker uniquement après clic Champion ;
12. tester #statistics ;
13. tester #live ;
14. tester ProviderBrowserWindow ;
15. tester Alt+P ;
16. tester upgrade d'un vrai parameters.toml schema 5 vers 6.

Ne termine PAS avec uniquement "tests verts".

Rapport final attendu :

- cause racine card Dashboard ;
- cause racine images obsolètes ;
- version Data Dragon réellement chargée ;
- résultat audit noms/spells ;
- résultat réel de chaque provider account/live ;
- headers XFO/CSP observés ;
- providers iframe-compatible ;
- providers nécessitant ProviderBrowserWindow ;
- résultat migration schema 5→6 ;
- commandes/tests exacts.

Si l'intégration Live ne peut toujours pas être déterminée automatiquement,
utilise plusieurs sous-agents pour la recherche et fournis le harness de test
au lieu de conclure sans preuve.