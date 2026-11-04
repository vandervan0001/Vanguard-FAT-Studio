# Vérification locale Windows du 2 novembre 2026

Source de départ : `00ab08c` dans le dépôt privé FAT-Studio. Les résultats portent sur cette base et les changements de livraison décrits ci-dessous, sur la branche locale `codex/windows-local-setup`. Le runtime applicatif et le frontend restent en 0.2.1. Les résultats historiques ne sont pas réattribués à ce poste.

## Plateforme et résultats

Windows 11 x64, build 26200, Python 3.12.10 x64. La première suite frontend a utilisé Node 24.22.1 fourni par Codex ; la seconde a utilisé le Node 22.23.4/npm 10.9.9 portable installé pour le projet. SDK .NET 10.0.403, runtimes 10.0.14. Voir [environment.json](environment.json), [node-install.json](node-install.json) et [dotnet-install.json](dotnet-install.json).

| Vérification réellement exécutée | Résultat | Preuve |
| --- | --- | --- |
| Suite Python complète | 414 réussis, 4 ignorés, aucun échec/erreur | [pytest.xml](pytest.xml) |
| Régressions après correctif du contrôle installé | 18 réussies, 4 ignorées ; exécution ciblée distincte | [pytest-installed-regression.xml](pytest-installed-regression.xml) |
| Liens symboliques Windows | 4 tests ignorés : privilège absent, WinError 1314 | Motifs détaillés dans le JUnit |
| Frontend complet sur Node 22 | 33 réussis, aucun flaky/retry | [frontend-tests.json](frontend-tests.json) |
| Ruff et `pip check` | Réussis | Commandes ci-dessous |
| TypeScript/Vite et intégration des assets | Réussis, bundle identique à la référence | [package-and-demo.json](package-and-demo.json) |
| Wheel | 32 fichiers applicatifs, noms et contenus identiques aux sources | [package-and-demo.json](package-and-demo.json) |
| Démonstration | 3 scénarios, 12 assertions réussies ; verdicts humains non évalués | [package-and-demo.json](package-and-demo.json) |
| Diagnostic | Dépendances présentes, interface prête, aucune cible autorisée | [doctor.json](doctor.json) |
| Premier lancement du kit neuf | Installation sans index/cache pip et service joignable en démo | [offline-first-launch.json](offline-first-launch.json) |
| Option Python MCP hors ligne | MCP 2.3.0 et pywin32 312 ; `pip check` et manifeste 43 wheels réussis | [offline-engineering-install.json](offline-engineering-install.json) |
| Contrôle installé depuis les sources | 5 contrôles réussis, nettoyage temporaire strict réussi | [source-installed-check.json](source-installed-check.json) |
| Contrôle installé depuis le kit | 5 contrôles réussis, dont historique après reset et nouveau processus | [offline-installed-check.json](offline-installed-check.json) |
| Kit final neuf | Manifeste vérifié, 43 wheels, 32 fichiers applicatifs identiques aux sources, contrôle corrigé inclus | [final-kit.json](final-kit.json) |
| NuGet worker net48 et host | Restauration dans un cache neuf depuis la seule source locale | [worker-offline-restore.log](worker-offline-restore.log), [host-offline-restore.log](host-offline-restore.log) |

Le [benchmark](benchmark.json) représente 50 équipements, 200 tags actifs et 1 000 cycles. Le p95 modèle + SQLite est de 2,849185 ms. Le réseau, OPC UA, Siemens, HTTP et le navigateur sont exclus de cette mesure.

L'[interface démarrée](demo-workbench.png) a été inspectée visuellement. Les suites navigateur ont utilisé leurs propres données temporaires. Aucun essai n'a été ajouté au dossier personnel `%LOCALAPPDATA%\FATStudio`.

## Dépendances et préparation de l'ingénierie

Les trois locks installés sont conservés dans le dépôt. `requirements-engineering.lock` ajoute `pywin32==312; sys_platform == "win32"` : le SDK MCP le demandait indirectement avec une borne basse, sans verrou Windows auparavant. Une résolution pip neuve des trois fichiers contient 54 paquets, chacun épinglé. Les versions installées sont dans [python-freeze.txt](python-freeze.txt).

La source Czarnak est au commit exact `10c5de2eb44c0362792cd141370b3f42f92f6ecd`. Les commandes `dotnet restore` ont conservé `UseTiaPortalReferenceStubs=false`. Elles ne compilent aucun serveur. Le [cache NuGet](nuget-cache.json) contient 61 paquets, dont les références net48 1.0.3 et le [paquet TiaMcpServer 4.3.0](tia-package.json). Son archive ne contient aucune DLL `Siemens.Engineering.*` ; aucun profil MCP vérifié n'est installé.

Les archives Node et .NET ont été téléchargées depuis leurs éditeurs, puis comparées aux empreintes des [releases Node](https://nodejs.org/dist/v22.23.4/SHASUMS256.txt) et des [métadonnées Microsoft .NET 10](https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json). Les rapports locaux enregistrent URL, version et empreinte réellement contrôlées. Le choix du SDK suit le `global.json` amont, qui exige une version stable 10.0.400 ou suivante.

## Commandes principales

Depuis `C:\FAT_Studio`, après création de `.venv` et installation de Node :

```powershell
. .\.local\dev-env.ps1
python -m pip install -r requirements.lock -r requirements-dev.lock -r requirements-engineering.lock
Push-Location frontend
npm.cmd ci --no-fund --no-audit
npm.cmd run build
Pop-Location
python scripts/build-web.py
python -m pip install --no-deps --no-build-isolation .
python -m pip check
python -m ruff check fat_studio integrations tests scripts
python -m pytest --junitxml=evidence/reprises/2026-11-02-windows-local/pytest.xml
Push-Location frontend
npx.cmd playwright install chromium
npm.cmd test
Pop-Location
python -m build --wheel --no-isolation
python evidence/reprises/2026-11-02-windows-local/reproduce-package-demo.py C:\FAT_Studio
```

`PLAYWRIGHT_SKIP_BROWSER_GC=1` a été conservé lors de l'installation de Chromium. Le helper de preuve exige sa racine source comme argument et utilise des données temporaires.

Le kit de validation a été créé avec `scripts/prepare-offline.ps1 -Engineering`. Son premier `Start-FAT.cmd -NoBrowser -Port 8767` a démarré sans `.venv` préexistante, avec `PIP_NO_INDEX=1`, `PIP_INDEX_URL=http://127.0.0.1:9` et `PIP_NO_CACHE_DIR=1`. L'option `scripts/setup.ps1 -Engineering` a ensuite été installée sous les mêmes conditions. Le service de test a été arrêté.

## Correctif du contrôle installé

Le premier `scripts/smoke-installed.py` sur ce poste a échoué au nettoyage temporaire : `PermissionError: [WinError 32]` sur `history.sqlite3`. Le contrôle attendait seulement le redirecteur de la `.venv`. Le [lanceur CPython 3.12.10](https://github.com/python/cpython/blob/v3.12.10/PC/launcher.c) place son enfant dans un job Windows ; attendre la fin du lanceur ne démontre pas encore la fin effective de cet enfant. La course observée est cohérente avec ce mécanisme.

Le bootstrap écrit désormais le PID réel avant le service. Le contrôle acquiert son handle Windows `SYNCHRONIZE`, puis attend sa fin après celle du lanceur, avec un délai borné et fermeture du handle dans tous les cas. Le nouveau test conserve une base SQLite ouverte dans un vrai Python et exige que son dossier soit immédiatement supprimable après l'arrêt. Les assertions applicatives, le nettoyage strict et la séparation hors sources restent présents.

Après cette correction, les régressions ciblées ont réussi, puis les contrôles installés complets ont réussi pour les deux environnements, sans verrou résiduel. Commandes finales :

```powershell
python -m pytest tests/test_installed_smoke.py tests/test_distribution.py `
  --junitxml=evidence/reprises/2026-11-02-windows-local/pytest-installed-regression.xml
python scripts/smoke-installed.py --python C:\FAT_Studio\.venv\Scripts\python.exe `
  --output evidence/reprises/2026-11-02-windows-local/source-installed-check.json
python scripts/smoke-installed.py `
  --python C:\FAT_Studio-Offline-Validation-2026-11-02\.venv\Scripts\python.exe `
  --output evidence/reprises/2026-11-02-windows-local/offline-installed-check.json
```

Les agents ont relu les frontières Windows, la préparation Siemens et le correctif. Aucune nouvelle exécution de la suite complète après l'ajout de ce test n'est revendiquée ; son résultat et celui des tests de distribution sont consignés séparément.

Le correctif est commité sous `1f54282`. Le kit final neuf est dans `C:\FAT_Studio-Offline-2026-11-02`, sans `.venv`, distinct du kit installé de validation. Sa vérification porte sur le manifeste et l'identité des fichiers livrés ; les contrôles d'installation réels décrits plus haut portent sur le kit de validation.

## Frontières

TIA Portal, Openness et PLCSIM sont absents. Aucun build natif V20, import, compilation Siemens, restauration d'archive TIA ou échange avec une CPU Siemens n'a été exécuté. Les tests OPC UA de la suite Python utilisent un serveur local générique. Aucune cible PLC, licence, identité ou validation FAT humaine n'a été inventée.
