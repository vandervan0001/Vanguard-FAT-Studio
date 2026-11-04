# Conserver et restaurer un projet entier

Un projet FAT peut rester dans un dossier local et se transmettre comme un fichier **`.fat.zip`**. Le ZIP contient la configuration du projet et les preuves de ses essais. Il se distingue du JSON de projet, qui décrit la configuration sans son historique.

## Depuis l’interface

1. Enregistrer le projet actif. Une archive doit porter la configuration que vous souhaitez conserver.
2. Ouvrir **Ouvrir → Exporter l’archive FAT**.
3. Choisir le dossier et le nom de sauvegarde proposés par votre navigateur. Conserver l’extension `.fat.zip`.
4. Pour récupérer ce dossier de travail, utiliser **Ouvrir → Restaurer une archive FAT** et sélectionner ce fichier.
5. Le banc vérifie tout le conteneur avant restauration. Il crée un nouveau dossier local, l’ouvre **au repos**, puis affiche son projet et son historique.
6. L’ancien espace reste présent dans **Dossiers FAT locaux**. Le rouvrir explicitement si vous souhaitez y revenir.

La restauration ne fusionne pas deux historiques et n’écrase pas un essai existant portant le même ID. Elle prépare un dossier temporaire neuf, ferme son stockage, puis le publie par renommage. Un échec de préparation n’active pas le dossier incomplet. Le serveur persiste le choix de l’espace actif pour sa prochaine ouverture.

Une archive peut être capturée pendant un essai : le serveur copie la configuration et épingle une transaction SQLite de lecture seule commune à tout l’historique sélectionné. La compression s’exécute ensuite dans un worker, hors de la boucle HTTP ; une demande d’arrêt du banc reste disponible pendant ce travail. Le lecteur garde sa vue même après de nouveaux échantillons, un arrêt ou la fermeture du stockage d’origine. Pour un dossier de clôture, terminer/arrêter l’essai puis réexporter. La préparation d’une archive n’arrête pas une CPU externe.

## Créer un dossier et l’archiver depuis le terminal

Le terminal humain peut préparer un dossier neuf sans ouvrir le navigateur ni connecter une cible. Avec le Python correspondant à votre distribution :

```powershell
$FatPython = (Resolve-Path '.\runtime\python.exe').Path
# Sources : $FatPython = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$FatProjects = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'FAT'
$FatProject = Join-Path $FatProjects 'Mon projet'
& $FatPython -B -X utf8 -m fat_studio new-project $FatProject --name 'Mon projet' --demo
& $FatPython -B -X utf8 -m fat_studio archive-create --data-dir $FatProject --output (Join-Path $FatProjects 'Mon projet.fat.zip')
& $FatPython -B -X utf8 -m fat_studio archive-restore (Join-Path $FatProjects 'Mon projet.fat.zip') --output (Join-Path $FatProjects 'Mon projet restaure')
```

Omettre `--demo` crée un projet vide. Les dossiers de destination et noms d’archive doivent être nouveaux ; aucune commande ne remplace un dossier existant. `archive-create` vise un dossier dont le serveur est fermé. Le verrou du stockage refuse sa prise en parallèle d’un serveur actif.

Avec un serveur déjà ouvert, utiliser plutôt le client local après découverte et capture du contexte selon [AI_QUICKSTART.md](AI_QUICKSTART.md) :

```powershell
& $FatPython @FatApi archive-export --output (Join-Path $FatDemo 'exports\projet.fat.zip')
# Arrêter ou mettre en pause l’essai avant cette sélection explicite :
& $FatPython @FatApi archive-import (Join-Path $FatDemo 'exports\projet.fat.zip')
& $FatPython @FatApi workspace
& $FatPython @FatApi runs
```

Le contexte est mis à jour après la restauration réussie. Une commande préparée dans l’ancien espace devient périmée, même si les deux projets possèdent le même ID et le même JSON. Aucun réessai automatique n’est effectué.

## Contenu du fichier

| Chemin dans le ZIP | Contenu |
| --- | --- |
| `manifest.json` | `format:"fat-studio/archive"`, `version:"1.0"`, ID du projet et liste des fichiers avec taille/SHA-256 |
| `project.json` | Enveloppe `fat-studio/project` : P&ID, paramètres, animations, variables, mapping et scénarios |
| `scenarios.json` | Copie versionnée des scénarios du projet archivé |
| `mapping.csv` | Mapping CSV exporté avec son encodage réversible |
| `runs/<id>/evidence.json` | Projet/scénario de l’essai, résultat saisi, connexion documentaire, événements et mesures |
| `runs/<id>/samples.csv` | Les mêmes mesures, bornées au même instantané |
| `runs/<id>/report.html` | Rapport généré depuis le même instantané fini |

L’archive sélectionne **tous les essais du seul projet courant**, y compris au-delà des 500 entrées que la liste d’historique peut afficher. Elle ne copie pas la base SQLite globale. Les identifiants d’essais, d’échantillons et d’événements, les horodatages et les décisions humaines enregistrées restent conservés. Les autres projets et leurs essais ne sont pas inclus.

Les fichiers de clé/certificat privés, secrets de l’environnement, licences Siemens et politique d’autorisation machine ne sont jamais collectés. Le format ne contient pas de sources de programme PLC ou de bibliothèque de programmation. Une configuration ou une observation peut cependant contenir le texte que son auteur a saisi : relire l’archive avant de la transmettre. Ce format n’est pas un outil de détection de secrets dans les commentaires libres.

Le schéma du manifeste est [archive.schema.json](../examples/archive.schema.json). Les enveloppes JSON sont décrites dans [FORMAT.md](FORMAT.md).

## Ce qui est rétabli

Le projet restauré garde son identité, son dessin, ses variables, ses scénarios et ses animations. Sa connexion active revient en **démonstration**, sans référence d’authentification ou autorisation de cible importée. Les informations de connexion contenues dans les anciens essais restent des éléments historiques ; elles ne provoquent aucune connexion.

Un essai fermé conserve son statut et sa fin d’origine. Un essai encore ouvert à la capture est restauré comme **interrompu**, avec la date de capture comme borne de cette copie figée ; il ne reprend jamais ses écritures. L’archive source exacte est conservée sous `archive-source.fat.zip` dans le dossier restauré : elle garde le statut et les bornes d’origine pour la traçabilité. Ce classement technique ne crée aucune observation ni verdict humain.

Les autorisations machine restent celles du poste. Pour une nouvelle cible OPC UA, refaire la vérification humaine du contrat, des identités, du certificat et des NodeIds ; importer une archive ne l’autorise pas. Les opérations du banc ne commandent ni téléchargement, ni RUN/STOP CPU.

## Contrôles du conteneur

Avant toute restauration, le lecteur vérifie format/version, projet, types, scénarios, mapping, identités et bornes des preuves, liste exacte des fichiers, tailles et SHA-256. Il refuse chemins absolus ou traversants, noms ambigus Windows, doublons y compris casse différente, liens, fichiers non attendus et ZIP chiffrés. Il compare le CSV aux preuves JSON ; l’HTML reste un document exporté, jamais exécuté comme composant de l’interface.

Les limites de cette version sont **100 Mio compressés**, **250 Mio décompressés**, **100 Mio par fichier**, **3 000 entrées** et un ratio maximal de décompression de **1 000**. Une archive trop grande est refusée avant activation. Une très longue campagne peut demander plusieurs dossiers de travail ; ne pas enlever les contrôles pour l’importer.

Le manifeste détecte une corruption ou une incohérence ; il ne prouve pas l’auteur ni l’authenticité de mesures provenant d’un tiers. Ne pas ouvrir automatiquement un rapport HTML reçu d’une source inconnue.

## API et module local

`GET /api/project/archive` télécharge l’archive sélectionnée. `POST /api/project/archive/import` reçoit son binaire ZIP, avec les mêmes gardes de jeton/projet/révision/essai que les autres mutations. Il retourne le projet au repos après l’ouverture du nouvel espace. Lire [AI_CONTROL.md](AI_CONTROL.md) pour le protocole de contexte.

Le module `fat_studio.archive` fournit les fonctions suivantes :

- `capture_archive(store, project) -> ArchiveSnapshot` épingle rapidement une lecture SQL indépendante et une copie profonde du projet. `project`, `run` et `samples` lisent ensuite cette même vue ; `close()` appartient au worker après sa fin réelle, y compris en cas d’annulation HTTP.
- `export_archive(store_ou_snapshot, project) -> bytes` assemble les fichiers et preuves sélectionnés.
- `prepare_archive(payload) -> ArchivePlan` valide sans écrire ni contacter de cible.
- `restore_archive(store, plan) -> Project` exige un Store neuf, sans projet, essai ou politique. L’appelant publie ce dossier seulement après sa fermeture.

La transaction SQLite protège l’insertion des essais et de leurs preuves ; elle ne rend pas les fichiers et SQLite atomiques ensemble. La publication d’un dossier neuf après préparation évite de modifier l’espace existant. Le logiciel n’annonce pas de fusion ou d’annulation d’écriture OPC UA.
