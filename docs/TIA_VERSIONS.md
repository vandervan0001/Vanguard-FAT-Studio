# Choisir TIA Portal V20 ou V21

FAT Studio 0.2.0 permet de choisir **V20** ou **V21** dans **Connexion → Version du projet TIA**. Le choix est enregistré, exporté et réimporté avec le projet FAT. Les anciens projets sans ce champ utilisent V21. Le sélecteur est verrouillé pendant un essai. Il ne convertit pas un projet Siemens ; la copie ouverte dans TIA et la passerelle installée doivent correspondre à la version choisie.

Le moteur FAT échange toujours par OPC UA. Le choix de version concerne le projet d'ingénierie et sa passerelle Openness ; il ne découvre pas les NodeIds ou les droits d'une CPU.

## Profils d'ingénierie

| Choix | Passerelle | Projet / archive | État de qualification |
| --- | --- | --- | --- |
| V21 | Czarnak `TiaMcpServer 4.3.0`, paquet NuGet épinglé | `.ap21` / `.zap21` | Contrats testés localement ; essais Siemens sur le poste à effectuer |
| V20 | Même source Czarnak épinglée, adaptation locale et compilation contre les DLL Openness V20 installées | `.ap20` / `.zap20` | Candidat de portage : transformation et gardes testées ; compilation et fonctionnement natifs V20 à vérifier sur Windows |

Le code amont 4.3.0 cible V21. Le profil V20 adapte ses chemins de découverte, extensions de projet/archive et identifiants XML, puis demande une vraie compilation avec les références V20. La compilation peut révéler une API incompatible : l'installation doit alors s'arrêter et le diagnostic doit être traité. Aucun serveur V21 ou référence factice n'est accepté comme repli V20.

Les deux profils sont installés dans des dossiers distincts. Le manifeste local `fat-tia-profile.json` enregistre version, révision source, transformation éventuelle et empreintes du host, du worker et des trois DLL Siemens utilisées. Il est obligatoire pour les deux versions. Un exécutable déjà présent sans ce manifeste est refusé ; choisir une destination neuve. Ce manifeste est un contrôle de cohérence locale, pas une signature d'éditeur ou une preuve d'acceptation Siemens.

## Préparer le poste Windows

Prérequis : Python 3.12 x64, TIA Portal de la version choisie avec Openness, droits du groupe `Siemens TIA Openness`, SDK .NET 10 stable au moins 10.0.400 et .NET Framework 4.8. Le build V20 demande aussi les références de compilation .NET Framework 4.8 et Git. TIA, ses DLL et ses licences s'installent séparément.

Depuis un clone source connecté, après installation du runtime FAT :

```powershell
.\scripts\setup.ps1 -Engineering

# Un menu demande V20 ou V21 si -TiaVersion est omis.
.\scripts\install-tia-mcp.ps1

# Ou un choix explicite :
.\scripts\install-tia-mcp.ps1 -TiaVersion V20
.\scripts\install-tia-mcp.ps1 -TiaVersion V21
```

Pour un emplacement Siemens non standard, fournir `-OpennessDirectory` avec le dossier contenant les trois DLL `Siemens.Engineering.Base.dll`, `Siemens.Engineering.Step7.dll` et `Siemens.Engineering.WinCCUnified.dll`. L'installateur vérifie leur version majeure réelle et leurs empreintes avant et après le build. Le lancement MCP et les fragments client conservent ce dossier via la variable `TiaPortalV20Dir` ou `TiaPortalV21Dir` du profil.

Le profil V20 utilise exactement le commit `10c5de2eb44c0362792cd141370b3f42f92f6ecd`. Il prépare un clone dédié, conserve sa licence et produit un rapport de transformation avant compilation. Les références factices sont interdites. Le build, le contrôle `--version` et `doctor` doivent réussir avant l'enregistrement du profil. Les DLL Siemens ne sont pas copiées dans le serveur publié.

Hors ligne : V21 demande une source NuGet locale avec le paquet 4.3.0. Pour V20, fournir aussi `-SourceDirectory` avec un clone dédié propre du commit exact et les dépendances NuGet nécessaires au build. Une source déjà modifiée n'est pas restaurée ou nettoyée automatiquement. Le kit runtime Windows 0.1.1 d'origine reste intact ; il ne contient pas ces deux installations d'ingénierie.

## Configurer la copie choisie

Ouvrir et sauvegarder d'abord une copie de développement dans la bonne version de TIA. Exemple V20 ; adapter les chemins aux fichiers réellement créés :

```powershell
$FatPython = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$FatMcp = (Resolve-Path '.\.tools\tia-mcp-v20\TiaMcpServer.exe').Path
$FatProject = 'C:\FAT\Sandbox\V20\UnitCopy\UnitCopy.ap20'
$FatPolicy = Join-Path (Get-Location) '.local\tia\v20\policy.json'

& $FatPython -m integrations.tia_engineering --config $FatPolicy configure `
  --tia-version V20 --project $FatProject --sandbox-root 'C:\FAT\Sandbox\V20' --server $FatMcp
& $FatPython -m integrations.tia_engineering --config $FatPolicy status
```

Pour V21 : utiliser `.tools\tia-mcp-v21\tia-mcp.exe`, une copie `.ap21`, `--tia-version V21` et une politique distincte dans `.local\tia\v21`. Les anciennes politiques JSON sans `tia_version` restent interprétées comme V21, mais exigent désormais un serveur V21 avec manifeste vérifié.

Les fragments générés à côté de chaque politique sont `codex.v20.mcp.toml` et `claude.v20.mcp.json`, ou leurs équivalents V21. Le nom de serveur MCP est `tia-fat-v20-readonly` ou `tia-fat-v21-readonly`. Intégrer le fragment dans la configuration du client en conservant ses autres serveurs, y compris la section d'environnement : elle fixe le dossier Openness vérifié. Recharger ensuite les connexions MCP du client. Les fragments seuls n'activent pas un client IA sur un autre ordinateur.

Les propositions contiennent la version et le profil d'origine. Une politique, une proposition, un acquittement ou une archive d'une autre version est refusé. L'archive attendue est `.zap20` ou `.zap21` selon le profil ; la présence d'une archive d'un autre suffixe ne suffit pas pour autoriser l'import.

## Revue, application et acceptation

Le client IA reste en lecture seule. Le parcours humain d'export, modification de `after.*`, diff, archive, import, compilation et sauvegarde est décrit dans [TIA_MCP.md](TIA_MCP.md). Les confirmations existantes s'appliquent aux deux versions. Le serveur FAT n'expose pas ces écritures par HTTP.

Sur chaque poste/version, suivre [ACCEPTANCE.md](ACCEPTANCE.md) : identité de la copie ouverte, lecture/export, refus d'une proposition périmée, archive réellement restaurable, import et diagnostics de compilation. Les tests de protocole et le build ne valident pas le comportement du programme PLC. Les résultats locaux 0.2.0 sont dans le [rapport V20/V21](../evidence/reprises/2026-11-02-v20-v21/VERIFICATION.md).
