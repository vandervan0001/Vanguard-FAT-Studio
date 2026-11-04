# Passe finale sur le backend corrigé

Le 3 novembre 2026, le seul backend 8770 a été redémarré sur les sources finales, après arrêt explicite de son essai et vérification du processus et du dossier de données. Le [reçu avant redémarrage](backend-restart-before.json) et le [reçu après redémarrage](backend-restart-after.json) conservent cette identité et les empreintes des sources. Le nouveau worker est 6688. Aucune autre instance applicative ou CPU n'a été commandée.

Cette passe utilise la **factory publique courante**, remappée sur les mêmes 75 correspondances natives, le même programme passif `DB_FAT_Demo` + `Main`, et le même [certificat serveur public](../native/opcua-server-public.der). Il n'y a eu **aucune recompilation ni aucun rechargement PLC**. Le [bilan de préparation native](../native/VERIFICATION.md) décrit les deux seuls blocs chargés, les offsets DB1 observés et les droits OPC UA. La nouvelle CPU virtuelle reste `FAT-DEMO-20261103`, adresse `.3` sur le seul adaptateur Siemens isolé. Les connexions utilisent **Basic256Sha256 / SignAndEncrypt**, certificat et ApplicationUri épinglés.

Le [résumé de campagne](campaign-summary.json) et le [journal CLI](public-cli-commands.jsonl) établissent le trajet par `python -m fat_studio.assistant`. Le contexte est neuf et capturé explicitement. Les huit scénarios courants sont comparés intégralement à la factory, sans changement de leurs attentes :

| Scénario | Attentes réussies | Preuve |
| --- | ---: | --- |
| Alimentation source | 4/4 | [JSON](timed/demo-fill-source/exports/evidence.json) |
| Transfert 1 | 4/4 | [JSON](timed/demo-transfer-1/exports/evidence.json) |
| Transfert 2 | 4/4 | [JSON](timed/demo-transfer-2/exports/evidence.json) |
| Vidange | 3/3 | [JSON](timed/demo-drain/exports/evidence.json) |
| Contact d'arrêt | 4/4 | [JSON](timed/demo-stop/exports/evidence.json) |
| Défaut physique de pompe | 5/5 | [JSON](timed/demo-pump-fault/exports/evidence.json) |
| Vanne bloquée | 3/3 | [JSON](timed/demo-valve-stuck/exports/evidence.json) |
| Analogique | 4/4 | [JSON](timed/demo-analog/exports/evidence.json) |

**31 attentes sur 31 ont réussi**, avec 460 échantillons, 25 760 écritures d'entrées et 9 660 valeurs REAL de trace exactement Float32. Chaque essai possède aussi son CSV et son rapport HTML. Les sorties viennent du vrai PLC ; aucun outil natif n'écrit d'I/O et le contrôleur Python de démonstration n'est pas utilisé dans ces essais OPC UA.

Le [premier STEP technique guidé](guided/summary.json) est appliqué : stimulus **12 mA**, `actual_wire_value` **13 824**, lecture native indépendante **50 %**, commande P101 **FALSE**. Aucun `step-observe`, aucune observation inscrite, **0/5 étapes revues**, verdict humain `not_evaluated`. Le [rapport guidé](guided/exports/report.html) conserve cette limite. Cette passe ne constitue aucune réception FAT humaine.

Le client a exécuté **139 commandes de campagne**, puis **un export d'archive**, toutes avec code de sortie 0. L'[archive du vrai projet et de son historique](project-with-real-history.fat.zip), obtenue par le CLI public et l'API d'archive, contient 19 essais. La [vérification de restauration](archive-restore-verification.json) utilise uniquement un **Store neuf dans TemporaryDirectory** : les huit nouveaux essais temporisés restent `completed`, leurs échantillons sont conservés, le projet actif restauré reste en mode démo déconnecté, aucune politique machine ni clé client n'est restaurée. Le workspace live n'est pas changé par ce contrôle.

À la clôture, l'[essai est arrêté](final-backend-state.json), la CPU est explicitement **STOP** et le [projet réel sécurisé](final-project.json) reste sélectionné. Le service 8770 est conservé pour la présentation suivante. Root a ensuite repris seul les commandes de cette nouvelle présentation ; son état live ultérieur est distinct de cette clôture.

La [revue backend indépendante](../review/summary.json) a reproduit quatre défauts puis contre-vérifié les corrections : historique terminé préservé après panne de sauvegarde, exports sous contexte de workspace, archivage sans bloquer Health/Stop et contexte correct après ouverture sans changement du workspace actif. Ces reproductions utilisent exclusivement des données temporaires ; elles n'ont contacté aucun serveur ni CPU de démonstration.

Les [contrôles finaux](verification.json) vérifient les oracles, les traces Float32, les empreintes, les liens, le filtre de contenu public et l'absence de clés/secrets copiés, y compris dans le ZIP. Le [manifeste SHA-256](checksums.json) hache les fichiers figés. Les preuves des premières passes et leurs reçus d'incident restent intacts.
