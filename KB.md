# Invariants du dépôt

## Paquet Python et assets web

Après une reconstruction Vite, comparer les noms **et le contenu** des fichiers web de la wheel à `fat_studio/web`. Effacer uniquement le cache généré identifié `build/lib/fat_studio/web` lors de l'intégration des assets, après contrôle de sa cible ; préserver le reste du build et refuser les liens sortants.

Cause : lors de la préparation 0.2.0, setuptools a conservé l'ancien fichier JS haché dans `build/lib` et l'a embarqué avec le nouveau, bien qu'il ait disparu des sources. Un build réussi ne prouve pas l'absence de fichiers périmés dans la wheel.

## Identité des profils TIA

Exiger un manifeste vérifié pour les deux versions, y compris V21. La version produit MCP `4.3.0` ne distingue pas une compilation V20 d'une compilation V21. Transmettre le dossier des DLL vérifiées au transport MCP et aux fragments client ; contrôler que les trois DLL proviennent du même dossier.

Cause : un exécutable sans manifeste était initialement admis comme V21 ; un chemin Openness utilisé seulement pendant l'installation pouvait ensuite être remplacé par l'environnement hérité ou la découverte native. Les vérifications de configuration seules ne prouvaient pas les références utilisées au lancement.

## Build du worker amont

Pour le portage source épinglé, restaurer explicitement le worker net48 avant la publication du host et transmettre les propriétés de version attendues aux deux. Conserver `UseTiaPortalReferenceStubs=false` et les références réelles de la version choisie.

Cause : le worker est construit par une cible MSBuild distincte, pas par un `ProjectReference` du host ; une restauration du seul host ne prépare pas ses dépendances. Le source brut n'intègre pas non plus la version produit injectée par le workflow de publication amont.
