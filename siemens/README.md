# Sources d'interface TIA

Ces sources accompagnent le raccordement d'un programme existant dans une copie de développement. Elles ne contiennent ni OB principal, ni régulation, ni séquence de cuve universelle.

1. Importer `DB_FAT.scl`, générer son bloc et compiler dans la version TIA cible.
2. Importer `FC_FAT_Exchange.scl` si son interface convient au programme ; sinon utiliser ses affectations comme point de départ pour le raccordement explicite.
3. Affecter les trois commandes du programme à `PumpCmd`, `InletCmd`, `OutletCmd`.
4. Utiliser les dix entrées simulées dans le chemin FAT de la logique, sans les réécrire depuis les E/S matérielles.
5. Configurer le serveur OPC UA et remplacer les NodeIds d'exemple dans le projet FAT par ceux observés.
6. Compiler, charger manuellement dans la CPU virtuelle convenue et exécuter le protocole de qualification.

L'appel du helper ne remet pas automatiquement un programme existant dans un état de test. Son ordre par rapport à la logique de contrôle peut introduire un retard d'un cycle ; l'automaticien doit fixer et vérifier ce contrat. Quand `EnableFAT` est faux, les sorties `Sim…` sont mises à zéro et doivent être ignorées par l'appelant.

Le nombre et le nom des variables du DB correspondent exactement aux treize tags de `fat_studio/demo.py`. Le tableau `DB_FAT-tags.csv` facilite leur contrôle, mais les NodeIds restent indicatifs.

**État de validation :** sources fournies et correspondance des noms contrôlée ; compilation réelle TIA et qualification Siemens à effectuer sur le poste cible.

Documentation : [mise en service PLCSIM](../docs/PLCSIM_SETUP.md), [guide de mapping](../docs/USER_GUIDE.md), [appel d'une fonction SCL selon Siemens V21](https://docs.tia.siemens.cloud/r/en-us/v21/creating-scl-programs/entering-scl-instructions/insert-block-calls-in-scl/basic-information-on-the-block-call-in-scl/calling-functions).
