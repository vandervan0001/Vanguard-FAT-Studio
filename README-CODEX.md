# FAT Studio — démarrer ou reprendre avec Codex

Ce dossier contient le projet complet et les éléments nécessaires pour le reprendre sans l'historique de la conversation ChatGPT.

## Pour Tai : trois étapes

1. Extraire **tout** le ZIP et ouvrir le dossier `fat-studio` dans Codex, ou donner accès à ce dossier à l'agent de code utilisé.
2. Copier le contenu de [docs/codex/PROMPT_CODEX.md](docs/codex/PROMPT_CODEX.md) dans une nouvelle conversation Codex.
3. Laisser Codex lire [l'état de reprise](docs/codex/ETAT_REPRISE.md), vérifier le poste et continuer le travail depuis l'existant. Le prompt lui demande de conserver le kit intact et de créer une copie source avant de modifier des fichiers couverts par son manifeste.

**Après une interruption ou dans une nouvelle conversation**, utiliser [docs/codex/PROMPT_REPRISE_CODEX.md](docs/codex/PROMPT_REPRISE_CODEX.md). Il demande de relire l'état réel des fichiers, les commits et la dernière note de session avant de poursuivre.

## Ce qui est inclus

| Élément | Emplacement |
| --- | --- |
| Prompt initial complet | `docs/codex/PROMPT_CODEX.md` |
| Prompt de reprise après interruption | `docs/codex/PROMPT_REPRISE_CODEX.md` |
| État initial, prochaines tâches et commandes Windows/Bash | `docs/codex/ETAT_REPRISE.md` |
| Consignes du dépôt pour les agents | `AGENTS.md` |
| Code, frontend et interface compilée | `fat_studio/`, `integrations/`, `frontend/` |
| Tests et preuves de la version 0.1.1 | `tests/`, `frontend/tests/`, `evidence/` |
| Historique Git et sauvegarde autonome | `.git/` et `FAT-Studio.bundle` dans le ZIP |
| Exécution Windows hors ligne | `Start-FAT.cmd`, `wheelhouse/`, `offline-manifest.json` |
| Paquet Python compilé | `dist/local_fat_studio-0.1.1-py3-none-any.whl` |

L'application reste **0.1.1**. Le tag `v0.1.1` désigne le code vérifié ; `v0.1.1-codex-handoff` ajoute cette passation documentaire. Aucun code d'exécution n'a été changé pour ajouter les prompts.

## Essayer directement la démonstration

Sous Windows avec **Python 3.12 x64**, lancer `Start-FAT.cmd`. Node.js n'est pas requis pour l'interface précompilée. Le kit contient les dépendances Python du runtime ; il ne contient pas l'interpréteur Python, Siemens, .NET, le serveur MCP TIA, les dépendances de développement npm ou le navigateur Playwright.

Sous macOS/Linux, ou pour développer, utiliser une copie source sans les wheels Windows. Depuis le dossier extrait, avec Git installé :

```text
git clone FAT-Studio.bundle ../fat-studio-source
```

Choisir un autre nom si cette destination existe déjà. Ouvrir ensuite `fat-studio-source` dans Codex. Le clone conserve les sources, les prompts, les preuves et les tags ; son éventuel remote `origin` désigne le **bundle local**, pas un dépôt GitHub. Les dépendances de développement s'installent selon [ETAT_REPRISE.md](docs/codex/ETAT_REPRISE.md).

## État de validation transmis

La référence 0.1.1 a obtenu **289 tests Python**, **31 tests frontend/API cliente** et **12 assertions de démonstration réussis**, ainsi que deux installations propres sous Linux. Les scripts Windows, TIA Portal et PLCSIM Advanced restent à qualifier sur le poste cible. La publication GitHub n'a pas été réalisée. Voir [VERIFICATION.md](evidence/VERIFICATION.md).

Le ZIP contient le logiciel et ses exemples. Les projets et essais personnels déjà créés sur un autre poste, les licences, les certificats, les secrets et un vrai projet TIA utilisateur ne sont pas dans cette archive.
