# Ouvrir, fermer et mettre à jour le portable

Extraire tout le ZIP dans un dossier accessible en écriture, puis ouvrir **Start-FAT.cmd** ou **Vanguard-FAT-Studio.cmd**. Le portable contient Python ; aucune installation Python ni commande PowerShell n’est nécessaire.

Le double-clic ouvre une petite fenêtre Windows avec l’état du service. Quand elle affiche **Prêt**, le navigateur ouvre FAT Studio. **Ouvrir FAT Studio** permet de retrouver l’interface si l’onglet a été fermé. Un second double-clic sur le même portable retrouve l’instance déjà ouverte, pour le même dossier de données et le même port. La fenêtre du lanceur peut être réduite.

**Quitter** arrête le service local et ferme ses fichiers. Enregistrer les brouillons utiles dans le navigateur avant de confirmer. Fermer l’onglet du navigateur ne quitte pas le service. L’arrêt conserve les essais et leur historique ; il ne commande pas le RUN/STOP d’une CPU.

**Ouvrir le dossier de données** donne accès aux projets, à l’historique et au journal `portable-launcher.log`. Le dossier habituel reste `%LOCALAPPDATA%\FATStudio`. Les données restent hors du dossier scellé du portable. La variable `FAT_STUDIO_DATA` et l’option `--data-dir` permettent de choisir un autre emplacement.

## Mise à jour guidée

1. Cliquer **Mise à jour**. Cette action consulte les releases publiques du dépôt GitHub officiel ; aucune recherche de mise à jour n’est lancée au démarrage.
2. Relire le portable proposé, sa release et son empreinte SHA-256. Confirmer le téléchargement pour préparer une nouvelle copie à côté du portable courant. Si le dossier de destination existe déjà, l’opération s’arrête sans le remplacer.
3. Le lanceur compare la taille et le SHA-256 publiés par GitHub, contrôle les chemins du ZIP puis vérifie chaque fichier du manifeste avec son propre vérificateur. Aucun programme de la nouvelle copie n’est exécuté pendant ces contrôles.
4. Quand la nouvelle copie est prête, enregistrer les brouillons et cliquer **Utiliser la mise à jour**. Après confirmation, le lanceur attend la fermeture du service courant puis ouvre la nouvelle copie avec le même dossier de données et le même port. Aucun essai ne reprend automatiquement.

L’ancien portable reste disponible. Une erreur de réseau, de téléchargement ou d’intégrité conserve la version courante et les données. Une mise à jour préparée n’est pas appliquée avant le choix explicite de l’utilisateur. Si les versions emploient des formats de données différents, consulter les notes de release avant de revenir à une ancienne version.

Le téléchargement doit être un asset `Vanguard-FAT-Studio-Windows-x64-….zip` du dépôt `vandervan0001/Vanguard-FAT-Studio`, accompagné du digest SHA-256 fourni par GitHub. Les limites du lecteur sont de 300 Mio compressés, 1 200 Mio décompressés et 12 000 entrées. Les liens, chemins absolus, chemins traversants, noms Windows réservés et doublons insensibles à la casse sont refusés. Ces contrôles vérifient le transfert et l’assemblage ; ils ne constituent pas une signature de l’éditeur.

## Diagnostic et automatisation

Les arguments explicites conservent le fonctionnement en console, utile pour les tests et l’automatisation. Depuis le dossier portable :

```powershell
.\Start-FAT.cmd --check
.\Start-FAT.cmd --no-browser --port 8784 --data-dir C:\FAT-essai
.\runtime\python.exe -B -X utf8 .\launch.py --status --port 8784 --data-dir C:\FAT-essai
.\runtime\python.exe -B -X utf8 .\launch.py --quit --port 8784 --data-dir C:\FAT-essai
```

`--check` contrôle le manifeste puis quitte sans ouvrir de serveur. `--no-browser` démarre le serveur en console ; `Ctrl+C` le ferme. `--gui` demande la fenêtre native Windows. `--status` et `--quit` ne visent que l’instance authentifiée de ce portable et de ce dossier ; ils refusent une autre version ou une réponse incompatible. Aucune commande ne tue un processus à partir d’un PID enregistré.

Un port occupé par un autre service bloque le démarrage. Un autre portable utilisant le même dossier doit être fermé depuis sa propre fenêtre avant de changer de version. Un ancien fichier d’identité ne suffit pas à autoriser une action : le lanceur vérifie le service par une requête locale signée, et un verrou système empêche deux lanceurs de prendre le même dossier.

Les opérations de démonstration et la préparation du projet TIA restent décrites dans le [guide utilisateur](USER_GUIDE.md) et le [guide d’installation](INSTALLATION.md).
