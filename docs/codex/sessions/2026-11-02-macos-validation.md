# Reprise et validation macOS — 2 novembre 2026

## Poste et référence

Session du 2 novembre 2026, macOS 26.3.1 ARM64, Python 3.12.12, Node 25.1.0. Clone source créé depuis `../fat-studio/FAT-Studio.bundle`, au commit `486d8180508a014fe4791d19bc13b59ecdc61146`, puis branche `codex/macos-validation`. Le kit extrait dans `../fat-studio` est resté intact ; manifeste et 29 wheels vérifiés.

## Travail terminé

Les exigences, la passation, les revues précédentes et les protocoles de qualification ont été lus, avec deux lectures indépendantes sur les exigences et les limites de validation. Le SDK MCP a été installé selon son verrou ; aucun serveur TIA réel n'a été lancé.

Les dépendances verrouillées ont été installées, le frontend reconstruit et recopié dans le paquet. Les assets sont identiques à la référence. Ruff et `pip check` passent ; **289 tests Python**, **31 tests frontend**, **3 scénarios et 12 assertions de démonstration** ont réussi. Les conclusions humaines restent `not_evaluated`.

Une nouvelle wheel a été construite. Ses 30 fichiers applicatifs correspondent aux sources et à la wheel originale. Une seconde `.venv`, dans un chemin avec espaces et accent, a été installée depuis 28 wheels de dépendances macOS et la wheel applicative, avec `--no-index --no-cache-dir`. `pip check` et `scripts/smoke-installed.py` passent : service hors sources, exports et historique après redémarrage. Les preuves sont dans [le dossier macOS](../../../evidence/reprises/2026-11-02-macos-arm64/VERIFICATION.md).

L'application a été ouverte et regardée dans le navigateur intégré. Le contrôle au format 1440 × 1000 a observé le CSS local et les huit équipements ; le viewport a ensuite été rétabli.

Une préparation via `economy-router` a été refusée avec `privacy_training_required`. Aucune préparation OpenRouter n'a été utilisée ; aucun repli payant ou assouplissement de confidentialité n'a été tenté.

L'installation Playwright 1.56.1 a purgé trois navigateurs d'un cache partagé. Les révisions exactes ont été restaurées et lancées depuis leur client réel ; aucun autre dépôt n'a été modifié. Les commandes de reprise conservent désormais `PLAYWRIGHT_SKIP_BROWSER_GC=1`. La règle globale R42 a reçu ce complément avec une copie préalable de sa source ; elle reste hors du dépôt FAT Studio.

## Fichiers et Git

Aucun changement du runtime, des verrous, des tests ou des exemples historiques. Modifications de `docs/INSTALLATION.md` et `docs/codex/ETAT_REPRISE.md`, ajout de cette note et de `evidence/reprises/2026-11-02-macos-arm64/`. Ces changements sont destinés au commit documentaire de cette session. Les environnements, données, logs de travail et dépendances restent hors Git. Vérifier `git status --short` et `git log -1` pour l'état exact après livraison.

La relecture indépendante de la livraison n'a trouvé aucun défaut concret : comptes JUnit/frontend, assertions et verdicts démo, contenu de la wheel, empreintes des assets et liens relatifs concordent avec le rapport. Aucune suite supplémentaire n'a été relancée pour cette seule relecture.

Le remote `origin` désigne toujours le bundle local du kit, sans publication réseau. Aucun dépôt GitHub ni résultat de CI distante n'a été créé.

## Processus et données

Le service FAT Studio est laissé actif sur **http://127.0.0.1:8765**, démarré par `bash scripts/start.sh --no-browser --data-dir …/demo-data` ; PID observé au démarrage : **87377**. Données dédiées : `../work/2026-11-02-macos-reprise/demo-data`. Il est en mode démonstration, initialement au repos, sans cible PLC autorisée. L'onglet du navigateur intégré est conservé comme accès à l'application.

Les processus des suites, les deux services temporaires du contrôle installé et les navigateurs de réparation ont été arrêtés. Le service utilisateur sur 8765 est le seul service FAT laissé actif. Ctrl+C dans son terminal l'arrête ; à défaut, vérifier d'abord le PID courant et sa commande, puis envoyer SIGINT à ce processus précis. Ne pas arrêter un processus sur le seul souvenir de ce PID.

## Blocages et prochaine action

Windows/PowerShell, TIA Portal, PLCSIM Advanced et un vrai projet Siemens autorisé n'ont pas été exécutés sur ce Mac. Les preuves de protocole OPC UA et les doubles MCP ne ferment pas ces qualifications. Aucun verdict humain FAT n'a été donné.

Sur le poste Windows x64 avec Python 3.12 : ouvrir le kit intact, lancer `Start-FAT.cmd`, puis suivre le contrôle installé de [ETAT_REPRISE.md](../ETAT_REPRISE.md). Sur une copie TIA/PLCSIM autorisée, poursuivre [ACCEPTANCE.md](../../ACCEPTANCE.md) et relever les versions, l'identité du serveur, les NodeIds, types et droits réels.

Pour reprendre seulement l'application locale, vérifier d'abord `http://127.0.0.1:8765/api/health`. Si elle est arrêtée, depuis `fat-studio-source` :

```bash
bash scripts/start.sh --no-browser --data-dir "$PWD/../work/2026-11-02-macos-reprise/demo-data"
```

Ne pas réinstaller ni relancer toutes les suites sans changement ou incertitude nouvelle. Les commandes et les résultats exécutés sont dans le [rapport de validation](../../../evidence/reprises/2026-11-02-macos-arm64/VERIFICATION.md).
