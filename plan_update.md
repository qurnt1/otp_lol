# Plan actif

## Compte, region et routage

- [x] Normaliser Riot ID, plateforme, region fournisseur et routage regional.
- [x] Persister uniquement les tuples complets et emettre un evenement lors d'un changement.
- [x] Exposer `/api/account/identity` et reutiliser le resolveur pour les liens Stats, Live et les donnees de compte.
- [x] Inverser le libelle du reglage en Détection automatique du compte.

## Fiabilite et interface

- [x] Ajouter l'identite au panneau Diagnostics sans secret par defaut.
- [x] Rendre les tons de statut explicites, avec ROLE et GAMEMODE informatifs.
- [x] Planifier le controle de mise a jour a 7 s puis toutes les 6 h apres chaque controle.
- [x] Afficher l'etat hors ligne du profil sauvegarde dans En direct.
- [x] Employer Fermer lorsque League est reellement ferme.

## Validation restante

- [x] Tests unitaires, API, frontend et E2E locaux.
- [ ] Verification native Windows avec League Client reel, WebView2 et scaling materiel.
- [x] Revue independante finale du diff et des limites de validation.

Le plan detaille est archive dans `docs/archive/2026-09-account-and-reliability-implementation.md`.
