# Assistance TIA par Claude Code ou Codex

Ce volet est **optionnel**. Le banc FAT, son P&ID et son adaptateur OPC UA fonctionnent sans IA. L'assistant analyse le projet d'ingénierie par TIA Openness ; il ne remplace ni le programme PLC, ni les échanges cycliques du runtime FAT.

Le serveur réutilisé est [Czarnak/tia-portal-mcp v4.3.0](https://github.com/Czarnak/tia-portal-mcp/tree/v4.3.0). Cette version est épinglée pour conserver les contrats inspectés. Le détail de la comparaison se trouve dans [UPSTREAM_REVIEW.md](UPSTREAM_REVIEW.md).

## Prérequis

- Windows et **TIA Portal V21**, avec Openness installé.
- Compte Windows membre de `Siemens TIA Openness` ; ouvrir une nouvelle session après une éventuelle modification de groupe.
- .NET Framework **4.8** pour le worker.
- SDK .NET **10.0.400 ou ultérieur dans la branche 10.0** pour installer l'outil.
- Python et environnement du projet FAT déjà installés.
- Une **copie de développement standalone `.ap21`**, ouverte et sauvegardée dans TIA. Utiliser « Enregistrer sous » ou un archivage/restauration TIA pour créer cette copie. Les sessions multiutilisateurs ne sont pas prises en charge par notre parcours d'écriture.

Source des prérequis : [guide upstream épinglé](https://github.com/Czarnak/tia-portal-mcp/blob/v4.3.0/docs/guides/installation.md). La matrice de compatibilité du banc indique ce qui a été testé et ce qui reste à qualifier sur Siemens.

## 1. Installer le composant optionnel

Depuis la racine du dépôt, dans PowerShell :

```powershell
.\scripts\install-tia-mcp.ps1
.\scripts\setup.ps1 -Engineering
```

Le premier script installe `TiaMcpServer 4.3.0` dans `.tools\tia-mcp`, vérifie la version et lance son `doctor`. Il ne télécharge ni TIA Portal, ni licence, ni DLL Siemens. Un autre outil déjà présent n'est pas remplacé silencieusement. `setup.ps1 -Engineering` installe les versions Python de `requirements-engineering.lock` ; l'exécuter depuis un clone source connecté ou un kit préparé avec `prepare-offline.ps1 -Engineering`. Le kit runtime livré ne contient pas cette option et la refuse avant installation.

Pour une installation isolée, préparer les paquets Python et NuGet sur un poste autorisé. Puis fournir le répertoire NuGet local :

```powershell
.\scripts\install-tia-mcp.ps1 -Offline -PackageSource 'D:\Packages\nuget'
.\scripts\setup.ps1 -Engineering
```

Ces deux commandes supposent un kit préparé avec `-Engineering` et un répertoire NuGet contenant le paquet épinglé et ses dépendances requises par l'installation. Les wheels du kit doivent correspondre à l'OS, l'architecture et la version Python. Ne pas supposer que des wheels Linux conviennent à Windows. Le mode `-Offline` fournit à NuGet une configuration avec uniquement la source locale ; aucune source réseau n'est conservée.

## 2. Déclarer la copie de travail

Exemple à adapter au chemin réellement créé et ouvert dans TIA :

```powershell
$FatPython = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$FatMcp = (Resolve-Path '.\.tools\tia-mcp\tia-mcp.exe').Path
$FatSandbox = 'C:\FAT\Sandbox'
$FatProject = 'C:\FAT\Sandbox\UnitCopy\UnitCopy.ap21'
$FatPolicy = Join-Path (Get-Location) '.local\tia\policy.json'

& $FatPython -m integrations.tia_engineering --config $FatPolicy configure `
  --project $FatProject --sandbox-root $FatSandbox --server $FatMcp
& $FatPython -m integrations.tia_engineering --config $FatPolicy status
```

Le dossier sandbox et le fichier `.ap21` doivent exister. Les liens/jonctions sont résolus avant de vérifier que le projet reste dans le dossier autorisé. L'état renvoyé doit correspondre au **chemin exact** de la copie, et non simplement à son nom.

La configuration créée est en lecture seule. Elle produit aussi deux fragments relisibles, `claude.mcp.json` et `codex.mcp.toml`, à côté de la politique. Les archives et le journal d'ingénierie sont placés dans ce même espace local, hors du dossier binaire TIA. Le journal doit être un fichier `.jsonl` situé hors du dossier contenant le `.ap21`. Le CLI refuse aussi un fichier d'audit qui désigne le projet ou l'exécutable par un autre lien : une lecture ne doit pas pouvoir y ajouter des lignes de journal.

## 3. Connecter le client IA en lecture seule

Utiliser les commandes natives d'installation fournies par le serveur épinglé :

```powershell
& $FatMcp install claude-code --name tia-fat-readonly `
  --access-mode read-only --tia-project $FatProject --server-path $FatMcp

# Ou pour Codex :
& $FatMcp install codex --name tia-fat-readonly `
  --access-mode read-only --tia-project $FatProject --server-path $FatMcp
```

Lancer uniquement la commande correspondant au client souhaité. Le CLI upstream appelle le CLI natif du client ; il peut donc signaler qu'il est absent. Les fragments générés restent disponibles pour une configuration manuelle inspectable.

**Toujours fournir `--access-mode read-only`.** Le lancement brut `tia-mcp` upstream a un autre mode par défaut. Ne pas enregistrer notre CLI interactif comme outil d'écriture auprès du modèle, et ne pas substituer `read-write` ou `full` dans la configuration IA.

En lecture seule, l'assistant peut demander l'arbre de projet, la lecture de blocs, types et tables de tags, les références croisées et les diagnostics de lecture exposés par le serveur. Le contenu disponible dépend du langage, de la protection du bloc et de la version Openness. L'absence d'un export n'est jamais interprétée comme un bloc vide.

Un serveur MCP local ne rend pas le modèle IA local. Si Claude Code ou Codex utilise un modèle hébergé, les extraits fournis au modèle peuvent quitter le poste. Le mode démo/FAT reste autonome ; le choix d'un client IA et de ses données doit suivre la politique de l'organisation.

## 4. Exporter un bloc et préparer une proposition

Les commandes ci-dessous n'altèrent pas le projet TIA :

```powershell
& $FatPython -m integrations.tia_engineering --config $FatPolicy tree
& $FatPython -m integrations.tia_engineering --config $FatPolicy tags --plc PLC_1
& $FatPython -m integrations.tia_engineering --config $FatPolicy export `
  --block 'PLC_1/Main' --format source --output '.local\tia\review-main'
```

`tree` lit toutes les pages de l'arbre dans **une seule session MCP**, puis renvoie un objet avec `status`, `snapshot`, `query`, `nodes`, `pages` et `warnings`. Les curseurs v3 de l'amont sont conservés en mémoire du processus : ils ne sont pas réutilisables par une deuxième invocation du CLI. L'ancien argument `--cursor` est donc refusé avec une consigne de relancer `tree` sans curseur. Le CLI vérifie la cible, le snapshot, les offsets, les séquences, les parents et le nombre total de nœuds ; une réponse incomplète ou incohérente ne devient pas un arbre présenté comme complet.

L'export crée un dossier neuf contenant :

| Fichier | Rôle |
| --- | --- |
| `before.scl` ou `before.xml` | Export de référence, à conserver intact. |
| `after.scl` ou `after.xml` | Proposition modifiable par l'ingénieur ou l'assistant. |
| `proposal.json` | Chemin exact du projet et du bloc, format, hash de référence upstream, SHA-256 du contenu, date et version du serveur. |

`--format source` est adapté aux blocs SCL et DB globaux exportables. Pour un bloc graphique pris en charge, utiliser `--format xml` et examiner le XML. Le CLI ne convertit pas arbitrairement un LAD en SCL. Modifier seulement le fichier `after.*`, puis afficher le diff :

```powershell
& $FatPython -m integrations.tia_engineering --config $FatPolicy diff `
  --proposal '.local\tia\review-main'
```

Le diff est également conservé dans `change.diff`. Si le fichier `before.*` a été modifié, le CLI refuse de poursuivre ; effectuer un nouvel export. Si le projet TIA change entre-temps, le hash upstream bloque l'import.

## 5. Autoriser puis appliquer depuis un terminal humain

L'activation d'écriture est distincte de l'approbation d'une modification :

```powershell
& $FatPython -m integrations.tia_engineering --config $FatPolicy enable-write
& $FatPython -m integrations.tia_engineering --config $FatPolicy apply `
  --proposal '.local\tia\review-main'
```

`enable-write` demande de recopier une phrase contenant le chemin exact de la copie. L'activation ne change pas le mode des clients IA. `apply` exige une entrée et une sortie de terminal interactives ; il refuse les approbations envoyées par un pipe.

Séquence d'application :

1. Vérifier la politique, le chemin de sandbox, l'attachement TIA, l'absence de modifications non sauvegardées et le hash du bloc exporté.
2. Appeler `plc_write` avec **`dryRun:true`**, conserver `preview.json`, afficher le diff complet et les gardes upstream.
3. Demander une phrase d'approbation contenant le chemin et un préfixe SHA-256 du contenu proposé. Refuser ici ne modifie pas le projet.
4. Prévisualiser puis créer une archive `.zap21` avec le serveur existant. L'upstream demande sa propre confirmation de cycle de vie, transmise au terminal humain. Le CLI vérifie le fichier non vide et journalise son SHA-256.
5. Relire la cible et le bloc. Si quelque chose a changé, arrêter avant l'import.
6. Importer **une seule** mise à jour de bloc existant avec `expectedContentHash`. Le serveur peut compiler/vérifier lors de cet import ; l'approbation le mentionne explicitement.
7. Demander séparément l'autorisation de compiler l'ensemble du logiciel PLC. Les erreurs et avertissements sont conservés ; `isError:false` dans MCP ne suffit pas à déclarer le succès.
8. Proposer une sauvegarde seulement après compilation réussie. La sauvegarde comporte une confirmation et une vérification de la cible.

Le parcours produit `receipt.json` avec les diagnostics, la sauvegarde préalable et le résultat. Si l'import a réussi mais que la compilation est refusée ou échoue, la copie peut être **modifiée en mémoire**. Examiner TIA ; le CLI ne prétend ni avoir annulé, ni avoir enregistré ces modifications.

Le succès de compilation exige un rapport présent et cohérent : au moins un PLC, des compteurs entiers non négatifs, des totaux concordants et aucun état d'erreur masqué dans un PLC. Un résultat manquant, contradictoire ou omis reste un échec de vérification. Ces gardes locales sont alignées sur le contrat standalone de l'amont **v4.3.0** ; leurs tests injectent notamment des réponses malformées, sans prétendre que le serveur amont conforme les produit.

Une compilation seule peut être demandée avec :

```powershell
& $FatPython -m integrations.tia_engineering --config $FatPolicy compile
```

Cette commande archive d'abord une copie déjà sauvegardée et demande l'accord de compilation. En fin de session :

```powershell
& $FatPython -m integrations.tia_engineering --config $FatPolicy disable-write
```

## Traçabilité et reprise

Le journal JSONL enregistre l'heure UTC, l'utilisateur Windows, le PID, la cible, les appels et arguments, les réponses, les approbations et les hashes. Chaque entrée est vidée sur disque avant de continuer. Les sources peuvent apparaître dans ce journal : c'est une donnée de projet à protéger et à ne pas committer par défaut. Les journaux upstream restent sous `%LOCALAPPDATA%\TiaMcpServer\audit` selon sa documentation.

En cas de perte du worker, refus Siemens, timeout, écriture partielle ou erreur de vérification : **aucun nouvel essai automatique**. Lire `receipt.json`, inspecter le projet ouvert et décider de conserver les changements, restaurer l'archive ou réexporter une proposition. Une archive non vide et hachée doit encore être testée en restauration TIA pendant la qualification initiale.

## Limites explicites

- Le parcours contrôlé met à jour un bloc existant. La création massive de tags, de matériels, de réseaux et de projets n'est pas exposée par ce CLI.
- Aucun outil du CLI ne réalise de téléchargement, de RUN/STOP CPU, de contrôle en ligne ou d'écriture matérielle. Le runtime FAT utilise son adaptateur OPC UA séparé.
- Le serveur upstream prend en charge d'autres fonctions ; elles ne sont pas ajoutées au parcours contrôlé par leur seule existence.
- Le compte Windows qui possède les fichiers peut modifier la politique ou le programme. Les gardes préviennent des erreurs et encadrent la revue ; elles ne rendent pas le système inviolable contre ce même compte.
- Les tests locaux vérifient la politique et le protocole contre des doubles. La présence de TIA V21, les exports et la compilation réelle sont à qualifier sur le poste cible, conformément à [COMPATIBILITY.md](COMPATIBILITY.md).

## Vérifier les contrôles sans Siemens

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_engineering.py -q
```

Avec l'extra `engineering`, la suite inclut un sous-processus de serveur MCP officiel factice et un vrai échange stdio. Elle vérifie aussi les refus en lecture seule, les cibles différentes, les sources périmées, une archive manquante, une confirmation rejetée, l'absence de terminal et les erreurs de compilation. Aucun de ces tests ne se connecte à un automate ou à TIA.
