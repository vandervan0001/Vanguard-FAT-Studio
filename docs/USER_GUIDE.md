# Utiliser Vanguard FAT Studio

Vanguard FAT Studio est un banc d’essai local. Le programme PLC fournit ses commandes ; le modèle de procédé calcule les mesures, retours et défauts simulés, puis les renvoie au PLC par OPC UA. Le mode **Démonstration** utilise un contrôleur Python distinct pour essayer le banc sans Siemens.

Ce guide décrit le parcours dans l’interface. Pour piloter le même banc avec votre propre assistant, lire [le démarrage IA](AI_QUICKSTART.md). Le [contrat de pilotage](AI_CONTROL.md) précise le CLI et l’API locale. Les limites de la démo PLC sont précisées dans [DEMO_PLC.md](DEMO_PLC.md). Les projets et scénarios utilisent le [format JSON versionné](FORMAT.md).

## 1. Installer et ouvrir le banc

Sous Windows, extraire toute la distribution **portable**, puis double-cliquer sur `Start-FAT.cmd` ou `Vanguard-FAT-Studio.cmd`. Python et les dépendances sont inclus. La fenêtre du lanceur affiche l’état du service, ouvre le navigateur et permet de retrouver l’interface, d’ouvrir les données ou de quitter. Un second double-clic retrouve la même instance du portable. Le [guide du lanceur](PORTABLE_LAUNCHER.md) décrit l’arrêt, les diagnostics et la mise à jour guidée.

Depuis une copie **source**, installer Python 3.12 x64 ; son lanceur crée `.venv` et installe les dépendances verrouillées. Le navigateur ouvre [http://127.0.0.1:8765](http://127.0.0.1:8765). Dans ce mode console, garder la fenêtre du serveur ouverte ; `Ctrl+C` arrête le service.

Le portable contient `portable-manifest.json`, `runtime/` et `app/`. Le kit source contenant `offline-manifest.json` et `wheelhouse/` vérifie ses fichiers et utilise ses dépendances locales. Garder ces fichiers ensemble. Pour développer, créer une copie source selon [README-CODEX](../README-CODEX.md). Pour les politiques PowerShell, un Python non standard ou l’installation sans Internet, suivre [INSTALLATION.md](INSTALLATION.md).

Sous Linux/macOS, depuis une copie source avec Python 3.12, lancer `bash scripts/start.sh`. La démonstration fonctionne sans TIA. TIA Portal et PLCSIM Advanced nécessitent Windows et leurs installations/licences propres.

Après installation, un contrôle local peut être lancé depuis la racine du dossier :

```powershell
.\.venv\Scripts\python.exe -m fat_studio doctor --json
```

Dans le portable, remplacer `.venv\Scripts\python.exe` par `runtime\python.exe`. `doctor` vérifie les dépendances et l’interface compilée. Il ne contacte pas Siemens et ne qualifie aucune CPU.

Le stockage habituel est `%LOCALAPPDATA%\FATStudio` sous Windows et `~/.fat-studio` ailleurs. `FAT_STUDIO_DATA` ou l’option CLI `--data-dir` choisit un autre dossier. Un seul processus serveur peut utiliser un même dossier de données.

## 2. Repérer les commandes

| Zone | Utilisation |
| --- | --- |
| Bandeau supérieur | Mode de contrôle, temps simulé, démarrer/reprendre, pause, arrêt, réinitialisation |
| Barre du projet | Nom, état enregistré, accueil, annuler/rétablir, nouveau/ouvrir/importer/exporter/enregistrer |
| **Accueil** | Essayer la démo, créer un procédé ou reprendre le projet courant |
| **Préparer l’essai** | Vérification du brouillon et accès direct aux équipements, variables ou réglages à corriger |
| **P&ID** | Dessin, pupitre d’entrées, observation des sorties, sélection et suivi de la FAT |
| **Variables & mapping** | Types, sens, valeurs, qualités, associations et identifiants PLC/OPC UA |
| **Scénarios** | Préparation des FAT pas à pas et des séquences automatiques |
| **Tendances & rapport** | Courbes, journal, marqueurs, observations, conclusion et exports |
| **Connexion** | Source des commandes, version TIA, pas de calcul, cible OPC UA et diagnostics |
| Pied de page | Contrôleur actif, cible, pas, vitesse et compteur d’écritures |

Le nom du mode doit correspondre à l’essai prévu. En **DÉMONSTRATION**, le pied de page indique un contrôleur de démonstration et aucun automate raccordé. Choisir V20/V21 dans Connexion ne convertit aucun projet Siemens.

Pendant un essai en cours, la structure est verrouillée. **Pause** suspend les échanges et rend le constructeur accessible. Sans modification enregistrée, **Reprendre** continue le même essai. **Appliquer en pause** enregistre les modifications, clôture l’ancien essai sans verdict humain et conserve ses preuves ; le projet revient au repos. Un nouveau **Démarrer** ouvre ensuite un nouvel essai. Une pause ne met pas une CPU externe en STOP.

## 3. Réaliser un premier essai sans Siemens

### Découvrir avec un petit circuit

1. Dans **Accueil**, choisir **Essayer la démo**. Un nouveau projet contient une cuve, une pompe, une vanne et leurs tags locaux. Les projets précédents restent disponibles dans **Ouvrir**.
2. Cliquer **Démarrer**, puis **Ouvrir la vanne** et **Mettre la pompe en marche** dans le bandeau **Votre premier essai**.
3. Observer le niveau de la cuve et les retours des équipements. Le contrôleur de démonstration traite les demandes manuelles ; aucun automate ni TIA Portal n’est nécessaire.
4. Cliquer **Essayer un défaut moteur**. Observer l’arrêt physique de la pompe, puis **Rétablir le moteur**. La demande de marche peut rester active pendant ce défaut : cette démo n’ajoute pas d’interverrouillage métier au programme testé.
5. Fermer la vanne ou arrêter la pompe depuis le même bandeau, puis **Arrêter l’essai** pour clore l’acquisition. Les tendances et les preuves restent consultables. Aucun verdict FAT humain n’est attribué automatiquement.

L’accueil apparaît à la première ouverture du navigateur et reste accessible par **Accueil**. **Créer mon procédé** ouvre un projet vide ; **Reprendre mon projet** ferme l’accueil et retrouve l’éditeur. **Masquer les indications** retire le bandeau de découverte.

### Explorer le laboratoire complet

1. Dans **Ouvrir**, cliquer **Charger le laboratoire**. Le projet devient **FAT LAB · Banc de transfert** : trois cuves, quatre pompes, huit vannes, instruments et pupitre, soit 36 objets et 75 variables. Enregistrer auparavant tout brouillon utile.
2. Dans **P&ID**, sélectionner **01 · Alimentation de la cuve source**, puis **Préparer la vue**.
3. Cliquer **Démarrer**. Le banc valide le projet et ouvre un nouvel essai.
4. Observer TK-101, la commande de P-101, son retour marche et les tendances. Le temps affiché est celui du modèle.
5. À sept secondes simulées, le scénario se termine en pause ; ses contrôles conservent les attentes, valeurs lues, qualités et résultats.
6. Dans **Tendances & rapport**, lire les données puis saisir une conclusion humaine seulement après votre revue. **Non évalué** reste le résultat tant qu’elle n’a pas eu lieu.
7. Télécharger CSV, rapport HTML et preuves JSON. Pour une sauvegarde du projet et de son historique, utiliser **Ouvrir → Exporter l’archive FAT**.
8. Pour une autre séquence, arrêter/réinitialiser le modèle, vérifier les conditions initiales du PLC externe s’il est utilisé, puis démarrer un nouveau scénario.

Les huit séquences automatiques illustrent remplissage, deux transferts, vidange, contact d’arrêt, défaut de pompe, vanne bloquée et conversion analogique. Le neuvième scénario est guidé. Le programme de démo recopie des demandes manuelles ; les séquences de test sont dans Vanguard FAT Studio. Un défaut moteur peut donc couper le retour physique alors que la commande PLC reste TRUE : ce cas est attendu dans cette démo passive, sans interverrouillage métier ajouté.

## 4. Utiliser le pupitre I/O

### Préparer la vue

Le P&ID s’ouvre en mode test. Utiliser **Construire** pour modifier le dessin, puis **Tester les I/O** pour revenir au pupitre et à l’observation. Le mode test présente les entrées digitales à gauche, les objets de procédé du laboratoire au centre et les entrées analogiques à droite. Les sorties PLC affichées sont lues depuis le contrôleur.

Choisir une FAT puis cliquer **Préparer la vue** pour cadrer les équipements concernés. Les métadonnées de la FAT peuvent aussi choisir les courbes utiles. Le laboratoire garde ses 36 objets dans le projet ; le cadrage permet de se concentrer sur le procédé du test.

**Mode présentation** masque les pupitres pour agrandir le dessin. **Afficher les pupitres** les réouvre et **Masquer les pupitres** les cache à nouveau ; **Quitter la présentation** rend la disposition de test habituelle. Ce changement d’affichage ne met pas l’essai en pause et ne change aucune commande.

### Entrées digitales à gauche

À côté du sélecteur de scénario, le bandeau affiche le mode d’essai et son état. Les pupitres indiquent si leurs commandes sont disponibles. Un clic sur une commande grisée affiche la raison à cet endroit, sans envoyer d’écriture. Au repos, démarrez l’essai. En pause, reprenez-le pour actionner les contacts TOR. Un forçage analogique reste possible en pause, puis les échanges reprennent avec l’essai.

Le laboratoire fournit 40 entrées BOOL ; le pupitre liste toutes les variables `input` de type BOOL du projet, y compris celles sans symbole de bouton dans le dessin. L’écriture doit être autorisée pour que la commande soit active.

| Geste | Effet |
| --- | --- |
| Clic simple | Inverse la valeur du contact pendant **300 ms simulées**, puis rend l’état précédent |
| Double clic | Maintient la valeur inverse ; un nouveau double clic libère le maintien |
| **Libérer le maintien** | Rend le signal au modèle |

Un clic souris attend environ **550 ms** avant son envoi pour pouvoir reconnaître un double clic. L’impulsion de 300 ms simulées commence ensuite côté serveur. Ce délai de reconnaissance et la durée du contact sont deux temps distincts.

Le serveur gère le retour de l’impulsion. Fermer le navigateur ne prolonge pas l’impulsion tant que le serveur et l’essai continuent. Sa durée suit le temps du modèle et le pas de calcul ; elle ne constitue pas une temporisation matérielle garantie. Une pause ou un arrêt ferme les échanges du banc.

Un contact normalement fermé, initialement à TRUE, passe donc à FALSE au clic puis retrouve son état. Le clic ne signifie pas systématiquement « mettre à TRUE ». La valeur `0/1`, le témoin et l’état de forçage permettent de constater le résultat. Après libération, le modèle peut produire une valeur différente de la valeur initiale si le procédé a évolué.

Ces commandes sont disponibles pendant un essai en cours. Elles écrivent uniquement des entrées simulées autorisées. Une commande de pompe ou de vanne déclarée `output` reste une lecture du PLC.

### Entrées analogiques à droite

1. Démarrer un essai libre ou une FAT.
2. Repérer la variable par son nom, son type et son adresse/symbole documentaires.
3. Saisir la valeur de test. Sans conversion déclarée, la saisie utilise l’unité native du tag.
4. Si un signal est déclaré, choisir **Brut**, **Ingénierie**, **Pourcentage**, **Courant · mA** ou **Tension · V** selon ce signal. Contrôler l’aperçu de conversion avant d’appliquer.
5. Cliquer **Forcer**. La mesure reste forcée jusqu’à une modification, une libération ou une réinitialisation.
6. Cliquer **Modifier** pour changer la valeur maintenue ; utiliser **Libérer** pour rendre la mesure au modèle.

Le curseur **Plage nominale** et les préréglages **0 %, 25 %, 50 %, 100 %** préparent la saisie ; cliquer ensuite **Forcer** ou **Modifier** pour l’appliquer. Déplacer le curseur seul ne change pas une entrée PLC. La saisie conserve l’unité sélectionnée et affiche la valeur brute préparée.

Les 16 entrées analogiques du laboratoire déclarent leurs plages et disposent du curseur : niveaux bruts 4 à 20 mA, volumes en litres, demandes et retours de vitesse ou de position en pourcentage. Les unités proposées dépendent de chaque déclaration ; une tension n’est proposée que pour un signal `0-10V`.

Avec un signal `4-20mA` déclaré de 0 à 27 648 comptes, **12 mA produit 13 824 comptes**. La plage ingénierie est déclarée séparément : une échelle de 10 à 30 °C donne alors 20 °C. La logique PLC testée doit utiliser l’échelle attendue ; modifier celle du pupitre ne modifie pas son programme. Le signal `0-10V` utilise également sa plage brute déclarée. Aucune conversion n’est déduite du nom, de l’adresse ou du type du tag.

Le forçage normal respecte le type et les limites du tag. La case **Stimulus de diagnostic hors plage** ouvre un mode explicite d’essai hors limites nominales. Pour un signal 4–20 mA, **Injecter 0 mA** et **Injecter 24 mA** appliquent immédiatement le stimulus de diagnostic. Lire le code brut et le profil affichés avant l’injection ; ces boutons ont un effet immédiat, tandis que les préréglages en pourcentage ne font que préparer une valeur. Les limites du type PLC restent toujours contrôlées. La libération rend la mesure au modèle.

## 5. Préparer et dérouler une FAT pas à pas

La FAT pas à pas est une séquence de test déclenchée par l’opérateur. Son enchaînement rappelle une lecture par étapes ; cette fonction ne revendique pas une conformité à la norme GRAFCET/IEC 60848.

### Construire la séquence

1. Arrêter ou mettre en pause l’essai, puis ouvrir **Scénarios**. Une application en pause clôturera l’ancien essai en conservant ses preuves.
2. Cliquer **Nouveau scénario** et choisir **Mode d’exécution → FAT pas à pas**.
3. Renseigner le nom, l’objectif, l’exigence et les conditions initiales. Décrire les états du procédé et du PLC à obtenir avant le premier STEP.
4. Cliquer **Ajouter une étape**. Donner un nom et des instructions exploitables par le testeur.
5. Dans **Écritures préparées**, cliquer **Ajouter une écriture**, sélectionner une entrée simulée et choisir **Forcer** ou **Libérer**. Saisir un booléen ou une valeur dans une unité compatible avec la conversion du tag : brut, ingénierie, pourcentage, mA ou V. Le mode diagnostic doit être explicitement coché pour un stimulus hors plage. Les boutons **Préparer 0/24 mA** du constructeur renseignent une future écriture du STEP ; ils ne l’exécutent pas.
6. Renseigner **Résultat attendu** en texte. Décrire la réaction attendue, son délai si celui-ci fait partie du protocole et les valeurs que le testeur doit lire.
7. Ajouter des **Contrôles mesurables (facultatifs)** : variable, opérateur, attente et tolérance. Les attentes numériques restent dans l’unité native de la variable contrôlée.
8. Répéter les étapes, les réordonner si nécessaire et prévoir une dernière étape de libération des stimuli.
9. Enregistrer le projet, puis utiliser **Connexion → Valider le projet**.

Les actions préparées d’un STEP sont validées avant de changer l’image de forçage. Les nombres non finis ou non représentables en double précision sont refusés à l’import avant enregistrement. Pendant l’attente du premier échange du STEP, les forçages, libérations, impulsions et injections de défaut sont temporairement suspendus. Le banc confirme ensuite les valeurs du lot transmis et conserve leur valeur brute dans les preuves (`actual_wire_value`). Pour une libération, il vérifie aussi l’absence de forçage. Un écart interrompt l’essai sans déclarer le STEP appliqué. Une étape peut contenir plusieurs écritures ; un lot OPC UA partiellement accepté demeure partiel et ne peut pas être annulé par le modèle.

### Exécuter et observer

1. Revenir au P&ID, sélectionner la FAT puis **Préparer la vue**.
2. Vérifier les conditions initiales et cliquer **Démarrer**. Ce bouton ouvre l’essai ; les écritures du STEP attendent son déclenchement.
3. Cliquer **Exécuter STEP 1**. Attendre l’indication d’application des écritures sur un cycle terminé.
4. Laisser au programme et au procédé le temps de réagir prévu par le protocole. Le modèle continue à avancer pendant cette observation.
5. Lire la réaction, les courbes et les qualités. Saisir **Observation du testeur**, puis choisir **Conforme** ou **Écart**.
6. Les contrôles mesurables sont évalués au moment de ce choix. **Conforme** est refusé si un contrôle mesuré échoue. Corriger l’état avant de réévaluer, ou consigner l’écart constaté.
7. L’étape suivante devient accessible après enregistrement de l’observation. Chaque STEP se déclenche une fois et dans l’ordre préparé.
8. Après la dernière observation, le banc termine le scénario en pause et ferme ses échanges.
9. Ouvrir le rapport et saisir séparément la conclusion FAT globale. Les observations de STEP ne la remplissent pas automatiquement.

Une FAT guidée n’expire pas à la durée du scénario automatique. L’opérateur décide quand déclencher et observer. Le temps simulé et les échantillons continuent d’être enregistrés. La pause suspend les échanges ; elle ne met pas une CPU externe en STOP.

### Exemple fourni dans le laboratoire

Sélectionner **09 · FAT manuelle pas à pas**. Ses cinq STEP préparent :

1. `guided-initial` : 12 mA sur `lt101_raw`, soit 13 824 comptes et `lt101_percent` à 50 %, pompe non commandée.
2. `guided-run` : demande P-101 à 50 % et ouverture XV-101, puis lecture des commandes et du retour marche.
3. `guided-stop` : ouverture de `stop_healthy`, puis lecture des commandes inhibées et de l’arrêt physique simulé.
4. `guided-requests-off` : retrait des demandes avant rétablissement du contact.
5. `guided-release` : libération des stimuli et retour aux entrées du modèle.

Lire les instructions et contrôles de chaque STEP. Ce contact d’arrêt de démo n’est pas une fonction de sécurité. En OPC UA, rétablir les conditions initiales prévues du programme ; le reset du banc agit sur son modèle local.

## 6. Utiliser un scénario automatique

Choisir **Mode d’exécution → Automatique temporisé** pour programmer une séquence sur le temps simulé. Les actions sont datées par `at_s`, triées par temps croissant et contenues dans la durée. Dans l’éditeur JSON, appliquer les étapes avant d’enregistrer le projet.

| Action | Cible et effet |
| --- | --- |
| `force` | Maintient une entrée simulée autorisée à la valeur donnée |
| `release` | Rend cette entrée au modèle |
| `fault` | Injecte un défaut compatible sur un équipement |
| `clear_fault` | Efface le défaut de l’équipement |
| `marker` | Écrit un événement de repère |
| `expect` | Compare une mesure à une attente et conserve le résultat |

Exemple dans le laboratoire, à intégrer à un scénario existant :

```json
[
  {"at_s": 1, "action": "force", "target": "p101_request", "value": true},
  {"at_s": 1.4, "action": "release", "target": "p101_request"},
  {"at_s": 4, "action": "expect", "target": "p101_command", "operator": "eq", "value": true,
   "message": "Commande pompe active après le départ"}
]
```

Les actions s’exécutent au premier début de cycle atteignant leur date ; les assertions à la première fin de cycle atteignant leur date. Prévoir au moins un pas de modèle, ainsi que le délai de réaction réel, entre une mutation et le contrôle de son effet. La validation refuse une mutation trop tardive pour être suivie d’un échange avant la fin du scénario.

Les opérateurs numériques sont `eq`, `ne`, `gt`, `ge`, `lt`, `le`. BOOL accepte `eq`/`ne`. `eq`/`ne` numérique utilise une tolérance absolue ; les comparaisons d’ordre n’utilisent pas cette tolérance. Les valeurs REAL échangées sont Float32 : choisir une tolérance cohérente plutôt que modifier une attente pour obtenir une réussite.

Le suivi affiche les actions prévues, leur progression et les contrôles avec attente, valeur lue, qualité et résultat. À la fin, le banc arrête les écritures et attend la conclusion humaine. Les huit scénarios temporisés du laboratoire contiennent 31 contrôles ; leurs résultats sont propres au programme passif de cette démo.

### Échanger des scénarios

Dans **Scénarios**, **Exporter tous les scénarios** produit une enveloppe JSON1.0 avec les contrats de variables et d’équipements utilisés. **Exporter ce scénario** limite le fichier à la sélection. **Importer des scénarios** propose **Ajouter sans remplacer** ou **Remplacer les scénarios**. Le premier mode refuse les identifiants déjà présents ; le second remplace la liste explicitement. Aucun mode ne modifie les tags pour rendre compatible un scénario. Lire **Format et règles d’import** et [FORMAT.md](FORMAT.md) avant un échange entre projets.

## 7. Créer le P&ID et ses variables

### Dessiner et paramétrer

1. Cliquer **Nouveau**, donner un nom puis **Créer le projet**. Le projet commence vide en démonstration.
2. Dans **P&ID → Construire**, ouvrir **Circuits et transferts** pour insérer un modèle ou relier les équipements existants. Le raccourci **Insérer un circuit de remplissage** reste disponible dans un dessin vide. Pour composer un autre procédé, rechercher un équipement dans la bibliothèque, puis cliquer dessus ou le glisser sur le dessin. Les ajouts au clic occupent une place libre et reçoivent un repère disponible.
3. Déplacer les symboles et utiliser le zoom/panoramique pour organiser la vue. Pour tracer seulement une conduite graphique, sélectionner le premier équipement, choisir le second dans **Relier à**, puis cliquer **Tracer la liaison**. Les points de connexion du dessin restent utilisables.
4. Sélectionner un équipement et ouvrir **Lier les tags automate** en haut de ses propriétés. Associer ses rôles aux variables existantes ou créer les tags manquants selon le parcours ci-dessous.
5. Renseigner les paramètres physiques. Pour les pompes/vannes, choisir la cuve par son nom, le sens et le groupe de débit. Pour un transfert, choisir aussi la **Cuve source du transfert** ; **Source extérieure** signifie qu’aucune autre cuve du modèle n’est débitée.
6. Lire les points du panneau **Préparer l’essai**, corriger les champs concernés puis enregistrer avec le bouton ou `Ctrl+S` (`Cmd+S` sur macOS). **Valider** reste accessible dans **Connexion**.

La bibliothèque comprend neuf types : cuve, pompe, pompe à variateur, vanne TOR, vanne modulante, capteur analogique, capteur binaire, bouton/contact et indicateur PLC. Les paramètres et ports disponibles dépendent du type. Le catalogue actif est aussi accessible par l’API pour un assistant.

Le circuit de départ est proposé seulement lorsque le P&ID est vide. Il prépare trois équipements, deux conduites et treize tags locaux. La pompe et la vanne sont configurées en série vers la cuve, avec un même groupe de débit. Les tags déjà présents sont conservés. Le bouton ne démarre pas d’essai et ne change pas le mode de connexion du projet. Dans un nouveau projet en démonstration, enregistrer puis cliquer **Démarrer** permet de voir le remplissage, sans automate ni TIA Portal. Les NodeIds créés restent vides.

Les traits sont des connexions visuelles. Les groupes de débit explicitement déclarés fixent le calcul : minimum des capacités des équipements en série, somme des branches indépendantes. Lire [MODEL.md](MODEL.md) pour le bilan de cuve et les limites du modèle. Le P&ID ne calcule pas un réseau hydraulique général.

Un brouillon incomplet peut être enregistré ; les erreurs sémantiques restent visibles et empêchent son démarrage. La limite du format est de 50 équipements et 200 variables par projet.

### Insérer un modèle réutilisable

Dans **Circuits et transferts → Insérer un modèle**, choisir **Remplissage**, **Vidange**, **Transfert entre cuves** ou **Pompe à variateur**. L’aperçu indique les équipements et tags supplémentaires. **Appliquer le circuit** les ajoute au brouillon, y compris dans un projet déjà rempli, avec des repères, identifiants et circuits distincts. Les équipements existants et le mode de connexion sont conservés. Enregistrer après relecture des paramètres et associations.

Chaque modèle prépare ses conduites et les paramètres de son débit. Les tags sont locaux, sans NodeId OPC UA. **Ajouter une trame FAT à relire** prépare trois étapes d’observation : état initial, écoulement, fin de transfert. Adapter leurs instructions et résultats attendus au programme testé. La trame ne contient aucune écriture préparée, aucun contrôle mesurable et aucun verdict.

### Configurer un transfert entre équipements existants

1. Ouvrir **Circuits et transferts → Relier mes équipements**.
2. Choisir la **Source du transfert**, une cuve existante ou une alimentation extérieure, puis une autre cuve comme **Destination du transfert**.
3. Cocher les pompes et vannes qui appartiennent au trajet. Les boutons **Avancer** et **Reculer** règlent leur ordre sur le dessin.
4. Relire l’aperçu. Les organes choisis partageront un circuit en série ; le modèle débitera la source et alimentera la destination. Pour une alimentation extérieure, aucune autre cuve du modèle n’est débitée.
5. Cliquer **Appliquer le circuit**, puis **Enregistrer**.

Cette opération renseigne ensemble la cuve destination, la cuve source, le sens d’entrée et le groupe de débit. Elle remplace les conduites graphiques physiques qui touchent les organes choisis ; l’aperçu en donne le nombre. Les liaisons d’instruments, débits maximaux, temps de réponse et associations aux tags restent conservés. Si un organe partage déjà son groupe physique avec d’autres, inclure ce groupe entier avant de modifier son trajet. Une cuve ne peut pas être sa propre source.

Le constructeur prépare les circuits pris en charge par le modèle. Il ne déduit pas un réseau hydraulique général à partir des traits, et les liaisons tracées seules par **Relier à** restent graphiques.

### Dupliquer un équipement ou un circuit

Sélectionner un équipement, puis **Dupliquer cet équipement ou son circuit**. Depuis une pompe ou une vanne, l’option **Inclure son circuit, les cuves et les capteurs associés** copie son groupe physique complet, les cuves référencées et les capteurs rattachés. Depuis un autre symbole, la copie concerne ce symbole seul. Relire l’aperçu puis **Appliquer la copie**.

La copie reçoit de nouveaux repères et tags. Ses conduites et références internes sont réorientées vers les éléments copiés. Les références à des équipements restés hors de la copie sont laissées à choisir. Les NodeIds, adresses et symboles PLC des tags copiés sont vides : revoir le mapping avant de connecter un automate. Les scénarios et preuves ne sont pas dupliqués.

### Conserver ses propres modèles de circuit

1. Dans **Construire**, sélectionner une pompe ou une vanne puis **Enregistrer ce circuit**.
2. Donner un nom au modèle et cliquer **Enregistrer dans ma bibliothèque**. Le circuit, ses cuves, ses capteurs et ses conduites sont vérifiés avant l’enregistrement.
3. Dans ce projet ou un autre, ouvrir **Mes circuits** à côté de **Circuits et transferts**, puis choisir le modèle.
4. Cliquer **Préparer la copie**, relire son contenu, puis **Appliquer la copie au brouillon**. Revoir les associations aux tags et enregistrer le projet.

La copie reçoit de nouveaux repères et identifiants, avec ses liaisons internes conservées. Les NodeIds, adresses et symboles PLC restent vides. La bibliothèque ne conserve ni connexion automate, ni scénarios, ni preuves d’essais. Un circuit incomplet doit être corrigé avant son enregistrement comme modèle ; les autres erreurs éventuelles du projet destinataire restent visibles dans **Préparer l’essai**.

Les modèles restent dans ce navigateur, à l’adresse locale du banc. La limite est de 20 modèles et 2 Mio pour la bibliothèque. **Exporter la bibliothèque** en télécharge une copie JSON. Pour la retrouver dans un autre navigateur ou sur un autre poste, choisir **Importer une bibliothèque**, relire les modèles proposés puis **Importer ces modèles**. Une copie identique déjà présente est ignorée ; un nom ou un identifiant en conflit bloque l’import sans remplacer l’existant.

Supprimer un modèle conserve ses copies déjà insérées dans les projets. Une archive FAT n’inclut pas la bibliothèque du navigateur : l’exporter séparément avant d’effacer les données du navigateur. Le [format de bibliothèque](FORMAT.md#bibliothèque-personnelle-de-circuits) détaille ses limites.

### Corriger depuis les diagnostics

Le panneau **Préparer l’essai** vérifie le brouillon sans l’enregistrer ni contacter une CPU. Cliquer sur un point ouvre l’équipement et son rôle, la variable, le scénario ou le réglage concerné. Les conseils de configuration restent repliés. **Configuration locale prête** signifie que les contrôles locaux passent ; en OPC UA, la connexion, les types et les droits réels des nœuds restent à vérifier avant les échanges.

### Comprendre un débit nul ou limité

Pendant un essai, cliquer **Expliquer les débits** en haut du P&ID, puis choisir la pompe ou la vanne à examiner. La fenêtre **Comprendre le débit** présente le dernier cycle calculé, son temps simulé et son pas de calcul. Elle montre la commande reçue, la vitesse ou la position calculée et demandée, puis la capacité disponible de chaque organe du circuit.

Le débit en série suit l’organe limitant ; les circuits indépendants s’additionnent. La fenêtre indique aussi si le liquide disponible à la source limite le transfert, en tenant compte de son alimentation extérieure et des sorties qui partagent ce volume. Une commande d’arrêt, une vanne fermée ou bloquée, un défaut moteur, une consigne réduite ou un temps de réponse encore en cours sont expliqués lorsqu’ils interviennent dans le modèle. Cliquer le nom d’un équipement le retrouve sur le dessin.

En pause ou après arrêt, la fenêtre indique qu’il s’agit du dernier cycle calculé. Au repos, attendre le démarrage d’un essai ; après une modification de modèle ou de défaut, un nouveau cycle peut être nécessaire. Les anciennes valeurs ne sont pas présentées comme un diagnostic actuel si le service est indisponible, si les échanges ont une qualité invalide, si l’essai est en erreur ou si le brouillon du modèle a changé.

Ces explications décrivent le modèle et les commandes qu’il reçoit. Elles ne déduisent pas les interverrouillages internes du programme automate. Une conduite dessinée seule ne crée pas un transfert physique ; les limites du calcul restent celles de [MODEL.md](MODEL.md).

### Annuler et retrouver un brouillon

Les boutons **Annuler la modification** et **Rétablir la modification** agissent sur les changements du projet avant enregistrement. Hors d’un champ de saisie, utiliser aussi `Ctrl+Z` et `Ctrl+Maj+Z` (`Cmd` sur macOS). Dans un champ, les raccourcis restent ceux de la saisie. L’historique de l’éditeur est réinitialisé lors de l’enregistrement ou du remplacement du projet ; il ne remplace pas l’historique des essais.

Le navigateur conserve automatiquement les modifications non enregistrées dans son stockage local. Cette copie est rattachée au dossier FAT, au projet et au document ouvert. Elle ne modifie pas le projet enregistré ni un essai. Si le stockage du navigateur est indisponible, un message propose de télécharger le brouillon.

Après rechargement, **Brouillon retrouvé** permet de reprendre explicitement les modifications, de les télécharger ou de **Continuer sans reprendre**. Choisir avant de poursuivre l’édition. Si la révision enregistrée a changé, utiliser la comparaison ci-dessous. Les observations et conclusions restent rattachées à leur essai d’origine. La récupération dans le navigateur ne remplace pas une archive `.fat.zip`, et effacer les données du navigateur peut effacer ces brouillons.

### Comparer un brouillon avec le projet enregistré

Dans **Brouillon retrouvé**, choisir **Comparer les versions**. Chaque changement présente trois valeurs : **Au départ**, **Enregistré maintenant** et **Mon brouillon**. Le logiciel propose les champs modifiés dans le brouillon ; les autres modifications de la version enregistrée sont conservées.

Les champs sans conflit sont présélectionnés. Cocher ou décocher chaque ligne ; un conflit reste décoché jusqu’à votre choix. **Choisir les champs sans conflit** et **Tout décocher** permettent de reprendre la sélection. Cliquer **Reprendre les champs choisis** pour vérifier le résultat, puis **Enregistrer** dans le projet pour le sauvegarder. Une sélection qui ajoute des incohérences, par exemple une liaison sans son tag, est refusée et les champs concernés sont indiqués. Reprendre aussi les éléments liés ou retirer le choix.

La comparaison exige la version de départ conservée avec les nouveaux brouillons. Une ancienne copie qui ne la contient pas reste téléchargeable. Si le projet ou l’essai change pendant la comparaison, fermer la fenêtre et relire le contexte ; le brouillon est conservé.

Le rapport, les observations et le texte d’étapes JSON encore non appliqué restent hors de la fusion. Lorsqu’ils existent, la reprise télécharge une copie complète du brouillon d’origine pour les conserver séparément. La comparaison ne transfère pas de constat ni de verdict FAT vers un autre essai. **Télécharger le brouillon d’origine** reste aussi disponible avant tout choix ; **Annuler** ferme la fenêtre sans reprendre de champ.

### Lier un équipement aux tags automate

1. Sélectionner l’équipement dans **Construire**, puis **Lier les tags automate**. À gauche figurent ses rôles : commande, retour, défaut, niveau, etc. La mention **requis** distingue les associations nécessaires ; le compteur inclut aussi les rôles facultatifs.
2. Choisir un rôle. La liste présente seulement les tags dont le sens et le type conviennent. Rechercher par nom, symbole PLC, adresse ou NodeId, puis cliquer le tag voulu. Deux tags de même nom affichent aussi leur identifiant pour pouvoir les distinguer.
3. Pour aller plus vite, cliquer **Proposer depuis le repère**. Par exemple, la commande de `P-101` peut correspondre à `P101_RunCommand` et son retour à `P101_Running`. Les propositions utilisent les noms et symboles PLC, complètent seulement les rôles libres et exigent une correspondance unique. Relire les associations proposées ; les cas ambigus restent à choisir.
4. Si le tag n’existe pas, utiliser **Créer un tag BOOL/REAL/…** pour le rôle sélectionné, ou **Créer les tags manquants** pour tous les rôles encore libres. Un choix de type apparaît lorsque le rôle en accepte plusieurs. Les nouveaux tags n’ont pas de NodeId ; ils peuvent être renommés et leurs limites réglées dans **Variables & mapping**.
5. Pour une connexion OPC UA, déplier **NodeId OPC UA de…** et coller l’identifiant réellement découvert. La revue globale décrite ci-dessous permet aussi de choisir ce NodeId sur le serveur après préparation de la cible. Cette modification concerne le tag et toutes ses utilisations. Aucun NodeId ni aucune échelle analogique ne sont déduits d’une adresse Siemens. En démonstration, ce champ peut rester vide.
6. Cliquer **Appliquer au brouillon**, puis **Enregistrer** dans le projet. **Annuler**, la croix ou Échap abandonne les changements de cette fenêtre, y compris les tags qu’elle venait de préparer.

Une entrée déjà produite par un autre équipement est signalée et ne peut pas être choisie comme second producteur physique. Les commandes PLC restent en lecture seule ; plusieurs équipements peuvent les lire. Les demandes manuelles ne sont pas considérées comme des producteurs physiques. Vérifier les droits d’écriture des entrées dans **Variables & mapping** avant une connexion.

Si le projet change ou devient verrouillé, la sélection reste visible dans la fenêtre et l’application est désactivée. Relire le projet avant de refaire les associations. Le logiciel ne reprend pas automatiquement une opération interrompue. Les listes d’association dans les propriétés restent disponibles pour les modifications ponctuelles.

### Revoir toutes les associations

Dans **Variables & mapping**, ouvrir **Revoir toutes les liaisons aux tags**. Les trois colonnes présentent équipements, rôles et tags compatibles. Le compteur distingue les rôles requis du total des rôles disponibles.

**Proposer pour tous les équipements** complète les correspondances uniques depuis les repères ; les associations déjà renseignées et les cas ambigus restent à relire. Choisir chaque rôle pour modifier sa liaison, ou **Créer les tags manquants de cet équipement** pour préparer ses tags locaux. Un tag d’entrée déjà produit physiquement par un autre rôle est signalé et ne peut pas devenir un second producteur.

**Appliquer les liaisons au brouillon** regroupe les changements de cette revue. **Annuler** les abandonne. Enregistrer ensuite le projet. Les NodeIds peuvent être choisis dans l’explorateur décrit ci-dessous ; cela ne crée aucune autorisation d’écriture ni aucune échelle analogique.

### Animer un symbole depuis une variable

1. Mettre en pause l’essai ou travailler au repos, puis sélectionner un équipement dans **Construire**.
2. Ouvrir **Animation par variable** et cocher **Lier l’apparence à un tag**.
3. Choisir **Variable d’animation**, **Condition active**, **Valeur active** puis **Effet visuel** : couleur, pulsation, rotation, niveau ou position.
4. Pour niveau/position, définir les valeurs correspondant à 0 et 100 %. Une variable numérique est requise. BOOL compare TRUE/FALSE avec égalité ou différence.
5. Choisir les couleurs active/inactive et enregistrer, ou **Appliquer en pause** pour préparer un nouvel essai.

Cette liaison est en lecture seule : elle ne modifie ni la commande PLC, ni les associations physiques, ni un forçage. Le texte d’aperçu distingue valeur acquise, valeur initiale et qualité indisponible. Une sortie peut animer plusieurs symboles sans être écrite. Le pourcentage dessiné est borné graphiquement de 0 à 100 % ; la mesure et sa qualité restent visibles. Cette animation ne remplace pas un contrôle FAT mesuré.

### Déclarer une variable

Dans **Variables & mapping**, cliquer **Nouvelle variable**, puis ouvrir sa ligne. Renseigner nom, sens, type, valeur initiale, unité, limites et associations.

| Sens, vu du PLC | Usage |
| --- | --- |
| `input` | Entrée simulée écrite vers le PLC : mesure, contact, fin de course, retour ou défaut. L’autorisation d’écriture doit être cochée. |
| `output` | Sortie lue depuis le programme : commande pompe/vanne, consigne ou état. Le banc ne l’écrit pas. |

BOOL attend `true`/`false`, INT un entier 16 bits, DINT un entier 32 bits et REAL un nombre fini en Float32. Le calcul physique interne reste en double précision. Une entrée ne peut avoir qu’un seul producteur de modèle ; plusieurs équipements peuvent lire une même sortie PLC.

### Distinguer adresse, symbole et transport

| Champ | Contenu |
| --- | --- |
| **Adresse Siemens** (`plc_address`) | Adresse absolue relevée dans le programme, par exemple `%I1.0`, `%IW264` ou `%DB43.DBX1.2` |
| **Symbole PLC** (`plc_symbol`) | Nom réellement déclaré, par exemple un membre de DB |
| **NodeId OPC UA** (`node_id`) | Identifiant réellement exposé par le serveur OPC UA de la CPU |

Les adresses absolues sont documentaires. Elles ne sont pas converties en NodeIds et ne pilotent aucun accès direct à la mémoire Siemens. Pour un DB optimisé sans offset absolu, conserver son symbole et laisser l’adresse vide. Un symbole de démonstration ne prouve pas qu’un projet Siemens l’expose. Ne remplir les NodeIds qu’après découverte de la cible réelle ; namespace 0 est interdit.

Le laboratoire utilise des symboles du contrat public `DB_FAT_Demo`. Les adresses et NodeIds d’une copie native doivent venir de son export et de sa découverte réels selon [DEMO_PLC.md](DEMO_PLC.md). Ne pas transposer un offset d’un autre DB ou d’un DB optimisé.

### Préparer les droits d’écriture

Dans **Variables & mapping**, **Autorisations d’écriture** ouvre une revue de toutes les entrées simulées. Utiliser **Tout autoriser**, **Tout refuser** ou cocher chaque entrée. Avec un filtre, les boutons ne changent que les résultats affichés ; les autres choix sont conservés. **Appliquer la sélection** met à jour le brouillon, puis **Enregistrer** sauvegarde le projet avec ses contrôles de contexte habituels. **Annuler** ou Échap conserve les droits précédents. Les sorties PLC restent en lecture seule. Une entrée refusée bloque la validation et le démarrage du projet, conformément au contrat actuel.

### Déclarer une conversion électrique

Dans **Variables & mapping**, ouvrir une variable numérique puis choisir **Conversion analogique** : **Brut ↔ unité ingénierie**, **4–20 mA** ou **0–10 V**. Renseigner :

1. **Brut minimum** et **Brut maximum**, soit les valeurs natives aux extrémités du signal nominal.
2. **Minimum ingénierie**, **Maximum ingénierie** et **Unité ingénierie**, par exemple 10, 30 et °C.
3. Si le protocole prévoit une injection 0/24 mA, les codes de diagnostic vérifiés pour le profil testé. Laisser vides les codes inconnus.
4. Enregistrer et valider le projet avant de démarrer.

L’unité du tag décrit les valeurs natives échangées, par exemple des comptes. L’unité ingénierie décrit la grandeur présentée au testeur. Le schéma accepte la déclaration suivante dans un tag numérique ; les codes ci-dessous sont un **exemple de profil de test** :

```json
{
  "signal": {
    "kind": "4-20mA",
    "raw_min": 0.0,
    "raw_max": 27648.0,
    "engineering_min": 10.0,
    "engineering_max": 30.0,
    "engineering_unit": "°C",
    "underflow_raw": -32768.0,
    "overflow_raw": 32767.0
  }
}
```

`kind:"linear"` déclare la relation brut/ingénierie sans lui attribuer un courant ou une tension. Les bornes brutes doivent convenir au type et aux limites du tag ; les deux plages déclarées sont croissantes. Le code de diagnostic doit rester représentable dans le type PLC, même lorsqu’il dépasse les limites nominales.

La conversion nominale est :

```text
brut = raw_min + (stimulus - bas_signal) / (haut_signal - bas_signal) × (raw_max - raw_min)
```

`bas_signal`/`haut_signal` valent 4/20 pour mA, 0/10 pour V, 0/100 pour le pourcentage, ou les bornes ingénierie pour une saisie dans cette unité. Avec le profil nominal d’exemple :

| Plage nominale | Courant | Brut | Ingénierie |
| --- | --- | --- | --- |
| 0 % | 4 mA | 0 | 10 °C |
| 25 % | 8 mA | 6 912 | 15 °C |
| 50 % | 12 mA | 13 824 | 20 °C |
| 100 % | 20 mA | 27 648 | 30 °C |

Pour INT/DINT, le résultat est arrondi à l’entier par `round` Python (les demi-entiers vers l’entier pair). Pour REAL, la valeur est représentée en Float32. Le JSON et les commandes utilisent le point décimal et les booléens JSON, même si la prose du guide utilise la virgule.

### Choisir un profil de diagnostic

Le nominal 0 à 27 648 comptes du profil et la plage d’un INT signé (**−32 768 à 32 767**) sont deux limites différentes. L’extrapolation linéaire à 24 mA produirait 34 560 comptes, qui ne tiennent pas dans un INT. Le logiciel refuse un dépassement du type ; il ne rabat pas silencieusement cette valeur à 32 767.

En mode diagnostic, à **exactement 0 mA** ou **exactement 24 mA**, un code `underflow_raw`/`overflow_raw` explicitement déclaré remplace le calcul linéaire. Dans le profil d’exemple, ces codes proposés sont respectivement −32 768 et 32 767. Le journal conserve le stimulus demandé et le brut appliqué. Le code à 24 mA est donc un stimulus de défaut du profil, sans prétendre représenter linéairement 24 mA.

Pour ces codes hors plage, le pupitre affiche **Diagnostic bas/haut** avec le brut du profil. Il ne présente pas une extrapolation en °C, %, mA ou V comme une mesure physique. Le stimulus demandé à 0 ou 24 mA reste visible dans la saisie et l’aperçu du code préparé.

Sans code déclaré, le calcul reste linéaire : 0 mA donne −6 912 comptes et 24 mA donne 34 560, avec refus si le type ne peut pas représenter ce résultat. Les autres stimuli ne sont pas automatiquement remplacés par ces codes d’extrémité.

Les codes de rupture de fil/dépassement dépendent du module, du paramétrage et de l’interface de simulation du PLC. Les valeurs du profil sont à qualifier pour la cible testée. Déclarer un code dans Vanguard FAT Studio ne simule pas le diagnostic matériel complet d’un module Siemens.

### Coller une liste de tags depuis Excel

1. Dans Excel ou un autre tableur, copier les cellules utiles, titres compris. Dans **Variables & mapping**, ouvrir **Coller des tags Excel** et coller le tableau. **Ouvrir un fichier CSV ou TSV** accepte aussi un export texte ; les classeurs `.xlsx` ne sont pas lus directement.
2. Vérifier **La première ligne contient les titres** et le séparateur, puis cliquer **Analyser le tableau**. La tabulation, le point-virgule et la virgule sont acceptés. Choisir le séparateur explicitement si la détection ne correspond pas au fichier.
3. Relire chaque correspondance de colonne. Les titres usuels français ou anglais donnent des suggestions modifiables. Choisir **Ignorer cette colonne** pour les données inutiles. **Nom**, **Sens automate** et **Type** sont nécessaires. Sans colonne de sens ou de type, choisir explicitement **Sens commun** ou **Type commun** pour toutes les lignes ; aucune valeur n’est choisie par défaut.
4. Cliquer **Préparer l’aperçu**, puis relire les lignes, les valeurs initiales, les droits d’écriture et les ajouts/modifications/suppressions. Corriger toute erreur à la ligne indiquée et préparer à nouveau l’aperçu.
5. Cliquer **Appliquer l’import au brouillon**, puis **Enregistrer**. Le collage ne crée pas les liaisons des équipements : utiliser ensuite **Revoir toutes les liaisons aux tags**.

Le sens se lit depuis l’automate : `input` ou `entrée` pour une entrée simulée, `output` ou `sortie` pour une commande lue depuis le PLC. Les types sont `BOOL`, `INT`, `DINT` et `REAL`. Les nombres acceptent le point ou la virgule décimale, sans séparateur de milliers ; les entiers restent entiers. Les booléens acceptent `true`/`false`, `vrai`/`faux`, `oui`/`non` et `1`/`0`.

Sans colonne **Identifiant (fusion)**, les lignes créent de nouvelles variables, même si un nom existe déjà. Pour mettre à jour des tags existants, reprendre leurs identifiants ; les champs dont les colonnes sont absentes sont conservés. Si une colonne d’identifiant est associée, toutes ses cellules doivent être remplies. Un sens ou un type commun s’applique seulement en l’absence de sa colonne associée : il ne corrige pas les cellules vides d’une colonne conservée.

Une nouvelle variable commence à `false` ou `0` si aucune colonne de valeur initiale n’est associée. Son droit d’écriture reste désactivé sauf valeur explicite dans **Écriture autorisée**. Le revoir ensuite dans **Autorisations d’écriture**, en particulier pour les entrées simulées. Une sortie reste en lecture seule. Le tableau ne permet pas de déduire un NodeId ou une conversion analogique depuis une adresse Siemens.

L’import accepte au plus 200 lignes de données, 30 colonnes et 2 Mo de texte UTF-8. Un fichier est aussi limité à 2 Mo ; UTF-8 et UTF-16 avec marqueur sont acceptés. En cas d’encodage illisible, exporter en CSV UTF-8 ou copier les cellules. Les champs CSV entre guillemets peuvent contenir un séparateur ou un retour à la ligne. Une erreur bloque l’application de tout le tableau. **Annuler** abandonne l’import ; si le projet change, le texte reste visible et copiable avant fermeture.

### Importer et exporter

**Exporter** dans la barre projet produit l’enveloppe JSON versionnée du projet. **Importer** accepte cette enveloppe ainsi que les anciens projets JSON compatibles ; les champs inconnus sont refusés. Enregistrer avant de remplacer le projet actif.

Dans Variables, **Exporter CSV** produit le mapping. Pour un export Vanguard, **Importer CSV** ouvre directement un aperçu et propose par défaut **Fusionner par identifiant et conserver les autres variables**. Un autre tableau CSV/TSV ouvre d’abord la correspondance des colonnes décrite ci-dessus. La fusion met à jour les identifiants présents, ajoute les nouveaux et conserve les autres. **Remplacer la liste des variables** reste un choix explicite. Arrêter l’essai avant de préparer cet import.

Relire les ajouts, modifications et suppressions. La suppression d’une variable utilisée, ou le changement de son sens, type, unité ou conversion analogique, bloque l’application tant que ses consommateurs n’ont pas été revus. **Appliquer l’import au brouillon** conserve le projet enregistré jusqu’à **Enregistrer** ; **Annuler** abandonne l’aperçu. Les associations et scénarios ne sont pas réécrits pour rendre le CSV compatible.

Le CSV utilise une virgule séparatrice et `true`/`false` pour `writable`. Les dix colonnes historiques restent acceptées ; les exports actuels ajoutent adresses, symboles, conversion et marqueur d’encodage. Le détail est dans [AI_CONTROL.md](AI_CONTROL.md#mapping-et-format-projet).

## 8. Injecter un défaut

Pendant un essai, sélectionner un équipement et utiliser ses commandes de défaut disponibles. Les défauts compatibles sont affichés pour cet équipement :

| Défaut | Paramètre et observation |
| --- | --- |
| Défaut moteur | Le moteur simule un défaut ; contrôler le retour et la réaction du programme |
| Vanne bloquée | Donner une position de 0 à 100 %, ou conserver la position au moment de l’injection |
| Capteur figé | La mesure publiée reste figée pendant que le procédé peut évoluer |
| Signal hors plage | Donner une valeur hors limites de procédé mais représentable dans le type PLC |

Effacer le défaut pour retrouver le comportement normal du modèle. Le PLC peut garder un défaut mémorisé et demander son propre réarmement. Libérer un forçage et effacer un défaut sont deux commandes distinctes.

Dans le scénario analogique du laboratoire, le défaut LT brut à 30 000 comptes dépasse le nominal 27 648 tout en restant représentable en INT. Il reste distinct des stimuli 0/24 mA du mode diagnostic et de leurs codes de profil.

## 9. Comprendre les états et les reprises

| Commande/état | Effet sur le banc |
| --- | --- |
| **Démarrer** | Valide puis crée un nouvel essai avec modèle et résultats initialisés |
| **Pause** | Suspend modèle et échanges ; la CPU externe peut continuer sa séquence |
| **Reprendre** | Reconnecte explicitement et revalide identité/mapping pour le même essai non terminé |
| **Arrêter** | Termine l’essai et déverrouille la configuration |
| **Réinitialiser** | Restaure le modèle local, ses valeurs et forçages ; conserve l’historique |
| Scénario terminé | Le banc est en pause, ses échanges sont coupés ; réinitialiser avant rejeu |
| Erreur | Écritures arrêtées, qualité mauvaise et cause visible ; aucune reconnexion automatique |

En cas d’erreur, relever le message et exporter les preuves de l’essai si le stockage reste accessible. Corriger la cause, vérifier l’état réel du PLC et décider de ses conditions de reprise avant de lancer un nouvel essai.

Une écriture OPC UA partielle ne peut pas être annulée par le modèle. Des valeurs déjà écrites peuvent rester dans le DB. Ni arrêt, ni pause, ni reset du banc n’envoient RUN/STOP à une CPU et ne réinitialisent ses mémoires.

Fermer un onglet laisse le serveur actif. Fermer le serveur arrête le banc ; un essai resté ouvert après une interruption inattendue est classé interrompu au redémarrage. Le logiciel ne reprend pas ses écritures automatiquement.

## 10. Lire et conserver les preuves

Dans **Tendances & rapport**, sélectionner jusqu’à huit variables. Les courbes montrent une fenêtre récente, avec BOOL représenté par `0/1`. Les échantillons de chaque cycle restent dans SQLite indépendamment de cette fenêtre et du rafraîchissement de l’écran (500 ms).

Ajouter un marqueur pour dater une observation sur le temps simulé. Saisir ensuite la conclusion humaine et cliquer **Enregistrer la conclusion** avant de télécharger le rapport final. Les champs modifiés mais non enregistrés restent un brouillon.

| Export | Contenu et usage |
| --- | --- |
| **Données CSV** | Mesures horodatées, variables, valeurs et qualités pour analyse |
| **Rapport FAT** | HTML imprimable : contexte, projet/cible, scénario, journal, contrôles et résultat utilisateur |
| **Preuves JSON** | Instantané structuré : configuration et données enregistrées pour revue technique |

L’export capture un instantané fini ; un essai encore actif continue après cette capture. Pour un dossier de clôture, arrêter ou terminer l’essai puis réexporter. Dans **Historique**, chaque essai conservé propose ses propres CSV, rapport et JSON, même après un reset ou un redémarrage.

Pour conserver **le projet entier avec ses essais**, ouvrir **Ouvrir → Exporter l’archive FAT** et enregistrer le fichier `.fat.zip` dans votre dossier de projet. Cette archive contient configuration, animations, scénarios, mapping et exports des seuls essais de ce projet. **Restaurer une archive FAT** vérifie le conteneur puis ouvre un nouveau dossier local, au repos ; l’ancien espace reste disponible dans **Dossiers FAT locaux**. Aucune cible ni clé du poste n’est importée. Le détail est dans [PROJECT_ARCHIVES.md](PROJECT_ARCHIVES.md).

Une sauvegarde brute du dossier de données exige l’arrêt du serveur pour copier SQLite proprement. Elle reste distincte de l’archive sélectionnée, qui exclut les autres projets et la politique du poste.

## 11. Raccorder une CPU virtuelle par OPC UA

Suivre [PLCSIM_SETUP.md](PLCSIM_SETUP.md) pour la préparation native et [ACCEPTANCE.md](ACCEPTANCE.md) pour la qualification. Le programme PLC doit être préparé dans une copie de test autorisée, avec ses interfaces de simulation et son serveur OPC UA.

1. Relever les versions Siemens, le firmware, la CPU virtuelle et son adaptateur isolé.
2. Découvrir endpoint, ApplicationUri, namespace, certificat, NodeIds, types et droits réellement exposés.
3. Faire autoriser cette cible exacte par le CLI humain `authorize-target`, dans le même dossier de données que le serveur FAT.
4. Dans **Connexion → Mes cibles sur ce poste**, choisir la cible déjà autorisée selon le parcours ci-dessous. La saisie manuelle reste disponible avec le mode **PLCSIM Advanced · OPC UA**. Les identifiants utilisateur sont référencés par noms de variables d’environnement ; les valeurs secrètes ne vont pas dans le projet.
5. Dans Variables, associer les NodeIds découverts, par saisie ou avec l’explorateur ci-dessous. Valider le projet. La validation en ligne des nœuds, types et droits intervient au démarrage avant les écritures.
6. Démarrer ; recopier exactement le nom de cible et l’endpoint demandés. Vérifier une commande lue et une mesure écrite avant la campagne.

Pour préparer plusieurs essais sur la même cible, cocher **Autoriser plusieurs essais dans cet onglet** dans la confirmation. **Tout sélectionner** couvre l’essai libre et les scénarios du projet ; décocher ceux à exclure, ou choisir **Garder cet essai uniquement**. **Refuser** annule le démarrage et retire l’accord précédent. Chaque essai se démarre manuellement ; les observations et verdicts restent séparés.

Le bandeau **Cible autorisée dans cet onglet** affiche la cible et permet de **Révoquer l’accord** pour les prochains démarrages. Révoquer ne coupe pas un essai déjà en cours ; utiliser **Arrêter l’essai** pour cela. L’accord reste en mémoire dans cet onglet : recharger la page, modifier ou remplacer le projet, rencontrer une erreur ou perdre la connexion le retire. Un scénario exclu demande une nouvelle confirmation. Le serveur reçoit toujours la confirmation exacte et vérifie à nouveau politique locale, identité, certificat et mapping à chaque connexion. Cet accord ne crée aucune autorisation de poste et ne se transmet ni aux archives ni au client IA.

Un projet importé ne peut pas autoriser une cible sur le poste. Le mode OPC UA conserve la vitesse à 1× ; aucune garantie de synchronisation avec le scan PLC n’est déduite du pas choisi.

Le serveur OPC UA générique `scripts/opcua-fixture.py` permet d’essayer le protocole sans Siemens. Son comportement et les démonstrations Python ne constituent pas une qualification PLCSIM ou une validation fonctionnelle du programme Siemens.

### Choisir une cible déjà autorisée

1. Avec l’essai arrêté, ouvrir **Connexion → Mes cibles sur ce poste**, puis **Actualiser les cibles** si la politique du poste vient de changer.
2. Choisir une **Cible habituelle**. Relire l’adresse, l’identité serveur, la sécurité proposée et l’empreinte de certificat lorsqu’elle est déclarée.
3. Cliquer **Préparer cette cible**, relire l’aperçu, puis **Utiliser cette cible dans le brouillon**. **Annuler le choix** abandonne cette préparation.
4. Si nécessaire, compléter les références dans **Certificats et authentification**. Cliquer **Vérifier la connexion en lecture seule**, lire le résultat, puis enregistrer le projet après revue du mapping.

Cette liste vient uniquement de la politique locale du poste. Si elle est vide, autoriser d’abord la cible exacte avec le CLI humain `authorize-target` ; importer un projet ne remplit pas cette autorisation. Une entrée incomplète ou ambiguë indique pourquoi elle ne peut pas être utilisée.

Le choix de cible prépare le mode OPC UA à vitesse réelle. Lors d’un changement d’identité, il efface le namespace et les références d’authentification de l’ancienne cible ; les références déjà exactes pour la même cible sont conservées. Les NodeIds des tags restent présents et doivent être revus pour la cible choisie. La liste ne transmet ni secret ni chemin de clé.

**Vérifier la connexion en lecture seule** contacte la cible affichée et contrôle son identité et son certificat avant l’authentification. Il ne lit pas de valeurs de procédé, n’écrit aucune valeur et ne démarre pas d’essai. Un résultat favorable ne valide pas les NodeIds, types ou droits du mapping : les vérifier au démarrage selon le parcours précédent. Modifier le projet retire le résultat affiché ; un changement pendant la préparation impose de relire la cible.

### Choisir un NodeId sur le serveur

L’explorateur s’utilise après avoir configuré et autorisé la cible exacte sur le poste, avec l’essai arrêté. Dans la revue globale d’un tag, cliquer **Choisir sur le serveur OPC UA**, relire la cible affichée, puis **Parcourir en lecture seule**. Dans les détails d’une variable, le bouton **Choisir le NodeId sur le serveur** ouvre le même explorateur. La politique locale, l’identité attendue et le certificat sont contrôlés avant l’authentification. Un mapping incomplet peut être exploré pour le compléter.

Ouvrir les dossiers jusqu’à la variable voulue. Le filtre ne porte que sur la page affichée ; utiliser **Page suivante** pour la suite. **Utiliser…** n’est disponible que pour un type scalaire compatible et les droits requis : lecture pour une commande PLC, écriture pour une entrée simulée. Le namespace système 0, les tableaux, structures, références externes et types non pris en charge ne peuvent pas être associés. Les pages contiennent au plus 100 nœuds, avec une limite de 2 000 nœuds par dossier.

L’exploration lit les noms, types et droits, sans écrire de valeur ni démarrer d’essai. Le choix remplit le NodeId dans la revue en cours ; appliquer cette revue puis enregistrer le projet. Une erreur ou un changement de contexte interrompt le parcours ; la reprise est explicite. L’explorateur ne configure pas le serveur OPC UA de TIA et ne qualifie pas une cible Siemens.

## 12. Travailler avec votre IA

Vanguard FAT Studio ne demande aucune clé API de modèle et n’intègre pas de conversation IA. Votre assistant peut lire le dossier, préparer un JSON et piloter le CLI/API de votre serveur local. Votre client IA conserve ses propres conditions d’accès ; les données transmises à un modèle hébergé peuvent quitter le poste.

Utiliser le [prompt prêt à copier et le tutoriel isolé](AI_QUICKSTART.md). Les fichiers [AGENTS.md](../AGENTS.md), [CODEX.md](../CODEX.md) et [CLAUDE.md](../CLAUDE.md) donnent au client le contrat et les bornes de travail. Pour l’ingénierie TIA optionnelle, suivre [TIA_MCP.md](TIA_MCP.md) : serveur Czarnak 4.3.0 épinglé, IA en lecture seule, imports/compilations via CLI humain avec les confirmations existantes.

## 13. Dépanner les cas courants

| Observation | Action |
| --- | --- |
| Page inaccessible | Vérifier l’état dans le lanceur, son URL/port et le résultat de `doctor`. Le bouton **Ouvrir FAT Studio** retrouve l’interface. |
| Anciennes valeurs, service indisponible | Vérifier le serveur ; les commandes sont bloquées tant que la connexion locale n’est pas revenue. |
| Projet changé dans un autre onglet | Conserver le brouillon, puis recharger volontairement le projet actif et utiliser **Comparer les versions**. Un autre onglet et une IA partagent le même serveur. |
| Démarrage refusé | Cliquer les points de **Préparer l’essai**, puis vérifier les diagnostics de Connexion : associations, types, bornes, droits et politique locale. |
| Transfert refusé dans le constructeur | Choisir deux cuves distinctes et inclure tous les organes du circuit physique déjà partagé. |
| Débit nul ou inférieur à la capacité attendue | Ouvrir **Expliquer les débits** et vérifier le cycle affiché, la commande, les organes limitants et la source. La fenêtre décrit le modèle, sans déduire les interverrouillages du PLC. |
| Variable CSV refusée | Lire la ligne d’aperçu ; revoir les consommateurs avant de supprimer ou changer le contrat d’un tag utilisé. |
| Tableau collé incomplet ou mal découpé | Vérifier le séparateur et les correspondances de colonnes. Renseigner le sens et le type, par colonne ou par choix commun explicite. Pour un fichier illisible, exporter en UTF-8 ou copier les cellules. |
| Brouillon retrouvé mais reprise indisponible | Choisir **Comparer les versions** si une version de départ est disponible. Sinon, télécharger le brouillon pour préserver son contenu ; les notes FAT restent liées à leur essai d’origine. |
| Modèles personnels absents | Vérifier le navigateur et l’adresse du banc. Importer l’export JSON de la bibliothèque pour la retrouver ailleurs ; une archive FAT ne contient pas ce stockage du navigateur. |
| Poussoir inactif | Vérifier qu’un essai tourne, que le tag est `input`, BOOL et autorisé en écriture. |
| Sortie impossible à forcer | Vérifier le sens : une sortie PLC est lue depuis le contrôleur. Corriger une déclaration erronée uniquement après revue du mapping. |
| Unité mA/V absente | Vérifier la conversion `signal` de la variable. Le logiciel ne la déduit pas d’une adresse analogique. |
| STEP suivant indisponible | Attendre l’application du STEP actif puis enregistrer l’observation du testeur. |
| **Conforme** refusé sur un STEP | Lire la valeur réelle, l’attente et la qualité des contrôles mesurables. Consigner l’écart ou corriger l’état avant un nouveau constat. |
| Scénario terminé impossible à reprendre | Arrêter/réinitialiser, vérifier les conditions initiales du PLC externe, puis ouvrir un nouvel essai. |
| OPC UA refusé | Comparer cible, politique du poste, identité/certificat, namespace et NodeIds réellement découverts. |
| Erreur SQLite/fichier | Vérifier espace disque et droits, conserver les fichiers ; le banc interrompt l’essai pour protéger sa traçabilité. |
