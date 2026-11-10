# Installer et démarrer Vanguard FAT Studio

## Portable Windows x64 : démarrage sans installation

Le portable contient Python officiel **3.12.10 x64**, les dépendances verrouillées, l’application et son interface compilée. Il ne demande ni Python ou Node.js global, ni droits administrateur, ni connexion Internet pour démarrer. Siemens reste une installation distincte, nécessaire uniquement aux essais qui l’utilisent.

`Vanguard-FAT-Studio.cmd` est un second nom pour `Start-FAT.cmd`. Les deux lanceurs utilisent les mêmes options et les mêmes données.

1. Extraire **toute** l’archive portable dans un dossier local, par exemple `C:\FAT\Vanguard-FAT-Studio`.
2. Garder ensemble `Start-FAT.cmd`, `runtime/`, `app/`, `scripts/` et `portable-manifest.json`.
3. Double-cliquer **Start-FAT.cmd**. La fenêtre du lanceur affiche la vérification puis l’état **Prêt** ; le navigateur s’ouvre automatiquement.
4. Utiliser **Ouvrir FAT Studio** pour retrouver l’interface. Un second double-clic retrouve le service du même portable et du même dossier.
5. Utiliser **Quitter** dans le lanceur pour fermer le service. Fermer seulement l’onglet ne termine pas un essai en cours. Les lancements avec des arguments explicites gardent une console et l’arrêt par `Ctrl+C`.

Les données sont stockées par défaut dans `%LOCALAPPDATA%\FATStudio`, **hors du runtime**. Une mise à jour s’installe dans un nouveau dossier et réutilise les mêmes données. L’ancien portable reste intact. Conserver une [archive de projet](PROJECT_ARCHIVES.md) avant toute mise à jour. Le [guide du lanceur](PORTABLE_LAUNCHER.md) décrit sa fenêtre et la mise à jour guidée.

Dans PowerShell, depuis le dossier du portable :

```powershell
.\Start-FAT.cmd --check
.\Start-FAT.cmd --port 8767 --no-browser
.\Start-FAT.cmd --data-dir 'D:\FAT\Mon projet' --port 8767
.\runtime\python.exe -B -X utf8 -m fat_studio doctor --json
```

Un `--data-dir` situé dans le runtime portable est refusé par son lanceur. Choisir un dossier de projet indépendant. Pour le client IA, utiliser `runtime\python.exe` et placer le contexte et les exports dans un autre dossier ; lire [AI_QUICKSTART.md](AI_QUICKSTART.md).

Le runtime utilise un fichier Python `._pth` isolé : il ne dépend ni du Python global, ni de `PYTHONPATH`, ni des paquets d’un autre utilisateur. Ne pas modifier ce fichier ou installer des paquets dans le portable. Le manifeste repère les fichiers modifiés ou ajoutés ; il ne remplace pas la confiance dans la provenance du ZIP. En cas d’erreur d’intégrité, conserver les données et réextraire une livraison complète dans un nouveau dossier.

Python 3.12.10 est épinglé pour reproduire cette livraison ; ce n’est pas une promesse de dernière version de sécurité disponible. Son remplacement demande une nouvelle construction et ses contrôles. Le SHA-256 de l’archive, la provenance officielle et la licence PSF sont conservés dans `portable-python.lock.json` et `runtime/LICENSE.txt`.

## Depuis les sources : Python 3.12

La distribution source et le kit source hors ligne utilisent un Python **3.12 x64 déjà installé**. L’interface compilée est fournie ; Node.js ne sert qu’au développement.

Le nom du paquet est `vanguard-fat-studio`. Après installation, `vanguard-fat-studio --help` et `fat-studio --help` ouvrent le même CLI ; `python -m fat_studio` reste disponible. Le nom de marque ne change ni `%LOCALAPPDATA%\FATStudio`, ni `~/.fat-studio`, ni `FAT_STUDIO_DATA`, ni le contenu des archives déjà créées.

1. Installer Python 3.12 x64 selon la politique de votre poste.
2. Extraire la copie source complète dans un dossier accessible en écriture.
3. Double-cliquer **Start-FAT.cmd**. Le premier lancement crée `.venv`, installe les versions verrouillées et ouvre le banc sur le port 8765.

```powershell
.\scripts\setup.ps1
.\scripts\setup.ps1 -Python 'C:\Python312\python.exe'
.\scripts\start.ps1 -Port 8767 -NoBrowser
.\scripts\start.ps1 -DataDir 'D:\FAT\Mon projet'
.\scripts\start.ps1 -Repair
.\.venv\Scripts\python.exe -m fat_studio doctor --json
```

Le lanceur source utilise PowerShell avec `RemoteSigned` limité au processus et respecte les stratégies imposées par l’organisation. Si Windows bloque un fichier téléchargé, contrôler sa provenance et utiliser la procédure de déblocage approuvée sur le poste. Aucun changement global de politique, UAC ou pare-feu n’est effectué par ce lanceur.

Le kit source contient `wheelhouse/` et `offline-manifest.json`. `scripts/check-kit.py` vérifie interpréteur, plateforme, chemins, doublons et empreintes avant pip. L’installation utilise `--no-index` et ne se rabat pas sur Internet si une wheel manque. Une copie source sans wheelhouse nécessite PyPI pour sa première installation.

Sous Linux/macOS, utiliser une copie source sans les wheels Windows, avec Python 3.12 :

```bash
bash scripts/start.sh --no-browser --port 8767
.venv/bin/python -m fat_studio doctor --json
```

## Dossiers de projets et sauvegardes

| Emplacement | Contenu |
| --- | --- |
| Dossier de données actif | Projets JSON, SQLite d’essais et références locales |
| `%LOCALAPPDATA%\FATStudio` | Racine par défaut sous Windows |
| `~/.fat-studio` | Racine par défaut sous Linux/macOS |
| `--data-dir` ou `FAT_STUDIO_DATA` | Choix explicite du dossier de données |
| Archive `.fat.zip` | Configuration et preuves du seul projet sélectionné |

Un serveur détient un verrou sur le dossier de données ; deux serveurs ne peuvent pas l’utiliser simultanément. Le logiciel permet d’ouvrir des dossiers FAT locaux et de restaurer une archive dans un **nouveau** dossier, au repos. Les autorisations de cible restent indépendantes des projets importés. Lire [PROJECT_ARCHIVES.md](PROJECT_ARCHIVES.md) et [FORMAT.md](FORMAT.md).

Une sauvegarde brute du dossier de données nécessite l’arrêt du serveur pour copier SQLite proprement. Elle peut contenir plusieurs projets et des références propres au poste. Pour transmettre un projet, privilégier l’archive sélectionnée, relue avant partage. Ne pas mettre historique SQLite, secrets ou clés privées dans le dépôt public du logiciel.

## Construire un portable pour distribution

Cette étape concerne le développeur sur **Windows x64 avec Python 3.12**. Partir d’une wheel publique construite après le gel du code, de l’interface et des documents. Le constructeur refuse une destination existante ou située dans les sources.

```powershell
.\.venv\Scripts\python.exe public_distribution.py check
.\.venv\Scripts\python.exe -m build --wheel --no-isolation
.\.venv\Scripts\python.exe public_distribution.py check-wheel dist\vanguard_fat_studio-0.4.0-py3-none-any.whl
.\.venv\Scripts\python.exe -m pip download --disable-pip-version-check --only-binary=:all: --no-deps --dest D:\FAT-Build\wheels -r requirements.lock
.\.venv\Scripts\python.exe scripts/build-portable.py --wheel dist\vanguard_fat_studio-0.4.0-py3-none-any.whl --wheelhouse D:\FAT-Build\wheels --output D:\Livraison\Vanguard-FAT-Studio-Portable
```

`build-portable.py` télécharge uniquement l’archive Python officielle épinglée si elle n’est pas déjà fournie avec `--python-archive CHEMIN`. Il vérifie sa taille et son SHA-256 avant extraction. Le dossier des wheels doit contenir exactement les paquets et versions de `requirements.lock`. L’installation utilise ces fichiers avec `--no-index --no-deps` ; les paquets ne sont pas cherchés sur un index pendant l’assemblage. L’archive Python peut aussi être transférée en amont pour une construction hors ligne.

La sélection publique est explicite dans `public-distribution.json`. Le constructeur vérifie la wheel de l’application, copie uniquement les documents autorisés, conserve les licences et les wheels d’origine, puis écrit `portable-manifest.json`. Le manifeste conserve la version, l’empreinte de la wheel et le commit source ; une livraison publique doit provenir de sources commitées. Il exécute ensuite le contrôle de cette livraison avec son propre interpréteur. Un échec laisse une construction incomplète dans sa destination neuve ; ne pas la distribuer.

Après construction, tester depuis **un autre dossier**, avec un `PATH` minimal, un dossier de données temporaire et sans dépendance au dépôt source. Le contrôle doit couvrir le service, une séquence de démo, les exports et une restauration d’archive. Seuls les contrôles effectivement exécutés peuvent être annoncés.

Pour produire un kit **source** hors ligne :

```powershell
.\scripts\prepare-offline.ps1 -Destination 'D:\Livraison\Vanguard-FAT-Studio-Source' -Python '.\.venv\Scripts\python.exe'
```

L’option `-Engineering` ajoute les dépendances Python verrouillées de l’ingénierie TIA, sans embarquer Siemens, .NET ou un serveur MCP installé. Lire [TIA_VERSIONS.md](TIA_VERSIONS.md), [TIA_MCP.md](TIA_MCP.md) et [COMPATIBILITY.md](COMPATIBILITY.md). L’IA TIA reste en lecture seule ; installer une option ne donne aucun droit de chargement ou de commande CPU.

## Dépanner

| Observation | Action |
| --- | --- |
| Portable incomplet ou modifié | Réextraire toute la livraison dans un nouveau dossier ; conserver les données séparées. |
| Python introuvable dans les sources | Préciser Python 3.12 x64 avec `setup.ps1 -Python`, ou utiliser la distribution portable. |
| Page inaccessible | Lire l’état du lanceur et cliquer **Ouvrir FAT Studio** ; pour un lancement console, lire son message. |
| Port occupé | Identifier le service déjà présent puis choisir un autre port ; ne pas arrêter un processus inconnu. |
| Dossier de données verrouillé | Identifier le serveur qui l’utilise et travailler dans un autre dossier ou l’arrêter volontairement. |
| Mauvaise plateforme de wheels | Repréparer un kit pour la plateforme voulue ; ne pas enlever le manifeste. |
| Erreur OPC UA | Vérifier la cible autorisée, l’identité et les NodeIds selon [PLCSIM_SETUP.md](PLCSIM_SETUP.md). |

Références : [distribution officielle Python 3.12.10](https://www.python.org/downloads/release/python-31210/), [paquet Python embarquable](https://docs.python.org/3.12/using/windows.html#the-embeddable-package), [installation pip depuis des paquets locaux](https://pip.pypa.io/en/stable/user_guide/#installing-from-local-packages).

## Mettre à jour un portable existant

Depuis 0.3.0, **Mise à jour** dans le lanceur recherche le portable officiel après un clic explicite. Le téléchargement est vérifié puis extrait dans un nouveau dossier. **Utiliser la mise à jour** ferme le service courant avant d’ouvrir la nouvelle copie, avec le même chemin de données et sans reprendre l’essai. Les étapes et limites sont dans [PORTABLE_LAUNCHER.md](PORTABLE_LAUNCHER.md).

Pour passer d’un portable antérieur à 0.3.0, suivre la procédure manuelle ci-dessous.

Les constructions du 7 novembre 2026 conservent la version applicative 0.2.1. La première ajoute les autorisations groupées ; la construction P&ID ajoute le circuit de départ, la bibliothèque filtrable et la fenêtre de liaison des tags automate. Le nom du ZIP, le commit source et le SHA-256 publiés dans la release identifient chaque construction. La version affichée par `/api/health` ne suffit pas à les distinguer.

1. Dans l’ancien banc, enregistrer les brouillons et exporter une archive FAT des projets à conserver avec leur historique.
2. Arrêter l’essai, puis fermer le serveur avant d’ouvrir le nouveau portable sur le même dossier de données.
3. Extraire entièrement le nouveau ZIP dans un **nouveau dossier**. Ne pas fusionner les fichiers avec l’ancien portable : chaque manifeste décrit sa propre livraison.
4. Lancer `Vanguard-FAT-Studio.cmd`. Le dossier de données habituel est conservé (`%LOCALAPPDATA%\FATStudio`). Si l’ancien lancement utilisait `--data-dir` ou `FAT_STUDIO_DATA`, conserver ce même chemin. Les archives exportées peuvent aussi être restaurées depuis **Ouvrir**.
5. Vérifier le projet actif et le mode avant de démarrer. Les autorisations locales de cible ne sont pas contenues dans le ZIP. L’accord groupé de l’interface doit être donné dans le nouvel onglet.

Pour revenir au portable précédent, arrêter le nouveau serveur puis lancer l’ancien dossier intact avec le dossier de données voulu. Cette mise à jour ne change pas le schéma de stockage ; les archives exportées restent la copie de sauvegarde du projet et de ses essais. Les données ne doivent pas être copiées dans `runtime/`, `app/` ou à l’intérieur du manifeste.

Les notes de release donnent le ZIP courant, son SHA-256, les sources exactes et le reçu des vérifications. Le tag `v0.4.0` identifie les sources de cette version. Les archives automatiques « Source code » de l’ancienne release d’aperçu suivent son tag historique ; utiliser la référence source indiquée dans cette ancienne release pour reconstruire ses portables.
