# Contrat de pilotage local

Ce document s’adresse aux assistants et aux intégrateurs qui pilotent Vanguard FAT Studio. Le [démarrage rapide](AI_QUICKSTART.md) donne un parcours utilisable sans écrire de client HTTP. Le [guide utilisateur](USER_GUIDE.md) décrit les effets des commandes et leur observation.

Le service sert son interface et son API sur une adresse de boucle locale. L’URL par défaut est `http://127.0.0.1:8765`. Découvrir la version et les contrats de l’instance en cours avant d’agir :

| Lecture | Réponse |
| --- | --- |
| `GET /api/health` | Version applicative et version du schéma |
| `GET /api/openapi.json` | Routes et modèles de requêtes actifs |
| `GET /api/schema` | Schéma JSON du projet de cette version |
| `GET /api/catalog` | Types d’équipements, ports, paramètres et défauts |
| `GET /api/project` | Projet actif et en-tête `X-FAT-Project-Revision` |
| `GET /api/state` | Instantané du modèle et de l’essai |
| `GET /api/validate` | `valid`, `errors`, `warnings` ; aucune écriture OPC UA |

La documentation d’une ancienne version ne remplace pas cette découverte. La validation locale d’un projet ne prouve ni les NodeIds, ni les droits de la CPU, ni l’exécution d’une FAT Siemens.

## CLI pour les assistants

Depuis la racine du dossier, utiliser le Python de son environnement :

```powershell
.\.venv\Scripts\python.exe -m fat_studio.assistant --help
.\.venv\Scripts\python.exe scripts/fat-api.py --help
```

Ces deux points d’entrée appellent le même module. Sous Linux/macOS, remplacer le chemin Python par `.venv/bin/python`. Dans un portable, utiliser `runtime\python.exe -B -X utf8 -m fat_studio.assistant` et un contexte hors du runtime. Le module est aussi disponible dans le paquet Python installé qui l’embarque ; le wrapper `scripts/fat-api.py` appartient aux sources.

Options globales, à placer avant la commande : `--url URL` (par défaut `http://127.0.0.1:8765`) et `--context CHEMIN` (par défaut `.local/ai-context.json`). Le tutoriel utilise le port8767 et un contexte explicite dans `%LOCALAPPDATA%/FATStudio/AI-Demo`. Le client exige une URL HTTP avec IP loopback et port explicites, par exemple `127.0.0.1` ou `[::1]`, sans identifiant, chemin, proxy ni redirection. Le nom `localhost` n’est pas accepté par ce client. Ne pas créer un proxy public du banc.

| Commande | Fonction |
| --- | --- |
| `context` | Capture volontaire du projet/révision/essai attendus |
| `health`, `state`, `project`, `catalog`, `schema`, `validate`, `runs` | Lectures JSON |
| `demo`, `pilot` | Charge l’exemple TK-101 ou le laboratoire public dans le banc éditable |
| `project-export --output FICHIER` | Exporte l’enveloppe projet versionnée |
| `scenarios-export --output FICHIER [--scenario ID]` | Exporte les scénarios et contrats utilisés |
| `scenarios-import FICHIER --mode MODE` | Ajoute sans collision ou remplace explicitement les scénarios |
| `archive-export --output FICHIER.fat.zip` | Capture projet et historique sélectionné |
| `archive-import FICHIER.fat.zip` | Restaure dans un nouvel espace, au repos |
| `workspaces`, `workspace` | Lit les espaces locaux ou l’espace actif |
| `workspace-open ID` | Ouvre explicitement un espace existant, sans démarrer d’essai |
| `load-project FICHIER` | Charge un JSON de projet, sans autoriser de cible |
| `start [--scenario ID] [--target-confirmation TEXTE]` | Ouvre un nouvel essai ; sans scénario, essai libre |
| `pause`, `resume`, `stop`, `reset` | Commandes du modèle et des échanges FAT |
| `force --tag ID --value JSON` | Force une entrée dans son type et son unité natives |
| `stimulus --tag ID --value JSON --unit UNITÉ [--diagnostic]` | Force avec conversion déclarée et mode diagnostic explicite |
| `release --tag ID` | Libère le forçage de l’entrée |
| `pulse --tag ID --value true\|false [--duration-ms 300]` | Impulsion BOOL ; la valeur est explicite |
| `step-execute ID` | Déclenche le prochain STEP de la FAT guidée |
| `step-observe ID --verdict pass\|fail [--observation TEXTE]` | Transmet l’observation et le choix explicitement fournis par le testeur |
| `marker TEXTE` | Ajoute un marqueur à l’essai courant |
| `export --run ID --kind json\|csv\|report --output FICHIER` | Télécharge un instantané de cet essai précis |

Les valeurs JSON sont strictes : `true` est un booléen, `13824` un entier et `"13824"` une chaîne refusée pour un INT. Les sorties normales sont du JSON ; une erreur est écrite sur stderr avec le code de sortie 2. Le client n’évalue pas le verdict global de FAT. Un export existant n’est pas écrasé ; choisir un nouveau nom pour chaque capture.

`pulse` applique la valeur booléenne fournie pendant 100 à 2 000 ms simulées (300 par défaut), puis restaure le forçage antérieur ou rend le signal au modèle. Pour reproduire le clic du pupitre, choisir la valeur inverse du contact observé : un contact normalement fermé à TRUE reçoit FALSE pour son impulsion. Le retour est géré par le serveur.

### Contexte conservé par le CLI

`context` sert à choisir explicitement l’état sur lequel travailler. Le fichier contient l’URL et l’identité projet/révision/essai, sans jeton de session, mot de passe ou clé privée. Avant une mutation, le client vérifie ce contexte puis fournit aussi les en-têtes de contexte au serveur. Les gardes du serveur couvrent le changement concurrent survenu entre ces deux opérations pour les routes gardées.

L’interface navigateur peut retenir un accord de cible pour les essais explicitement choisis par le testeur, dans cet onglet et sur cette révision du projet. Cet accord ne modifie ni le contrat HTTP ni le CLI : chaque démarrage OPC UA fournit toujours `target_confirmation` et repasse les contrôles de cible. Il ne constitue aucune autorisation pour un assistant externe de lancer d’autres essais. Voir le [parcours de confirmation dans le guide utilisateur](USER_GUIDE.md#11-raccorder-une-cpu-virtuelle-par-opc-ua).

Après une mutation réussie, le client conserve le contexte renvoyé par cette opération, notamment le nouvel essai de `start`. Une lecture de `state` n’avance jamais cette référence. Sur conflit ou erreur, le client s’arrête sans recapture ni réessai automatique. Lire le projet et l’état, préserver les brouillons, puis recapturer seulement après avoir choisi volontairement la nouvelle situation.

Les routes de sélection de projet (`demo`, `pilot`, `load-project`) changent explicitement le projet actif et vérifient le même contexte attendu que les autres mutations. Un changement concurrent de projet, de révision ou d’essai bloque aussi cette sélection. Pour modifier le projet actuel, utiliser `PUT /api/project` avec sa révision de base ; l’import ne contourne pas un conflit.

## Session et contexte HTTP

Chaque requête de mutation exige un jeton obtenu par `GET /api/session`, dans `X-FAT-Token`. Le jeton change au redémarrage du serveur. Garder sa valeur en mémoire ; ne pas l’imprimer dans les preuves ni le committer. Il protège contre les mutations issues d’une page externe ; il ne constitue pas un compte utilisateur ou un secret de modèle IA.

Une requête d’écriture du client doit fournir :

| En-tête | Valeur attendue |
| --- | --- |
| `X-FAT-Token` | `token` de la session locale active |
| `X-FAT-Project-ID` | `id` du projet sélectionné |
| `X-FAT-Project-Revision` | En-tête reçu d’une lecture/sauvegarde réussie du projet |
| `X-FAT-Run-ID` | Essai visé, ou chaîne vide pour affirmer l’absence d’essai courant |

Les trois derniers en-têtes de contexte restent optionnels côté serveur pour compatibilité avec les anciens clients. **Un assistant doit les utiliser.** L’absence d’un en-tête ne vaut pas vérification. En particulier, un `X-FAT-Run-ID` vide signifie « aucun essai courant », tandis que son omission saute ce contrôle.

La révision est le SHA-256 du JSON canonique du projet. La recevoir depuis `GET /api/project` ou une réponse de projet réussie ; ne pas remplacer la référence attendue par la révision d’un simple polling d’état.

Le serveur compare les en-têtes de contexte fournis sous son verrou avant toute mutation : commandes d’essai, sauvegarde/mapping, création, import et chargement de projet, y compris démo et laboratoire. Projet, révision et essai doivent correspondre, même si un en-tête présent est explicitement vide. `GET /api/mapping` vérifie aussi le projet et la révision fournis. Ces protections n’autorisent aucune nouvelle cible.

Les en-têtes restent optionnels côté serveur pour les clients historiques ; un client qui les omet perd la garde correspondante. Le client IA public les transmet toujours, y compris pour `/api/project/import`, `/api/projects`, `/api/projects/{id}/load`, `/api/demo/load` et `/api/pilot/load`. Ces opérations exigent aussi le jeton et un banc éditable. La réponse réussie fournit le nouveau contexte ; une réponse 409 conserve celui que le client attendait et ne déclenche aucun rejeu automatique.

Les requêtes doivent rester sur l’URL locale. Le serveur refuse un Host externe, une origine externe et les requêtes cross-site. Aucun navigateur n’accède directement au PLC.

### Exemple HTTP direct en PowerShell

Cet exemple vise le serveur **isolé de démonstration** du tutoriel, déjà ouvert et au repos. Dans son interface, utiliser d’abord **Ouvrir → Charger le laboratoire**. Le bloc lit un contexte cohérent puis démarre un essai libre sur ce laboratoire. Il n’importe aucun projet et n’autorise aucune cible :

```powershell
$FatUrl = 'http://127.0.0.1:8767'
$FatProjectResponse = Invoke-WebRequest -UseBasicParsing "$FatUrl/api/project"
$FatProject = $FatProjectResponse.Content | ConvertFrom-Json
$FatRevision = [string]$FatProjectResponse.Headers['X-FAT-Project-Revision']
$FatState = Invoke-RestMethod "$FatUrl/api/state"
if ($FatState.project_id -ne $FatProject.id -or $FatState.project_revision -ne $FatRevision) {
    throw 'Le projet a changé pendant la lecture ; relire avant toute mutation.'
}
if ($FatProject.id -ne 'public-io-lab' -or $FatProject.plc.mode -ne 'demo' -or $FatState.status -in @('running', 'paused')) {
    throw 'Ce tutoriel exige le laboratoire en démonstration au repos.'
}
$FatToken = (Invoke-RestMethod "$FatUrl/api/session").token
$FatHeaders = @{
    'X-FAT-Token' = $FatToken
    'X-FAT-Project-ID' = $FatProject.id
    'X-FAT-Project-Revision' = $FatRevision
    'X-FAT-Run-ID' = [string]$FatState.run_id
}
$FatStarted = Invoke-RestMethod "$FatUrl/api/run/start" -Method Post -Headers $FatHeaders -ContentType 'application/json' -Body '{}'
$FatHeaders['X-FAT-Run-ID'] = [string]$FatStarted.run_id
```

Pour les commandes suivantes, conserver ce contexte, contrôler la réponse et ne pas poursuivre après une erreur. Une réponse HTTP perdue après mutation peut signifier que l’action a déjà eu lieu ; lire l’état avant de décider de la suite.

Exemples sur le laboratoire chargé et démarré en essai libre :

```powershell
Invoke-RestMethod "$FatUrl/api/force/pulse" -Method Post -Headers $FatHeaders -ContentType 'application/json' -Body '{"tag_id":"p101_request","value":true,"duration_ms":300}'
Invoke-RestMethod "$FatUrl/api/force" -Method Post -Headers $FatHeaders -ContentType 'application/json' -Body '{"tag_id":"lt101_raw","value":13824}'
Invoke-RestMethod "$FatUrl/api/force/lt101_raw" -Method Delete -Headers $FatHeaders
Invoke-RestMethod "$FatUrl/api/run/stop" -Method Post -Headers $FatHeaders -ContentType 'application/json' -Body '{}'
```

Ces identifiants appartiennent au laboratoire fourni. Pour un autre projet, utiliser les identifiants réellement lus par `/api/project` ; ne pas les déduire d’un nom d’équipement.

## Routes de projet et d’essai

| Méthode et chemin | Corps / résultat |
| --- | --- |
| `PUT /api/project` | Projet complet ; sauvegarde gardée par son contexte |
| `POST /api/project/import` | Enveloppe projet1.0 ou ancien projet compatible ; sélection explicite |
| `POST /api/projects` | `{"name":"Nom"}` ; nouveau projet vide |
| `GET /api/projects` | Liste des projets enregistrés |
| `POST /api/projects/{id}/load` | Charge ce projet enregistré |
| `POST /api/demo/load` / `/api/pilot/load` | Charge l’exemple correspondant |
| `GET /api/project/download` | Enveloppe JSON `fat-studio/project`, version1.0 |
| `GET /api/scenarios/export?scenario_id=ID` | Enveloppe des scénarios ; paramètre facultatif |
| `POST /api/scenarios/import` | `{"package":{...},"mode":"merge"}` ou `replace` ; contrats vérifiés |
| `GET /api/workspace`, `/api/workspaces` | Espace actif ou liste des dossiers locaux |
| `POST /api/workspaces/{id}/open` | Ouvre un dossier existant sous le contexte attendu |
| `GET /api/mapping` | CSV de mapping du projet attendu |
| `POST /api/mapping` | `{"csv":"..."}` ; remplace les variables |
| `POST /api/run/start` | `{"scenario_id":"...","target_confirmation":"..."}` ; champs optionnels |
| `POST /api/run/pause`, `/resume`, `/stop`, `/reset` | Corps vide ; instantané en réponse |
| `POST /api/force` | `{"tag_id":"...","value":...}` en unité native |
| `POST /api/force/stimulus` | `{"tag_id":"...","value":...,"unit":"mA","diagnostic":false}` |
| `POST /api/force/pulse` | `{"tag_id":"...","value":true,"duration_ms":300}` |
| `DELETE /api/force/{tag_id}` | Libère le forçage |
| `POST /api/fault` | `{"equipment_id":"...","kind":"...","value":...}` ; valeur selon défaut |
| `DELETE /api/fault/{equipment_id}` | Efface les défauts de cet équipement |
| `POST /api/markers` | `{"message":"Observation"}` |
| `POST /api/result` | `{"verdict":"not_evaluated","comment":"..."}` ; décision humaine explicite |
| `GET /api/connection/policy` | Noms/endpoints autorisés, `editable_from_browser:false` |
| `GET /api/runs` | Essais archivés et résultats enregistrés |
| `GET /api/runs/{run_id}/json`, `/csv`, `/report` | Export de l’essai identifié |
| `GET /api/export/json`, `/csv`, `/report` | Export de l’essai actuellement sélectionné |

Pour un export fiable en présence de plusieurs clients, privilégier l’URL avec `run_id` capturé au démarrage. Les exports courants et par `run_id` vérifient le contexte de projet/révision/essai fourni. Une lecture de découverte peut constater un nouvel état sans avancer le baseline ; elle ne remplace pas la garde d’un téléchargement. Chaque export lit un instantané fini. Le résultat global accepte `pass`, `fail`, `not_evaluated` ; sa sauvegarde et l’événement correspondant appartiennent à une même transaction SQLite. Le CLI assistant ne propose pas une conclusion automatique.

Les forçages normaux sont acceptés sur un essai actif, en cours ou en pause, tant que le scénario n’est pas terminé. En pause, ils changent l’image locale ; les échanges attendent une reprise explicite. Une impulsion et l’exécution/observation d’un STEP demandent un essai **en cours**. La pause rend le constructeur accessible. Une sauvegarde **Appliquer en pause** termine l’ancien essai sans modifier sa conclusion humaine et conserve ses preuves ; le projet devient idle et un nouveau démarrage est requis. Une reprise sans modification continue le même essai. Les remplacements de projet restent refusés tant que l’état n’est pas éditable.

## FAT guidée

Un scénario guidé contient `execution_mode:"guided"` et `fat_steps`. Les scénarios historiques omettant ce champ restent `timed` avec leur liste `steps`. Les deux modes sont distincts ; un scénario guidé ne démarre aucune de ses écritures avant `execute`.

Exemple de scénario à inclure dans le laboratoire, avec identifiants déjà connus :

```json
{
  "id": "check-level",
  "name": "Vérifier le niveau à mi-échelle",
  "execution_mode": "guided",
  "requirement": "Exigence à renseigner",
  "preconditions": "Laboratoire au repos, aucun défaut",
  "focus_equipment": ["LT101", "TK101"],
  "trend_tags": ["lt101_percent", "lt101_raw"],
  "duration_s": 120.0,
  "steps": [],
  "fat_steps": [
    {
      "id": "level-mid",
      "name": "Présenter 12 mA",
      "instructions": "Exécuter, attendre la réaction puis lire le niveau ingénierie.",
      "expected_result": "Le niveau ingénierie atteint 50 %.",
      "actions": [{"action":"force","target":"lt101_raw","value":12,"unit":"mA"}],
      "checks": [{"target":"lt101_percent","operator":"eq","value":50.0,"tolerance":0.1}]
    },
    {
      "id": "level-release",
      "name": "Rendre la mesure au modèle",
      "instructions": "Libérer puis constater la valeur de procédé.",
      "expected_result": "LT101_Raw n’est plus forcé.",
      "actions": [{"action":"release","target":"lt101_raw"}],
      "checks": []
    }
  ]
}
```

Les actions acceptent `force`/`release`. Une action de forçage numérique peut utiliser `native`, `mA`, `V`, `engineering` ou `percent` selon la déclaration du tag. Le mode `diagnostic` est explicite. Les contrôles restent en unité native de leur tag et acceptent `eq`, `ne`, `gt`, `ge`, `lt`, `le`, avec une tolérance absolue pour `eq`/`ne` numérique. Les métadonnées `requirement`, `preconditions`, `focus_equipment` et `trend_tags` préparent l’observation ; elles n’inventent pas de contrôle.

| Appel | Condition et effet |
| --- | --- |
| `POST /api/run/start {"scenario_id":"..."}` | Ouvre l’essai et fait tourner le modèle |
| `POST /api/run/steps/{id}/execute {}` | Prochain STEP uniquement, une seule fois ; actions validées ensemble avant changement local |
| `GET /api/state` | Le STEP demandé est `queued`, puis `applied` après échange réussi et échantillon enregistré |
| `POST /api/run/steps/{id}/observe` | `{"verdict":"pass","observation":"..."}` (`pass` ou `fail`) ; exige le STEP appliqué et un essai en cours |

À l’observation, les contrôles sont évalués sur les valeurs et qualités courantes. Un contrôle en échec refuse `pass`. L’observation enregistrée passe le STEP à `reviewed` et ouvre le suivant. La dernière observation termine le scénario en pause avec fermeture des échanges. Les `duration_s` des scénarios temporisés ne constituent pas une échéance de la FAT guidée.

`guided_steps` conserve les actions demandées, les valeurs converties (`raw_value`) et, après application confirmée, celles du lot transmis (`actual_wire_value`), ainsi que les temps, contrôles, verdicts et observations. Pendant `queued`, les commandes de forçage, libération, impulsion, stimulus et défaut sont refusées avec HTTP 409. Le passage à `applied` vérifie le lot envoyé et l’absence de forçage pour une libération ; une divergence produit `fat_step_not_applied` puis l’arrêt en erreur, sans confirmer l’application. Les nombres préparés non finis ou non représentables en double précision sont refusés par la validation d’import avant sauvegarde. Les événements restent conservés dans les preuves. Le verdict d’un STEP est un acte du testeur ; le résultat global reste `not_evaluated` jusqu’à la décision humaine explicite.

La validation locale préalable d’une image ne rend pas un lot OPC UA atomique. Un lot partiellement reçu peut avoir changé certaines entrées de la CPU ; aucune restauration automatique n’est promise.

## Mapping et format projet

Le schéma courant reste `schema_version:"1.0"` avec des champs optionnels à valeur par défaut pour les anciens projets. Les champs inconnus sont refusés. Les limites du format sont 50 équipements, 200 variables, 100 scénarios et 100 STEP guidés par scénario. Interroger `/api/schema` et `/api/catalog` plutôt que reconstruire le format depuis un exemple ancien.

Le conteneur d’échange est décrit dans [FORMAT.md](FORMAT.md) : `format:"fat-studio/project"`, `version:"1.0"` et `project`. La version du conteneur et `project.schema_version` sont distinctes. Les scénarios s’échangent avec leur contrat de tags dans une enveloppe `fat-studio/scenarios`.

Un tag contient notamment `id`, `name`, `direction`, `data_type`, `unit`, `initial_value`, `min`, `max`, `node_id`, `writable`, plus les métadonnées `plc_address`, `plc_symbol` et `signal`. Les adresses et symboles sont documentaires. L’échange utilise uniquement le NodeId découvert et validé. Un DB optimisé peut conserver un symbole sans adresse absolue. Namespace 0 est interdit après résolution aussi bien que dans un NodeId fourni directement.

Une conversion `signal` déclare `kind`, `raw_min`, `raw_max`, `engineering_min`, `engineering_max`, `engineering_unit`, et éventuellement `underflow_raw`/`overflow_raw`. `kind` accepte `4-20mA`, `0-10V` ou `linear`. Les anciens objets signal utilisent par défaut 0 à 100 % côté ingénierie. Aucun nom de tag ni aucune adresse ne crée implicitement une échelle. Consulter le [guide utilisateur](USER_GUIDE.md#déclarer-une-conversion-électrique) pour la formule et les exemples.

`diagnostic:true` autorise un stimulus hors limites nominales, tout en gardant les contrôles de finitude et de stockage PLC. Uniquement pour `unit:"mA"` et une valeur exactement 0 ou 24, les codes de profil déclarés remplacent l’extrapolation linéaire. Sans code, la conversion linéaire reste utilisée puis validée ; aucun écrêtage automatique n’est appliqué. Le laboratoire propose −32 768 et 32 767 comme codes de test, à qualifier pour le module et le programme visés. Le journal conserve demande et valeur brute ; ces codes ne valent pas simulation matérielle d’un module analogique.

L’export CSV contient :

```csv
id,name,direction,data_type,unit,initial_value,min,max,node_id,writable,plc_address,plc_symbol,signal,_fat_csv_encoding
```

`signal` est un JSON dans une cellule CSV, ou vide. Utiliser le module CSV d’un langage ou exporter une base depuis le logiciel pour respecter les guillemets. `initial_value` est un scalaire JSON, `writable` vaut exactement `true`/`false` ; les bornes vides deviennent `null`.

L’import accepte aussi les dix colonnes historiques, avec ou sans marqueur d’encodage, et le format intermédiaire avec adresses/symboles sans signal. Il remplace la liste complète des tags. Un fichier tronqué, une colonne dupliquée, une structure inconnue ou des identifiants dupliqués sont refusés.

Le marqueur `_fat_csv_encoding` vaut `apostrophe-v1`. Les textes `name`, `unit`, `node_id`, `plc_address`, `plc_symbol` reçoivent un échappement réversible des préfixes de formule de tableur et des apostrophes initiales. Conserver le marqueur et les cellules tels qu’exportés ; ne pas supprimer globalement les apostrophes. Les anciens CSV sans marqueur restent importés littéralement.

## État, erreurs et politique d’exécution

L’instantané contient `project_id`, `project_revision`, `run_id`, `status`, `sim_time_s`, `wall_time`, `connection`, `tags`, `equipment`, `faults`, `events`, `series`, `result`, `scenario`, `guided_steps`, `error`, `write_count`, `lag_ms` et `model_warnings`.

Lire pour chaque tag `value`, `quality`, `forced`. Une valeur affichée avec qualité `initial`, `paused`, `stale` ou `bad` ne constitue pas une acquisition fraîche en cours. Le front interroge l’état toutes les 500 ms ; les preuves conservent les cycles du modèle. Les REAL sont Float32 à la frontière d’échange ; le procédé interne reste en double précision et les attentes de contrôle conservent la valeur fournie.

| Réponse | Traitement attendu |
| --- | --- |
| HTTP 400/422 | Corriger la requête, le type ou le projet à partir du diagnostic |
| HTTP 403 | Vérifier session/origine ou autorisation de cible ; aucune élévation automatique de politique |
| HTTP 409 | Contexte périmé ou transition refusée ; relire sans remplacer le contexte attendu |
| HTTP 404 | Identifier la cible réellement présente ; ne pas inventer un identifiant |
| HTTP 503 | Erreur de stockage, essai interrompu pour traçabilité |
| Timeout/coupure de réponse | L’effet d’une mutation peut être incertain ; constater l’état avant toute décision |
| `status:"error"` | Écritures arrêtées, aucune reconnexion automatique ; préserver les preuves et traiter la cause |

Un jeton absent peut être redemandé après constat d’un redémarrage local. Cela n’autorise pas à rejouer automatiquement une commande dont la réponse a été perdue. Un conflit de contexte ne se résout jamais en prenant silencieusement la nouvelle révision pour réessayer.

## Frontière avec Siemens et TIA

Le runtime FAT écrit uniquement les **entrées simulées autorisées** et lit les sorties PLC. Avant les écritures OPC UA, il vérifie la politique locale, la confirmation exacte de cible, l’identité/certificat, puis les nœuds, types et droits. Un fichier projet importé ne peut pas modifier `machine-policy.json`. La commande interactive humaine `python -m fat_studio authorize-target --help` documente l’autorisation du poste ; elle ne fait pas partie du client assistant.

Pause/arrêt/reset du banc ne commandent pas RUN/STOP et ne remettent pas une CPU externe dans son état initial. Le statut transport OPC UA ne prouve pas que la CPU Siemens est en RUN. Les essais génériques asyncua et le contrôleur Python ne qualifient pas Siemens.

Pour consulter une copie de projet TIA, suivre [TIA_MCP.md](TIA_MCP.md) et [TIA_VERSIONS.md](TIA_VERSIONS.md). Le serveur reste Czarnak `TiaMcpServer 4.3.0`, avec profil V20/V21 vérifié et `--access-mode read-only` explicite côté IA. Les imports et compilations autorisés restent dans le CLI humain distinct et ses confirmations. Une autorisation ponctuelle sur une CPU virtuelle d’essai ne devient pas une permission générale des futurs utilisateurs.

Chaque résultat reste lié au programme, à la plateforme et au montage réellement exercés.

## Archives complètes et espaces locaux

`GET /api/project/archive` fournit une archive `.fat.zip` du projet sélectionné et des seuls essais de ce projet. `POST /api/project/archive/import` reçoit les octets ZIP, avec jeton et en-têtes de contexte, puis restaure dans un nouveau dossier local validé. Il retourne le `Project` restauré au repos. Aucun essai ne reprend et aucune connexion n’est activée. L’ancien espace est conservé. La capture d’archive utilise une transaction SQLite indépendante en lecture seule ; la compression se poursuit hors de la boucle HTTP, sans retenir le verrou des commandes. Les échanges et un arrêt explicite peuvent continuer pendant la génération. Le protocole et les limites sont dans [PROJECT_ARCHIVES.md](PROJECT_ARCHIVES.md).

Une révision de projet distingue aussi l’espace local : deux JSON identiques dans deux dossiers ne sont pas la même cible d’une commande. Une ouverture de l’espace déjà actif conserve son essai et son en-tête `X-FAT-Run-ID`. Le client doit garder le contexte reçu après une mutation réussie, sans fabriquer une révision ni recapturer après conflit. La politique machine reste indépendante de l’archive et du projet restauré.
