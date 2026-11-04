# Piloter Vanguard FAT Studio avec votre IA

Votre assistant peut préparer un projet, lire les valeurs, lancer une séquence de démonstration et exporter ses preuves par le client local. **Aucune clé API de modèle n’est demandée par Vanguard FAT Studio.** Utilisez votre propre client et votre accès habituel au modèle. Le logiciel n’embarque ni modèle ni conversation en langage naturel ; les commandes passent par son API locale.

Le client doit pouvoir lire le dossier et exécuter Python ou des requêtes HTTP sur le poste. Sans cet accès, il peut préparer des fichiers et des commandes, mais pas constater leur exécution. Les données transmises à un modèle hébergé peuvent quitter le poste selon votre client et sa configuration.

Pour l’interface, lire [USER_GUIDE.md](USER_GUIDE.md). Pour le protocole complet, lire [AI_CONTROL.md](AI_CONTROL.md). Les formats de fichiers sont dans [FORMAT.md](FORMAT.md) et [PROJECT_ARCHIVES.md](PROJECT_ARCHIVES.md).

## 1. Ouvrir une démonstration isolée

Installer selon [INSTALLATION.md](INSTALLATION.md). Le tutoriel utilise le port **8767** et des données séparées. Le port 8766 est réservé par défaut aux tests navigateur du dépôt. Depuis le dossier Vanguard FAT Studio, dans PowerShell :

```powershell
# Portable : son interpréteur et son contrôle d’intégrité.
$FatPython = (Resolve-Path '.\runtime\python.exe').Path
.\Start-FAT.cmd --check

# Depuis les sources, remplacer les deux lignes précédentes par :
# $FatPython = (Resolve-Path '.\.venv\Scripts\python.exe').Path

$FatDemo = Join-Path $env:LOCALAPPDATA 'FATStudio\AI-Demo'
& $FatPython -B -X utf8 -m fat_studio serve --host 127.0.0.1 --port 8767 --data-dir (Join-Path $FatDemo 'data')
```

Garder ce terminal ouvert. Vérifier l’URL et le dossier affichés, puis ouvrir [http://127.0.0.1:8767](http://127.0.0.1:8767). Si le port est occupé, identifier le service existant et choisir un autre port sans arrêter un processus inconnu. Aucun Siemens n’est requis ici. Sous Linux/macOS, utiliser `.venv/bin/python` et un dossier de données personnel indépendant.

## 2. Donner ce prompt à votre assistant

Ouvrir le dossier Vanguard FAT Studio dans le client, ou lui donner un accès explicite à ce dossier. Adapter le chemin de données si nécessaire :

```text
Tu travailles avec Vanguard FAT Studio dans ce dossier. Lis AGENTS.md, README-CODEX.md,
docs/AI_QUICKSTART.md et docs/AI_CONTROL.md. Inspecte Git avant de modifier
les sources ; ne change aucun fichier d’une livraison vérifiée.

Je t’autorise à piloter uniquement la démonstration http://127.0.0.1:8767,
données %LOCALAPPDATA%/FATStudio/AI-Demo/data. Utilise le Python runtime
si c’est un portable, ou le Python .venv pour les sources, et le module
fat_studio.assistant. Place le contexte dans AI-Demo/context.json, hors du
runtime. Lis health, project, state, catalog et schema. Vérifie le mode demo
et l’absence d’essai utilisateur actif, puis capture explicitement context.

Charge le laboratoire public avec pilot, valide, démarre demo-fill-source.
Lis les contrôles jusqu’à sa fin. Exporte JSON, CSV et HTML de son run_id
précis dans AI-Demo/exports, avec des noms nouveaux. Rapporte les attentes,
valeurs, qualités, erreurs et fichiers réellement obtenus.

Ne crée aucun standard de programmation ou programme métier. N’invente
aucun NodeId, adresse, essai Siemens ou verdict humain. Ne commande aucune
CPU ni politique de cible ; pas d’ingénierie TIA ni de publication. Après
conflit de contexte ou erreur, constate l’état sans recapture ni réessai
automatique. Les observations de STEP et la conclusion globale attendent
ma décision explicite.
```

Le nom de commande `pilot` est conservé pour compatibilité ; il charge maintenant le laboratoire public, sans bibliothèque de programmation. Ce prompt autorise une démo précise. Un projet importé n’autorise jamais une cible OPC UA. [CODEX.md](../CODEX.md) et [CLAUDE.md](../CLAUDE.md) pointent vers le même contrat.

## 3. Vérifier les commandes à la main

Dans un second terminal, depuis le même dossier, exécuter ligne par ligne. Choisir le Python correspondant à votre distribution :

```powershell
$FatPython = (Resolve-Path '.\runtime\python.exe').Path
# Sources : $FatPython = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$FatDemo = Join-Path $env:LOCALAPPDATA 'FATStudio\AI-Demo'
$FatApi = @('-B', '-X', 'utf8', '-m', 'fat_studio.assistant', '--url', 'http://127.0.0.1:8767', '--context', (Join-Path $FatDemo 'context.json'))

& $FatPython @FatApi health
& $FatPython @FatApi project
& $FatPython @FatApi state
& $FatPython @FatApi catalog
& $FatPython @FatApi schema
& $FatPython @FatApi context
& $FatPython @FatApi pilot
& $FatPython @FatApi validate
$FatStarted = & $FatPython @FatApi start --scenario demo-fill-source | ConvertFrom-Json
if (-not $FatStarted.run_id) { throw 'Aucun essai confirmé ; lire le diagnostic avant de poursuivre.' }
$FatRun = $FatStarted.run_id
& $FatPython @FatApi state
```

`context` capture le projet, sa révision et l’essai attendus, sans jeton sur disque. Une mutation réussie avance ce contexte ; une lecture ne le déplace jamais. Si une autre fenêtre change le projet ou ouvre un essai, la commande suivante est refusée. Relire la situation avant de décider d’une nouvelle capture ; ne pas recapturer pour rejouer automatiquement.

`demo-fill-source` dure **sept secondes simulées**. Lire `state` jusqu’à `status:"paused"` et `scenario.state:"completed"`. Une erreur ne constitue pas une fin réussie. `scenario.assertions` contient les attentes, mesures, qualités et résultats ; le résultat humain reste `not_evaluated`.

```powershell
& $FatPython @FatApi export --run $FatRun --kind json --output (Join-Path $FatDemo 'exports\fill.json')
& $FatPython @FatApi export --run $FatRun --kind csv --output (Join-Path $FatDemo 'exports\fill.csv')
& $FatPython @FatApi export --run $FatRun --kind report --output (Join-Path $FatDemo 'exports\fill.html')
```

Le client refuse d’écraser un export existant. Choisir de nouveaux noms pour un rejeu. Un export actif représente un instantané fini ; réexporter après la fin pour la clôture. Pour sauvegarder tout le projet avec son historique, suivre [PROJECT_ARCHIVES.md](PROJECT_ARCHIVES.md).

## 4. Préparer une FAT pas à pas

```powershell
& $FatPython @FatApi stop
& $FatPython @FatApi reset
& $FatPython @FatApi start --scenario demo-guided-io
& $FatPython @FatApi step-execute guided-initial
& $FatPython @FatApi state
```

Le premier STEP passe de `queued` à `applied` après un échange réussi. Il présente **12 mA → 13 824 comptes** sur `lt101_raw` et attend `lt101_percent = 50`, `p101_command = false`. Lire `guided_steps`, attendre le temps de réaction prescrit et observer. Les contrôles sont évalués lors de l’observation, pas lors du clic d’exécution.

Demander ensuite à l’assistant :

```text
Lis les mesures et les qualités du STEP. Présente les écarts avec le résultat
attendu, puis attends mon observation et mon choix Conforme/Écart avant
step-observe. Le résultat global doit rester Non évalué.
```

Le client transmet une décision humaine explicite avec `step-observe ID --verdict pass|fail --observation TEXTE`. Un contrôle en échec interdit `pass`. Le suivant reste verrouillé jusqu’à la revue du précédent. Les cinq identifiants sont `guided-initial`, `guided-run`, `guided-stop`, `guided-requests-off`, `guided-release` ; lire leurs actions avant de les exécuter.

## 5. Faire préparer un projet et ses scénarios

Fournir besoin de procédé, équipements, plages, interfaces connues, préconditions et attentes. Demander un fichier candidat à relire :

```text
Découvre catalogue et schéma actifs. Prépare une enveloppe fat-studio/project
version1.0 avec P&ID, variables, associations et FAT pas à pas. Pour chaque
STEP, décris les écritures d’entrées simulées, résultat attendu et contrôles.
Prévois la libération des stimuli et les courbes utiles. Garde le mode demo.
Laisse vide toute adresse ou NodeId inconnu. Déclare les conversions sans
les déduire d’un nom. Présente hypothèses et diagnostics. Ne charge rien
dans un essai actif et ne modifie aucune attente pour obtenir un succès.
```

Après revue, `load-project CHEMIN` charge une enveloppe ou un ancien projet compatible, si le banc est éditable. `validate` expose les diagnostics. Les scénarios versionnés incluent leurs contrats de tags ; importer un scénario ne change ni sens, ni type, ni unité d’une variable pour le rendre compatible. Lire [FORMAT.md](FORMAT.md).

## 6. D’un projet TIA réel au client local

Cette partie demande une copie virtuelle autorisée, déjà préparée avec ses interfaces de simulation et son serveur OPC UA. Elle ne commande pas d’installation, de téléchargement ou de RUN/STOP CPU. Suivre [DEMO_PLC.md](DEMO_PLC.md), [PLCSIM_SETUP.md](PLCSIM_SETUP.md) et [TIA_MCP.md](TIA_MCP.md).

1. Relever endpoint, ApplicationUri, certificat serveur et SHA-256, namespace, NodeIds, types scalaires et droits sur la cible autorisée. Vérifier son adaptateur virtuel isolé. Une adresse `%DB…` n’est pas un NodeId.
2. Préparer votre projet candidat en `plc.mode:"opcua"`, vitesse1 et mapping réellement découvert. Garder les attentes approuvées pour ce programme.
3. Fournir au serveur FAT les chemins approuvés du certificat et de la clé client. Les éventuels identifiants restent dans son environnement ; le projet contient seulement les noms `username_env`/`password_env`, jamais leurs valeurs.
4. Faire autoriser la cible par le terminal humain `python -m fat_studio authorize-target --help`, dans la racine de données utilisée par le serveur. Cette autorisation machine reste indépendante du JSON et des workspaces.
5. Démarrer le serveur dans le dossier choisi. Lire `health/project/state`, puis capturer volontairement le contexte. Charger le candidat avec `load-project`, valider et vérifier les diagnostics.
6. Utiliser `start --scenario ID --target-confirmation 'NOM @ ENDPOINT'` avec le nom et l’endpoint réellement autorisés. Conserver le `run_id`, constater commandes lues, entrées écrites et qualités avant de poursuivre la campagne.

Une session déjà prête ne demande pas de refaire ces étapes d’ingénierie. Vérifier son URL, son dossier et son état avant intervention. Arrêt/reset/redémarrage du banc ne remplacent pas le contrôle des entrées retenues et le réarmement prévu par votre programme. Ne pas remettre les sorties à zéro par forçage ni modifier les attentes après un écart.

Le client `fat_studio.assistant` ne découvre pas automatiquement les tags Siemens, ne charge pas une CPU et ne commande pas RUN/STOP. Le transport OPC UA connecté ne prouve pas que la CPU est en RUN. Les preuves d’une autre cible ne qualifient pas votre programme, V20, une CPU physique ou une fonction de sécurité.

## 7. Terminer

Utiliser `stop` si l’essai est encore ouvert, conserver les exports puis `Ctrl+C` dans le terminal du serveur. Une erreur de communication ou de stockage interrompt le banc sans reprise automatique ; un lot OPC UA partiel n’est pas annulable par le modèle.

L’ingénierie TIA reste séparée : Czarnak `TiaMcpServer` 4.3.0 épinglé, profil vérifié et IA en lecture seule. Les imports/compilations autorisés suivent le CLI humain et ses confirmations. Ne partager que les fichiers relus, sans clés privées, secrets, programmes ou bibliothèques confidentiels.
