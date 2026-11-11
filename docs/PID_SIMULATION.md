# Simuler un échangeur et une vanne trois voies

Le banc propose onze types de modèles de simulation et 41 familles de symboles documentaires. Un symbole documentaire garde son dessin et ses piquages sans produire de signal. Les modèles `heat_exchanger` et `valve_three_way` ajoutent des bilans explicitement paramétrés pour les essais FAT. Ils ne sont pas activés par la reconnaissance d'un plan.

## Choisir un modèle

Dans la palette **P&ID**, choisir **Échangeur simulé** ou **Vanne trois voies simulée**. Lors d'un import, les familles correspondantes restent documentaires par défaut ; sélectionner explicitement le modèle simulé dans la revue pour créer un brouillon de simulation. Les valeurs du catalogue sont des valeurs de départ, à remplacer par les données de l'installation.

L'exemple [Boucle thermique avec répartition trois voies](../examples/pid-thermal-loop.project.json) déclare trois cuves, une vanne de diversion et un échangeur. Il utilise exclusivement le contrôleur de démonstration local. Son entrée manuelle de position agit sur la consigne du contrôleur de démonstration ; le moteur de procédé ne commande jamais un PLC. En mode OPC UA, la commande provient du programme externe.

Dans **Connexion**, en mode Démo, sélectionner **Modèles configurables** pour ce comportement. **Laboratoire I/O public** conserve le contrôleur passif du laboratoire historique. Un projet importé ne change pas de contrôleur sans choix explicite.

## Vanne trois voies

Les piquages physiques sont `AB`, `A`, `B`. La position indique la part vers A : 0 % ouvre la branche B, 100 % ouvre la branche A, 50 % répartit le débit nominal à parts égales. Le modèle est linéaire et ne représente aucune position centrale fermée.

| Paramètre | Signification |
| --- | --- |
| `mode: diverting` | La cuve AB alimente les cuves A et B. |
| `mode: mixing` | Les cuves A et B alimentent la cuve AB. Il s'agit d'un mélange volumique ; aucune composition ni température de cuve n'est calculée. |
| `common_tank_id`, `branch_a_tank_id`, `branch_b_tank_id` | Trois cuves simulées distinctes, obligatoires. Les traits du dessin ne les remplacent pas. |
| `max_flow_l_s` | Débit nominal total avant limitation par les stocks disponibles. |
| `response_s` | Constante de réponse de position ; zéro applique la consigne au cycle suivant. |

La commande PLC `command` est une sortie REAL lue par le banc. Les retours `position`, `flow_a`, `flow_b`, `feedback_a`, `feedback_b` sont des entrées simulées facultatives. Les fins de course correspondent à une position ≥ 99,5 % vers A et ≤ 0,5 % vers B. Le défaut `valve_stuck` bloque la position déclarée, sans créer de fonction de sécurité.

Les débits réels respectent `qAB = qA + qB`. Lorsque plusieurs équipements demandent du volume à une même cuve, le stock disponible limite proportionnellement leurs demandes. Un transfert entrant devient disponible pour d'autres transferts au cycle suivant. Les cuves conservent leur calcul de débordement ; une destination pleine n'impose pas de contre-pression.

## Échangeur à deux volumes mélangés

Chaque circuit possède un volume interne constant, parfaitement mélangé. Les fluides restent séparés. La température de sortie est celle du volume mélangé. La conductance `ua_kw_k` relie leurs températures ; une puissance positive va du primaire au secondaire. Le sens s'inverse si le secondaire est plus chaud.

Pour chaque circuit, déclarer le volume en L, la masse volumique en kg/L, la capacité thermique en kJ/(kg·K), le débit en L/s, la température d'entrée et la température initiale en °C. Les deux circuits peuvent avoir des fluides différents. La plage numérique des températures est de −100 à 500 °C ; elle n'affirme pas qu'un fluide réel reste liquide dans cette plage.

Avec `C = volume × densité × cp` en kJ/K et `F = débit × densité × cp` en kW/K, le modèle calcule :

```text
Cprimaire × dTp/dt   = Fprimaire × (TentréeP − Tp) − Q
Csecondaire × dTs/dt = Fsecondaire × (TentréeS − Ts) + Q
Q = UAeffectif × (Tp − Ts)
```

Les deux équations sont résolues ensemble par Euler implicite. Le bilan de chaque cycle inclut l'énergie stockée dans les volumes internes. À débit nul, ces volumes peuvent encore échanger leur chaleur ; « débit nul » n'impose donc pas immédiatement « puissance nulle ». Le modèle ne représente ni le profil spatial d'un contre-courant, ni la masse métallique, ni les pertes ambiantes, ni le changement de phase ou le calcul de pression.

Le défaut `fouling` reçoit une perte explicite de conductance de 0 à 100 %. À 100 %, UA devient nul et les circuits évoluent séparément. Les températures, débits et puissance peuvent être associés directement aux entrées PLC du catalogue, ou mesurés par les capteurs génériques existants. Les signaux REAL restent convertis en Float32 ; le calcul physique conserve la double précision.

### Déclarer les conditions d'entrée

Les températures et débits viennent des paramètres constants, sauf association explicite :

- Les sorties PLC facultatives `primary_inlet_command` et `secondary_inlet_command` imposent les températures d'entrée.
- `primary_flow_command` et `secondary_flow_command` imposent les débits. Une valeur négative ou hors plage arrête le cycle sans avancer son état.
- `primary_flow_equipment` et `secondary_flow_equipment` peuvent lire le débit réel d'une pompe ou d'une vanne simulée. Le champ choisi est `flow_l_s`, ou `flow_a_l_s` / `flow_b_l_s` pour une vanne trois voies. La source est lue après allocation des volumes au même cycle.

Une source d'équipement et une sortie PLC ne peuvent pas imposer simultanément le débit d'un même circuit. Les sources ne peuvent pas être des échangeurs, ce qui évite les boucles algébriques. Dans l'exemple, la branche A détermine explicitement le débit secondaire. Les cuves restent des modèles volumiques : l'échangeur ne leur ajoute pas de température ou de bilan d'énergie caché.

Le principe de volume parfaitement mélangé et d'échange par conductance est aussi décrit dans la documentation primaire [Modelica Buildings, MixingVolumes](https://simulationresearch.lbl.gov/modelica/releases/latest/help/Buildings_Fluid_MixingVolumes.html). L'implémentation FAT est originale ; aucun code Modelica ni moteur de simulation tiers n'est embarqué.

## Enregistrer et échanger

Le JSON de projet complet et l'archive restaurable conservent les paramètres, associations de signaux, sources de débit et scénarios. Les exports **P&ID** PDF, DWG, SVG et autres conservent le schéma et ses piquages ; ils excluent les paramètres physiques et le mapping PLC. Leur réimport prépare donc un dessin documentaire pour ces deux nouvelles familles, même si le dessin provenait d'un modèle simulé.

Les [formats et crédits](PID_EXCHANGE.md), le [modèle volumique historique](MODEL.md) et la [portée des vérifications](PID_COVERAGE.md) donnent les autres contrats. Un essai du moteur ou du contrôleur de démonstration ne constitue pas une qualification du procédé réel ni un verdict FAT humain.
