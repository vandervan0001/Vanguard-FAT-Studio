# FAT Studio

**Banc FAT local avec P&ID interactif, simulation de procédé et connexion OPC UA à une instance PLCSIM Advanced configurée.**

Le programme PLC reste le contrôleur du procédé. FAT Studio lit ses commandes, calcule les équipements et renvoie les capteurs simulés. Le mode **Démonstration** fournit un contrôleur distinct pour essayer l'application sans Siemens.

Version actuelle : **0.2.0**, le 2 novembre 2026, avec [choix V20/V21](docs/TIA_VERSIONS.md) et profils d'ingénierie séparés. La [revue adverse 0.1.1](docs/ADVERSARIAL_REVIEW.md) et ses preuves restent conservées. **TIA Portal et PLCSIM Advanced ne sont pas présents dans l'environnement de réalisation : la compilation du portage V20 et la qualification Siemens des deux versions restent à effectuer sur le poste cible.** Voir [ACCEPTANCE](docs/ACCEPTANCE.md) et les [preuves 0.2.0](evidence/reprises/2026-11-02-v20-v21/VERIFICATION.md).

## Démarrer sous Windows

1. Installer **Python 3.12 x64** sur le poste. Node.js n'est pas nécessaire pour utiliser la distribution précompilée.
2. Extraire l'archive entière dans un dossier local, ou cloner le dépôt.
3. Double-cliquer **`Start-FAT.cmd`**.
4. Lors du premier lancement, les dépendances verrouillées sont installées dans `.venv`. Le navigateur ouvre ensuite **http://127.0.0.1:8765**.
5. Garder la fenêtre du serveur ouverte. La fermer arrête le banc.

Si l'archive contient `wheelhouse/` et `offline-manifest.json`, la première installation utilise ces dépendances locales et vérifie leurs empreintes. Depuis un clone sans ces fichiers, elle utilise PyPI. L'exécution du banc est entièrement locale. Le kit Windows livré contient les 29 wheels runtime pour Python 3.12 x64 ; un nouveau kit se prépare avec `scripts/prepare-offline.ps1`. L'interpréteur Python, Siemens et l'option d'ingénierie TIA s'installent séparément. Voir le [guide d'installation](docs/INSTALLATION.md) pour la politique PowerShell, les postes sans Internet et le dépannage.

### Essayer la démonstration

Le projet **TK-101 · Banc de remplissage** est chargé au premier démarrage : huit équipements, treize tags et trois scénarios.

1. Choisir **Cycle de référence** dans le sélecteur de scénario.
2. Cliquer **Démarrer** et observer la cuve, les commandes et les tendances.
3. Le scénario s'arrête à **32 secondes simulées**. Ses assertions sont enregistrées.
4. Ouvrir **Tendances & rapport**, ajouter un commentaire et renseigner le verdict humain.
5. Exporter le CSV, le rapport HTML imprimable ou les preuves JSON.
6. Réinitialiser et essayer **Défaut moteur** ou **Capteur de niveau figé**.

L'absence de Siemens n'est jamais masquée : le bandeau affiche **DÉMONSTRATION** et « aucun PLC connecté ».

### Linux / macOS, pour la démonstration

Depuis un clone source sans les wheels Windows, avec Python 3.12 installé :

```bash
bash scripts/start.sh
```

PLCSIM Advanced et TIA Portal restent des logiciels Windows. Le script installe le banc dans un environnement Python isolé puis sert la même interface locale. L'archive Windows contient un dépôt Git et un bundle : `git clone FAT-Studio.bundle fat-studio-source` crée une copie source sans les dépendances spécifiques à Windows.

## Fonctions livrées

| Domaine | Fonctionnement |
| --- | --- |
| P&ID | Palette de sept symboles, glisser-déposer, déplacement, connexions, zoom, panoramique, grille, propriétés et sauvegarde JSON |
| Variables | BOOL, INT, DINT, REAL ; sens vu depuis le PLC ; unités, bornes, autorisation d'écriture ; mapping CSV et NodeIds |
| Procédé | Cuve avec bilan de volume, pompe, vannes TOR/modulante, instruments analogiques/binaires et indicateur PLC |
| Scénarios | Actions datées, forçages, libérations, défauts, marqueurs, assertions et durée ; pause/reprise/arrêt/reset |
| Défauts | Moteur en défaut, vanne bloquée, capteur figé et signal hors plage ; état visible et journalisé |
| Traces | Historique SQLite local, enregistrement à chaque cycle, tendances à 2 Hz, rapports HTML, CSV et JSON |
| OPC UA | Validation des nœuds/types/droits avant écriture, identité serveur, politique locale, confirmation de cible, certificats et arrêt sur erreur |
| TIA/IA | Czarnak MCP épinglé, clients IA en lecture seule, export/diff puis import et compilation via CLI humain séparé |
| Livraison | Interface précompilée, scripts Windows/Linux, procédure hors ligne, exemples Siemens, tests et CI Windows/Linux |

Les lignes du dessin sont des connexions visuelles. Les débits utilisent les paramètres explicites **cuve / sens / groupe de débit** : les capacités en série prennent leur minimum, les branches indépendantes s'additionnent. Ce comportement évite de prétendre fournir un solveur hydraulique général. Voir [modèle de procédé](docs/MODEL.md).

## Connecter PLCSIM Advanced

Suivre [PLCSIM_SETUP](docs/PLCSIM_SETUP.md). La procédure prévoit :

1. Relever CPU, firmware, Windows, TIA Portal, PLCSIM Advanced et configuration OPC UA.
2. Utiliser une **copie du projet TIA**, activer sa simulation et configurer PLCSIM en TCP/IP avec l'adaptateur virtuel local isolé.
3. Créer le DB d'échange à partir de `siemens/DB_FAT.scl` ou mapper les variables existantes. Le helper livré doit être adapté aux interfaces du programme testé ; il ne remplace pas sa logique.
4. Exposer les variables OPC UA et relever leurs **NodeIds réels**, le namespace et l'ApplicationUri. Les exemples ne sont pas une découverte automatique.
5. Autoriser la cible sur le poste avec `python -m fat_studio authorize-target`, après contrôle de son isolation. Un fichier projet importé ne peut pas modifier cette politique.
6. Choisir OPC UA dans l'interface, renseigner les informations concordantes et saisir la confirmation de cible au démarrage.

Le banc n'envoie jamais de commande RUN/STOP ou de téléchargement. Une pause ou un reset du modèle ne remet donc pas le PLC dans son état initial. Pour un rejeu réel comparable, l'ingénieur doit aussi remettre le programme PLC dans les conditions de départ prévues.

Un serveur OPC UA local indépendant est fourni pour tester le raccordement et une perte de communication sans Siemens :

```bash
python scripts/opcua-fixture.py
```

Il affiche le chemin du projet exporté et la commande d'autorisation locale. Arrêter ce serveur pendant un essai permet de constater l'arrêt des écritures. Cette fixture est **un test de protocole**, pas une émulation Siemens.

## Réutilisation de l'existant

| Composant | Réutilisation effective | Limite |
| --- | --- | --- |
| [React Flow](https://github.com/xyflow/xyflow) | Éditeur de graphe, interactions et canevas | Symboles et logique métier FAT spécifiques |
| [FreeOpcUa / asyncua](https://github.com/FreeOpcUa/opcua-asyncio) | Client et serveur OPC UA, types et chiffrement | La qualification CPU/firmware reste propre au poste |
| [HistorianSim](https://github.com/ScottDuncanAI/HistorianSim) | Module de caractéristiques de vanne conservé identique et attribué | Aucun régulateur ou moteur batch de cet outil dans le runtime FAT |
| [Czarnak/tia-portal-mcp](https://github.com/Czarnak/tia-portal-mcp) | Serveur existant `TiaMcpServer 4.3.0`, Openness et contrats audités | Installation séparée sur Windows/TIA V21 ; qualification à réaliser |
| [SDK MCP officiel](https://github.com/modelcontextprotocol/python-sdk) | Transport du CLI d'ingénierie | Le CLI n'expose pas ses opérations d'écriture à un agent IA |
| [HistorianRCA](https://github.com/ScottDuncanAI/HistorianRCA) | Référence documentaire examinée | Pas de jeu de données ni SVG repris |

Les révisions, licences et choix sont consignés dans [UPSTREAM_REVIEW](docs/UPSTREAM_REVIEW.md), [upstream.lock.json](integrations/upstream.lock.json) et [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md).

## Claude Code / Codex et TIA Portal

Voir [TIA_MCP](docs/TIA_MCP.md). Les clients IA utilisent uniquement le serveur existant en **`--access-mode read-only`**. Le serveur amont n'est pas lancé avec son mode brut par défaut.

Dans **Connexion**, sélectionner la version du projet TIA. V21 utilise le paquet Czarnak 4.3.0 ; V20 dispose d'un candidat de portage à compiler sur Windows avec les DLL V20 réellement installées. L'installateur demande la version et refuse les mélanges de profils ou une compilation incompatible. Voir [l'installation et les limites V20/V21](docs/TIA_VERSIONS.md).

Le CLI `fat-tia` orchestre la préparation et l'application d'une proposition : copie sandbox exacte, sources et empreintes, diff, activation d'écriture distincte, confirmation au terminal, archive avant import, contrôle de source périmée, import, compilation et audit. Le résultat de compilation ne vaut pas validation fonctionnelle.

Le runtime FAT n'a pas de dépendance à un modèle IA. Si l'utilisateur emploie Claude Code/Codex avec un modèle hébergé, le contenu qu'il transmet au client peut quitter le poste ; cette décision relève de sa politique de données.

## Développement et vérification

```bash
python3.12 -m venv .venv
# Windows : .venv\Scripts\python ; Linux/macOS : .venv/bin/python
.venv/bin/python -m pip install -r requirements-dev.lock -r requirements-engineering.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation .
.venv/bin/python -m pytest
.venv/bin/python -m ruff check fat_studio integrations tests scripts
```

Reconstruction de l'interface avec Node.js 22+ :

```bash
cd frontend
npm ci
npm run build
cd ..
.venv/bin/python scripts/build-web.py
```

Tests navigateur : voir [frontend/README](frontend/README.md). La CI décrit les mêmes vérifications sur Windows et Ubuntu ; l'existence de ce workflow ne signifie pas qu'une exécution distante a déjà eu lieu.

## Documentation et preuves

- [URS d'origine](docs/URS-original.md) et [décisions de reprise](docs/URS-implementation.md).
- [FDS et architecture](docs/FDS.md), [contrat API](docs/CONTRACT.md).
- [Matrice exigences → implémentation → preuves](docs/REQUIREMENTS_MATRIX.md).
- [Installation](docs/INSTALLATION.md), [utilisation](docs/USER_GUIDE.md), [modèle](docs/MODEL.md).
- [Raccordement Siemens](docs/PLCSIM_SETUP.md), [compatibilité](docs/COMPATIBILITY.md), [ingénierie MCP](docs/TIA_MCP.md).
- [Protocole d'acceptation](docs/ACCEPTANCE.md) et [résultats exécutés](evidence/VERIFICATION.md).
- [Revue adverse 0.1.1 : défauts reproduits, corrections et limites](docs/ADVERSARIAL_REVIEW.md).

## Données et maintenance

Les projets et résultats sont placés dans `%LOCALAPPDATA%\FATStudio` sous Windows, `~/.fat-studio` ailleurs, ou dans `FAT_STUDIO_DATA` si défini. Les projets sont des JSON lisibles ; le précédent enregistrement est conservé. Les essais restent dans `history.sqlite3`, y compris après un reset. Copier ce dossier serveur arrêté pour sauvegarder les preuves. Les exports JSON/CSV/HTML sont indépendants du poste.

L'application accepte un seul processus par dossier de données, un seul projet actif et une seule cible PLC à la fois. Une perte de communication arrête l'essai et exige une reprise explicite dans un nouvel essai. Les mots de passe et clés privées ne sont pas stockés dans les projets ; ceux-ci contiennent uniquement les références locales approuvées.

Le logiciel est un outil d'essai fonctionnel. Il ne simule pas la sécurité, les SIL, la mécanique 3D, la pression d'un réseau général ou la validation GMP d'une installation. Les modèles et résultats doivent être confrontés au procédé et au programme réellement testés.
