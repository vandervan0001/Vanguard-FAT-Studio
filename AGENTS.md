# Consignes de travail — FAT Studio

## Lire avant de modifier

Commencer par `README-CODEX.md`, `docs/codex/ETAT_REPRISE.md` et les éventuelles notes récentes dans `docs/codex/sessions/`. Les instructions de la demande utilisateur en cours priment sur ce document. Les preuves historiques ne remplacent pas l'inspection de l'état Git courant.

Si `offline-manifest.json` et `wheelhouse/` sont présents, ce dossier est un kit d'exécution vérifié. Créer une copie source distincte depuis le bundle ou le dépôt avant les modifications ; conserver le kit intact. Ne pas enlever le manifeste ou désactiver ses contrôles pour faire passer une installation. Si une copie source est déjà en cours de travail, la reprendre sans écraser ses changements.

## Projet et architecture

FAT Studio est un banc FAT local : FastAPI/Python, interface React/TypeScript/Vite avec React Flow, modèle de procédé, preuves SQLite et adaptateur OPC UA. Le programme PLC contrôle le procédé ; le contrôleur de démonstration reste distinct et n'est utilisé qu'en mode démo. Le dessin P&ID n'est pas un solveur hydraulique général.

Réutiliser les composants présents. Le serveur d'ingénierie reste Czarnak `TiaMcpServer` **4.3.0** épinglé ; les références et licences sont dans `integrations/upstream.lock.json` et `THIRD_PARTY_NOTICES.md`. Lire le contrat de la version épinglée avant de changer son intégration.

## Invariants à préserver

- Validation des projets, types et mappings avant communication ; namespace 0 interdit après résolution ; identité/certificat avant authentification et écritures.
- Politique de cible propre au poste, indépendante d'un projet importé ; forçages limités aux entrées simulées.
- Erreur de communication, stockage ou annulation : arrêt explicite, qualité visible et aucune reprise automatique. Une écriture OPC UA partielle n'est pas annulable par le modèle.
- Contexte projet/révision/essai des commandes ; refus d'un contexte périmé ; verdict et événement dans une transaction unique.
- Tags REAL en Float32, physique interne en double précision ; attentes d'assertion conservées ; traces fidèles aux valeurs échangées.
- Export d'un instantané fini et cohérent ; historique conservé après reset ; aucune validation FAT humaine inventée.
- Client IA TIA en lecture seule. Les imports/compilations autorisés suivent le CLI humain et ses confirmations existantes. Aucun téléchargement, RUN/STOP CPU ou accès de production ajouté automatiquement.

## Méthode de travail

Examiner `git status`, le diff et les commits avant d'agir. Préserver les modifications utilisateur, les données d'essais et les secrets ; ne pas utiliser de reset ou nettoyage destructif. Procéder aux lectures, installations locales autorisées, corrections réversibles et tests utiles sans multiplier les demandes de confirmation. Si une action manque réellement d'accès, de cible ou d'autorisation, terminer ce qui est possible et préciser le blocage concret.

Utiliser les verrous de dépendances. Reproduire un défaut avant correction quand c'est possible, puis tester le comportement observable et les frontières touchées. Pour une modification documentaire seule, vérifier les liens, l'exactitude et l'assemblage ; ne pas annoncer de nouvelle exécution de tests qui n'a pas eu lieu.

Construire le frontend, copier ses assets avec `scripts/build-web.py`, puis tester le bundle livré. `npm test` est la suite complète ; `npm run test:e2e` ne lance que `workbench.spec.ts`. Les suites navigateur utilisent des données temporaires, jamais une instance contenant les essais utilisateur.

Conserver les preuves 0.1.1. Placer les nouvelles preuves dans un sous-dossier daté et consigner la plateforme, le commit ou l'état de travail, les commandes et le résultat. Un mock TIA ou un serveur asyncua local ne qualifie pas Siemens ; un workflow présent ne prouve pas son exécution.

## À chaque interruption ou livraison

Actualiser l'état courant dans `docs/codex/ETAT_REPRISE.md` et ajouter une note datée dans `docs/codex/sessions/` : fichiers modifiés, état Git, tests exécutés, blocages, prochaine action précise et commandes nécessaires. Ne pas inscrire de secrets. Des instructions initiales sont disponibles dans `docs/codex/PROMPT_CODEX.md`, et le prompt de continuation dans `docs/codex/PROMPT_REPRISE_CODEX.md`.
