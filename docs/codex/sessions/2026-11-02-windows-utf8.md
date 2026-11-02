# Correctif d'encodage Windows — 0.2.1

Le 2 novembre 2026, la première CI du dépôt privé a testé le commit `1d86ca42c06a551b4831dc2b4ffe5b6ce08ac4ca`. Ubuntu a réussi ses 418 tests Python et 33 tests frontend. Windows a réussi 411 cas Python et en a échoué sept ; les étapes frontend et installation hors ligne n'ont donc pas tourné. [Exécution initiale](https://github.com/vandervan0001/FAT-Studio/actions/runs/41466328324).

Cause : cinq captures de processus Python demandaient du UTF-8 au parent mais laissaient les enfants écrire dans l'encodage Windows ; deux tests du vrai source amont lisaient un chemin Git accentué avec l'encodage local. Un des tests de capture défaillants existait déjà en 0.1.1 ; cette version n'avait pas été exécutée sous Windows.

Changements : `prepare_tia_server._git` décode explicitement UTF-8 ; les enfants Python de `test_distribution.py` sont lancés avec `-X utf8`. Les assertions de contenu, de refus et de préservation des fichiers restent inchangées. Version portée à 0.2.1, sans déplacement du tag 0.2.0. Source avant modification conservée sous `../work/2026-11-02-windows-encoding/scratchpad/source-before`.

Contrôles locaux : les 30 tests distribution/préparation source affectés passent, avec le vrai clone Czarnak épinglé ; Ruff et le build TypeScript/Vite passent. Le bundle JS est identique au 0.2.0. Les preuves et commandes sont dans le [rapport dédié](../../../evidence/reprises/2026-11-02-windows-utf8/VERIFICATION.md). Les résultats de la nouvelle CI sont à vérifier sur GitHub avant d'annoncer la réussite Windows.

Branche de correction : `codex/windows-utf8`, base `1d86ca4`, destinée à être avancée et poussée sur `main`. Vérifier `git status`, `git log -1` et les refs distantes pour l'état exact après publication. Le dépôt reste privé ; aucun service FAT local n'est laissé actif, données conservées. Les essais TIA/PLCSIM et le build natif du candidat V20 restent à effectuer sur une copie autorisée et la vraie installation Windows.
