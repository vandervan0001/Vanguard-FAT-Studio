# Aide des pupitres, 4 novembre 2026

Le P&ID affiche le mode et l’état à côté du sélecteur de scénario. `IoAccess.tsx` fournit le motif de verrouillage et la cible d’aide. Les commandes restent désactivées quand une écriture est interdite. L’aide peut être ouverte à la souris ou au clavier. Le pupitre distingue les contacts à reprendre et les forçages analogiques disponibles en pause.

Modifications dans `App.tsx`, `PidCanvas.tsx`, `TestConsole.tsx`, `ForceField.tsx`, `Panels.tsx`, les styles et le guide. Le bundle livré est `index-CttV4vd8.js` et `index-Bf7P50aB.css`. Le travail initial sur `codex/vanguard-fat-studio-brand` part de `f5ad062`. Les notes et le brouillon Windows préexistants sont conservés.

Le test ciblé a d’abord reproduit l’absence d’indication sur l’ancien bundle. Après correction, le clic TOR et analogique bloqué montre l’aide sans requête de forçage. Le même test vérifie les trois modes affichés, le maintien TOR en cours, l’aide clavier en pause et l’écriture analogique en pause. `npm run typecheck`, `npm run build` et `python scripts/build-web.py` ont réussi. `npm test` a réussi les 57 cas sur données temporaires. Les captures de 1440 et 768 pixels ont été relues.

Le serveur de démo 8777 répond avec les deux nouveaux fichiers du bundle. Le contrôle était en lecture seule. Pour reprendre, ouvrir `http://127.0.0.1:8777` et recharger la page après avoir enregistré un éventuel brouillon. Les preuves sont dans `.local/io-guidance-2026-11-04/`.

Reprise Git du 4 novembre. Le diff utile a été isolé dans `.local/io-guidance-2026-11-04/git-source` sur `codex/io-guidance`, depuis `origin/main` au commit `40323f6`. Les trois fichiers du bundle indexés correspondent aux empreintes du reçu de la suite locale. Le filtre public et `git diff --cached --check` ont passé. Commit `9f634f769dbbdc2157a3f5f012aed640f649883d` poussé et [PR brouillon n° 2](https://github.com/vandervan0001/Vanguard-FAT-Studio/pull/2) ouverte. Les jobs Windows et Ubuntu étaient en file d’attente lors de la vérification. Pour reprendre cette revue, utiliser `gh pr checks 2 --repo vandervan0001/Vanguard-FAT-Studio`.

Fusion du 4 novembre. La [CI n° 41862879239](https://github.com/vandervan0001/Vanguard-FAT-Studio/actions/runs/41862879239) a réussi sur Windows et Ubuntu pour `9f634f7`. Après vérification du commit et de la cible, la PR a été fusionnée dans `main` au commit `6d822c135f11e4c6ba21be13debe19f165a580c4`. L’arbre distant de `main` est identique à celui du commit testé. Reçu local dans `.local/io-guidance-2026-11-04/github-merge.json`.
