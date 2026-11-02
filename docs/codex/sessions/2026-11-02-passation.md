# Note initiale — passation Codex

Date : **2 novembre 2026**. Cette note décrit la préparation du ZIP de reprise, pas une qualification du poste de destination.

## Travail terminé

- Ajout de `README-CODEX.md`, `AGENTS.md`, du prompt initial, du prompt de continuation et de l'état détaillé de reprise.
- Commandes distinctes Windows/PowerShell et Linux/macOS/Bash ; distinction entre kit d'exécution vérifié et copie source à modifier.
- Priorités, frontières fonctionnelles, preuves historiques et qualifications Windows/Siemens non exécutées explicitement documentées.
- Correction documentaire du README frontend : le build npm est manuel et doit être copié dans `fat_studio/web` ; la commande `test:e2e` ne couvre que `workbench.spec.ts`.

## Référence Git et preuves

Le runtime reste celui de `v0.1.1`, commit `b271bba7cccb3dca1283ebfb4c301116b5df43f3`. La passation documentaire est identifiée par `v0.1.1-codex-handoff`, sur la branche `main`. Le manifeste du ZIP donne le commit de passation exact ; `git status` et `git log -1` permettent de contrôler la copie reçue.

Les fichiers d'exécution Python, les sources frontend, les assets, les scripts, les verrous et les tests n'ont pas changé par rapport à `v0.1.1`. La wheel est identique à celle enregistrée dans `evidence/packaged-wheel.json`. Les liens relatifs des documents de reprise et le diff documentaire ont été vérifiés. L'assemblage final contrôle le manifeste, le bundle Git et l'intégrité ZIP.

Aucun nouveau lancement des 289 tests Python ou des 31 tests frontend n'a été réalisé pour ces ajouts documentaires. Les résultats précédents et leurs conditions restent dans `evidence/VERIFICATION.md`.

## État à transmettre

Pas de travail applicatif non commité à reprendre dans l'archive, ni de processus dont le maintien serait nécessaire. Aucun projet TIA utilisateur, secret, licence ou dossier personnel d'essais n'est inclus. Aucun dépôt GitHub ou résultat de CI distante n'est présenté comme créé.

**Prochaine action :** inspecter le poste et l'état du dépôt, puis créer ou retrouver la copie source. Démarrer la démonstration dans des données temporaires avec l'interpréteur adapté. Exécuter ensuite les contrôles utiles au poste et les qualifications accessibles selon le tableau de `docs/codex/ETAT_REPRISE.md`.

À la fin de la prochaine session, ajouter une note datée et mettre à jour le lien vers la dernière note dans l'état de reprise, en conservant cette note initiale.
