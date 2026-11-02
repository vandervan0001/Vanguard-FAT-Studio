# Validation locale macOS — 2 novembre 2026

FAT Studio **0.1.1** démarre sur ce poste macOS ARM64. Les 289 tests Python, les 31 tests frontend et les 12 assertions des trois scénarios de démonstration ont réussi. Une installation runtime neuve, sans accès aux index pip pendant l'installation, a aussi passé le contrôle du paquet installé et de sa persistance. Aucun défaut applicatif n'a été reproduit ; aucun fichier du runtime n'a été modifié.

## Référence et environnement

Le kit Windows a été extrait dans `fat-studio`, puis conservé intact. `scripts/check-kit.py::validate_kit` a contrôlé le manifeste, les empreintes et les 29 wheels avec la cible déclarée `Windows-x64`. Ce contrôle d'intégrité exécuté sur Mac ne vaut pas une installation Windows.

La copie de travail est un clone source du bundle, au commit de départ `486d8180508a014fe4791d19bc13b59ecdc61146`, sur la branche `codex/macos-validation`. Le runtime est celui de `v0.1.1` (`b271bba7cccb3dca1283ebfb4c301116b5df43f3`). Les nouveaux fichiers concernent la documentation et les preuves de cette reprise.

| Élément | Version observée |
| --- | --- |
| Système | macOS 26.3.1, ARM64 |
| Python de test | 3.12.12 |
| Node / npm | 25.1.0 / 11.6.2 |
| Playwright / Chromium de la suite | 1.56.1 / 141.0.7390.37, build 1194 |
| FastAPI / Pydantic / asyncua | 0.162.0 / 2.14.2 / 1.1.8 |

Détail : [environment.json](environment.json). Les environnements Python, dépendances npm, navigateurs et données d'essai sont exclus du dépôt.

## Contrôles exécutés

| Commande ou parcours | Résultat |
| --- | --- |
| `python3.12 -m venv .venv`, installation des trois verrous Python | Dépendances runtime, développement et MCP installées |
| `npm ci`, `npm run build` dans `frontend/` | Typage TypeScript et build Vite réussis ; avertissement de taille de chunk conservé |
| `.venv/bin/python scripts/build-web.py` | Assets intégrés ; aucun diff avec le bundle web de référence |
| Installation du paquet local et `pip check` | Aucune dépendance cassée |
| `.venv/bin/python -m ruff check fat_studio integrations tests scripts` | Réussi |
| `.venv/bin/python -m pytest --junitxml=evidence/reprises/2026-11-02-macos-arm64/pytest.xml` | 289 réussis, 0 échec, 0 erreur, 0 ignoré ; 85,26 s |
| `npm test` dans `frontend/` | 31 réussis, 0 échec, 0 ignoré, 0 flaky ; 53,1 s |
| Générateur de démonstration, sorties redirigées vers ce dossier | 3 scénarios, 12 assertions réussies ; verdicts humains `not_evaluated` |
| `bash scripts/start.sh --no-browser --data-dir …/demo-data` | Service prêt sur `127.0.0.1:8765` ; mode démonstration |
| `.venv/bin/python -m fat_studio doctor --json --data-dir …/demo-data` | Version 0.1.1, interface présente, dépendances présentes, 0 cible autorisée |
| `.venv/bin/python -m build --wheel --no-isolation` | Wheel construite ; ses 30 fichiers applicatifs correspondent aux sources et à la wheel originale |
| Seconde `.venv`, installation runtime par `pip --no-index --no-cache-dir` | 28 wheels de dépendances macOS et wheel applicative installées ; `pip check` réussi |
| `scripts/smoke-installed.py --python …/FAT installation épreuve/.venv/bin/python --output …/installed-check.json` | Réussi : 4 échantillons, exports et historique après redémarrage |

La suite frontend comprend 24 parcours navigateur et 7 tests du client API/formats TypeScript. Elle utilise un serveur et des données temporaires sur le port 8766, distincts du service laissé à Tai. Elle exerce notamment l'édition du vrai P&ID, la sauvegarde/relecture, le mapping CSV, les scénarios, les forçages, les conflits entre onglets et les erreurs réseau.

Le contrôle installé démarre son service hors du dépôt dans un dossier temporaire, lit les assets locaux, démarre et met en pause la démo, produit CSV/HTML/JSON, puis vérifie l'historique après arrêt, reset et redémarrage. L'import Python de ce second environnement vient bien de son `site-packages`, hors des sources.

L'interface a aussi été regardée dans le navigateur intégré à 1440 × 1000 : feuille CSS locale chargée, document visible, huit équipements dans une zone P&ID bornée de 972 × 708 px. Le réglage temporaire du viewport a ensuite été annulé. Cette observation ne qualifie pas tous les formats d'écran.

## Fichiers de preuve

- [pytest.xml](pytest.xml) et [frontend-tests.json](frontend-tests.json) : résultats complets des suites.
- [verification-summary.json](verification-summary.json) : comptes, verdicts et correspondance du contenu de la wheel.
- [doctor.json](doctor.json), [clean-install.json](clean-install.json) et [installed-check.json](installed-check.json) : diagnostic et installation neuve.
- [ui-observation.json](ui-observation.json) : observation de l'interface.
- [demo-scenarios.json](demo/evidence/demo-scenarios.json), [rapport HTML](demo/examples/reference-report.html) et [CSV](demo/examples/reference.csv) : nouveaux résultats du moteur livré.

Les preuves historiques, exemples et tags 0.1.1 n'ont pas été remplacés. Le générateur a été exécuté avec son répertoire de sortie déplacé dans ce dossier daté, sans modifier le script.

Une relecture indépendante a comparé le rapport aux cas JUnit, aux résultats frontend et démo, à la wheel et aux empreintes des assets. Aucun écart concret n'a été trouvé ; les liens relatifs des documents de reprise ont aussi été vérifiés.

## Reproduire les contrôles locaux

Depuis la copie source, avec les dépendances des trois fichiers de verrou installées :

```bash
(cd frontend && npm ci && npm run build)
.venv/bin/python scripts/build-web.py
.venv/bin/python -m pip install --no-deps --no-build-isolation .
.venv/bin/python -m pip check
.venv/bin/python -m ruff check fat_studio integrations tests scripts
.venv/bin/python -m pytest
(cd frontend && PLAYWRIGHT_SKIP_BROWSER_GC=1 npx playwright install chromium && npm test)
.venv/bin/python -m build --wheel --no-isolation
```

Choisir un nouveau dossier de preuves pour un nouveau run. Pour rejouer le générateur sans écraser les résultats historiques, depuis la racine du dépôt :

```python
import asyncio
from pathlib import Path
import runpy

root = Path.cwd()
output = root / "evidence" / "reprises" / "nouveau-run" / "demo"
(output / "evidence").mkdir(parents=True, exist_ok=False)
module = runpy.run_path(str(root / "scripts" / "generate-examples.py"))
module["main"].__globals__["ROOT"] = output
asyncio.run(module["main"]())
```

Pour le contrôle d'installation neuve, préparer un wheelhouse macOS depuis `requirements.lock`, créer une seconde `.venv`, installer ces wheels et la wheel applicative avec `--no-index --no-cache-dir`, puis exécuter `scripts/smoke-installed.py` en lui donnant le Python de cette seconde `.venv`. Ne pas résoudre son lien symbolique vers le Python système.

## Incident d'outillage résolu

L'installation Playwright a déclenché son nettoyage automatique du cache partagé et supprimé Chromium 1247, son headless 1247 et WebKit 2368, utilisés par un autre projet. Les trois révisions ont été restaurées, le lien de leur client réel réenregistré, puis les trois navigateurs lancés depuis ce client avec lecture d'un DOM témoin. Aucun autre dépôt n'a été modifié. Le rapport local détaillé reste dans `../work/2026-11-02-macos-reprise/playwright-cache-repair.json`, à partir du dossier `fat-studio-source`. Les commandes de reprise utilisent désormais `PLAYWRIGHT_SKIP_BROWSER_GC=1`.

## Qualifications encore ouvertes

PowerShell/Windows réel et premier lancement du kit Windows n'ont pas été exécutés ici. PowerShell et .NET ne sont pas disponibles dans le PATH de ce poste ; aucun environnement Siemens autorisé n'a été fourni pour cette reprise.

TIA Portal, PLCSIM Advanced, compilation/restauration d'un vrai projet, NodeIds, droits et certificats du serveur Siemens restent à vérifier suivant [ACCEPTANCE.md](../../../docs/ACCEPTANCE.md). Les tests OPC UA locaux et les doubles MCP ne constituent pas une qualification Siemens. Aucun téléchargement ou changement RUN/STOP CPU n'a été fait. Aucun verdict FAT humain n'est attribué par ces tests.

Aucune publication GitHub, exécution de CI distante ou nouvelle mesure de performance n'est revendiquée. Le remote `origin` reste le bundle local. La prochaine action est le premier lancement du kit intact sur un poste Windows x64 équipé de Python 3.12, puis le raccordement à une copie Siemens autorisée.
