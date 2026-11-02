# Vérification CI — FAT Studio 0.2.1

Exécution du **2 novembre 2026**, sur les runners GitHub `windows-latest` et `ubuntu-latest`.

- Runtime : **0.2.1**.
- Source vérifiée : `b55bfded63dc5572da8d3409409210381cc50c34`.
- [Exécution GitHub Actions 41471993176](https://github.com/vandervan0001/FAT-Studio/actions/runs/41471993176) : les deux jobs ont terminé avec succès.

## Résultats observés

| Job | Python | Frontend et API cliente | Tests ignorés |
| --- | ---: | ---: | ---: |
| Windows | 418 réussis | 33 réussis | 0 |
| Ubuntu | 418 réussis | 33 réussis | 0 |

Aucun échec ni erreur dans les deux rapports JUnit. Aucun échec, test ignoré ou résultat instable dans les deux rapports Playwright. La construction web, l'intégration des assets, l'analyse Python, le diagnostic et la construction de la wheel ont réussi sur les deux OS. Le parsing des scripts PowerShell a réussi sur Windows.

Les tests Python utilisent notamment des serveurs OPC UA locaux et des doubles de contrat pour l'ingénierie. Les tests frontend couvrent le bundle servi par le backend temporaire. Ces preuves restent attachées à la source indiquée ci-dessus.

## Installation Windows du runtime

Le job Windows a préparé le kit avec accès aux dépendances, puis créé une installation dans un nouveau dossier avec une nouvelle `.venv`. L'installation a utilisé `wheelhouse` avec les index pip désactivés. Les journaux montrent deux recherches dans le répertoire de wheels et l'installation effective de `local-fat-studio-0.2.1`.

Le contrôle du paquet installé, lancé hors de l'arbre source, a réussi avec **quatre échantillons** et cinq vérifications :

1. HTML, JavaScript et CSS de production servis localement.
2. Démonstration démarrée et mise en pause, marqueur enregistré et verdict explicitement non évalué.
3. Exports CSV, HTML et JSON cohérents.
4. Arrêt et reset conservant les preuves archivées.
5. Nouveau processus retrouvant l'historique et restant inactif.

Le résultat est conservé dans [windows-clean-install.json](windows-clean-install.json). Il ne remplace pas la réception humaine d'une FAT.

## Périmètre restant

TIA Portal, PLCSIM Advanced, les compilations Siemens, l'installation du serveur d'ingénierie sur les DLL réelles V20/V21 et le raccordement à un programme PLC n'ont pas été exécutés par cette CI. Leur qualification reste à réaliser sur le poste autorisé. Le succès du runtime sous les runners Windows et Ubuntu ne clôt pas ces essais.

## Preuves conservées

Les fins de ligne du JSON Windows ont été normalisées de CRLF vers LF pour le suivi Git. Le résumé conserve `source_sha256` pour l’artefact original et `sha256` pour la copie suivie. Les deux fichiers XML restent identiques aux artefacts téléchargés.

- [Résumé et empreintes](github-ci.json).
- [JUnit Windows](pytest-windows-latest.xml).
- [JUnit Ubuntu](pytest-ubuntu-latest.xml).
- [Contrôle de l'installation Windows](windows-clean-install.json).

Les journaux et rapports Playwright bruts de ce run sont conservés dans les artefacts GitHub et dans le dossier de travail local `work/2026-11-02-windows-ui/`, hors du dépôt suivi.
