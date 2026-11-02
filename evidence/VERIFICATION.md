# Vérification exécutée — FAT Studio 0.1.0

Date : **2 novembre 2026**. Les résultats ci-dessous décrivent des exécutions réelles dans l'environnement de réalisation. Ils ne constituent pas une qualification de TIA Portal ou de PLCSIM Advanced sur le poste de destination.

## Résultat

| Vérification | Résultat constaté | Preuve |
| --- | --- | --- |
| Suite Python complète | **209 réussis**, 0 échec, 0 erreur, 0 ignoré ; 69,871 s | [pytest.xml](pytest.xml) |
| Interface et API cliente | **12 réussis**, 0 échec, 0 instable, 0 ignoré ; 10,138 s | [frontend-tests.json](frontend-tests.json) |
| Construction web | TypeScript strict et Vite terminés ; un JS et un CSS dans le paquet final | Interface dans `fat_studio/web/` |
| Analyse statique | Ruff sans erreur sur `fat_studio integrations tests` | Commande reproductible ci-dessous |
| Scénarios de démonstration | 3 exécutions, **12 assertions réussies** | [demo-scenarios.json](demo-scenarios.json) |
| Distribution Python | Wheel construite, installée hors du dépôt et exécutée | [packaged-wheel.json](packaged-wheel.json) |
| Dépendances Windows | 29 wheels disponibles, tags CPython 3.12 x64 compatibles, 33 contraintes transitives vérifiées | [windows-wheels.json](windows-wheels.json) |
| Charge du modèle et du stockage | 50 équipements, 200 tags, 1 000 cycles mesurés | [benchmark.json](benchmark.json) |

Environnement exécuté : Linux x86_64, Python 3.12.14, SQLite 3.53.1, Node.js 24.22.1 et Chromium 141 via Playwright 1.56.1. Les versions Python et JavaScript sont verrouillées par les fichiers `requirements*.lock` et `frontend/package-lock.json`.

## Ce qui a été testé

### Suite Python

| Module | Tests | Périmètre |
| --- | ---: | --- |
| `test_models` | 45 | Types, valeurs finies, associations, paramètres, ordonnancement et validation des scénarios |
| `test_engine` | 28 | Bilan de volume, groupes de débits, vannes, pompe, instruments, forçages et défauts |
| `test_runtime` | 21 | Cycle, pause/reprise, arrêt, reset, journal, erreurs de communication et de stockage |
| `test_api` | 23 | Projets, mapping, session locale, exports, limites de requêtes, récupération et concurrence entre onglets |
| `test_opcua` | 17 | Serveur OPC UA local réel, types et droits, namespace, écritures partielles, perte de communication et session chiffrée |
| `test_security` | 43 | Politique du poste, cible autorisée, identité serveur, certificats, secrets et refus d'autoautorisation par un projet |
| `test_cli` | 16 | Diagnostic, configuration locale et confirmation de la cible |
| `test_engineering` | 16 | Lecture seule MCP, copie sandbox, diff, empreintes, confirmation, archive, import et compilation simulés au niveau du contrat |

Les tests OPC UA utilisent de véritables échanges avec un serveur `asyncua` sur la boucle locale, y compris une connexion `Basic256Sha256 / SignAndEncrypt`. Ils ne font pas fonctionner un automate Siemens. Le volet d'ingénierie comporte un échange stdio réel avec le SDK MCP ; TIA Portal et son compilateur ne sont pas exécutés.

La revue a notamment reproduit puis corrigé : export dont les métadonnées et les échantillons n'étaient pas cohérents, reprise d'un flux SQLite sur un autre thread, conflits entre onglets sur le même identifiant projet, validation NaN/Infinity, pointeur de projet corrompu, conservation de la sauvegarde précédente et arrêt du runtime lorsque le journal ne peut plus être écrit.

### Interface

Six parcours navigateur couvrent :

1. Modification du P&ID, sauvegarde et rechargement.
2. Essai avec le backend réel : défaut moteur, forçage/libération, pause/reprise, arrêt, marqueur, verdict et exports.
3. Rejet puis correction d'un scénario invalide.
4. Import invalide sans perte du projet actif.
5. Changement de projet dans un autre onglet et conservation du brouillon local.
6. Conflit sur le même identifiant projet, contrôle de révision, refus HTTP 409 et absence d'écrasement.

Six autres tests vérifient les formats de scénario, les erreurs de l'API et le renouvellement de session. Le backend des parcours utilise un dossier temporaire et une base SQLite réelle. Les captures ont été inspectées pendant la réalisation ; elles ne font pas partie des preuves FAT de l'utilisateur.

### Démonstration exécutée

| Scénario | Durée simulée | Assertions | Observation |
| --- | ---: | ---: | --- |
| Cycle de référence | 32 s | 4/4 | Remplissage, seuil de commande, arrêt et soutirage |
| Défaut moteur | 28 s | 5/5 | Retour marche perdu, défaut transmis, arrêt du remplissage et reprise |
| Capteur de niveau figé | 24 s | 3/3 | Mesure bloquée à 40 %, volume continuant d'évoluer, puis retour de la mesure |

Les résultats sont générés par `scripts/generate-examples.py`, à partir du même moteur que l'application. [reference-report.html](../examples/reference-report.html) et [reference.csv](../examples/reference.csv) sont des exports effectivement produits. Le verdict utilisateur reste **non évalué** : aucune signature FAT humaine n'a été inventée.

### Vérification du paquet

La wheel finale a été installée avec `pip --no-index --no-deps --target` dans un répertoire distinct. L'import a été vérifié depuis un répertoire extérieur au dépôt, afin de ne pas servir accidentellement le code source.

Ont ensuite réussi : le diagnostic `doctor`, le chargement HTTP de l'HTML et des bundles JS/CSS, le projet à huit équipements et treize tags, le démarrage et la pause d'un essai, quatre échantillons persistés, l'export JSON cohérent, les exports HTML/CSV et l'arrêt. Les licences vendorisées et les notices web sont présentes dans la wheel. Son SHA-256 est enregistré dans `packaged-wheel.json`.

Les 29 dépendances Windows ont été téléchargées et inspectées sur Linux pour CPython 3.12 Windows x64. Les tags de wheels, les versions de chaque dépendance du verrou et les contraintes `Requires-Dist` avec marqueurs Windows ont été contrôlés. Cette vérification ne fait pas exécuter de code Windows. Le kit ne contient ni l'interpréteur Python, ni Siemens, ni le serveur MCP optionnel.

## Mesure de performance

Le benchmark comporte dix cuves et quarante vannes modulantes, soit 50 équipements et 200 tags tous associés. Après 50 cycles de préchauffage, 1 000 cycles sont mesurés avec un pas simulé de 100 ms. Le stockage utilise WAL, `synchronous=FULL` et un commit réel par échantillon.

| Partie mesurée | Médiane | 95e percentile | Maximum |
| --- | ---: | ---: | ---: |
| Modèle seul | 0,216 ms | 0,305 ms | 1,417 ms |
| SQLite seul | 0,299 ms | 0,627 ms | 3,108 ms |
| Modèle + SQLite | 0,666 ms | **1,045 ms** | 4,293 ms |

Ces durées excluent OPC UA, PLCSIM, l'ordonnancement complet, le réseau et le navigateur. Elles indiquent le coût du calcul et du journal dans cet environnement ; elles ne garantissent pas un délai temps réel sur le poste Windows. La mesure doit être répétée sur le matériel et le disque de destination.

## Commandes reproductibles

Après installation des dépendances de développement et d'ingénierie verrouillées :

```bash
python -m pytest --junitxml=evidence/pytest.xml
python -m ruff check fat_studio integrations tests
python scripts/generate-examples.py
python scripts/benchmark.py --output evidence/benchmark.json
```

Pour l'interface, depuis `frontend/` :

```bash
npm ci
npm run build
npx playwright install chromium
npm test
```

Puis, à la racine :

```bash
python scripts/build-web.py
python -m build --wheel --no-isolation
python -m fat_studio doctor --json
```

La CI livrée prévoit Windows et Ubuntu. **Aucune exécution distante GitHub Actions n'est annoncée comme réussie dans cette livraison.**

## Qualification restante sur le poste cible

Les éléments suivants demandent l'environnement Windows/Siemens de destination :

- Exécution effective des lanceurs PowerShell et du kit hors ligne ; test du verrou de dossier Windows.
- Compatibilité exacte Windows, TIA, Openness, CPU, firmware, serveur OPC UA et PLCSIM Advanced.
- Isolation réseau réelle de l'instance, identité et certificat observés, NodeIds, droits et types exposés.
- Compilation des sources SCL et raccordement au programme PLC existant.
- Perte de communication et répétabilité avec le véritable programme Siemens ; préparation de son état initial.
- Installation et qualification de `TiaMcpServer 4.3.0`, export/import et compilation via Openness dans une copie TIA.
- Acceptation métier et verdict humain, selon [ACCEPTANCE](../docs/ACCEPTANCE.md).

La matrice [REQUIREMENTS_MATRIX](../docs/REQUIREMENTS_MATRIX.md) couvre les 39 exigences fonctionnelles, les 14 exigences non fonctionnelles et les 14 critères d'acceptation en distinguant implémentation, preuves exécutées et qualification encore nécessaire.
