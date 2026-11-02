# Vérification exécutée — FAT Studio 0.1.1

Date : **2 novembre 2026**. Cette livraison corrige `v0.1.0` (`c18e0d4`) après revue de code, reproductions adverses et relecture croisée. Le détail se trouve dans [ADVERSARIAL_REVIEW.md](../docs/ADVERSARIAL_REVIEW.md). Les résultats ci-dessous proviennent d'exécutions réelles ; ils ne constituent pas une qualification Windows, TIA Portal ou PLCSIM Advanced.

## Résultats

| Vérification | Résultat constaté | Preuve |
| --- | --- | --- |
| Suite Python complète | **289 réussis**, 0 échec, 0 erreur, 0 ignoré ; **128,394 s** | [pytest.xml](pytest.xml) |
| Interface et API cliente | **31 réussis**, 0 échec, 0 instable, 0 ignoré ; **44,440 s** | [frontend-tests.json](frontend-tests.json) |
| Construction web | TypeScript strict et Vite terminés ; un JS, un CSS et notices dans le paquet | Assets dans `fat_studio/web/`, empreintes dans les preuves frontend et wheel |
| Analyse statique | Ruff sans erreur sur `fat_studio integrations tests scripts` ; syntaxe Bash valide | Commandes ci-dessous |
| Scénarios de démonstration | 3 exécutions, **12 assertions réussies** ; verdict humain non évalué | [demo-scenarios.json](demo-scenarios.json) |
| Premier lancement hors ligne | Nouveau dossier avec espaces/accents, nouvelle `.venv`, **28 wheels Linux**, index et cache pip désactivés | [linux-clean-install.json](linux-clean-install.json), [journal d'installation](linux-clean-install-log.txt) |
| Wheel finale | Installation dans une seconde `.venv` neuve, sans index ; import et service hors des sources | [packaged-wheel.json](packaged-wheel.json) |
| Dépendances Windows | **29 wheels**, tags CPython 3.12 x64 compatibles, 33 contraintes transitives vérifiées | [windows-wheels.json](windows-wheels.json) |
| Charge modèle et stockage | **50 équipements, 200 tags, 1 000 cycles**, après 50 cycles de préchauffage | [benchmark.json](benchmark.json) |

Environnement : Linux x86_64, Python **3.12.14**, SQLite **3.53.1**, Node.js **24.22.1**, Chromium **141** via Playwright **1.56.1**. Les dépendances sont verrouillées dans `requirements*.lock` et `frontend/package-lock.json`. Par rapport à 0.1.0 : **80 tests Python et 19 tests frontend supplémentaires**. Leur nombre ne constitue pas une mesure de couverture exhaustive.

## Suite Python

| Module | Tests | Périmètre exercé |
| --- | ---: | --- |
| `test_models` | 45 | Types, valeurs finies, associations, paramètres, ordonnancement et scénarios |
| `test_engine` | 28 | Bilan de volume, circuits, vannes, pompe, instruments, forçages et défauts |
| `test_runtime` | 21 | Cycle, pause/reprise, arrêt/reset, journal et erreurs d'échange/stockage |
| `test_api` | 23 | Projets, mapping, session locale, exports, récupération et concurrence |
| `test_opcua` | 30 | Échanges locaux réels, droits/types, namespace, écritures partielles, identité et certificats |
| `test_security` | 43 | Politique du poste, cible, certificats, secrets et absence d'autoautorisation |
| `test_cli` | 16 | Diagnostic et autorisation explicite de cible |
| `test_engineering` | 24 | Contrats MCP, sandbox, audit, export/diff, confirmation, archive, pagination et compilation |
| `test_adverse_backend` | 21 | Ancien essai, transaction du verdict, pannes de journal, annulations, sauvegardes et CSV |
| `test_adverse_process` | 22 | Float32, bornes, domaines capteurs, calcul atomique et contrôle de démonstration |
| `test_distribution` | 16 | Plateforme Python, manifeste, BOM, chemins, doublons, corruption et wheels |

Les tests OPC UA utilisent de véritables connexions `asyncua` sur localhost, dont `Basic256Sha256 / SignAndEncrypt`. L'identité entre `CreateSession` et `ActivateSession` est exercée avec un serveur TLS instrumenté ; les certificats expirés, pas encore valides ou incohérents avec l'ApplicationUri sont refusés. Aucun automate Siemens ne participe à ces tests.

Le volet ingénierie suit le contrat **Czarnak v4.3.0**, lu dans sa révision épinglée. Un test exerce réellement le transport stdio du SDK MCP. Les opérations TIA et les compilations utilisent des doubles : une réponse malformée injectée ne démontre pas que le serveur amont conforme la produit.

Les échecs SQLite et annulations asyncio sont injectés de façon contrôlée. Ils ne constituent pas des essais physiques de panne de disque ou de coupure électrique.

## Interface compilée

La suite finale utilise le vrai serveur FastAPI, SQLite et les **assets précompilés**, sans serveur Vite. Elle comprend **24 parcours navigateur** (`workbench` : 6 ; `adversarial` : 18) et **7 tests TypeScript** du client API et du format de scénario.

Les parcours vérifient la création/import/export d'un projet, le glisser-déposer et les connexions réels du P&ID, sa persistance, les scénarios et défauts, le forçage, les conclusions et les exports. Les nouveaux essais ciblent aussi les conclusions pendant une sauvegarde lente, les actions d'un ancien essai, les conflits entre onglets, les réponses de polling tardives, les coupures/délais réseau, les brouillons JSON incomplets, les associations incompatibles, le forçage vide et les états des symboles.

Le MODE FAT et les commandes ont été inspectés à **768 × 1024** et **1024 × 768**, sans dépassement horizontal dans les états testés. Les captures sont des artefacts d'inspection, pas des preuves FAT utilisateur. Aucun résultat Firefox, Safari, lecteur d'écran ou téléphone n'est revendiqué ; l'interface conserve une largeur minimale de 760 pixels. L'avertissement Vite sur la taille du bundle reste non bloquant et ne vaut pas mesure de performance.

## Démonstration

| Scénario | Durée simulée | Assertions | Observation |
| --- | ---: | ---: | --- |
| Cycle de référence | 32 s | 4/4 | Remplissage, seuil de commande, arrêt et soutirage |
| Défaut moteur | 28 s | 5/5 | Retour marche perdu, défaut transmis, arrêt du remplissage et reprise |
| Capteur de niveau figé | 24 s | 3/3 | Mesure à 40 %, volume continuant d'évoluer, puis retour de la mesure |

Ces résultats ont été régénérés avec les tags REAL quantifiés en Float32. [reference-report.html](../examples/reference-report.html) et [reference.csv](../examples/reference.csv) sont de vrais exports du même moteur. Le verdict utilisateur reste **non évalué** : aucune validation humaine n'est attribuée automatiquement.

## Première installation et paquet final

### Sources et lanceur

Une copie des sources et assets a été placée dans un dossier neuf avec espaces/accents, les 28 wheels Linux requises et un manifeste UTF-8 avec BOM. Sans `.venv` préexistante, **`scripts/start.sh` a réellement créé l'environnement et installé les versions verrouillées, puis le paquet**. L'environnement imposait `PIP_NO_INDEX=1`, une URL d'index inutilisable et `PIP_NO_CACHE_DIR=1`. Le journal montre la recherche dans le répertoire de wheels ; aucun index pip n'a été utilisé. `pip check` et `doctor` ont réussi.

Ensuite, `scripts/smoke-installed.py` a lancé le Python installé depuis un autre répertoire, sans `PYTHONPATH`, et vérifié :

1. Santé du service, HTML, JavaScript et CSS locaux.
2. Projet de démonstration à huit équipements et treize tags.
3. Démarrage, pause, marqueur et verdict explicitement non évalué.
4. Exports CSV, HTML et JSON cohérents, avec quatre échantillons.
5. Arrêt et reset préservant les preuves de l'essai archivé.
6. Nouveau processus sur les mêmes données : historique retrouvé et état inactif.

### Wheel finale

`local_fat_studio-0.1.1-py3-none-any.whl` a été installée dans **une deuxième `.venv` vierge**, avec les mêmes restrictions d'index/cache. Le contrôle HTTP et de persistance a réussi hors des sources. L'import provient bien de `site-packages`. Les fichiers Python et web de la wheel ont été comparés octet par octet aux sources livrées ; les licences HistorianSim et notices web sont présentes.

SHA-256 de la wheel exécutée :

```text
d1b8e8db0cd4bed83a17b5fa971d44750614b6a2f30a76ef50c776be8f692567
```

Les 29 wheels Windows sont les fichiers vérifiés pour 0.1.0 : le verrou runtime n'a pas changé. Leurs empreintes sont recontrôlées à l'assemblage 0.1.1. Elles ont été téléchargées et inspectées pour CPython 3.12 Windows x64 **sur Linux** ; ni leur code Windows ni PowerShell ne sont exécutés ici. Python, Siemens, .NET et le serveur MCP optionnel ne sont pas inclus dans le kit.

## Performance mesurée

Dix cuves et quarante vannes modulantes représentent 50 équipements et 200 tags tous associés. Le pas simulé est 100 ms. SQLite utilise WAL, `synchronous=FULL` et un commit réel par échantillon.

| Partie mesurée | Médiane | 95e percentile | Maximum |
| --- | ---: | ---: | ---: |
| Modèle seul | 0,420 ms | 0,728 ms | 3,465 ms |
| SQLite seul | 0,366 ms | 0,843 ms | 4,762 ms |
| Modèle + SQLite | 0,918 ms | **1,315 ms** | 7,568 ms |

Ces mesures excluent OPC UA, PLCSIM, réseau, ordonnancement complet et navigateur. Elles ne constituent ni une garantie temps réel ni un essai d'endurance sur le poste cible. Les événements d'un rapport sont encore chargés en mémoire ; les échantillons sont parcourus progressivement.

## Reproduire les contrôles

Après installation des dépendances de développement et d'ingénierie verrouillées :

```bash
python -m pytest --junitxml=evidence/pytest.xml
python -m ruff check fat_studio integrations tests scripts
python scripts/generate-examples.py
python scripts/benchmark.py --output evidence/benchmark.json
```

Construire puis copier les assets **avant** les tests navigateur :

```bash
cd frontend
npm ci
npm run build
cd ..
python scripts/build-web.py
cd frontend
npx playwright install chromium
npm test
cd ..
python -m build --wheel --no-isolation
python -m fat_studio doctor --json
```

Pour vérifier une installation distincte, donner le chemin absolu de son Python sans résoudre son lien symbolique vers l'interpréteur de base :

```bash
python scripts/smoke-installed.py --python /chemin/installation/.venv/bin/python \
  --output evidence/installed-check.json
```

La [CI fournie](../.github/workflows/ci.yml) prévoit Windows et Ubuntu. Sa branche Windows prépare un kit neuf, interdit les index pip, exécute `setup.ps1` et teste le service installé hors des sources. **Aucun run distant GitHub Actions n'a été exécuté pour cette livraison.** Le dépôt et son historique Git sont livrés localement ; l'authentification GitHub via Google a été refusée pour ce navigateur non reconnu.

## Qualification restante

À exécuter sur le poste de destination, sans remplacer ces observations par les succès locaux :

- premier lancement Windows, kit hors ligne, scripts PowerShell et verrou de dossier Windows ;
- versions exactes de Windows, TIA, Openness, CPU, firmware, PLCSIM Advanced et serveur OPC UA ;
- isolation réseau, identité/certificat, NodeIds, namespaces, droits et types réels ;
- compilation SCL, raccordement au programme PLC et observation de ses consommateurs ;
- scénarios métier, perte de communication, conditions initiales et répétabilité du programme réel ;
- option Czarnak 4.3.0 : export/import, compilation et restauration réelle d'une archive TIA ;
- charge complète avec Siemens et navigateur, endurance et disque cible ;
- réception métier et verdict humain selon [ACCEPTANCE.md](../docs/ACCEPTANCE.md).

La [matrice d'exigences](../docs/REQUIREMENTS_MATRIX.md) distingue implémentation, preuves locales et qualification restante pour 39 exigences fonctionnelles, 14 non fonctionnelles et 14 critères d'acceptation. La 0.1.1 est vérifiée pour le périmètre exécuté décrit ici ; aucune FAT Siemens déjà reçue n'est déclarée.
