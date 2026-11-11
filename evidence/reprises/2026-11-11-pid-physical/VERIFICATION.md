# Vérification des modèles P&ID, 11 novembre 2026

Windows 11, Python 3.12.10, source HEAD `f5ad062cfc9babbd2ab61d22ee55528ad0fc7979` avec changements non commités. Le [reçu JSON](verification.json) lie résultats, fichiers et paquet. Les preuves historiques restent séparées.

- Suite Python complète : 909 réussis, cinq ignorés pour privilèges de liens symboliques Windows, 290,50 s. Après la correction d'un libellé d'export, 106 contrôles ciblés réussissent ; ces comptes ne sont pas additionnés.
- Suite navigateur complète sur le bundle final : 74 réussis, zéro échec, ignoré ou flaky, 232,96 s. Build, typecheck, Ruff et dépendances vérifiés.
- Modèles : bilans de volume, stockage thermique, inversion chaud/froid, débit nul, encrassement, cuves vides, concurrence de soutirages, rollback et Float32. Le scénario public passe cinq assertions en 1 000 cycles sans verdict humain.
- Échanges : dix formats natifs ; dessin vectoriel et piquages tournés contrôlés séparément des métadonnées. Import HX/trois voies documentaire par défaut, modèle physique sur choix explicite ; projet complet/archive pour restaurer paramètres et mappings.
- Wheel installé hors source : 66 fichiers installés égaux au paquet, 60 fichiers produit égaux aux sources, 33 modules importés depuis l'installation, assets HTTP exacts, 20,992 s de vérification. Projet, archives, historique et redémarrage vérifiés avec dépendances réutilisées.
- Serveur source local relancé dans son dossier de démonstration isolé. Exemple thermique exécuté puis remis au repos ; Virden et le laboratoire antérieurs conservés. PDF et DWG réels produits, cinq repères vérifiés dans le PDF et 61 entités DWG relues.

Les [contrats de simulation](../../../docs/PID_SIMULATION.md) et la [portée des imports](../../../docs/PID_COVERAGE.md) précisent les limites. Pas de solveur de pression, de reconnaissance universelle des plans, de qualification CAO propriétaire, Windows vierge, temps réel ou Siemens. Aucun accès de production ni conclusion FAT humaine. Le banc et cette extension utilisent des outils gratuits.
