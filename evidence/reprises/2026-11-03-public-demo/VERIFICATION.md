# Vérification de la reprise publique

Plateforme : Windows x64, Python 3.12.10, Node.js 22.23.4 ; TIA Portal V21 et PLCSIM Advanced 8 pour la campagne Siemens. Branche source `codex/windows-local-setup`, HEAD `cd4daba16580309a675dfa6b1ec95efe5a669038`, arbre de travail modifié et non commité. Aucun push ni publication.

Cette reprise couvre le banc FAT/test, une démo passive, les formats ouverts et la commande par un assistant local. Les standards et sources d'ingénierie privés sont isolés hors des fichiers publics. Les anciennes preuves et livraisons vérifiées restent conservées ; leurs résultats ne sont pas attribués au nouveau programme.

## Résultats acquis

| Frontière | Résultat | Preuve |
| --- | --- | --- |
| Démo sans Siemens | Huit scénarios, 31 attentes, aucun verdict humain | `tests/test_demo_lab.py` |
| Vrai PLC public | Nouveau DB/OB1 compilé et chargé ; huit scénarios, 31 attentes réussies en OPC UA chiffré | [Campagne native](native/VERIFICATION.md) |
| STEP technique natif | 12 mA → 13 824 bruts → 50 %, commande pompe FALSE ; zéro observation | [Résumé natif](native/campaign-summary.json) |
| Archives, dossiers et client IA | 45 tests réussis après les dernières corrections | [Log des frontières](python-final-boundaries.log) |
| Suite Python finale | 572 réussis, cinq ignorés pour privilège de liens symboliques absent, zéro échec | [Reçu et provenance](python-verification.json) |
| Conservation de l'historique | Une erreur d'édition ultérieure ne réécrit pas l'essai terminé | [Contre-vérification](review/after-fix-completed-history-save-failure.json) |
| Contexte d'export | Ancien espace refusé, y compris si projet et ID d'essai sont identiques | [Routes et client public](review/after-fix-all-export-routes-and-public-client.json) |
| Réouverture du dossier actif | Contexte d'essai conservé ; commande suivante possible sans recapture | [Client no-op](review/after-fix-active-workspace-client-context.json) |
| Archivage et réactivité | 6 000 échantillons/75 tags, archive validée ; santé et Stop répondent chacun en 15 ms pendant sa préparation | [Mesure indépendante](review/after-fix-archive-event-loop-latency.json) |
| Bundle livré | JS, CSS et HTML identifiés par SHA-256 | [Empreintes](ui/final/assets.json) |
| Suite navigateur finale | 54 réussis, zéro échec/ignoré/flaky, mêmes assets livrés | [Résultats](ui/final/frontend-results-final.json) |
| Nouvelle passe réelle finale | Huit scénarios/31 attentes, 140 appels client réussis ; archive de 19 essais restaurée temporairement | [Reçu natif final](final-live/verification.json) |
| Vue native réelle | 75 tags good, fenêtre native à 125 %, aucun débordement horizontal ni écriture de la vérification visuelle | [Présentation](presentation/native-window.json) |
| Portable final | 3 090 fichiers contrôlés, cinq contrôles HTTP/redémarrage hors sources avec Python embarqué isolé | [Lancement exact](distribution/portable-final-service.json) |
| Source final | 483 fichiers/29 wheels, installation hors index dans une copie puis cinq contrôles HTTP/redémarrage | [Installation](distribution/source-final-service.json) |
| ZIP de livraison | CRC et SHA-256 de tous les contenus décompressés conformes aux deux manifestes, originaux inchangés | [ZIP et empreintes](distribution/delivery-zips.json) |
| Client IA du portable final | 37 commandes réussies, archive d'un essai terminé restaurée, quatre attentes temporisées, STEP 13 824 sans observation | [Parcours final](distribution/portable-final-client.json) |

La suite finale Python a réussi 572 tests en 257,13 s, et les 54 tests navigateur ont réussi en 145,771 s. Les rapports JUnit de travail restent privés : les octets originaux et les copies sont conservés à part, leurs compteurs et empreintes figurent dans le reçu public. Les identifiants des tests de confidentialité ne sont pas redistribués. Les premiers échecs et leurs corrections sont consignés dans la note de session, sans modification d'oracle natif. Les deux livraisons finales sont scellées, démarrent hors sources et leurs manifestes sont intacts après tous les essais. Les [contrôles de clôture](distribution/final-delivery-checks.json) complètent ces preuves sans réécrire les livraisons.

## Comportements vérifiés et limites

Le projet entier contient P&ID, paramètres, variables, correspondances, animations, scénarios et historique. Les enveloppes JSON versionnées ont leurs schémas ; l'archive `.fat.zip` ajoute les preuves JSON/CSV/HTML d'un instantané fini et un manifeste de tailles/SHA-256. La restauration publie un dossier neuf au repos, préserve l'ancien espace et distingue son contexte d'édition. Les erreurs de préparation ne remplacent pas l'espace actif.

Le lecteur d'archive refuse les chemins ambigus, doublons, liens, contenus inattendus, preuves incompatibles et dépassements de limites. Les politiques machine, clés, licences et autorisations ne sont pas collectées. Les observations libres restent le contenu de leur auteur : le format ne garantit ni leur provenance ni une recherche de secrets dans ces textes.

Les commandes d'I/O n'agissent que sur les entrées simulées. Les animations suivent des tags et leur qualité sans écrire de sorties PLC. Une FAT guidée applique un stimulus puis attend le testeur ; les contrôles techniques ne remplacent ni son observation ni sa conclusion. Le dessin P&ID reste un modèle borné, pas un solveur hydraulique général.

L'accès IA TIA reste en lecture seule avec Czarnak TiaMcpServer 4.3.0 épinglé. La campagne Siemens qualifie uniquement le programme public et la CPU virtuelle dédiée réellement exercés ; aucune qualification V20, CPU physique, installation de production ou sécurité fonctionnelle n'est annoncée. Les commandes CPU privées utilisées pour l'essai ne sont pas ajoutées au client public.

## Commandes de vérification

```powershell
. .\.local\dev-env.ps1
python -m pytest -q --tb=short
python -m ruff check fat_studio integrations tests scripts public_distribution.py build_public.py
python public_distribution.py check
```

Depuis `frontend/` : `npm run typecheck`, `npm run build`, copie avec `python scripts/build-web.py` depuis la racine, puis `npm test` contre les assets livrés et des données temporaires. `npm run test:e2e` seul n'est pas la suite complète. Les détails sont dans [la note de session](../../../docs/codex/sessions/2026-11-03-public-demo.md), [le format](../../../docs/FORMAT.md) et [les archives](../../../docs/PROJECT_ARCHIVES.md).
