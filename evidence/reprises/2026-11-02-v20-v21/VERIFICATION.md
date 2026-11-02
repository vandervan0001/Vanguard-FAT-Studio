# FAT Studio 0.2.0 — sélection V20/V21

Vérification du 2 novembre 2026 sur macOS 26.3.1 ARM64, Python 3.12.12, Node 25.1.0. Source de départ `1054d96d28bc2edb47f5ad8f2cbb742f6b2828da`, branche `codex/tia-v20-v21`. Ce dossier conserve les nouvelles preuves ; les résultats 0.1.1 n'ont pas été remplacés.

## Résultats exécutés

| Contrôle | Résultat observé |
| --- | --- |
| Suite Python complète, source Czarnak réelle épinglée fournie aux tests | **418 réussis**, 0 erreur/échec/ignoré ; 83,39 s |
| Suite frontend complète sur le bundle servi | **33 réussis**, 0 échec/ignoré/flaky ; 37,6 s |
| Typage TypeScript et build Vite | Réussis ; avertissement de taille du chunk conservé |
| Ruff et `pip check` | Réussis |
| Préparation source V20 | 9 tests dédiés, dont deux sur des clones du vrai source épinglé ; aucune DLL Siemens simulée présentée comme preuve native |
| Parseur PowerShell 7.6.9 sur Mac | 0 erreur ; 1 662 tokens ; garde « Windows requis » exercée avec refus attendu |
| Wheel Python 0.2.0 | 32 fichiers applicatifs identiques aux sources ; 5 fichiers web, aucun asset périmé |
| Contrôle du paquet installé hors sources | Réussi, version 0.2.0 ; 4 échantillons, exports CSV/HTML/JSON, historique après reset et redémarrage |

La suite Python couvre les deux versions pour les politiques, propositions, archives, acquittements, profils et refus d'écriture. Elle refuse notamment une version/suffixe incompatible, un manifeste absent ou altéré, un backend croisé, des DLL modifiées ou de dossiers différents et une proposition d'un autre profil. Les fragments TOML sont parsés ; le transport et les configurations clients reçoivent le dossier Openness vérifié malgré un environnement hérité conflictuel.

Les deux nouveaux parcours navigateur vérifient le choix V20/V21, sauvegarde/rechargement, export/import et verrouillage en essai. Les 31 parcours antérieurs passent aussi. [Capture V20 regardée](tia-version-v20.png).

Un contrôle de wheel a reproduit la présence de l'ancien JS haché dans le cache setuptools. Après correction de `build-web.py`, la liste et le contenu des fichiers embarqués correspondent aux sources. Les tests du vrai script vérifient aussi que les autres sorties du build restent présentes et que les liens sortants sont refusés avant mutation.

## Commandes et fichiers

Depuis la copie source, dépendances verrouillées déjà installées :

```bash
(cd frontend && npm run build)
.venv/bin/python scripts/build-web.py
FAT_TIA_UPSTREAM_SOURCE=/chemin/du/clone/Czarnak-v4.3.0 .venv/bin/python -m pytest --junitxml=evidence/reprises/nouveau-run/pytest.xml
(cd frontend && npm test)
.venv/bin/python -m ruff check fat_studio integrations tests scripts
.venv/bin/python -m pip check
.venv/bin/python -m build --wheel --no-isolation
```

Le clone fourni aux tests est exactement `10c5de2eb44c0362792cd141370b3f42f92f6ecd`. Les tests sans ce clone ne doivent pas être présentés comme ayant exercé sa transformation réelle. Le workflow CI le récupère explicitement à cette révision ; son existence ne prouve pas son exécution.

La wheel finale a été installée avec `pip --no-index --no-deps` dans la seconde `.venv` runtime créée pendant la reprise macOS précédente. Cette preuve porte sur la mise à jour et l'exécution hors sources du paquet 0.2.0 ; l'installation neuve des dépendances figure dans le [dossier macOS 0.1.1](../2026-11-02-macos-arm64/VERIFICATION.md). Le contrôle suivant a ensuite démarré et arrêté ses propres services temporaires :

```text
.venv/bin/python scripts/smoke-installed.py --python <seconde-venv>/bin/python --output evidence/reprises/2026-11-02-v20-v21/installed-check.json
```

Fichiers : [JUnit](pytest.xml), [résultats frontend](frontend-tests.json), [contenu de la wheel](build-verification.json), [contrôle installé](installed-check.json), [parseur PowerShell et préparation source](source-installer-verification.json). Les relectures indépendantes ont vérifié les liaisons de version, la propagation de l'environnement, le restore/build et les guides ; les défauts identifiés ont été corrigés avant livraison.

## Portée native restant ouverte

**Aucun build ni essai Siemens réel V20/V21 n'a été exécuté sur ce Mac.** Le code amont cible V21. V20 est un candidat de portage qui doit encore compiler contre les vraies DLL V20 sur Windows, puis passer l'acceptation. Le code réseau/HMI/VCI typé de l'amont peut notamment révéler une incompatibilité au build ; l'installateur doit s'arrêter au lieu de produire un profil utilisable. Une transformation réussie, un parseur PowerShell ou un double MCP ne prouvent pas ce build.

V21 conserve le paquet NuGet 4.3.0. Les deux profils exigent leur manifeste, les DLL de la version choisie et une copie autorisée ; les écritures restent soumises aux confirmations du terminal humain. Les tests n'attribuent aucun verdict FAT humain et n'envoient aucun ordre de téléchargement ou RUN/STOP CPU.

Le serveur utilisateur local a été arrêté à la demande de Tai, données conservées. Les services des tests et du contrôle installé sont temporaires. Le dépôt de publication est privé ; les résultats de CI distante sont à lire séparément, sans en déduire une qualification TIA ou PLCSIM.
