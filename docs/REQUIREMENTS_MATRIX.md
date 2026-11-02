# Matrice de couverture de l'URS

Référence : [URS originale, version 0.1](URS-original.md). Cette matrice distingue les composants livrés, les preuves exécutables locales et la qualification Siemens. Elle ne transforme pas un test sur double en essai sur une CPU virtuelle Siemens.

## Lecture des statuts

| Statut | Sens |
| --- | --- |
| **Local** | Implémenté ; comportement couvert par les vérifications locales indiquées. |
| **Local + Siemens** | Partie applicative et/ou protocole testés localement ; qualification de la combinaison TIA/CPU/PLCSIM à effectuer. |
| **Local + poste cible** | Partie applicative vérifiée localement ; installation et exécution sur le système cible restant à qualifier. |
| **Partiel explicite** | Fonction disponible avec une limite technique indiquée ; l'écart est conservé dans la remise. |
| **Documenté** | Procédure ou décision organisationnelle fournie ; l'application ne peut pas en attester seule l'exécution. |

Les commandes et résultats effectivement exécutés pour la livraison figurent dans [VERIFICATION.md](../evidence/VERIFICATION.md). Les fichiers `tests/` et `frontend/tests/` permettent de rejouer les contrôles. Les exécutions de cette livraison ont été réalisées sous Linux ; les scripts Windows ont été relus, mais l'installation Windows, sa variante hors ligne et les essais TIA/PLCSIM ne sont pas déclarés exécutés. La présence d'une CI configurée ne vaut pas résultat d'une exécution distante.

## Exigences fonctionnelles

| ID | Couverture livrée | Preuve / fichiers | Statut et limite |
| --- | --- | --- | --- |
| FR-001 | Créer, nommer, enregistrer, charger et exporter un projet JSON. | `app.py`, `storage.py`, `frontend/src/App.tsx` ; `tests/test_api.py` ; `frontend/tests/workbench.spec.ts`. | **Local**. Persistance après redémarrage et préservation d'un fichier corrompu testées. |
| FR-002 | Placer, déplacer, sélectionner, renommer et supprimer les symboles. | `frontend/src/PidCanvas.tsx`, React Flow ; tests navigateur du P&ID. | **Local**. Édition bloquée pendant exécution/pause. |
| FR-003 | Lignes entre symboles, libellés, direction facultative. | `Connection`, canevas React Flow ; validation de références dans `models.py`. | **Local**. Les lignes sont graphiques ; les circuits physiques se configurent explicitement. |
| FR-004 | Cuve, pompe, vanne TOR, vanne modulante, capteur analogique/binaire, indicateur. | `catalog.py`, `engine.py`, `demo.py` ; test de présence des sept types. | **Local**. Tous présents dans la démonstration. |
| FR-005 | Nom, description, unité, paramètres physiques et bindings éditables. | Catalogue et inspecteur de propriétés ; validation des plages/types de paramètres. | **Local**. Paramètres inconnus refusés au démarrage. |
| FR-006 | États de commande, retours simulés, positions, niveau, défaut et forçages visibles. | `engine.equipment_state`, snapshot runtime, symboles React ; tests boucle/défauts. | **Local + Siemens**. État du procédé et de ses tags ; état interne CPU non mesuré. |
| FR-007 | Souris, drag/drop, zoom/panoramique, grille, suppression et raccourci sauvegarde. | React Flow, `PidCanvas.tsx`, `App.tsx` ; tests navigateur. | **Local**. Utilisation poste de travail ; pas une CAO de construction. |
| FR-008 | DB d'échange et helper SCL, correspondance des treize tags de démo. | `siemens/DB_FAT.scl`, `FC_FAT_Exchange.scl`, `DB_FAT-tags.csv` ; `test_siemens_exchange_declarations_match_demo_tags`. | **Local + Siemens**. Sources et noms vérifiés ; compilation/raccordement TIA à réaliser. |
| FR-009 | Écritures des seules entrées simulées autorisées. | `adapters/opcua.py`, `models.py` ; tests de lot/type/droit et roundtrip OPC UA. | **Local + Siemens**. Vrai protocole contre serveur local de test ; CPU Siemens à qualifier. |
| FR-010 | Lecture des commandes et indicateurs PLC, image complète exigée. | Adaptateur OPC UA et `ProcessEngine.step` ; tests d'image incomplète et mauvaise qualité. | **Local + Siemens**. Aucun contrôleur de remplacement en mode OPC UA. |
| FR-011 | BOOL, INT, DINT, REAL scalaires, limites de stockage contrôlées. | `validate_tag_value` ; tests de types et `test_real_roundtrip_all_four_scalar_types`. | **Local + Siemens**. Tableaux/structures non pris en charge ; validation serveur obligatoire. |
| FR-012 | Associations par port, diagnostics de sens/type/référence/conflit. | `models.validate_project`, panneau Variables, inspecteur ; tests modèles/API. | **Local**. Deux producteurs ne peuvent pas écrire le même tag. |
| FR-013 | Import/export CSV du mapping et JSON du projet. | `mapping.py`, routes API, interface ; `test_csv_mapping_roundtrip_and_rejection`. | **Local**. Import invalide conservant le projet précédent testé. |
| FR-014 | Validation locale puis existence/type/rang scalaire/droits OPC UA avant écriture. | `_validate_nodes` ; tests nœud absent, mauvais type, doublon, droit insuffisant. | **Local + Siemens**. Vérification sur les NodeIds de la CPU cible à consigner. |
| FR-015 | `direction=input` et `writable=true` nécessaires, lot exact, aucune écriture output. | Schéma, moteur et adaptateur ; tests `test_output_variable_never_written`, lot complet. | **Local + Siemens**. La politique locale ne peut être créée par un projet importé. |
| FR-016 | Pas configurable 20–2 000 ms, boucle asynchrone, détection dépassements. | `SimulationConfig`, `runtime.py`, benchmark 50/200. | **Local + Siemens**. Pas de synchronisation déterministe avec le scan PLC ; mesures cible à faire. |
| FR-017 | Commandes → modèle → capteurs → contrôleur, boucle fermée de démonstration. | Moteur, adaptateurs et runtime ; scénarios de référence/rejeu. | **Local + Siemens**. Boucle avec le programme Siemens existant à démontrer. |
| FR-018 | Comportement paramétré des sept types, coefficients persistés dans le JSON. | `catalog.py`, `engine.py` ; tests volume, circuits, réponse et capteurs. | **Local**. Modèle simplifié documenté, sans hydraulique générale. |
| FR-019 | Cuve TK-101 complète, pompe, vannes, niveau et seuils. | `demo.py`, projet d'exemple ; scénarios 32/28/24 s. | **Local**. Démo originale ; données HistorianRCA non redistribuées. |
| FR-020 | Hypothèses, paramètres et avertissement de modèle visibles/documentés. | Catalogue, propriétés, `MODEL.md`, avertissement sur les lignes graphiques. | **Local / Documenté**. Fidélité adaptée aux séquences fonctionnelles. |
| FR-021 | `ProcessEngine` sans régulateur ; contrôleur fictif uniquement dans DemoAdapter. | Séparation `engine.py` / `adapters/demo.py` / `adapters/opcua.py` ; `test_plant_never_invents_a_controller`. | **Local**. Le contrôleur du PLC reste seul actif en OPC UA. |
| FR-022 | Démarrer, pause, reprise, arrêt, remise à zéro et fin de scénario. | Runtime/API/interface ; tests concurrence et pause/reprise. | **Local + Siemens**. Pause/reset du banc ne change pas RUN/STOP ni les états internes de la CPU. |
| FR-023 | Forçage d'inputs avec types, bornes, unité, indication et libération. | Moteur, routes `/force`, panneau variables ; tests limites, libération, refus output. | **Local + Siemens**. Les forces sont des valeurs de simulation, pas le mécanisme de force Siemens. |
| FR-024 | Capteur figé/hors plage, vanne bloquée, défaut moteur. | `set_fault`, catalogue, UI ; tests physiques et scénarios. | **Local + Siemens**. Réactions du programme réel à vérifier. |
| FR-025 | Scénarios nommés, durée, étapes temporelles et assertions sauvegardées. | `Scenario`, `ScenariosPanel`, runtime ; tests JSON/timeline. | **Local**. Édition des étapes en JSON validé. |
| FR-026 | Réinitialisation déterministe du modèle et archivage de sa configuration/scénario. | Runtime/store ; tests trajectoire identique et conservation d'évidence. | **Local + Siemens**. Réinitialisation du PLC externe à définir dans le protocole client. |
| FR-027 | Cible, état des échanges, dernier échantillon, erreur et perte de connexion. | Snapshot, bandeau Connexion ; tests perte OPC UA. | **Partiel explicite**. RUN/STOP de la CPU n'est pas lu ; état serveur OPC UA distinct, expliqué dans `PLCSIM_SETUP.md`. |
| FR-028 | Courbes directes et choix des variables. | `TrendChart`, fenêtre de 600 échantillons UI, historique complet dans SQLite. | **Local**. Rafraîchissement UI nominal 500 ms ; performance Siemens/PC cible à mesurer. |
| FR-029 | Temps UTC/simulé, valeurs, qualité et actions en historique. | `storage.py`, `runtime.py` ; tests de traces et redémarrage interrompu. | **Local**. Journal applicatif, pas registre inviolable de conformité. |
| FR-030 | CSV, rapport HTML et preuve JSON ; résultat utilisateur distinct des assertions. | `reporting.py`, API, panneau rapport ; tests exports et échappement de texte. | **Local**. Les exports utilisent la configuration archivée de l'essai. |
| FR-031 | Marqueurs/commentaires pendant l'essai. | Route `/markers`, UI et événements SQLite ; tests navigateur. | **Local**. Horodatage et temps simulé conservés. |
| FR-032 | Configurations Claude Code/Codex en lecture seule, upstream épinglé. | `integrations/tia_engineering.py`, `upstream.lock.json`, `TIA_MCP.md`. | **Local + Siemens**. Configurations générées ; clients et TIA réels à qualifier. |
| FR-033 | Arbre, blocs, tags, types/références selon serveur upstream. | Czarnak v4.3.0 ; CLI status/tree/tags/export ; tests MCP SDK stdio. | **Local + Siemens**. Langages/protections et contenus accessibles à établir sur projet cible. |
| FR-034 | Proposition indépendante `after.*`, diff et revue avant import. | CLI export/diff, références hashées ; tests source modifiée et refus. | **Local + Siemens**. Aucune promesse sur l'exactitude d'une proposition de modèle IA. |
| FR-035 | Lecture seule par défaut ; terminal humain distinct, activation, diff, archive avant import. | CLI d'ingénierie, sandbox, confirmation, hash ; tests non interactif/refus/archive/source périmée. | **Local + Siemens**. Restauration effective de l'archive `.zap21` à qualifier. |
| FR-036 | Demande de compilation approuvée, diagnostics structurés, sauvegarde conditionnée. | `compile_check` upstream et CLI ; test erreurs de compilation non sauvegardées. | **Local + Siemens**. Pas de compilation TIA exécutée dans l'environnement Linux de développement. |
| FR-037 | Aucun outil de téléchargement CPU, RUN/STOP ou provisioning dans le parcours contrôlé. | Liste étroite READ_TOOLS/WRITE_TOOLS, mode IA read-only ; test refus d'outils. | **Local + Siemens**. Vérifier la configuration du client installé ; le compte Windows reste maître de ses autres outils. |
| FR-038 | Journal JSONL des demandes/outils/cibles/confirmations/résultats et reçus de proposition. | `Audit`, `receipt.json`, notices `TIA_MCP.md` ; tests parcours contrôlé. | **Local + Siemens**. Traces applicatives altérables par le propriétaire du poste ; règles de rétention à fixer. |
| FR-039 | Avertissement explicite sur les données envoyées au modèle hébergé. | `TIA_MCP.md`, `USER_GUIDE.md`, configuration lecture seule séparée. | **Documenté**. Approbation confidentialité/IT et choix du client relèvent de l'organisation. |

## Exigences non fonctionnelles

| ID | Couverture livrée | Preuve / fichiers | Statut et limite |
| --- | --- | --- | --- |
| NFR-001 | Serveur loopback, UI embarquée, modèle et stockage locaux. | CLI, FastAPI, assets Vite ; essais API/navigateur sans Siemens. | **Local**. Le runtime FAT ne nécessite aucun service cloud. |
| NFR-002 | Aucun envoi externe de données de procédé par le runtime. | UI sans service distant, OPC UA limité à cible privée autorisée ; `security.py`. | **Local**. Dépendances téléchargées à l'installation standard ; IA optionnelle régie séparément. |
| NFR-003 | Double-clic Windows ou commande shell, serveur unique ouvrant le navigateur. | `Start-FAT.cmd`, `scripts/start.*`, CLI et `INSTALLATION.md`. | **Local + poste cible**. CLI testé localement ; scripts PowerShell à exécuter sur Windows cible. |
| NFR-004 | Locks Python/npm, assets précompilés, collecteur de kit Windows hors ligne et SHA-256. | `prepare-offline.ps1`, `setup.ps1`, locks ; disponibilité des wheels Windows CPython 3.12 vérifiée. | **Partiel explicite**. Kit générable ; installation Windows entièrement hors ligne à qualifier, Siemens séparé. |
| NFR-005 | Diagnostics lisibles, import invalide préservé, erreurs API/PLC visibles. | Validation, handlers API, UI ; tests mauvais JSON/type/mapping/origine et erreurs non JSON. | **Local**. Aucune réussite de communication fabriquée en cas d'échec. |
| NFR-006 | Perte de communication verrouille l'essai, cesse les écritures, aucune reconnexion automatique. | Adaptateur/runtime ; tests mauvais statut, déconnexion et écriture partielle. | **Local + Siemens**. Dernières valeurs possibles dans le DB ; aucune remise à zéro CPU garantie. |
| NFR-007 | Projets JSON atomiques et historique SQLite persistants. | Store et sauvegarde précédente ; tests rechargement/reprise après interruption. | **Local**. Sauvegarder le dossier service arrêté pour un transfert complet. |
| NFR-008 | Bandeau MODE FAT, états visibles et verrouillage de l'édition pendant l'essai. | App React ; tests UI/API d'édition interdite et conflit d'onglets. | **Local**. Un seul projet actif par processus. |
| NFR-009 | Mode démo par défaut, politique du poste séparée, identité/cible requises avant connexion. | `MachinePolicy`, CLI, tests auto-autorisation interdite. | **Local + Siemens**. Nature virtuelle établie par qualification de l'adaptateur, pas par l'IP seule. |
| NFR-010 | Aucune cible de production préconfigurée ; aucune entrée autorisée initialement. | Configuration par défaut, politique absente, mode démo. | **Local**. La procédure exclut les réseaux de production. |
| NFR-011 | Confirmation cible exacte, contrôle ApplicationUri et certificat lorsque chiffré. | CLI, dialog UI, adaptateur ; tests identité/confirmation/empreinte. | **Local + Siemens**. `None` ne fournit pas d'authentification cryptographique du serveur. |
| NFR-012 | MODE FAT visible, politique locale, IP explicite, blocage nœuds système et séparation Openness/runtime. | UI, policy, validations OPC UA, `PLCSIM_SETUP.md`. | **Partiel explicite**. Prévention d'erreurs ; pas de détecteur matériel garantissant qu'une IP privée est virtuelle. |
| NFR-013 | Ports, chemins, comptes, certificats, mode `<Local>` et Openness documentés. | `PLCSIM_SETUP.md`, `TIA_MCP.md`, `COMPATIBILITY.md`. | **Documenté**. Adapter à la version Siemens et aux règles IT réelles. |
| NFR-014 | Limites d'usage fonctionnel, absence de qualification sécurité et rôle de l'ingénieur explicités. | `MODEL.md`, `ACCEPTANCE.md`, documentation d'ingénierie. | **Documenté**. Aucun verdict SIL/GMP/conformité machine ou autorisation de mise en service. |

### Objectif indicatif de charge : 50 équipements / 200 tags

Le script [`scripts/benchmark.py`](../scripts/benchmark.py) construit 10 cuves et 40 vannes, avec **200 tags tous associés à des ports**, puis mesure séparément moteur, SQLite et combinaison des deux. [`evidence/benchmark.json`](../evidence/benchmark.json) contient la date, la plateforme, les versions, les empreintes des sources, p50/p95/max et les limites de la mesure.

La mesure inclut 1 000 cycles après échauffement et un véritable commit SQLite par échantillon. Elle exclut OPC UA, PLC, serveur HTTP et rendu navigateur. Le test local ne fixe pas la performance complète de l'installation Windows : la qualification doit mesurer le délai bout en bout, la charge CPU, les dépassements et la visibilité des erreurs sur le poste cible.

## Critères d'acceptation de l'URS

| N° | Critère | Preuve locale disponible | Réception restant à consigner |
| --- | --- | --- | --- |
| 1 | Créer, sauvegarder, fermer et recharger un P&ID des sept types. | Schéma/demo, API persistence, tests navigateur d'édition/rechargement. | Rejouer le parcours sur le poste de l'opérateur ; validation ergonomique utilisateur. |
| 2 | Mapping correct ; anomalies détectées avant démarrage. | Diagnostics de références/types/droits, vrai serveur OPC UA de test. | Relever les NodeIds/types/droits dans la CPU Siemens cible. |
| 3 | Connexion à l'instance PLCSIM convenue, cible non ambiguë. | Policy/identity/confirmation testées. | **À qualifier sur Siemens** : instance et isolement réseau observés. |
| 4 | Entrée simulée visible par PLC et commande PLC reflétée sur P&ID. | Roundtrip OPC UA réel contre serveur local de test ; boucle démo. | **À qualifier sur Siemens**, jusqu'au bloc consommateur, pas seulement au DB. |
| 5 | Scénario de référence en boucle fermée. | Trois scénarios démonstration et assertions/rejeu. | Adapter et approuver le scénario du programme client, puis le jouer sur PLCSIM. |
| 6 | Défaut injecté, effets visibles et enregistrés. | Moteur/runtime/UI testés, traces exportées. | Vérifier alarmes/interverrouillages attendus du programme Siemens. |
| 7 | Perte de communication : signalement et arrêt d'écriture. | Tests déconnexion, mauvais statut, écriture partielle et absence de reprise automatique. | Provoquer la perte prévue dans le protocole sur l'instance virtuelle isolée. |
| 8 | CSV et rapport synthétique. | Exports API/navigateur, contexte archivé et texte échappé. | Examiner et accepter le format de rapport avec le client FAT. |
| 9 | Reproductible depuis fichiers et dépendances versionnés. | Locks, builds, suite de tests, scripts et assets embarqués. | Installation propre Windows, puis kit hors ligne si demandé ; consigner versions et logs. |
| 10 | Aucun test ne requiert un automate de production. | Tests locaux sans Siemens ; protocole cible limité à une instance isolée. | Confirmer l'architecture d'essai, ses routes et la copie de développement. |
| 11 | IA liste/lit un bloc via MCP approuvé. | Client SDK et serveur MCP factice testés ; config upstream fixée. | **À qualifier sur TIA V21**, avec client choisi et bloc représentatif. |
| 12 | Diff visible, proposition rejetable sans altération. | Tests export/diff/refus sur double ; sources avant/après séparées. | Répéter sur une copie TIA et constater le bloc inchangé après refus. |
| 13 | Import approuvé, sauvegarde préalable, compilation et diagnostics. | Tests archive/import/compilation/refus/erreur contre double. | **À qualifier sur TIA V21**, y compris restauration de l'archive et refus de sauvegarde après erreur. |
| 14 | Aucun téléchargement/contrôle de CPU physique. | Inspection allowlist, tests d'outils interdits, mode client IA read-only. | Vérifier l'installation cliente et les opérations effectives ; conserver les journaux. |

Le protocole opératoire associé est [ACCEPTANCE.md](ACCEPTANCE.md). Les cases Siemens ne sont pas déclarées réussies dans cette livraison sans leurs preuves de poste.
