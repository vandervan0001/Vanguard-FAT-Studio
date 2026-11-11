# Cartouches compacts et conventions P&ID, 11 novembre 2026

## Livraison

Demande utilisateur de compacter le cartouche et d'intégrer couleurs de services, symboles et noms selon les références applicables. Implémentation locale et gratuite, sans achat ni intégration de tables normatives protégées. Le [guide d'impression](../../PID_PRINTING.md) et la [preuve datée](../../../evidence/reprises/2026-11-11-pid-conventions/VERIFICATION.md) décrivent les fonctions et limites.

Fichiers principaux : `pid_conventions.py` (services, codes, références), modèles/échanges/imports/API (service et réglages persistés, GET conventions et ZIP polices), `pid_sheet.py` et `pid_export.py` (compact/full, couleurs, typographie et masques CAO), bibliothèque/provenance/licence des symboles, composants React d'édition/guide/canevas. Schémas, README, notices, changelog, package-data et sélection publique actualisés. Les nouveaux tests couvrent services, glyphes/CAO, symboles sourcés et parcours navigateur. Physique et règles PLC inchangées.

Le cartouche compact imprime les révisions renseignées, au moins une ligne ; le mode détaillé conserve cinq lignes. Aucune information déclarée n'est tronquée. Couleurs choisies dans la palette ACI R2000, avec codes textuels et légende. Chaque service est déclaré explicitement. Les repères reçus sont conservés ; les seuls alias fonctionnels FT/PT/etc. explicitement déclarés sont reconnus, FT-101 n'est pas deviné par le résolveur de types.

61 familles : 41 historiques inchangées, quatre adaptations de pyflowsheet, Jochen Steimel, MIT, commit 8a68f2569a9a977079ece242aa7771b9d53448a8, et 16 fonctions d'instrumentation. Source et licence intégrées, références ISA-5.1-2024/ISO10628/ISO14617-2025/EN1861 sans certification globale. La palette de projet n'est pas un marquage de sécurité universel.

## Validation

1 150 Python réussis / cinq ignorés Windows, 297,08 s. 79 scénarios navigateur réussis sans retry, 252.486 s. Wheel `4774462c5f8644599cf22270145117bc5a66a9f83c0e8599f2e192fe68a12c59`, 72 entrées ; installation isolée privée 34.935 s avec 71 fichiers égaux au wheel, 65 payloads égaux aux sources, 37 modules importés depuis l'installation. Quarante restaurations natives, dix exports HTTP, preview/archives/redémarrage et cinq assertions thermiques passent. Dépendances réutilisées. Les 91 empreintes produit figées n'ont pas changé.

Le premier passage ciblé navigateur a révélé deux erreurs de fixture, puis un vrai conflit CSS sur la couleur d'une liaison sélectionnée. Fixtures et CSS corrigés, traces préservées. Premier passage complet : 78 réussis et une assertion de compteur restée à 41 symboles dans pid-physics.spec.ts ; attente actualisée à 61 sans modification produit, puis seconde suite complète réussie. Premier contrôle installé arrêté sur une tolérance privée MediaBox de 1e-6 mm, corrigée à 0,001 mm pour l'arrondi PDF mesuré ; aucun changement produit résultant. Le diagnostic SVG privé avait une règle evenodd incompatible avec les contours Geist ; correction nonzero limitée au visualiseur texte. Ces premières preuves sont conservées séparément.

## Service et données

Le service source 8765 a été redécouvert : seul dossier `.local/pid-catalogue-demo-2026-11-11/data`, projet Virden, idle, sans run/PLC/écriture. Identités des processus13244/33524 vérifiées avant leur arrêt, puis relance masquée du même service, parent8568/listener35660 au constat (à revalider à toute action). Manifeste courant dans `.local/pid-catalogue-demo-2026-11-11/server.json`.

Découverte santé/projet/état/catalogue/schéma/workspace puis capture explicite du contexte avant deux imports de copies nouvelles : `pid-virden-compact-20261111` et `pid-thermal-services-20261111`. Les projets antérieurs sont conservés. Six nouveaux fichiers dans `output/pdf/` et `output/cad/`, préfixes `PID-Virden-Alun-A3-Compact-Rev-B` et `PID-Thermique-Services-A3-Rev-B`, plus ZIP de polices. Export A3 et relecture réelle PDF/DWG/DXF vérifiés ; originaux Rev A inchangés. Projet final thermique couleur au repos, zéro écriture, aucune connexion PLC ni conclusion FAT créée. Ouverture PDF demandée au panneau Codex : queued ; rendus PNG inspectés directement.

## Reprise

HEAD f5ad062, dossier partagé toujours modifié avec les changements antérieurs, aucun stage/commit/push/publication. Journal privé complet : `.dev-loop/pid-conventions-2026-11-11/logbook.md`. Preuves privées dans `.local/pid-conventions-2026-11-11/` ; sources/proofs anciens et kits conservés. Relire Git, journal et service courant avant toute nouvelle mutation. La présente demande est traitée ; aucun contrôle obligatoire restant. Pour vérifier à nouveau sans toucher aux données utilisateur :

```powershell
. ./.local/dev-env.ps1
.venv/Scripts/python.exe -B -m pytest -q
npm --prefix frontend test
```

Limites : aucune conformité complète ISO/ISA, acceptation CAO propriétaire/imprimante physique, Windows vierge ou qualification Siemens revendiquée. Les polices et styles de tracé du destinataire restent à contrôler. Le bandeau d'actions mobile a un débordement historique hors périmètre ; guide et service restent lisibles dans les captures relues.
