# Revue des composants existants

Date de revue : **2 novembre 2026**. Les décisions ci-dessous reposent sur la lecture des dépôts, des licences et des contrats de code aux révisions indiquées. Les affirmations de compatibilité des auteurs ne constituent pas une qualification sur le poste de l'utilisateur.

## Décision d'architecture

Le runtime FAT échange les valeurs de procédé par **OPC UA**, avec la bibliothèque existante **asyncua**. L'assistance d'ingénierie utilise séparément **Czarnak/tia-portal-mcp 4.3.0**, appuyé sur TIA Openness. Aucun serveur TIA MCP n'a été réécrit. Une couche Python courte orchestre le serveur existant pour ajouter les exigences spécifiques de l'URS : copie de développement, revue de diff, archive vérifiée et approbations interactives.

L'éditeur s'appuie sur React Flow. Les dépendances, le dessin interactif et le protocole OPC UA sont donc réutilisés. Le code propre au projet concerne l'assemblage, le modèle simplifié, les règles de FAT et la traçabilité.

## Dépôts comparés

| Projet | Révision examinée | Licence observée | Usage retenu |
| --- | --- | --- | --- |
| [Czarnak/tia-portal-mcp](https://github.com/Czarnak/tia-portal-mcp/tree/v4.3.0) | v4.3.0, `10c5de2eb44c0362792cd141370b3f42f92f6ecd` | MIT | Serveur d'ingénierie optionnel, installé séparément et épinglé. |
| [heilingbrunner/tiaportal-mcp](https://github.com/heilingbrunner/tiaportal-mcp/tree/fdec356bf4f23031c44015ad72856bafc475d555) | `fdec356bf4f23031c44015ad72856bafc475d555` | MIT, `LICENSE.txt` | Alternative examinée ; pas embarquée. |
| [ScottDuncanAI/HistorianSim](https://github.com/ScottDuncanAI/HistorianSim/tree/14e616c382a9db8026cbb4ab86bdd803d56ca72e) | `14e616c382a9db8026cbb4ab86bdd803d56ca72e` | MIT | `core/valve.py` embarqué sous `fat_studio/vendor/historiansim/`, avec licence et provenance ; pipeline complet non retenu. |
| [ScottDuncanAI/HistorianRCA](https://github.com/ScottDuncanAI/HistorianRCA/tree/8d12a821395ce5f72e464dc78cc2c10d05cbb9ed) | `8d12a821395ce5f72e464dc78cc2c10d05cbb9ed` | CC BY 4.0 | Référence documentaire ; données et schéma non redistribués. |
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | paquet `mcp==2.3.0` | MIT | Client stdio, négociation et elicitation officiels. |
| [FreeOpcUa/opcua-asyncio](https://github.com/FreeOpcUa/opcua-asyncio) | version exacte dans le lockfile Python | LGPL-3.0-or-later | Client/serveur OPC UA importé comme bibliothèque séparée. |

Le manifeste lisible par machine est [`integrations/upstream.lock.json`](../integrations/upstream.lock.json). Il distingue le tag retenu du `main` observé, car ce dernier continue d'évoluer.

## Czarnak : pourquoi le retenir et ce qu'il faut ajouter

La version inspectée cible **TIA Portal V21**. Son hôte MCP tourne en **.NET 10** ; un worker **.NET Framework 4.8** charge les DLL Openness depuis l'installation Siemens. Les DLL Siemens ne sont pas redistribuées. Le poste doit disposer de TIA V21, Openness et des droits Windows du groupe `Siemens TIA Openness`.

L'interface permet de consulter l'arbre du projet, de lire des blocs, types et tables de tags, et d'obtenir les diagnostics disponibles. `plc_read` fournit du contenu et un `contentHash` pour un objet isolé. `plc_write` accepte ce hash lors d'un remplacement afin de refuser une source modifiée depuis la lecture. Le contenu source est pris en charge pour des blocs SCL et des DB globaux ; XML convient à d'autres représentations supportées. Cela n'autorise pas à promettre une édition équivalente de tous les langages graphiques ou des blocs protégés.

**Point de contrôle vérifié dans le code : le lancement brut du serveur est en `read-write` par défaut.** Le mode doit toujours être spécifié explicitement. En outre, `plc_write`, `network_write`, `hmi_write` et `vci_write` ne demandent pas tous une confirmation humaine. Un `dryRun` omis peut exécuter une écriture. Une installation directe en mode écriture ne suffit donc pas à respecter FR-035.

Décisions appliquées :

- Le client IA reçoit le serveur **en lecture seule**. Les outils d'écriture, de compilation et de cycle de vie sont absents dans ce mode selon le contrat upstream.
- Le CLI `integrations.tia_engineering` est séparé du serveur FAT et n'expose aucune commande d'application par MCP ni par HTTP.
- Les seuls outils d'écriture autorisés dans ce CLI sont `archive_project`, `plc_write` pour le remplacement d'un bloc existant, `compile_check` et `save_project`.
- Le CLI exige une copie `.ap21` située dans un répertoire sandbox explicite. Il vérifie le chemin remonté par TIA avant les étapes sensibles.
- Le remplacement est relu, présenté en diff et prévisualisé par `dryRun:true`. L'approbation porte sur le chemin exact et un hash du contenu proposé.
- Une archive `.zap21` non vide est obtenue et hachée avant l'import. La copie doit déjà être sauvegardée ; l'archive ne sauvegarde pas silencieusement une version modifiée.
- Toute modification concurrente du bloc provoque un refus, et aucune écriture n'est retentée automatiquement.
- Le résultat de compilation est inspecté au niveau des diagnostics, même si l'appel MCP indique `isError:false`.

Sources de contrats : [lecture PLC](https://github.com/Czarnak/tia-portal-mcp/blob/v4.3.0/TiaMcpServer/Plc/PlcReadTools.cs), [écriture PLC](https://github.com/Czarnak/tia-portal-mcp/blob/v4.3.0/TiaMcpServer/Plc/PlcWriteTools.cs), [cycle de vie](https://github.com/Czarnak/tia-portal-mcp/blob/v4.3.0/TiaMcpServer/Tools/ProjectWriteTools.cs), [compilation](https://github.com/Czarnak/tia-portal-mcp/blob/v4.3.0/TiaMcpServer/Tools/ProjectEngineeringTools.cs), [analyse des modes d'accès](https://github.com/Czarnak/tia-portal-mcp/blob/v4.3.0/TiaMcpServer/Cli/AccessModeParser.cs), [politique de sécurité](https://github.com/Czarnak/tia-portal-mcp/blob/v4.3.0/SECURITY.md).

## Alternative heilingbrunner

L'alternative propose une couverture importante des objets TIA, des exports dans plusieurs formats et un mode `--allow-write`. Elle a été examinée comme solution possible, pas copiée. Sa définition de « read-only » diffère du besoin : la documentation liste notamment `SaveProject`, `SaveAsProject`, `CloseProject` et des outils de compilation dans sa surface disponible par défaut. Ses préréglages `--force-presets` ne constituent pas une sandbox des chemins d'import. Ce n'est pas une conclusion générale sur sa qualité ; ce sont des écarts à contrôler pour cette URS. [README à la révision examinée](https://github.com/heilingbrunner/tiaportal-mcp/blob/fdec356bf4f23031c44015ad72856bafc475d555/README.md).

## HistorianSim et HistorianRCA

HistorianSim sépare une partie de ses modèles d'équipements. Le fichier [`core/valve.py`](https://github.com/ScottDuncanAI/HistorianSim/blob/14e616c382a9db8026cbb4ab86bdd803d56ca72e/src/historiansim/core/valve.py) fournit des caractéristiques linéaire, égal pourcentage et ouverture rapide, ainsi qu'un modèle de stiction, sans dépendance autre que la bibliothèque standard. Il se prête à une réutilisation ciblée avec conservation de sa licence.

Ce fichier est effectivement intégré sous `fat_studio/vendor/historiansim/valve.py`. La notice MIT et `PROVENANCE.md` accompagnent cette copie ; le moteur importe les caractéristiques nécessaires à ses équipements.

Son pipeline global produit des séries d'historien et inclut des contrôleurs PI, des traitements en tableaux, de l'instrumentation et de la compression. Le reprendre intégralement ajouterait une seconde régulation en parallèle du PLC et des dépendances `numpy`, `scipy`, `pandas`, `pyarrow`, etc. Le banc utilise les seuls modèles d'équipement nécessaires et garde le programme PLC comme contrôleur lorsqu'un PLC est connecté. La génération batch de 90 jours n'est pas une boucle de communication FAT.

Une caractéristique égal pourcentage vaut mathématiquement `1/R` à l'ouverture zéro dans le modèle upstream. L'assemblage FAT doit donc traiter séparément la fermeture étanche s'il veut représenter une vanne sans fuite. Le nom du modèle ne constitue pas une garantie physique universelle.

HistorianRCA est un **jeu de données et un cas documentaire**, pas une application de simulation interactive. Son cas TK-101 est utile comme référence pédagogique, mais son SVG et ses données ne sont pas nécessaires à la cuve de démonstration du présent projet. Une éventuelle adaptation future doit citer Scott Duncan, fournir le lien CC BY 4.0 et signaler les modifications.

## Interface PLCSIM Advanced : comparaison

| Interface | Intérêt | Contraintes | Décision |
| --- | --- | --- | --- |
| OPC UA de la CPU virtuelle | Bibliothèque cliente existante, types explicites, accès par NodeId, serveur factice testable sur Linux et Windows. | Serveur et variables à configurer dans TIA ; réseau TCP/IP requis ; n'établit pas à lui seul que la CPU est virtuelle. | Adaptateur runtime retenu. Qualification sur le poste réel obligatoire. |
| API native PLCSIM Advanced | Identification des instances, accès et synchronisation spécifiques à la simulation ; fonctionnement étroit avec Siemens. | DLL et versions Siemens ; implémentation native C++/C# ; incompatibilités d'interface entre versions d'API. | Extension possible après identification de la version installée, pas annoncée comme implémentée. |
| TIA Openness / MCP | Lire, exporter, importer et compiler un projet d'ingénierie. | TIA/Openness, droits et versions ; pas un échange cyclique de valeurs de procédé. | Circuit d'ingénierie distinct. |

Siemens documente l'accès OPC UA via **TCP/IP Single Adapter / Multiple Adapter**, et non via Softbus. Le réglage **`<Local>`** du Control Panel coupe le Virtual Switch vers les adaptateurs physiques tout en laissant la communication TCP/IP locale sur l'adaptateur virtuel. Ce réglage fait partie de la procédure de qualification. Un DB portant le texte « simulation » ne prouve pas à lui seul la nature virtuelle de la cible.

Sources Siemens : [communications](https://docs.tia.siemens.cloud/r/simatic_s7_1500_et_200mp_manual_collection_enus_21/comprehensive-information/cpu-function-manuals/s7-plcsim-advanced/communication-paths/communication), [Control Panel et mode Local](https://docs.tia.siemens.cloud/r/simatic_et_200sp_manual_collection_enus_20/general-information/cpu-function-manuals/s7-plcsim-advanced/simulating/simulating-a-cpu/control-panel-user-interface/s7-plcsim-advanced-control-panel), [chargement de l'API V8 et différences entre versions](https://docs.tia.siemens.cloud/r/simatic_s7_1500_et_200mp_manual_collection_enus_21/comprehensive-information/cpu-function-manuals/s7-plcsim-advanced-api/initialize-api/load-api-library), [manuel V8](https://support.industry.siemens.com/cs/attachments/109997788/s7-plcsim_advanced_function_manual_en-US_en-US.pdf).

## Licences et maintenance

Le dépôt ne contient aucune DLL, licence, projet binaire ou installateur Siemens. Les composants réutilisés conservent leurs notices. `asyncua` est sous LGPL-3.0-or-later ; il est importé comme paquet séparé et non réécrit ou fusionné dans un exécutable propriétaire. Une redistribution binaire future devra fournir les notices et satisfaire les obligations applicables aux dépendances concernées.

La mise à jour d'un composant épinglé est une modification de projet : comparer les contrats, mettre à jour les locks, rejouer les tests et refaire les essais Siemens affectés. Le script d'installation MCP refuse de remplacer silencieusement une autre version déjà présente. Le support de sécurité upstream peut ne couvrir que la version la plus récente ; l'épinglage impose donc un suivi régulier, il ne dispense pas de mise à jour.
