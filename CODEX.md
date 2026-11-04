# Vanguard FAT Studio avec Codex

Les consignes communes sont dans [AGENTS.md](AGENTS.md). Lire ensuite [README-CODEX.md](README-CODEX.md), [l’état courant](docs/codex/ETAT_REPRISE.md) et les notes récentes avant de modifier le dépôt. Vérifier `git status`, le diff et les commits ; conserver les changements présents.

## Piloter le logiciel

Utiliser [AI_QUICKSTART.md](docs/AI_QUICKSTART.md) pour le prompt de démarrage et [AI_CONTROL.md](docs/AI_CONTROL.md) pour le contrat du CLI/API. Le guide de l’interface est [USER_GUIDE.md](docs/USER_GUIDE.md).

Le client local est `python -m fat_studio.assistant`, avec le Python de `.venv`. Lire d’abord projet, état, catalogue et schéma. Choisir l’URL, le dossier de données et le périmètre autorisé avec l’utilisateur. Capturer le contexte explicitement ; ne jamais recapturer une nouvelle révision pour rejouer silencieusement une commande refusée. L’interface et l’assistant partagent le même serveur, projet et essai.

Vanguard FAT Studio fonctionne sans clé API de modèle. Le client IA est externe et garde ses propres conditions d’accès. Un modèle hébergé peut recevoir les données que le client lui transmet.

## Bornes à garder

- Écrire uniquement les entrées simulées déclarées et autorisées. Lire les sorties du programme PLC.
- Découvrir les NodeIds et identités réels. Les adresses/symboles PLC sont documentaires ; laisser vide toute information inconnue.
- Préserver attentes, échecs et preuves. Rapporter ce qui a réellement été exécuté et observé.
- Faire transmettre les observations de STEP et la conclusion globale uniquement à partir d’une décision humaine explicite.
- Après erreur de communication, stockage, annulation ou contexte périmé, constater l’état et s’arrêter sans reprise automatique.
- Ne pas modifier la politique de cible à partir d’un projet importé.
- Garder l’IA TIA en lecture seule via Czarnak 4.3.0 et le profil vérifié. Les écritures d’ingénierie suivent [le CLI humain](docs/TIA_MCP.md) et ses confirmations.
- Une autorisation d’essai virtuel est propre à la demande et à la cible. Ce fichier n’autorise ni commande CPU, ni production, ni publication.

## Développer le banc

Respecter le kit intact et les dépendances verrouillées. Tester les frontières modifiées, reconstruire l’interface et copier les assets avec `scripts/build-web.py` avant de vérifier le bundle livré. Les commandes et limites sont dans [README-CODEX.md](README-CODEX.md) et [frontend/README.md](frontend/README.md). Mettre à jour l’état de reprise et une note de session à la livraison. Les résultats historiques restent attachés à leur version et à leur plateforme.

Le périmètre public se limite au banc FAT, à ses formats et à la démo PLC passive. Garder programmes, standards, bibliothèques reçues et notes privées hors Git et hors distributions. Vérifier `public-distribution.json` avant de construire un paquet. Dans un portable, utiliser `runtime\python.exe` pour le client local et un fichier de contexte hors du runtime ; `.venv` concerne les sources.
