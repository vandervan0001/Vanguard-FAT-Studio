# Préparer la validation TIA sur le PC Windows

Le 2 novembre 2026, Tai a demandé un prompt pour reprendre avec Codex sur le PC Windows et finir la validation TIA V20/V21. La base du travail est `main`, commit `6c854ddc4c04643647f522e75b7c98c835aa8ea5`, tag `v0.2.1`, dans le dépôt privé FAT-Studio. La CI du runtime reste celle du code `b55bfded63dc5572da8d3409409210381cc50c34` ; aucun nouvel essai Windows ou Siemens n'a été exécuté pendant cette préparation.

Le [prompt dédié](../PROMPT_VALIDATION_WINDOWS_TIA_V20_V21.md) décrit le poste, les profils et DLL distincts, le build natif V20, le client Codex en lecture seule, les essais d'ingénierie avec confirmations humaines, puis les échanges OPC UA et scénarios sur instance virtuelle isolée. Il exige une preuve par version et conserve le statut non exécuté lorsqu'un prérequis manque.

Trois mentions historiques limitées à V21 dans `docs/ACCEPTANCE.md` ont été adaptées aux suffixes et profils V20/V21. `README-CODEX.md` et l'état de reprise pointent vers ce prompt. Les fichiers existants avant édition sont préservés sous `../work/2026-11-02-windows-handoff/scratchpad/source-before`.

Changements documentaires uniquement : relecture de cohérence et contrôle des liens requis, sans relance des suites applicatives. Les résultats de la CI 0.2.1 restent attachés à leur SHA ; cette passation ne prouve aucune compilation native ou qualification Siemens supplémentaire. Aucun serveur n'a été démarré.

Prochaine action : cloner ou ouvrir le dépôt sur le PC Windows, donner le prompt à Codex, puis relever les versions et copies Siemens réellement disponibles. Conserver le parcours de confirmation du terminal humain et consigner les résultats avant de déclarer V20 ou V21 qualifié.
