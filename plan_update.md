## Constat vérifié

Le comportement actuel est explicite dans le code et les tests : en mode automatique, les liens Stats et En direct n’utilisent un compte que si League est connecté. Hors connexion, le résolveur renvoie un compte vide; un test vérifie précisément ce cas. [Résolution du compte]( /F:/Users/qurnt1/Documents/otp_lol/src/services/urls.py:125), [test API]( /F:/Users/qurnt1/Documents/otp_lol/tests/test_api.py:578)

Il existe déjà des champs `auto_detected_riot_id`, `auto_detected_region` et `auto_detected_platform`. League les met à jour en mémoire; l’application les sauvegarde lors de l’arrêt normal, mais pas immédiatement à chaque détection. Le résolveur et l’écran Compte ne les réutilisent toutefois pas hors connexion. [Détection LCU]( /F:/Users/qurnt1/Documents/otp_lol/src/core/websocket.py:665), [champ affiché dans les réglages]( /F:/Users/qurnt1/Documents/otp_lol/frontend/src/features/settings/SettingsPage.tsx:125)

Il faut distinguer deux choses :

- Les pages Stats et En direct affichent des fournisseurs externes. Avec un Riot ID et une région mémorisés, elles peuvent ouvrir le profil quand League est fermé, si Internet est disponible. Mais une page « En direct » ne peut pas afficher les données d’une partie qui n’a pas lieu.
- Le backend a aussi un cache local de statistiques hors ligne, indexé par une empreinte d’identité. Il peut retourner des résultats anciens, mais je n’ai trouvé aucun appel à ces routes dans le frontend : la page Stats actuelle est le panneau du fournisseur externe. [Cache hors ligne]( /F:/Users/qurnt1/Documents/otp_lol/src/lcu/account_stats.py:465), [page Stats actuelle]( /F:/Users/qurnt1/Documents/otp_lol/frontend/src/features/statistics/StatisticsPage.tsx:1)

Enfin, on ne peut pas retrouver un compte lors d’un tout premier lancement sans League, sans compte mémorisé et sans saisie manuelle. L’app devra alors guider l’utilisateur vers la saisie manuelle.

## Plan recommandé

1. **Fixer les règles de priorité du compte**
   - En mode automatique, utiliser le compte LCU actuel quand il est complet et valide.
   - Quand League est fermé, utiliser le dernier compte LCU enregistré.
   - En mode manuel, l’identifiant et la région manuels restent prioritaires, même si League est connecté.
   - Sans compte complet valide, ne pas fabriquer de lien de profil; proposer la configuration du compte.
   - Ne jamais combiner le Riot ID d’un compte avec la région d’un autre.

2. **Enregistrer proprement le dernier compte détecté**
   - Sauvegarder Riot ID, région et plateforme comme un seul ensemble cohérent, dès qu’une détection complète est validée.
   - Réutiliser les champs existants si possible, pour éviter une évolution du format des réglages.
   - Ne rien écraser avec une détection partielle ou invalide; ne pas modifier les valeurs manuelles.
   - N’enregistrer ni PUUID ni identifiants d’authentification.
   - Émettre un signal de changement quand le compte mémorisé change, afin de rafraîchir les deux pages.

3. **Centraliser la résolution utilisée par tous les liens**
   - Faire passer `/api/links/stats`, `/api/links/live` et l’ouverture de fenêtre fournisseur par le même résolveur.
   - Retourner la source du compte, par exemple `connecté`, `dernier compte` ou `manuel`, pour rendre son état visible dans l’interface.
   - Valider le Riot ID et la région après résolution, avant de générer le lien. Les deux routes utilisent déjà ce résolveur central, ce qui limite les changements dispersés. [Routes Stats/En direct]( /F:/Users/qurnt1/Documents/otp_lol/src/api/routes/runtime.py:251)

4. **Rendre l’état compréhensible dans Réglages > Compte**
   - En mode automatique, afficher le compte connecté, ou indiquer clairement « dernier compte enregistré, League fermé ».
   - Conserver le mode manuel existant pour remplacer le compte choisi.
   - Ajouter une action explicite pour recopier le dernier compte détecté dans les champs manuels, sans écraser une saisie existante en silence.
   - Ajouter une action pour oublier le dernier compte.
   - Si aucun compte n’a encore été détecté, afficher une consigne de configuration plutôt qu’un champ vide inexpliqué.

5. **Gérer l’import/export et la réinitialisation**
   - Aujourd’hui, l’export prend l’ensemble des paramètres, et l’import accepte aussi les champs `auto_detected_*`.
   - Décision à prendre avant implémentation : le dernier compte détecté doit-il suivre un fichier de réglages exporté? Je recommande de le garder local à cette installation, afin qu’un import ne remplace pas le compte déjà détecté sur le PC. Le compte saisi manuellement peut conserver le comportement actuel.
   - Définir si « Réinitialiser les réglages » efface aussi le dernier compte, et rendre cette conséquence explicite.

6. **Mettre à jour tests et documentation**
   - Modifier le test qui exige actuellement qu’un Riot ID mémorisé soit ignoré hors connexion, ainsi que les scénarios E2E associés.
   - Corriger la documentation qui décrit encore des comportements divergents : le mode auto sans secours hors connexion est aujourd’hui documenté comme attendu. Par ailleurs, `docs/architecture.md` présente une vue native de statistiques que le frontend ne semble pas utiliser; vérifier et harmoniser ces descriptions avec `docs/V2_PARITY.md`. [Matrice Settings]( /F:/Users/qurnt1/Documents/otp_lol/docs/SETTINGS_TEST_MATRIX.md:9), [parité V2]( /F:/Users/qurnt1/Documents/otp_lol/docs/V2_PARITY.md:19)

## Vérifications à prévoir

- Tests du résolveur pour les cas connecté, hors ligne avec compte mémorisé, mode manuel, compte absent, Riot ID invalide, région absente et changement de compte.
- Test de persistance réelle : détecter un compte, arrêter proprement, recréer le contexte, puis vérifier que Stats et En direct génèrent encore le bon profil sans League.
- Tests API et fenêtre fournisseur pour vérifier que les liens utilisent la même identité résolue.
- E2E des réglages : affichage du compte mémorisé hors ligne, remplacement manuel, copie du dernier compte, oubli du compte et rafraîchissement des pages après changement.
- Vérification manuelle : lancer OTP LOL avec League fermé et Internet disponible; vérifier l’ouverture du profil, puis connecter un autre compte et s’assurer que le nouveau devient le dernier mémorisé.
- Garder séparée une éventuelle fonctionnalité future de statistiques locales en cache : elle demanderait de brancher l’interface aux routes `/api/account/*` et d’indiquer que les données affichées sont anciennes.

## Autres points à corriger ou améliorer

- **Risque de région périmée :** les champs détectés sont mis à jour séparément, et la région n’est modifiée que si elle est présente. Une détection incomplète pourrait donc associer un nouveau Riot ID à une ancienne région. L’enregistrement atomique d’un compte complet règle ce risque.
- **État hors ligne invisible :** aujourd’hui, le réglage auto peut afficher un Riot ID vide alors qu’un compte précédent est présent dans les paramètres. Afficher la source et l’état évitera que « dernier compte » soit confondu avec « compte actuellement connecté ».
- **Première utilisation :** proposer la saisie manuelle du Riot ID et de la région si aucun compte n’a jamais été détecté.
- **Limite à annoncer :** mémoriser un compte permet d’ouvrir ses pages web lorsque League est fermé; cela ne garantit ni une connexion Internet ni des données de partie en direct.

Aucun code n’a été modifié. L’audit révèle aussi une branche et un worktree déjà fortement modifiés; si tu demandes ensuite l’implémentation, il faudra préserver ces changements existants.

Letzgo Quent