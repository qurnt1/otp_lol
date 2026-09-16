# OTP LOL V2, contrat de parité avec `main`

Ce document sert de contrat de non-régression pour la migration vers le shell WebView. Les comportements métier restent portés par `src/core` et `src/lcu`; le frontend V2 ne fait que les exposer et les configurer.

| Fonction | Comportement dans `main` | Correspondance V2 | Statut | Test | Action |
|---|---|---|---|---|---|
| Auto-Accept | Accepte le ready-check si activé | Switch Dashboard + runtime LCU | Couvert | `tests/test_integration_lcu.py` | Conserver |
| Pre-pick | Survole le champion prioritaire | Runtime LCU, presets V2 | Couvert | `tests/test_core_champ_select.py` | Conserver |
| Presets 1 → 2 → 3 | Essaie les slots dans l’ordre | Éditeur Presets | Couvert | `tests/test_api.py` | Conserver |
| Auto-Pick / Auto-Ban | Verrouille pick ou ban configuré | Switches Dashboard | Couvert | `tests/test_core_champ_select.py` | Conserver |
| Auto-Summs / Auto-Runes | Applique les réglages du slot | Preset slot + runtime | Couvert | `tests/test_lcu_runtime.py` | Conserver |
| `rune_auto_apply` | Choix indépendant par preset | Éditeur Runes | Couvert | `tests/test_api.py` | Conserver |
| Skin fixe / pool aléatoire | Sélection et fallback LCU | Skin picker différé | Couvert | `tests/test_datadragon.py` | Conserver |
| Skins possédés | Inventaire LCU puis fallback pickable | Skin picker | Couvert | `tests/test_api.py` | Conserver |
| Override skin de la fenêtre principale | Mode global historique | Override par slot V2, quatre modes dans chaque card | Couvert | `tests/test_config.py`, `tests/test_api.py`, `frontend/e2e/dashboard-disconnected.spec.ts` | Conserver |
| Recovery champion select / retries | Reconnexion et retries existants | Runtime inchangé | Couvert | `tests/test_integration_lcu.py` | Ne pas réécrire |
| Statuts d’automatisation | Confirme les étapes LCU et les erreurs | Événements `status` structurés, libellés dans `fr.ts` | Couvert | `tests/test_core_champ_select.py`, `frontend/src/domain/runtimeStatus.test.ts` | Conserver |
| Auto Play Again | Retour au lobby après partie | Switch Settings | Couvert | `tests/test_integration_lcu.py` | Conserver |
| Compte / région / Riot ID manuel | Détection LCU ou saisie manuelle | RuntimeTopBar + Settings | Couvert | `tests/test_api.py` | Conserver |
| Liens OP.GG, Porofessor, DeepLOL, DPM, League of Graphs | URL allowlistée et fournisseur choisi | Quick actions + Settings | Couvert | `tests/test_api.py` | Conserver |
| Historique / effacement | Journal local et suppression confirmée | Table History + filtres + recherche + confirmation | Couvert | `tests/test_history.py`, `frontend/e2e/settings.spec.ts` | Conserver |
| Tray, show/hide, Settings, quit | Contrôles natifs | `src/desktop/tray.py` + bridge | Couvert | `tests/test_desktop.py` | Conserver |
| Toggle presets / Auto-Ban | Menu tray persistant | API Settings | Couvert | `tests/test_desktop.py` | Conserver |
| Hotkeys show/hide et stats | Raccourcis globaux | HotkeyManager | Couvert | `tests/test_desktop.py` | Conserver |
| Dark / Light | Thème persistant | Appearance Settings | Couvert | `tests/test_api.py` | Harmoniser tokens |
| Auto-hide connect / close LoL | Effets de transition LCU | `ApplicationContext` | Couvert | `tests/test_context.py` | Ajouter cas UI natif |
| GitHub updates | Vérification différée et ignorée | Query updates 7 s après le premier rendu, puis toutes les 6 h | Couvert | `frontend/e2e/dashboard-disconnected.spec.ts`, `tests/test_api.py` | Conserver |
| Assets, icônes, cache | Cache local et ressources bundle | Routes assets | Couvert | `tests/test_api.py` | Conserver |
| Instance unique / migration config | Lockfile et TOML migré | Launcher WebView | Couvert | `tests/test_config.py` | Ajouter géométrie |
| Fenêtre redimensionnable | Taille native persistée | `WebViewWindow`, restauration position/taille/maximisation et validation multi-écran | Couvert localement | `tests/test_desktop.py`, `tests/test_config.py` | Vérifier sur plusieurs écrans réels |

## Règle de validation

Toute nouvelle fonctionnalité visible doit avoir une entrée ici, un test ciblé et une vérification E2E si elle traverse le shell. Les tests locaux prouvent la logique et le contrat HTTP, pas la disponibilité réelle du client League ni le comportement d’un WebView2 installé sur chaque machine.
