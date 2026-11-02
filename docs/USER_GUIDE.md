# Utiliser le banc FAT

## Réaliser le premier essai

1. Lancer `Start-FAT.cmd` sur Windows ou `bash scripts/start.sh` sur Linux/macOS.
2. Vérifier le bandeau **MODE FAT · DÉMONSTRATION** et le projet **TK-101 · Banc de remplissage**.
3. Dans **P&ID**, choisir **01 · Cycle de référence**.
4. Cliquer sur **Démarrer**. Observer la pompe, les vannes et le niveau de la cuve.
5. Ouvrir **Tendances & rapport** pour consulter les mesures, les assertions et le journal.
6. À la fin du scénario, saisir le verdict utilisateur et un commentaire, puis exporter CSV, rapport HTML et preuve JSON selon le besoin.

Un verdict utilisateur et les assertions automatiques restent deux informations distinctes. Le verdict n'est pas déduit de l'absence d'erreur de communication.

## Construire un projet

**Nouveau** crée un projet vide. Nommer le projet dans la barre supérieure. Dans le P&ID, déposer les équipements depuis la palette, déplacer les symboles et les relier par leurs points de connexion. Sélectionner un objet pour modifier ses propriétés. Les outils de zoom/panoramique et la grille facilitent l'édition ; Suppr efface la sélection et Ctrl+S/Cmd+S enregistre.

La bibliothèque comprend une cuve, une pompe, une vanne TOR, une vanne modulante, un capteur analogique, un capteur binaire et un indicateur. Les propriétés affichent les paramètres réels du modèle.

Pour les pompes et vannes, renseigner la cuve associée, le sens et le circuit. Les lignes de dessin ne créent pas automatiquement un modèle hydraulique. Lire [MODEL.md](MODEL.md) pour construire un circuit cohérent.

Les modifications restent un brouillon jusqu'à **Enregistrer**. Un projet incomplet peut être sauvegardé, mais ses diagnostics bloquent le démarrage. L'édition est verrouillée pendant l'exécution et la pause : arrêter l'essai avant de modifier la configuration.

## Déclarer et associer les variables

Dans **Variables & mapping**, définir pour chaque variable : identifiant stable, nom, type, unité, valeur initiale, limites et sens.

| Sens | Interprétation |
| --- | --- |
| `input` | Entrée du PLC, produite par le modèle : mesure, retour de position, fin de course, défaut. Elle exige une autorisation d'écriture explicite. |
| `output` | Sortie du programme PLC, lue par le modèle : commande pompe, ouverture de vanne, consigne. Le banc ne l'écrit jamais. |

Associer ensuite les ports de chaque symbole aux variables correspondantes. Le catalogue précise les types acceptés. Un input ne peut avoir qu'un seul producteur de modèle ; plusieurs équipements peuvent lire la même commande PLC.

En démonstration, les NodeIds ne sont pas utilisés. En OPC UA, renseigner les NodeIds réellement relevés sur la CPU virtuelle, ainsi que le namespace si nécessaire. L'adresse proposée dans un exemple n'est pas une découverte de votre projet TIA.

L'import/export CSV du mapping permet de travailler avec un tableur. Le projet complet s'importe/s'exporte en JSON. Les imports sont validés ; une erreur ne doit pas être contournée en changeant arbitrairement le type déclaré.

## Contrôler un essai

- **Démarrer** sauvegarde la configuration, la valide et ouvre un nouvel essai.
- **Pause** suspend le modèle et les écritures. Sur un PLC externe, le programme de la CPU peut continuer de tourner ; la pause du banc n'est pas un STOP CPU.
- **Reprendre** poursuit le même essai après rétablissement de la session prévue. Vérifier l'état du PLC si sa séquence a continué pendant la pause.
- **Arrêter** termine l'essai et permet l'édition.
- **Réinitialiser** restaure le modèle et les conditions initiales locales ; les traces des essais précédents restent conservées.

Un scénario terminé doit être réinitialisé avant d'être rejoué. Pour le PLC réel simulé, remettre aussi les états internes du programme dans les conditions de départ définies par votre protocole FAT.

## Forcer une mesure ou injecter un défaut

Les forçages portent uniquement sur les entrées simulées autorisées. Saisir une valeur dans le type et les limites du tag ; les tags forcés sont signalés. Libérer le forçage pour reprendre le signal du modèle.

Sur un équipement, sélectionner un défaut compatible : défaut moteur, vanne bloquée, capteur figé ou hors plage. Pour une vanne bloquée, une position peut être donnée ; sinon la position actuelle est conservée. Le défaut hors plage exige une valeur explicite en dehors des limites de procédé. Effacer le défaut pour rétablir le comportement normal.

Le niveau physique de la cuve et le signal LT-101 peuvent diverger lorsqu'un capteur est figé ou forcé : cette différence est le comportement recherché pour tester les réactions du PLC.

## Écrire un scénario

Dans **Scénarios**, créer un scénario, nommer son objectif, fixer sa durée et éditer ses étapes. Les étapes doivent être classées par `at_s` croissant et rester dans la durée du scénario. Après modification du JSON, utiliser l'action d'application avant d'enregistrer le projet.

Exemple d'étapes :

```json
[
  {"at_s": 0, "action": "marker", "message": "Début du test défaut moteur"},
  {"at_s": 5, "action": "fault", "target": "P101", "value": {"kind": "motor_trip"}},
  {"at_s": 6, "action": "expect", "target": "pump_running", "operator": "eq", "value": false, "message": "Le retour marche doit tomber"},
  {"at_s": 10, "action": "clear_fault", "target": "P101"},
  {"at_s": 12, "action": "expect", "target": "pump_fault", "operator": "eq", "value": false}
]
```

Actions disponibles : `force`, `release`, `fault`, `clear_fault`, `marker`, `expect`. Une assertion numérique peut utiliser `eq`, `ne`, `gt`, `ge`, `lt`, `le`, avec une tolérance pour l'égalité. BOOL accepte `eq`/`ne`. L'assertion utilise une mesure d'un pas terminé, pas une valeur anticipée.

Les actions sont exécutées au premier début de cycle atteignant leur date ; les assertions à la première fin de cycle atteignant leur date. La précision est donc limitée par le pas choisi. Éviter de programmer une action et une assertion de son effet exactement au même instant : laisser au moins un pas, et le délai de réponse réel du procédé/PLC. Une mutation doit pouvoir être suivie d'une écriture : la validation refuse les forçages, libérations et défauts placés à la fin ou trop tard dans le dernier cycle. Les marqueurs et assertions restent autorisés à la durée finale.

## Tendances, marqueurs et rapports

Les tendances de l'interface montrent une fenêtre récente ; le stockage d'essai conserve les échantillons enregistrés, indépendamment de cette fenêtre. Les BOOL sont représentés numériquement pour les courbes. Les unités restent celles du mapping.

Poser un marqueur/commentaire pour signaler une observation pendant l'essai. Renseigner ensuite le résultat utilisateur et son justification. Les exports comprennent :

- **CSV** : mesures avec temps, variable, valeur et qualité ;
- **rapport HTML** : contexte, cible, scénario, assertions, actions et résultat utilisateur ;
- **preuve JSON** : configuration et données structurées permettant une revue technique.

Les essais archivés restent consultables après redémarrage. Un arrêt inattendu du serveur classe un essai ouvert comme interrompu ; le logiciel ne reprend pas automatiquement ses écritures.

## Passer à PLCSIM Advanced

Ouvrir **Connexion**, sélectionner OPC UA et suivre [PLCSIM_SETUP.md](PLCSIM_SETUP.md). Le démarrage requiert une cible déjà autorisée localement et la confirmation de son nom et de son endpoint. Les contrôles de projet ne remplacent pas la vérification de l'isolation réseau.

En cas de perte de communication ou de réponse partielle, l'essai passe en erreur et les écritures cessent. Les dernières valeurs peuvent rester dans le DB de la CPU ; le banc ne garantit pas une remise à zéro du PLC. Identifier la cause, remettre la séquence dans l'état convenu, puis lancer volontairement un nouvel essai.

## Assistance TIA optionnelle

Le runtime FAT fonctionne sans IA. Pour consulter un projet avec Claude Code ou Codex, utiliser le serveur existant configuré en lecture seule et le parcours documenté dans [TIA_MCP.md](TIA_MCP.md). Les imports, sauvegardes et compilations suivent un terminal humain distinct, avec revue du changement et copie de développement. Selon le client IA choisi, le code transmis au modèle peut quitter le poste : appliquer la politique de confidentialité du client.
