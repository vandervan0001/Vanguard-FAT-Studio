# Installer et démarrer FAT Studio

**État de vérification : les essais de livraison ont été exécutés sous Linux. Les scripts PowerShell ont été relus, mais leur exécution sous Windows, l'installation Windows hors ligne et les échanges avec TIA Portal/PLCSIM Advanced restent à qualifier sur le poste cible.** L'exécution sous macOS n'a pas été vérifiée. Les résultats disponibles figurent dans [VERIFICATION.md](../evidence/VERIFICATION.md) ; le protocole du poste est dans [ACCEPTANCE.md](ACCEPTANCE.md).

## Premier démarrage sur Windows

La livraison contient l'interface compilée. **Python 3.12 x64 est le seul prérequis du banc de démonstration.** Node.js, TIA Portal, PLCSIM Advanced, .NET et un compte IA ne sont pas nécessaires pour cette démonstration.

1. Installer Python 3.12 x64 depuis la distribution officielle approuvée par votre IT. Le lanceur `py` facilite sa détection.
2. Extraire l'archive complète ou cloner le dépôt dans un dossier accessible en écriture, par exemple `C:\FAT\fat-studio`.
3. Double-cliquer **`Start-FAT.cmd`**.
4. Au premier lancement, le script crée `.venv`, installe les versions de `requirements.lock`, installe le paquet local et ouvre **http://127.0.0.1:8765**.
5. La cuve TK-101 est proposée en démonstration. Choisir **01 · Cycle de référence**, puis **Démarrer**.

Laisser la fenêtre du serveur ouverte pendant l'utilisation. **Ctrl+C** dans cette fenêtre arrête le service. Fermer seulement l'onglet du navigateur n'arrête pas un essai en cours.

Une connexion Internet est nécessaire à la première installation standard des dépendances. Le fonctionnement après installation est local. Aucun CDN, police distante, analytics ni API IA n'est requis par l'interface FAT.

### Politique PowerShell

Le lanceur utilise `RemoteSigned` pour son processus et respecte les stratégies Windows imposées par l'organisation. Si Windows signale que les scripts de l'archive sont bloqués, vérifier leur provenance et utiliser le déblocage de l'archive autorisé par l'IT, puis réextraire les fichiers. Une stratégie d'entreprise qui interdit leur exécution doit être traitée avec l'administrateur. Le logiciel ne modifie pas les stratégies globales.

### Commandes utiles

Depuis le dossier du dépôt :

```powershell
# Installation ou mise à jour après un git pull
.\scripts\setup.ps1

# Choisir explicitement l'interpréteur
.\scripts\setup.ps1 -Python "C:\Python312\python.exe"

# Port différent, sans ouvrir le navigateur
.\scripts\start.ps1 -Port 8770 -NoBrowser

# Choisir un dossier de données
.\scripts\start.ps1 -DataDir "D:\FAT\donnees"

# Réinstaller les dépendances et le paquet
.\scripts\start.ps1 -Repair

# Diagnostic d'installation, sans connexion à Siemens
.\.venv\Scripts\python.exe -m fat_studio doctor --json
```

Le lancement normal n'installe pas l'assistance d'ingénierie. Pour cette option, lire [TIA_MCP.md](TIA_MCP.md), puis utiliser `setup.ps1 -Engineering`. TIA Portal V21, Openness et le serveur upstream restent des installations distinctes.

## Linux et macOS : démonstration et développement

La démonstration et les tests de protocole sont portables ; l'intégration Siemens s'utilise sur le poste Windows qualifié.

```bash
bash scripts/start.sh
```

Le script utilise Python 3.12, crée l'environnement si nécessaire, installe les dépendances et démarre le même service. Exemples :

```bash
bash scripts/start.sh --no-browser --port 8770
bash scripts/start.sh --data-dir "$PWD/fat-data"
.venv/bin/python -m fat_studio doctor
```

Après mise à jour du dépôt, réinstaller explicitement :

```bash
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation .
```

## Emplacement des projets et des essais

| Plateforme | Dossier par défaut |
| --- | --- |
| Windows | `%LOCALAPPDATA%\FATStudio` |
| Linux / macOS | `~/.fat-studio` |
| Toutes | `--data-dir` ou variable `FAT_STUDIO_DATA` pour choisir un autre dossier |

Les projets sont des JSON lisibles dans `projects/`. Les essais, échantillons et événements sont enregistrés dans `history.sqlite3`. La politique d'autorisation PLC est propre au poste dans `machine-policy.json` ; elle ne fait pas partie des projets importables.

Pour une sauvegarde complète, arrêter le service puis copier le dossier de données. Pour versionner un projet dans Git, utiliser **Exporter** dans l'interface et conserver ce JSON dans le dépôt de votre affaire. Éviter de versionner l'historique SQLite ou les clés privées. La version précédente d'un projet écrasé est conservée sous `*.previous.json`.

## Préparer une installation sans Internet

La préparation se fait sur **un poste Windows x64 avec Python 3.12 x64 et accès Internet**. Elle collecte les wheels correspondant à cette plateforme ; ce kit n'est pas un kit Linux/macOS.

```powershell
.\scripts\prepare-offline.ps1 -Destination "D:\Livraison\FAT-Studio-Windows"

# Inclure aussi les dépendances Python de l'option ingénierie
.\scripts\prepare-offline.ps1 -Destination "D:\Livraison\FAT-Studio-Windows-IA" -Engineering
```

Le dossier produit contient le code Python et frontend, la documentation, les preuves de livraison, les assets web compilés, les dépendances Python dans `wheelhouse/` et un manifeste SHA-256. Les dépendances Node et le dossier de construction `frontend/dist` ne sont pas copiés ; l'interface utilisable est déjà dans `fat_studio/web`. Le script refuse une destination existante. Copier le dossier complet vers le poste isolé, fournir séparément l'installateur Python validé par l'IT si nécessaire, puis lancer `Start-FAT.cmd`.

L'installation vérifie les empreintes, refuse les wheels non répertoriées et passe `--no-index` à pip. Elle ne tente pas de se rabattre sur Internet si une dépendance manque. Le manifeste détecte une corruption des fichiers ; il ne remplace pas une signature de distribution approuvée.

Ce kit ne redistribue pas Siemens, .NET ni `tia-portal-mcp`. Pour un poste d'ingénierie totalement hors ligne, préparer ces composants séparément selon leurs licences et la procédure IT. Voir la matrice dans [COMPATIBILITY.md](COMPATIBILITY.md).

## Reconstruire l'interface et la wheel

Cette étape concerne les développeurs. La version Node utilisée par CI est **22**, et les dépendances frontend sont verrouillées par `frontend/package-lock.json`.

```bash
cd frontend
npm ci
npm run build
cd ..
python scripts/build-web.py
python -m pip install -r requirements.lock -r requirements-dev.lock -r requirements-engineering.lock
python -m pip install --no-deps --no-build-isolation .
python -m pytest
python -m build --wheel --no-isolation
```

Les assets compilés sont copiés dans `fat_studio/web` et inclus dans la wheel. Aucun serveur Vite n'est nécessaire en exploitation. La CI construit l'interface et exécute les tests sur Windows et Ubuntu ; un fichier de workflow fourni n'est pas une preuve qu'un run distant a déjà réussi.

## Dépannage

| Symptôme | Action |
| --- | --- |
| Python introuvable / mauvaise version | Installer Python 3.12 x64 ou préciser `setup.ps1 -Python` ; ne pas réutiliser un `.venv` créé avec une autre version. |
| `Interface compilée absente` | Utiliser la livraison complète ou reconstruire l'interface avec les commandes ci-dessus. |
| Port 8765 occupé | Fermer l'autre instance ou choisir `-Port 8770` / `--port 8770`. |
| Page inaccessible | Vérifier que la console du serveur tourne et ouvrir l'URL indiquée par celle-ci. |
| `Service indisponible` dans l'interface | Les valeurs affichées sont anciennes ; vérifier le serveur avant de reprendre un essai. |
| Kit hors ligne incomplet | Repréparer le kit sur la bonne plateforme ; une wheel Linux ne remplace pas une wheel Windows. |
| Projet signalé invalide | Corriger les diagnostics de **Connexion** ; l'enregistrement d'un brouillon incomplet reste possible. |
| Cible OPC UA refusée | Suivre [PLCSIM_SETUP.md](PLCSIM_SETUP.md), vérifier la politique locale et l'identité observée. |

### Références d'outillage

- [Python : création d'environnements virtuels](https://docs.python.org/3.12/library/venv.html).
- [pip : installation depuis des paquets locaux](https://pip.pypa.io/en/stable/user_guide/#installing-from-local-packages).
- Contrats des actions CI consultés : [checkout v6](https://github.com/actions/checkout/blob/v6/action.yml), [setup-python v6](https://github.com/actions/setup-python/blob/v6/action.yml), [setup-node v6](https://github.com/actions/setup-node/blob/v6/action.yml), [upload-artifact v6](https://github.com/actions/upload-artifact/blob/v6/action.yml).
