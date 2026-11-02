# FAT Studio — état de reprise autonome

Passation initiale : **2 novembre 2026**. Ce document est destiné au prochain agent et à l'ingénieur qui reprend le projet. Les sections historiques ci-dessous décrivent la livraison ; inscrire les développements ultérieurs dans la section « État courant » et les notes de session.

## État courant — poste Windows local préparé, sans Siemens

Le 2 novembre 2026, le dépôt privé a été cloné intégralement dans `C:\FAT_Studio`, depuis `00ab08c`. Le travail local est sur `codex/windows-local-setup`. Python 3.12.10 x64, les dépendances runtime/dev/MCP, Node.js 22.23.4/npm 10.9.9 et le SDK .NET 10.0.403 sont disponibles. Le [guide de ce poste](../WINDOWS_LOCAL_SETUP.md) indique le lancement et l'environnement de développement local.

Vérifications réellement exécutées ici : **414 tests Python réussis et 4 ignorés** (création de liens symboliques refusée par Windows, erreur 1314), **33 tests frontend réussis** avec Node 22, TypeScript/Vite, Ruff et `pip check` réussis. Les 32 fichiers applicatifs de la wheel correspondent aux sources ; les 3 scénarios de démonstration passent leurs 12 assertions, avec verdict humain `not_evaluated`. L'interface a été démarrée, contrôlée visuellement, puis arrêtée. Les nouvelles [preuves Windows locales](../../evidence/reprises/2026-11-02-windows-local/VERIFICATION.md) restent distinctes des preuves historiques.

Un kit neuf de validation runtime/MCP a été créé dans `C:\FAT_Studio-Offline-Validation-2026-11-02`. Son premier `Start-FAT.cmd` a installé une `.venv` neuve et démarré le service avec index pip et cache pip désactivés. L'ajout MCP hors ligne et le manifeste de 43 wheels sont vérifiés. `pywin32==312` est maintenant épinglé pour Windows ; la résolution des trois locks confirme 54 dépendances toutes épinglées.

La source Czarnak épinglée reste propre dans `.tools/tia-upstream`. Le cache NuGet local contient 61 paquets, dont les références net48 et le paquet TiaMcpServer 4.3.0. Le worker et le host ont été restaurés dans un cache neuf avec cette seule source locale et `UseTiaPortalReferenceStubs=false`. **Aucune compilation TIA, installation de profil MCP ou qualification Siemens n'a été faite.** TIA Portal, Openness et PLCSIM manquent toujours.

Le premier contrôle `smoke-installed.py` a révélé un verrou SQLite au nettoyage temporaire. Le contrôle attend désormais la fin du vrai processus Python Windows via un handle acquis avant l'arrêt du redirecteur de `.venv`. Le nouveau test utilise un vrai worker avec SQLite ouverte. Les régressions ciblées passent (**18 réussies, 4 ignorées**, distinctes de la suite complète initiale). Les contrôles installés finaux passent contre la `.venv` source et celle du kit hors ligne : assets servis hors sources, exports CSV/HTML/JSON, historique après reset et relecture par un nouveau processus. Aucun contrôle d'assertion ou de nettoyage n'a été supprimé.

Aucun service de test n'est laissé actif. Le raccourci **FAT Studio** du bureau ou `Start-FAT.cmd` démarre l'application. Les données d'essais personnels restent hors du dépôt. Les outils locaux ignorés sont conservés dans `.tools/` et `.local/`. Les changements de cette mission sont conservés en commits locaux ; aucun push ni nouveau résultat GitHub Actions n'est revendiqué.

Prochaine action fonctionnelle : installer TIA Portal/Openness et PLCSIM, puis utiliser le [prompt de qualification Windows](PROMPT_VALIDATION_WINDOWS_TIA_V20_V21.md). Les sources, commandes et dépendances sont préparées ; les versions, DLL, licences et le vrai projet Siemens doivent encore être disponibles pour cette qualification.

Dernière note : [préparation locale Windows sans Siemens](sessions/2026-11-02-windows-local-setup.md).

Le correctif de livraison est commité sous `1f54282`. Le kit final neuf `C:\FAT_Studio-Offline-2026-11-02` contient le correctif du contrôle, les mêmes 32 fichiers applicatifs et 43 wheels ; son manifeste est vérifié. Le kit installé de validation reste distinct. La documentation et les preuves sont conservées dans le commit suivant sur la même branche.

## Historique — 0.2.1, choix V20/V21 et dépôt privé

La version actuelle est **0.2.1**. Dans **Connexion → Version du projet TIA**, l'utilisateur choisit V20 ou V21 ; le choix suit les sauvegardes, exports et imports. Les anciens projets utilisent V21. Le guide [TIA_VERSIONS.md](../TIA_VERSIONS.md) décrit les profils, prérequis et commandes propres à chaque version.

La [CI finale 41471993176](https://github.com/vandervan0001/FAT-Studio/actions/runs/41471993176), sur le code `b55bfded63dc5572da8d3409409210381cc50c34`, a réussi les deux jobs **Windows et Ubuntu**, avec **418 tests Python et 33 tests frontend par système**. Windows a aussi réussi la construction de wheel, le parsing PowerShell et l'installation d'un kit runtime neuf sans index pip. Le contrôle externe du paquet installé 0.2.1 valide les assets, la démo, les exports, l'historique après reset et le redémarrage. Voir les [preuves finales](../../evidence/reprises/2026-11-02-windows-ci/VERIFICATION.md).

Les deux corrections ayant permis cette validation sont documentées séparément : [encodage UTF-8 des sous-processus Windows](../../evidence/reprises/2026-11-02-windows-utf8/VERIFICATION.md), puis [délais mesurés du banc navigateur Windows](../../evidence/reprises/2026-11-02-windows-ui/VERIFICATION.md). Les assertions, traces et captures sont conservées, sans retry. Le tag 0.2.0 n'est pas déplacé.

V21 conserve le paquet Czarnak 4.3.0. V20 prépare un portage de la même source épinglée, à compiler sur Windows contre les trois DLL Openness V20 réellement installées. Les profils vérifient binaires, DLL, politique, proposition et archive ; ils conservent le dossier Openness aux lancements MCP et dans les fragments client. Le manifeste est obligatoire dans les deux cas. **Le build natif V20 et l'acceptation Siemens V20/V21 n'ont pas été exécutés sur ce Mac.** Une erreur native bloque l'installation, sans repli V21 ou références factices.

Contrôles locaux finaux : **418 tests Python et 33 tests frontend réussis**, build TypeScript/Vite et Ruff réussis, wheel dont les 32 fichiers applicatifs correspondent aux sources, contrôle du paquet installé 0.2.0 avec exports et persistance réussi. Les gardes, l'installation et la documentation ont fait l'objet de relectures indépendantes. Voir les [preuves 0.2.0](../../evidence/reprises/2026-11-02-v20-v21/VERIFICATION.md).

Le dépôt GitHub créé pour cette livraison est **privé** : [vandervan0001/FAT-Studio](https://github.com/vandervan0001/FAT-Studio). `origin` désigne ce dépôt ; `handoff` conserve le bundle local d'origine. Le code est poussé sur **main** ; le tag **v0.2.1** est préparé après cette CI, avec une dernière mise à jour documentaire des résultats. Vérifier les SHA distants à la reprise. Les tags 0.1.1 et 0.2.0 restent inchangés. La CI du runtime n'est pas une qualification Siemens.

**Serveur local arrêté à la demande de Tai**, par SIGINT envoyé au processus FAT identifié. Données de démonstration conservées dans `../work/2026-11-02-macos-reprise/demo-data`. Aucun service FAT persistant n'est requis à la reprise. La section macOS ci-dessous décrit le démarrage précédent et reste historique.

Prochaine action : ouvrir le dépôt sur le PC Windows équipé de Siemens et utiliser le [prompt de validation TIA V20/V21](PROMPT_VALIDATION_WINDOWS_TIA_V20_V21.md). Installer le profil de la version effectivement disponible, relever les diagnostics de compilation/doctor, puis qualifier une copie autorisée avec [ACCEPTANCE.md](../ACCEPTANCE.md). Ne pas transformer le statut du candidat V20 en compatibilité native acquise sans ces résultats.

Dernière note : [préparation de la reprise Windows TIA](sessions/2026-11-02-windows-tia-handoff.md). Les [preuves de livraison privée 0.2.1](sessions/2026-11-02-ci-private-delivery.md) et les notes [de délais Windows](sessions/2026-11-02-windows-ui.md), [d'encodage Windows](sessions/2026-11-02-windows-utf8.md) et [de sélection V20/V21](sessions/2026-11-02-v20-v21-private-git.md) restent conservées.

## Historique — reprise du 2 novembre 2026, macOS ARM64

Le kit extrait dans `../fat-studio` est resté intact ; ses empreintes et ses 29 wheels Windows ont été vérifiées. Le travail se poursuit dans le clone source `fat-studio-source`, branche `codex/macos-validation`, créé depuis le bundle au commit `486d8180508a014fe4791d19bc13b59ecdc61146`. Le runtime reste celui de la version **0.1.1** : les assets reconstruits et les 30 fichiers applicatifs de la wheel sont identiques à la référence.

Contrôles exécutés sur ce poste : **289 tests Python**, **31 tests frontend**, **3 scénarios et 12 assertions de démonstration** réussis ; Ruff et `pip check` réussis. Une seconde installation runtime dans une `.venv` neuve, depuis 28 wheels macOS et sans index pip ni cache pip, a passé `scripts/smoke-installed.py` : service hors sources, exports CSV/HTML/JSON, historique après reset et redémarrage. Les conclusions humaines restent `not_evaluated`. Aucun correctif du runtime n'a été nécessaire. Voir le [rapport et les preuves macOS](../../evidence/reprises/2026-11-02-macos-arm64/VERIFICATION.md).

Le service de démonstration est laissé actif sur **http://127.0.0.1:8765**, sans cible PLC autorisée. Ses données isolées sont dans `../work/2026-11-02-macos-reprise/demo-data`, hors du dépôt. Pour le redémarrer depuis la copie source si nécessaire :

```bash
bash scripts/start.sh --no-browser --data-dir "$PWD/../work/2026-11-02-macos-reprise/demo-data"
```

Vérifier d'abord si le service répond ; ne pas lancer une seconde instance sur le même port. La dernière note décrit le processus laissé actif et son arrêt. Le remote `origin` reste le bundle local du kit ; aucune publication GitHub ni exécution de CI distante n'a été faite.

**Prochaine qualification :** utiliser un poste Windows avec Python 3.12 x64 pour le premier lancement du kit intact et le contrôle installé, puis une copie TIA/PLCSIM autorisée pour [ACCEPTANCE.md](../ACCEPTANCE.md). TIA Portal, PLCSIM, .NET et PowerShell n'ont pas été exécutés ici. Les essais OPC UA locaux et les doubles MCP ne ferment pas cette qualification Siemens.

Dernière session : [validation macOS du 2 novembre 2026](sessions/2026-11-02-macos-validation.md).

## 1. État courant à la remise

| Point | État |
| --- | --- |
| Application | **FAT Studio 0.1.1**, code existant et interface compilée |
| Référence vérifiée | `b271bba7cccb3dca1283ebfb4c301116b5df43f3`, tag `v0.1.1` |
| Version précédente | `c18e0d439925155a91fbd1476c92be54f8a8cb06`, tag `v0.1.0` |
| Passation Codex | Tag `v0.1.1-codex-handoff` ; ajout documentaire, même runtime et même wheel |
| Branche livrée | `main` ; vérifier le HEAD courant avec `git log -1` |
| Git distant | Aucun dépôt GitHub créé ; aucun remote réseau dans l'archive |
| État d'exécution | Aucun processus applicatif requis ou laissé à reprendre dans ce ZIP |
| Prochaine action | Inspecter le poste, choisir kit intact ou copie source, reproduire le démarrage, puis fermer les qualifications accessibles |

Le ZIP final contient `.git` et `FAT-Studio.bundle`. Le bundle permet de recréer le dépôt si un outil d'extraction perd le dossier `.git`. Un clone depuis ce bundle peut avoir un `origin` local : ce n'est pas une publication GitHub. Le champ `git_commit` du manifeste identifie le commit de passation exact sans dépendre d'un chemin de la machine de création.

La connexion GitHub tentée précédemment a été refusée par Google dans le navigateur utilisé. Ce constat ne préjuge pas de l'authentification disponible sur le nouveau poste ; la vérifier normalement si une publication doit être faite.

## 2. Objectif et périmètre fonctionnel

Le besoin est un banc de FAT local avec P&ID interactif, modèles simples d'équipements, mapping PLC, scénarios, injections de défaut et preuves exportables. Le PLC réel ou virtuel fournit les commandes ; le banc calcule les entrées simulées et les lui renvoie. Le mode démonstration possède un contrôleur distinct pour essayer le produit sans Siemens.

Livré :

- sept types d'équipements, éditeur React Flow, propriétés et associations de tags ;
- cuve, pompe, vannes TOR/modulante, capteurs et indicateur, avec bilan volumique ;
- tags BOOL/INT/DINT/REAL, mapping CSV, projets et scénarios JSON ;
- démarrage, pause/reprise, arrêt/reset, forçages, défauts, marqueurs et assertions ;
- preuve SQLite par cycle, tendances, verdict humain et exports CSV/HTML/JSON ;
- adaptateur OPC UA avec politique de cible locale, identité, droits, types et chiffrement optionnel ;
- option TIA utilisant le serveur Czarnak existant, lecture seule côté IA et parcours humain pour les modifications ;
- lanceurs, kit runtime Windows, CI décrite, sources SCL et dossier de qualification.

Les connexions du dessin sont visuelles. Le calcul des circuits utilise explicitement cuve, sens et groupe de débit : minimum des capacités en série, somme des branches. Il ne faut pas annoncer un solveur hydraulique général, une simulation SIL ou une synchronisation déterministe avec le scan Siemens.

Documents de référence : [URS](../URS-original.md), [décisions](../URS-implementation.md), [matrice](../REQUIREMENTS_MATRIX.md), [FDS](../FDS.md), [contrat](../CONTRACT.md), [modèle](../MODEL.md).

## 3. Carte du dépôt

| Chemin | Responsabilité |
| --- | --- |
| `fat_studio/models.py`, `catalog.py`, `demo.py` | Schémas, validation, catalogue, exemple TK-101 |
| `fat_studio/engine.py` | Modèle physique et contrôleur de démonstration distinct |
| `fat_studio/runtime.py` | Cycle, scénarios, interventions, état et erreurs |
| `fat_studio/app.py` | API FastAPI locale, protections de contexte et interface servie |
| `fat_studio/adapters/` | Démonstration et échanges OPC UA |
| `fat_studio/storage.py`, `reporting.py`, `mapping.py` | Projets, SQLite, exports et CSV de mapping |
| `frontend/src/` | Application React, canevas, panneaux et client API |
| `fat_studio/web/` | Interface de production effectivement servie et incluse dans la wheel |
| `integrations/tia_engineering.py` | Orchestration du serveur MCP existant et du parcours humain |
| `integrations/upstream.lock.json` | Révisions, licences et choix de réutilisation |
| `scripts/` | Installation, build web, kit, benchmark, fixture OPC UA et contrôle du paquet installé |
| `tests/`, `frontend/tests/` | Tests Python et Playwright/TypeScript |
| `docs/`, `evidence/`, `examples/`, `siemens/` | Exigences, preuves, exports d'exemple et sources à adapter |

Réutilisation : React Flow, Recharts, asyncua, SDK MCP officiel, module de vanne HistorianSim attribué et Czarnak `TiaMcpServer 4.3.0`. Lire [UPSTREAM_REVIEW](../UPSTREAM_REVIEW.md) et les notices avant toute mise à jour. La révision Czarnak retenue est `10c5de2eb44c0362792cd141370b3f42f92f6ecd` ; les contrats d'une branche courante peuvent différer.

## 4. Preuves historiques et frontières non qualifiées

La référence 0.1.1 a obtenu :

| Contrôle | Résultat enregistré |
| --- | --- |
| Python | 289 réussis, 0 échec/erreur/ignoré, environ 128,4 s |
| Frontend/API cliente | 31 réussis : 24 parcours navigateur et 7 tests TypeScript, environ 44,4 s |
| Démonstration | 3 scénarios, 12 assertions réussies, verdict humain non évalué |
| Installation source | Nouvelle `.venv` par `start.sh`, dossier avec espaces/accents, 28 wheels Linux, index/cache pip désactivés |
| Installation wheel | Deuxième `.venv` neuve, paquet importé et servi hors du dépôt, exports et redémarrage vérifiés |
| Windows wheels | 29 fichiers et leurs contraintes inspectés sur Linux, sans exécution Windows |
| Charge | 50 équipements/200 tags, 1 000 cycles ; p95 modèle + SQLite 1,315 ms, hors OPC UA/Siemens/UI |

Environnement de ces preuves : Linux x86_64, Python 3.12.14, SQLite 3.53.1, Node 24.22.1 et Chromium 141/Playwright 1.56.1. Sources : [VERIFICATION](../../evidence/VERIFICATION.md), [JUnit](../../evidence/pytest.xml), [frontend](../../evidence/frontend-tests.json), [installation](../../evidence/linux-clean-install.json), [wheel](../../evidence/packaged-wheel.json), [benchmark](../../evidence/benchmark.json).

**Non exécuté à la passation :** PowerShell/Windows réel, TIA Portal, PLCSIM Advanced, compilateur Siemens, téléchargement/raccordement du vrai programme, restauration d'une archive TIA et CI GitHub distante. Les échanges asyncua locaux sont réels ; les opérations TIA utilisent des doubles de contrat. Pas d'endurance complète UI/PLC à 200 tags. Le détail des défauts reproduits et corrigés est dans [ADVERSARIAL_REVIEW](../ADVERSARIAL_REVIEW.md).

Les modifications de passation ajoutent des documents et corrigent deux explications du README frontend. Elles ne changent ni les fichiers Python du runtime, ni les assets, ni la wheel exécutée. Les résultats historiques restent attachés à leur référence ; aucun nouveau run de 289/31 tests n'est revendiqué pour ces seuls ajouts.

## 5. Préparer la bonne copie de travail

### Kit Windows pour exécuter

Le ZIP inclut un kit runtime **Python 3.12 x64 / Windows x64**. Garder `wheelhouse/` et `offline-manifest.json` ensemble. Les empreintes couvrent les fichiers distribués ; les modifier invalide le kit. Lancer `Start-FAT.cmd`, ou dans PowerShell depuis sa racine :

```powershell
.\scripts\setup.ps1
.\.venv\Scripts\python.exe -m fat_studio doctor --json
$FatDemoData = Join-Path $env:TEMP ("FAT-reprise-demo-" + [guid]::NewGuid().ToString("N"))
.\scripts\start.ps1 -NoBrowser -DataDir $FatDemoData
```

Utiliser un dossier de données neuf pour cet essai et arrêter le serveur avec Ctrl+C. `setup.ps1 -Python 'C:\chemin\python.exe'` permet de choisir un Python 3.12 x64. Les scripts respectent les politiques PowerShell du poste ; traiter un blocage d'entreprise selon sa procédure IT.

Le kit runtime ne contient pas pytest, le SDK MCP, npm, Playwright, Python, .NET ou Siemens. `setup.ps1 -Engineering` est refusé dans ce kit runtime : utiliser une copie source connectée ou un kit préparé avec cette option.

### Copie source pour développer, sous Windows/macOS/Linux

Depuis le kit, créer une destination sœur neuve, sans écraser une copie déjà commencée :

```text
git clone FAT-Studio.bundle ../fat-studio-source
```

Ouvrir ce nouveau dossier dans l'outil de code. Il contient les sources suivies par Git, les documents et les tags, sans wheelhouse, manifeste, `.venv`, `node_modules` ou wheel de distribution. Les installations ci-dessous requièrent un accès aux index approuvés, ou des dépendances préparées pour la plateforme réelle. Ne pas essayer d'installer des wheels Windows sur un Mac ou sous Linux.

## 6. Commandes de développement

À lancer depuis la racine de la **copie source**. Adapter les chemins si une `.venv` correcte existe déjà. Ne pas résoudre le lien symbolique du Python d'une `.venv` vers le Python système.

### Windows / PowerShell

Python 3.12 x64, Git et Node.js 22+ doivent être disponibles. Une erreur d'une commande doit être traitée avant la suivante ; les blocs ci-dessous ne sont pas un script autorisant à ignorer les codes de sortie.

```powershell
py -3.12 -m venv .venv
$FatPython = (Resolve-Path '.\.venv\Scripts\python.exe').Path
& $FatPython -m pip install -r requirements.lock -r requirements-dev.lock -r requirements-engineering.lock

Push-Location frontend
npm ci
npm run build
Pop-Location
& $FatPython scripts/build-web.py
& $FatPython -m pip install --no-deps --no-build-isolation .
& $FatPython -m pip check
& $FatPython -m fat_studio doctor --json
& $FatPython -m ruff check fat_studio integrations tests scripts
& $FatPython -m pytest

Push-Location frontend
$env:PLAYWRIGHT_SKIP_BROWSER_GC = '1'
npx playwright install chromium
npm test
Pop-Location
& $FatPython -m build --wheel --no-isolation
```

### Linux/macOS / Bash

Python 3.12, Git et Node.js 22+ doivent être disponibles. L'exécution macOS n'a pas été qualifiée lors de la livraison initiale.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock -r requirements-dev.lock -r requirements-engineering.lock
(cd frontend && npm ci && npm run build)
.venv/bin/python scripts/build-web.py
.venv/bin/python -m pip install --no-deps --no-build-isolation .
.venv/bin/python -m pip check
.venv/bin/python -m fat_studio doctor --json
.venv/bin/python -m ruff check fat_studio integrations tests scripts
.venv/bin/python -m pytest
(cd frontend && PLAYWRIGHT_SKIP_BROWSER_GC=1 npx playwright install chromium && npm test)
.venv/bin/python -m build --wheel --no-isolation
```

Sous Linux, si les bibliothèques système du navigateur manquent, l'installation CI utilise `npx playwright install --with-deps chromium` ; appliquer les permissions de la machine. Les tests E2E ont besoin d'ouvrir des sockets loopback et de lancer des sous-processus. Un environnement qui l'interdit doit être signalé, pas contourné par la désactivation des tests.

Sur un poste partagé, conserver `PLAYWRIGHT_SKIP_BROWSER_GC=1` lors de l'installation des navigateurs : le nettoyage automatique peut supprimer des builds utilisées par d'autres projets dont le lien de cache manque. Durant cette reprise, trois builds supprimées automatiquement ont été restaurées et lancées depuis leur client réel ; aucun autre dépôt n'a été modifié.

Les tests Playwright utilisent par défaut leur serveur temporaire sur 8766. `npm test` couvre toute la suite ; `npm run test:e2e` cible uniquement `workbench.spec.ts`. Ne pas définir `FAT_E2E_BASE_URL` vers une instance contenant des essais utilisateur. `FAT_E2E_PYTHON` permet de préciser le Python si nécessaire.

`start.sh` ne réinstalle pas systématiquement le paquet lorsqu'une `.venv` existe. Après une modification du code ou des assets, refaire l'installation du paquet avant de vérifier une distribution installée. La wheel doit embarquer les assets copiés par `build-web.py` ; effacer uniquement les sorties de build identifiées avant un nouveau build si des fichiers obsolètes s'y trouvent.

## 7. Ordre des travaux restants

| Priorité | Travail | Preuve attendue |
| --- | --- | --- |
| 1 | Inspecter poste/dépôt et démarrer la démonstration dans des données temporaires | Diagnostic, version, commandes, observations, erreurs éventuelles |
| 2 | Reproduire les contrôles nécessaires et corriger les défauts démontrés | Tests ciblés puis intégration adaptée au changement, bundle réel |
| 3 | Premier lancement Windows et kit sans index sur un environnement neuf | Résultat `smoke-installed.py`, dépendances, exports et persistance |
| 4 | Qualification Siemens sur une copie autorisée | Fiche `docs/ACCEPTANCE.md`, versions, NodeIds, types/droits, scénarios et rupture de communication |
| 5 | Option ingénierie si retenue | Czarnak 4.3.0 installé, lecture seule, export/diff, archive, confirmations, compilation et restauration réelles |
| 6 | Livraison et publication dans le périmètre autorisé | Commit/tag, archive complète, empreintes, URL/CI seulement si réellement obtenues |

La CI dans `.github/workflows/ci.yml` définit déjà les étapes Windows/Ubuntu, dont la préparation d'un kit neuf et le contrôle installé. Sur Windows, `scripts/prepare-offline.ps1 -Destination 'C:\chemin\neuf'` nécessite un poste connecté pour collecter les wheels ; l'installation du kit produit utilise ensuite `--no-index`. Prendre une destination neuve hors du dépôt.

Le contrôle suivant démarre et arrête des processus de test avec données temporaires et boucle locale ; il n'autorise aucune cible PLC :

```powershell
& $FatPython scripts/smoke-installed.py `
  --python 'C:\chemin\kit-neuf\.venv\Scripts\python.exe' `
  --output 'evidence\reprises\date-poste\installed-check.json'
```

Remplacer `date-poste` par l'identifiant réel de l'exécution. La qualification Siemens demande un vrai projet et les valeurs observées. Les NodeIds d'exemple ne sont pas une découverte de la CPU. Ne pas laisser une absence d'outils Siemens bloquer les tâches indépendantes.

## 8. Conserver les données, les preuves et les licences

Les données personnelles du banc sont normalement dans `%LOCALAPPDATA%\FATStudio`, `~/.fat-studio`, ou le dossier choisi par `FAT_STUDIO_DATA`/`--data-dir`. Copier ce dossier **serveur arrêté** pour sauvegarder les projets et SQLite. Le ZIP des sources ne contient pas les données de l'utilisateur.

Conserver les preuves de référence. Enregistrer les nouvelles dans `evidence/reprises/<date-poste>/`, avec OS, interpréteur, commit, état de travail si modifié, commande exacte et résultat. Les captures/traces brutes de test restent dans les dossiers ignorés ; sélectionner uniquement les preuves utiles sans données personnelles ni secrets.

Les clés et mots de passe ne vont ni dans Git ni dans les projets JSON exportés. Les modifications de la copie TIA suivent les confirmations existantes. Les licences, attributions et fichiers vendorisés doivent rester présents.

## 9. Construire une nouvelle archive complète

`prepare-offline.ps1` produit un **kit d'exécution** et copie les documents sous `docs/` ainsi que les README racine. Il ne produit pas à lui seul la passation complète : `.git`, `FAT-Studio.bundle` et `AGENTS.md` doivent être inclus explicitement dans un assemblage destiné au développement.

Pour une livraison complète : partir d'un état Git inspecté, conserver les prompts et l'état de reprise, reconstruire les assets et la wheel si le code change, préparer les bonnes wheels Windows, générer un bundle incluant les refs livrées, puis produire le manifeste **après** toutes les modifications. Vérifier le kit, le bundle, la cohérence des versions et l'intégrité du ZIP. Exclure les environnements, caches, secrets et données de travail.

Ne pas déplacer `v0.1.1`, qui identifie la référence déjà testée. Un changement applicatif ultérieur reçoit une version/tag appropriés et de nouvelles preuves. Les seuls ajouts documentaires de cette passation sont identifiés par `v0.1.1-codex-handoff`.

## 10. Journal des sessions et prochaine reprise

Dernière note : [2026-11-02, préparation locale Windows sans Siemens](sessions/2026-11-02-windows-local-setup.md). Les notes précédentes restent conservées. La prochaine qualification requiert les installations Siemens selon l'état courant en tête de ce document.

Dans la copie source, créer une note `docs/codex/sessions/<date-heure>-<sujet>.md` à chaque pause importante. Mettre à jour cette section avec un lien vers la dernière note. Utiliser ce format :

```text
Date UTC / poste / OS :
Objectif de la session :
Branche / HEAD / état Git :
Travail terminé :
Fichiers modifiés et changements non commités :
Commandes et tests réellement exécutés :
Preuves et chemins relatifs :
Processus laissés actifs / ports / arrêt :
Blocages précis et information manquante :
Prochaine action concrète :
Commandes ou conditions pour reprendre :
```

Une nouvelle conversation utilise [PROMPT_REPRISE_CODEX.md](PROMPT_REPRISE_CODEX.md). Les notes et l'état Git doivent suffire pour poursuivre sans dépendre d'un résumé oral de Tai.
