# Matrice de vérification des réglages V2

La matrice couvre les réglages éditables par l’interface. Le test API vérifie le contrat PATCH, la normalisation, la persistance via le contexte et la valeur retournée. Les tests desktop couvrent les effets natifs qui nécessitent Windows. Les tests Playwright vérifient le chemin visible et le retour optimiste.

| Groupe | Réglages | Contrat automatisé | Effet vérifié |
|---|---|---|---|
| Général | `auto_hide_on_connect`, `close_app_on_lol_exit` | `test_settings_matrix_persists_every_frontend_editable_setting`, `test_runtime_transition_hides_once_and_closes_only_after_a_real_connection` | Transition déconnecté → connecté, puis fermeture uniquement après une connexion réelle |
| Automatisations | `auto_accept_enabled`, `auto_pick_enabled`, `auto_ban_enabled`, `auto_summoners_enabled`, `auto_play_again_enabled` | matrice API, tests LCU existants | Accept, pick/ban, sorts/runes et retour lobby restent branchés au runtime |
| Compte | `summoner_name_auto_detect`, `manual_summoner_name`, `manual_region` | matrice API, validation Riot ID | RuntimeTopBar utilise la valeur manuelle quand la détection est désactivée |
| Liens | `preferred_stats_site`, `preferred_hotkey_site` | matrice API, tests URLs/API existants | URLs allowlistées et fournisseur choisi |
| Raccourcis | `hotkey_toggle_window`, `hotkey_open_site` | matrice API, tests hotkeys desktop | Reconfiguration après l’événement `settings_updated` |
| Apparence | `theme` | matrice API, E2E Settings | Tokens sombre/clair appliqués immédiatement |
| Skin principal | `main_skin_mode_override`, `main_skin_mode_overrides` | matrice API, tests skin modes/core | Modes `INHERIT`, `OFF`, `FIXED`, `RANDOM`, sans modifier le preset |
| Fenêtre | `window_x`, `window_y`, `window_width`, `window_height`, `window_maximized` | matrice API, tests desktop geometry | Taille, position valide, maximisation et sauvegarde à la fermeture |
| Presets | `presets_enabled`, `selected_pick_1..3`, `selected_ban`, `pick_slots` | tests preset/API/core dédiés | Parité des trois slots, fallback et invariants pick/ban |
| Maintenance | `ignored_update_version` | matrice API, test updates | Version ignorée respectée et vérification GitHub différée côté frontend |

Validation UI de référence : `npm run test:e2e`, dont `settings.spec.ts` vérifie un toggle immédiat et les scénarios de navigation/layout vérifient le shell. Les tests locaux ne prouvent pas la disponibilité réelle du client League ni le comportement de chaque backend WebView2.
