# Film P&ID, 4 novembre 2026

Le montage de 49 secondes donne la priorité à la construction du P&ID et à l’essai du circuit qui vient d’être construit. Le travail part du bundle UI vérifié au commit `f5ad062cfc9babbd2ab61d22ee55528ad0fc7979`. Le code produit et les kits scellés ne sont pas modifiés. La note locale Windows présente au départ reste en place.

Les sources du film sont dans `.local/vanguard-pid-film-2026-11-04/film/`, une copie isolée du ZIP média. La prise UI a créé une cuve, une pompe et une vanne, tracé deux conduites, associé les paramètres de débit et lié la rotation de la pompe à son retour marche. L’essai temporisé a satisfait trois contrôles. Le niveau est passé de 25 % à environ 66 % avant que le défaut moteur arrête le remplissage. Un STEP distinct a écrit le défaut simulé et le retour marche est passé à FALSE. Aucune observation ni conclusion humaine n’a été saisie.

Le reçu de capture est `film/capture-receipt.json`. L’instance de capture 127.0.0.1:8775 utilisait un dossier jetable et a été arrêtée proprement. Les autres services et les essais Siemens n’ont pas servi aux prises.

Le brouillon et le master ont chacun passé 29 contrôles. La revue des images décodées a conduit à resserrer les cadrages du tracé, du déroulé et du STEP, et à exclure trois images où l’affichage du retour marche avait un retard sur la lecture du banc. Le master compte 1 470 images en 1080 × 1350 à 30 images/s. Les deux MP4 ont la même piste vidéo. La planche du master a été relue et le ZIP de 66 entrées a été vérifié contre son manifeste. Le dossier `film/exports/` contient les livrables et `verification.json`.

Pour refaire le rendu, partir de cette copie ou du ZIP média. Installer les dépendances avec `npm ci --legacy-peer-deps --ignore-scripts` puis exécuter `npm run subtitles`, `npm run master` et `npm run check -- --master`. Fournir Chromium et FFmpeg/FFprobe dans l’environnement de rendu. Vérifier la disponibilité sur la [version d’aperçu](https://github.com/vandervan0001/Vanguard-FAT-Studio/releases/tag/public-preview-2026-11-04).

Les deux MP4, le SRT et le ZIP de sources ont été ajoutés à cette version d’aperçu. Leurs tailles et SHA-256 distants correspondent aux fichiers locaux. Le reçu est `.local/vanguard-pid-film-2026-11-04/publication-receipt.json`. Les liens précédents restent disponibles et la page de l’aperçu présente le nouveau montage en tête.
