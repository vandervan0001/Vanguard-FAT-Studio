# Programme public : TIA → PLCSIM Advanced → FAT Studio

Passe du 3 novembre 2026, sous Windows 11, TIA V21 et PLCSIM Advanced 8. Le programme chargé contient uniquement `DB_FAT_Demo` (DB1 standard) et `Main` (OB1 optimisé). Aucun FB, UDT, standard client, séquence métier ou diagnostic d'équipement n'est importé. Les [sources publiques et leur manifeste](public-bundle/manifest.json) restent distincts de la copie virtuelle activée.

La compilation native a produit exactement deux objets, avec **0 erreur et 3 avertissements** : accès invité permis, endpoint sans sécurité disponible sur le serveur virtuel, mot de passe de l'afficheur non défini. Le [chargement matériel et logiciel](native-online-2.receipt.json) a réussi avec **0 erreur et 0 avertissement**, sans démarrage automatique. Les essais utilisent exclusivement **Basic256Sha256 / SignAndEncrypt**.

La nouvelle CPU est `FAT-DEMO-20261103`, ID natif 1, article `6ES7 511-1AK02-0AB0`, firmware 2.9. Son stockage privé neuf est `.local/public-demo-2026-11-03/cpu-storage`. L'adresse `192.168.247.3` est routée sur le seul adaptateur Siemens virtuel, index 12, hôte `.1/24`, sans passerelle. La [preuve réseau publique](preflight-public.json) montre les bindings PLCSIM désactivés sur les autres cartes ; seul l'identifiant de l'ancienne fixture en a été retiré, son reçu d'origine reste privé et intact. L'ancienne CPU, son programme et le serveur FAT 8768 n'ont reçu aucune commande de cette passe. Les kits précédents restent intacts.

Le [certificat serveur public DER](opcua-server-public.der), vérifié comme certificat X.509, porte l'empreinte SHA-256 `bc9b4c3aacd92c1e50ae9c1efd09383b54c7e4324d050cc92b3e33c81e99e391`. L'ApplicationUri attendue et observée est `urn:SIMATIC.S7-1500.OPC-UA.Application:FAT-DEMO`. La première connexion S7 a refusé le certificat de démarrage inconnu avant tout secret ; son épinglage explicite repose sur l'identité native, le stockage et la route de cette seule instance. Le [reçu initial](native-online-1.receipt.json) conserve ce refus. Les secrets DPAPI et la clé privée client restent dans `.local` et ne sont pas copiés ici.

Les **75 correspondances** du [mapping observé](mapping-native-opcua.json) combinent les offsets en bits de l'[export Openness natif](DB_FAT_Demo.xml) et un parcours du vrai serveur en session chiffrée. Les 56 entrées sont inscriptibles et les 19 sorties sont en lecture seule ; `EnableDemo` est masqué à OPC UA. Le namespace 3 et les NodeIds sont observés, jamais déduits d'une adresse physique. Les REAL sont exposés en Float, les INT en Int16 et les BOOL en Boolean.

Le [résumé de campagne](campaign-summary.json) et le [journal des commandes](public-cli-commands.jsonl) établissent le trajet `python -m fat_studio.assistant` → FAT Studio 8770 → vrai OPC UA Siemens. Le client a capturé son contexte explicitement, importé le projet mappé, validé, démarré avec la confirmation exacte de cible, lu l'état, exporté chaque essai en JSON/CSV/HTML et arrêté l'exécution. **145 invocations publiques ont réussi**. Les écritures portent uniquement sur les entrées simulées ; aucun outil natif n'écrit de valeur d'I/O.

| Scénario public | Attentes réussies | Preuve |
| --- | ---: | --- |
| Alimentation source | 4/4 | [JSON](timed/demo-fill-source/exports/evidence.json) |
| Transfert vers cuve intermédiaire | 4/4 | [JSON](timed/demo-transfer-1/exports/evidence.json) |
| Transfert vers réception | 4/4 | [JSON](timed/demo-transfer-2/exports/evidence.json) |
| Vidange et position FCV | 3/3 | [JSON](timed/demo-drain/exports/evidence.json) |
| Contact d'arrêt de démonstration | 4/4 | [JSON](timed/demo-stop/exports/evidence.json) |
| Défaut physique de pompe | 5/5 | [JSON](timed/demo-pump-fault/exports/evidence.json) |
| Vanne bloquée | 3/3 | [JSON](timed/demo-valve-stuck/exports/evidence.json) |
| Échelles analogiques | 4/4 | [JSON](timed/demo-analog/exports/evidence.json) |

Les **31 attentes ont réussi sans modification des oracles**. Le modèle fournit les retours physiques et capteurs ; le PLC conserve ses commandes passives. Le défaut de pompe coupe ainsi le retour simulé alors que la commande reste demandée : cette différence fait partie de l'attente publique.

Le [premier STEP guidé](guided-continuation/summary.json) a été appliqué par le même client public : **12 mA → 13 824 points → 50 %**, commande P101 à FALSE. La lecture indépendante par l'API native confirme ces trois valeurs. **Aucune commande `step-observe` n'a été appelée, aucune observation n'a été inscrite, 0/5 étapes sont observées, le verdict humain reste `not_evaluated`.** Le [rapport HTML](guided-continuation/exports/report.html) conserve cet état incomplet.

Le premier harness a correctement terminé les huit cas, puis a lu une clé inexistante (`applied_at_s` au lieu de `applied_s`) après l'application du STEP. Son [reçu d'échec](harness-failure.json) et l'arrêt explicite de l'essai et de la nouvelle CPU sont conservés. La continuation a vérifié cet arrêt, corrigé seulement la lecture du champ et créé un nouvel essai guidé ; aucun scénario timed n'a été rejoué, aucun contexte n'a été recapturé automatiquement.

À la clôture de cette campagne, l'[essai est arrêté](final-backend-state.json), le projet OPC UA réel reste sélectionné et la nouvelle CPU est explicitement **STOP**. Une présentation utilisateur démarrée ensuite constitue un autre essai. Le propriétaire natif privé reste disponible sur loopback 8771 sans redémarrage automatique ; aucune commande CPU n'est ajoutée au client public ou au MCP.

Le [reçu de restauration](original-helper-restored.json) vérifie l'empreinte **et l'horodatage d'origine** de l'outil d'ingénierie précédent, temporairement utilisé au seul chemin Openness déjà autorisé. Cet outil est spécifique au poste de test et n'est pas requis par le parcours public de préparation manuelle. La tâche de mise à jour de l'AllowList a terminé avec le résultat 0. Les essais et les reçus précédents sont préservés.

Les refus de préparation sont aussi conservés : [type natif de licence](native-prepare-1.receipt.json), [politique de mot de passe du banc](native-prepare-2.receipt.json), [attribut d'optimisation OB1 absent](native-prepare-3.receipt.json), puis [compilation réussie](native-prepare-4.receipt.json). Les tests finaux du générateur sont **7 réussis et 1 ignoré** (création de symlinks interdite au compte Windows) ; Ruff passe. Les [contrôles finaux](final-verification-3.json) vérifient les empreintes, les Float32 des traces, les liens locaux et l'absence de clé privée ou secret copié ; le [manifeste SHA-256](checksums-3.json) couvre les fichiers figés. Ces résultats techniques ne constituent aucune validation FAT humaine et ne qualifient aucune bibliothèque privée.
