# Revue adverse — FAT Studio 0.1.1

Date : **2 novembre 2026**. Référence initiale : **commit c18e0d4, version 0.1.0**. Ce rapport décrit les corrections et vérifications de la version **0.1.1** par rapport à cette référence.

La revue a cherché des comportements incorrects observables dans les limites de l'[URS d'origine](URS-original.md) : mauvais essai ciblé, preuves incohérentes, écriture sans journal, perte de modifications, modèle partiellement avancé, frontière OPC UA insuffisante et installation mal contrôlée. Les tests existants ont servi de contrôle de régression ; leur nombre n'a pas été considéré comme une preuve préalable de robustesse.

Les reproductions décrites sont couvertes par les tests de la livraison corrigée. Les preuves d'exécution consolidées, les mesures et la vérification de l'installation sont regroupées dans [VERIFICATION](../evidence/VERIFICATION.md). La qualification du poste Windows et du véritable programme Siemens relève toujours du [protocole de réception](ACCEPTANCE.md).

## 1. Portée et lecture des résultats

La revue couvre le backend HTTP, le runtime asynchrone, les projets et preuves SQLite, les exports, le moteur de procédé, l'adaptateur OPC UA, le CLI d'ingénierie TIA, les lanceurs et le frontend compilé.

Les gravités expriment l'effet potentiel sur ce banc :

- **P1 — élevée :** une protection de communication, la cible d'une action ou la fidélité d'une preuve d'essai peut être compromise.
- **P2 — significative :** une fonction produit un résultat incorrect, perd un contexte ou une version utile, ou empêche un usage normal.
- **P3 — présentation ou diagnostic :** l'information reste disponible mais sa lecture ou son accessibilité est insuffisante.

Un cas construit pour vérifier une réponse impossible, incomplète ou malformée est identifié comme **contrôle défensif**. Il ne prouve pas que le fournisseur de cette réponse l'a réellement produite. Les familles ci-dessous regroupent parfois plusieurs variantes d'un même problème ; aucun total de « vulnérabilités » n'est déduit du nombre de tests.

### Résultats globaux exécutés

| Vérification | Résultat | Portée de la preuve |
| --- | --- | --- |
| Suite Python complète | **289 tests réussis**, aucune erreur, aucun échec, aucun ignoré ; environ **128,40 s** | [Rapport JUnit](../evidence/pytest.xml), incluant backend, modèle, OPC UA, sécurité, distribution et contrats d'ingénierie |
| Suite frontend et API cliente | **31 tests réussis sur 31**, environ **44,4 s**, avec le bundle compilé | [Bilan de vérification](../evidence/VERIFICATION.md) et [résultats frontend](../evidence/frontend-tests.json) ; cette suite inclut des tests TypeScript et des parcours navigateur, ce ne sont pas 31 parcours de bout en bout |
| Analyse statique | Ruff sans erreur sur le code Python vérifié | Commandes et périmètre dans [VERIFICATION](../evidence/VERIFICATION.md) |
| Première installation hors ligne dans un dossier neuf | Résultat et conditions consignés dans le bilan de livraison | Voir [VERIFICATION](../evidence/VERIFICATION.md) ; aucun succès d'installation n'est déduit ici des seuls tests du manifeste |
| CI Windows | Workflow fourni, **aucune exécution distante annoncée** | [Workflow CI](../.github/workflows/ci.yml) |

La suite backend ciblée comprend 65 cas, dont 21 nouveaux cas adverses ; 18 de ces nouveaux cas ont été observés en échec avant correction. Les nouveaux fichiers [test_adverse_process.py](../tests/test_adverse_process.py) et [test_distribution.py](../tests/test_distribution.py) regroupent respectivement 22 et 16 cas dans le rapport JUnit. Ces nombres décrivent les tests, pas un inventaire de défauts indépendants.

## 2. Backend, concurrence et conservation des preuves

Sources : [app.py](../fat_studio/app.py), [runtime.py](../fat_studio/runtime.py), [storage.py](../fat_studio/storage.py), [mapping.py](../fat_studio/mapping.py). Reproductions : [test_adverse_backend.py](../tests/test_adverse_backend.py). Régressions : [test_api.py](../tests/test_api.py) et [test_runtime.py](../tests/test_runtime.py).

### B1 — P1 : une commande d'un ancien essai pouvait agir sur le nouvel essai

**Reproduction.** Démarrer A, arrêter A, démarrer B dans le même projet, puis envoyer un verdict ou une commande depuis le contexte de A. L'identifiant et la révision du projet restaient identiques ; l'API acceptait l'action et visait B.

**Correction.** Les commandes d'essai vérifient désormais l'en-tête `X-FAT-Run-ID` sous le verrou des mutations. Une valeur périmée renvoie HTTP 409 avant l'action ; une chaîne vide signifie qu'aucun essai n'est attendu. Le frontend capture ce contexte au moment de l'action et le conserve lors d'un renouvellement du jeton.

**Test.** `test_actions_from_a_previous_run_cannot_target_a_replacement_run` refuse verdict, marqueur, forçage et arrêt de A pendant B, puis accepte la pause avec le bon identifiant. L'en-tête demeure facultatif pour les anciens clients API ; la protection du frontend livré repose sur son envoi effectif.

### B2 — P1 : un verdict pouvait être validé malgré l'échec de son journal

**Reproduction.** Un déclencheur SQLite refuse l'insertion de l'événement `user_result`. L'API renvoyait 503, mais le verdict « pass » et son commentaire avaient déjà été enregistrés dans une transaction distincte.

**Correction.** La conclusion et son événement sont écrits dans une même transaction. La copie en mémoire n'est modifiée qu'après validation de cette transaction. Les snapshots exposent maintenant `result: {verdict, comment}`, permettant de relire la conclusion enregistrée sans la réinitialiser dans le navigateur.

**Tests.** `test_failed_result_journal_does_not_commit_a_verdict` vérifie le rollback conjoint. `test_result_is_exposed_and_resets_only_for_a_new_run` couvre la lecture après sauvegarde, la conservation après pause/arrêt et la remise à zéro du nouvel essai, tout en conservant la conclusion archivée.

### B3 — P1 : une mutation non journalisée pouvait laisser le runtime exécutable

**Reproduction.** Faire échouer `Store.event()` pendant un forçage, une libération, une injection ou une suppression de défaut. Le modèle avait déjà changé et l'appel levait une exception, mais le runtime restait `running`, adaptateur connecté. La récupération HTTP intervenait après libération du verrou du modèle.

**Correction.** L'action enregistre son événement et traite son échec en conservant ce verrou. Une erreur entraîne la déconnexion, l'état d'erreur et l'annulation de la boucle avant de remonter à l'appelant. Les marqueurs et conclusions sont également gérés par le runtime.

**Test.** Les quatre variantes de `test_unrecorded_model_change_stops_before_another_plc_write` vérifient l'arrêt et l'absence d'écriture supplémentaire lors d'un nouveau cycle. Les erreurs de stockage restent visibles même si l'enregistrement du diagnostic échoue à son tour.

### B4 — P1 : une annulation asynchrone pouvait laisser un essai affiché en cours sans boucle active

**Reproduction.** Annuler le démarrage après connexion, ou annuler un cycle après l'écriture et avant son échantillon. Le premier cas laissait une connexion ouverte ; le second laissait un état `running` et une tâche morte. Des annulations pendant pause, reprise, arrêt et reset produisaient aussi des transitions incomplètes.

**Correction.** `CancelledError` est traité explicitement aux frontières de ces opérations. L'essai est clôturé en erreur, la communication est fermée et la dernière image reçoit la qualité `bad`. Une interruption pendant l'échange indique que le dernier lot peut être partiel. La tâche se détache à sa sortie ; une annulation normale provoquée par pause/arrêt ne devient pas un faux défaut.

**Tests.** `test_cancelled_connection_is_closed_and_recorded_as_error`, `test_cancelled_cycle_after_a_write_cannot_leave_a_silent_running_run` et les quatre variantes de `test_cancelled_lifecycle_transition_is_recorded_and_cannot_resume` couvrent ces transitions avec des adaptateurs suspendus de façon déterministe.

### B5 — P2 : recharger un projet écrasait sa version précédente

**Reproduction.** Enregistrer A puis B, charger un autre projet et recharger B. Le fichier `.previous.json` contenant A était remplacé par B alors qu'aucune nouvelle modification n'avait été enregistrée.

**Correction.** Une sauvegarde identique au document présent n'est plus traitée comme une nouvelle révision. La précédente version distincte est conservée.

**Test.** `test_reloading_saved_project_preserves_previous_revision` compare les octets de la sauvegarde avant et après le rechargement.

### B6 — P2 : un pointeur de démarrage absent pouvait remplacer une démo personnalisée

**Reproduction.** Un projet `tank-demo.json` personnalisé existe, mais `last-project.json` est absent. Le démarrage assimilait le dossier à une première installation et réenregistrait la démo d'origine sous le même identifiant.

**Correction.** Si des fichiers projet existent sans pointeur, le parcours de récupération crée un projet distinct et rend l'anomalie visible. Les fichiers existants restent intacts.

**Test.** `test_startup_without_pointer_preserves_existing_saved_demo` vérifie la conservation exacte du fichier et la présence du diagnostic.

### B7 — P2 : le mapping CSV pouvait exposer des cellules texte comme formules

**Reproduction.** Des noms, unités ou NodeIds commençant par `=`, `+`, `-` ou `@`, éventuellement après espaces, tabulation ou retour chariot, étaient exportés sans protection.

**Correction.** Le nouveau format ajoute la colonne `_fat_csv_encoding` avec la valeur `apostrophe-v1`. Les champs texte `name`, `unit` et `node_id` sont échappés de manière réversible ; une apostrophe initiale originale est elle-même échappée. Les nombres négatifs restent des nombres. L'import accepte encore les dix colonnes historiques et les interprète littéralement ; un marqueur nouveau inconnu ou un échappement incohérent est refusé.

**Tests.** `test_mapping_export_is_formula_safe_and_exactly_reversible` couvre préfixes formule, espaces, tabulation, CR, apostrophes et nombres négatifs. `test_legacy_mapping_import_keeps_literal_apostrophes_and_formulas` vérifie la compatibilité des anciens fichiers.

### B8 — P2 : un export de mapping pouvait provenir d'un autre contexte de projet

**Reproduction.** Modifier le mapping dans un autre onglet, puis exporter avec l'ancien contexte. Le GET renvoyait le mapping désormais actif sans contrôler les en-têtes de révision.

**Correction.** `GET /api/mapping` vérifie identifiant et révision sous le verrou utilisé pour les remplacements de projet. La réponse contient `X-FAT-Project-Revision`. Le frontend vérifie la réponse avant de déclencher le téléchargement.

**Test.** `test_mapping_export_rejects_a_stale_project_context` vérifie 409 pour l'ancien contexte, 200 pour le contexte actuel et la présence de la bonne révision. Un parcours navigateur provoque le changement de projet pendant la requête et confirme l'absence de téléchargement.

### B9 — P2 : la liste des projets pouvait masquer une discordance de fichier

**Reproduction.** Un fichier `wrong-name.json` contenant l'identifiant interne `tank-demo` apparaissait comme un second `tank-demo`. L'entrée ne désignait donc pas son propre fichier.

**Correction.** La liste applique maintenant la même validation que le chargement : le nom du fichier doit correspondre à l'identifiant interne. Une entrée incohérente reste identifiée par son fichier et porte une erreur visible.

**Test.** `test_project_listing_marks_internal_filename_mismatch_as_unloadable` vérifie l'entrée défectueuse distincte et la disponibilité du projet valide.

## 3. Modèle de procédé et frontière OPC UA

Sources : [models.py](../fat_studio/models.py), [engine.py](../fat_studio/engine.py), [opcua.py](../fat_studio/adapters/opcua.py). Tests : [test_adverse_process.py](../tests/test_adverse_process.py), [test_opcua.py](../tests/test_opcua.py). Les échanges OPC UA utilisent un serveur local réel de la bibliothèque asyncua, pas une instance Siemens.

### P1 — Namespace système atteint après résolution d'une URI

**Reproduction.** Un NodeId configuré dans un namespace numérique autorisé était remappé vers le namespace système 0 par une URI correspondante. Le contrôle effectué avant la résolution ne suffisait pas et la connexion était acceptée.

**Correction et test.** La résolution de l'URI vers 0 est maintenant refusée avant toute écriture. `test_namespace_resolution_cannot_bypass_system_namespace_prohibition` expose volontairement une variable inscriptible dans le namespace 0 et vérifie qu'elle reste inchangée. La résolution normale d'un index numérique devenu périmé reste couverte.

### P1 — Identité de session vérifiée après l'activation authentifiée

**Reproduction.** Le serveur de test change l'ApplicationUri dans la réponse CreateSession. Le client envoyait ses identifiants lors d'ActivateSession avant de rejeter l'identité inattendue.

**Correction et test.** La validation est déplacée dans le traitement de CreateSession, avant l'activation. `test_session_identity_is_checked_before_user_authentication` vérifie qu'aucune tentative d'authentification n'a lieu lorsque cette identité diffère.

### P1 — Une empreinte correcte ne garantissait pas la validité du certificat

**Reproduction.** Avec l'empreinte attendue, des certificats expirés, pas encore valides ou dont le SAN URI ne correspondait pas à l'application étaient acceptés.

**Correction et test.** Le contrôle de l'empreinte est complété par les vérifications de période de validité, d'URI d'application et de rôle serveur du validateur asyncua. Les trois variantes de `test_pinned_certificate_still_requires_valid_time_and_application_uri` sont refusées avant écriture. Cela ne remplace pas la qualification du certificat et de la politique sur le poste cible.

### P1 — L'image REAL du modèle pouvait différer de celle reçue par le PLC

**Reproduction.** Une valeur comme 16 777 217 était conservée dans l'image Python alors que le Float OPC UA transporte 16 777 216. Une borne décimale telle que 0,1 pouvait aussi rejeter sa propre représentation Float32 relue.

**Correction.** Les signaux REAL sont quantifiés en Float32 aux frontières des tags, mesures, forces et commandes. Les bornes sont comparées dans la même représentation. Le calcul physique interne conserve sa précision double ; les cibles et tolérances d'assertion restent celles demandées par l'utilisateur.

**Tests.** `test_real_measurement_and_force_are_the_value_a_plc_receives`, `test_decimal_real_limit_accepts_its_wire_representation_but_not_next_float` et `test_model_evidence_matches_real_float32_roundtrip` couvrent le modèle, les limites et le transfert OPC UA effectif. Le défaut hors plage doit rester hors plage après quantification.

### P2 — Certaines plages de capteurs étaient acceptées avant un échec d'initialisation

**Reproduction.** Un capteur INT avec offset 40 000, mesurant un débit agrégé ou le volume de débordement cumulé, était validé puis échouait à la construction du modèle. Un débit admissible de 25 L/s multiplié par 2 000 dépassait également INT sans rejet préalable.

**Correction.** La validation calcule les bornes des débits agrégés à partir des groupes configurés et vérifie la valeur initiale des grandeurs cumulées. Une grandeur cumulative sans borne supérieure reçoit un avertissement explicite ; un dépassement ultérieur du type reste une erreur d'essai.

**Tests.** Les trois variantes de `test_sensor_initial_offset_is_validated_even_for_aggregate_or_cumulative_fields` et `test_aggregate_flow_range_is_validated_before_start` couvrent ces configurations.

### P1 — Une erreur de capteur pouvait laisser un demi-cycle de procédé

**Reproduction.** Une mesure INT du débordement cumulé dépasse sa plage pendant un cycle. L'exception survenait après l'avancement du volume et du temps, laissant une image incohérente.

**Correction et test.** Le cycle est calculé sur un état préparatoire puis validé globalement. En cas d'échec, valeurs, qualités, états d'équipement et temps reviennent à la dernière image cohérente. `test_dynamic_sensor_overflow_does_not_commit_a_partial_process_step` vérifie cette restauration.

### P2 — Le contrôle de niveau d'une sortie de cuve utilisait le sens du remplissage

**Reproduction.** Un équipement de vidange réglé sur contrôle de niveau démarrait au niveau bas, comme un équipement d'alimentation.

**Correction et tests.** Le contrôleur de démonstration inverse l'action pour une sortie : démarrage au seuil haut, maintien dans l'hystérésis, arrêt au seuil bas. `test_demo_outlet_level_control_drains_at_high_level_and_stops_at_low_level` le vérifie. `test_demo_outlet_constant_command_stays_explicit_and_plant_has_no_controller` confirme qu'une commande constante reste explicite et que le moteur physique ne remplace pas le PLC.

### Contrôles complémentaires et fermeture de transport

Les tests supplémentaires couvrent authentification correcte, erronée ou absente sans repli anonyme, valeurs REAL non finies ou tableau reçus à chaud, limites et sous-normaux Float32, et annulation de la fermeture.

La fermeture explicite du socket dans un bloc `finally` renforce la responsabilité de l'adaptateur et est vérifiée avec un client suspendu. **Aucune fuite de socket réelle d'asyncua n'est revendiquée : asyncua 1.1.8 possédait déjà une fermeture dans son propre finally.** Ce cas est un renforcement de contrat, distinct des reproductions précédentes.

## 4. CLI d'ingénierie TIA et contrats MCP

Sources : [tia_engineering.py](../integrations/tia_engineering.py), [tests d'ingénierie](../tests/test_engineering.py), [verrou upstream](../integrations/upstream.lock.json), [revue upstream](UPSTREAM_REVIEW.md). Le serveur retenu reste Czarnak **v4.3.0**, commit **10c5de2eb44c0362792cd141370b3f42f92f6ecd**. Les modifications concernent son client FAT Studio, sans réécrire ce serveur.

### P1 — Le journal pouvait désigner un fichier du projet TIA

**Reproduction.** Une politique en lecture seule pouvait choisir le fichier projet comme chemin d'audit. Même une simple consultation consigne un événement : elle pouvait donc ajouter du JSON à un fichier TIA.

**Correction.** Le journal doit être un fichier .jsonl hors du répertoire projet, ne pas être un répertoire et ne pas aliaser le projet ou l'exécutable MCP. Le contrôle passe par les chemins canoniques et, pour les fichiers existants, par leur identité.

**Preuve.** `test_readonly_policy_cannot_append_audit_into_tia_project` refuse le chemin du projet. Les conditions supplémentaires d'extension et d'alias sont des contrôles défensifs visibles dans la validation de politique ; elles ne sont pas présentées comme autant d'incidents reproduits.

### P2 — L'arbre paginé était coupé à la première page

**Reproduction et contrat.** Le CLI lisait une page, fermait le processus stdio et proposait de réutiliser un curseur dans une autre invocation. Les curseurs du contrat d'arbre v3 sont attachés au processus ; ce parcours ne permettait pas de parcourir correctement un arbre dépassant une page.

**Correction.** La commande tree consomme toutes les pages dans la même session. Elle vérifie la stabilité du snapshot et de la requête, les offsets et nombres de nœuds, leur ordre, leurs parents, l'unicité des identifiants et la progression du curseur. Un ancien curseur fourni séparément est refusé avec explication.

**Preuve.** `test_tree_collects_pages_within_one_server_session` fournit deux pages de contrat et vérifie une unique connexion et l'ordre des appels. `test_tree_v3_failure_is_not_a_successful_cli_exit` injecte une réponse d'échec et vérifie le code de sortie non nul.

### P1 potentiel — Diagnostics incomplets ou contradictoires : validation défensive

La matrice `test_compile_incomplete_or_malformed_result_is_not_passed` construit des réponses de contrat comportant une omission, un statut contradictoire, un booléen à la place d'un compteur, une erreur PLC cachée dans un total incohérent ou une liste PLC vide. Le client vérifie désormais l'enveloppe, les compteurs entiers, leur somme et la concordance des états avant de déclarer une compilation réussie. Les omissions de vérification d'import et les réponses de sauvegarde sont également contrôlées.

**Ces réponses sont synthétiques. Aucun de ces cas n'est présenté comme un défaut observé du serveur Czarnak ou du compilateur Siemens.** Un aller-retour stdio réel du SDK MCP est testé, mais la compilation et les opérations TIA restent exercées au moyen de doubles de contrat. La validité réelle d'un import, d'une compilation et d'une restauration d'archive sur TIA reste à qualifier selon [TIA_MCP](TIA_MCP.md) et [ACCEPTANCE](ACCEPTANCE.md).

## 5. Distribution et première installation

Sources : [check-kit.py](../scripts/check-kit.py), [setup.ps1](../scripts/setup.ps1), [start.sh](../scripts/start.sh), [prepare-offline.ps1](../scripts/prepare-offline.ps1). Tests : [test_distribution.py](../tests/test_distribution.py).

### P2 — Les lanceurs n'appliquaient pas la même validation du kit

Les contrôles du manifeste étaient dupliqués entre PowerShell et shell, et ne vérifiaient pas uniformément la plateforme du kit, son option d'ingénierie et la paire manifeste/wheelhouse. La validation est désormais centralisée dans un script Python utilisant uniquement la bibliothèque standard, exécuté avant pip.

Les **16 tests de distribution** couvrent un manifeste avec BOM PowerShell, un chemin contenant espaces et accents, l'absence normale de kit dans un clone source, une plateforme incompatible, une option d'ingénierie non préparée, une wheel modifiée ou non répertoriée, un manifeste ou wheelhouse absent, des chemins non portables ou sortant du kit, des collisions de casse Windows et le code de sortie du validateur.

Ces tests utilisent pour certaines vérifications des fichiers wheel opaques : ils vérifient l'intégrité et le contrôle des entrées du kit, pas l'installation de ces fichiers fictifs. La vérification d'un paquet réellement installé est une preuve distincte dans [VERIFICATION](../evidence/VERIFICATION.md).

### P2 — L'architecture doit être celle de l'interpréteur choisi

Les lanceurs imposent Python 3.12 64 bits ; sous Windows, l'interpréteur doit utiliser la plateforme AMD64. La vérification suit la plateforme Python, pas seulement le processeur hôte : un hôte ARM utilisant Python AMD64 n'est pas assimilé à un Python ARM.

`test_windows_kit_uses_python_architecture_even_on_an_arm_host` simule cette distinction. Il ne constitue pas une exécution sur Windows ARM. Un kit incompatible est refusé avant l'installation, sans repli implicite vers un index.

### Préparation du kit et CI : prévention de contamination

La préparation exclut désormais des répertoires de tests et caches, environnements locaux, fichiers .env, clés et certificats, fichiers de construction temporaires et points de réanalyse. Il s'agit d'un durcissement de la sélection des fichiers ; aucune fuite de secret préalable n'est revendiquée.

Le workflow livré prévoit une première installation Windows dans un nouveau dossier, avec index désactivé, puis un contrôle HTTP du paquet installé via [smoke-installed.py](../scripts/smoke-installed.py). **Ce workflow Windows n'a pas été exécuté dans l'environnement de revue.** Le manifeste SHA-256 vérifie l'intégrité des fichiers comparés ; il ne fournit pas une signature d'authenticité de l'éditeur.

## 6. Interface et contexte opérateur

Sources : [App.tsx](../frontend/src/App.tsx), [Panels.tsx](../frontend/src/Panels.tsx), [PidCanvas.tsx](../frontend/src/PidCanvas.tsx), [api.ts](../frontend/src/api.ts), [styles.css](../frontend/src/styles.css). Preuves : [parcours adverses](../frontend/tests/adversarial.spec.ts), [tests de l'API cliente](../frontend/tests/api-errors.spec.ts) et [parcours existants](../frontend/tests/workbench.spec.ts).

| Famille et gravité | Reproduction ou contrôle | Correction et preuve |
| --- | --- | --- |
| Conclusions et marqueurs, P1 | Changer de section faisait perdre un brouillon ; recharger une conclusion enregistrée la présentait à nouveau comme non évaluée | État du rapport conservé au niveau de l'application, relu depuis snapshot.result. Tests « un brouillon de conclusion et de marqueur survit… » et « une conclusion enregistrée est relue… ». |
| Brouillon attaché à son essai, P1 | Un autre onglet arrête puis démarre un nouvel essai pendant la rédaction | Le brouillon garde son run_id, l'envoi vers le nouvel essai est bloqué, un téléchargement permet de le récupérer. Une sauvegarde lente conserve aussi les nouvelles observations saisies pendant la requête. |
| Réponse de polling périmée, P2 | Retarder une réponse running, mettre en pause, puis libérer l'ancienne réponse pouvait rétablir un affichage obsolète | Le frontend filtre les snapshots par contexte, date et génération de mutation. Le test confirme que l'écran reste en pause. |
| Renouvellement de session, P1 | Changer le contexte global pendant le renouvellement d'un jeton pouvait rediriger une action en attente | Projet, révision et essai sont capturés au départ et conservés lors de la reprise. Le test de l'API cliente vérifie l'envoi du contexte original et le refus 409. |
| Sauvegarde inchangée, P2 | Enregistrer ou valider un projet inchangé réinitialisait le contexte de l'essai arrêté et ses liens d'export | Le frontend évite le PUT lorsque le projet n'a pas changé. Le test conserve l'identifiant d'essai et l'accès au rapport après Enregistrer puis Valider. |
| Réseau et attente bloquée, P2 | Une session ou une lecture d'état sans réponse pouvait laisser l'interface attendre indéfiniment | Délais bornés : 5 s pour session/polling, garde d'initialisation de 10 s. Les commandes sont bloquées pendant l'indisponibilité, le brouillon est conservé et le retour du service est testé. |
| Exports et conflit de projet, P1 | Le pointeur actif du serveur pouvait changer entre l'affichage et le téléchargement | Les preuves utilisent le run_id affiché, le projet exporté correspond au document affiché et le mapping passe par la garde de révision. Le changement d'onglet pendant l'export CSV est provoqué en test. |
| JSON de scénario non appliqué, P2 | Un conflit de projet laissait un brouillon JSON brut hors du projet sauvegardé | Le texte non appliqué reste visible et peut être téléchargé séparément, octet pour octet, y compris s'il est encore incomplet. |
| Forçage vide, P1 | Effacer le champ numérique était converti par JavaScript en zéro | Une saisie vide est refusée avant l'appel API ; le test vérifie l'absence de force active sur la mesure. |
| Associations et états des symboles, P2 | Une association devenue incompatible était masquée par le sélecteur ; une pompe sans retour optionnel et une vanne partiellement ouverte pouvaient être mal représentées | Association conservée avec diagnostic et aria-invalid jusqu'à correction ; retour visuel sur l'état physique de pompe ; état actif de vanne fondé sur sa position, y compris une ouverture de l'ordre de 35 %. Les parcours vérifient l'association, la pompe et la vanne en fonctionnement. |
| Poste de largeur 768 px, P2/P3 | Les libellés masqués perdaient leur nom accessible et le bandeau FAT/démonstration disparaissait | Noms accessibles explicites et adaptation du bandeau. Vérifications à 768 × 1 024 et 1 024 × 768, sans débordement horizontal, avec MODE FAT et DÉMONSTRATION visibles. |

Un parcours supplémentaire construit réellement le graphe à la souris : ajout par glisser-déposer, liaison des ports, déplacement, sauvegarde, rechargement et suppression. Il vérifie les positions et connexions stockées, l'absence de suppression d'un symbole lors d'un Backspace dans un champ, et la conservation des tags lors de la suppression d'un équipement. Ce parcours est un **contrôle de fonctionnement**, sans défaut de persistance des positions revendiqué à partir de ce seul test.

Le résultat de 31 tests concerne le frontend compilé et l'API cliente dans leur ensemble. Le [guide frontend](../frontend/README.md) précise le serveur de test et la configuration Playwright ; un serveur Vite de développement seul ne vaut pas validation du bundle livré.

## 7. Contrôles restés satisfaisants et limites fonctionnelles assumées

Les suites de régression continuent de vérifier le refus des Host/Origin externes et des requêtes cross-site, le jeton local, les limites de corps HTTP, les valeurs non finies, les mappings invalides avant écriture et l'impossibilité d'autoriser une cible depuis un projet importé. Les références sont [test_api.py](../tests/test_api.py), [test_security.py](../tests/test_security.py) et [test_opcua.py](../tests/test_opcua.py).

Les preuves conservent le projet initial de chaque essai. Les exports capturent un préfixe fini et cohérent pendant la poursuite de l'exécution, et un ancien essai peut être exporté sans recevoir les marqueurs du nouvel essai. Le CSV de mesures neutralisait déjà les préfixes formule ; le HTML échappait déjà les textes opérateur. Les nouveaux contrôles tabulation/CR et balises exécutables passent. Voir [test_runtime.py](../tests/test_runtime.py) et [test_adverse_backend.py](../tests/test_adverse_backend.py).

Les protections existantes du dossier de données restent couvertes : refus d'un second processus, conservation d'une base corrompue, récupération des essais non clôturés comme interrompus, et conservation des preuves après reset. Les tendances et le journal visible restent bornés ; les mesures sont exportées progressivement. Les événements d'un rapport complet sont encore chargés en mémoire : il n'est pas annoncé ici un export à mémoire constante de tous les types de preuve.

La quantification des actions au prochain début de pas et l'évaluation des assertions sur une image achevée sont décrites dans [FDS](FDS.md), [MODEL](MODEL.md) et [CONTRACT](CONTRACT.md). Ce comportement documenté n'a pas été transformé en faux défaut. La pause du banc ne met pas la CPU en STOP et le reset du modèle ne réinitialise pas le programme PLC.

## 8. Qualifications et opérations non réalisées

- **Windows, TIA Portal, Openness et PLCSIM Advanced réels :** ni les lanceurs Windows, ni un programme Siemens, ni le compilateur TIA n'ont été exécutés pendant cette revue. La compatibilité CPU/firmware, l'isolation réseau, le scan PLC et les opérations d'ingénierie demandent les essais de [COMPATIBILITY](COMPATIBILITY.md), [PLCSIM_SETUP](PLCSIM_SETUP.md) et [ACCEPTANCE](ACCEPTANCE.md).
- **Pannes physiques et endurance :** les erreurs de disque et les annulations sont injectées de manière déterministe. Il n'y a pas de campagne de coupures électriques, d'usure disque, de saturation prolongée ou d'endurance complète navigateur/OPC UA à 200 tags. Le [benchmark](../evidence/benchmark.json) mesure un périmètre plus limité ; ses conditions sont décrites dans [VERIFICATION](../evidence/VERIFICATION.md).
- **Sécurité externe :** la revue et les tests de frontières locales ne constituent pas un pentest externe, une certification SIL, une validation machine ou une preuve que tout serveur portant une identité approuvée est virtuel.
- **Contrats tiers :** les matrices de réponses MCP malformées éprouvent le refus défensif du client. Aucun défaut amont de Czarnak n'est affirmé à partir de ces réponses construites.
- **Publication distante :** la création d'un dépôt GitHub n'a pas été réalisée dans cette session : le connecteur disponible ne permettait pas de créer un dépôt et Google a refusé la connexion dans ce navigateur non reconnu. Une CI fournie dans les sources n'est donc pas présentée comme une CI exécutée ou publiée.
- **Réception métier :** les tests automatiques n'attribuent pas de verdict humain aux FAT client. Les conditions initiales du PLC, les séquences attendues et la décision de réception restent à renseigner dans le protocole du poste.

Ce rapport clôt la revue des modifications décrites pour 0.1.1. Les résultats observés et les limites ci-dessus doivent accompagner la livraison ; les qualifications non exécutées restent explicitement ouvertes.
