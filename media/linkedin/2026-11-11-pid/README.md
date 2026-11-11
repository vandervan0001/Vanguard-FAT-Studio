# Post LinkedIn : P&ID, revue et dossier de plans

Préparé le 11 novembre 2026. Aucune publication LinkedIn effectuée.

## Utilisation

Copier [le texte du post](POST.md). Joindre [le PDF de présentation de quatre pages](documents/Vanguard-PID-presentation-LinkedIn.pdf) comme document, ou choisir les captures PNG séparées pour une publication d'images. Les plans A3 et fichiers CAO sont des pièces de démonstration complémentaires ; les polices Geist et leur licence accompagnent les DWG/DXF.

Ordre conseillé des captures : application et services, mise en page avec aperçu, détail du cartouche Virden, catalogue et crédits. Les captures sont des prises de l'application réelle, sans maquette ni remplacement des API. Les diagrammes PNG proviennent des PDF exportés. Le PDF LinkedIn reprend ces images avec des légendes ; le texte éditorial est dans POST.md.

## Sources et droits

- Scott Duncan / ScottDuncanAI, [PID-to-Knowledge-Graph](https://github.com/ScottDuncanAI/PID-to-Knowledge-Graph), MIT : référence d'ontologie et de graphe, workflow Claude non exécuté.
- [Public Chemical Manufacturing Datasets](https://github.com/ScottDuncanAI/public-chemical-manufacturing-datasets), catalogue adapté en français sous CC BY 4.0. Licence jointe ; les documents externes gardent leurs propres conditions.
- Virden : reconstruction documentaire partielle à partir du dessin D-016-0, page 14 du [dossier public du Manitoba](https://www.gov.mb.ca/sd/eal/registries/5697virden/2019-04-26_5697_00_phase_2_p_and_i_drwngs.pdf). Huit repères, quatre liaisons, disposition réorganisée. Le document source complet n'est pas redistribué dans ce pack.
- Jochen Steimel, [pyflowsheet](https://github.com/nukleon84/pyflowsheet/tree/8a68f2569a9a977079ece242aa7771b9d53448a8), MIT : quatre géométries adaptées, licence complète jointe. [Provenance détaillée](../../../fat_studio/pid_symbols_PROVENANCE.md).
- Geist : The Geist Project Authors, SIL OFL, licence jointe au ZIP des polices. Logo Vanguard fourni par le propriétaire du projet. Captures et mise en page produites localement.

## Preuves et limites

Résultats de la version illustrée : 1 150 tests Python réussis, cinq ignorés Windows ; 79 scénarios navigateur réussis. Ces résultats sont historiques et n'ont pas été réexécutés pour préparer le post. [Preuves de la version](../../../evidence/reprises/2026-11-11-pid-conventions/VERIFICATION.md).

Les captures du 11 novembre utilisent le seul serveur de démonstration local 8765, projet thermique au repos, sans PLC ni écriture. Seules navigation et demande d'aperçu ont été effectuées ; aucun projet enregistré par la prise de vue. Les données et scripts temporaires restent privés.

L'import demande une revue. La palette est une convention de projet, les symboles libres ne certifient pas une conformité globale ISA/ISO, et la réception FAT reste humaine. Le DWG a été relu via LibreDWG ; la CAO et les styles d'impression du destinataire restent à contrôler. Les PDF de plans sont marqués BROUILLON avec des mentions d'entreprise EXEMPLE.

Le manifeste donne les tailles et SHA-256 de tous les fichiers du dossier, hors manifeste lui-même. Les quatre pages du PDF de présentation et les captures ont été inspectées visuellement. Les fichiers CAO/PDF A3 sont des copies vérifiées des exports Rev B ; aucune source de l'application n'a été modifiée pour ce post.
