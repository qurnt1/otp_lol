# OTP LOL V2, démarrage et instrumentation

Le chemin critique reste local : `/api/bootstrap` expose les réglages et aperçus déjà disponibles, puis le Dashboard s'affiche sans charger les catalogues complets, l'historique, les maîtrises ou les challenges. Au démarrage, OTP LOL lit le snapshot LCU local et le cache Data Dragon depuis le disque, sans requête réseau. Après connexion du client League, le rafraîchissement du snapshot statique LCU se fait en arrière-plan. Data Dragon reste un fallback de secours.

À l'ouverture de `#statistics`, seuls le résumé de compte, le classement et les derniers matchs sont demandés. Maîtrises, challenges, détail d'un match et timeline sont lazy. `#live` conserve son lien de statistiques de partie séparé. Les diagnostics et leurs tests d'endpoints ne s'exécutent que depuis la page Diagnostics; aucun catalogue items complet ni challenge n'est chargé au démarrage.

Repères disponibles dans les logs :

- `T0`, entrée launcher
- `T1`, settings normalisés
- `T2`, FastAPI prêt
- `T3`, WebView créé
- `T4`, DOM initial
- `T5`, montage React
- `T6`, bootstrap reçu
- `T7`, Dashboard interactif
- `T8`, Dashboard prêt pour les interactions

Mesure locale :

```powershell
python scripts/benchmark_startup.py
```

Le script construit `onefile` et `onedir`, exécute cinq démarrages packagés via `--self-test` par variante et écrit `build-benchmark/startup-results.txt`. Ces mesures représentent le cache du système de fichiers du poste courant, pas un démarrage à froid après redémarrage Windows. Le choix de distribution doit être fait avec ces chiffres et la contrainte de livraison, pas avec une intuition.

Dernière mesure locale, le 15 septembre 2026 : `onefile` a démarré en moyenne en 5 421 ms, contre 1 586 ms pour `onedir` (environ 71 % plus rapide). `onedir` est donc le format embarqué de l’installateur V2. Le workflow de release construit maintenant l’application onedir puis l’installateur `OTP-LOL-Setup.exe`.
