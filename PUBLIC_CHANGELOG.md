# Changements publics

## 0.4.0, 10 novembre 2026

- Collage de cellules Excel et import de tableaux CSV/TSV avec choix du séparateur, correspondance des colonnes modifiable et erreurs par ligne. Le sens et le type restent explicites, avec une valeur commune possible lorsqu’une colonne manque. L’aperçu conserve la fusion par identifiant et les contrôles des tags utilisés ; les nouvelles variables n’autorisent pas l’écriture par défaut.
- Explication des débits calculés : commande reçue, vitesse ou position, capacité disponible, organe limitant en série et volume disponible dans la source. Le dernier cycle et son pas sont affichés ; les données périmées ou de qualité indisponible ne servent pas de diagnostic actuel. Les interverrouillages internes du PLC ne sont pas déduits.
- Choix d’une cible déjà autorisée sur le poste, aperçu avant application au brouillon et contrôle de connexion en lecture seule. L’identité et le certificat précèdent l’authentification ; ce contrôle ne lit pas de valeurs de procédé et ne valide pas le mapping.
- Bibliothèque personnelle de circuits dans le navigateur, avec enregistrement, aperçu, réinsertion et export/import JSON. Les copies reçoivent de nouveaux identifiants, conservent leurs liaisons internes et effacent les NodeIds, adresses et symboles PLC. La connexion, les scénarios et les preuves d’essais sont exclus des modèles.
- Comparaison d’un brouillon retrouvé avec sa version de départ et le projet enregistré. Les champs sans conflit sont proposés ensemble ; chaque conflit reste à choisir. La reprise est vérifiée puis appliquée au brouillon. Le rapport, les observations et les étapes JSON non appliquées restent dans une copie téléchargée, sans fusion de résultats FAT.

Les formats de projet et de scénarios restent en version 1.0. Le reçu de la [release 0.4.0](https://github.com/vandervan0001/Vanguard-FAT-Studio/releases/tag/v0.4.0) détaille les vérifications du logiciel et du portable. Ces fonctions ne constituent pas une nouvelle qualification Siemens et n’attribuent aucun verdict FAT humain.

## 0.3.0, 10 novembre 2026

- Accueil avec démonstration manuelle prête à démarrer, création de procédé et reprise du projet. Le premier circuit se commande sans automate ni TIA Portal.
- Constructeur de transfert avec source, destination et organes en série : aperçu commun des conduites et des paramètres physiques avant application au brouillon.
- Modèles de remplissage, vidange, transfert entre cuves et pompe à variateur, ajoutables dans un projet existant. Trame FAT d’observation facultative, à relire et compléter.
- Duplication d’un équipement ou de son circuit avec nouveaux repères et tags, références internes remappées et identifiants PLC laissés vides.
- Diagnostics du brouillon avec accès aux équipements, rôles, variables, scénarios ou réglages concernés ; vérification locale distincte de la connexion réelle.
- Revue de toutes les liaisons aux tags dans une même fenêtre, propositions par repère, compteurs des rôles requis et application groupée.
- Import CSV avec fusion par identifiant, aperçu des ajouts/modifications/suppressions et refus des changements qui casseraient le contrat d’une variable utilisée. Remplacement complet disponible explicitement.
- Explorateur OPC UA des métadonnées sur la cible autorisée, avec contrôles d’identité, sélection des types/droits compatibles et aucune écriture de valeur ni démarrage d’essai.
- Annuler/rétablir dans l’éditeur et copie locale des brouillons dans le navigateur, avec reprise explicite et refus d’une révision périmée. Les observations restent rattachées à leur essai.
- Lanceur portable Windows avec état du service, réouverture de l’instance existante, arrêt explicite et mise à jour guidée dans une nouvelle copie vérifiée. Projets et historique restent hors du portable.

Les formats de projet et de scénarios restent en version 1.0. Le reçu de la [release 0.3.0](https://github.com/vandervan0001/Vanguard-FAT-Studio/releases/tag/v0.3.0) détaille les vérifications du logiciel et du portable. Ces changements ne constituent pas une nouvelle qualification Siemens et n’attribuent aucun verdict FAT humain.

## Portable P&ID du 7 novembre 2026 (application 0.2.1)

- Circuit de remplissage insérable en un clic dans un P&ID vide : cuve, pompe, vanne, conduites, tags locaux et paramètres du modèle.
- Recherche dans la bibliothèque, placement des équipements au clic sans superposition et repères disponibles après suppression.
- Tracé d’une liaison en choisissant le second équipement par son nom ; sélection lisible des cuves associées et sources de transfert.
- Fenêtre **Lier les tags automate** : rôles regroupés, recherche des tags compatibles, propositions par repère à relire, création des tags utiles et saisie du NodeId découvert.
- Annulation avant application au brouillon, distinction des tags de même nom et signalement des entrées déjà produites. Aucun NodeId ou réglage analogique déduit d’une adresse Siemens.

Cette construction inclut aussi les autorisations groupées du premier portable du 7 novembre décrit ci-dessous. Le nom du ZIP et le commit source distinguent les deux constructions.

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
