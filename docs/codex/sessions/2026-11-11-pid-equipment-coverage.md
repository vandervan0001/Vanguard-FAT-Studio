# Bibliothèque P&ID et portée réelle des essais

11 novembre 2026, Windows 11 x64 / Python 3.12.10. Suite aux questions sur l’exhaustivité des chemins et les échangeurs/vannes trois voies. Source `C:/FAT_Studio`, branche `codex/vanguard-fat-studio-brand`, HEAD `f5ad062cfc9babbd2ab61d22ee55528ad0fc7979`, modifications préexistantes conservées, aucun commit/push/publication. Checkpoint privé `.local/pid-equipment-2026-11-11/baseline/`.

## Changements

41 familles documentaires originales dans `pid_symbols.py`, avec ports et primitives inertes : échangeurs quatre piquages, vannes trois/quatre voies, organes manuels, clapets, filtres, pompes spécialisées, compresseurs, réacteurs, etc. Le modèle `pid_symbol` conserve `symbol_kind`, `source_kind` et une rotation orthogonale. Les connexions stockent `source_port` et `target_port`, distincts des associations PLC. Les objets inconnus restent génériques, sans conversion en indicateur. Les neuf types historiques du banc sont conservés. Aucune nouvelle physique thermique ou hydraulique n’est revendiquée ; la préférence utilisateur sur cette profondeur reste ouverte.

La palette, la revue d’import, l’inspecteur, les exports et la restauration native utilisent cette bibliothèque. La rotation conserve les coordonnées des bornes ; les piquages non localisés sont signalés sans effacement de leur identifiant. Les objets documentaires affichent « Non simulé » et ne publient aucune fausse mesure zéro ou qualité saine. Un projet documentaire sans variable s’enregistre et s’exporte mais ne démarre pas une FAT vide.

PDF dense : dépassement de géométrie conserve aperçu/texte et écarte les liaisons de la page incomplète avec avertissement ; la borne n’est pas désactivée. Cartouches, fichiers et références réglementaires filtrés pour ne pas devenir des pompes. AT reste ambigu dans le texte/OCR. Les classes spécialisées sont préservées au lieu d’être ramenées à une cuve ou vanne générique. L’ellipse verticale de l’export CAO a été corrigée avec un axe majeur et un ratio valides.

Principaux fichiers : `pid_symbols.py`, `pid_ports.py`, modèles/catalogue/moteur, modules d’import/préparation/export/API ; `PidCanvas.tsx`, `PidExchange.tsx`, `PidSymbolSvg.tsx`, types et CSS ; schémas JSON, politique publique, tests P&ID, README/changelog et `docs/PID_COVERAGE.md`. Aucun adaptateur PLC modifié.

## Preuves et limites

- **764 tests Python réussis, cinq ignorés**, 264,44 s selon la sortie pytest. Les cinq cas exigent le privilège Windows de liens symboliques ; les jonctions sont testées. Vrai clone amont TIA épinglé pour les vérifications de source, aucune communication Siemens.
- **71 tests navigateur réussis**, zéro échec/ignoré/flaky, 221,80 s. Les trois nouveaux parcours complètent les huit parcours P&ID et les autres fonctions du banc. Typecheck/build/copieur de bundle, Ruff, pip check et sélection publique réussis. JS `index-40v7MTO4.js`, CSS `index-DWY2VCnU.css`.
- 41 symboles/rotations et onze connexions à piquages conservés sur dix formats. Après suppression du JSON natif, les DXF et vrais DWG R2000 conservent les textes, calques et coordonnées des onze raccordements. Ce contrôle est distinct de la restauration native : un dessin effacé peut encore relire son JSON incorporé, ce qui ne mesure pas l’extraction d’un plan externe.
- Wheel finale SHA-256 `5796a038b502247b606bc75344c611b8456363347607bc6fc6a06ddcdcef8396`. Installation séparée sous `-I`, HTTP loopback temporaire : 66 fichiers installés égaux au wheel, 60 fichiers produit égaux aux sources, 33 modules chargés depuis le paquet. Dix formats relus/repréparés exactement sur 42 objets et 41 connexions, types/ports/rotations/source conservés, contextes et ancien projet intacts ; redémarrage et refus de démarrage sans variables confirmés. Dépendances réutilisées par `.pth` privée, pas de qualification Windows vierge. Le second contrôle du wheel final dure 18,362 s ; les résultats des deux phases ne sont pas additionnés.
- Captures desktop relues. Le cadrage de la palette à 390 px et les débordements globaux préexistants ne permettent pas de revendiquer une qualification mobile générale. Aucun logiciel CAO propriétaire, autre OS, précision exhaustive d’OCR ou tous les chemins d’entrée qualifiés.

Les vrais Pahala 10/16 restent partiellement reconnus : le traitement conserve maintenant le dessin au lieu d’échouer et ne fait plus passer les références de plan pour des pompes. Le [document de couverture](../../PID_COVERAGE.md) précise les limites. Les anciens reçus 681/68 restent historiques.

## Démonstration réelle demandée précédemment

Le serveur source a été relancé sur `http://127.0.0.1:8765` après vérification de sa seule instance et de son état idle/déconnecté. Dossier dédié `.local/pid-catalogue-demo-2026-11-11/data/`, processus courant dans `server.json`. Aucun service ancien, donnée d’essai utilisateur ou kit à manifeste modifié.

Import réel de Virden page 14, dessin D-016-0 « PROCESS / ALUM / P&ID ». OCR : 35 candidats et zéro liaison. Huit repères vérifiés sur la source ont été retenus et typés explicitement comme symboles documentaires : deux cuves AT, deux pompes doseuses ASP, deux vannes BAV et deux clapets CHV. Quatre liaisons simples ont été tracées à la revue visuelle puis la disposition réorganisée. Les avertissements et le reçu distinguent ces liaisons du résultat OCR ; aucune conversion automatique complète n’est prétendue.

PDF, DWG R2000 réel, PNG et JSON dans `.local/pid-catalogue-demo-2026-11-11/exports/`, préfixe `Virden-Alum-page14-revue`. Les huit libellés ont été vérifiés dans le texte PDF et les entités DWG. L’état reste idle, déconnecté, sans essai, tag ni écriture PLC ; ancien laboratoire conservé. Le premier contrôle privé attendait à tort stopped après sauvegarde ; lecture corrigée vers idle, sans rejouer import/sauvegarde/export. Le PDF a été proposé au panneau de fichiers Codex ; aucun pilotage Chrome repris après l’arrêt CUA du tour précédent.

## Reprise

Aucun blocage logiciel connu dans le périmètre exécuté. La profondeur de simulation des nouvelles familles reste à définir ; ne pas les présenter comme des modèles physiques. Le serveur de démonstration reste disponible, avec son projet documentaire. Aucune autorisation CPU ou observation FAT humaine n’est déduite.

Relire README-CODEX, ETAT_REPRISE, cette note, `docs/PID_COVERAGE.md` et le journal entier `.dev-loop/pid-equipment-2026-11-11/logbook.md`. Preuves publiques synthétiques : `evidence/reprises/2026-11-11-pid-equipment/`. Logs, JUnit/Playwright, matrice détaillée, snapshots et helpers dans `.local/pid-equipment-2026-11-11/` ; scans et résultats réels privés dans `.local/pid-catalogue-demo-2026-11-11/`.

Commandes : `. .local/dev-env.ps1`, `.venv/Scripts/python.exe -B -m pytest -q --tb=short`, Ruff sur fat_studio/integrations/tests/scripts, `pip check`, `npm --prefix frontend run build`, `python scripts/build-web.py`, `npm test` depuis frontend sans FAT_E2E_BASE_URL, `python public_distribution.py check` et `check-wheel`. Les suites navigateur utilisent seulement leurs données temporaires, jamais le serveur de démonstration 8765.
