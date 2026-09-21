# Refactor Dashboard presets

## État

- [x] Auditer le routing, le Dashboard, l’orchestration Presets, les pickers, les tests et les contrats backend.
- [x] Confirmer qu’aucune migration de settings ni changement backend n’est nécessaire.
- [x] Introduire les sous-routes `#dashboard`, `#dashboard/pick_1`, `#dashboard/pick_2`, `#dashboard/pick_3` et `#dashboard/ban`.
- [x] Extraire le workflow d’édition dans `PresetEditorFlow` et le monter au-dessus du Dashboard.
- [x] Rendre les cartes de priorité et le ban accessibles depuis le Dashboard avec restauration du focus.
- [x] Supprimer la page Presets, sa navigation, ses tests et son code mort associé.
- [x] Mettre à jour Quick Actions, onboarding, textes actifs, styles et documentation.
- [x] Ajouter/transférer les tests de routing, édition, navigation, cache et accessibilité.
- [x] Exécuter la validation frontend, backend, E2E, diff et la revue finale indépendante.

## Contraintes

- Le métier `presets` backend, le format des settings et le schéma restent inchangés.
- Aucune route legacy `#presets` ni migration automatique n’est ajoutée.
- `frontend/` reste distinct de `website/`.
- Aucun commit ni push n’est effectué.

Le plan détaillé fourni pour ce chantier est archivé dans `docs/archive/2026-09-dashboard-presets-refactor-plan.md`.
