# Vérification étendue Windows et CI

Date : 2 novembre 2026, Europe/Zurich. Suite à la demande de Tai de gérer et tester tout ce qui est accessible sans Siemens, reprise sur `ef8f96c`, branche `codex/windows-local-setup`, état Git propre au départ.

## Résultats

Huit tests de jonctions NTFS réelles ont été ajoutés dans `tests/test_distribution.py`, avec cibles externes et internes. Ils conservent les quatre tests de liens symboliques et leurs assertions. Aucun changement système ni code produit n'est requis. Commit testé : `682be875662d99b37752d6174e471a72dcef451d`.

Suite complète locale : **423 réussis, 4 ignorés** pour privilège de liens symboliques absent. La [CI 41532733264](https://github.com/vandervan0001/FAT-Studio/actions/runs/41532733264), déclenchée sur la branche poussée, a réussi sur **Windows (427 tests Python réussis)** et **Ubuntu (419 réussis, 8 jonctions Windows ignorées)**, avec **33 tests frontend sur chaque système**. Les quatre liens symboliques passent en CI Windows. L'installation hors ligne Windows de la CI et son contrôle installé réussissent. `main` n'a pas changé.

Le ZIP exact de la livraison initiale a été extrait et installé hors ligne dans un nouveau dossier ; son script de contrôle passe hors sources, et le bundle extrait se reclone proprement. Les 33 tests frontend passent contre cette installation exacte. Une charge UI de 50 équipements/200 tags produit 305 échantillons sans erreur navigateur et affiche les 200 lignes de variables.

Les essais OPC UA locaux réels passent : fixture CLI à 1× avec 3 scénarios/12 assertions, puis serveur chiffré à 200 tags avec 1 000 cycles sains et 160 000 écritures de valeurs. Coupure, qualité `bad`, absence de reprise spontanée, redémarrage explicite, Float32, exports et intégrité SQLite sont vérifiés. Le p95 est de 30,7969 ms, le maximum de 223,6864 ms ; les trois dépassements restent consignés. Aucune performance Siemens n'est déduite de cette mesure sur poste partagé.

Le paquet NuGet MCP réel est installé uniquement dans `.local/tia-mcp-package-check`. La négociation en lecture seule liste huit outils ; le doctor confirme les trois prérequis Siemens manquants. Un probe incorrect `--help` a brièvement démarré le serveur amont par défaut puis s'est arrêté sur fin d'entrée, sans requête d'outil ni projet présent. Les probes suivants sont explicitement en lecture seule ; utiliser `doctor --help` pour l'aide. Le constat est conservé dans `KB.md`.

Les relevés npm/PyPI ne signalent aucune alerte connue sur les dépendances consultées, sans garantie générale de sécurité. La [preuve étendue](../../../evidence/reprises/2026-11-02-windows-extended/VERIFICATION.md) donne résultats, JUnit, logs, commandes, mesures et limites.

## Fichiers et reprise

Changements suivis de cette campagne : huit tests dans `tests/test_distribution.py`, connaissance CLI dans `KB.md`, preuves datées, cette note et l'état de reprise. Aucun fichier applicatif du runtime ni asset web n'a changé. Les helpers et certificats de travail restent isolés dans `.local/` ; les helpers sans secrets sont aussi conservés avec les preuves pour reproduction. La politique personnelle n'a pas changé.

Les processus de test sont arrêtés. Le logiciel reste lançable depuis le raccourci **FAT Studio** du bureau. Les changements sont poussés sur la branche de validation ; aucune fusion dans `main`, aucune installation/licence Siemens et aucune validation FAT humaine n'ont été effectuées.

La livraison complémentaire est dans `C:\FAT_Studio-Delivery-2026-11-02-extended`, avec bundle de la branche, wheel, ZIP et reçu `delivery.json`. Le runtime du ZIP est celui déjà installé et testé, sans modification de ses octets ; la source Git ajoute les tests et preuves étendus. Le reçu enregistre le HEAD final et les contrôles de récupération. La livraison initiale reste conservée.

Prochaine action fonctionnelle : installer TIA Portal/Openness et PLCSIM, puis suivre `PROMPT_VALIDATION_WINDOWS_TIA_V20_V21.md` sur une copie de projet autorisée. Pour reprendre les contrôles locaux, charger `. .\.local\dev-env.ps1` et lire le dossier de preuve étendu. Les résultats de CI restent attachés au SHA `682be875...` ; les commits documentaires suivants ne changent pas le code testé.
