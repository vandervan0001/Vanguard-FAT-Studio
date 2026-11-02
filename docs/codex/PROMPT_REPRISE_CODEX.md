# Prompt court — continuer après interruption

Reprends **FAT Studio** depuis le dossier de travail actuel. C'est la continuation du projet et de sa validation, pas un nouveau développement.

1. Lis `AGENTS.md`, `README-CODEX.md`, `docs/codex/ETAT_REPRISE.md`, puis les notes les plus récentes dans `docs/codex/sessions/`.
2. Vérifie l'OS, le répertoire courant, `git status`, le diff et les derniers commits. Les fichiers et commandes réellement exécutés priment sur un ancien résumé. Préserve mes changements, les essais et les données ; ne fais pas de reset ou de nettoyage destructif.
3. Si la copie contient un manifeste de livraison et des wheels, conserve-la intacte et utilise une copie source distincte. Si une copie source contient déjà le travail en cours, continue-la sans recommencer l'installation ou le projet inutilement.
4. Repère la dernière action terminée et la prochaine action documentée. Vérifie seulement les points nécessaires pour savoir où reprendre ; évite de répéter toute la revue si aucun changement ne le justifie.
5. Continue les corrections, tests, qualification et préparation de livraison encore autorisés. Exécute les tâches utiles au lieu de t'arrêter à un plan. Si un accès ou une décision manque, termine les tâches indépendantes et indique le blocage exact.
6. Distingue les preuves Linux/démo/protocole des essais Windows/Siemens. Conserve les confirmations du parcours TIA et les protections de cible. N'annonce aucune compilation réelle, publication GitHub ou réussite de CI sans observation.
7. Actualise l'état de reprise et ajoute une note datée avant une nouvelle interruption : changements, référence Git, commandes et résultats, blocages, prochaine étape et processus laissés actifs.

L'objectif complet est dans `docs/codex/PROMPT_CODEX.md`. Commence par un bref état factuel, puis reprends le travail à l'étape identifiée.
