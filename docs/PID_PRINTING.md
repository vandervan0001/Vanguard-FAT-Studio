# Éditer une feuille P&ID pour l'impression

Dans **Échanges P&ID > Mise en page**, préparer le cartouche du projet : entreprise, client, référence de projet, site, unité, titre et numéro de document. Déclarer l'indice de révision, la date d'émission, le statut et le folio dans le dossier. Les formats A4 à A0 et les orientations portrait/paysage sont disponibles.

Les champs **Dessiné par**, **Vérifié par** et **Approuvé par** sont des mentions déclarées par l'utilisateur. Ils restent vides par défaut ; le banc ne produit ni signature ni visa vérifié. Le statut initial est **Brouillon**. La date d'émission ne change pas automatiquement à chaque téléchargement et l'indice n'est jamais incrémenté sans action de l'utilisateur. Ces informations sont distinctes du verdict FAT.

## Préparer, prévisualiser et enregistrer

L'aperçu utilise la géométrie du projet enregistré et les valeurs du cartouche en préparation. Il n'applique aucune modification au procédé, aux associations PLC ou à l'essai. Enregistrer les modifications de géométrie avant de les attendre dans cet aperçu.

Appliquer ou enregistrer la mise en page depuis la fenêtre selon l'action proposée. L'export définitif utilise toujours l'instantané enregistré. En cas de conflit de projet ou de révision, conserver les champs préparés et comparer le projet courant ; aucune requête refusée n'est rejouée automatiquement.

Les notes se répartissent dans une zone réservée. L'historique comporte jusqu'à cinq lignes de révision, avec description, date et mentions de préparation/vérification/approbation. Le cartouche se trouve en bas à droite, avec bordure, zones de repérage, hiérarchie de traits et textes vectoriels. Les champs de cartouche trop volumineux pour la feuille demandent un format plus grand au lieu d'être tronqués silencieusement.

Le style **Compact**, proposé par défaut, réduit les espacements et imprime les révisions renseignées avec au moins une ligne. Le style **Détaillé** garde les cinq lignes visibles. Les informations déclarées sont conservées dans les deux styles ; un texte long peut agrandir le bloc. Ce réglage libère la zone du schéma sans réduire les textes à une taille illisible.

Un fichier correspond à un folio. **Folio / total** décrit sa place dans un dossier de plans ; ce champ ne génère pas les autres feuilles. Pour un schéma dense, choisir une feuille plus grande ou préparer plusieurs dessins distincts. Un avertissement de densité signale les cas qui demandent une relecture à la taille d'impression réelle.

## PDF, DWG et unités

Le PDF contient une feuille aux dimensions physiques du format choisi et des polices locales incorporées. PDF, PNG imprimable et CAO utilisent la même composition. Le DXF/DWG conserve des entités éditables et des calques séparant cadre, cartouche, révisions, équipements, conduites, signaux et textes. La conversion DWG gratuite utilise toujours LibreDWG ; son écriture R2000 reste expérimentale.

Les textes CAO référencent **Geist Regular/Bold**. Télécharger le compagnon **Polices CAO** avec les exports DXF/DWG et installer les polices dans la CAO destinataire pour conserver les métriques du PDF. Le paquet contient les TTF et leur licence SIL OFL ; le DWG ne les incorpore pas. Les positions centrées sont calculées avant écriture et stockées comme points d'insertion explicites. La conversion de hauteur em PDF vers capitale CAO évite le débordement trouvé lors de la revue Virden.

Le contrôle de rendu utilise une feuille blanche et les couleurs des objets, y compris les remplissages blancs des symboles. Une table de styles d'impression externe peut remapper ces couleurs ; vérifier ces réglages dans la CAO destinataire avant l'impression.

La mention **Sans échelle** est volontaire : un P&ID décrit les fonctions et les liaisons, sans fournir de longueurs réelles de tuyauterie. Les unités CAO de cette feuille représentent des millimètres sur papier. Elles ne transforment pas les coordonnées de l'éditeur en dimensions du procédé. Les réglages d'impression du logiciel destinataire restent à contrôler avant une émission contractuelle.

SVG et draw.io conservent leur présentation de diagramme et leurs piquages existants. Les données natives P&ID conservent le cartouche ; le projet complet et l'archive conservent aussi la simulation et les preuves. Le graphe JSON utilise l'extension explicite `fat_studio_drawing` pour ces seules métadonnées. Aucun paramètre physique ou droit PLC n'est ajouté à un dessin.

## Références de présentation

La composition est une trame propre au banc. Les références documentaires consultées sont :

- [ISO 7200:2004](https://www.iso.org/standard/35446.html), champs de données des cartouches et en-têtes.
- [ISO 5457:1999, avec amendement 2010](https://www.iso.org/standard/29017.html), formats et présentation des feuilles de dessin.
- [ISO 128-2:2022](https://www.iso.org/standard/83355.html), conventions de base des traits.
- [ISO 10628-1:2014](https://www.iso.org/standard/51840.html), classification, contenu et représentation des schémas de procédé.

Les notices publiques de ces normes établissent leur objet ; elles ne constituent pas une vérification complète des clauses. La présence d'un cartouche n'atteste aucune conformité ISO/ISA des symboles, des données de procédé ou du dossier. Appliquer les conventions du donneur d'ordre avant une émission officielle. Aucun achat de norme, service payant ou logiciel CAO propriétaire n'est requis par cette fonction.

Pour les formats et leur attribution, voir [PID_EXCHANGE.md](PID_EXCHANGE.md). La [portée des essais](PID_COVERAGE.md) et les [modèles simulés](PID_SIMULATION.md) restent distincts de la qualité de présentation d'un plan.

## Services, symboles et repères

Choisir le service d'une liaison dans l'éditeur : départ/retour froid, départ/retour chaud, vapeur, condensats, eau de refroidissement, air instruments ou fluide de procédé. Une liaison importée sans service reste non renseignée. Aucune température, nature de fluide ou fonction de sécurité n'est déduite d'une couleur, d'un nom ou d'un symbole.

**Couleurs de services** utilise une palette de projet et des codes textuels (CHWS/CHWR, HWS/HWR, STM, COND, CW, IA, PROC). Ils ne sont pas présentés comme des codes universels imposés par ISO/ISA. La palette est limitée aux couleurs ACI conservées par le DWG R2000 ; les mêmes valeurs sont utilisées en PDF et dans l'éditeur. **Noir et blanc** conserve les codes et la légende. La couleur seule ne porte donc pas l'identification du service. Revoir cette convention contre le cahier des charges du projet.

Le catalogue propose 61 familles documentaires : les 41 historiques, quatre représentations générales adaptées de pyflowsheet et 16 fonctions d'instrumentation. Les sources, la révision épinglée et les adaptations sont décrites dans [la provenance des symboles](../fat_studio/pid_symbols_PROVENANCE.md). Les symboles restent documentaires ; leur ajout ne sélectionne ni modèle physique ni variable PLC.

Le guide de conventions explique des repères courants tels que FT-101 (transmission de débit), FIC-101 (indication et régulation de débit), PT-101, LT-101 ou TIC-101. Les suffixes numériques illustrent une convention de boucle et ne constituent pas une numérotation obligatoire du site. Les repères reçus restent conservés. Les préfixes d'équipements P, TK, E ou V du catalogue relèvent également de la convention du projet.

Références primaires consultées le 11 novembre 2026 :

- [ANSI/ISA-5.1-2024](https://www.isa.org/standards-and-publications/isa-standards/find-isa-standards-by-topic), symboles et identification des fonctions d'instrumentation ; [guide ISA de lecture](https://www.isa.org/getmedia/e122051e-8c8c-48be-97ef-5d344c585771/Chapter7_Control).
- [ISO 10628-2:2012](https://www.iso.org/standard/51841.html), symboles graphiques des schémas pour l'industrie chimique et pétrochimique.
- [ISO 14617-1:2025](https://www.iso.org/standard/85641.html) et [ISO 14617-2:2025](https://www.iso.org/standard/83364.html), règles générales et bibliothèque de symboles.
- [EN 1861:1998](https://www.dinmedia.de/en/standard/din-en-1861/4533906), schémas des systèmes frigorifiques et pompes à chaleur.
- [ISO 20560-1:2024](https://www.iso.org/standard/86049.html), marquage de sécurité des tuyauteries physiques aériennes. Son objet ne définit pas la palette P&ID du projet.

Ces références situent les conventions applicables ; les tables et dessins normatifs protégés ne sont pas redistribués. Les dessins libres adaptés et le guide ne constituent pas une certification de conformité à l'ensemble de ces normes.
