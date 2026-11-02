# Modèle de procédé et limites

## Contrat physique

Le moteur représente des cuves à section constante, des alimentations/soutirages à débit paramétré, des actionneurs et des instruments. Les volumes sont en **litres**, les débits en **litres par seconde**, les positions et niveaux en **pour cent**.

À chaque pas de temps, il reçoit une image complète des commandes PLC, calcule l'évolution du procédé et produit les entrées simulées. `ProcessEngine` n'implémente aucune régulation. En mode démonstration, un `DemoController` séparé remplace explicitement le PLC ; l'adaptateur OPC UA utilise exclusivement les commandes lues dans la CPU virtuelle.

Le pas est configurable de 20 à 2 000 ms, avec 100 ms par défaut. Le temps simulé progresse par pas fixes. La communication OPC UA et le programme PLC ne sont pas exécutés en synchronisation déterministe : un dépassement de temps est journalisé, sans rattrapage en rafale. Le mode OPC UA impose une vitesse de 1×. L'accélération de la démonstration ne constitue pas une qualification de performance temps réel.

## Cuve et bilan volumique

Pour une cuve de capacité C, le niveau vaut `100 × V / C`.

```text
volume disponible = volume précédent + débit entrant × pas
débit sortant réel = min(débit sortant demandé, volume disponible / pas)
volume avant limite = volume disponible − débit sortant réel × pas
débordement ajouté = max(volume avant limite − capacité, 0)
volume suivant = min(max(volume avant limite, 0), capacité)
```

Une cuve vide ne délivre pas de liquide inexistant. Le débordement est comptabilisé séparément dans `overflow_l`. Il n'est pas effacé par une simple limitation numérique du niveau. Les seuils haut et bas utilisent le niveau physique, tandis qu'un transmetteur peut retourner une mesure forcée ou défectueuse.

## Connexions et circuits de débit

**Les lignes du P&ID sont graphiques.** Le calcul utilise les propriétés suivantes sur les pompes et vannes :

| Paramètre | Effet |
| --- | --- |
| `tank_id` | Cuve à laquelle le circuit apporte ou retire du volume. |
| `role` | `inlet` pour l'alimentation, `outlet` pour le soutirage. |
| `flow_group` | Nom du circuit en série. |
| `max_flow_l_s` | Débit maximal de cet équipement selon le modèle choisi. |

Pour une même cuve, un même sens et un même groupe, le débit est le **minimum** des capacités instantanées des équipements. Les groupes indépendants s'additionnent. Tous les équipements d'un circuit portent le même débit réel, limité par le volume disponible en soutirage.

Exemple : P-101 peut délivrer 30 L/s et XV-101 laisse passer 25 L/s. Dans le groupe `feed`, le circuit fournit 25 L/s. Une deuxième pompe dans un groupe `feed_2` ajoute un débit indépendant. Une vanne fermée dans `feed` bloque le circuit entier.

Les limites sont explicites : pas de calcul de pression, de courbe de pompe, de pertes de charge ou de hauteur géométrique ; pas de transfert conservatif automatique entre deux cuves ; pas de solveur de réseau déduit du dessin. Une alimentation représente une réserve disponible et un soutirage une évacuation. Pour un autre procédé, modifier les modèles et leurs tests avant d'utiliser des résultats comme preuve de comportement.

## Actionneurs

- **Pompe** : commande BOOL, vitesse 0–100 %, débit proportionnel à la vitesse. Le retour marche devient vrai au-dessus de 5 %. Un défaut moteur coupe immédiatement le débit, sans modèle d'énergie résiduelle.
- **Vanne TOR** : commande BOOL, position cible 0 ou 100 %, débit proportionnel à la position.
- **Vanne modulante** : commande REAL 0–100 %, caractéristique linéaire, égal pourcentage ou ouverture rapide.

La réponse utilise un premier ordre exact : `nouvel état = cible + (ancien état − cible) × exp(−pas / réponse_s)`. `response_s` est une **constante de temps**, pas un temps total de course. Zéro donne une réponse instantanée. Les fins de course sont actifs à ≤ 0,5 % et ≥ 99,5 %.

Les caractéristiques de vanne proviennent du fichier MIT HistorianSim conservé sans modification dans `fat_studio/vendor/historiansim/`. La fonction égal pourcentage amont vaut `1 / rangeability` à ouverture nulle ; FAT Studio impose séparément une fermeture étanche à zéro. Le modèle de stiction du fichier amont n'est pas utilisé dans cette version. Voir sa [provenance](../fat_studio/vendor/historiansim/PROVENANCE.md).

## Instrumentation et valeurs PLC

Un capteur analogique mesure un état d'une cuve, pompe ou vanne : `mesure = source × scale + offset`. Pour INT/DINT, le résultat est arrondi à l'entier le plus proche, les demi-entiers allant vers l'entier pair. Un capteur binaire applique une comparaison à son seuil. Un indicateur affiche une sortie PLC sans agir sur le procédé.

| Type | Valeurs acceptées |
| --- | --- |
| BOOL | Booléen JSON `true` ou `false` ; ni `0`/`1` ni chaîne. |
| INT | Entier signé de −32 768 à 32 767. |
| DINT | Entier signé de −2 147 483 648 à 2 147 483 647. |
| REAL | Nombre fini dans la plage IEEE-754 simple précision ; transfert OPC UA en Float. |

Les limites min/max de procédé s'appliquent aux commandes lues et aux forçages ordinaires. Un défaut `out_of_range` peut dépasser ces limites, mais jamais le type de stockage PLC. Les valeurs non finies, les types incohérents et les images de commandes incomplètes provoquent un arrêt en erreur.

## Forçages, défauts et qualité

| Action | Effet |
| --- | --- |
| Forçage d'un input | Remplace la valeur renvoyée au PLC, dans ses limites déclarées ; le procédé physique continue d'évoluer. |
| Libération | Rétablit la mesure du modèle ou la valeur initiale d'un tag manuel. |
| `sensor_stuck` | Fige la mesure actuelle, ou une valeur explicitement renseignée. |
| `out_of_range` | Fournit une valeur explicitement hors des bornes du capteur. |
| `valve_stuck` | Fige la position actuelle, ou une position donnée entre 0 et 100 %. |
| `motor_trip` | Coupe la pompe et active son retour de défaut. |

Un capteur ne cumule pas simultanément `sensor_stuck` et `out_of_range`. Un forçage manuel a priorité sur le signal défectueux et reste visible. Les qualités enregistrées sont `good`, `forced`, `fault`, `out_of_range`, auxquelles le runtime ajoute l'état de communication lors d'une erreur.

La remise à zéro efface forces et défauts, restaure les volumes initiaux et réinitialise le contrôleur de démonstration. Elle ne remet pas à zéro le programme d'une CPU externe. Pour rejouer une FAT Siemens dans des conditions comparables, l'automaticien doit remettre aussi les états internes du programme testé dans les conditions convenues.

## Démonstration TK-101

La cuve de 1 000 L démarre à 25 %. Son contrôleur fictif commande le remplissage sous 30 % et l'arrête à 70 %. FCV-101 reste à 35 % en démonstration, soit 4,2 L/s après stabilisation. Le contrôleur lit les **tags simulés**, donc il réagit aux forçages et défauts du transmetteur.

Trois scénarios sont livrés : cycle de référence, défaut moteur/reprise, capteur figé/libéré. Leurs assertions visent ce contrôleur de démonstration et doivent être adaptées aux séquences du programme PLC réel. La réussite de ces scénarios démontre le comportement de ce modèle et de cette logique de test ; elle ne certifie aucune installation.

Les tests exécutables du modèle sont dans `tests/test_engine.py` et `tests/test_models.py`.
