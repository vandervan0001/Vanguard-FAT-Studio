# Utiliser Vanguard FAT Studio

Vanguard FAT Studio est un banc d’essai local. Le programme PLC fournit ses commandes ; le modèle de procédé calcule les mesures, retours et défauts simulés, puis les renvoie au PLC par OPC UA. Le mode **Démonstration** utilise un contrôleur Python distinct pour essayer le banc sans Siemens.

Ce guide décrit le parcours dans l’interface. Pour piloter le même banc avec votre propre assistant, lire [le démarrage IA](AI_QUICKSTART.md). Le [contrat de pilotage](AI_CONTROL.md) précise le CLI et l’API locale. Les limites de la démo PLC sont précisées dans [DEMO_PLC.md](DEMO_PLC.md). Les projets et scénarios utilisent le [format JSON versionné](FORMAT.md).

## 1. Installer et ouvrir le banc

Sous Windows, extraire toute la distribution **portable**, puis double-cliquer sur `Start-FAT.cmd`. Python et les dépendances sont inclus. Depuis une copie **source**, installer Python 3.12 x64 ; son lanceur crée `.venv` et installe les dépendances verrouillées. Le navigateur ouvre [http://127.0.0.1:8765](http://127.0.0.1:8765). Garder la fenêtre du serveur ouverte ; `Ctrl+C` dans cette fenêtre arrête le service.

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
| Barre du projet | Nom, nombre d’équipements/variables, état enregistré, nouveau/ouvrir/importer/exporter/enregistrer |
| **P&ID** | Dessin, pupitre d’entrées, observation des sorties, sélection et suivi de la FAT |
| **Variables & mapping** | Types, sens, valeurs, qualités, associations et identifiants PLC/OPC UA |
| **Scénarios** | Préparation des FAT pas à pas et des séquences automatiques |
| **Tendances & rapport** | Courbes, journal, marqueurs, observations, conclusion et exports |
| **Connexion** | Source des commandes, version TIA, pas de calcul, cible OPC UA et diagnostics |
| Pied de page | Contrôleur actif, cible, pas, vitesse et compteur d’écritures |

Le nom du mode doit correspondre à l’essai prévu. En **DÉMONSTRATION**, le pied de page indique un contrôleur de démonstration et aucun automate raccordé. Choisir V20/V21 dans Connexion ne convertit aucun projet Siemens.

Pendant un essai en cours, la structure est verrouillée. **Pause** suspend les échanges et rend le constructeur accessible. Sans modification enregistrée, **Reprendre** continue le même essai. **Appliquer en pause** enregistre les modifications, clôture l’ancien essai sans verdict humain et conserve ses preuves ; le projet revient au repos. Un nouveau **Démarrer** ouvre ensuite un nouvel essai. Une pause ne met pas une CPU externe en STOP.

## 3. Réaliser un premier essai sans Siemens

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
2. Dans **P&ID**, sélectionner **Construire** et déposer les équipements depuis la palette.
3. Déplacer les symboles, les relier par les points de connexion et utiliser le zoom/panoramique pour organiser la vue. Sélectionner un équipement pour afficher ses propriétés.
4. Renseigner ses paramètres physiques et associer ses ports à des variables compatibles. **Créer les tags manquants**, lorsqu’il est proposé dans les propriétés, prépare les variables nécessaires ; vérifier ensuite leur type, leurs limites et leurs droits.
5. Pour les pompes/vannes, définir explicitement cuve associée, sens et groupe de débit. Pour un transfert, renseigner aussi la cuve source ; ne pas attendre qu’un trait du dessin crée ce bilan.
6. Enregistrer avec le bouton ou `Ctrl+S` (`Cmd+S` sur macOS), puis valider dans **Connexion**.

La bibliothèque comprend onze types de modèles : cuve, pompe, pompe à variateur, vanne TOR, vanne modulante, vanne trois voies, échangeur, capteur analogique, capteur binaire, bouton/contact et indicateur PLC. Elle propose aussi 41 familles documentaires. Les paramètres et ports disponibles dépendent du type. Le catalogue actif est aussi accessible par l’API pour un assistant. Les [modèles trois voies et thermique](PID_SIMULATION.md) déclarent leurs sources, unités et limites ; ils ne sont pas déduits des traits ou des symboles importés.

Les traits sont des connexions visuelles. Les groupes de débit explicitement déclarés fixent le calcul : minimum des capacités des équipements en série, somme des branches indépendantes. Lire [MODEL.md](MODEL.md) pour le bilan de cuve et les limites du modèle. Le P&ID ne calcule pas un réseau hydraulique général.

Un brouillon incomplet peut être enregistré ; les erreurs sémantiques restent visibles et empêchent son démarrage. La limite du format est de 50 équipements et 200 variables par projet.

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

### Importer et exporter

**Exporter** dans la barre projet produit l’enveloppe JSON versionnée du projet. **Importer** accepte cette enveloppe ainsi que les anciens projets JSON compatibles ; les champs inconnus sont refusés. Enregistrer avant de remplacer le projet actif.

**Échanges P&ID** ouvre un parcours distinct pour partir d'un PDF, d'un scan, d'un fichier CAO ou d'un graphe. Inspecter le document, choisir les équipements et les connexions, confirmer leurs types, puis préparer un nouveau brouillon. **Appliquer au brouillon** l'affiche dans l'éditeur ; **Enregistrer** le conserve comme nouveau projet. Les paramètres physiques et le mapping PLC restent à renseigner. Le document source interprété reste consultable après rechargement, avec ses avertissements et les objets exclus.

Dans **Exporter le P&ID**, le schéma enregistré s'exporte en SVG, PDF, PNG, DXF, DWG R2000 expérimental, JSON P&ID/graphe, GraphML, CSV ZIP ou draw.io. Les formats sont gratuits et traités localement ; DWG nécessite l'installation séparée de LibreDWG sur le poste. Le catalogue attribué à Scott Duncan fournit des liens publics pour trouver des plans et données de procédé. Le [guide des échanges P&ID](PID_EXCHANGE.md) détaille le parcours, les limites OCR/CAO, les crédits et l'installation DWG.

Dans Variables, **Exporter CSV** produit le mapping ; **Importer CSV** remplace l’ensemble de sa liste de variables. Vérifier les associations et scénarios après remplacement. Le CSV utilise une virgule séparatrice et `true`/`false` pour `writable`. Les dix colonnes historiques restent acceptées ; les exports actuels ajoutent adresses, symboles, conversion et marqueur d’encodage. Le détail est dans [AI_CONTROL.md](AI_CONTROL.md#mapping-et-format-projet).

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
4. Dans **Connexion**, choisir **PLCSIM Advanced · OPC UA** puis remplir les mêmes informations. Les identifiants utilisateur sont référencés par noms de variables d’environnement ; les valeurs secrètes ne vont pas dans le projet.
5. Dans Variables, associer les NodeIds découverts. Valider le projet. La validation en ligne des nœuds, types et droits intervient au démarrage avant les écritures.
6. Démarrer ; recopier exactement le nom de cible et l’endpoint demandés. Vérifier une commande lue et une mesure écrite avant la campagne.

Pour préparer plusieurs essais sur la même cible, cocher **Autoriser plusieurs essais dans cet onglet** dans la confirmation. **Tout sélectionner** couvre l’essai libre et les scénarios du projet ; décocher ceux à exclure, ou choisir **Garder cet essai uniquement**. **Refuser** annule le démarrage et retire l’accord précédent. Chaque essai se démarre manuellement ; les observations et verdicts restent séparés.

Le bandeau **Cible autorisée dans cet onglet** affiche la cible et permet de **Révoquer l’accord** pour les prochains démarrages. Révoquer ne coupe pas un essai déjà en cours ; utiliser **Arrêter l’essai** pour cela. L’accord reste en mémoire dans cet onglet : recharger la page, modifier ou remplacer le projet, rencontrer une erreur ou perdre la connexion le retire. Un scénario exclu demande une nouvelle confirmation. Le serveur reçoit toujours la confirmation exacte et vérifie à nouveau politique locale, identité, certificat et mapping à chaque connexion. Cet accord ne crée aucune autorisation de poste et ne se transmet ni aux archives ni au client IA.

Un projet importé ne peut pas autoriser une cible sur le poste. Le mode OPC UA conserve la vitesse à 1× ; aucune garantie de synchronisation avec le scan PLC n’est déduite du pas choisi.

Le serveur OPC UA générique `scripts/opcua-fixture.py` permet d’essayer le protocole sans Siemens. Son comportement et les démonstrations Python ne constituent pas une qualification PLCSIM ou une validation fonctionnelle du programme Siemens.

## 12. Travailler avec votre IA

Vanguard FAT Studio ne demande aucune clé API de modèle et n’intègre pas de conversation IA. Votre assistant peut lire le dossier, préparer un JSON et piloter le CLI/API de votre serveur local. Votre client IA conserve ses propres conditions d’accès ; les données transmises à un modèle hébergé peuvent quitter le poste.

Utiliser le [prompt prêt à copier et le tutoriel isolé](AI_QUICKSTART.md). Les fichiers [AGENTS.md](../AGENTS.md), [CODEX.md](../CODEX.md) et [CLAUDE.md](../CLAUDE.md) donnent au client le contrat et les bornes de travail. Pour l’ingénierie TIA optionnelle, suivre [TIA_MCP.md](TIA_MCP.md) : serveur Czarnak 4.3.0 épinglé, IA en lecture seule, imports/compilations via CLI humain avec les confirmations existantes.

## 13. Dépanner les cas courants

| Observation | Action |
| --- | --- |
| Page inaccessible | Vérifier la fenêtre serveur, son URL/port et le résultat de `doctor`. Ne pas lancer un second serveur sur le même port. |
| Anciennes valeurs, service indisponible | Vérifier le serveur ; les commandes sont bloquées tant que la connexion locale n’est pas revenue. |
| Projet changé dans un autre onglet | Télécharger le brouillon proposé, puis recharger volontairement le projet actif. Un autre onglet et une IA partagent le même serveur. |
| Démarrage refusé | Lire les diagnostics dans Connexion ; vérifier associations, types, bornes, droits et politique locale. |
| Poussoir inactif | Vérifier qu’un essai tourne, que le tag est `input`, BOOL et autorisé en écriture. |
| Sortie impossible à forcer | Vérifier le sens : une sortie PLC est lue depuis le contrôleur. Corriger une déclaration erronée uniquement après revue du mapping. |
| Unité mA/V absente | Vérifier la conversion `signal` de la variable. Le logiciel ne la déduit pas d’une adresse analogique. |
| STEP suivant indisponible | Attendre l’application du STEP actif puis enregistrer l’observation du testeur. |
| **Conforme** refusé sur un STEP | Lire la valeur réelle, l’attente et la qualité des contrôles mesurables. Consigner l’écart ou corriger l’état avant un nouveau constat. |
| Scénario terminé impossible à reprendre | Arrêter/réinitialiser, vérifier les conditions initiales du PLC externe, puis ouvrir un nouvel essai. |
| OPC UA refusé | Comparer cible, politique du poste, identité/certificat, namespace et NodeIds réellement découverts. |
| Erreur SQLite/fichier | Vérifier espace disque et droits, conserver les fichiers ; le banc interrompt l’essai pour protéger sa traçabilité. |
