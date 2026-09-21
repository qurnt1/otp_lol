# OTP LOL V2, contrat de parité avec `main`

Ce document sert de contrat de non-régression pour la migration vers le shell WebView. Les comportements métier restent portés par `src/core` et `src/lcu`; le frontend V2 ne fait que les exposer et les configurer.

| Fonction | Comportement dans `main` | Correspondance V2 | Statut | Test | Action |
|---|---|---|---|---|---|
| Auto-Accept | Accepte le ready-check si activé | Switch Dashboard + runtime LCU | Couvert | `tests/test_integration_lcu.py` | Conserver |
| Pre-pick | Survole le champion prioritaire | Runtime LCU, presets V2 | Couvert | `tests/test_core_champ_select.py` | Conserver |
| Presets 1 → 2 → 3 | Essaie les slots dans l’ordre | Éditeur Presets | Couvert | `tests/test_api.py` | Conserver |
| Auto-Pick / Auto-Ban | Verrouille pick ou ban configuré | Switches Dashboard | Couvert | `tests/test_core_champ_select.py` | Conserver |
| Auto-Summs / Auto-Runes | Applique les réglages du slot | Preset slot + runtime | Couvert | `tests/test_lcu_runtime.py` | Conserver |
| `rune_page_id = 0` | Conserver la page actuelle | Éditeur Runes | Couvert | `tests/test_api.py`, `frontend/src/features/presets/RunePicker.tsx` | Les champs legacy ne sont pas interprétés |
| Skin fixe / pool aléatoire | Sélection et fallback LCU | Skin picker différé | Couvert | `tests/test_datadragon.py` | Conserver |
| Skins possédés | Inventaire LCU puis fallback pickable | Skin picker | Couvert | `tests/test_api.py` | Conserver |
| Modes de skin | Override global historique | Modes par preset `none`, `fixed`, `random`, identiques sur Dashboard et Presets | Couvert | `tests/test_config.py`, `tests/test_skin_modes.py`, `tests/test_core_champ_select.py`, E2E Dashboard | Aucun mode hérité ni override global |
| Recovery champion select / retries | Reconnexion et retries existants | Runtime inchangé | Couvert | `tests/test_integration_lcu.py` | Ne pas réécrire |
| Statuts d’automatisation | Confirme les étapes LCU et les erreurs | Événements `status` structurés, libellés dans `fr.ts`, dernière action visible sur le Dashboard | Couvert | `tests/test_core_champ_select.py`, `frontend/src/domain/runtimeStatus.test.ts`, `frontend/e2e/dashboard-connected.spec.ts` | Conserver |
| Auto Play Again | Retour au lobby après partie | Switch Settings | Couvert | `tests/test_integration_lcu.py` | Conserver |
| Compte / région / Riot ID manuel | Détection LCU ou saisie manuelle | Snapshot LCU complet, dernier compte local hors connexion, ou compte manuel explicite | Couvert | `tests/test_api.py`, `tests/test_context.py`, `tests/test_integration_lcu.py`, `tests/test_desktop.py`, `frontend/e2e/settings.spec.ts` | Aucun mélange de Riot ID/régions, source affichée, copie/oubli explicites; le tuple auto reste local à l’installation |
| Statistiques du compte | Profil via le fournisseur externe configuré | `#statistics`: WebView provider top-level préchargée, sinon navigateur | Couvert | `frontend/e2e/statistics.spec.ts` | Aucune iframe tierce |
| Statistiques en direct | Lien de partie généré côté backend | `#live`, `preferred_hotkey_site`, Alt+P | Couvert | `tests/test_api.py`, `tests/test_desktop.py`, `frontend/e2e/statistics.spec.ts` | WebView provider top-level; navigateur en fallback |
| Historique / effacement | Journal local et suppression confirmée | Table History + filtres + recherche + confirmation | Couvert | `tests/test_history.py`, `frontend/e2e/settings.spec.ts` | Conserver |
| Tray, show/hide, Settings, quit | Contrôles natifs | `src/desktop/tray.py` + bridge | Couvert | `tests/test_desktop.py` | Conserver |
| Toggle presets / Auto-Ban | Menu tray persistant | API Settings | Couvert | `tests/test_desktop.py` | Conserver |
| Hotkeys show/hide et stats | Raccourcis globaux | HotkeyManager, Alt+P ouvre `#live` dans la fenêtre native | Couvert | `tests/test_desktop.py` | Conserver |
| Dark / Light | Thème persistant | Appearance Settings | Couvert | `tests/test_api.py` | Harmoniser tokens |
| Auto-hide connect / close LoL | Effets de transition LCU | `ApplicationContext` | Couvert | `tests/test_context.py` | Ajouter cas UI natif |
| GitHub updates | Vérification différée et ignorée | Query updates 7 s après le premier rendu, puis toutes les 6 h | Couvert | `frontend/e2e/dashboard-disconnected.spec.ts`, `tests/test_api.py` | Conserver |
| Assets, icônes, cache | Cache local et ressources bundle | Routes assets | Couvert | `tests/test_api.py` | Conserver |
| Données statiques locales | LCU local puis snapshot persistant, Data Dragon en secours | `LcuStaticDataService`, `LcuAssetService`, `/api/game-data/status` | Couvert par fake LCU | `tests/test_lcu_static_data.py`, `tests/test_lcu_assets.py`, `tests/test_lcu_api_routes.py` | Catalogue chargé à la demande; refresh après connexion en arrière-plan |
| Diagnostics LCU | Flux/runtime unique, tests GET prédéfinis mémorisés, payload JSON dans le drawer, export redacted | Réglages > Avancé > `#diagnostics` | Couvert par fake LCU | `tests/test_lcu_diagnostics.py`, `frontend/e2e/diagnostics.spec.ts` | Aucun proxy ou endpoint de méthode arbitraire; résultat disponible après navigation et inclus à l'export |
| Instance unique / format des réglages | Lockfile et paramètres TOML | Launcher WebView; schéma 6 strict, création au premier lancement, aucune migration d'ancien schéma | Couvert | `tests/test_config.py`, `tests/test_api.py` | Ancien schéma sauvegardé en `.bak`, puis remplacé par les défauts |
| Fenêtre redimensionnable | Taille native persistée | `WebViewWindow`, restauration position/taille/maximisation et validation multi-écran | Couvert localement | `tests/test_desktop.py`, `tests/test_config.py` | Vérifier sur plusieurs écrans réels |

`presets_enabled` est le master gate des automatisations des presets, sans effacer les préférences Auto-Pick, Auto-Ban, Auto-Summs ou Auto-Skin. Les pages de runes restent configurées par slot, avec `rune_page_id = 0` pour conserver la page active. Auto-Accept et Auto Play Again restent indépendants. Dashboard, Presets et menu tray partagent ce même réglage. Factory reset rétablit les starter presets modifiables (Garen, Lux, Ashe et ban Teemo) et laisse toutes les automatisations désactivées. « Restaurer les presets d'exemple » remet ces choix et coupe le master en conservant les autres préférences. « Effacer uniquement les presets » vide picks et ban sans changer les réglages généraux ni les automatisations.

## Règle de validation

Toute nouvelle fonctionnalité visible doit avoir une entrée ici, un test ciblé et une vérification E2E si elle traverse le shell. Les tests locaux prouvent la logique et le contrat HTTP, pas la disponibilité réelle du client League ni le comportement d’un WebView2 installé sur chaque machine.

## Identity and reliability additions

The account and region parity path now has one normalized resolver and `/api/account/identity`. Diagnostics expose the tuple source without secrets, Live explains when a saved profile is shown while League is closed, and update checks run 7 seconds after mount then every 6 hours after each completed check. Runtime status tones are explicit: role and game-mode notices are informational, while success is reserved for completed actions.
