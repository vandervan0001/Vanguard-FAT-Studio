# Reprise de l'URS — décisions de réalisation 0.1.0

Date : 2 novembre 2026. Document de conception livré pour revue de l'ingénieur ; aucune approbation formelle du client n'est prétendue. L'URS d'origine reste conservée sans modification dans `URS-original.md`.

## Périmètre réalisé

Le MVP est une application locale complète : canevas P&ID, modèles déterministes, mapping, scénarios, historique, exports, adaptateur OPC UA et outillage d'ingénierie TIA séparé. L'interface est précompilée et servie par le même processus Python que l'API ; un utilisateur Windows n'a pas à lancer un frontend et un backend séparément.

## Hypothèses levées par conception

| Sujet de l'URS | Décision |
| --- | --- |
| Bibliothèque graphique | React Flow réutilisé ; symboles SVG propres au domaine FAT |
| Modèle | Bilan de volume d'une cuve, dynamique simple des actionneurs, caractéristiques de vanne HistorianSim |
| Couplage du dessin et de la physique | Lignes graphiques ; routage physique explicite par cuve/sens/groupe, affiché et documenté |
| Contrôleur autonome | Uniquement `DemoController` dans le mode Démonstration ; jamais dans l'adaptateur OPC UA |
| Interface PLC du MVP | OPC UA via asyncua ; types BOOL, INT, DINT, REAL ; nœuds scalaires et validation des droits |
| API native PLCSIM | Comparée dans l'étude, non implémentée dans cette version. L'OPC UA satisfait l'alternative autorisée par l'URS, sous qualification de la CPU |
| DB | Exemple SCL et contrat de treize tags ; adaptation manuelle et NodeIds observés dans TIA |
| IA | Czarnak MCP 4.3.0 séparé ; lecture seule côté client ; CLI d'import/compilation avec revue humaine |
| Persistance | JSON versionné pour projets/mappings/scénarios ; SQLite pour preuves de cycle ; sauvegardes atomiques |
| Résultat | Assertions automatiques et verdict humain distincts, rapport HTML imprimable, CSV et JSON complets |
| Installation | Python 3.12, UI précompilée, lanceur Windows, version portable de démonstration, construction de kit hors ligne |

## Ce qui nécessite toujours le poste Siemens

La version TIA **V21** est la cible de l'intégration MCP choisie. Les versions exactes de PLCSIM Advanced, Windows, CPU et firmware de l'utilisateur ne sont pas fournies. Il serait incorrect de déclarer une compatibilité concrète sans les relever et effectuer les essais.

Les points suivants sont donc des conditions d'acceptation sur site, pas des fonctions absentes remplacées par un succès fictif :

1. Disponibilité du serveur OPC UA de la CPU simulée, activation de sa licence/configuration applicable et réglage TCP/IP local.
2. Identité et accès aux NodeIds, types, droits, certificats et comportement du vrai programme PLC.
3. Définition des conditions initiales du programme PLC pour le rejeu.
4. Installation TIA Openness V21 et Czarnak, lecture d'un bloc, import d'une modification et diagnostics de compilation.
5. Temps de cycle réellement atteint en présence de TIA et PLCSIM sur le poste.

Le protocole est fourni dans `ACCEPTANCE.md`. Il n'exige aucun automate physique et ne requiert jamais une connexion au réseau de production.

## Garanties concrètes et limites

Un projet reçu peut contenir des adresses OPC UA mais ne peut pas autoriser sa cible. La politique locale est modifiée par le CLI humain, avec identité et références aux secrets épinglées. Le démarrage demande la cible exacte. Cela prévient les connexions accidentelles ; une ApplicationUri, une IP ou un nom de DB ne constituent pas, à eux seuls, une attestation cryptographique de virtualité. L'isolation de l'adaptateur PLCSIM doit donc être vérifiée par l'ingénieur.

Le temps du modèle avance par pas fixes. OPC UA ne synchronise pas chaque pas au cycle de la CPU. La vitesse accélérée est limitée au mode démo. Les dépassements de temps sont enregistrés. Une pause cesse les échanges et ferme la session, sans modifier l'état RUN/STOP du PLC.

La simulation et l'application n'appellent aucun service cloud. Le volet IA est optionnel et indépendant ; le choix d'un modèle hébergé peut transmettre du code hors du poste.
