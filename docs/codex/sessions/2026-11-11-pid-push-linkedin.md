# Push public et préparation LinkedIn, 11 novembre 2026

Demande explicite : pousser les changements, documenter le travail et préparer le prochain post avec captures et PDF. Branche conservée : `codex/vanguard-fat-studio-brand`, remote `origin` du dépôt Vanguard-FAT-Studio. Aucun merge sur main ni publication LinkedIn demandés.

Le périmètre Git est la sélection publique des sources et médias, avec suppression des deux anciens assets remplacés. Les données, journaux privés, kits et fichiers non sélectionnés sont conservés localement. La modification de `docs/WINDOWS_LOCAL_SETUP.md` pointe sur un chantier privé et reste exclue du commit. Les autres notes locales non sélectionnées restent hors Git.

Le dossier [LinkedIn](../../../media/linkedin/2026-11-11-pid/README.md) contient le texte prêt à copier, trois captures réelles de l'application, deux vues de plans et un détail du cartouche, un PDF de présentation de quatre pages, les deux plans PDF/DWG/DXF et les licences/polices. Les prises sont effectuées sur le seul serveur de démonstration 8765 au repos ; navigation et aperçu passif, sans enregistrement ni PLC. Rendus et pages PDF inspectés, manifeste SHA-256 et archive ZIP contrôlés. Aucune publication sociale effectuée.

Sources applicatives et bundle inchangés depuis les résultats de la [validation précédente](../../../evidence/reprises/2026-11-11-pid-conventions/VERIFICATION.md) : 1 150 Python réussis / cinq ignorés Windows, 79 navigateur réussis, paquet installé contrôlé. Aucune nouvelle exécution de ces suites pour ce travail documentaire et média. Contrôles nouveaux : captures réelles sans erreur JavaScript, rendu PDF quatre pages, copies des plans et ZIP par empreintes, sélection publique, liens, voix et diff. Les dépendances et standards ne sont pas réévalués dans cette phase.

Le commit regroupe les imports/exports P&ID, modèles et bibliothèque, feuilles compactes/services, documentation/licences/preuves et pack LinkedIn. Message et liste exacte des chemins conservés dans `.local/pid-linkedin-2026-11-11/`. Le reçu local `push-receipt.json` sera écrit après vérification du SHA distant, pour éviter d'annoncer un push sur la seule base d'une tentative. Aucun secret dans les reçus publics. La CI distante n'est pas présentée comme exécutée par la validation locale.

Reprise : vérifier `git status`, `git log -1` et `git ls-remote --heads origin codex/vanguard-fat-studio-brand`. Le prochain acte éditorial est la publication humaine du post et du document choisis. Le logiciel conserve ses limites de reconnaissance des plans, de conformité normative et d'acceptation CAO destinataire.

Premier commit refusé faute d'identité Git configurée ; aucun commit créé lors de cette tentative. L'historique du dépôt emploie Codex avec codex@localhost pour les trois derniers commits. Cette identité d'agent est reprise uniquement par options de commande pour le commit présent, sans changer la configuration globale.
