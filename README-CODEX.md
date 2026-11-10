# Vanguard FAT Studio : démarrer avec un assistant

Pour utiliser le banc, commencer par [INSTALLATION.md](docs/INSTALLATION.md) et le [guide utilisateur](docs/USER_GUIDE.md). Pour le piloter avec votre propre IA, suivre [AI_QUICKSTART.md](docs/AI_QUICKSTART.md). [AI_CONTROL.md](docs/AI_CONTROL.md) décrit le contrat canonique CLI/API ; [AGENTS.md](AGENTS.md), [CODEX.md](CODEX.md) et [CLAUDE.md](CLAUDE.md) donnent les consignes communes.

Vanguard FAT Studio fournit un environnement FAT, des formats JSON et une démo PLC passive. Il ne fournit pas de standard de programmation utilisateur. Le client IA reste externe ; aucune clé API de modèle n’est nécessaire dans le banc.

## Reprendre les sources

Lire [AGENTS.md](AGENTS.md), [l’état de reprise](docs/codex/ETAT_REPRISE.md) et les notes locales disponibles. Examiner `git status`, le diff et les derniers commits avant toute modification. Préserver les brouillons et essais présents. Une distribution avec un manifeste est une livraison vérifiée : créer une copie source distincte avant de modifier son contenu.

Sous Windows, le lanceur source `Start-FAT.cmd` utilise Python 3.12 x64. Le portable possède son propre `runtime\python.exe` et ne sert pas d’environnement de développement. Sous Linux/macOS, utiliser Python 3.12 et `bash scripts/start.sh` depuis une copie source.

Le paquet est `vanguard-fat-studio`, le module reste `fat_studio`. Les deux commandes `vanguard-fat-studio` et `fat-studio` pointent vers le même CLI. Préserver `FAT_STUDIO_DATA`, les dossiers existants, les identités OPC UA et les formats `fat-studio/*` ; un changement de marque ne migre pas les données. Le dépôt courant est [Vanguard-FAT-Studio](https://github.com/vandervan0001/Vanguard-FAT-Studio). Les preuves historiques gardent les noms et liens relevés lors de leur exécution.

```powershell
.\.venv\Scripts\python.exe -m fat_studio doctor --json
.\.venv\Scripts\python.exe -m fat_studio.assistant --help
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check fat_studio integrations tests scripts public_distribution.py build_public.py
```

Les outils de développement viennent de `requirements-dev.lock`. Pour l’interface, utiliser `npm ci`, `npm run typecheck`, `npm run build` et `npm test` depuis `frontend/`, puis copier les assets avec `python scripts/build-web.py`. Tester le bundle livré sur des données temporaires. Une suite navigateur ne doit jamais viser une instance contenant les essais d’un utilisateur.

## Construire une distribution publique

`public-distribution.json` énumère les fichiers autorisés. `public_distribution.py`, les hooks de setuptools et les constructeurs de kits refusent un module inattendu ou un contenu privé détecté. La liste est à relire lorsqu’un fichier public est ajouté ; ne pas la remplacer par une copie récursive du dépôt.

```powershell
.\.venv\Scripts\python.exe public_distribution.py check
.\.venv\Scripts\python.exe -m build --no-isolation
.\.venv\Scripts\python.exe public_distribution.py check-wheel dist\vanguard_fat_studio-0.3.0-py3-none-any.whl
```

L’assemblage Windows portable et le kit source hors ligne sont documentés dans [INSTALLATION.md](docs/INSTALLATION.md). Ils utilisent une destination neuve, des dépendances verrouillées et un manifeste de tailles/SHA-256. Le manifeste contrôle l’intégrité du transfert ; il ne remplace pas la confiance dans l’origine de l’archive.

Les sources et données propres aux utilisateurs restent en dehors des paquets publics. Les notes de travail privées et le journal multi-agent ne sont pas redistribués. Préserver les preuves historiques dans l’espace de travail ; distribuer uniquement les preuves relues et explicitement ajoutées à la sélection publique. Ne pas transférer la qualification d’un ancien programme à la démo actuelle.

## TIA et cible virtuelle

Le banc OPC UA, le programme de démonstration et l’ingénierie TIA sont distincts. Lire [DEMO_PLC.md](docs/DEMO_PLC.md), [PLCSIM_SETUP.md](docs/PLCSIM_SETUP.md), [TIA_VERSIONS.md](docs/TIA_VERSIONS.md) et [TIA_MCP.md](docs/TIA_MCP.md) selon le besoin. Czarnak `TiaMcpServer` 4.3.0 reste épinglé ; l’accès IA est en lecture seule. Un import/une compilation suit les confirmations du CLI humain. Aucun chargement ni RUN/STOP CPU n’est autorisé par ce document.

Les projets et scénarios s’échangent au [format JSON versionné](docs/FORMAT.md). Le projet entier se conserve dans une [archive restaurable](docs/PROJECT_ARCHIVES.md). Un fichier reçu n’autorise ni cible machine ni conclusion FAT humaine. Toute preuve doit préciser la plateforme, la version et l’opération réellement exécutée.
