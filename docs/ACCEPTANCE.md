# Protocole de réception et qualification sur poste

Ce protocole couvre le banc FAT local et son option d'ingénierie. Il est à exécuter sur une copie du programme et une CPU virtuelle isolée. Il ne constitue pas une validation de sécurité de machine, une qualification GMP automatique ou une autorisation de mise en service.

**État initial de cette fiche : non exécutée sur Siemens.** Les essais automatisés locaux et le benchmark sont des preuves distinctes. Laisser un résultat « non exécuté » tant que l'observation demandée n'a pas été réalisée sur le poste indiqué.

## Fiche d'essai

| Champ | À renseigner |
| --- | --- |
| Affaire / installation représentée | |
| Automaticien / témoin | |
| Date et fuseau horaire | |
| Commit FAT Studio et empreinte de l'archive livrée | |
| Windows / build / architecture | |
| Python et versions verrouillées | |
| TIA Portal / Update / Openness | |
| PLCSIM Advanced / Update | |
| CPU virtuelle, référence et firmware | |
| Nom d'instance et chemin de copie `.ap21` | |
| IP / endpoint / namespace / ApplicationUri | |
| Politique et empreintes OPC UA | |
| Version `tia-portal-mcp`, client IA et politique de données | |
| Identifiant de projet FAT / scénario / rapport | |

Conserver le JSON du projet, les rapports d'essai, les diagnostics TIA, les versions et les observations. Les mots de passe et clés privées ne font pas partie du dossier de preuve.

## A. Installation et démonstration autonome

**A1 — Installation propre.** Sur le poste retenu, installer Python 3.12 x64, extraire/cloner la livraison et lancer `Start-FAT.cmd`. Exécuter `python -m fat_studio doctor --json` dans le venv et conserver le résultat. Attendu : interface embarquée disponible, dépendances identifiées, aucune connexion Siemens automatique.

**A2 — Projet et éditeur.** Charger TK-101, déplacer un symbole, modifier un nom et ajouter une connexion. Enregistrer, fermer le navigateur et le serveur, puis relancer. Attendu : géométrie/propriétés conservées, sept types disponibles. Importer un JSON volontairement invalide : une erreur lisible apparaît et le projet valide reste disponible.

**A3 — Scénarios autonomes.** Jouer successivement `reference`, `motor-trip` et `sensor-freeze`, avec réinitialisation entre essais. Attendu : assertions des scénarios de démo réussies ; mesure figée et volume physique divergent pendant le défaut prévu ; réinitialisation efface les forçages/défauts. Exporter les traces.

**A4 — Persistance et rapport.** Ajouter un marqueur et un verdict avec commentaire. Télécharger CSV/HTML/JSON, fermer puis relancer le service. Attendu : essai archivé consultable, configuration d'origine conservée dans la preuve, résultat utilisateur distinct des assertions.

**A5 — Installation hors ligne, si retenue.** Préparer le kit sur Windows avec `prepare-offline.ps1`, transférer le dossier complet vers un poste sans accès Internet et exécuter le lanceur. Attendu : vérification des empreintes, installation depuis wheelhouse, ouverture de la démo sans index externe. Modifier une copie d'une wheel : la vérification doit refuser le kit avant installation.

## B. Préparer la communication Siemens

Suivre [PLCSIM_SETUP.md](PLCSIM_SETUP.md), puis noter les observations :

1. La copie de développement est indépendante et sauvegardée ; son chemin exact est connu.
2. L'instance PLCSIM et son CPU/firmware correspondent à la fiche.
3. Le mode de communication utilise TCP/IP avec liaison `<Local>` ; l'opérateur a vérifié les routes/bridges/VPN et l'absence de chemin vers un réseau de production.
4. Le projet compile dans TIA ; le DB et son raccordement au programme sont relus.
5. Les variables ont les droits OPC UA nécessaires et les NodeIds proviennent d'une observation réelle.
6. La politique locale enregistre cette cible précise et ses champs de certificats/authentification ; aucune valeur de secret n'est inscrite dans le projet.
7. L'échelle de temps est 1× côté banc et PLCSIM pour cette qualification initiale.

Le contrôle du serveur OPC UA ne suffit pas à connaître l'état RUN/STOP du PLC. Le relever dans l'outil Siemens pour chaque séquence concernée.

## C. Échanges et contrôles de refus

### C1 — Identité et types avant écriture

Dans une copie du projet FAT, essayer successivement une cible non autorisée, une confirmation différente, une ApplicationUri différente, un NodeId absent, un type erroné et un input sans droit d'écriture. Avec chiffrement, essayer aussi une empreinte serveur erronée.

**Attendu :** démarrage refusé avant écriture, diagnostic précis ; les valeurs de surveillance du DB restent inchangées. Conserver les messages et observations Siemens. Ne pas convertir un contrôle refusé en contournant sa validation : corriger la configuration réelle.

### C2 — Entrées simulées

Démarrer un essai libre sur la cible approuvée. Forcer un tag BOOL, puis une mesure REAL dans les limites prévues. Observer leur valeur dans la table TIA et dans le bloc consommateur du programme.

| Type | Tag choisi | Valeur demandée | Valeur vue dans DB | Valeur vue dans logique | Résultat / preuve |
| --- | --- | --- | --- | --- | --- |
| BOOL | | | | | |
| REAL | | | | | |
| INT si utilisé | | | | | |
| DINT si utilisé | | | | | |

Le DB de démo contient BOOL/REAL. Pour INT/DINT, utiliser des variables de preuve distinctes dans le DB convenu, les exposer et les mapper explicitement. Tester les bornes utiles au procédé ; une valeur dépassant le type de stockage doit être refusée par le banc.

**Attendu :** valeur correcte au consommateur, indication visible de force, retour à la mesure du modèle après libération. Vérifier qu'une affectation cyclique du programme n'écrase pas le tag simulé.

### C3 — Sorties PLC et effet sur le procédé

Faire produire une commande pompe et une commande de vanne par le programme testé, selon sa procédure normale de test. Observer les valeurs lues dans FAT Studio et l'évolution cohérente du modèle. Vérifier l'unité/échelle de la vanne modulante.

**Attendu :** les commandes proviennent du PLC, l'application ne les force pas ; le niveau et les retours simulés évoluent suivant les paramètres enregistrés. Consigner le retard d'acquisition observé et la séquence de raccordement au scan PLC.

## D. FAT fonctionnelle et comportement en erreur

**D1 — Scénario client.** Adapter et faire relire un scénario au programme réel : conditions initiales, demande opérateur, permissifs, seuils, temporisations et assertions. Réinitialiser les états PLC et le modèle selon la procédure convenue. Exécuter deux fois et comparer les traces ; une différence de temporisation doit être expliquée, pas assimilée à un rejeu déterministe du scan.

**D2 — Défauts.** Injecter au moins un défaut moteur, un capteur figé, un signal hors plage et une vanne bloquée lorsque ces objets font partie du projet. Attendu : défaut visible, évolution physique cohérente, alarme/interverrouillage du programme conforme au scénario, trace de l'injection et de sa suppression.

**D3 — Perte de communication.** Pendant un essai sur instance isolée, provoquer la rupture définie dans le protocole du poste. Attendu : qualité d'échange en erreur, arrêt de toute nouvelle écriture du banc, aucune reconnexion automatique. Les dernières valeurs du DB peuvent persister ; vérifier le comportement prévu du programme face à cette situation. Rétablir la liaison, constater l'absence de reprise spontanée, puis redémarrer volontairement après remise en conditions initiales.

**D4 — Pause et arrêt.** Mettre le banc en pause puis reprendre, arrêter puis réinitialiser. Attendu : modèle/échanges suspendus, aucune commande RUN/STOP envoyée à la CPU ; l'opérateur constate séparément si la séquence PLC a continué. Vérifier que l'édition reste verrouillée tant que l'essai est actif ou en pause.

**D5 — Charge maximale prévue.** Utiliser un projet représentatif allant jusqu'à 50 équipements/200 tags. Mesurer le pas réel, la fraîcheur des valeurs, les dépassements, le rendu UI et la charge du poste avec TIA/PLCSIM en fonctionnement. Les résultats du benchmark Linux ne remplacent pas cette mesure.

Le script de mesure locale peut être rejoué sur le disque du poste :

```powershell
.\.venv\Scripts\python.exe scripts\benchmark.py --cycles 1000 --warmup 50 `
  --work-dir "D:\FAT\Mesures" --output "D:\FAT\Preuves\benchmark-poste.json"
```

Il mesure moteur et SQLite ; mesurer séparément la liaison Siemens et l'interface. Fixer les objectifs d'acceptation avant d'interpréter les résultats.

## E. Option d'ingénierie MCP / IA

Ces essais s'exécutent seulement si le volet IA est retenu et les règles de circulation des sources approuvées. Utiliser la procédure de [TIA_MCP.md](TIA_MCP.md), Czarnak v4.3.0 épinglé et une copie standalone `.ap21` ouverte/sauvegardée dans TIA V21.

**E1 — Lecture seule.** Exécuter le `doctor` upstream, déclarer la copie puis connecter le client choisi avec `--access-mode read-only`. Lister l'arbre, lire un bloc SCL représentatif, un DB et les tables de tags nécessaires. Pour LAD/FBD, tester un bloc réellement utilisé et relever la représentation accessible. Attendu : cible exacte, contenu fidèle, outils d'écriture/compilation absents du client IA en lecture seule.

**E2 — Proposition refusée.** Exporter un bloc vers `before.*`/`after.*`, préparer une modification locale simple, afficher le diff et refuser l'application lorsqu'elle est proposée. Attendu : le bloc dans TIA reste identique et le refus est journalisé. Ne pas modifier le fichier `before.*`.

**E3 — Modification acceptée.** Activer l'écriture depuis le terminal humain et appliquer une proposition relue. Attendu : prévisualisation, confirmation avec la cible/hash, archive `.zap21` vérifiée avant import, contrôle de non-modification concurrente, diagnostics de compilation, sauvegarde soumise à sa confirmation. Examiner le bloc résultant dans TIA.

**E4 — Garde de concurrence.** Après export, modifier volontairement le bloc de la copie dans TIA, puis tenter l'application de l'ancien export. Attendu : refus d'import sur source périmée. Produire un nouvel export avant tout autre changement.

**E5 — Compilation en erreur.** Dans une copie de test dédiée, proposer une modification dont le comportement de compilation attendu est connu et contrôlé. Attendu : diagnostics conservés et aucune déclaration trompeuse de succès ; aucune sauvegarde automatique après erreur. Si l'import a réussi, le projet peut rester modifié en mémoire : relever l'état exact et restaurer/abandonner selon la procédure TIA.

**E6 — Restauration et limites.** Restaurer réellement une archive produite dans un autre dossier et comparer le bloc concerné. Vérifier les journaux et la liste d'outils : aucun téléchargement, commande CPU, écriture matérielle ou provisioning réseau dans le parcours fourni. Désactiver ensuite le mode écriture. Le SHA d'une archive non vide n'est pas une preuve de restaurabilité sans cet essai.

## Enregistrement de réception

Pour chaque essai, inscrire **réussi / échoué / non exécuté**, la preuve associée, les écarts et l'action décidée. Un non-exécuté Siemens ne peut pas être remplacé par un succès du double de protocole.

| Groupe | Résultat | Preuves / identifiants | Écart et action | Responsable/date |
| --- | --- | --- | --- | --- |
| A1–A5 Installation/démo | Non exécuté sur poste cible | | | |
| B Préconditions Siemens | Non exécuté | | | |
| C1 Identité/mapping/refus | Non exécuté | | | |
| C2 Entrées simulées | Non exécuté | | | |
| C3 Commandes PLC | Non exécuté | | | |
| D1–D2 Séquences/défauts | Non exécuté | | | |
| D3–D4 Communication/pause | Non exécuté | | | |
| D5 Charge cible | Non exécuté | | | |
| E1–E6 Ingénierie optionnelle | Non exécuté / hors périmètre si non retenu | | | |

La réception de la livraison logicielle et la réception de la FAT du programme client sont deux décisions séparées. Faire signer la fiche correspondant au périmètre effectivement exécuté, avec les limitations restantes.
