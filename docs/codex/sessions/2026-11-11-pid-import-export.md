# Import et export P&ID locaux

11 novembre 2026, Windows 11 x64 / Python 3.12.10. Mandat utilisateur : intégrer PDF, DWG et formats utiles, utiliser le catalogue public, rester gratuit et créditer les dépôts utilisés dans le README et les notices. Travail dans `C:/FAT_Studio`, branche `codex/vanguard-fat-studio-brand`, HEAD `f5ad062cfc9babbd2ab61d22ee55528ad0fc7979`, sans commit, push ni publication.

## Résultat

**Échanges P&ID** fournit inspection locale, aperçu source, sélection/types/liaisons à revoir, préparation passive d’un nouveau projet et application explicite au brouillon. Enregistrer utilise le mécanisme existant et conserve l’ancien projet. Le document interprété reste dans `pid_document`, avec provenance, confiance, avertissements et aperçus, sans droit de cible ni données PLC inventées. La source se rouvre après rechargement.

Imports : PDF vectoriel/scanné, PNG/JPEG/TIFF/BMP/WebP, SVG, DXF, DWG via LibreDWG local, JSON natif et graphe Scott Duncan, GraphML, XML DEXPI/Proteus partiel, CSV/TSV et données natives draw.io/ZIP CSV. Dix exports : SVG, PDF, PNG, DXF, DWG R2000, JSON P&ID, JSON graphe, GraphML, CSV ZIP et draw.io. Les exports dessinent le projet actif, sans promettre une reproduction complète du fichier CAO source.

Catalogue de dix entrées adapté de Scott Duncan, liens externes sans récupération serveur automatique. Deux PDF testés localement depuis leurs sources : Pahala page 9, quatre objets proposés en 2,33 s ; Virden page 5 scannée, 27 objets proposés par OCR en 11,36 s. Aucune précision exhaustive ni topologie raster qualifiée. Les PDF et leurs données extraites restent privés dans `.local`, hors distribution.

Lecteurs et OCR gratuits, sans modèle hébergé ni clé API. LibreDWG 0.14 installé uniquement dans `.tools/pid-cad/`, archives binaire et source correspondante vérifiées ; version, commit, SHA-256 et GPL documentés. Les outils ne sont pas incorporés aux paquets FAT. Les références Scott Duncan, licences et modifications du catalogue sont dans README, guide et notices ; licence complète CC BY 4.0 conservée. Aucun code du convertisseur Claude amont n’est copié : interopérabilité de graphe et référence d’ontologie, lecteurs locaux indépendants.

## Fichiers et frontières

Nouveaux modules `fat_studio/pid_{models,import,ocr,export,cad,exchange,catalog,api,process,worker}.py`, licence du catalogue et six fichiers de tests `test_pid_*`. Adaptations ciblées de `app.py`, `models.py`, `assistant.py`. UI : nouveaux `PidExchange.tsx`, `pid-exchange.css` et `pid-exchange.spec.ts`, intégration dans App/api/types. Dépendances directes et transitives verrouillées, schémas JSON, politique publique explicite, guide `docs/PID_EXCHANGE.md`, README/notices/guides/changelog et bundle actualisés.

Le lecteur natif tourne dans un enfant borné à 90 s / 2 Gio, avec arrêt des descendants sous Windows et gestion de groupe Unix. La déconnexion HTTP annule la lecture. Les conversions CAO sont limitées à 30 s / 20 Mo. DTD/entités externes, formats/tailles/complexités excessives, références incohérentes et contextes périmés sont refusés. Une inspection ne tient pas le verrou FAT. La file frontend des commandes exclut les POST passifs ; la régression forçage/Stop pendant inspection a été reproduite puis corrigée. La sonde des outils CAO tourne hors boucle async.

Les modifications préexistantes ont été conservées. Checkpoint privé `.local/pid-exchange-2026-11-11/baseline/`, dont l’ancien bundle ; 47 fichiers de source hors périmètre restent identiques octet par octet. Journal spécifique `.dev-loop/pid-exchange-2026-11-11/logbook.md`, ancien journal intact. Aucune donnée d’essai utilisateur, CPU, instance de démonstration existante ou livraison à manifeste modifiée. Aucun verdict FAT humain créé.

## Vérifications réellement exécutées

- Dernière suite Python complète : **681 réussis, cinq ignorés**, 275,60 s, environnement `.local/dev-env.ps1` avec vrai clone TIA amont épinglé. Les cinq cas ignorés nécessitent le privilège Windows de création de liens symboliques ; les tests de jonctions restent exécutés. Première passe antérieure : 675 réussis / sept ignorés, conservée séparément, non additionnée au résultat final.
- Suite navigateur complète `npm test` : **68 réussis**, zéro échec/ignoré/flaky, 187,90 s, vrai backend temporaire sur loopback. Les huit nouveaux parcours couvrent sauvegarde/rechargement, erreurs, source persistée, révisions, revue et conflits, inspection en cours d’essai, commandes pendant inspection, clavier et écran étroit.
- TypeScript/Vite et `scripts/build-web.py` réussis. Bundle final `index-CzFbymNi.js` / `index-D0XwxBzv.css`. Captures desktop 1 120 px et mobile 390 px relues ; rendu PNG exporté relu. Ruff, `pip check`, politique publique et 59 liens documentaires locaux réussis.
- DWG réel R2000 / signature AC1015 : 62 entités DXF sur 62 et métadonnées natives conservées. Dix exports suivis de dix réimports conservent objets et connexions. Écriture LibreDWG expérimentale ; aucune qualification AutoCAD ou application CAO propriétaire.
- Wheel construite et contrôlée : SHA-256 `07d015cf14400b008d70b0d3519adc97ef470d072e8a524bade8dfd856413644`. Installée dans une venv séparée, lancée avec `-I` hors du checkout et service HTTP sur données temporaires : origine du paquet vérifiée, assets servis identiques, inspection/préparation passives et contexte inchangé, nouvelle sauvegarde préservant l’ancien projet, dix exports/réimports HTTP exacts, refus 409 et redémarrage avec source persistée réussis. Les dépendances sont réutilisées depuis la venv de développement via une `.pth` privée ; ce test ne qualifie pas Windows vierge.

Commandes : `. .local/dev-env.ps1`, `python -B -m pytest -q --tb=short`, `python -m ruff check fat_studio integrations tests scripts public_distribution.py build_public.py`, `python -m pip check`, `npm --prefix frontend run build`, `python scripts/build-web.py`, puis `npm test` depuis `frontend`, `python public_distribution.py check`, `python -m build --wheel --no-isolation`, et contrôle du wheel installé par helper privé. Toutes les suites navigateur utilisent des données temporaires et `FAT_E2E_BASE_URL` supprimé.

Reçus publics synthétiques dans `evidence/reprises/2026-11-11-pid-exchange/`. Logs complets, JUnit/Playwright, captures, PDF publics de test, helper et résultats du paquet installé dans `.local/pid-exchange-2026-11-11/`. Serveurs temporaires fermés.

## Reprise

Aucun blocage logiciel connu dans le périmètre testé. Relancer le serveur depuis cette copie source pour charger les nouvelles routes ; les anciens portables et kits scellés restent historiques. La compatibilité CAO propriétaire, les sous-ensembles XML, la fidélité d’extraction de grands plans et les plateformes autres que Windows ne sont pas qualifiées par cette campagne. Les objets inconnus, paramètres physiques et associations PLC restent à revoir et à renseigner. Aucun nouvel accès CPU n’est autorisé par cette livraison.

Pour reprendre : lire `README-CODEX.md`, `docs/codex/ETAT_REPRISE.md`, cette note, `docs/PID_EXCHANGE.md` et le journal spécifique entier, puis `git status --short`. Utiliser les commandes ci-dessus uniquement sur données temporaires. Aucun commit ou changement d’un kit à manifeste n’est implicite.
