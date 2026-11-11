# Vérification des échanges P&ID

11 novembre 2026, Windows 11 x64, Python 3.12.10, HEAD `f5ad062cfc9babbd2ab61d22ee55528ad0fc7979` avec modifications de travail. Les changements préexistants sont conservés. [Reçu synthétique](verification.json).

- Suite Python complète : **681 réussis, cinq ignorés**, zéro échec/erreur, 275,60 s. Les cinq cas demandent le privilège Windows de création de liens symboliques ; contrôles de jonctions exécutés. Vrai clone du serveur TIA épinglé utilisé pour ses tests de source, sans communication Siemens.
- Suite navigateur complète `npm test` : **68 réussis**, zéro échec/ignoré/flaky, 187,90 s. Backend local et données temporaires. Huit nouveaux parcours P&ID, dont un forçage et l’arrêt pendant une inspection retardée.
- TypeScript/Vite, copie `scripts/build-web.py`, Ruff, `pip check`, sélection publique et 59 liens documentaires locaux réussis. Captures desktop/mobile et PNG exporté relus.
- Dix formats exportés puis réimportés : équipements et connexions conservés. DWG R2000 / AC1015 réel avec GNU LibreDWG 0.14 : 62 entités sur 62 conservées. L’écriture est expérimentale ; aucune qualification dans un logiciel CAO propriétaire.
- Deux fichiers du catalogue, récupérés depuis leurs sources publiques et gardés hors distribution : Pahala, page 9 numérique, quatre objets proposés ; Virden, page 5 scannée avec OCR CPU, 27 objets proposés. Ces nombres ne mesurent pas une précision d’extraction. Aucun lien raster inventé.
- Wheel construite, contrôlée et installée dans une venv séparée, exécutée avec `-I` hors sources : 64 fichiers installés identiques au wheel, 58 fichiers produit identiques au checkout, bundle servi par HTTP identique. Inspection/préparation passives, contexte inchangé, ancienne sauvegarde conservée, dix exports/réimports HTTP exacts, refus des révisions périmées et redémarrage avec source persistée réussis. Dépendances réutilisées via une `.pth` privée ; Windows vierge non qualifié.

Wheel SHA-256 : `07d015cf14400b008d70b0d3519adc97ef470d072e8a524bade8dfd856413644`. Bundle : `index-CzFbymNi.js` et `index-D0XwxBzv.css`.

Commandes principales depuis la source : `. .local/dev-env.ps1`, `python -B -m pytest -q --tb=short`, `python -m ruff check fat_studio integrations tests scripts public_distribution.py build_public.py`, `python -m pip check`, `npm --prefix frontend run build`, `python scripts/build-web.py`, `npm test` depuis `frontend`, `python public_distribution.py check`, `python -m build --wheel --no-isolation`, puis `python public_distribution.py check-wheel` sur le fichier construit. Les contrôles HTTP installés utilisent un helper privé et des données temporaires.

Les formats sont détaillés dans le [guide P&ID](../../../docs/PID_EXCHANGE.md). Les lecteurs fournissent des propositions à revoir ; paramètres physiques, associations PLC et conclusion FAT restent séparés. Aucun accès PLC, observation ou verdict FAT humain, publication ou modification des anciens kits à manifeste pendant ce chantier. Les logs complets, sources publiques de test, captures et reçus détaillés restent dans le dossier privé `.local/pid-exchange-2026-11-11/`.
