# Raccorder une CPU virtuelle PLCSIM Advanced

## Ce qui est livré et ce qui doit être qualifié

Le client OPC UA, la validation des types et des droits, la liste d'écritures autorisées, les contrôles d'identité et l'arrêt sur erreur sont implémentés. Les essais contre un serveur OPC UA de test ne prouvent pas la compatibilité d'une combinaison Siemens donnée.

**Aucun essai sur Windows, compilation de ces sources dans TIA Portal ni échange avec une instance Siemens PLCSIM Advanced n'a été exécuté pour cette livraison.** Les preuves locales Linux sont consignées dans [VERIFICATION.md](../evidence/VERIFICATION.md) ; les opérations ci-dessous font partie de la qualification à réaliser.

Avant la première FAT, compléter la fiche de [COMPATIBILITY.md](COMPATIBILITY.md) : Windows, TIA Portal, CPU, firmware, PLCSIM Advanced, configuration OPC UA et versions. L'URS ne fournit pas ces informations ; aucune version universelle n'est supposée. Les fichiers SCL fournis sont des sources d'interface à compiler et à vérifier dans la copie du projet cible, pas un projet TIA binaire déjà qualifié.

## 1. Préparer une copie du programme

Créer une copie de développement indépendante du projet de production. Identifier les points où les entrées de procédé sont consommées et les commandes produites. Définir avec l'automaticien comment basculer les entrées vers le DB FAT, sans écraser les valeurs simulées à chaque cycle.

Deux fichiers sont fournis :

- [`DB_FAT.scl`](../siemens/DB_FAT.scl) : les treize variables exactes de la démonstration ;
- [`FC_FAT_Exchange.scl`](../siemens/FC_FAT_Exchange.scl) : copie des commandes du programme vers le DB et présentation des entrées simulées à l'appelant.

Importer les sources dans les sources externes du projet de test, générer les blocs et compiler. Appeler le helper selon l'architecture existante. Ses sorties `Sim…` ne doivent être utilisées que lorsque `EnableFAT` est actif ; dans les autres cas, conserver le chemin d'entrées prévu par le programme. Ce helper n'écrit aucune adresse matérielle et ne crée pas la logique de commande de la cuve.

L'ordre des appels reste à concevoir : les entrées simulées doivent alimenter la logique testée, puis les commandes résultantes doivent être publiées. Selon les blocs existants, des affectations séparées avant/après la logique seront plus adaptées qu'un appel unique du helper. Consigner tout retard d'un cycle induit par le raccordement.

## 2. Utiliser TCP/IP local isolé

Siemens documente le serveur OPC UA de PLCSIM Advanced sur les chemins **TCP/IP Single Adapter / Multiple Adapter** ; le chemin Softbus ne le fournit pas. Dans le Control Panel, la sélection **`<Local>`** désactive le Virtual Switch vers les adaptateurs physiques et conserve la communication TCP/IP locale par l'adaptateur virtuel. [Communications Siemens](https://docs.tia.siemens.cloud/r/simatic_s7_1500_et_200mp_manual_collection_enus_21/comprehensive-information/cpu-function-manuals/s7-plcsim-advanced/communication-paths/communication) · [Control Panel et Local](https://docs.tia.siemens.cloud/r/simatic_et_200sp_manual_collection_enus_20/general-information/cpu-function-manuals/s7-plcsim-advanced/simulating/simulating-a-cpu/control-panel-user-interface/s7-plcsim-advanced-control-panel).

Sur le poste cible :

1. Choisir le mode TCP/IP applicable à la version installée et la liaison `<Local>`.
2. Créer/identifier l'instance virtuelle convenue et son adresse IP locale.
3. Vérifier les routes, ponts, VPN et réglages de la VM éventuelle : aucune liaison du banc vers un réseau de production ne doit être introduite.
4. Laisser l'échelle de temps PLCSIM à **1×** pour la première qualification.
5. Charger manuellement la copie du projet dans cette instance depuis TIA, puis vérifier son état d'exécution dans Siemens.

Ces actions restent réalisées dans Siemens par l'automaticien. Le banc FAT n'a pas de commande de téléchargement ni de RUN/STOP CPU.

## 3. Configurer le serveur et ses variables OPC UA

Activer le serveur OPC UA supporté par la CPU/firmware retenus. Configurer les interfaces, droits, politiques et certificats selon la documentation correspondant à cette combinaison. Les licences nécessaires restent celles du poste Siemens.

| Variables du DB | Type | Accès du banc |
| --- | --- | --- |
| `PumpCmd`, `InletCmd` | BOOL | Lecture |
| `OutletCmd` | REAL | Lecture |
| `LevelPct`, `VolumeL` | REAL | Écriture |
| `PumpRunning`, `PumpFault` | BOOL | Écriture |
| `InletPosition`, `OutletPosition` | REAL | Écriture |
| `InletOpen`, `InletClosed`, `LevelHigh`, `LevelLow` | BOOL | Écriture |

Limiter les droits du client aux variables nécessaires. Relever les **NodeIds réels**, l'URI de namespace, l'**ApplicationUri** serveur et son certificat. Une chaîne ressemblant à `ns=3;s="DB_FAT"."LevelPct"` dans le projet fourni est un exemple, pas une adresse garantie par Siemens. Le numéro de namespace peut changer ; l'URI de namespace configurée permet sa résolution avant validation.

FAT Studio prend en charge `None` ou **Basic256Sha256 / SignAndEncrypt**. Si un nom utilisateur est nécessaire, le chiffrement est obligatoire dans cet adaptateur. Le projet conserve seulement les noms de variables d'environnement, jamais le mot de passe. Les chemins de certificat client et de clé privée pointent vers des fichiers sur le poste ; le serveur doit faire confiance au certificat client selon sa configuration.

## 4. Autoriser la cible sur le poste

La politique locale est séparée des JSON de projet : importer un projet ne peut pas autoriser sa propre cible. Les noms DNS, IP publiques et URL contenant des identifiants sont refusés. Une adresse privée n'est toutefois pas une preuve de virtualisation : l'isolation doit être vérifiée par l'opérateur.

### Exemple SignAndEncrypt

Remplacer les valeurs entre chevrons et adapter l'adresse à l'instance observée :

```powershell
.\.venv\Scripts\python.exe -m fat_studio authorize-target `
  --name "PLCSIM_TK101" `
  --endpoint "opc.tcp://192.168.50.10:4840" `
  --application-uri "<ApplicationUri_observee>" `
  --server-certificate-sha256 "<64_caracteres_SHA256_du_certificat_serveur>" `
  --client-certificate "C:\FAT\certs\client.der" `
  --client-private-key "C:\FAT\certs\client-key.pem" `
  --isolated-virtual-adapter
```

La commande affiche la cible et demande de saisir exactement :

```text
PLCSIM_TK101 @ opc.tcp://192.168.50.10:4840
```

Si une authentification utilisateur est configurée, ajouter `--username-env FAT_OPCUA_USER --password-env FAT_OPCUA_PASSWORD`. Définir ces variables dans l'environnement du service selon la procédure de secrets du site. Les valeurs de secrets ne sont pas des arguments du projet ou du CLI.

### Cas d'une configuration locale sans chiffrement

Uniquement pour la configuration isolée convenue, autoriser explicitement `None` :

```powershell
.\.venv\Scripts\python.exe -m fat_studio authorize-target `
  --name "PLCSIM_TK101" `
  --endpoint "opc.tcp://192.168.50.10:4840" `
  --application-uri "<ApplicationUri_observee>" `
  --isolated-virtual-adapter --allow-insecure
```

Cette commande ne désactive aucune protection Siemens et n'ouvre pas de port Windows. Elle enregistre l'accord pour cet endpoint précis. L'ApplicationUri avec `None` n'est pas une identité cryptographiquement authentifiée. Le contrôle de topologie reste indispensable.

## 5. Configurer FAT Studio

Dans **Connexion** :

1. Sélectionner OPC UA.
2. Renseigner exactement le même nom, endpoint, ApplicationUri, empreinte, chemins de certificats et noms de variables d'environnement que dans la politique du poste.
3. Dans **Variables & mapping**, remplacer les NodeIds d'exemple par ceux réellement observés.
4. Définir les paramètres de procédé et garder la vitesse à 1×.
5. Enregistrer et valider.
6. Démarrer un **essai libre** pour la preuve de communication ; saisir à nouveau la cible affichée.

Avant la première écriture, l'adaptateur vérifie la cible autorisée, l'identité serveur, les NodeIds, les types et les droits applicables. Il rejette également les nœuds système du namespace 0. Une écriture partielle ou une mauvaise qualité de lecture met fin à l'essai, sans reprise automatique.

## 6. Prouver la boucle avant de lancer la FAT

Réaliser et consigner les contrôles suivants sur l'instance virtuelle :

1. Faire produire une commande par le programme existant et constater sa lecture dans FAT Studio.
2. Observer une mesure simulée dans `DB_FAT` puis dans le bloc qui la consomme réellement. Une variable visible dans un DB ne prouve pas à elle seule que la séquence testée l'utilise.
3. Tester chaque type utilisé. Le DB de démonstration utilise BOOL et REAL ; ajouter des variables de preuve distinctes INT/DINT si ces types sont requis par le projet réel.
4. Vérifier qu'aucun autre bloc n'écrase les entrées simulées à chaque cycle.
5. Injecter un défaut moteur ou un capteur figé et constater la réaction attendue du programme.
6. Provoquer une perte de communication contrôlée : constater l'erreur, l'arrêt des écritures et l'absence de reprise automatique.
7. Exporter le rapport et joindre les observations Siemens ainsi que les versions relevées.

Le statut « serveur OPC UA Running » est un diagnostic du serveur, **pas une lecture de l'état RUN/STOP de la CPU**. Cette version n'utilise pas l'API native PLCSIM pour obtenir cet état. Une pause du banc n'arrête pas la CPU, et une perte de communication peut laisser les dernières valeurs dans son DB. Les séquences nécessitant un watchdog doivent disposer du mécanisme convenu dans la copie du programme et d'un protocole d'essai adapté.

Les essais de référence fournis sont liés au contrôleur de démonstration. Remplacer leurs seuils, temporisations et critères par ceux de votre programme avant d'enregistrer un verdict de FAT.

## Interfaces et droits

| Interface | Usage |
| --- | --- |
| HTTP loopback `127.0.0.1:8765` par défaut | Navigateur vers service FAT ; pas d'écoute sur le réseau physique. |
| OPC TCP vers l'IP virtuelle et le port configuré | Échange de variables ; 4840 est un exemple, relever le port réel. |
| Fichiers locaux | Projets JSON, historique SQLite, politique, certificats et clés client. |
| TIA Openness/MCP optionnel | Ingénierie distincte du runtime ; voir TIA_MCP.md. |

Le service FAT ne requiert pas de droits administrateur pour son fonctionnement courant. L'installation/configuration Siemens, les certificats, les droits Openness et les règles réseau suivent les procédures du poste. L'API native PLCSIM n'est pas livrée dans cette version ; sa comparaison et les motifs du choix OPC UA figurent dans [UPSTREAM_REVIEW.md](UPSTREAM_REVIEW.md).
