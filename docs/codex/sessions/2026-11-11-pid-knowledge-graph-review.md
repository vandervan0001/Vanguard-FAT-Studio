# Lecture des deux dépôts P&ID de Scott Duncan

11 novembre 2026, Windows/PowerShell, checkout `C:/FAT_Studio`, HEAD `f5ad062cfc9babbd2ab61d22ee55528ad0fc7979`. L’utilisateur a fourni deux liens sans demander d’installation ni d’intégration. Première évaluation documentaire de leur intérêt pour FAT Studio, avec lecture indépendante du catalogue de données par un agent.

## Sources et constats

- [PID-to-Knowledge-Graph, README](https://github.com/ScottDuncanAI/PID-to-Knowledge-Graph/blob/main/README.md), [dépendances](https://github.com/ScottDuncanAI/PID-to-Knowledge-Graph/blob/main/pyproject.toml), [ontologie](https://github.com/ScottDuncanAI/PID-to-Knowledge-Graph/blob/main/skills/pid-to-kg/references/ontology.md) et [licence MIT](https://github.com/ScottDuncanAI/PID-to-Knowledge-Graph/blob/main/LICENSE) lus via le connecteur GitHub. Le dépôt décrit un skill Claude : lecture visuelle des PDF par le modèle, puis construction et contrôle du graphe par des scripts Python. Sorties JSON, DuckDB, synthèse et rapport QA. Provenance, confiance et relations inférées sont représentées. Les logiques présentes seulement dans une analyse fonctionnelle ou une matrice causes-effets ne sont pas extraites du P&ID. Le README demande une revue d’ingénierie. Aucun essai du convertisseur réalisé ici.
- [Public chemical manufacturing datasets, README](https://github.com/ScottDuncanAI/public-chemical-manufacturing-datasets/blob/main/README.md) : catalogue de liens vers cinq ensembles de P&ID de traitement d’eau et cinq ensembles temporels réels ou simulés. La CC BY 4.0 annoncée pour le catalogue concerne ses liens et descriptions ; les sources externes gardent leurs conditions propres. Les pages GitHub des deux dépôts ont aussi été ouvertes avec l’outil web.
- Le worker a également consulté [HistorianRCA](https://github.com/ScottDuncanAI/HistorianRCA/blob/main/README.md) et sa [licence](https://github.com/ScottDuncanAI/HistorianRCA/blob/main/LICENSE) : données simulées avec qualité et dictionnaire de tags, piste éventuelle de rejeu pour le diagnostic séparé. Corrigé privé, aucune qualification industrielle déduite.
- Contrat FAT relu dans `docs/FORMAT.md` et modèles `Equipment`, `Connection`, `Project` de `fat_studio/models.py`. Un graphe documentaire ne fournit pas les paramètres du procédé ni les associations PLC/OPC UA nécessaires à un essai.

## Proposition, sans implémentation

Évaluer d’abord une seule feuille publique dans un dossier isolé, avec une référence humaine des équipements, tags et connexions. Un éventuel adaptateur produirait ensuite un brouillon `fat-studio/project`, avec provenance et incertitudes conservées dans une pièce jointe adaptée. Définir le traitement des objets non pris en charge et les limites de taille du banc avant de convertir un grand graphe. Les adresses PLC, NodeIds, échelles analogiques et verdicts FAT resteraient déclarés et vérifiés séparément. Aucun import actif ou accès cible ne découle de cette proposition.

## État Git et vérification

Les modifications produit, frontend, bundle et documents déjà présentes ont été conservées. Seuls cette note et un ajout en tête de `docs/codex/ETAT_REPRISE.md` appartiennent à cette session. Sauvegarde privée de l’état documentaire et du statut initial sous `.local/pid-review-2026-11-11-3bef60fe1ac94d00aad2d00cf4db8bde/`.

Commandes de lecture : `git status --short`, `git log -5 --oneline`, `git diff --stat`, `git diff -- docs/codex/ETAT_REPRISE.md`, `Get-Content` et `rg`. Vérification finale ciblée des liens locaux et de la conservation des octets antérieurs de l’état de reprise. Aucune suite de tests, installation, exécution de code externe, récupération de PDF, communication PLC, modification du laboratoire diagnostic, compilation, publication ou opération Git d’écriture.

## Reprise

Aucun blocage pour cette lecture. Le choix d’un prototype et de son document source reste à définir avec l’utilisateur. Ne pas traiter l’envoi des liens comme une demande d’installation de skill. Pour reprendre : `git status --short`, puis `Get-Content docs/codex/sessions/2026-11-11-pid-knowledge-graph-review.md` et `Get-Content docs/FORMAT.md`. Si un prototype est demandé, épingler le commit amont, vérifier les droits du document choisi et travailler hors des données d’essais existantes.
