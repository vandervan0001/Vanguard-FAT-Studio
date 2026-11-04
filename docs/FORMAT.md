# Formats des projets, scénarios et archives FAT

JSON est le format canonique des données. Il se lit dans un éditeur, se génère par une IA et se valide avec JSON Schema. Le builder et l'éditeur JSON décrivent les mêmes objets ; aucun langage de script ou code téléchargé n'est exécuté pendant l'import. ZIP sert uniquement de conteneur pour un dossier de projet et ses preuves.

## Projets

Un export de projet utilise cette enveloppe :

```json
{
  "format": "fat-studio/project",
  "version": "1.0",
  "project": {
    "schema_version": "1.0",
    "id": "mon-banc",
    "name": "Mon banc FAT",
    "equipment": [],
    "connections": [],
    "tags": [],
    "scenarios": []
  }
}
```

Ce brouillon vide est enregistrable ; il ne peut pas démarrer un échange avant d'avoir les associations nécessaires. Le schéma complet est [project-package.schema.json](../examples/project-package.schema.json). Le projet contient le P&ID, les paramètres physiques, les tags, leurs types/sens/plages, les associations, les animations et les scénarios. Les anciens projets JSON plats avec `schema_version` restent importables. Une version ou un format inconnu est refusé.

Les symboles PLC, adresses mémoire et NodeIds OPC UA sont distincts. Une adresse `%IW264` ne permet pas de deviner son NodeId. Les entrées sont vues depuis le PLC : le banc leur transmet le procédé simulé. Les sorties PLC sont lues par le banc et ne sont pas forçables. Un import ne crée aucune autorisation de cible du poste.

## Scénarios

Un paquet peut contenir une ou plusieurs FAT. Exemple minimal de FAT guidée pour les tags de la démo publique :

```json
{
  "format": "fat-studio/scenarios",
  "version": "1.0",
  "scenarios": [
    {
      "id": "essai-manuel-p101",
      "name": "Demande manuelle P-101",
      "execution_mode": "guided",
      "preconditions": "Arrêt relâché, nouveau modèle, aucune demande active.",
      "fat_steps": [
        {
          "id": "ouvrir-et-demander",
          "name": "Ouvrir l'arrivée et demander la pompe",
          "instructions": "Appliquer puis attendre deux cycles d'échange.",
          "expected_result": "La commande de P-101 passe à TRUE.",
          "actions": [
            {"action": "force", "target": "xv101_request", "value": true},
            {"action": "force", "target": "p101_request", "value": true}
          ],
          "checks": [
            {"target": "p101_command", "operator": "eq", "value": true}
          ]
        }
      ]
    }
  ]
}
```

L'[exemple complet exporté](../examples/demo-scenarios.json) inclut aussi les `tag_contracts` et `equipment_contracts`. Ces contrats déclarent identifiant, sens, type, unité, conversion analogique et type d'équipement. L'import contrôle leur compatibilité et les références avant d'appliquer le paquet. Un paquet minimal écrit à la main peut omettre les contrats ; ses actions doivent quand même être valides pour le projet destinataire. Ajouter refuse les identifiants déjà présents ; Remplacer est un choix explicite et conserve l'ancien essai dans l'historique si le projet était en pause.

`execution_mode: timed` utilise `steps`, une liste ordonnée contenant `at_s`, `action`, `target`, `value`, `operator`, `tolerance` et `message`. Le temps `at_s` et la durée `duration_s` sont en secondes simulées. Les actions sont `force`, `release`, `fault`, `clear_fault`, `marker` et `expect`. Les valeurs des écritures temporisées sont natives au type PLC déclaré. Un défaut décrit son `kind` et éventuellement sa `value`.

`execution_mode: guided` utilise `fat_steps`. Chaque STEP possède des instructions et un résultat attendu libres, plusieurs actions `force`/`release` et des contrôles facultatifs. Une action préparée peut utiliser `unit: native`, `mA`, `V`, `engineering` ou `percent`, et un diagnostic explicite. Exemple : `target: lt101_raw`, `value: 12`, `unit: mA` représente 13 824 bruts pour la plage 4–20 mA de la démo. Les types, limites et profils restent contrôlés côté serveur.

Exécuter un STEP ne prononce pas sa conformité. Le testeur observe puis enregistre son résultat ; la conclusion FAT globale reste séparée. Le format ne revendique pas une conformité GRAFCET/IEC 60848.

Schéma : [scenario-package.schema.json](../examples/scenario-package.schema.json). Il est aussi accessible depuis le serveur par `GET /api/schemas/scenarios`, comme celui des projets par `GET /api/schemas/project`.

## Animations et édition en pause

Les `bindings` d'un objet relient ses rôles physiques aux tags. L'option `animation` est une association visuelle indépendante : `tag_id`, `operator`, `value`, `effect`, `min`, `max`, `active_color` et `inactive_color`. Pour un BOOL, choisir `eq` ou `ne` avec `true` ou `false`. Pour un nombre, les comparaisons usuelles sont disponibles. Les effets sont `highlight`, `pulse`, `rotate`, `level` et `position` ; les deux derniers ramènent la plage min/max à 0–100 %. Les couleurs sont hexadécimales `#RRGGBB`.

Une animation ne modifie ni le modèle physique ni une commande PLC. Un tag inconnu, un type incompatible ou une plage invalide est signalé par la validation. Une qualité indisponible n'est pas affichée comme une mesure saine.

En cours d'essai, la structure est figée et les commandes de test sont disponibles. En pause, le builder revient. Sans modification, Reprendre poursuit l'essai. Appliquer un brouillon en pause termine l'ancien essai sans inventer son verdict, en conserve les preuves et ouvre une révision au repos ; un nouveau démarrage est nécessaire.

## Dossiers et archives

Un répertoire local contient les projets lisibles et l'historique SQLite du banc. Le CLI permet de créer un dossier dédié :

```powershell
.\.venv\Scripts\python.exe -m fat_studio new-project "C:\FATProjects\Mon banc" --name "Mon banc" --demo
.\.venv\Scripts\python.exe -m fat_studio serve --data-dir "C:\FATProjects\Mon banc"
```

L'archive `.fat.zip` embarque une sélection finie : projet, scénarios, correspondances et preuves JSON/CSV/HTML de ses essais, avec manifeste SHA256. Elle n'inclut pas les autres projets, la base globale brute, les licences, clés ou politiques d'accès. Les bornes, la restauration dans un nouveau dossier et la vérification d'intégrité sont décrites dans [PROJECT_ARCHIVES.md](PROJECT_ARCHIVES.md).

Un espace restauré reste au repos. Son identité d'édition est distincte de l'original même si les données sont identiques ; les commandes d'un ancien onglet sont refusées. Le dossier actif est conservé au redémarrage. Les historiques déjà reçus ne deviennent pas des essais réexécutés.

## Commandes IA

Le client local propose `project-export`, `scenarios-export`, `scenarios-import`, `archive-export`, `archive-import`, `workspaces`, `workspace` et `workspace-open`. Les options globales `--url` et `--context` précèdent la commande. Capturer explicitement `context` après lecture du banc ; les lectures ne remplacent jamais le contexte attendu. Les exports refusent d'écraser un fichier existant, les imports refusent un contexte périmé et aucun conflit n'est réessayé automatiquement. Voir [AI_CONTROL.md](AI_CONTROL.md) pour le protocole et [AI_QUICKSTART.md](AI_QUICKSTART.md) pour le prompt de mise en route.
