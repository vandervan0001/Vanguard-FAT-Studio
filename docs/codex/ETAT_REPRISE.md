# Vanguard FAT Studio : état de reprise

## Version 0.3.0, 9 novembre 2026

L’accueil, la démonstration manuelle sans automate, les circuits et transferts, les diagnostics ciblés, la revue des tags, la fusion CSV, l’exploration OPC UA en lecture seule et la récupération des brouillons sont documentés dans la [note 0.3.0](sessions/2026-11-09-ux-0.3.0.md). Le portable propose une fenêtre Windows pour ouvrir, fermer et préparer une mise à jour dans une nouvelle copie vérifiée.

Consulter le [changelog](../../PUBLIC_CHANGELOG.md), le [guide utilisateur](../USER_GUIDE.md) et le [reçu de la release](https://github.com/vandervan0001/Vanguard-FAT-Studio/releases/tag/v0.3.0). Les sources du tag et le manifeste identifient cette livraison. Les paragraphes suivants sont des archives datées ; ils ne décrivent pas l’état actuel d’une machine ou d’un essai. Relire le contexte réel avant toute mutation.

## Aperçu public, 4 novembre 2026

Le README public présente le banc, le démarrage depuis les sources, la capture de démo, les guides Siemens et IA, et les contributions. Le code original conserve la licence MIT. La publication vise `main` et la [version d’aperçu](https://github.com/vandervan0001/Vanguard-FAT-Studio/releases/tag/public-preview-2026-11-04). Le film de lancement affiche la disponibilité sur GitHub et conserve les images de démonstration. Voir la [note de publication](sessions/2026-11-04-vanguard-public-preview.md).

## Demande en cours, 3 novembre 2026

Appliquer la DA du dépôt `vandervan0001/vanguard_systems`, renommer le produit et le dépôt GitHub en **Vanguard FAT Studio**, puis livrer une vidéo LinkedIn rythmée et sous-titrée, sans voix. Les standards et programmes privés restent exclus de Git et des paquets publics.

Branche source `codex/vanguard-fat-studio-brand`, HEAD initial `cd4daba16580309a675dfa6b1ec95efe5a669038`, changements précédents conservés. Checkpoint privé pré-DA : `.local/vanguard-brand-2026-11-03/source-checkpoint`, 588 fichiers et 31 593 648 octets vérifiés. Les anciennes livraisons PUBLIC/SOURCE du round 5, leurs ZIP et toutes les preuves historiques restent intacts.

## Produit et identité

DA reprise au commit `b4df8d8ed0942e98ceee643a9be210f00aca9e9f` du dépôt de marque : bleu `#0055DD`, surfaces pâles, Geist et logos originaux non recolorés. Sources étudiées : `app/[locale]/globals.css`, assets de logos et fontes/OFL. Aucune reprise du code applicatif du site. Les logos, trois fontes et OFL sont dans `frontend/public/brand/` et `fat_studio/web/brand/`.

Le nom humain est Vanguard FAT Studio, le paquet pip `vanguard-fat-studio`, avec les deux CLI `vanguard-fat-studio` et `fat-studio`. Le lanceur supplémentaire `Vanguard-FAT-Studio.cmd` délègue au lanceur existant. Les identifiants techniques, le module `fat_studio`, les formats `fat-studio/*`, les archives `.fat.zip`, URI de certificats et chemins de données compatibles sont conservés. Les anciens projets et essais ne sont pas réécrits pour changer leur marque.

Root : `fat_studio/branding.py`, API/montage `/brand`, rapports autonomes (logo + trois fontes embarquées), noms du client OPC UA et du verrou de données. Frontend : header, navigation, toutes vues, favicons, tokens et fontes. Distribution : métadonnées, docs courantes et sélection explicite. Le filtre autorise la marque et continue de refuser les signatures de programmes privés, secrets et modules non autorisés. Deux graphies Unicode privées ont été reproduites puis corrigées, sans élargir la sélection de fichiers.

## Vérifications round 6

- 75 tests ciblés archives/runtime/OPC UA réussis, puis 38 API réussis.
- 25 tests archives réussis, dont restauration exacte de l'ancienne archive native de 19 essais avec rapports et historique inchangés.
- Première globale : 579 Python réussis, cinq ignorés sous Windows pour privilège de liens symboliques absent. Deux régressions Unicode ajoutées ensuite ont passé la suite ciblée distribution/CLI/smoke (69 réussis, quatre ignorés). Dernière globale sur les sources corrigées : **581 réussis, cinq ignorés**, 234,41 s ; log privé `python-tests-sealed-source.log`, reçu public `software-verification.json`.
- Frontend final livré : 56/56 réussis, zéro échec/ignoré/flaky, 161,480624 s. Fenêtre Edge réelle et cadrage d'un cran : 1/1 chacun. Sources et douze fichiers livrés re-hachés stables. JS `index-CDBs7U1H.js`, SHA256 `cd411b8c23911c581ca3642fc92608a83555d25f224a9259fef675e6668a5ca9` ; CSS `index-6ra9f6L1.css`, SHA256 `35ced3e286c8c4be5e4f33a2fb0e6f1bedc4ab731742cf15d4457e59dd1d77b1`.
- Rapports HTML autonomes générés depuis un scénario de démo réellement exécuté : quatre attentes réussies, verdict humain non évalué. Captures 1440 et 390 pixels relues, trois fontes chargées, logo décodé, aucun script ni appel externe ni débordement horizontal.
- Nouveau nom du client lu sur la vraie CPU virtuelle déjà autorisée : 75 mappings validés, 19 sorties lues, SignAndEncrypt et certificat/URI d'origine, zéro écriture et zéro commande CPU. Preuve `native-read-only.json` ; cette lecture ne remplace pas une nouvelle campagne FAT.
- Prototype source installé hors ligne : deux alias CLI et cinq contrôles de service réussis. Prototype portable 3.12.10 isolé, PATH minimal et environnement Python piégé : deux lanceurs, cinq contrôles de service, ressources locales et rapport autonome validés, intégrité conservée. Prototypes temporaires libérés.

Preuves nouvelles : `evidence/reprises/2026-11-03-vanguard-brand/`. Les preuves round 5 restent : 31/31 attentes sur TIA V21/PLCSIM Advanced 8, 140 commandes client, archive de 19 essais restaurée ; aucune réception humaine ni qualification V20/CPU physique.

## Livrables vérifiés le 4 novembre 2026

- Portable Windows dans `C:/Vanguard_FAT_Studio_2026-11-03` et kit source dans `C:/Vanguard_FAT_Studio_Source_2026-11-03`. 3 209 fichiers portables et 592 fichiers source, dont 29 wheels. Cinq contrôles de service chacun, deux alias CLI, deux lanceurs et 19 appels du client public réussis. Le kit source a été installé sur une copie et les services de test ont été fermés.
- ZIP dans `.local/Vanguard_FAT_Studio_2026-11-03.zip` et `.local/Vanguard_FAT_Studio_Source_2026-11-03.zip`. Ensemble exact des entrées, CRC et SHA-256 de chaque fichier décompressé vérifiés. Voir `distribution/delivery-zips.json` dans les preuves de cette reprise. Les dossiers scellés contiennent l'état documentaire au moment de l'assemblage.
- Film dans `media/vanguard-fat-studio/exports/`. 45 s, 1080 × 1350, 30 images/s, sous-titres FR intégrés et SRT, musique originale ou silence. Les images de démo et la campagne Siemens du 3 novembre sont identifiées séparément. Planche relue à partir du master. 36 contrôles de rendu et 19 après extraction du ZIP de sources. Le serveur 8774 est fermé. Le contrôle automatique a refusé la suppression du dossier de données temporaires de capture. Ce dossier est hors livrables.
- GitHub a repris le nom `Vanguard-FAT-Studio` avec le même ID 1443049301. La visibilité était privée au renommage et l'API l'indique publique le 4 novembre. La [PR n° 1](https://github.com/vandervan0001/Vanguard-FAT-Studio/pull/1) a réuni le code et les médias sélectionnés. Les standards maison et fournisseurs sont hors périmètre de livraison.

## Services à préserver

Ancien 8768 et ancienne CPU réservés, aucune mutation. Le seul service 8770 a été arrêté proprement puis redémarré sur les sources brandées : worker 26580, session 86369, même dossier `.local/public-demo-2026-11-03/fat-data`. L'ancien essai de présentation a été clôturé avec son historique intact.

Root a créé une nouvelle copie locale `vanguard-live-20261103`, « Démo Vanguard · PLCSIM V21 », reliée aux mêmes 75 tags observés et au certificat existant. Nouvel essai `run-7f50a1dddf6a44ddafec976ce6b45f7f` : cinq échanges, 280 écritures d'entrées simulées, 75 qualités good, puis pause explicite avant STEP 1. État final paused/déconnecté, zéro STEP/observation/verdict humain, zéro commande CPU. Les anciens projets et historiques restent présents. Reçu `native-presentation.json`.

Root possède seul les mutations de 8770. Le frontend a libéré 8766 ; la vidéo possède seulement son serveur temporaire 8774. Toujours relire l'état/contextes, ne pas recapturer et rejouer après conflit. Aucun téléchargement ou RUN/STOP générique ajouté.
