# Importer et exporter un P&ID

La [bibliothèque et la portée des essais](PID_COVERAGE.md) distinguent les onze modèles de simulation des 61 familles documentaires, dont les échangeurs, vannes multivoies et fonctions d'instrumentation. Les [modèles d'échangeur et de vanne trois voies](PID_SIMULATION.md) s'activent par choix explicite avec leurs paramètres ; l'import de ces familles reste documentaire par défaut.

Le bouton **Échanges P&ID** ouvre l’inspection, la revue, les exports et le catalogue public. Les fichiers sont traités localement avec des outils gratuits, sans abonnement ni clé API. Les liens du catalogue ouvrent les sites sources sur demande ; le serveur FAT ne récupère pas les documents à votre place.

L'onglet **Mise en page** prépare les feuilles A4 à A0 et les données du cartouche pour le PDF et la CAO. Lire [le guide d'impression](PID_PRINTING.md) pour les révisions, folios, unités de feuille et références de présentation.

## Préparer un nouveau projet

1. Choisir un fichier et les pages utiles, par exemple `9` ou `9,12-14`. Sans sélection, seule la première page est inspectée. Limites : 20 Mo et 20 pages sélectionnées.
2. Activer l’OCR pour les scans. RapidOCR et ses modèles CPU sont installés avec les dépendances sous Python 3.12. Cette version est indisponible sous Python 3.13/3.14 ; la lecture vectorielle reste disponible. L’interface affiche les capacités du poste.
3. Comparer l’aperçu source, les repères, les types et les liaisons. Choisir un type FAT pour chaque objet retenu. Un objet inconnu reste à qualifier ou à écarter. Les confiances sont des indications d’extraction, sans précision garantie.
4. Sélectionner au plus 50 équipements et 200 liaisons, confirmer la revue, puis préparer un nouveau projet. Appliquer le brouillon local et utiliser **Enregistrer**. Le projet précédemment enregistré reste dans la liste des projets.
5. Renseigner les paramètres physiques, les variables et les associations PLC avant un essai. Les paramètres par défaut viennent du catalogue FAT, pas du dessin. Aucune adresse, échelle analogique, logique PLC ou conclusion FAT n’est déduite du fichier.

L’inspection et la préparation ne modifient pas le projet actif. La revue reste disponible après une erreur ou un conflit. L’application est bloquée lorsqu’un essai ou un brouillon existant demande encore une décision. Une inspection peut continuer pendant un essai sans retenir le verrou des commandes FAT. Le lecteur isolé est borné à 90 secondes et 2 Gio ; réduire le périmètre si cette limite est atteinte.

## Formats d’import

| Format | Lecture et limites |
| --- | --- |
| PDF | Texte/géométrie vectoriels, aperçu et OCR optionnel des pages sans texte exploitable. Les PDF FAT natifs contiennent aussi le JSON en pièce jointe. |
| PNG, JPEG, TIFF, BMP, WebP | Aperçu, pages TIFF et OCR des repères. Les traits raster ne deviennent pas automatiquement des tuyauteries validées. |
| SVG | Texte, transformations et géométrie simple ; métadonnées FAT si présentes. Scripts et références externes non exécutés. |
| DXF | Entités, blocs, texte et géométrie candidate lus par ezdxf. Les objets métier CAO propriétaires peuvent rester incomplets. |
| DWG | Conversion locale gratuite par LibreDWG vers DXF, puis même revue. Classes et versions dépendent du convertisseur. |
| JSON | Document `fat-studio/pid` version `1.0`, ou graphe `nodes`/`edges` compatible avec PID-to-Knowledge-Graph. Types, relations et provenance conservés comme données documentaires. |
| GraphML | Graphe et métadonnées FAT si présentes. Les relations ne sont pas traduites en logique PLC. |
| XML DEXPI / Proteus | Sous-ensemble des objets, repères, positions et connexions explicites. Aucune conformité complète DEXPI ni reprise des extensions fournisseur revendiquée. DTD et entités externes refusées. |
| CSV / TSV | Équipements avec identifiant, nom, type et coordonnées selon les colonnes reconnues. Une disposition de revue est générée si les coordonnées manquent. |
| draw.io / ZIP CSV FAT | Données natives incorporées dans les exports correspondants. Pas de lecture générale d’archives ou dessins arbitraires. |

Une liaison géométrique reste une proposition. Le sens physique doit être vérifié. Les logiques présentes seulement dans une analyse fonctionnelle, un programme PLC ou une matrice causes-effets ne sont pas établies par un P&ID. Le graphe peut proposer une contraction de segments de flux et connecteurs hors-page ; elle est signalée comme dérivée.

Le champ optionnel `pid_document` conserve le document interprété, les avertissements, la provenance et les aperçus dans le projet et ses archives. Il est limité à 4 Mo. Le bouton **Revoir le document source du projet** le rouvre après rechargement. Le PDF/DWG d’origine n’est pas archivé intégralement : conserver aussi votre original.

## Exporter le schéma

Enregistrer le projet, puis ouvrir **Exporter le P&ID**. Chaque export utilise un instantané et sa révision ; un contexte périmé est refusé. Les commandes d’arrêt restent disponibles pendant la génération.

| Format | Usage |
| --- | --- |
| SVG / PDF | Dessin vectoriel partageable ; données natives incorporées pour réimport. |
| PNG | Image pour rapport ou présentation, avec données natives pour réimport. |
| DXF | Reprise CAO des symboles, repères et liaisons, avec données natives. |
| DWG R2000 | Conversion du DXF par LibreDWG. Écriture expérimentale, à vérifier dans le logiciel destinataire. |
| JSON P&ID | Objets, positions, liaisons et provenance au format `fat-studio/pid`. |
| JSON graphe / GraphML | Analyse documentaire et outils de graphes. |
| CSV ZIP | Tables équipements/liaisons et document natif. |
| draw.io | Diagramme éditable et document natif pour réimport. |

Ces exports représentent le schéma actif reconstruit avec les symboles du banc. Ils ne reproduisent pas tous les calques, styles, objets métier et annotations du document CAO d’origine. Un export P&ID ne contient pas les variables, secrets, autorisations, observations ou verdicts. Utiliser `.fat.zip` pour conserver le projet et ses preuves.

## Installer le convertisseur DWG gratuit

Depuis la copie source Windows :

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup-pid-cad.ps1
```

Le script installe uniquement dans `.tools/pid-cad/`, avec archives binaire et source épinglées par SHA-256. Aucun PATH global n’est modifié. Version de référence : LibreDWG 0.14, commit `d9468ae948b8f07a08efa756c19f8916052358c0`. Lecture annoncée R13 à R2018 selon les classes ; écriture du banc R2000. La présence des outils ne qualifie pas tous les DWG.

Sur un autre poste/système, installer séparément `dwg2dxf` et `dxf2dwg`, puis définir `FAT_STUDIO_PID_CAD_DIR` avec leur dossier absolu avant de lancer le banc. Un document ne peut pas choisir ce chemin ou une commande. Chaque conversion est bornée à 30 secondes et 20 Mo.

LibreDWG est un outil externe remplaçable sous GPL-3.0-or-later. Les paquets FAT ne contiennent pas ses binaires. Leur redistribution impose aussi les obligations de cette licence et les sources correspondantes. Le script conserve les sources et la provenance localement.

## Catalogue et crédits

Le catalogue fournit cinq sources de P&ID et cinq sources temporelles. Les séries temporelles restent des références d’analyse ; elles ne sont pas importées comme des dessins. Les liens peuvent changer. Certains jeux demandent un compte Kaggle gratuit.

- **Scott Duncan / [PID-to-Knowledge-Graph](https://github.com/ScottDuncanAI/PID-to-Knowledge-Graph)**, MIT, référence `7ee3a82e655c13c11aa26ee25bdc2c0c01bd58f1` : ontologie et format de graphe utilisés pour l’interopérabilité. Son workflow Claude n’est pas exécuté ni nécessaire au banc. Aucun code amont incorporé dans les lecteurs locaux.
- **Scott Duncan / [Public Chemical Manufacturing Datasets](https://github.com/ScottDuncanAI/public-chemical-manufacturing-datasets)**, référence `3f21a8540cac027489d22ebc7af757b0b5299880` : liens et descriptions adaptés en français sous [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), [licence complète conservée](../fat_studio/pid_catalog_LICENSE.txt). Les documents externes gardent les conditions de leurs auteurs et ne sont pas redistribués avec le banc.
- **GNU [LibreDWG](https://www.gnu.org/software/libredwg/)** : conversion DWG externe. **ezdxf**, **pypdf / pypdfium2**, **Pillow**, **ReportLab**, **defusedxml** et **RapidOCR / ONNX Runtime** : lecture, rendu et OCR locaux. Versions, licences et sources dans les [notices tierces](../THIRD_PARTY_NOTICES.md) et les verrous.

## API et assistant local

`GET /api/pid/capabilities` annonce les outils présents. `GET /api/pid/catalog` fournit le catalogue attribué. `POST /api/pid/inspect?filename=plan.pdf&pages=9&ocr=true` reçoit le fichier brut. `POST /api/pid/prepare` reçoit `document`, `selected_ids`, `types` et `name`, puis retourne un nouveau projet et des avertissements. Ces POST restent passifs et exigent jeton local et contexte attendu. `GET /api/pid/export/{format}` exporte le schéma enregistré avec son contexte de révision.

Le CLI garde le contexte explicite sans activer un projet lors d’une inspection/préparation :

```powershell
.\.venv\Scripts\python.exe -m fat_studio.assistant --context .local/pid-context.json context
.\.venv\Scripts\python.exe -m fat_studio.assistant pid-capabilities
.\.venv\Scripts\python.exe -m fat_studio.assistant --context .local/pid-context.json pid-inspect plan.pdf --pages 9 --output .local/plan.pid.json
.\.venv\Scripts\python.exe -m fat_studio.assistant --context .local/pid-context.json pid-prepare .local/plan.pid.json --select P101 --name "Mon transfert" --output .local/transfert.fat.json
.\.venv\Scripts\python.exe -m fat_studio.assistant --context .local/pid-context.json pid-export --format dxf --output .local/schema.dxf
```

Les `--select` proviennent du résultat inspecté. Les types inconnus demandent `--types fichier.json`, objet associant identifiants et types FAT. Les sorties existantes ne sont pas écrasées. Appliquer le projet reste une action séparée selon le [contrat IA](AI_CONTROL.md).
