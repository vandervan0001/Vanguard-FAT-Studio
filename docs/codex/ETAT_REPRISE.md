# Vanguard FAT Studio : état de reprise

## Publication Git et pack LinkedIn, 11 novembre 2026

Changements publics sélectionnés pour commit/push sur la branche codex/vanguard-fat-studio-brand. Pack prêt avec texte, captures réelles, PDF de présentation, plans PDF/DWG/DXF et crédits. Aucune publication LinkedIn ni fusion sur main. Données et notes privées conservées hors Git. Lire [la note](sessions/2026-11-11-pid-push-linkedin.md) et [le pack](../../media/linkedin/2026-11-11-pid/README.md). Le reçu local du push contient le SHA distant vérifié après envoi.


## P&ID compacts, couleurs et symboles sourcés, 11 novembre 2026

Cartouche compact/détaillé, services froid/chaud et utilités explicites avec codes/couleurs/légende et mode noir et blanc. 61 familles, dont quatre dessins pyflowsheet MIT et 16 fonctions d'instrumentation ; guide ISA/ISO/EN et crédits conservés, sans renommage des sources ou conformité inventée. Les débordements typographiques, centrages et masques CAO de la revue précédente sont corrigés et relus sur les nouveaux exports.

Validation : 1 150 Python réussis / cinq ignorés Windows, 79 scénarios navigateur réussis sans retry, wheel installé isolément avec 40 restaurations natives/quatre modes et dix exports HTTP vérifiés. Les 91 empreintes produit sont inchangées. Deux copies nouvelles et six PDF/DWG/DXF Rev B exportés par API gardée, originaux Rev A conservés. Source8765 relancée sur le seul dossier de démo, thermique couleur actif au repos, sans PLC ni écriture. Lire [la livraison](sessions/2026-11-11-pid-conventions.md) et [le guide](../PID_PRINTING.md). Aucun contrôle obligatoire restant ; qualification CAO propriétaire/impression physique et ancien débordement du bandeau mobile hors périmètre.


## Contrôle visuel Virden PDF/DWG, 11 novembre 2026

PDF A3 relu avec Poppler : cartouche et historique visibles, révision A du 2026-11-11, visas non renseignés et statut BROUILLON. La comparaison visuelle CAO échoue : description de révision débordant dans « Dessiné », caractères plus grands en DXF et dans le DWG reconverti. Le même nombre utilisé comme taille em PDF et hauteur de capitale DXF explique cet écart, avec des polices différentes. La chaîne LibreDWG perd aussi le point d'alignement de 56 textes centrés ; l'attribution encodage/lecture reste ouverte faute de lecteur DWG indépendant. La conservation des données natives, unités et layout ne démontre donc pas l'équivalence d'impression. Aucun correctif produit ni nouvel export ce tour ; originaux conservés. Lire le [contrôle complémentaire](sessions/2026-11-11-pid-engineering-sheets.md#contrôle-visuel-complémentaire-du-11-novembre-2026). Prochaine action : corriger les métriques CAO et contrôler le centrage sur un lecteur indépendant avant de déclarer le DWG équivalent.


## Feuilles P&ID de bureau d'études, 11 novembre 2026

PDF/DXF/DWG A4 à A0, cadre/cartouche, entreprise/client, numéro de document, révision/date/statut/folio, mentions de visas et cinq lignes d'historique. Aperçu passif et sauvegarde dans Mise en page, brouillons/contexte préservés. PDF vectoriel avec polices/propriétés, DWG éditable en mm de feuille et layout d'impression 1:1 ; aucune conformité complète ISO/ISA, signature ou validation FAT humaine revendiquée.

Validation finale : 1 059 tests Python réussis / cinq ignorés Windows, 77 scénarios navigateur réussis sans retries. Premier passage navigateur avec un ECONNRESET en préparation conservé séparément, seconde suite complète réussie sans modification produit. Wheel installé hors source et dix formats HTTP vérifiés, deux feuilles A3 thermique/Virden exportées par API et relues avec Poppler/CAO. Serveur 8765 démarré sur le seul dossier de démonstration (ancien processus absent), Virden cartouché actif au repos, projets antérieurs conservés. Lire [la note](sessions/2026-11-11-pid-engineering-sheets.md), [le guide](../PID_PRINTING.md) et [la preuve](../../evidence/reprises/2026-11-11-pid-drafting/VERIFICATION.md). Aucun contrôle obligatoire en attente ; aucun accès PLC ou publication.


## Modèles P&ID thermiques et trois voies, 11 novembre 2026

Réponse utilisateur « couvre le plus et le mieux » : deux modèles supplémentaires livrés, soit onze types de simulation et 41 familles documentaires. Vanne mélange/diversion avec conservation volumique ; échangeur à deux volumes mélangés, bilan d'énergie, sources de débit explicites et encrassement. Import de ces familles documentaire par défaut, simulation choisie explicitement ; aucun solveur de pression ou couplage déduit des lignes.

Validation : suite complète 909 tests Python réussis / cinq ignorés Windows, puis 106 contrôles ciblés après correction d'un libellé ; 74 scénarios navigateur réussis sur le bundle final. Wheel installé hors source, dix formats HTTP et scénario thermique 100 s/1 000 cycles/cinq assertions vérifiés. Serveur source 8765 relancé, exemple thermique actif au repos, Virden et laboratoire précédents conservés, exports PDF/DWG disponibles. Aucun PLC ou verdict FAT humain. Lire [la note de livraison](sessions/2026-11-11-pid-physical-models.md), [les contrats](../PID_SIMULATION.md) et [la preuve](../../evidence/reprises/2026-11-11-pid-physical/VERIFICATION.md). Aucun contrôle obligatoire en attente ; limites externes et matérielles maintenues.


## Bibliothèque documentaire P&ID et couverture, 11 novembre 2026

41 familles documentaires ajoutées, dont échangeurs quatre piquages et vannes trois/quatre voies, avec rotation et bornes nommées conservées. Inconnus maintenus sans les convertir en indicateurs. Les neuf types historiques sont inchangés ; aucune nouvelle physique thermique/hydraulique n’est revendiquée. PDF denses et faux repères de cartouche corrigés, extraction réelle encore partielle.

Dernière validation : 764 tests Python réussis / cinq ignorés Windows, 71 scénarios navigateur réussis. Dix formats natifs et coordonnées DXF/DWG sans JSON contrôlés ; wheel final installé et vérifié hors sources avec dépendances réutilisées. Exemple Virden page 14 importé et revu en huit objets/quatre liaisons tracées, exports PDF/DWG disponibles ; serveur source 8765 au repos, sans PLC. Lire [la note et les preuves](sessions/2026-11-11-pid-equipment-coverage.md) et [la portée des essais](../PID_COVERAGE.md). Ne pas confondre restauration native et lecture de tous les plans.

## Import et export P&ID livrés dans les sources, 11 novembre 2026

Inspection et revue locales PDF/scans/images, SVG, DXF, DWG via LibreDWG gratuit, graphes et formats documentaires. Nouveau brouillon sans mapping ni autorisation, document source conservé et dix exports. Catalogue Scott Duncan intégré et attribué, crédits et licences dans README/notices. Aucun service IA payant requis.

Dernière validation : 681 tests Python réussis / cinq cas de liens symboliques ignorés sous Windows, 68 scénarios navigateur réussis, build/bundle et wheel installé hors sources vérifiés. Dix allers-retours HTTP dont DWG R2000 réel ; dépendances réutilisées, pas de qualification Windows vierge ou CAO propriétaire. Changements préexistants et anciens kits conservés, aucun accès PLC ni publication. Lire [la livraison P&ID](sessions/2026-11-11-pid-import-export.md) et [le guide](../PID_EXCHANGE.md). Relancer le serveur source pour charger les nouvelles routes.

## Lecture de deux dépôts P&ID, 11 novembre 2026

Première évaluation documentaire de `ScottDuncanAI/PID-to-Knowledge-Graph` et `public-chemical-manufacturing-datasets`. Le premier extrait un graphe avec Claude et des scripts Python ; le second référence des P&ID et séries temporelles. Piste proposée : une feuille publique revue, puis un brouillon de projet FAT avec paramètres et associations PLC déclarés séparément. Aucune intégration réalisée ni test FAT relancé. Seules notes de reprise ajoutées ; changements préexistants conservés. Voir [la note de lecture](sessions/2026-11-11-pid-knowledge-graph-review.md).

## Diagnostic autonome : round 010 terminé, 10 novembre 2026

Projet séparé `C:/Vanguard_Diagnostic_Lab/siaccess-2026-11-09` : éditeur guidé de candidat pour les 22 pilotes Python, validation passive et export exact, sans activation ni connexion. 2 333 tests Python et 84 scénarios UI passent. Kits source et portable vérifiés après extraction ; les 22 modèles sont aussi validés sous le Python embarqué. Roadmap, spécification et revue adverse actualisées.

Aucun code produit FAT ni accès production. Changements préexistants conservés ; seules notes de reprise, sans tests FAT relancés. Lire [la livraison du round 010](sessions/2026-11-10-diagnostic-round010-delivery.md). Qualifications CPU, série physique, Windows vierge et droits siAccess restent ouvertes, ainsi que les extensions de protocoles documentées.


## Diagnostic autonome : round 009 terminé, 10 novembre 2026

Projet séparé `C:/Vanguard_Diagnostic_Lab/siaccess-2026-11-09` : Host Link CS/CJ DM/CIO/HR/AR, découverte CIP étendue et SRTP expérimental en lecture seule. 22 profils Python ; 2 209 tests Python et 71 scénarios UI passent. Kits source et portable vérifiés après extraction, 23 cas réseau/UDT avec 46 workers embarqués, cinq profils série injectés et deux cas Windows Job réussis. Spécification, roadmap et revue adverse actualisées.

Aucun code produit FAT ni accès de production. Changements préexistants conservés ; seules notes de reprise, sans tests FAT relancés. Lire [la livraison du round 009](sessions/2026-11-10-diagnostic-round009-delivery.md). SRTP reste limité à `%R` sans authentification ; les variantes CIP et qualifications matérielles restent ouvertes.


## Diagnostic autonome : round 008 terminé, 10 novembre 2026

Projet séparé `C:/Vanguard_Diagnostic_Lab/siaccess-2026-11-09` : découverte CIP native vers candidat, chaînes Siemens/CIP, FINS CS/CJ multi-aires et SLMP3E UDP. 20 profils Python ; 2016 tests Python et 66 scénarios UI passent. Nouveaux kits source/portable vérifiés après extraction, 21 parcours avec workers embarqués, 4 séries injectées et 2 cas Windows Job réussis. Documentation et roadmap actualisées.

Aucun code produit FAT ni accès de production. Changements préexistants conservés ; seules notes de reprise, sans tests FAT relancés. Lire [la livraison du round 008](sessions/2026-11-10-diagnostic-round008-delivery.md). Les limites de découverte, autres bus et qualifications matérielles restent ouvertes.


## Diagnostic autonome : round 007 terminé, 10 novembre 2026

Projet séparé `C:/Vanguard_Diagnostic_Lab/siaccess-2026-11-09` : UDT locaux réutilisables, chaînes ADS/OPC UA, archives v2 et deux profils Mitsubishi ajoutés. 1754 tests Python et 65 scénarios UI passent. Nouveaux kits source/portable vérifiés extraits, 17 cas réseau/texte, 4 séries injectées et 2 cas Windows Job embarqués passent. Documentation et roadmap actualisées.

Aucun code produit FAT ni accès de production. Dirty préexistant conservé ; seules notes de reprise, sans tests FAT relancés. Lire [la livraison du round 007](sessions/2026-11-10-diagnostic-round007-delivery.md). UDT natifs, découverte, bus et qualification matérielle restent distincts des preuves logicielles.


## Diagnostic autonome : round 006 terminé, 9 novembre 2026

Projet séparé `C:/Vanguard_Diagnostic_Lab/siaccess-2026-11-09` : composites déclarés, lectures groupées et sept profils ajoutés (quinze Python au total). 1 493 tests Python et 55 scénarios UI passent ; nouveaux kits source/portable vérifiés après extraction, onze profils réseau et quatre séries injectées testés avec Python embarqué. Spécification, roadmap, revue adverse et limites actualisées.

Aucun code produit FAT ni accès de production modifié. Le dirty FAT existant reste conservé ; seules les notes de reprise sont ajoutées, sans tests FAT relancés. Lire [la livraison du round 006](sessions/2026-11-09-diagnostic-round006-delivery.md). La qualification matérielle et les profils encore absents restent distincts des preuves logicielles.


## Diagnostic autonome multiconstructeur, clôture du 9 novembre 2026

Projet séparé `C:/Vanguard_Diagnostic_Lab/siaccess-2026-11-09` : spécification de 35 sections, roadmap et code après cinq rounds dev-loop. Huit profils Python et deux parcours Siemens, analyse hors ligne, workers Windows contenus et export séparé. 1 027 tests Python, 45 scénarios UI, heure synthétique 99,9944 % de cycles bons ; charge concurrente et navigation de l’heure mesurées. Kits source et portable neufs vérifiés sur copie extraite ; rapport externe de livraison avec empreintes. Les limites matérielles, Windows propre, licence et extensions restent explicites.

Aucun code produit FAT ni accès CPU/production ajouté par ces rounds. Le dirty FAT préexistant est conservé ; seuls ces documents de reprise sont actualisés et aucune suite FAT n’est relancée. Voir [la note de livraison autonome](sessions/2026-11-09-diagnostic-round005-delivery.md). Ne pas réutiliser une ancienne autorisation de lecture pour qualifier un nouveau collecteur.


## Diagnostic : round 001 et roadmap multiconstructeur, 9 novembre 2026

Projet indépendant `C:/Vanguard_Diagnostic_Lab/siaccess-2026-11-09`. Roadmap/spec/matrice couvrent Siemens, Schneider, Rockwell, grands fabricants et Ethernet/série. Premier lot logiciel Siemens ponctuel intégré et relu, sans nouvel accès CPU : 127 tests Python, 68 contrôles classic, 13 scénarios UI, builds et intégration capture/archive/rejeu réussis. Protocoles non Siemens à développer, qualifications natives toujours distinctes. Nouveau kit source à 82 fichiers vérifié ; précédent kit intact. Voir [la note du round 001](sessions/2026-11-09-diagnostic-round001-multivendor.md). Aucun produit FAT modifié ni test FAT relancé. Prochaine étape : contrat multiconstructeur, puis Modbus et CIP ; ne relancer aucune sonde de production.

## Lecture de production réussie après correction du délai, 9 novembre 2026

Sur nouvelle demande explicite de résoudre le timeout et lire le même BOOL, le TCP vers la cible a répondu en 2,74 secondes, au-delà du délai local initial de 2 secondes. Une nouvelle sonde privée conserve exactement la cible/adresse/rack/slot fournis et porte ses délais SDK à 15 secondes. Une lecture absolue unique réussie, qualité bonne, en 2,61 secondes ; déconnexion SDK et sortie processus réussies. Aucun catalogue, secret, écriture, contrôle CPU, changement de protection ou réseau. La valeur et les coordonnées de production restent exclusivement dans `.local/production-bit-once-vpn-timeout` du laboratoire indépendant.

Le profil confirmé est conservé localement sans auto-connexion. Kit et collecteur symbolique livrés inchangés ; aucun test cyclique de production n'est déduit de ce succès. Ne pas interpréter le délai allongé comme une modification du PLC. Voir [la note de correction](sessions/2026-11-09-production-read-timeout-fixed.md). L'échec initial ci-dessous reste une preuve historique distincte.

## Lecture ponctuelle sur production, 9 novembre 2026

L'utilisateur a signalé une CPU réelle de production ouverte dans TIA V20, puis autorisé une unique lecture BOOL avec adresse et rack/slot explicites. Aucun transfert de l'autorisation du simulateur. Le collecteur symbolique livré n'a pas été lancé, car sa connexion charge le catalogue global. Une sonde privée siAccess classique, sans catalogue, secret, écriture ou contrôle CPU, a été compilée puis exécutée une seule fois. Échec à la connexion : SDK `-720892 Timeout`, zéro fonction de lecture appelée et aucune valeur obtenue. Pas de relance. Les connexions TIA observées initialement avaient disparu avant la tentative ; une route VPN subsistait, sans cause de panne établie.

Adresse, variable, preuve et sonde sont uniquement dans `.local/production-bit-once` du laboratoire indépendant, hors Git/kit/Page. Le marqueur empêche une répétition accidentelle. Aucun changement produit FAT ni nouvelle qualification Siemens. Le kit livré conserve son empreinte. Voir [la note de lecture production](sessions/2026-11-09-production-read-once.md). Un nouvel essai nécessite un accès cible rétabli et une demande explicite ; ne pas modifier les protections ou activer PUT/GET.

## Prototype diagnostic autonome, 9 novembre 2026

Implémentation séparée dans `C:/Vanguard_Diagnostic_Lab/siaccess-2026-11-09`, branche neuve `codex/siaccess-readonly` sans commit. Aucun changement produit FAT. Spécification complète locale de 29 sections et 35 recettes, également enregistrée dans la Page privée séquence 5. Service FastAPI/SQLite, moteur d'acquisition et déclenchement, collecteur symbolique siAccess C# isolé, analyseur React, captures, curseurs sources, annotations/vues versionnées, conversions et exports propres implémentés. Revue adverse corrigée, y compris imports hostiles, captures concurrentes et export sur instantané indépendant de la collecte.

Validation finale dans l'environnement Python propre au diagnostic : 92 tests Python réussis, Ruff propre, dépendances cohérentes et huit tests navigateur réussis. Essai natif intégré bref : 12 lots et 72 observations de six variables concordantes avec la référence, capture, exports et réimport hors ligne. La CPU virtuelle copiée est restée STOP ; aucun RUN/STOP, téléchargement ou écriture de variable. Aucun contrôle de fenêtre repris après l'arrêt CUA utilisateur. Campagnes synthétiques distinctes : 64 signaux/100 ms sur 60 s, puis 15 s avec horloge QPC corrigée ; aucune qualification d'une heure revendiquée.

Kit source final `dist/Vanguard-Diagnostic-Source-20261109-144056728.zip` dans ce projet, SHA-256 `28ae28c257034a13182557a8a18f7765744f2ccbdc04b748491d8e6b8ca49d58`, 271 122 octets. Ses 66 fichiers autorisés et leurs empreintes sont vérifiés sur une copie extraite dans un chemin avec espaces. Démarrage HTTP, actifs UI, cinq lots/deux signaux, capture et exports/import réussis sur cette copie. Aucun runtime Python, SDK propriétaire, stockage CPU ou secret dans ce kit. CPU physique/DB optimisé, poste sans logiciels Siemens, charge longue et redistribution restent à qualifier ; M5 non accepté. Voir la note [diagnostic autonome](sessions/2026-11-09-diagnostic-prototype.md).

## Essai siAccess indépendant, 9 novembre 2026

Laboratoire séparé dans `C:/Vanguard_Diagnostic_Lab/siaccess-2026-11-09`, dépôt neuf sans commit, branche `codex/siaccess-readonly`. Essai officiel siAccess 7.20 téléchargé après connexion MySofting par l’utilisateur, signature Softing valide, installé sous le laboratoire avec exemples dans le dossier public Windows du fournisseur. Sur autorisation distincte de préparation du simulateur, copie du stockage public dans ce laboratoire et nouvelle instance `VDIAG-SIACCESS-20261109`, STOP sur `192.168.247.3`, TCPIPSingleAdapter isolé. L’original des 87 fichiers de stockage FAT est inchangé par empreinte.

Connexion S7 native TLS et certificat connu vérifié avant authentification, 83 nœuds parcourus directement depuis la CPU et six variables BOOL/REAL lues. Six valeurs sur six confirmées par lecture native PLCSIM indépendante. Session siAccess déconnectée ; copie de CPU laissée en STOP, processus propriétaire identifié dans `evidence/cpu-host.pid` du laboratoire. Aucun RUN/STOP, téléchargement de programme ou écriture de variable. La préparation a enregistré et mis sous tension la seule copie, et ajouté l’adresse hôte sur le seul adaptateur virtuel.

Preuves et limites dans `evidence/RESULTATS.md` du laboratoire : DB de démo non optimisé, aucune qualification DB optimisé, CPU physique, cadence longue ou poste sans logiciels Siemens. Avis modal de l’essai observé à chaque lancement. Aucun changement produit FAT ni publication. Voir la [note de session](sessions/2026-11-09-siaccess-readonly-lab.md).

## Médias du post de lundi, 7 novembre 2026

Le pack préparé pour le 9 novembre est dans `.local/vanguard-post-2026-11-09/` : vidéo de 26 secondes en 1 080 × 1 350 avec musique originale ou sans audio, quatre visuels 4:5, cinq captures HD et couverture. Le ZIP contient seulement les livrables sélectionnés ; `README-MEDIA.md` décrit les prises, sources et commandes. Le master et l’archive sont vérifiés. Les prises utilisent la source `674504c` du worktree `portable-approvals-20261107`, avec un laboratoire séparé sur 8781. L’essai est arrêté et ce serveur fermé. Aucun PLC connecté, observation FAT laissée vide et aucune publication effectuée. Aucun changement produit ni modification des anciens médias. Voir la [note de production](sessions/2026-11-07-post-lundi-medias.md).

## Portable publié avec autorisations groupées, 7 novembre 2026

Le [nouveau ZIP Windows x64](https://github.com/vandervan0001/Vanguard-FAT-Studio/releases/download/public-preview-2026-11-04/Vanguard-FAT-Studio-Windows-x64-2026-11-07-6c2e463.zip) est publié dans la release d’aperçu, avec SHA-256 et comptes rendus Markdown/JSON. Python 3.12.10, application 0.2.1, source exacte `6c2e463`, PR n° 3 fusionnée dans `main` au commit `32788f1`. Le correctif CI `674504c` fixe Ubuntu 24.04 pour Playwright 1.56.1 ; il ne change que le workflow.

Validation : 60/60 tests navigateur sur le portable extrait, cinq contrôles d’installation et lanceur sans Python global réussis, 3 218 fichiers intacts après essais. CI Windows et Ubuntu 24.04 réussie ; arbre fusionné identique à celui testé. Quatre fichiers publics retéléchargés sans authentification et vérifiés par SHA-256 ; CRC du ZIP valide. Les onze pièces jointes historiques et le tag restent conservés. Worktree de livraison conservé (checkout principal protégé par Codex), preuves et artefacts conservés dans `.local/portable-approvals-2026-11-07/`. Aucun blocage. Voir la [note de livraison](sessions/2026-11-07-portable-approvals.md).

## Autorisations groupées, 7 novembre 2026

L’interface propose un accord de cible optionnel pour les essais choisis dans un onglet, révocable et lié à la révision active. Elle propose aussi une revue groupée des écritures des entrées simulées avec filtre, choix individuels et application au brouillon. Les contrôles serveur et les sorties PLC restent inchangés. Bundle source reconstruit ; le portable a ensuite été publié selon la note de livraison ci-dessus. Aucun accès à une CPU. Les modifications préexistantes sont conservées ; les changements publics ont été isolés et fusionnés dans la PR n° 3. Vérifications finales : 68 tests backend ciblés et 60 tests navigateur réussis, zéro échec. Revues cible/écritures relues à 768 pixels ; build, sélection publique et empreintes du bundle vérifiés. Aucun blocage local. Ces ajouts sont disponibles dans la copie source et le nouveau portable daté du 7 novembre. Voir la [note de reprise](sessions/2026-11-07-approval-review.md).

## ZIP portable Windows public, 4 novembre 2026

Le [ZIP portable Windows x64](https://github.com/vandervan0001/Vanguard-FAT-Studio/releases/download/public-preview-2026-11-04/Vanguard-FAT-Studio-Windows-x64-6d822c1.zip) de la release d’aperçu a été construit depuis `main` au commit `6d822c1`. Python 3.12.10 est embarqué. Le ZIP extrait démarre la démo sans Python global et les exports d’essai ont passé. Aucun standard ni programme métier privé dans le paquet. Voir la [note de livraison](sessions/2026-11-04-portable-main.md).

## Audit du contenu public, 4 novembre 2026

L’historique accessible via les références Git, les PR et les fichiers de la release publique ont été vérifiés contre les fichiers d’ingénierie isolés. Aucun standard, programme métier ou archive fournisseur n’a été retrouvé dans ce périmètre. Reçu local dans `.local/privacy-audit-2026-11-04/verification.json`.

## Aide des pupitres, 4 novembre 2026

Le bandeau P&ID affiche le mode et l’état de l’essai. Les pupitres annoncent la disponibilité des commandes et expliquent un clic bloqué à l’endroit de la saisie. La démo locale 8777 sert le nouveau bundle. La [PR n° 2](https://github.com/vandervan0001/Vanguard-FAT-Studio/pull/2) est fusionnée dans `main` au commit `6d822c1`, après réussite de la CI Windows et Ubuntu sur le code fusionné. Voir la [note de vérification](sessions/2026-11-04-io-guidance.md).

## Démo laboratoire locale, 4 novembre 2026

Instance prête sur `http://127.0.0.1:8777`, en mode démonstration et au repos. Données isolées dans `.local/demo-laboratoire-4d8061fb/data/`. Voir la [note de lancement](sessions/2026-11-04-local-demo.md).

## Démo animée, 4 novembre 2026

La vidéo de 56 secondes équilibre construction du P&ID, forçages TOR et analogique, scénario automatique et FAT guidée. Les gestes et les réactions sont filmés dans le navigateur, avec un curseur visible. Les deux MP4 et le SRT sont en tête de la [release publique](https://github.com/vandervan0001/Vanguard-FAT-Studio/releases/tag/public-preview-2026-11-04). Les sources du montage sont dans `.local/vanguard-pid-motion-2026-11-04/film/`. Voir la [note de reprise vidéo](sessions/2026-11-04-vanguard-pid-motion.md).

## Film P&ID, 4 novembre 2026

Le montage « Construire et tester » suit un projet de démo créé à l’écran, depuis la dépose de trois équipements jusqu’à l’arrêt de P-101 sur défaut moteur. Il montre aussi la préparation et l’application d’un STEP sur le même projet. Sources, rendus et reçus dans `.local/vanguard-pid-film-2026-11-04/`. Le détail des prises et des vérifications figure dans la [note vidéo](sessions/2026-11-04-vanguard-pid-film.md).

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
