# Préparation du poste Windows sans Siemens

Date : 2 novembre 2026, Europe/Zurich. Poste Windows 11 x64, Python 3.12.10. Demande de Tai : récupérer FAT-Studio, lire le prompt Codex et réaliser les préparations indépendantes de TIA Portal et PLCSIM, sans demandes d'autorisation supplémentaires.

## Référence et périmètre

Dépôt privé cloné dans `C:\FAT_Studio` au commit `00ab08c`, avec branches distantes et tags. État initial propre. Branche de travail locale : `codex/windows-local-setup`. Le prompt `PROMPT_CODEX.md`, les consignes du dépôt, l'état de reprise et les notes précédentes ont été lus. Le runtime reste en 0.2.1 ; les assets reconstruits sont identiques au dépôt.

## Travail effectué

- Création de `.venv` et installation des dépendances runtime, développement et ingénierie selon les trois locks.
- Installation locale indépendante de Codex de Node.js 22.23.4/npm 10.9.9 et du SDK .NET 10.0.403, avec vérification des empreintes publiées par les éditeurs. L'environnement se charge avec `. .\.local\dev-env.ps1`.
- Clone Czarnak propre à la révision épinglée, restauration du worker net48 et du host, préparation de 61 paquets NuGet locaux, puis restauration dans un cache neuf depuis cette seule source. Aucune compilation Siemens ni utilisation de DLL factices.
- Correction du lock d'ingénierie : dépendance Windows `pywin32==312` explicitement épinglée. Une résolution neuve confirme 54 dépendances verrouillées.
- Compilation et intégration du frontend, installation du paquet, construction de la wheel et comparaison des noms et contenus de ses 32 fichiers applicatifs.
- Premier lancement réel de `Start-FAT.cmd` dans un kit neuf, sans index ni cache pip ; installation MCP hors ligne et contrôle des 43 wheels.
- Raccourci **FAT Studio** ajouté au bureau ; guide [WINDOWS_LOCAL_SETUP.md](../../WINDOWS_LOCAL_SETUP.md) ajouté. Les données personnelles par défaut n'ont pas été utilisées pour les tests.

## Vérifications exécutées

Suite complète Python : 414 réussis, 4 ignorés pour privilège de création des liens symboliques absent, aucun échec. Suite frontend complète : 33 réussis, aucun retry, avec Node 24 fourni initialement par Codex puis avec le Node 22 portable livré. Ruff, TypeScript/Vite et `pip check` réussis. Démonstration : 3 scénarios, 12 assertions réussies, aucun verdict FAT humain attribué.

Le benchmark 50 équipements/200 tags sur 1 000 cycles a mesuré un p95 modèle + SQLite de 2,849185 ms. Cette mesure exclut OPC UA, Siemens, HTTP et navigateur ; elle ne constitue pas une garantie de cadence avec PLCSIM.

Les fichiers de preuve sont sous `evidence/reprises/2026-11-02-windows-local/`. Le helper `reproduce-package-demo.py` y est conservé avec une racine source explicite. Les logs de travail et outils locaux sont ignorés par Git dans `.local/` et `.tools/`.

## Correctif du contrôle installé

Le premier `scripts/smoke-installed.py` a atteint le nettoyage de son dossier temporaire, puis échoué sur `PermissionError: [WinError 32]` pour `history.sqlite3`. L'attente portait sur le redirecteur de `.venv` ; Windows peut encore terminer son vrai Python après cette attente. Le bootstrap du contrôle écrit désormais le PID réel. Un handle Windows `SYNCHRONIZE` est acquis avant la vérification de santé, attendu après l'arrêt du lanceur et fermé même en erreur. Le second lancement ne peut plus être validé pendant que le processus précédent est encore en cours d'arrêt.

`tests/test_installed_smoke.py` démarre un vrai Python tenant SQLite ouverte, exécute l'arrêt et vérifie la suppression immédiate du dossier. Les régressions ciblées ont obtenu **18 réussites et 4 tests de liens symboliques ignorés**. Elles sont distinctes de la suite complète initiale. Ruff passe après le correctif. Les contrôles installés finaux sont réussis contre la `.venv` source et celle du kit : [source](../../../evidence/reprises/2026-11-02-windows-local/source-installed-check.json) et [hors ligne](../../../evidence/reprises/2026-11-02-windows-local/offline-installed-check.json). Tous deux vérifient les assets hors sources, les exports, le reset et le redémarrage. Le nettoyage temporaire strict est conservé.

Les changements significatifs et les preuves ont fait l'objet de relectures indépendantes. Les échecs de diagnostic dans l'ancien sandbox d'un agent ne sont pas comptés comme défauts de l'application. Seules les commandes exécutées sur le poste avec accès complet sont retenues pour les résultats locaux.

## Reprise et processus

Aucun service de test n'est laissé actif sur 8765, 8766 ou 8767 à cette étape. Le serveur de démonstration reste lançable depuis le raccourci ou `Start-FAT.cmd`. Les données de vérification sont isolées dans `.local/` et les répertoires temporaires.

Fichiers suivis modifiés : `requirements-engineering.lock`, `scripts/smoke-installed.py`, `tests/test_installed_smoke.py`, le guide Windows, l'état de reprise, cette note et les preuves datées. Le runtime Python et les assets frontend sont identiques à la base. Les modifications de livraison sont conservées par commits locaux sur `codex/windows-local-setup` ; vérifier `git log -3` et `git status --short` à la reprise. Aucun push ni nouvelle CI distante n'a été exécuté.

Le correctif est conservé au commit `1f54282`. Le kit final neuf est dans `C:\FAT_Studio-Offline-2026-11-02` : manifeste vérifié, 43 wheels, 32 fichiers applicatifs identiques aux sources et script de contrôle corrigé inclus. Il n'est pas installé ; le contrôle d'installation réel porte sur le kit de validation distinct. Voir `final-kit.json`. La documentation et les preuves sont conservées dans le commit suivant.

La sauvegarde finale est dans `C:\FAT_Studio-Delivery-2026-11-02` : `FAT-Studio.bundle`, wheel, `FAT-Studio-Windows-2026-11-02.zip`, `SHA256SUMS.txt` et `delivery.json`. Le reçu donne le HEAD sauvegardé et les empreintes. Le bundle est vérifié et sa récupération par clone avec `git fsck --full` a réussi ; le ZIP de 245 fichiers est contrôlé par CRC. Les données personnelles et les environnements/caches de développement sont exclus. L'assemblage se reproduit avec les commandes enregistrées et `.local/archive-delivery.py` sur ce poste.

Prochaine action : installer TIA Portal/Openness et PLCSIM, puis utiliser `PROMPT_VALIDATION_WINDOWS_TIA_V20_V21.md` avec une copie de projet autorisée. Pour reprendre le développement sans Siemens, ouvrir PowerShell dans `C:\FAT_Studio`, exécuter `. .\.local\dev-env.ps1`, puis les commandes du guide Windows. Le kit de validation est conservé intact ; générer tout nouveau kit dans une destination neuve avec `scripts/prepare-offline.ps1 -Engineering`.
