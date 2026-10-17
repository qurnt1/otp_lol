Oui. Le problème de région mérite d’être traité comme un correctif prioritaire, parce qu’il casse toute la chaîne `compte détecté → région → URL Stats/Live → persistance du compte`.

J’ai vérifié le fonctionnement LCU actuel. Riot distingue bien les platform IDs comme `EUW1`, `EUN1`, `NA1`, etc., des regional routings comme `EUROPE`, `AMERICAS`, `ASIA`, `SEA`. ([Riot Developer Portal][1]) Côté LCU, `/riotclient/region-locale` existe bien et est encore utilisé par des projets actuels pour déterminer la région, tandis que `/lol-platform-config/v1/namespaces/...` expose également les données de plateforme ; un projet récent récupère explicitement `LoginDataPacket.platformId`. ([GitHub][2])

Le bug de ton implémentation me paraît assez clair : ton pipeline finit par faire `PLATFORM_TO_REGION.get(platform)`, alors que cette table attend des valeurs du type `euw1`, `na1`, etc.  Si la source utilisée te renvoie une valeur de région du type `EUW` au lieu d’un platform ID `EUW1`, la résolution échoue et le compte automatique devient inutilisable.

Je ferais le chantier suivant.

## Plan d’implémentation

### Phase 1 — Fiabiliser complètement la détection Riot ID + région

C’est la priorité P0.

Le but doit être de produire une seule identité normalisée :

```text
Riot ID           Quentin#TAG
Platform ID       euw1
Provider region   euw
Regional routing  europe
Source            platform_config
```

Il faut surtout arrêter de considérer `platform`, `region` et `regional routing` comme trois variantes interchangeables de la même donnée.

Je créerais une petite couche de normalisation LCU, sans framework compliqué, par exemple dans `src/lcu/region.py` ou directement dans `src/lcu/runtime.py` si tu préfères éviter un fichier supplémentaire.

Elle exposerait conceptuellement :

```python
normalize_platform_id(...)
normalize_provider_region(...)
platform_to_provider_region(...)
platform_to_regional_routing(...)
detect_account_routing(connection)
```

La détection doit essayer plusieurs sources par ordre de fiabilité.

1. Source principale :

```text
/lol-platform-config/v1/namespaces/LoginDataPacket/platformId
```

ou le namespace `LoginDataPacket` si le endpoint ciblé est moins stable.

Le résultat attendu est un platform ID Riot, par exemple :

```text
EUW1
EUN1
NA1
KR
```

C’est précisément le type de valeur dont ton `PLATFORM_TO_REGION` a besoin. Le endpoint `lol-platform-config` et sa clé `platformId` sont attestés dans le LCU, et du code récent continue à utiliser `LoginDataPacket.platformId`. ([Gist][3])

2. Premier fallback :

```text
/rso-auth/v1/authorization
```

et récupérer :

```json
{
  "currentPlatformId": "EUW1"
}
```

Cette information représente explicitement la plateforme du compte connecté. ([Gist][3])

3. Deuxième fallback :

```text
/riotclient/region-locale
```

puis éventuellement :

```text
/riotclient/get_region_locale
```

Ces endpoints exposent bien une région/locale. ([GitHub][4])

Mais il faut traiter leur `region` comme une **région Riot**, pas aveuglément comme un `platformId`.

Donc :

```text
EUW  -> euw -> EUW1
EUNE -> eune -> EUN1
NA   -> na -> NA1
```

4. Dernier fallback raisonnable :

```text
/riotclient/command-line-args
```

et parser :

```text
--region=EUW
```

Des intégrations LCU utilisent également cette information. ([GitHub][5])

Je n’utiliserais pas `locale`, `webLanguage` ou `webRegion` pour déduire la plateforme. Ce serait trop fragile.

---

### Phase 2 — Centraliser les mappings

Aujourd’hui tu as essentiellement :

```python
PLATFORM_TO_REGION = {
    "euw1": "euw",
    ...
}
```

Je garderais cette table mais ajouterais explicitement son inverse :

```python
REGION_TO_PLATFORM = {
    "euw": "euw1",
    "eune": "eun1",
    "na": "na1",
    "kr": "kr",
    ...
}
```

Et une fonction de normalisation qui accepte les variantes connues :

```text
EUW
euw
EUW1
euw1
```

pour toujours retourner :

```text
platform_id = euw1
provider_region = euw
regional_routing = europe
```

Riot documente officiellement `EUW1`, `EUN1`, `NA1`, `BR1`, `LA1`, `LA2`, etc. comme platform routing values et `EUROPE`, `AMERICAS`, `ASIA`, `SEA` comme regional routing values. ([Riot Developer Portal][1])

Important : je ne mélangerais plus jamais ces trois notions.

---

### Phase 3 — Rendre la persistance du compte automatique robuste

Une fois Riot ID + région détectés :

```text
Quentin#TAG
euw
euw1
```

les trois valeurs doivent être considérées comme un seul objet cohérent.

Aucune écriture si tu as seulement :

```text
Riot ID = OK
region = vide
```

ou :

```text
region = euw
Riot ID = invalide
```

Mais dès que l’identité complète est valide :

```python
persist_detected_account(
    riot_id="Quentin#TAG",
    region="euw",
    platform="euw1",
)
```

Et il faut ensuite immédiatement mettre à jour :

```text
runtime snapshot
settings
stats-link
live-stats-link
Settings UI
```

Autre petit correctif : aujourd’hui `account_identity_updated` est envoyé même lorsque les données n’ont pas changé. Je modifierais ça pour ne publier l’événement que lorsque `changed == True`.

Ça évite des invalidations React Query inutiles.

---

### Phase 4 — Découpler complètement « Compte » de « Stats »

Je profiterais de ce chantier pour corriger une faiblesse actuelle.

`SettingsPage` utilise actuellement :

```tsx
api.getStatsLink()
```

pour récupérer `account_source`.

Ça fonctionne, mais c’est conceptuellement mauvais :

```text
Settings > Compte
       ↓
endpoint Stats
       ↓
identité Riot
```

Je créerais un endpoint dédié :

```text
GET /api/account/identity
```

Réponse :

```json
{
  "riot_id": "Quentin#TAG",
  "region": "euw",
  "platform_id": "euw1",
  "regional_routing": "europe",
  "source": "connected",
  "connected": true
}
```

`source` :

```text
connected
saved
manual
unavailable
```

Ensuite :

```text
Settings
Stats
Live
Desktop provider browser
```

utilisent tous le même résolveur.

C’est beaucoup plus propre et ça rend la résolution de région testable indépendamment des providers.

---

## Phase 5 — Inverser le réglage Compte comme tu le demandes

Là c’est très simple et c’est une bonne modification UX.

Ton modèle backend est déjà dans le bon sens :

```text
summoner_name_auto_detect = true
```

C’est uniquement l’interface qui inverse actuellement la logique :

```tsx
label={fr.settings.manualAccount}
checked={!local.summoner_name_auto_detect}
onChange={(value) =>
  update("summoner_name_auto_detect", !value)
}
```



Donc surtout : **ne change pas la clé backend**.

Pas de migration de settings.

On garde :

```text
summoner_name_auto_detect
```

et on modifie simplement l’UI :

```text
Détection automatique du compte        [ON]
```

avec :

```tsx
checked={local.summoner_name_auto_detect}

onChange={(value) =>
  update("summoner_name_auto_detect", value)
}
```

Le comportement devient beaucoup plus intuitif.

Quand ON :

```text
Détection automatique du compte       ON

Riot ID
Quentin#TAG

Région
EUW

● Compte League connecté
```

ou, League fermé :

```text
Détection automatique du compte       ON

Riot ID
Quentin#TAG

Région
EUW

Dernier compte détecté · League fermé

[ Oublier ce compte ]
```

Quand OFF :

```text
Détection automatique du compte       OFF

Riot ID
[ Nom#Tag                  ]

Région
[ EUW ▼ ]

Compte configuré manuellement
```

C’est beaucoup plus logique que « Utiliser un Riot ID manuel ».

---

## Phase 6 — Corriger les textes du mode Compte

Il faut en profiter pour corriger le wording actuel.

Je remplacerais :

```text
Utiliser un Riot ID manuel
```

par :

```text
Détection automatique du compte
```

Description :

```text
Détecte automatiquement le Riot ID et la région du compte connecté à League.
Le dernier compte détecté reste disponible lorsque League est fermé.
```

Quand désactivé :

```text
La détection automatique est désactivée.
Le Riot ID et la région saisis ci-dessous sont utilisés.
```

Il y a aussi une contradiction actuellement dans la description du mode manuel : elle dit que les valeurs manuelles sont utilisées puis parle du dernier compte LCU lorsque League est fermé. Cette phrase doit disparaître.

---

## Phase 7 — Ajouter un état de diagnostic de la détection

Vu que Riot peut changer le LCU après un patch, je pense que c’est particulièrement pertinent pour OTP LOL.

Dans Diagnostics, je rajouterais une petite section :

```text
Compte Riot

Riot ID             Quentin#TAG
Platform ID         EUW1
Région provider     EUW
Routing             EUROPE
Source              platform-config
État                Valide
```

Aucune donnée d’authentification.

Pas de token.

Pas de PUUID si ce n’est pas nécessaire.

Ça permettrait, si un patch Riot casse la détection, de voir immédiatement :

```text
Riot ID : OK
Platform : —
Region locale : EUW
Résolution : échec
```

au lieu de « Stats ne marche plus » sans savoir pourquoi.

---

## Phase 8 — Corriger le composant « Dernière action »

Je reprendrais le petit problème identifié dans mon audit précédent.

Actuellement :

```tsx
WARN/ERROR -> warning
INFO       -> info
tout le reste -> success
```



Or `ROLE`, `GAMEMODE`, etc. ne sont pas des succès.

Le fallback doit être :

```text
info
```

et `success` doit être explicitement associé aux actions réussies.

Idéalement `runtimeStatus.ts` retourne directement :

```ts
{
  message: "...",
  tone: "success" | "info" | "warning"
}
```

Ainsi le composant Dashboard ne réinterprète plus des codes métier.

---

## Phase 9 — Corriger définitivement le scheduler de mises à jour

Le système actuel fait bien un premier contrôle, mais le timer ne se reprogramme pas réellement toutes les six heures.

Je ferais un timeout récursif :

```text
startup
  ↓
7 s
  ↓
check
  ↓
6 h
  ↓
check
  ↓
6 h
  ↓
check
```

Pas un `setInterval` aveugle : avec un timeout récursif, tu peux programmer le prochain check **après** la fin de la requête.

Ajouter un test avec fake timers :

```text
t = 0        0 requête
t = 7 sec    1 requête
t = 6h+7s    2 requêtes
t = 12h+7s   3 requêtes
```

Et vérifier également que la version ignorée reste masquée.

---

## Phase 10 — Corriger les deux petits problèmes de wording restants

Changer :

```text
Ferme OTP LOL si le client League se ferme ou perd sa connexion.
```

en :

```text
Ferme OTP LOL lorsque le client League est réellement fermé.
```

Puis adapter les textes liés au compte manuel à la nouvelle logique positive « Détection automatique ».

---

## Phase 11 — Ajouter un petit état explicatif dans En direct

Quand League est fermé mais qu’un dernier compte existe, ne pas donner l’impression qu’une partie live peut être détectée.

Par exemple :

```text
League est fermé

Le profil du dernier compte détecté reste accessible.
Les informations de partie en direct seront disponibles lorsque League sera lancé et qu’une partie commencera.
```

Le provider peut rester accessible.

Ce n’est pas un blocage.

---

## Phase 12 — Nettoyer `plan_update.md`

Je ne laisserais pas le prompt Codex de plusieurs centaines de lignes comme `plan_update.md`.

Le diff montre qu’il est justement devenu le prompt complet.

Je déplacerais cette trace vers :

```text
docs/archive/2026-09-account-and-reliability-implementation.md
```

et je remettrais `plan_update.md` à quelque chose comme :

```text
# Plan actif

[x] OpenAPI
[x] Skin race
[x] LCU transient disconnect
[x] Account persistence
[ ] Region auto-detection
[ ] Auto-detection toggle UX
[ ] Update scheduler
[ ] Runtime status tones
[ ] Native Windows smoke test
```

Une fois tout terminé, le fichier peut être vidé ou archivé.

---

# Tests que je demanderais à Codex

La partie région doit avoir une vraie matrice.

| Cas                             | Entrée              | Attendu                 |
| ------------------------------- | ------------------- | ----------------------- |
| Platform config                 | `EUW1`              | `euw / euw1 / europe`   |
| Platform config                 | `EUN1`              | `eune / eun1 / europe`  |
| Platform config                 | `NA1`               | `na / na1 / americas`   |
| Platform config                 | `KR`                | `kr / kr / asia`        |
| region-locale fallback          | `EUW`               | `euw / euw1 / europe`   |
| command-line fallback           | `--region=EUW`      | même résultat           |
| source principale HS            | fallback valide     | détection réussie       |
| toutes sources HS               | —                   | `unavailable`           |
| Riot ID valide + région absente | partiel             | aucune persistance      |
| région valide + Riot ID absent  | partiel             | aucune persistance      |
| compte identique                | aucune modification | aucun événement inutile |
| changement de compte            | nouvelles données   | persistence + event     |
| auto ON connecté                | compte courant      | `connected`             |
| auto ON League fermé            | compte sauvegardé   | `saved`                 |
| auto OFF                        | manuel              | `manual`                |
| auto ON sans historique         | rien                | `unavailable`           |

Côté React/Playwright :

```text
Détection auto ON → champs non éditables + compte détecté
Détection auto OFF → champs manuels éditables
ON → OFF → ON → aucune inversion de valeur
compte connecté → source correcte
compte sauvegardé → source correcte
Oublier compte → disparition immédiate
région détectée → URLs Stats fonctionnelles
région détectée → URLs Live fonctionnelles
status ROLE/GAMEMODE → info et pas succès
update checker → plusieurs checks successifs
```

---

# Validation réelle indispensable

Et cette fois je demanderais explicitement à Codex de te fournir une checklist pour **toi**, car il ne pourra pas simuler parfaitement League.

Sur ton Windows :

1. Supprimer/renommer temporairement les données de compte sauvegardées.
2. Lancer OTP LOL avec League fermé.
3. Vérifier `unavailable`.
4. Lancer League et te connecter.
5. Vérifier que Riot ID apparaît.
6. Vérifier surtout que `EUW` apparaît.
7. Vérifier Diagnostics :

```text
platformId = EUW1
provider region = euw
routing = europe
```

8. Vérifier que Stats ouvre directement ton profil.
9. Vérifier En direct.
10. Fermer OTP LOL.
11. Fermer League.
12. Relancer OTP LOL.
13. Vérifier que le compte apparaît comme :

```text
Dernier compte détecté · EUW · League fermé
```

14. Réactiver League et vérifier le passage automatique `saved → connected`.
15. Tester le switch :

```text
Détection automatique ON
↓
OFF
↓
saisie manuelle
↓
ON
```

sans mélange entre le compte manuel et le compte détecté.

---

### Ordre que je donnerais à Codex

Je ferais exactement :

```text
P0  Détection/normalisation région
P0  Endpoint account/identity
P0  Tests backend région
P1  Inversion UI détection automatique
P1  Tests Settings/Stats/Live
P1  account_identity_updated uniquement si changement
P1  Correctif update scheduler
P1  Correctif tone Dernière action
P2  Wording Settings
P2  Indication En direct hors connexion
P2  Diagnostics de routing
P2  Nettoyage plan_update.md
P3  Full pytest + Vitest + Playwright + OpenAPI + build
P3  Review indépendante
P3  Smoke-test Windows réel
```

Le point clé est que je ne ferais **pas** simplement un patch `EUW -> EUW1` au milieu de `websocket.py`. Je corrigerais maintenant la notion de routing proprement, avec une résolution à plusieurs sources. C’est un des morceaux dont dépendent Stats, Live, la persistance du compte et maintenant toute l’UX de détection automatique.

[1]: https://developer.riotgames.com/docs/lol?utm_source=chatgpt.com "Riot Developer Portal"
[2]: https://github.com/Nicetyone/league-lean?utm_source=chatgpt.com "GitHub - Nicetyone/league-lean: Pengu Loader plugin: lean Riot client tweaks, auto rune/build apply, meta tier list, post-game op.gg. Personal use; not endorsed by Riot Games. · GitHub"
[3]: https://gist.github.com/Pupix/bbcef124f094f5684804438faedabe19?utm_source=chatgpt.com "A swagger JSON map representing the API used inside the new League of Legends alpha client as it's presented in v0,3 · GitHub"
[4]: https://github.com/XHXIAIEIN/LeagueCustomLobby/blob/main/README.md?utm_source=chatgpt.com "LeagueCustomLobby/README.md at main · XHXIAIEIN/LeagueCustomLobby · GitHub"
[5]: https://github.com/WordlessMeteor/LoL-DIY-Programs/blob/main/Customized%20Program%2013%20-%20Fetch%20Ranked%20Apex.py?utm_source=chatgpt.com "LoL-DIY-Programs/Customized Program 13 - Fetch Ranked Apex.py at main · WordlessMeteor/LoL-DIY-Programs · GitHub"
