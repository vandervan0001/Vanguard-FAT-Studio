# Vérification des feuilles P&ID, 11 novembre 2026

Windows 11, Python 3.12.10, HEAD `f5ad062cfc9babbd2ab61d22ee55528ad0fc7979` et travail non commité. Résultats liés aux sources/artefacts par le [reçu JSON](verification.json).

- Suite Python complète : 1 059 réussis, cinq ignorés pour privilèges de liens symboliques Windows, 315,53 s.
- Suite navigateur complète finale : 77 réussis, zéro échec/ignoré/flaky, 255,63 s, sans retries. Premier passage : un `ECONNRESET` en préparation HTTP d'un cas et 76 réussis ; conservé séparément, seconde suite exécutée sans modification produit après Python. Cause non établie.
- Formats A4 à A0, orientations, cartouche, cinq révisions, dates/folios stricts, champs longs, cadre/labels et oracle physique indépendant. PDF vectoriel avec polices incorporées et propriétés ; vrai DWG avec calques, mm de feuille, poids/tirets et layout 1:1 conservés.
- Aperçu HTTP borné et passif : ni sauvegarde, ni changement de contexte/essai, ni blocage de Stop pendant le rendu. Brouillons/409, Ctrl+S, exports complets et sauvegarde lente vérifiés.
- Wheel installé hors source : 68 fichiers conformes au paquet, 62 fichiers produit conformes aux sources, 35 modules installés, assets exacts, dix formats HTTP, aperçu, archives/historique et redémarrage, 19,888 s. Dépendances réutilisées ; aucune qualification Windows vierge.
- Deux exemples exportés par l'API source gardée : thermique et extrait réel Virden revu. PDF A3 420×297 mm rendus par Poppler et relus ; DWG AC1015 rouverts, 195/220 entités et layout/mm conservés. Projets antérieurs conservés, aucun essai/PLC lancé, état final au repos.

Les [références et contrats](../../../docs/PID_PRINTING.md) bornent la présentation : pas de conformité ISO/ISA complète, de visa signé, de verdict FAT ou d'acceptation CAO propriétaire revendiqués. La qualité d'impression n'établit pas la reconnaissance de tous les plans externes ni la qualification d'un procédé.
