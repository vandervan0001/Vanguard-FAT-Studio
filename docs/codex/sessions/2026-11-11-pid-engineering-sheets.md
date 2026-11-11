# Feuilles P&ID de bureau d'études, 11 novembre 2026

## Livraison

Demande : impressions PDF/DWG plus professionnelles, cartouche, révisions, entreprise et dates. Feuilles A4 à A0 portrait/paysage livrées, cadre et zones, cartouche en bas à droite, historique de cinq révisions, notes, mentions de préparation/vérification/approbation, statut et folio. Le P&ID reste sans échelle de procédé. Les noms et dates sont déclaratifs ; aucun visa, signature ou verdict FAT n'est inventé.

Source Windows 11/Python 3.12.10, branche `codex/vanguard-fat-studio-brand`, HEAD `f5ad062cfc9babbd2ab61d22ee55528ad0fc7979`, travail non commité et changements préexistants conservés. Aucun commit, push, accès CPU, déploiement ou modification des anciens kits. Baseline et journal privés : `.local/pid-drafting-2026-11-11/baseline` et `.dev-loop/pid-drafting-2026-11-11/logbook.md`.

## Fichiers et contrats

- Nouveaux `pid_titleblock.py` et `pid_sheet.py` ; intégration dans `models.py`, `pid_models.py`, `pid_exchange.py`, `pid_import.py`, `pid_export.py`. `Project.pid_drawing` et `PidDocument.drawing` ont des valeurs par défaut compatibles avec les anciens fichiers. L'extension graphe `fat_studio_drawing` conserve les seuls réglages de feuille. Cartouche actif distinct de l'ancien document source et des révisions des essais historiques.
- PDF/PNG/DXF/DWG partagent la feuille en mm, textes vectoriels et traits monochromes. PDF avec Geist régulier/gras incorporés, titre/entreprise/code/révision dans les propriétés. DXF/DWG éditables avec calques, poids et tirets ; unités de feuille en mm et layout réellement adressable `PID_SHEET`, papier/viewport/échelle d'impression 1:1 conservés par le vrai LibreDWG R2000. SVG/draw.io gardent leur scène de diagramme et leurs piquages.
- Les champs longs de cartouche se répartissent sans perte. Les combinaisons impossibles demandent un format plus grand. Densité signalée, légende réservée, libellés de conduites dégagés ; une course de validation de folio et des ticks traversant le dernier rang du cartouche ont été reproduits puis corrigés.
- `pid_api.py` et middleware `app.py` : aperçu POST passif sur géométrie enregistrée + réglages proposés, PNG ≤ 1600×1100, contexte attendu, snapshot et rendu hors verrou des commandes. Aucun enregistrement ou changement d'essai par l'aperçu.
- Frontend `PidDrawingEditor.tsx`, `PidExchange.tsx`, `App.tsx`, `types.ts`, `api.ts`, CSS : nouvel onglet Mise en page, groupes repliables, sauvegarde, aperçu, récupération du brouillon et protection des conflits. Ctrl+S ouvert sauvegarde le vrai cartouche ; Ctrl+S global et exports complets signalent un cartouche non appliqué au lieu d'annoncer une sauvegarde trompeuse. Sauvegarde lente : édition de géométrie verrouillée même après fermeture de la modale.
- Nouveaux tests `test_pid_drafting_contract.py`, `test_pid_drawing_api.py`, `test_pid_sheet.py`, `pid-drafting.spec.ts`. Témoins anciens de géométrie adaptés aux coordonnées physiques, avec oracle A3 indépendant. Schémas, exemple thermique, sélection publique, guides, README et changelog actualisés. Crédits et dépendances gratuites conservés.

Lire [PID_PRINTING.md](../../PID_PRINTING.md) pour les champs, les unités et les références primaires ISO 7200/5457/128-2/10628-1. C'est une trame propre au banc, sans déclaration de conformité complète ISO/ISA.

## Vérifications

Suite complète Python finale : **1 059 réussis, cinq ignorés Windows, 315,53 s**. Les ignorés nécessitent le privilège de liens symboliques ; contrôles de junction conservés. Commande :

```powershell
. ./.local/dev-env.ps1
.venv/Scripts/python.exe -B -m pytest -q --junitxml=.local/pid-drafting-2026-11-11/python-results.xml
```

Suite complète navigateur finale : **77 réussis, zéro échec/ignoré/flaky, 255,63 s**, `npm test` depuis `frontend/`, sans retries. Premier passage conservé séparément : 76 réussis et un échec dans la découverte HTTP du `beforeEach`, deux GET ayant subi `ECONNRESET` avant toute assertion du parcours. Les lectures voisines et cas suivants répondaient normalement ; une course keep-alive est une hypothèse, pas une cause démontrée. Seconde suite complète effectuée après la fin de Python, sans modification produit, entièrement réussie. Aucun retry ajouté pour masquer l'incident.

Typecheck, Vite, copie `scripts/build-web.py`, Ruff, `pip check`, sélection publique, liens et diff vérifiés. Assets : `index-HzS-uWsS.js` / `index-4oe-xmsA.css`. 55 empreintes produit figées et inchangées après contrôles. Captures desktop/mobile du formulaire et PNG réel relus ; pas de qualification générale de tous les appareils/navigateurs.

Wheel final `.local/pid-drafting-2026-11-11/dist/vanguard_fat_studio-0.2.1-py3-none-any.whl`, SHA256 `f779e20b746fd595d6f3fab094855127939b88a2c35173b467926196d2bee96c`, 69 entrées contrôlées. Installation privée hors source sous `-I -B` : **19,888 s**, 68 fichiers installés égaux au wheel, 62 fichiers produit égaux aux sources, 35 modules issus de l'installation. Dix formats HTTP conservent le cartouche, PDF vectoriel/2 polices incorporées, DWG réel en mm/layout 1:1, aperçu passif et conflit 409, projet/archives/révisions historiques et redémarrage vérifiés. Scénario thermique installé : 1 000 cycles, cinq assertions, verdict humain not_evaluated. Dépendances réutilisées, pas de qualification Windows vierge. Un témoin initial du helper privé pointait au mauvais niveau du schéma de paquet ; corrigé sans changement produit, preuve initiale conservée séparément.

## Serveur et deux feuilles réelles

Le serveur 8765 était absent au contrôle préalable (connexion refusée, ancien parent inexistant, aucun listener). Aucun processus n'a été arrêté. La seule source du dossier isolé `.local/pid-catalogue-demo-2026-11-11/data` a été démarrée masquée ; parent `13244`, listener `33524` au constat, à revalider car ces PID peuvent être réutilisés. Manifeste courant : `.local/pid-catalogue-demo-2026-11-11/server.json`.

Après découverte santé/projet/état/catalogue/schéma/workspace et capture explicite du contexte, deux copies de démonstration ont été enregistrées par API gardée puis exportées : `pid-thermal-sheet-20261111` et `pid-virden-sheet-20261111`. Les projets précédents sont conservés. Projet final actif : Virden, idle/run_id absent, déconnecté, zéro écriture. Aucun essai n'a été lancé par ce chantier d'impression.

Livrables locaux dans `output/pdf/` et `output/cad/`, préfixes `PID-Thermique-A3-Rev-A` et `PID-Virden-Alun-A3-Rev-A`. Deux PDF A3 420×297 mm, deux vrais DWG AC1015 et deux DXF ; PNG de contrôle issus de Poppler 120 dpi relus. Propriétés PDF et métadonnées natives contrôlées. DWG thermique : 195 entités ; Virden : 220, unités/mm/layout conservés. Le Virden reste l'extrait de huit repères/quatre liaisons revu depuis D-016-0 page 14, avec notes de portée. Aucune qualification du réseau complet ou d'un procédé réel n'est déduite de cette présentation.

## Limites et reprise

LibreDWG R2000 reste expérimental et l'acceptation dans une CAO propriétaire reste à vérifier. Pas de conformité complète ISO/ISA, d'émission contractuelle, de signature vérifiée, d'impression physique qualifiée, de qualification Siemens/temps réel ou Windows vierge. Un export représente un folio ; le total déclaré ne génère pas les autres feuilles.

Aucun contrôle obligatoire en attente. Pour continuer, relire cette note et le journal complet, vérifier Git et le service actuel, puis ouvrir Échanges P&ID > Mise en page. Les fichiers de démonstration et les journaux restent hors distribution publique ; seules les preuves relues sont sélectionnées explicitement. [Preuve publique](../../../evidence/reprises/2026-11-11-pid-drafting/VERIFICATION.md).


## Contrôle visuel complémentaire du 11 novembre 2026

Demande : ouvrir le PDF Virden, montrer le cartouche et l'historique, vérifier le rendu du DWG. Inspection des fichiers déjà livrés, sans relance du serveur, changement de projet, accès PLC ou édition produit. État Git toujours partagé et non commité, HEAD f5ad062 ; changements préexistants préservés.

Le PDF `output/pdf/PID-Virden-Alun-A3-Rev-A.pdf` a été rendu avec Poppler, puis le rectangle physique x=228..412 mm / y=174..290 mm depuis le haut a été extrait à 180 dpi. Cartouche complet et cinq lignes d'historique lisibles. Révision A datée 2026-11-11, numéro EX-VIR-PID-014, entreprise explicitement EXEMPLE, statut BROUILLON et visas non renseignés. Le plan reste l'extrait revu de huit repères et quatre liaisons, pas le réseau complet de la source. L'ouverture demandée au panneau Codex a répondu queued ; le rendu raster a été inspecté directement.

Le DWG AC1015 réel a été reconverti avec LibreDWG 0.14, puis ses entités CAO ont été rendues par ezdxf 1.4.5 et sharp, sans reconstruire l'image depuis le JSON natif. Le DXF livré a été rendu séparément. Les deux rendus CAO montrent un débordement dans l'historique, absent du PDF. La description mesure 54,56 mm en PDF Geist, contre 72,85 mm en CAO Arial pour une taille déclarée de 2,2 ; elle termine à x=334,85 mm et dépasse de 8,85 mm la cellule jusqu'à x=326 mm. L'export utilise la même valeur pour une taille em PDF et une hauteur de capitale DXF ; les polices diffèrent également. Le contrat de [TEXT.height ezdxf](https://ezdxf.readthedocs.io/en/stable/dxfentities/text.html) précise la hauteur de capitale.

La chaîne DWG conserve les 220 entités, les textes, les données natives, les unités mm et le layout PID_SHEET 1:1. En revanche, 56 textes centrés sont relus avec un point d'alignement à l'origine, malgré un point d'insertion conservé. Comparaison de la spécification et de deux implémentations insuffisante pour attribuer définitivement ce défaut à l'encodage ou à la lecture LibreDWG. Aucun lecteur DWG indépendant disponible n'a été trouvé ; aucune installation effectuée. L'équivalence visuelle PDF/DWG n'est pas établie et ne doit pas être annoncée.

Preuves privées sous `.local/pid-drawing-review-2026-11-11/` : `geometry-verification.json`, `font-verification.json`, rendus SVG/PNG, scripts de reproduction `verify_geometry.py`, `render_cad.py`, `raster_cad.cjs`. Contrôles de ce tour : rendu Poppler, comparaison des entités et métadonnées, lecture DWG JSON, rendu CAO et mesures de polices. Aucune nouvelle exécution des suites Python/navigateur ni reconstruction du wheel ; leurs résultats précédents restent historiques. Aucun PDF/DWG/DXF livré modifié.

Prochaine action précise : fixer une convention em/capitale et des largeurs réellement compatibles avec la police CAO dans `fat_studio/pid_export.py`, reproduire le centrage indépendamment de la restauration native, ajouter un témoin de débordement qui échoue sur l'export actuel, puis produire de nouveaux fichiers distincts et comparer leurs impressions. Reproduction locale en lecture seule :

```powershell
.venv/Scripts/python.exe -B .local/pid-drawing-review-2026-11-11/verify_geometry.py
.venv/Scripts/python.exe -B .local/pid-drawing-review-2026-11-11/render_cad.py
```
