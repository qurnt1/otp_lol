# Matrice de vérification des réglages V2

La matrice couvre les réglages éditables par l’interface. Le test API vérifie le contrat PATCH, la normalisation, la persistance via le contexte et la valeur retournée. Les tests desktop couvrent les effets natifs qui nécessitent Windows. Les tests Playwright vérifient le chemin visible et le retour optimiste.

| Groupe | Réglages | Contrat automatisé | Effet vérifié |
|---|---|---|---|
| Général | `auto_hide_on_connect`, `close_app_on_lol_exit` | `test_settings_matrix_persists_every_frontend_editable_setting`, `test_transient_disconnect_never_closes_the_application`, `test_definitive_disconnect_keeps_application_open_while_league_process_exists`, `test_definitive_disconnect_closes_when_league_process_is_gone` | Transition déconnecté → connecté, puis fermeture seulement après vérification que le processus League est absent; une déconnexion transitoire ne ferme jamais l'application |
| Automatisations | `presets_enabled`, `auto_accept_enabled`, `auto_pick_enabled`, `auto_ban_enabled`, `auto_summoners_enabled`, `skin_automation_enabled`, `auto_play_again_enabled`, `pick_slots[slot].rune_page_id` | tests API, `tests/test_core_champ_select.py`, `tests/test_desktop.py`, `frontend/e2e/presets.spec.ts`, `frontend/e2e/settings.spec.ts` | Le master gate pick/ban/sorts/runes/skins sans écraser les préférences enfants; Auto-Accept et Auto Play Again restent indépendants; `rune_page_id = 0` conserve la page active; les champs legacy ne sont pas interprétés |
| Compte | `summoner_name_auto_detect`, `manual_summoner_name`, `manual_region`, tuple local `auto_detected_*` | `tests/test_api.py`, `tests/test_context.py`, `tests/test_integration_lcu.py`, `tests/test_desktop.py`, `frontend/e2e/settings.spec.ts` | Auto utilise l’identité LCU complète puis le dernier tuple validé hors ligne; mode manuel prioritaire; ID/région/plateforme persistés atomiquement, copie et oubli explicites |
| Liens | `preferred_stats_site`, `preferred_hotkey_site` | matrice API, tests URLs/API, `frontend/e2e/statistics.spec.ts` | `preferred_stats_site` ne rafraîchit que `#statistics`; `preferred_hotkey_site` ne rafraîchit que `#live`; reset/import invalident les deux |
| Raccourcis | `hotkey_toggle_window`, `hotkey_open_site` | matrice API, tests hotkeys desktop | Reconfiguration après l’événement `settings_updated` |
| Apparence | `theme` | matrice API, E2E Settings | Tokens sombre/clair appliqués immédiatement |
| Skin | `pick_slots[slot].skin_mode`, `skin_automation_enabled` | `test_skin_modes`, matrice API, tests core et E2E Dashboard | Modes `none`, `fixed`, `random` identiques entre Dashboard et Presets; aucun mode `inherit` ni fallback de mode vers le slot 1 |
| Fenêtre | `window_x`, `window_y`, `window_width`, `window_height`, `window_maximized` | matrice API, tests desktop geometry | Taille, position valide, maximisation et sauvegarde à la fermeture |
| Presets | `presets_enabled`, `selected_pick_1..3`, `selected_ban`, `pick_slots` | tests preset/API/core dédiés, E2E presets/settings | First launch et factory reset fournissent Garen/Lux/Ashe, ban Teemo, automation OFF; le clear-presets séparé vide seulement les presets |
| Diagnostics | route `#diagnostics`, buffers LCU, résultats GET, payload drawer, export | `tests/test_lcu_diagnostics.py`, `frontend/e2e/diagnostics.spec.ts` | Page accessible depuis Réglages > Avancé, GET allowlist, résultats après reload et dans l'export, JSON uniquement dans Voir JSON, buffers bornés, export redacted par défaut |
| Maintenance | `ignored_update_version` | matrice API, test updates | Version ignorée respectée et vérification GitHub différée côté frontend |

Validation UI de référence : `npm run test:e2e`, dont `settings.spec.ts` vérifie un toggle immédiat et les scénarios de navigation/layout vérifient le shell. Les tests locaux ne prouvent pas la disponibilité réelle du client League ni le comportement de chaque backend WebView2.

Le fichier de réglages utilise le schéma 6. Le premier lancement crée et persiste les valeurs d'usine et les presets de départ; un schéma différent n'est pas migré, il est sauvegardé puis remplacé par cet état sûr. L'import exige aussi la version courante.

Les champs `auto_detected_*` sont locaux à l'installation, absents de l'export portable et ignorés à l'import. La réinitialisation complète les efface; les actions de reset/clear des seuls presets les conservent.

## Identity and maintenance checks

The account row also covers the positive automatic-detection label, source-aware account identity, platform/region consistency, and the saved-profile path while League is closed. Diagnostics covers the account identity card and redacted export. The maintenance row covers the recursive 7-second then 6-hour update scheduler.
