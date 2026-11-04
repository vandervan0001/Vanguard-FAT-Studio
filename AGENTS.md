# Consignes de travail — Vanguard FAT Studio

## Lire avant de modifier

Commencer par `README-CODEX.md`, `docs/codex/ETAT_REPRISE.md` et les éventuelles notes récentes dans `docs/codex/sessions/`. Les instructions de la demande utilisateur en cours priment sur ce document. Les preuves historiques ne remplacent pas l'inspection de l'état Git courant.

Si `offline-manifest.json` et `wheelhouse/`, ou `portable-manifest.json` et `runtime/`, sont présents, ce dossier est une livraison vérifiée. Créer une copie source distincte depuis le bundle ou le dépôt avant les modifications ; conserver le kit intact. Ne pas enlever le manifeste ou désactiver ses contrôles pour faire passer une installation. Si une copie source est déjà en cours de travail, la reprendre sans écraser ses changements.

## Piloter le logiciel avec un assistant

Le [guide utilisateur](docs/USER_GUIDE.md) décrit l'interface ; [AI_QUICKSTART.md](docs/AI_QUICKSTART.md) donne le prompt et un tutoriel dans des données isolées ; [AI_CONTROL.md](docs/AI_CONTROL.md) est le contrat canonique CLI/API. [CODEX.md](CODEX.md) et [CLAUDE.md](CLAUDE.md) pointent vers ces mêmes consignes. Vanguard FAT Studio n'embarque pas de modèle ni de clé API IA : le client choisi par l'utilisateur lit les fichiers et pilote le serveur local.

Avant toute mutation d'essai, découvrir la santé/version, le projet, l'état, le catalogue et le schéma actifs. Vérifier l'URL loopback, le dossier de données et le périmètre réellement autorisé. Utiliser `python -m fat_studio.assistant` avec un contexte capturé explicitement, ou fournir à l'API le jeton local et les en-têtes projet/révision/essai. Une lecture d'état ne doit pas avancer silencieusement le contexte attendu. Après conflit, préserver les brouillons et relire ; ne pas recapturer pour rejouer automatiquement.

La FAT pas à pas déclenche des écritures d'entrées simulées puis attend l'observation explicite du testeur. Les contrôles mesurables, le verdict de STEP et la conclusion FAT globale restent distincts. Aucune observation ni conclusion humaine n'est déduite par l'assistant. Déclarer les conversions analogiques et leurs profils de diagnostic ; ne déduire aucune échelle ou NodeId d'une adresse Siemens. Les autorisations ponctuelles d'une CPU virtuelle ne valent que pour la demande et la cible concernées.

## Projet et architecture

Vanguard FAT Studio est un banc FAT local : FastAPI/Python, interface React/TypeScript/Vite avec React Flow, modèle de procédé, preuves SQLite et adaptateur OPC UA. Le programme PLC contrôle le procédé ; le contrôleur de démonstration reste distinct et n'est utilisé qu'en mode démo. Le dessin P&ID n'est pas un solveur hydraulique général.

Le périmètre public contient l’environnement FAT, ses formats JSON et une démo PLC passive. Aucun standard de programmation utilisateur, bibliothèque fournie, programme client ou note privée ne doit entrer dans Git ou une distribution publique. Les conserver dans un emplacement privé hors des packages publics ; `.gitignore` seul ne protège pas un paquet. `public-distribution.json` énumère les fichiers autorisés, contrôlés par les builds wheel/sdist et les constructeurs de kits. Ne pas remplacer cette liste par une copie récursive.

Réutiliser les composants présents. Le serveur d'ingénierie reste Czarnak `TiaMcpServer` **4.3.0** épinglé ; les références et licences sont dans `integrations/upstream.lock.json` et `THIRD_PARTY_NOTICES.md`. Lire le contrat de la version épinglée avant de changer son intégration.

Depuis 0.2.0, le profil V21 utilise le paquet amont et le profil V20 prépare un portage de la même source, à compiler sur Windows contre les vraies DLL V20. Voir `docs/TIA_VERSIONS.md`. Exiger le manifeste de profil pour les deux versions, préserver le chemin Openness aux lancements et ne jamais prendre des références factices ou un build V21 pour une preuve V20. La compilation et l'acceptation Siemens restent distinctes des tests locaux.

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

Si le chantier utilise `.dev-loop/logbook.md`, le relire intégralement à chaque itération. Chaque worker ajoute ses fichiers, décisions, commandes, résultats, limites et suite ; seul l'orchestrateur actualise la section State. Ce journal reste privé, ignoré par Git et exclu des livraisons. Ne pas y placer de secrets. Les changements publics vont dans `PUBLIC_CHANGELOG.md`.

Utiliser les verrous de dépendances. Reproduire un défaut avant correction quand c'est possible, puis tester le comportement observable et les frontières touchées. Pour une modification documentaire seule, vérifier les liens, l'exactitude et l'assemblage ; ne pas annoncer de nouvelle exécution de tests qui n'a pas eu lieu.

Construire le frontend, copier ses assets avec `scripts/build-web.py`, puis tester le bundle livré. `npm test` est la suite complète ; `npm run test:e2e` ne lance que `workbench.spec.ts`. Les suites navigateur utilisent des données temporaires, jamais une instance contenant les essais utilisateur.

Conserver les preuves 0.1.1. Placer les nouvelles preuves dans un sous-dossier daté et consigner la plateforme, le commit ou l'état de travail, les commandes et le résultat. Un mock TIA ou un serveur asyncua local ne qualifie pas Siemens ; un workflow présent ne prouve pas son exécution.

## À chaque interruption ou livraison

Actualiser l'état courant dans `docs/codex/ETAT_REPRISE.md` et ajouter une note datée dans `docs/codex/sessions/` : fichiers modifiés, état Git, tests exécutés, blocages, prochaine action précise et commandes nécessaires. Ne pas inscrire de secrets. Des instructions initiales sont disponibles dans `docs/codex/PROMPT_CODEX.md`, et le prompt de continuation dans `docs/codex/PROMPT_REPRISE_CODEX.md`.
