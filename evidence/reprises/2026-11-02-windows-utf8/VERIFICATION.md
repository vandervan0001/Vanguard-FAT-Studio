# FAT Studio 0.2.1 — encodage Windows

Le correctif traite les sept échecs Python de la première [CI 0.2.0](https://github.com/vandervan0001/FAT-Studio/actions/runs/41466328324). Ubuntu avait réussi ; Windows avait 411 tests réussis et sept échecs. Les étapes Windows suivantes, dont le kit hors ligne, n'avaient pas été exécutées.

Deux causes ont été distinguées dans les logs :

- Cinq captures Python décodaient du UTF-8 sans demander le même encodage à l'enfant Windows. L'enfant reçoit désormais `-X utf8` ; les assertions restent les mêmes.
- Deux tests du vrai source amont utilisaient un chemin accentué renvoyé par Git en UTF-8, décodé selon la locale Windows. Le helper décode désormais explicitement UTF-8.

La version applicative passe à **0.2.1** ; le tag 0.2.0 reste conservé. L'interface et les profils V20/V21 ne changent pas.

Contrôles locaux exécutés sur macOS ARM64 / Python 3.12.12 :

```text
FAT_TIA_UPSTREAM_SOURCE=<clone épinglé> .venv/bin/python -m pytest tests/test_distribution.py tests/test_tia_server_source.py
30 passed in 1.17s
```

Ruff et le build TypeScript/Vite passent aussi. Ces contrôles locaux ne remplacent pas la nouvelle exécution Windows ; son résultat reste à consulter séparément. Les preuves de référence du changement fonctionnel sont dans le [dossier V20/V21](../2026-11-02-v20-v21/VERIFICATION.md).

Fichiers : [JUnit ciblé](pytest-targeted.xml), [CI initiale](github-ci-initial.json). La compilation Siemens V20/V21, la restauration de l'archive et la qualification PLCSIM restent hors du périmètre de ces tests. Aucun serveur FAT persistant n'est laissé actif.
