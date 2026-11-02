# FAT Studio — démarrer ou reprendre avec Codex

Ce dossier contient le projet complet et les éléments nécessaires pour le reprendre sans l'historique de la conversation ChatGPT.

## Pour Tai : trois étapes

1. Extraire **tout** le ZIP et ouvrir le dossier `fat-studio` dans Codex, ou donner accès à ce dossier à l'agent de code utilisé.
2. Copier le contenu de [docs/codex/PROMPT_CODEX.md](docs/codex/PROMPT_CODEX.md) dans une nouvelle conversation Codex.
3. Laisser Codex lire [l'état de reprise](docs/codex/ETAT_REPRISE.md), vérifier le poste et continuer le travail depuis l'existant. Le prompt lui demande de conserver le kit intact et de créer une copie source avant de modifier des fichiers couverts par son manifeste.

**Après une interruption ou dans une nouvelle conversation**, utiliser [docs/codex/PROMPT_REPRISE_CODEX.md](docs/codex/PROMPT_REPRISE_CODEX.md). Il demande de relire l'état réel des fichiers, les commits et la dernière note de session avant de poursuivre.

**Sur le PC Windows équipé de Siemens**, utiliser le [prompt de validation TIA V20/V21](docs/codex/PROMPT_VALIDATION_WINDOWS_TIA_V20_V21.md). Il reprend la référence 0.2.1 et conduit les builds natifs, les essais Openness/MCP et la qualification sur instance virtuelle, avec des résultats distincts pour chaque version.

## Contenu de l'archive initiale 0.1.1

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

L'application actuelle est **0.2.1** : [choix V20/V21 et profils d'ingénierie](docs/TIA_VERSIONS.md), puis correctif d'encodage Windows. Les tags `v0.1.1` et `v0.1.1-codex-handoff` conservent la référence et la passation initiales ; l'état courant figure dans [ETAT_REPRISE.md](docs/codex/ETAT_REPRISE.md). Les résultats de référence ci-dessous décrivent 0.1.1 ; les nouveaux résultats sont enregistrés séparément.

## Essayer directement la démonstration

Sous Windows avec **Python 3.12 x64**, lancer `Start-FAT.cmd`. Node.js n'est pas requis pour l'interface précompilée. Le kit contient les dépendances Python du runtime ; il ne contient pas l'interpréteur Python, Siemens, .NET, le serveur MCP TIA, les dépendances de développement npm ou le navigateur Playwright.

Sous macOS/Linux, ou pour développer, utiliser une copie source sans les wheels Windows. Depuis le dossier extrait, avec Git installé :

```text
git clone FAT-Studio.bundle ../fat-studio-source
```

Choisir un autre nom si cette destination existe déjà. Ouvrir ensuite `fat-studio-source` dans Codex. Le clone conserve les sources, les prompts, les preuves et les tags ; son éventuel remote `origin` désigne le **bundle local**, pas un dépôt GitHub. Les dépendances de développement s'installent selon [ETAT_REPRISE.md](docs/codex/ETAT_REPRISE.md).

## État de validation transmis

La référence 0.1.1 a obtenu **289 tests Python**, **31 tests frontend/API cliente** et **12 assertions de démonstration réussis**, ainsi que deux installations propres sous Linux. À cette remise initiale, les scripts Windows n'avaient pas été exécutés et aucun dépôt GitHub n'avait été publié. Voir [VERIFICATION.md](evidence/VERIFICATION.md).

La reprise 0.2.1 est publiée dans le dépôt privé [vandervan0001/FAT-Studio](https://github.com/vandervan0001/FAT-Studio). Sa CI a réussi **418 tests Python et 33 tests frontend sur chacun des systèmes Windows et Ubuntu**, puis l'installation d'un kit runtime Windows neuf sans index pip. Les [preuves datées](evidence/reprises/2026-11-02-windows-ci/VERIFICATION.md) identifient le commit testé. Le portage natif V20 et la qualification TIA/PLCSIM des deux versions restent à effectuer sur le poste Siemens.

Le ZIP contient le logiciel et ses exemples. Les projets et essais personnels déjà créés sur un autre poste, les licences, les certificats, les secrets et un vrai projet TIA utilisateur ne sont pas dans cette archive.
