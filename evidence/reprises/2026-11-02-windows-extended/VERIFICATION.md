# Vérification étendue sans Siemens, 2 novembre 2026

Cette campagne complète la préparation locale et teste le ZIP livré lui-même. Le code testé est `682be875662d99b37752d6174e471a72dcef451d`, branche `codex/windows-local-setup`. Il ajoute huit tests de jonctions NTFS ; aucun fichier du runtime ni asset applicatif n'a changé pendant cette campagne. Les preuves initiales restent conservées dans [windows-local](../2026-11-02-windows-local/VERIFICATION.md).

## Suites complètes et CI

| Environnement | Python | Frontend | Preuve |
| --- | --- | --- | --- |
| Ce poste Windows 11, Python 3.12.10 | 423 réussis, 4 ignorés | 33 réussis contre le logiciel extrait du ZIP | [JUnit local](pytest-full.xml), [frontend installé](frontend-installed.json) |
| CI Windows | 427 réussis, aucun ignoré | 33 réussis | [JUnit Windows](ci/pytest-windows-latest.xml), [frontend Windows](ci/frontend-windows.json) |
| CI Ubuntu | 419 réussis, 8 ignorés spécifiques NTFS | 33 réussis | [JUnit Ubuntu](ci/pytest-ubuntu-latest.xml), [frontend Ubuntu](ci/frontend-ubuntu.json) |

La [CI 41532733264](https://github.com/vandervan0001/FAT-Studio/actions/runs/41532733264) a réussi ses deux jobs sur ce SHA. La branche a été poussée et le workflow a été déclenché manuellement ; `main` reste inchangé. Les documents et preuves ajoutés ensuite ne revendiquent pas une nouvelle exécution du workflow. Le [reçu du run](ci/run.json) et l'[extrait des logs](ci/selected-results.log) identifient les résultats observés.

Les quatre tests de liens symboliques sont toujours ignorés sur ce compte Windows pour manque de privilège (WinError 1314). Ils passent sur le runner Windows de la CI. Les huit nouveaux essais utilisent de vraies jonctions, sans modifier Windows : quatre positions du cache ou de ses parents, avec cible externe ou partagée dans la racine. Ils vérifient le refus avant mutation et la conservation des fichiers. Voir [junction-summary.json](junction-summary.json).

Ruff, `pip check`, TypeScript/Vite, construction des wheels et installation hors ligne Windows réussissent également en CI. La [comparaison des wheels](ci/wheel-comparison.json) trouve les mêmes 32 fichiers applicatifs. La wheel Windows correspond aux octets des sources locales. Dans la wheel Ubuntu, trois textes diffèrent seulement par LF/CRLF : la licence HistorianSim, les notices du frontend et `requirements-engineering.txt`. Python, JS, CSS, HTML et SVG correspondent exactement.

## ZIP exact et application installée

Le ZIP `FAT-Studio-Windows-2026-11-02.zip`, empreinte `7fe117bd80029f134d796b3957db41b19f13e1828b1efb000bd8bb8cfae90f82`, a été extrait dans un nouveau dossier. Son installation runtime/MCP sous Windows PowerShell 5.1 a réussi avec `PIP_NO_INDEX=1`, index de repli `http://127.0.0.1:9` et cache pip désactivé. Le manifeste de 43 wheels est vérifié avant et après installation. Le module utilisé provient bien du `site-packages` de cette nouvelle `.venv`.

Le script de contrôle contenu dans le ZIP a réussi ses cinq contrôles hors sources : assets, démarrage/pause, exports CSV/HTML/JSON, historique après reset, relecture par un nouveau processus. Le nettoyage temporaire strict passe. Le bundle extrait se reclone au HEAD `ef8f96c` et passe `git fsck --full`. Le ZIP et les kits originaux n'ont pas été modifiés. Voir [archive-acceptance.json](archive/archive-acceptance.json).

La suite frontend de 33 tests, dont 26 parcours navigateur et 7 tests de client/format, a ensuite utilisé cette même installation sur `127.0.0.1:8768`, avec un dossier de données dédié. Le [relevé d'import](installed-ui-environment.json) confirme le paquet effectivement servi. Aucun dossier d'essais personnels n'a été utilisé.

Un essai complémentaire sur cette installation a affiché 50 équipements et 200 tags pendant environ 30 secondes : 305 échantillons exportés avec 200 valeurs chacun, 200 lignes de variables rendues, pause/arrêt opérationnels et aucune erreur navigateur. Les 64 réponses de supervision mesurées ont un p95 de 55,01 ms. Cette mesure utilise un projet synthétique et un poste partagé, sans seuil de réception temps réel. Voir [ui-load-50x200.json](ui-load-50x200.json) et la [capture](ui-load-50x200.png).

## OPC UA réel générique

Le [rapport OPC UA](opcua-extended.json) couvre deux essais loopback réels, indépendants de Siemens :

- La fixture CLI exacte a exécuté les trois scénarios à 1×, soit 840 cycles et 12 assertions réussies. Le forçage Float32, le défaut moteur observé sur le serveur, la pause sans écriture, l'export borné pendant l'essai, la coupure et la relecture de l'historique ont été vérifiés.
- Un serveur local en `SignAndEncrypt` a échangé 200 tags pour 50 équipements pendant 1 000 cycles sains : 160 000 écritures de valeurs de tags, avec comparaison de l'image serveur aux traces et aux Float32. Il ne s'agit pas de 160 000 transactions réseau. Les forçages et la vanne bloquée sont vérifiés. Après coupure, le banc passe en erreur et qualité `bad` ; le retour serveur ne reprend pas les écritures. Un nouvel essai explicite de 20 cycles réussit.

Les exports de charge contiennent 200 201 lignes CSV, en-tête inclus, et SQLite passe `integrity_check`. Le p95 du cycle mesuré est de 30,7969 ms ; le maximum atteint 223,6864 ms et trois dépassements sont consignés. Le poste était partagé avec d'autres vérifications. Ces résultats ne garantissent pas la cadence avec TIA/PLCSIM, le navigateur ou le réseau Siemens. La politique personnelle est inchangée ; les certificats et clés de test restent dans `.local/`, hors Git.

## Paquet MCP et prérequis Siemens

Le vrai paquet NuGet Czarnak 4.3.0 a été installé hors ligne dans un dossier de diagnostic distinct des profils FAT. Son CLI renvoie `4.3.0` ; la négociation MCP renvoie `4.3.0.0`, forme déjà admise par l'intégration. Le SDK officiel a listé huit outils en lecture seule. Les outils d'écriture/compilation sont absents et les huit commandes interdites du contrôle local sont refusées avant appel. Aucune opération sur un projet TIA n'a été demandée. Voir [transport MCP](tia-package-readonly-transport.json).

Le [doctor en lecture seule](tia-package-doctor-readonly.json) renvoie le code 1 attendu : TIA Portal, ses DLL Openness et le groupe Windows associé sont absents. Ce diagnostic reste un blocage Siemens, distinct du succès du transport. Aucun manifeste de profil n'a été créé. Voir [tia-package-check.json](tia-package-check.json).

Un premier probe de diagnostic utilisait à tort `--help` seul. Dans cette version, cet argument démarre le serveur MCP par défaut en lecture-écriture ; il s'est arrêté à la fin de l'entrée, sans requête d'outil ni projet Siemens. Le probe corrigé utilise le mode explicite lecture seule et `doctor --help` pour l'aide. Cette observation et sa règle d'usage sont enregistrées dans `KB.md`. Les erreurs initiales de paramètres/version du harness ne sont pas comptées comme défauts du produit.

Le relevé [PyPI](python-advisories.json) des 54 dépendances Windows verrouillées ne rapporte aucune alerte dans les métadonnées des versions consultées ; [npm audit](npm-audit.json) ne rapporte aucune vulnérabilité connue. Ces relevés datés ne constituent pas une certification de sécurité du code.

## Reproduire les essais complémentaires

Les helpers exacts sont conservés dans ce dossier. Ils sont prévus pour `C:\FAT_Studio` et ses dépendances préparées ; adapter explicitement `ROOT` sur un autre poste. Les helpers UI doivent être copiés dans `.local/` pour retrouver leur import relatif. La fixture OPC UA exige la création de son dossier parent :

```powershell
Set-Location C:\FAT_Studio
. .\.local\dev-env.ps1
New-Item -ItemType Directory -Force .local/opcua-extended | Out-Null
Copy-Item evidence/reprises/2026-11-02-windows-extended/reproduce-opcua.py .local/opcua-extended/verify-opcua.py
python -X utf8 .local/opcua-extended/verify-opcua.py

Copy-Item evidence/reprises/2026-11-02-windows-extended/reproduce-ui-load.mjs .local/test-installed-ui-load.mjs
Copy-Item evidence/reprises/2026-11-02-windows-extended/ui-load-project.json .local/ui-load-project.json
# Démarrer d'abord le paquet installé sur 8768 avec un dossier de données de test neuf.
node .local/test-installed-ui-load.mjs
```

Les scripts UI modifient les projets du serveur de test ; conserver le port et les données dédiés, puis arrêter le serveur. Le helper MCP exige le paquet de diagnostic déjà installé dans `.local/tia-mcp-package-check` ; il conserve `--access-mode read-only`. Les clés, certificats de travail et journaux complets non retenus restent dans `.local/` ; les journaux sélectionnés pour preuve sont conservés ici.

## Frontières restantes

TIA Portal, Openness et PLCSIM restent absents. Aucun build natif V20, profil MCP vérifié, compilation/import TIA, restauration d'archive Siemens ou essai avec une CPU virtuelle Siemens n'a été exécuté. Les verdicts FAT humains restent non évalués. Ces points demandent les installations/licences et une copie autorisée du vrai projet ; ils ne sont pas remplacés par les succès locaux.
