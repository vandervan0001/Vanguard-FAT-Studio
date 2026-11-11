# Ce que vérifient les essais P&ID

Une suite qui passe ne prouve pas la lecture de tous les plans, versions CAO et conventions de repérage. Les résultats sont rattachés aux cas et à l’état de source indiqués dans les reçus datés. Le banc possède onze types de modèles de simulation et une bibliothèque documentaire de 61 familles. Les symboles restent documentaires ; les modèles d'échangeur et de vanne trois voies demandent un choix et des paramètres explicites. La vanne quatre voies reste documentaire. Voir [les contrats de simulation](PID_SIMULATION.md).

## Trois vérifications distinctes

| Vérification | Ce qu’elle établit | Limite |
| --- | --- | --- |
| Restauration native | Objets, types, positions, rotations, provenance et piquages conservés grâce au JSON incorporé dans les exports. | Un SVG ou DXF dont le dessin est effacé peut encore restaurer ce JSON. Ce test ne mesure pas l’extraction du dessin visible. |
| Géométrie exportée | Symboles, textes, calques et coordonnées des raccordements présents dans le SVG/PDF/PNG et les entités DXF/DWG, y compris après suppression des métadonnées natives. | Un dessin correct à l’export ne qualifie pas le lecteur de tous les fichiers CAO externes ni un logiciel destinataire. |
| Extraction externe | Repères et géométrie proposés depuis des fichiers indépendants, écrits sans exporteur ni métadonnées FAT : PDF, SVG, DXF/DWG, images/OCR, graphes et tableaux. | Conventions, symboles, qualité des scans et extensions métier restent variables. Les propositions demandent une revue. |

Les imports draw.io et ZIP CSV relisent les données natives FAT. Ils ne sont pas présentés comme des lecteurs généraux de tout diagramme ou archive.

## Bibliothèque documentaire

Les familles couvrent cuves et réservoirs, réacteurs, colonnes, séparateurs, échangeurs tubulaires et à plaques, chauffage/refroidissement, chaudières, pompes, compresseurs, soufflantes, filtration, mélangeurs, vannes manuelles, vannes trois/quatre voies, clapets, régulateurs et organes de décharge. Un objet non classé peut rester générique, avec son type source, au lieu d’être remplacé par un indicateur PLC.

`Equipment.type: pid_symbol` déclare un objet documentaire et `symbol_kind` choisit son dessin. Les piquages physiques sont distincts des ports de variables PLC. Un échangeur possède `primary_in`, `primary_out`, `secondary_in`, `secondary_out` ; une vanne trois voies possède `AB`, `A`, `B`. Les connexions conservent `source_port` et `target_port`. Une rotation de 0, 90, 180 ou 270 degrés tourne le symbole et ses bornes. Un nom de piquage fournisseur non localisé est conservé et signalé, sans inventer sa position.

Ces objets ne produisent aucune mesure, valeur zéro ou qualité saine fictive. Ils n’ont pas d’association d’écriture PLC ; une animation peut lire une variable existante. Un projet exclusivement documentaire sans variable peut être enregistré et exporté ; il ne démarre pas de FAT vide.

## Cas réels et limites observées

- **Pahala, pages 10 à 25** : certains plans dépassent la borne de géométrie. L’import conserve désormais aperçu et texte, écarte les liaisons de la page incomplète et affiche un avertissement. L’OCR optionnel peut proposer des repères ; la reconnaissance demeure partielle. Les références de fichiers et de plans ne doivent pas devenir des pompes.
- **Virden, page 14 « Alum »** : les repères de cuves `AT-5510` et `AT-5520` ne permettent pas de conclure à des transmetteurs analogiques. Le préfixe ambigu reste à qualifier sur le dessin et sa légende. Le scan ne fournit pas de réseau de tuyauteries automatiquement validé.
- **XML DEXPI/Proteus** : lecture d’un sous-ensemble documentaire. Pas de conformité complète ni de reprise universelle des extensions ou des piquages fournisseur.
- **DWG** : conversion réelle par LibreDWG, écriture R2000 expérimentale. La géométrie peut être contrôlée après aller-retour ; l’acceptation dans une CAO propriétaire reste à vérifier.
- **Blocs DXF externes** : un attribut de repère peut être conservé sans reconnaissance de la forme, de la rotation ou des piquages du bloc. L'expansion générale des blocs et la reconnaissance des symboles fournisseur ne sont pas acquises.

Les tests utilisent des dossiers temporaires et des cibles loopback. Ils vérifient aussi les refus de contexte périmé, la conservation des brouillons, les bornes de données, l’absence de chargement de ressources externes, l’annulation et la disponibilité des commandes pendant l’inspection. Ils ne constituent pas une qualification Siemens, une validation de procédé ou un verdict FAT humain.

Pour utiliser les fonctions et connaître les formats : [guide P&ID](PID_EXCHANGE.md). Les crédits et licences sont dans les [notices tierces](../THIRD_PARTY_NOTICES.md).
