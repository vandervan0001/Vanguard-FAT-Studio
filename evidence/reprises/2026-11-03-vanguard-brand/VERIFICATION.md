# Vanguard FAT Studio : identité et vérifications

Reprise du 3 novembre 2026, Windows x64, Python 3.12.10, Node 22.23.4. Sources sur `codex/vanguard-fat-studio-brand`, depuis `cd4daba16580309a675dfa6b1ec95efe5a669038`, travail local conservé et checkpoint avant DA vérifié. Les anciennes preuves et livraisons scellées sont intactes.

La DA reprend les logos originaux, Geist/OFL, le bleu `#0055DD` et les surfaces claires du dépôt `vanguard_systems`, commit `b4df8d8ed0942e98ceee643a9be210f00aca9e9f`. Les couleurs d'état restent fonctionnelles. Le code applicatif du site et les standards privés ne sont pas repris.

| Contrôle | Résultat | Preuve |
| --- | --- | --- |
| Suite Python finale | 581 réussis, cinq ignorés sous ce compte Windows, 234,41 s | [Reçu logiciel](software-verification.json) |
| Frontend livré | 56/56, zéro échec/ignoré/flaky, 161,481 s | [Reçu UI](ui/audit-receipt.json) |
| Vraie fenêtre Edge et cadrage | 1/1 chacun ; fichiers sources/assets stables | [Empreintes UI](ui/checksums.json) |
| Rapport autonome | Trois fontes et logo embarqués, deux tailles relues, aucun appel externe/script/débordement | [Rendus](reports/render-verification.json) |
| Nouveau nom client OPC UA réel | 75 mappings, 19 sorties lues, SignAndEncrypt, zéro écriture | [Lecture native](native-read-only.json) |
| Présentation réelle brandée | Nouvelle copie locale, 75 good pendant échanges, puis pause avant STEP 1 ; historiques précédents conservés | [Présentation](native-presentation.json) |
| Anciennes archives | Véritable archive native de 19 essais restaurée avec données et rapports d'origine | Régression `test_pre_branding_real_archive_keeps_its_original_reports_and_history` |
| GitHub | Dépôt renommé, même ID et visibilité privée, origin à jour | [Renommage](github-rename.json) |

Les rapports JUnit et journaux bruts restent privés ; les compteurs et empreintes du reçu sont publics. La lecture native vérifie le nouveau client ; les 31 attentes TIA V21/PLCSIM Advanced 8 antérieures restent une [campagne distincte](../2026-11-03-public-demo/final-live/VERIFICATION.md). Aucun verdict humain, qualification V20, CPU physique ou sécurité fonctionnelle déduit.

Les deux kits Windows scellés ont passé les contrôles de lancement et de service, dont 19 appels du client public pour le portable. Les ZIP ont été contrôlés entrée par entrée. [Contrôles des kits](distribution/final-delivery-checks.json) et [empreintes des ZIP](distribution/delivery-zips.json).

Le film séparé dure 45 s en 1080 × 1350 à 30 images/s. Il présente des commandes réellement exécutées en mode démo et cite la campagne Siemens antérieure. Le dossier média du dépôt contient les MP4 sous-titrés, le SRT, les sources et les résultats des contrôles. La planche du master a été relue.

Le [guide de reprise](../../../docs/codex/ETAT_REPRISE.md) et la [note de session](../../../docs/codex/sessions/2026-11-03-vanguard-brand-video.md) donnent l'état courant et les prochaines opérations précises.
