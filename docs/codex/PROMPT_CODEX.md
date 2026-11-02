# Prompt à copier dans Codex — reprise complète de FAT Studio

Tu reprends **FAT Studio**, le projet existant dans ce dépôt. Agis comme responsable de sa finalisation technique, avec une compétence automation Siemens, Python, TypeScript, OPC UA et validation de logiciels d'essai.

## Mon objectif

Je veux un banc FAT local complet et utilisable : dessiner un P&ID, configurer les équipements et leurs tags, simuler le procédé, le relier à un programme Siemens via PLCSIM Advanced/OPC UA, exécuter des scénarios et produire des preuves fiables. Le programme PLC doit conserver la responsabilité du contrôle. L'option IA/TIA doit réutiliser les projets existants, notamment **Czarnak/tia-portal-mcp**, avec un parcours de revue et d'application maîtrisé.

J'ai demandé une revue de code et une revue adverse poussées pour viser un fonctionnement correct au premier essai. Une version 0.1.1 a déjà été construite, corrigée et testée. **Reprends cet existant et avance jusqu'à un résultat vérifié dans l'environnement dont tu disposes.** Ne te limite pas à proposer un plan. Ne recrée pas le projet et ne remplace pas son architecture sans défaut ou besoin démontré.

## Prendre connaissance du dossier

Lis dans cet ordre :

1. `AGENTS.md`, `README-CODEX.md`, `docs/codex/ETAT_REPRISE.md`, puis les dernières notes de `docs/codex/sessions/` s'il y en a.
2. `README.md`, `docs/URS-original.md`, `docs/URS-implementation.md` et `docs/REQUIREMENTS_MATRIX.md` pour comprendre les exigences, les décisions et les écarts restant à qualifier.
3. `docs/ADVERSARIAL_REVIEW.md` et `evidence/VERIFICATION.md` pour connaître les défauts déjà corrigés et les preuves réellement obtenues.
4. `docs/FDS.md`, `docs/CONTRACT.md`, `docs/MODEL.md`, puis les guides d'installation/Siemens/MCP utiles à la prochaine étape.

La conversation précédente n'est pas nécessaire : les sources et documents du dépôt sont le dossier de reprise. Vérifie leur concordance avec les fichiers actuels, sans prendre les résultats historiques pour des tests exécutés aujourd'hui sur ce poste.

## Commencer par l'état réel

- Identifier la racine du dépôt, l'OS, les versions de Python/Node/Git, les outils réellement accessibles, l'état Git, le diff, les tags et les remotes.
- Repérer les modifications en cours et les données utilisateur avant toute action ; conserver ce travail.
- Si tu es dans le ZIP extrait avec `offline-manifest.json` et `wheelhouse/`, garder ce kit intact. Créer une copie source sœur depuis `FAT-Studio.bundle`, dans une destination neuve, puis travailler dans cette copie. Si tu travailles déjà dans une copie source modifiée, continuer cette copie.
- Utiliser des dossiers temporaires dédiés pour les essais. Les données FAT personnelles résident normalement hors du dépôt ; elles ne sont pas sauvegardées par le ZIP des sources.
- Expliquer brièvement ce que tu as trouvé et commencer les actions utiles, sans attendre une validation du plan pour chaque opération réversible.

## Ordre du travail

### 1. Reproduire le démarrage et les contrôles utiles

Suivre les commandes adaptées à l'OS dans `docs/codex/ETAT_REPRISE.md`. Installer les dépendances verrouillées. Vérifier le diagnostic et le démarrage de la démonstration, puis les tests nécessaires. Pour le frontend : construire, copier les assets dans `fat_studio/web`, puis utiliser `npm test` pour la suite complète sur le bundle réellement servi.

Si un défaut est reproductible, le corriger avec une modification ciblée, ajouter un test pertinent et refaire la vérification affectée. Vérifier les comportements visibles : P&ID, mapping, scénarios, forçages, états de communication, conclusions, exports et persistance. Ne pas affaiblir un contrôle ou une assertion pour rendre la suite verte.

### 2. Fermer les qualifications encore ouvertes lorsque le poste le permet

Sous Windows : vérifier le premier lancement PowerShell, un environnement Python neuf, le kit runtime sans accès aux index pip, le service installé hors des sources et la persistance après redémarrage. Les commandes et le contrôle `scripts/smoke-installed.py` existent déjà.

Avec TIA/PLCSIM réellement disponibles et une copie autorisée : suivre `docs/PLCSIM_SETUP.md` et `docs/ACCEPTANCE.md`. Relever les versions et observer les vrais NodeIds, droits, types, ApplicationUri et certificats. Valider le raccordement au programme, les scénarios métier et le comportement lors d'une rupture de communication.

Pour l'ingénierie, conserver Czarnak **4.3.0** et le client IA en **lecture seule**. Préparer les propositions dans `after.*`. Les opérations qui modifient ou compilent la copie TIA restent dans le parcours humain avec archive, diff, empreintes et confirmations déjà prévues. Ne pas contourner ces confirmations, inventer une identité Siemens ou connecter une cible de production par défaut.

Si un composant, une licence, un projet ou un accès manque, terminer toutes les tâches indépendantes et décrire exactement la qualification non réalisée. Un serveur OPC UA local et un double MCP restent des preuves de protocole, pas des essais Siemens.

### 3. Revue et livraison

Utiliser une relecture indépendante pour les changements significatifs lorsque des agents parallèles sont disponibles, avec des périmètres de fichiers distincts. Examiner surtout l'attribution des actions au bon essai, la fidélité des traces, les erreurs/annulations, le typage PLC, l'installation et le parcours opérateur.

Conserver les preuves historiques 0.1.1. Enregistrer les nouvelles commandes, résultats, plateforme et références Git dans un dossier daté, mettre à jour les documents affectés et effectuer des commits cohérents des changements de la mission. Ne pas inclure les données personnelles d'essai ni les secrets dans les commits ou archives.

Le dépôt GitHub distant n'a pas été créé à la passation. Vérifier les remotes et l'authentification actuels avant d'annoncer une publication. Ne pas inventer d'URL ni de réussite GitHub Actions ; si une publication est effectuée dans le périmètre autorisé de cette session, transmettre son URL et les résultats effectivement observés.

## Résultat attendu

Je veux du travail effectué : application démarrée dans l'environnement disponible, défauts démontrés corrigés, vérifications pertinentes exécutées, documentation et preuves cohérentes, dépôt récupérable et prochaine étape explicite pour toute qualification matériellement impossible ici.

Ne présente pas « right first time » comme une garantie abstraite. Donne les faits : ce qui fonctionne, comment tu l'as vérifié, les écarts encore ouverts et leur condition de résolution.

Avant de t'interrompre, actualise `docs/codex/ETAT_REPRISE.md` et ajoute une note dans `docs/codex/sessions/` avec l'état Git, les changements non commités, les tests, les processus laissés actifs et la prochaine action exacte. Une nouvelle session doit pouvoir continuer sans me demander de raconter de nouveau le projet.

**Commence maintenant par l'inspection du dépôt et du poste, puis poursuis l'exécution.**
