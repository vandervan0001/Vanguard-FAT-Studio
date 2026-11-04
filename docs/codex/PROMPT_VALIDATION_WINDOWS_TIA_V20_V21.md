# Prompt de reprise sur Windows — validation TIA V20/V21

Reprends Vanguard FAT Studio sur ce PC Windows et termine la validation native de l'intégration TIA Portal V20/V21. Continue le projet existant, corrige les défauts démontrés et conserve les preuves. Ne t'arrête pas à un plan ou à un inventaire.

## Référence et lecture initiale

Le dépôt est https://github.com/vandervan0001/Vanguard-FAT-Studio. Utilise le clone actuel s'il existe. Sinon, clone-le dans un nouveau dossier accessible en écriture. Vérifie la visibilité et l'authentification actuelles avant de pousser. Ne remplace aucun dossier existant. Vérifie la branche, `git status`, les changements locaux, les derniers commits et le remote avant de travailler. Préserve les modifications et les données. Évite les resets destructifs, stash et nettoyages globaux.

Lis `AGENTS.md`, `KB.md`, `README-CODEX.md`, `docs/codex/ETAT_REPRISE.md` et la dernière note de session, puis `docs/TIA_VERSIONS.md`, `docs/TIA_MCP.md`, `docs/COMPATIBILITY.md`, `docs/PLCSIM_SETUP.md` et `docs/ACCEPTANCE.md`. Utilise les outils Windows disponibles ; l'absence d'un outil propre au précédent Mac ne bloque pas la reprise.

La référence livrée est **0.2.1**, tag `v0.2.1`, commit `6c854ddc4c04643647f522e75b7c98c835aa8ea5`. Le code applicatif testé est `b55bfded63dc5572da8d3409409210381cc50c34` ; le commit suivant ajoute seulement documentation et preuves. La CI `41471993176` a réussi **418 tests Python et 33 tests frontend sur chacun des systèmes Windows et Ubuntu**, sans test ignoré. L'installation d'un kit runtime Windows neuf sans index pip a aussi réussi. Les preuves sont dans `evidence/reprises/2026-11-02-windows-ci/`. Vérifie les changements ultérieurs avant de réutiliser ces résultats ; ne déplace aucun tag existant.

**Reste à faire :** le build natif du candidat V20, l'installation et le fonctionnement réels Openness/MCP pour chaque version, puis les échanges et scénarios Siemens sur une instance virtuelle isolée. Un mock, une démo, un `doctor` réussi ou une compilation seule ne clôt pas cette qualification.

## 1. Préparer le poste et les copies

Relève Windows/build/architecture, Python **3.12 x64**, Git, les versions TIA et leurs Updates, Openness, PLCSIM Advanced et ses Updates, ainsi que les CPU/firmwares disponibles. Vérifie le SDK .NET **10.0.400 ou supérieur stable dans la branche 10.0**, .NET Framework **4.8**, les références de compilation net48 requises par V20 et l'appartenance effective au groupe **Siemens TIA Openness**.

Prépare les dépendances verrouillées depuis la copie source avec `scripts/setup.ps1 -Engineering`. Node.js **22** et les dépendances de développement ne sont nécessaires que si les changements ou contrôles l'exigent. Respecte les politiques IT ; ne modifie pas globalement les stratégies PowerShell ni les protections du poste. Signale un prérequis absent avec son diagnostic précis ; continue les tâches indépendantes.

Identifie les projets et instances TIA déjà ouverts. Travaille uniquement sur des **copies standalone dédiées** dans des dossiers sandbox distincts V20 et V21, ouvertes et sauvegardées par leur version TIA respective. Ne convertis ni n'écrase l'original. Demande le chemin de la copie autorisée s'il ne peut pas être établi. Si une version, une licence ou PLCSIM manque, marque les essais correspondants **non exécutés** et qualifie ce qui est disponible ; n'installe pas un produit Siemens ni une licence en supposant mon accord ou leur disponibilité.

## 2. Installer et prouver chaque profil

Utilise séparément, pour chaque version présente :

```powershell
.\scripts\install-tia-mcp.ps1 -TiaVersion V20
.\scripts\install-tia-mcp.ps1 -TiaVersion V21
```

V21 utilise Czarnak **TiaMcpServer 4.3.0** épinglé. V20 prépare le portage de sa source au commit **10c5de2eb44c0362792cd141370b3f42f92f6ecd** et doit compiler contre les trois DLL Siemens **réelles V20**. Vérifie `Siemens.Engineering.Base.dll`, `Siemens.Engineering.Step7.dll` et `Siemens.Engineering.WinCCUnified.dll` : dossier commun, identité, version majeure et SHA-256. Pour un chemin non standard, utilise `-OpennessDirectory`.

Conserve les profils séparés : V20 `.tools\tia-mcp-v20\TiaMcpServer.exe`, V21 `.tools\tia-mcp-v21\tia-mcp.exe`. Vérifie `--version`, `doctor` et le manifeste `fat-tia-profile.json` par les contrôles du dépôt. Préserve une installation existante non conforme et choisis une destination neuve au besoin. Aucun stub, DLL d'une autre version, faux manifeste ou repli V21 ne vaut build V20.

En cas d'incompatibilité API V20, conserve les logs complets, reproduis et corrige l'adaptation dans le dépôt, avec un test pertinent ; une modification isolée du clone temporaire ne constitue pas une correction livrée. Préserve la révision amont, la licence et les contrôles de transformation, de restauration net48 et de version. Si le portage ne peut pas être rendu fonctionnel avec les API réelles, indique le blocage exact sans annoncer la compatibilité acquise.

## 3. Valider Openness et Codex en lecture seule

Configure la copie exacte avec `integrations.tia_engineering configure`, `--tia-version` et une politique distincte dans `.local\tia\v20\policy.json` ou `.local\tia\v21\policy.json`, selon les exemples du guide. Vérifie le chemin réellement attaché, puis `status`, l'arbre complet, les tables de tags et l'export d'un bloc SCL et d'un DB représentatifs. Compare le contenu à TIA ; teste aussi la représentation LAD/FBD si le projet l'utilise.

Intègre le fragment `codex.v20.mcp.toml` ou `codex.v21.mcp.toml` dans la configuration effective de Codex, sans supprimer les autres serveurs et en conservant sa section `env`. Elle fixe le dossier Openness vérifié. Garde **`--access-mode read-only`** et les noms MCP distincts. Recharge les connexions si nécessaire et prouve un appel réel du client Codex ; un fichier TOML généré ne suffit pas. Vérifie que les outils d'écriture et de compilation sont absents du client IA. Respecte les règles de confidentialité des sources du projet.

## 4. Exécuter les essais d'ingénierie contrôlés

Prépare et exécute **E1–E6** de `docs/ACCEPTANCE.md` pour chaque version : lecture fidèle, proposition refusée sans changement, import d'une modification simple relue, source périmée refusée, diagnostics d'une compilation volontairement erronée et restauration réelle de l'archive dans un autre dossier. Utilise `.ap20/.zap20` pour V20 et `.ap21/.zap21` pour V21. Vérifie aussi le refus des profils/propositions croisés, sans effectuer d'import sur une mauvaise version.

Prépare les diff, cibles, hashes et commandes avant l'étape humaine. **Tai saisit personnellement les confirmations interactives** d'activation, application, archivage, compilation et sauvegarde prévues par le CLI. Ne les saisis pas à sa place, ne les fournis pas par pipe, ne modifie pas la politique à la main pour les éviter et n'expose pas le CLI d'écriture comme outil IA. En attendant une confirmation, poursuis les préparations indépendantes. Après un import interrompu ou une erreur de compilation, inspecte l'état TIA et le reçu avant toute nouvelle tentative : le projet peut rester modifié en mémoire.

## 5. Qualifier le banc avec Siemens

Si l'instance virtuelle et la copie autorisée sont disponibles, exécute les sections **A–D** applicables du protocole. Relève les vrais endpoint, namespace, ApplicationUri, NodeIds, types, droits et certificats ; ne prends pas les exemples pour des valeurs découvertes. Vérifie les préconditions réseau et l'absence de route vers la production avant d'autoriser la cible exacte.

Observe dans TIA les BOOL/REAL et, si utilisés, INT/DINT ; compare les valeurs, la logique consommatrice et les traces Float32. Vérifie les commandes venant du PLC, les scénarios et défauts, la perte de communication sans reprise automatique, pause/reprise/arrêt et la charge représentative du poste. Pour toute préparation Siemens nécessitant un téléchargement vers la CPU virtuelle ou un RUN/STOP, prépare la procédure et laisse l'opérateur agir dans l'outil Siemens. N'utilise aucune cible physique ou de production et ne contourne aucun interverrouillage.

Contrôle le choix V20/V21 dans l'interface FAT : sauvegarde, réimport et verrouillage pendant un essai. Ce choix ne convertit pas un projet TIA. Pour les essais de communication, le PLC reste le contrôleur ; un résultat du contrôleur de démo ne remplace pas celui du programme Siemens. Libère les forçages de test et constate les états finaux ; ne crée aucune réception ou signature humaine à ma place.

## 6. Corriger, documenter et livrer

Pour tout défaut démontré, préserve la source avant édition, apporte une correction minimale, fais-la relire et rejoue les contrôles touchés. Si le code évolue, valide aussi le build et le paquet réellement installé ; si l'interface change, reconstruis et contrôle ses assets. Réutilise les résultats encore pertinents sans répéter tout le banc pour une édition documentaire seule. Ne désactive pas un contrôle pour obtenir du vert.

Conserve un rapport **séparé pour V20 et V21**, dans un nouveau dossier daté sous `evidence/reprises/`, avec commit/état local, OS, versions, DLL et profils, commandes, observations, diagnostics, reçus et preuves de restauration. Chaque essai reçoit **réussi / échoué / non exécuté**, avec sa preuve et la prochaine action. Distingue build natif, lecture MCP depuis Codex, ingénierie, communication OPC UA et validation du programme client. Les journaux ou archives peuvent contenir des sources privées : garde les bruts localement et ne pousse que les preuves relues sans secrets, DLL Siemens ni projet client.

Actualise `docs/codex/ETAT_REPRISE.md` et une note de session. Committe seulement tes chemins explicites après relecture du diff indexé, avec un message passé par fichier. Pousse les corrections et preuves admissibles dans le dépôt et vérifie les références distantes. Si la version applicative change, applique la procédure de version du dépôt sans déplacer les anciens tags.

Termine par un bilan factuel V20/V21 : ce qui fonctionne réellement, les essais non exécutés, les blocages et l'action humaine restante. Arrête uniquement les services temporaires que tu as lancés, conserve les données et indique les processus/ports restants. Ne ferme pas une session TIA avec des changements non sauvegardés et n'archive pas le chat.

Commence maintenant par vérifier le clone, le poste Windows et les versions Siemens disponibles, puis poursuis jusqu'à terminer le périmètre accessible.
