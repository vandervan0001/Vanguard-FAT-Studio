# Vanguard FAT Studio avec Claude

Appliquer les consignes communes de [AGENTS.md](AGENTS.md). Lire [README-CODEX.md](README-CODEX.md), [l’état courant](docs/codex/ETAT_REPRISE.md) et les notes de session récentes avant toute modification. Le nom historique « Codex » des documents de reprise ne limite pas leur usage à un client particulier. Inspecter `git status`, le diff et les commits ; préserver les changements présents.

## Démarrer une session de pilotage

Le prompt prêt à copier est dans [AI_QUICKSTART.md](docs/AI_QUICKSTART.md). Le contrat canonique de pilotage est [AI_CONTROL.md](docs/AI_CONTROL.md) et le mode d’emploi de l’interface est [USER_GUIDE.md](docs/USER_GUIDE.md).

Utiliser `python -m fat_studio.assistant` avec le Python `.venv`, une URL loopback et un fichier de contexte explicite. Commencer par les lectures du projet, de l’état, du catalogue et du schéma. Vérifier le périmètre de l’utilisateur et les données du serveur avant de capturer le contexte. Un autre onglet ou assistant peut changer la session ; un refus de contexte impose une relecture, sans recapture ni réessai automatique.

Vanguard FAT Studio ne demande aucune clé API de modèle et n’embarque pas de conversation IA. Votre client reste responsable de son accès au modèle et des données qu’il lui transmet.

## Contrat d’intervention

- Le programme PLC fournit les sorties ; le banc écrit uniquement les entrées simulées autorisées.
- Ne pas inventer NodeId, identité, adresse ou compilation Siemens. Un symbole et une adresse absolue ne sont pas un transport OPC UA.
- Conserver les attentes, résultats mesurés, qualités et erreurs. Une démonstration Python ou un serveur OPC UA générique ne qualifie pas Siemens.
- Les observations de STEP et le verdict global relèvent de l’humain. Transmettre ses décisions explicites sans les déduire des contrôles automatiques.
- Après erreur de communication, stockage ou annulation, aucune reprise automatique. Une écriture OPC UA partielle n’est pas annulable par le modèle.
- Un projet importé n’autorise jamais la cible sur le poste.
- Pour TIA, conserver Czarnak `TiaMcpServer 4.3.0`, le profil V20/V21 vérifié et `--access-mode read-only`. Les imports/compilations utilisent [le terminal humain](docs/TIA_MCP.md) et ses confirmations.
- Les permissions d’une CPU virtuelle d’essai restent propres à la demande et à cette cible. Aucun accès de production, contrôle CPU ou publication n’est autorisé par ce fichier.

Pour développer, respecter le kit vérifié, les locks, la séparation démo/PLC et les règles de validation de [AGENTS.md](AGENTS.md). Construire puis copier les assets avant de tester le bundle. Consigner les commandes réellement exécutées, les limites et la prochaine action dans l’état de reprise et une note de session.

Le périmètre public se limite au banc FAT, à ses formats et à la démo PLC passive. Garder programmes, standards, bibliothèques reçues et notes privées hors Git et hors distributions. Vérifier `public-distribution.json` avant de construire un paquet. Dans un portable, utiliser `runtime\python.exe` pour le client local et un fichier de contexte hors du runtime ; `.venv` concerne les sources.
