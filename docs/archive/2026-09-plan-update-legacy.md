Oui. Je ferais maintenant un seul chantier de consolidation, avec priorité à la stabilité pywebview et au cycle de vie des fenêtres providers avant de continuer l’UX.

L’exception `Main window failed to start` est importante : pywebview attend que certains événements de readiness de la fenêtre soient déclenchés avant `evaluate_js`, et les fonctions exposées via `js_api` sont exécutées dans des threads séparés avant que leur résultat soit renvoyé vers JavaScript. La documentation recommande explicitement d’attendre `pywebviewready` avant d’appeler `window.pywebview.api`. ([Pywebview][1]) Le stacktrace que tu as correspond justement au retour d’un appel Python → callback JS alors que la fenêtre principale n’est pas considérée comme prête.

Je donnerais donc ce plan à Codex.

## P0 — Corriger définitivement le lifecycle pywebview

Aujourd’hui, `DesktopBridge.open_provider_window()` crée et pilote directement les fenêtres secondaires depuis les appels JS.

Je ne veux plus que React puisse déclencher des opérations natives avant que pywebview soit réellement prêt.

À implémenter :

1. Créer un état frontend explicite `nativeBridgeReady`.
2. Ne pas simplement tester :

```ts
window.pywebview?.api
```

3. Écouter :

```ts
window.addEventListener("pywebviewready", ...)
```

et seulement à partir de là autoriser :

* ouverture provider ;
* resize ;
* fullscreen ;
* appels natifs ;
* opérations desktop.

En mode navigateur/Vite normal, prévoir un fallback propre.

Créer idéalement un hook :

```text
useNativeBridgeReady()
```

qui centralise ce comportement.

Aucun composant ne doit appeler directement le bridge sans passer par cette couche.

---

## P0 — Sortir la gestion des fenêtres provider du `DesktopBridge`

Je ferais un vrai petit :

```text
ProviderWindowManager
```

dans :

```text
src/desktop/provider_browser.py
```

ou un fichier dédié.

Il possède :

```text
stats_window
live_window
```

et gère lui-même :

```text
create
preload
show
hide
focus
navigate
reload
close
shutdown
status
```

`DesktopBridge` ne fait ensuite que déléguer.

Cela évite que toute la logique de lifecycle soit dispersée dans le bridge.

Le manager doit être thread-safe, parce que les fonctions `js_api` pywebview s’exécutent dans des threads séparés. ([Pywebview][2])

Utiliser un simple :

```python
threading.RLock()
```

autour de l’état des fenêtres est suffisant.

Pas besoin d’un système complexe.

---

# P0 — Précharger Stats et Live en arrière-plan

C’est ce qui résout ton problème de lenteur.

Objectif :

```text
Démarrage OTP LOL
        ↓
fenêtre principale affichée
        ↓
identité Riot disponible
        ↓
URLs Stats / Live résolues
        ↓
WebView Stats charge en arrière-plan
WebView Live charge en arrière-plan
        ↓
Utilisateur clique sur Statistiques
        ↓
show + focus
        ↓
site déjà chargé
```

Important : **ne pas lancer ce preload avant que la fenêtre principale soit `shown`**.

pywebview documente les événements `shown` et `loaded`, et son code attend explicitement que la fenêtre principale soit affichée avant d’initialiser d’autres fenêtres créées au démarrage. ([Pywebview][1])

Je déclencherais le preloader côté Python depuis :

```python
main_window.events.shown
```

et non depuis un `useEffect` React au démarrage.

Cela réduit beaucoup le risque lié à ton stacktrace.

---

## Ne pas utiliser naïvement `hidden=True`

Je serais prudent ici.

Il existe des bugs pywebview documentés autour de fenêtres démarrées `hidden=True` puis réaffichées, avec précisément des erreurs `Main window failed to start`. ([GitHub][3])

Je demanderais à Codex de tester deux stratégies et de conserver celle qui fonctionne réellement sous WebView2 :

### Stratégie préférée

Créer la fenêtre :

```text
focus=False
x/y hors écran ou emplacement neutre
```

la laisser atteindre :

```text
shown
loaded
```

puis appeler :

```python
hide()
```

Une fois que `loaded` est arrivé, elle est considérée comme initialisée.

Lorsque l’utilisateur clique :

```text
show()
restore()
focus()
```

### Alternative

`minimized=True + focus=False`

si cela fonctionne mieux avec la version pywebview installée.

Ne pas supposer que `hidden=True` est fiable sans test Windows réel.

---

# P0 — Une seule WebView préchargée par type

Je ne chargerais surtout pas 8 sites en parallèle.

Architecture :

```text
ProviderWindowManager
├── stats
│   └── provider actuellement choisi
└── live
    └── provider actuellement choisi
```

Donc seulement :

```text
2 WebView2 maximum préchargées
```

Si le provider Stats est OP.GG :

```text
stats = OP.GG déjà chargé
```

Si l’utilisateur passe ensuite à DeepLOL :

```text
même WebView
→ load_url(DeepLOL)
→ chargement background
```

Ça évite d’exploser la RAM.

---

# P0 — Ajouter un vrai état de chargement des providers

Pour chaque fenêtre :

```text
not_created
loading
ready
visible
hidden
error
closed
```

et conserver :

```text
provider_id
url
last_loaded_url
```

Utiliser les événements pywebview `loaded`, `shown`, `closed`.

Le frontend peut afficher par exemple :

```text
OP.GG
● Prêt
```

ou :

```text
DeepLOL
Chargement…
```

Mais ne pas spammer React avec des callbacks JS.

Tu peux exposer cet état via une petite API REST locale ou via le snapshot existant.

---

# P0 — Corriger le bouton Actualiser

Comme vu dans l’audit précédent, le bouton actuel peut seulement refaire le GET d’URL sans réellement recharger la WebView si l’URL n’a pas changé.

Créer une vraie fonction :

```python
reload_provider_window(kind)
```

qui appelle :

```text
load_url(current_url)
```

ou le mécanisme de reload WebView2 disponible.

Le bouton :

```text
Actualiser
```

doit donc :

```text
reload de la vraie WebView
```

et non :

```text
refetch de /api/links/stats
```

seulement.

---

# P0 — Tester et corriger le changement de provider

Quand une fenêtre existe :

```text
OP.GG
↓
DeepLOL
```

faire :

1. valider URL ;
2. mettre à jour le titre ;
3. appeler `load_url()`;
4. passer état `loading`;
5. événement `loaded`;
6. état `ready`.

Actuellement `navigate()` met à jour provider + URL mais pas forcément le titre de fenêtre.

Ajouter :

```text
DeepLOL | OTP LOL
```

après navigation.

---

# P0 — Nettoyage complet des fenêtres au shutdown

Au moment de fermer OTP LOL :

```text
fermer Stats
fermer Live
annuler preload
supprimer callbacks
puis détruire fenêtre principale
```

Il ne faut pas qu’un thread `js_api` termine après destruction du main WebView et essaie encore de résoudre sa Promise JS.

Ça pourrait justement produire ton stacktrace.

Ajouter un flag :

```python
shutting_down = True
```

et refuser toute nouvelle opération native après ce point.

---

# P1 — Mettre les providers directement dans Statistiques

Actuellement tu dois passer par Settings, ce qui est inutilement lourd.

En haut de la page :

```text
STATISTIQUES

Site

[ OP.GG ] [ DeepLOL ] [ DPM.LOL ] [ League of Graphs ]

Compte
Quentin#EUW · EUW

● OP.GG prêt

[ Afficher ]
[ Actualiser ]
[ Ouvrir dans le navigateur ]
```

Utiliser le catalogue providers existant.

Le provider sélectionné doit être visuellement évident.

Au clic sur DeepLOL :

```text
PATCH setting preferred_stats_site = deeplol
↓
invalidation React Query
↓
ProviderWindowManager.navigate("stats", DeepLOL)
↓
preload
```

Pas besoin d’aller dans Settings.

---

# P1 — Même chose pour En direct

En haut :

```text
EN DIRECT

[ Porofessor ] [ DeepLOL ] [ DPM.LOL ] [ OP.GG ]
```

Cliquer sur un provider met directement à jour :

```text
preferred_hotkey_site
```

Et le raccourci Alt+P utilisera donc immédiatement ce nouveau provider.

---

## Que faire des selectors dans Settings ?

Je les retirerais de l’interface Settings.

Il ne doit y avoir qu’un seul endroit principal pour choisir chaque provider :

```text
Statistiques → provider Stats
En direct → provider Live
```

Les settings backend restent évidemment stockés.

Cela évite deux UI différentes modifiant exactement la même chose.

---

# P1 — Corriger « Exporter le rapport » Diagnostics

Le code actuel génère un `Blob`, crée un `<a download>` puis fait `anchor.click()`.

Ça passe en Playwright parce que Chromium normal sait gérer ce téléchargement.

Mais dans ton WebView2 pywebview, le comportement de téléchargement Blob n'est manifestement pas fiable.

Je supprimerais ce mécanisme comme chemin principal desktop.

Créer une fonction native dédiée :

```python
save_diagnostics_report(include_riot_id: bool)
```

Elle doit :

1. générer le rapport via la même logique backend ;
2. ouvrir une boîte de dialogue Windows :

```text
Enregistrer le rapport
otp-lol-diagnostics.json
```

3. écrire en UTF-8 ;
4. retourner :

```json
{
  "success": true,
  "path": "..."
}
```

Ne surtout pas exposer un bridge générique :

```python
write_file(path, content)
```

Le bridge doit rester spécifique :

```text
export_diagnostics_report
```

pour éviter de créer une API arbitraire d’écriture filesystem.

Dans Chrome/Vite/Playwright :

```text
fallback Blob
```

pour conserver le développement navigateur.

Ajouter tests :

* desktop bridge présent → fonction native appelée ;
* annulation dialog → pas une erreur ;
* erreur écriture → message utilisateur ;
* navigateur normal → Blob download fonctionne.

---

# P1 — Renommer Historique → Journal de logs

Je ne renommerais PAS :

* route `#history`;
* API `/history`;
* fichier `history.json`;
* noms de classes backend.

Aucun intérêt technique.

Changer seulement l’UX :

```text
Historique
↓
Journal de logs
```

et titre :

```text
Journal de logs
```

La route interne reste :

```text
#history
```

Le label actuel vient bien de `fr.nav.history` et `fr.history.title`.

Adapter tests sidebar.

---

# P1 — Dashboard : supprimer complètement le selector de skin

Tu as actuellement le `<Select>` :

```text
Aucun / Fixe / Aléatoire
```

directement sur chaque card, avec son CSS `priority-mode-select`.

Je suis d’accord pour le retirer.

Le Dashboard doit être une synthèse.

La configuration se fait dans Presets.

Résultat :

```text
┌────────────────────────────────┐
│ Garen                          │
│ Flash · Ignite                 │
│ Conquérant                     │
│ Skin : God-King Garen          │
│                                │
│        Toute la carte cliquable│
└────────────────────────────────┘
```

Un clic n'importe où :

```text
#presets/pick_1
```

Supprimer :

* `<Select>`;
* callback `onSkinModeChange` dans la card ;
* CSS `.priority-mode-select`;
* largeur/padding réservés au selector.

Attention notamment au :

```css
padding-right: 96px
```

du preview skin s’il était uniquement destiné au selector.

Le retirer pour récupérer l’espace.

---

# P1 — Retirer `v11.0` du titre de fenêtre

Le code est explicite :

```python
title=f"{APP_NAME} v{CURRENT_VERSION}"
```



Remplacer par :

```python
title=APP_NAME
```

Donc dans Windows :

```text
OTP LOL
```

et non :

```text
OTP LOL v11.0
```

Ne pas supprimer pour autant la version de :

* metadata build ;
* update checker ;
* release GitHub ;
* installer ;
* diagnostics ;
* éventuel affichage Settings/About.

Le numéro de version doit toujours exister techniquement, juste pas dans le titre de fenêtre.

---

# P1 — Corriger les runes restantes de l'audit

Inclure également les correctifs précédents dans le même chantier.

### « Ne rien faire » doit exister même League déconnecté

Même si les pages ne peuvent pas être récupérées :

```text
⊘ Ne rien faire
  Conserver ma page actuelle

League doit être connecté pour afficher les autres pages.
```

L'utilisateur doit pouvoir désactiver les runes sans ouvrir League.

---

### Actualiser les runes à chaque ouverture du picker

Ne pas garder :

```text
staleTime = 1 heure
```

pour des pages utilisateur.

Faire :

```ts
staleTime: 0
refetchOnMount: "always"
```

ou équivalent.

---

### Page sauvegardée mais supprimée

Trois états :

```text
0
→ Ne rien faire

ID trouvé
→ page normale

ID > 0 introuvable
→ ⚠ Page de runes supprimée ou indisponible
```

Ne jamais faire croire qu'une page supprimée correspond à « Ne rien faire ».

---

### Dashboard

Remplacer :

```text
Runes par défaut
```

par :

```text
Conserver ma page actuelle
```

quand `rune_page_id == 0`.

Icône :

```text
CircleOff
```

plutôt que `R`.

---

### try/finally complet

Dès que :

```python
rune_apply_in_progress = True
```

tout le code suivant doit être dans :

```python
try:
    ...
finally:
    rune_apply_in_progress = False
```

y compris `_resolve_rune_selection()`.

---

# P2 — Compléter les régions SEA

Ajouter au resolver :

```text
PH2
SG2
TH2
TW2
VN2
```

avec routing :

```text
SEA
```

Mais séparer deux concepts :

```text
Riot platform → Riot routing
```

et :

```text
Riot platform → alias utilisé par OP.GG / DeepLOL / etc.
```

Ne pas supposer qu'un provider utilise forcément `ph2`, `sg2`, etc.

Ajouter tests par provider lorsque possible.

---

# P2 — Synchronisation de fermeture des provider windows

Si l'utilisateur clique sur la croix :

```text
provider state = closed
```

Le frontend ne doit plus afficher :

```text
« La fenêtre est ouverte »
```

Le plus simple est probablement d’éviter une affirmation trop précise.

Utiliser toujours :

```text
[ Afficher le site ]
```

avec état :

```text
Prêt
Chargement
Erreur
```

plutôt que :

```text
Fenêtre ouverte
```

---

# P2 — Documentation

Mettre à jour :

```text
README
PRODUCT.md
docs/architecture.md
docs/performance.md
docs/V2_PARITY.md
```

Les docs actuelles parlent encore de l'ancien modèle iframe ou de comportements qui ont changé ; par exemple `performance.md` décrit encore l'intégration directe du fournisseur dans `#statistics`.

Nouvelle source de vérité :

```text
React OTP LOL
+
WebView provider top-level préchargée
+
aucune iframe fournisseur
+
navigateur système uniquement fallback volontaire
```

Et corriger toutes les mentions de :

```text
rune_auto_apply
```

comme réglage utilisateur actif.

---

# P2 — `plan_update.md`

Remettre une checklist courte.

Par exemple :

```text
# Plan actif

## WebView
[ ] native bridge readiness
[ ] provider manager
[ ] preload Stats
[ ] preload Live
[ ] refresh réel
[ ] shutdown propre

## UI
[ ] providers dans Stats
[ ] providers dans Live
[ ] Historique → Journal de logs
[ ] Dashboard cards entièrement cliquables
[ ] titre OTP LOL sans version

## Diagnostics
[ ] export natif

## Runes
[ ] Ne rien faire offline
[ ] refresh pages
[ ] page supprimée
[ ] Dashboard wording
[ ] try/finally

## Finalisation
[ ] docs
[ ] tests
[ ] WebView2 natif
```

Archiver l'ancien gros plan.

---

# Tests automatisés à exiger

Backend/Python :

* ProviderWindowManager create/reuse/navigate.
* preload Stats.
* preload Live.
* aucune création avant `main_window.shown`.
* reload provider.
* fermeture/recréation.
* shutdown pendant preload.
* aucune action après `shutting_down=True`.
* changement titre provider.
* diagnostics export succès.
* diagnostics export cancel.
* diagnostics export erreur.
* rune lock toujours libéré.
* régions SEA.

Frontend :

* aucun appel native avant `pywebviewready`.
* provider Stats sélectionnable depuis Stats.
* provider Live sélectionnable depuis Live.
* changement provider persistant.
* état loading/ready/error.
* bouton refresh.
* renommage Journal de logs.
* Dashboard sans selector skin.
* toute card Dashboard navigue Presets.
* `Ne rien faire` visible offline.
* page rune supprimée.
* Dashboard `Conserver ma page actuelle`.

E2E :

* Stats provider 1 → provider 2.
* Live provider 1 → provider 2.
* setting mis à jour sans Settings.
* Diagnostics export fallback navigateur.
* navigation Journal de logs.
* card preset entière cliquable.

---

# Validation Windows réelle obligatoire

Codex ne doit pas prétendre que c'est entièrement validé sans cette étape.

Test manuel :

```text
1. Lancer OTP LOL.
2. Vérifier absence totale de :
   WebViewException: Main window failed to start.

3. Attendre 10–20 s sans ouvrir Stats.
4. Cliquer Statistiques.
5. Le site doit apparaître quasi immédiatement.

6. Faire pareil avec En direct.

7. Changer OP.GG → DeepLOL.
8. Attendre chargement.
9. Fermer fenêtre.
10. Réouvrir.
11. Actualiser.
12. Vérifier changement de titre.

13. Alt+P League au premier plan.
14. Alt+P OTP LOL minimisé.

15. Exporter Diagnostics.
16. Vérifier fichier JSON réel sur disque.

17. Dashboard :
    aucune dropdown skin.
    clic partout sur card → preset.

18. Vérifier titre Windows :
    OTP LOL
    et pas OTP LOL v11.0.

19. Tester DPI 100 / 125 / 150 %.
```

## Ordre d'implémentation recommandé

Je le ferais exactement dans cet ordre :

```text
P0  pywebviewready / bridge lifecycle
P0  ProviderWindowManager
P0  shutdown propre
P0  preload background Stats/Live
P0  reload réel

P1  selectors providers dans les pages
P1  export Diagnostics natif
P1  Dashboard preset cards
P1  Journal de logs
P1  titre OTP LOL

P1  correctifs runes restants

P2  régions SEA
P2  docs
P2  plan_update

P3  full test suite
P3  reviewer indépendant
P3  smoke test Windows/WebView2/League
```

Le point sur lequel je serais le plus strict avec Codex est : **ne pas simplement entourer `WebViewException` d'un `try/except` pour faire disparaître le traceback**. Il faut corriger le lifecycle qui permet à un appel `js_api` d'être exécuté avant/après la période où la fenêtre principale peut résoudre correctement sa Promise JS. Le preload doit ensuite être construit au-dessus de ce lifecycle corrigé, pas l'inverse.

[1]: https://pywebview.flowrl.com/api/?utm_source=chatgpt.com "API | pywebview"
[2]: https://pywebview.flowrl.com/guide/interdomain?utm_source=chatgpt.com "Javascript–Python bridge | pywebview"
[3]: https://github.com/r0x0r/pywebview/issues/1050?utm_source=chatgpt.com "Using create_window with hidden=True makes the show() command not work · Issue #1050 · r0x0r/pywebview · GitHub"
