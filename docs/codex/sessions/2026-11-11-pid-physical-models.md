# Modèles P&ID thermiques et trois voies, 11 novembre 2026

## Demande et état courant

Après la livraison documentaire, l'utilisateur a répondu « je sais pas, couvre le plus et le mieux » au choix de profondeur. Deux modèles FAT supplémentaires sont livrés : `valve_three_way` et `heat_exchanger`. Les neuf types historiques et les 41 familles documentaires sont conservés. Aucun ancien symbole documentaire n'est activé automatiquement.

Checkout source `C:/FAT_Studio`, Windows 11, Python 3.12.10, branche `codex/vanguard-fat-studio-brand`, HEAD `f5ad062cfc9babbd2ab61d22ee55528ad0fc7979` avec modifications préexistantes conservées. Aucun commit, push, déploiement, accès CPU ou modification des anciens kits. Baselines, journaux, reçus détaillés et fichiers d'essai sont privés dans `.local/pid-physical-2026-11-11` et `.dev-loop/pid-physical-2026-11-11`.

## Comportement et fichiers

- `catalog.py`, `models.py`, `engine.py` : vanne en mélange/diversion entre trois cuves distinctes, débits complémentaires et allocation commune avec les circuits historiques ; échangeur à deux volumes mélangés, stockage thermique, puissance signée et encrassement explicite. Sources de débit associées après allocation volumique ; limites et conflits contrôlés. Cycle local transactionnel et publication REAL/Float32 préservés.
- `pid_ports.py`, `pid_exchange.py`, `pid_export.py` : quatre piquages HX et AB/A/B, rotations, import documentaire par défaut et simulation sur choix explicite seulement. Le dessin n'embarque pas les paramètres physiques ou le mapping. Ancrages draw.io corrigés ; libellé inférieur dupliqué omis lorsqu'il répète le repère déjà visible au-dessus, après reproduction d'une collision sur la conduite B.
- Frontend `PidCanvas.tsx`, `types.ts`, `PidExchange.tsx`, `pid-symbols.css`, `Panels.tsx` : mesures 2T/kW signés et position/qA/qB, paramètres et sources sélectionnables, animations par branche/circuit, défaut d'encrassement numérique, choix explicite du contrôleur de démonstration. Aucun débit animé sur les objets documentaires. Création de cinq mesures HX sans commandes nulles remplaçant les conditions constantes.
- Exemple public `examples/pid-thermal-loop.project.json` : trois cuves, une vanne, un échangeur, douze tags, un scénario de 100 secondes avec cinq contrôles automatiques. La branche A fournit explicitement le débit secondaire ; les cuves restent volumiques, sans thermique cachée.
- Nouveaux tests `test_pid_physics.py`, `test_pid_physics_validation.py`, `test_pid_physical_exchange.py`, `test_pid_thermal_example.py` et navigateur `pid-physics.spec.ts`. Schémas projet/paquet/scénarios, sélection publique, README, guides et changelog actualisés. Crédits Scott Duncan et licences existantes conservés ; aucune bibliothèque payante ajoutée.

Lire [PID_SIMULATION.md](../../PID_SIMULATION.md) pour les équations, unités, commandes, sources et limites. La référence documentaire Modelica Buildings est citée ; aucun code de cette bibliothèque n'a été incorporé.

## Vérifications exécutées

La suite Python complète a donné **909 réussis, cinq ignorés**, en 290,50 s :

```powershell
. ./.local/dev-env.ps1
.venv/Scripts/python.exe -B -m pytest -q --junitxml=.local/pid-physical-2026-11-11/python-results.xml
```

Les cinq ignorés concernent les privilèges de création de liens symboliques Windows ; les contrôles de junction exécutables restent dans la suite. Après cette exécution, la correction bornée du libellé exporté et ses deux témoins ont été vérifiés par **106 tests réussis en 8,44 s**, sans sommer ces résultats au total de la suite complète :

```powershell
.venv/Scripts/python.exe -m pytest tests/test_pid_physical_exchange.py tests/test_pid_equipment_exchange.py tests/test_pid_export.py -q
```

Sur le bundle final, `npm test` depuis `frontend/` donne **74 réussis, zéro échec, ignoré ou flaky**, en 232,96 s. Typecheck, Vite et copie `scripts/build-web.py` passent. Assets finaux : `index-BvN0g2-r.js` et `index-Djb7A6da.css`. Ruff global et `pip check` passent. Une capture desktop de configuration a été relue ; pas de nouvelle qualification mobile ou d'un autre navigateur.

Le wheel final `.local/pid-physical-2026-11-11/dist/vanguard_fat_studio-0.2.1-py3-none-any.whl`, SHA256 `ccd73ae133402e2b6cca510e0996f2370421693ed870abbd446fc0affd935086`, comporte 67 entrées vérifiées. Une installation privée hors source, exécutée avec `-I -B`, vérifie 66 fichiers installés, 60 fichiers produit identiques aux sources, 33 modules issus du paquet installé et les assets servis exactement. Le reçu installé passe en 20,992 s : scénario 100 s/1 000 cycles/cinq assertions, 8 000 L conservés, débit secondaire égal à la branche A, dix exports/réimports HTTP, projet complet, archives et historique après redémarrage. Les dépendances sont réutilisées ; ce n'est pas un poste Windows vierge.

Les essais distinguent restauration des données natives et dessin visible. Les ports/rotations et coordonnées vectorielles sont vérifiés après retrait du JSON incorporé dans les formats concernés. Le dessin ne qualifie pas la reconnaissance de tous les plans externes.

## Serveur et démonstration locale

Le serveur source a été relancé sur `http://127.0.0.1:8765` après vérification du processus parent/enfant, du dossier isolé `.local/pid-catalogue-demo-2026-11-11/data`, de l'absence d'essai et de connexion. Parent `38128`, listener `38488` au constat de livraison ; ces PID peuvent être réutilisés plus tard, les revalider avant toute action. Le manifeste local courant est `.local/pid-catalogue-demo-2026-11-11/server.json`.

Le projet actif est `pid-thermal-demo-20261111`, copie explicite de l'exemple à vitesse de démonstration 10×. Son scénario a terminé 100 secondes simulées avec cinq assertions réussies, puis le modèle a été réinitialisé. État final : idle, run_id absent, déconnecté, zéro écriture courante. L'essai terminé reste dans l'historique, avec verdict humain **not_evaluated**. Le projet Virden `pid-26f8b46defb64583` et `public-io-lab` sont conservés.

Les exports réels HTTP sont dans `.local/pid-physical-2026-11-11/live-exports/` : PDF, DWG AC1015, PNG, P&ID JSON, projet complet et archive avec preuves. Les cinq repères sont présents dans le texte PDF et les 61 entités du DWG relu ; le PNG a été inspecté. Le vrai plan catalogue Virden et ses anciens exports restent disponibles dans leurs dossiers précédents. Aucun résultat de ce modèle n'est attribué au procédé Virden.

## Limites et suite

L'échangeur représente deux volumes monophasiques et une conductance UA ; pas de profil spatial, changement de phase, paroi métallique, pertes ambiantes ou calcul de pression. La vanne ne calcule ni pression ni composition/température du mélange. Lignes, imports et animation n'établissent aucun couplage physique implicite. Les résidus d'arrondi restent ceux du calcul double précision aux paramètres extrêmes.

Les blocs CAD fournisseur, la reconnaissance générale des scans, les extensions DEXPI, l'acceptation CAO propriétaire, Windows vierge, les autres OS et Siemens restent hors qualification. DWG R2000 LibreDWG demeure expérimental. Aucune observation humaine ni conclusion FAT n'a été renseignée.

Le périmètre demandé est livré ; aucune vérification obligatoire ne reste en attente. Pour reprendre, lire cette note et le journal privé entier, vérifier Git et le service actif, puis ouvrir l'exemple ou le projet local. Les qualifications matérielles exigent leur propre cible et autorisation ; aucune ancienne permission CPU n'est réutilisable. Preuves publiques : [vérification](../../../evidence/reprises/2026-11-11-pid-physical/VERIFICATION.md).
