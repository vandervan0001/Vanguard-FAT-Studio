# Modèle de procédé et limites

## Contrat physique

Le moteur représente des cuves à section constante, des alimentations/soutirages à débit paramétré, des actionneurs et des instruments. Les volumes sont en **litres**, les débits en **litres par seconde**, les positions et niveaux en **pour cent**.

À chaque pas de temps, il reçoit une image complète des commandes PLC, calcule l'évolution du procédé et produit les entrées simulées. `ProcessEngine` n'implémente aucune régulation. En mode démonstration, un `DemoController` séparé remplace explicitement le PLC ; l'adaptateur OPC UA utilise exclusivement les commandes lues dans la CPU virtuelle.

Le pas est configurable de 20 à 2 000 ms, avec 100 ms par défaut. Le temps simulé progresse par pas fixes. La communication OPC UA et le programme PLC ne sont pas exécutés en synchronisation déterministe : un dépassement de temps est journalisé, sans rattrapage en rafale. Le mode OPC UA impose une vitesse de 1×. L'accélération de la démonstration ne constitue pas une qualification de performance temps réel.

Le calcul interne du procédé conserve la double précision (`float64`). Un appel à `ProcessEngine.step` valide toute l'image de commandes, puis prépare un cycle complet avant de le conserver. Si le calcul ou la publication d'une mesure échoue, il restaure ensemble le temps, les états des équipements, les valeurs brutes, les valeurs publiées et leurs qualités. Cette restauration porte sur l'appel local à `step` ; les forçages ou actions appliqués avant cet appel restent distincts. Elle ne constitue pas une transaction OPC UA et ne peut pas annuler une écriture déjà reçue par le serveur.

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
| `source_tank_id` | Cuve source d’un transfert vers `tank_id` ; vide pour un apport externe. |
| `max_flow_l_s` | Débit maximal de cet équipement selon le modèle choisi. |

Pour une même cuve, un même sens et un même groupe, le débit est le **minimum** des capacités instantanées des équipements. Les groupes indépendants s'additionnent. Tous les équipements d'un circuit portent le même débit réel, limité par le volume disponible en soutirage.

Exemple : P-101 peut délivrer 30 L/s et XV-101 laisse passer 25 L/s. Dans le groupe `feed`, le circuit fournit 25 L/s. Une deuxième pompe dans un groupe `feed_2` ajoute un débit indépendant. Une vanne fermée dans `feed` bloque le circuit entier.

Les limites sont explicites : pas de calcul de pression, de courbe de pompe, de pertes de charge ou de hauteur géométrique ; pas de solveur de réseau déduit du dessin. Un transfert entre deux cuves exige sa source et sa destination explicitement déclarées ; il n’est jamais déduit d’un trait graphique. Une alimentation représente une réserve disponible et un soutirage une évacuation. Pour un autre procédé, modifier les modèles et leurs tests avant d'utiliser des résultats comme preuve de comportement.

### Transfert explicite entre cuves

Un circuit d’entrée peut renseigner `source_tank_id`. Le même débit réel est alors débité de la source et crédité à la destination. Si plusieurs circuits consomment une même cuve, leurs débits sont réduits proportionnellement lorsque le volume disponible ne suffit pas. Les apports externes du cycle peuvent alimenter cette disponibilité ; un volume reçu d’un autre transfert devient disponible au cycle suivant, sans boucle algébrique instantanée.

Le bilan conserve le volume transféré. Un débordement de la destination reste comptabilisé dans son `overflow_l` et ne disparaît pas dans une limitation silencieuse. Les groupes d’un même circuit doivent utiliser une seule source cohérente. Le laboratoire public illustre source vers intermédiaire, puis intermédiaire vers réception ; [DEMO_PLC.md](DEMO_PLC.md) distingue les demandes manuelles du programme passif et le procédé simulé.

## Actionneurs

- **Pompe** : commande BOOL, vitesse 0–100 %, débit proportionnel à la vitesse. Le retour marche devient vrai au-dessus de 5 %. Un défaut moteur coupe immédiatement le débit, sans modèle d'énergie résiduelle.
- **Vanne TOR** : commande BOOL, position cible 0 ou 100 %, débit proportionnel à la position.
- **Vanne modulante** : commande REAL 0–100 %, caractéristique linéaire, égal pourcentage ou ouverture rapide.

La réponse utilise un premier ordre exact : `nouvel état = cible + (ancien état − cible) × exp(−pas / réponse_s)`. `response_s` est une **constante de temps**, pas un temps total de course. Zéro donne une réponse instantanée. Les fins de course sont actifs à ≤ 0,5 % et ≥ 99,5 %.

Les caractéristiques de vanne proviennent du fichier MIT HistorianSim conservé sans modification dans `fat_studio/vendor/historiansim/`. La fonction égal pourcentage amont vaut `1 / rangeability` à ouverture nulle ; Vanguard FAT Studio impose séparément une fermeture étanche à zéro. Le modèle de stiction du fichier amont n'est pas utilisé dans cette version. Voir sa [provenance](../fat_studio/vendor/historiansim/PROVENANCE.md).

## Instrumentation et valeurs PLC

Un capteur analogique mesure un état d'une cuve, pompe ou vanne : `mesure = source × scale + offset`. Pour INT/DINT, le résultat est arrondi à l'entier le plus proche, les demi-entiers allant vers l'entier pair. Un capteur binaire applique une comparaison à son seuil. Un indicateur affiche une sortie PLC sans agir sur le procédé.

| Type | Valeurs acceptées |
| --- | --- |
| BOOL | Booléen JSON `true` ou `false` ; ni `0`/`1` ni chaîne. |
| INT | Entier signé de −32 768 à 32 767. |
| DINT | Entier signé de −2 147 483 648 à 2 147 483 647. |
| REAL | Nombre fini dans la plage IEEE-754 simple précision, normalisé en `float32` dès sa validation ; transfert OPC UA en Float. |

Les limites min/max de procédé s'appliquent aux commandes lues et aux forçages ordinaires. Un défaut `out_of_range` peut dépasser ces limites, mais jamais le type de stockage PLC. Les valeurs non finies, les types incohérents et les images de commandes incomplètes provoquent un arrêt en erreur.

### Représentation des REAL et assertions

Les valeurs initiales, les forçages, les mesures publiées et les commandes validées utilisent la même représentation IEEE-754 simple précision. L'image des tags enregistrée correspond ainsi à la valeur représentable dans le Float OPC UA envoyé. Par exemple, `16777217` devient `16777216`, et `0.1` devient `0.10000000149011612`. Les états physiques internes conservent leur double précision ; leur affichage ou leur mesure par un tag REAL peut donc présenter un arrondi.

Les bornes REAL représentables sont comparées après la même quantification. Une borne maximale déclarée à `0.1` accepte son retour Float32 `0.10000000149011612`. Le calcul de la qualité et la validation d'un défaut hors plage suivent cette règle : une valeur demandée qui s'arrondit à la borne n'est pas un défaut hors plage. NaN, les infinis, les booléens utilisés comme REAL et les dépassements de la plage de stockage restent refusés.

Les assertions conservent l'attente et la tolérance choisies dans le scénario. Pour `eq` et `ne` numériques, `tolerance` est une tolérance absolue, avec une tolérance relative nulle ; les comparaisons `gt`, `ge`, `lt`, `le` ne l'utilisent pas. La valeur attendue n'est pas automatiquement arrondie pour rendre l'assertion vraie. Avec une tolérance nulle, une attente `0.1` peut donc échouer face au tag REAL correspondant ; choisir la tolérance selon le signal et l'essai à réaliser.

### Plages des capteurs

La validation du projet contrôle les extrémités connues de la plage mesurée après application de l'échelle et du décalage, puis de l'arrondi INT/DINT éventuel. Les domaines des débits agrégés `inflow_l_s` et `outflow_l_s` tiennent compte des circuits : minimum des capacités en série et somme des branches. Un capteur INT qui pourrait mesurer `25 L/s × 2000 = 50000` est ainsi refusé avant le démarrage.

Le débordement cumulé `overflow_l` commence à zéro, mais n'a pas de borne supérieure pour un essai manuel sans durée maximale. Sa valeur initiale, décalage compris, est vérifiée ; une échelle non nulle entraîne un avertissement sur cette absence de borne. Un dépassement ultérieur du type PLC arrête l'essai sans conserver un cycle local partiellement calculé. Le modèle ne sature pas silencieusement ce compteur pour masquer le dépassement.

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

Une erreur de communication ou une annulation de l'échange interrompt l'essai, ferme la session et marque l'image courante `bad`. Si l'annulation intervient pendant l'écriture, une partie du dernier lot peut déjà être appliquée au serveur ; l'image calculée n'est alors pas une confirmation de réception de toutes les valeurs. Aucun nouveau lot ni aucune reconnexion automatique ne sont engagés après cet arrêt.

La remise à zéro efface forces et défauts, restaure les volumes initiaux et réinitialise le contrôleur de démonstration. Elle ne remet pas à zéro le programme d'une CPU externe. Pour rejouer une FAT Siemens dans des conditions comparables, l'automaticien doit remettre aussi les états internes du programme testé dans les conditions convenues.

## Laboratoire public

Le projet `public-io-lab` regroupe trois cuves, quatre pompes, huit vannes et les instruments/commandes associés : 36 objets, 75 variables. Le contrôleur Python `manual_lab_v1` reproduit le pont PLC passif public. Les demandes manuelles fournissent les commandes ; le modèle produit les retours physiques. Un défaut moteur peut donc couper marche et débit alors que la demande et la commande restent actives. Les séquences de remplissage/transfert/arrêt sont dans les scénarios FAT, pas dans un standard de programmation.

Les animations par variable sont des règles d’affichage en lecture seule. Elles n’interviennent ni dans les commandes ni dans le bilan physique. Leurs plages graphiques ne modifient pas les mesures enregistrées.

## Exemple historique TK-101

La cuve de 1 000 L démarre à 25 %. Son contrôleur fictif commande le remplissage sous 30 % et l'arrête à 70 %. FCV-101 reste à 35 % en démonstration, soit 4,2 L/s après stabilisation. Le contrôleur lit les **tags simulés**, donc il réagit aux forçages et défauts du transmetteur.

Pour les équipements configurés avec `demo_control="level"`, le sens du débit détermine le sens de la commande : une alimentation (`inlet`) démarre au seuil bas et s'arrête au seuil haut ; un soutirage (`outlet`) démarre au seuil haut et s'arrête au seuil bas. Entre les seuils, le contrôleur conserve son état. Avec `demo_control="constant"`, il utilise la commande constante configurée. Ces règles appartiennent uniquement au contrôleur de démonstration.

Trois scénarios sont livrés : cycle de référence, défaut moteur/reprise, capteur figé/libéré. Leurs assertions visent ce contrôleur de démonstration et doivent être adaptées aux séquences du programme PLC réel. La réussite de ces scénarios démontre le comportement de ce modèle et de cette logique de test ; elle ne certifie aucune installation.

Les comportements sont implémentés dans [models.py](../fat_studio/models.py), [engine.py](../fat_studio/engine.py) et [runtime.py](../fat_studio/runtime.py). Les tests exécutables du modèle et de ses frontières sont dans [test_engine.py](../tests/test_engine.py), [test_models.py](../tests/test_models.py) et [test_adverse_process.py](../tests/test_adverse_process.py).
