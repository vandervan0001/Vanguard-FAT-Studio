# Poste Windows préparé sans Siemens

Installation du 2 novembre 2026 dans `C:\FAT_Studio`, depuis le dépôt privé `vandervan0001/FAT-Studio`. Le runtime reste en version 0.2.1. TIA Portal, Openness et PLCSIM ne sont pas installés.

## Ouvrir le banc

Double-cliquer sur le raccourci **FAT Studio** du bureau, ou sur `C:\FAT_Studio\Start-FAT.cmd`. Le navigateur ouvre `http://127.0.0.1:8765`. Garder la fenêtre du serveur ouverte ; Ctrl+C arrête le banc.

Les essais personnels créés par ce lancement seront enregistrés dans `%LOCALAPPDATA%\FATStudio`. Les vérifications de cette session utilisent des dossiers temporaires ou `.local/`, sans essai dans ce dossier personnel. Aucune cible PLC n'est autorisée.

Choisir **Cycle de référence**, puis **Démarrer** pour essayer la démonstration. Le contrôleur de démonstration est distinct du programme Siemens qui sera raccordé ultérieurement. Les verdicts humains des essais automatiques sont restés `not_evaluated`.

## Développer sur ce poste

Python 3.12.10 x64 était déjà installé. Les dépendances verrouillées runtime, développement et MCP sont dans `.venv`. Node.js 22.23.4 avec npm 10.9.9 et le SDK .NET 10.0.403 sont installés dans `.tools`, sans modification du PATH système.

Depuis PowerShell :

```powershell
Set-Location C:\FAT_Studio
. .\.local\dev-env.ps1
python -m fat_studio doctor --json
python -m ruff check fat_studio integrations tests scripts
python -m pytest

Push-Location frontend
npm.cmd run build
Pop-Location
python scripts/build-web.py

Push-Location frontend
npm.cmd test
Pop-Location
```

Le script `.local/dev-env.ps1` et les outils `.tools/` appartiennent à ce poste et sont ignorés par Git. Après un clone neuf ailleurs, suivre les commandes standard de [l'état de reprise](codex/ETAT_REPRISE.md). Après un changement applicatif ou des assets, réinstaller le paquet avant de vérifier sa distribution installée.

## Préparation TIA disponible

La source Czarnak 4.3.0 est conservée propre dans `.tools/tia-upstream`, au commit `10c5de2eb44c0362792cd141370b3f42f92f6ecd`. Les dépendances NuGet du host et du worker net48, les références .NET Framework 4.8 et le paquet V21 sont disponibles dans `.tools/nuget-offline`. Une restauration dans un cache neuf, avec cette seule source locale, a réussi. Cela vérifie les dépendances ; aucun serveur TIA n'a été compilé contre des DLL Siemens et aucun profil n'a été créé.

Après installation de la version Siemens choisie avec Openness, ouvrir un terminal et charger `.local/dev-env.ps1`. Pour V21 :

```powershell
.\scripts\install-tia-mcp.ps1 -TiaVersion V21 `
  -Offline -PackageSource C:\FAT_Studio\.tools\nuget-offline
```

Pour V20, conserver le clone de référence intact et créer d'abord une copie dédiée :

```powershell
git clone --no-hardlinks .tools/tia-upstream .tools/tia-v20-source
if ($LASTEXITCODE -ne 0) { throw 'Verifier le clone avant de continuer.' }
.\scripts\install-tia-mcp.ps1 -TiaVersion V20 `
  -SourceDirectory C:\FAT_Studio\.tools\tia-v20-source `
  -Offline -PackageSource C:\FAT_Studio\.tools\nuget-offline
```

Ces commandes exigent les trois vraies DLL Openness de la version choisie. L'installateur conserve ses refus de références factices et de versions croisées. La restauration préparée ici n'établit pas la compatibilité native V20. Suivre ensuite [TIA_VERSIONS.md](TIA_VERSIONS.md), le [prompt de validation Windows](codex/PROMPT_VALIDATION_WINDOWS_TIA_V20_V21.md), puis [ACCEPTANCE.md](ACCEPTANCE.md) sur une copie autorisée du projet.

## Vérifications et récupération

Les [preuves du poste](../evidence/reprises/2026-11-02-windows-local/VERIFICATION.md) identifient les tests réellement exécutés, les limites Windows et les contrôles d'installation. Les sources, la documentation et les preuves sont conservées dans la branche locale `codex/windows-local-setup`. Les outils ignorés par Git restent dans ce dossier de travail.

Le kit d'exécution hors ligne utilise Python 3.12 x64 et contient les dépendances runtime et MCP. Il ne contient ni Siemens, ni ses licences. La sauvegarde Git ne contient pas les données personnelles d'essai ; sauvegarder `%LOCALAPPDATA%\FATStudio` séparément, serveur arrêté, lorsqu'il contiendra des essais.

Le kit final neuf est dans `C:\FAT_Studio-Offline-2026-11-02` ; son manifeste est vérifié et ses fichiers applicatifs correspondent aux sources testées. Le kit de validation installé reste séparé dans `C:\FAT_Studio-Offline-Validation-2026-11-02`. Garder ces kits intacts et poursuivre les modifications dans `C:\FAT_Studio`.

`C:\FAT_Studio-Delivery-2026-11-02` contient la sauvegarde Git et le ZIP complet du kit. Le bundle a été recloné et vérifié ; le ZIP a passé son contrôle CRC. Le fichier `delivery.json` et `SHA256SUMS.txt` identifient les artefacts et leurs empreintes.
