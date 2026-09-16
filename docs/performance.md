# OTP LOL V2, démarrage et instrumentation

Le chemin critique est désormais local : le serveur FastAPI expose `/api/bootstrap`, le WebView peut afficher le shell, puis les catalogues Data Dragon et GitHub sont demandés en arrière-plan ou à l’ouverture du picker. Une copie Data Dragon déjà présente est lue depuis le disque au démarrage sans réseau, puis une éventuelle mise à jour est vérifiée en arrière-plan.

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
