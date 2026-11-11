# Changements publics

## Échanges P&ID, 11 novembre 2026 (sources)

- Cartouche compact et historique limité aux révisions renseignées, avec style détaillé disponible. Services explicites et palette partagée PDF/CAO/éditeur, codes textuels conservés en noir et blanc. Typographie CAO alignée sur les métriques PDF, centrages stockés sans dépendre du champ d'alignement LibreDWG, polices libres téléchargeables.
- Catalogue porté à 61 familles avec quatre dessins adaptés de pyflowsheet sous MIT et 16 fonctions d'instrumentation ; guide des repères ISA et liens ISO/EN, sans renommage des sources ni conformité normative inventée.

- Mise en page de bureau d'études pour PDF/DXF/DWG : formats A4 à A0, cartouche, champs documentaires d'entreprise/révision/date/folio/visas, notes et historique. Aperçu passif, données persistées avec le projet, traits et calques d'impression ; aucune approbation humaine automatique.

- Deux modèles FAT supplémentaires : vanne trois voies en mélange/diversion avec bilan volumique et échangeur dynamique à deux circuits avec bilan d'énergie. Sources de débit explicitement associées, défauts de position/encrassement, imports de ces familles documentaires par défaut. Aucune topologie physique déduite des lignes.

- Bibliothèque initiale de 41 familles documentaires avec piquages nommés et rotation, dont échangeurs et vannes trois/quatre voies. Objets inconnus conservés sans les transformer en indicateurs ; les neuf types historiques du banc restent distincts.
- Lecture des PDF denses avec aperçu/texte conservés et avertissement si la géométrie dépasse la borne. Filtrage des faux repères de cartouche/fichier et qualification explicite des préfixes ambigus.
- Essais séparant restauration native et géométrie réelle : bornes et coordonnées DXF/DWG contrôlées sans les métadonnées JSON. La reconnaissance de tout plan externe n’est pas revendiquée.

- Inspection locale de PDF, scans/images, SVG, DXF, DWG avec LibreDWG externe, graphes JSON/GraphML, tableaux et sous-ensemble XML DEXPI. Revue des objets/liaisons avant nouveau brouillon, provenance conservée.
- Export du schéma enregistré en SVG, PDF, PNG, DXF, DWG R2000 expérimental, JSON, GraphML, CSV ZIP et draw.io. Instantané lié à la révision, sans autorisation de cible ni verdict.
- Catalogue attribué à Scott Duncan, crédits des deux dépôts et licences dans le README et les notices. Lecteurs, OCR et convertisseur gratuits ; aucun service IA payant nécessaire.

## Portable du 7 novembre 2026 (application 0.2.1)

- Confirmation de cible réutilisable dans un onglet pour les seuls essais choisis, avec révocation et expiration après modification du projet, rechargement ou erreur. Les contrôles serveur restent exécutés à chaque connexion.
- Revue groupée des droits d’écriture des entrées simulées, sélection filtrée et annulation avant application au brouillon.

## Aperçu public 0.2.1

- Nom courant Vanguard FAT Studio, identité visuelle Vanguard et polices Geist locales ; noms et résultats des preuves historiques conservés.
- Paquet `vanguard-fat-studio`, nouveau CLI du même nom et lanceur `Vanguard-FAT-Studio.cmd` ; module `fat_studio`, commande `fat-studio`, formats et dossiers de données compatibles.

- Démonstration laboratoire : trois cuves, quatre pompes, huit vannes et 75 variables. Programme PLC de démonstration passif, indépendant des scénarios FAT.
- FAT pas à pas avec écritures préparées, application constatée sur un échange terminé et observations du testeur ; scénarios automatiques et tendances conservés.
- Pupitre BOOL avec impulsions gérées côté serveur ; stimuli analogiques en brut, ingénierie, pourcentage et unités de signal déclarées.
- Mode et état de l’essai visibles près du scénario. Les pupitres expliquent pourquoi une commande est grisée et quoi faire pour la débloquer.
- Projets et scénarios JSON versionnés ; archive complète du seul projet sélectionné et restauration dans un nouveau dossier local.
- Client local pour l’assistant choisi par l’utilisateur ; aucune clé API de modèle dans Vanguard FAT Studio.
- Sélection explicite des sources publiques et construction d’un portable Windows x64 avec Python officiel épinglé.

Les résultats d’essai restent rattachés à leurs reçus et à leur version. Le testeur saisit ses observations et la conclusion FAT séparément des contrôles automatiques.
