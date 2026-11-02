# Compatibilité et limites de qualification

## Trois niveaux de preuve

1. **Code implémenté et tests locaux** : moteur, application et contrôles d'erreur exécutés sur l'environnement de développement. Consulter le rapport de vérification livré pour les résultats précis.
2. **Protocole exercé contre un double de test** : OPC UA et MCP peuvent être exécutés localement contre des serveurs de test. Cela vérifie la sérialisation, les types, les droits et les erreurs simulées.
3. **Qualification Siemens sur Windows** : TIA Portal, firmware de CPU, PLCSIM Advanced et projets réels doivent être essayés sur le poste cible. Aucun succès local ne remplace ce niveau.

## Matrice

| Composant | Cible choisie | État / preuve |
| --- | --- | --- |
| Application locale et procédé démo | Python 3.12 ; interface construite depuis le lock Node | Implémentés ; scripts et tests livrés. |
| Adaptateur OPC UA | Bibliothèque `asyncua`, versions exactes dans le lock Python | Implémenté ; serveur OPC UA de test disponible. |
| PLCSIM Advanced | OPC UA d'une CPU virtuelle configurée, accès TCP/IP avec liaison `<Local>` | Documentation Siemens examinée ; qualification réelle à effectuer. |
| CPU et firmware du client | À relever sur le poste cible | Non fournis dans l'URS. Aucune compatibilité universelle revendiquée. |
| API native PLCSIM Advanced | Non utilisée par cette version | Comparée ; pas d'adaptateur natif livré ni de DLL Siemens requise pour la démo. |
| TIA MCP | Czarnak `TiaMcpServer` **4.3.0**, tag/commit fixés | V21 : paquet amont ; V20 : candidat de portage source local. Contrats et profils testés ; aucune qualification Siemens déduite des doubles. |
| TIA Portal / Openness du volet MCP | Choix **V20/V21**, projet standalone `.ap20` ou `.ap21` | V20 exige une compilation réussie contre les vraies DLL V20 ; build et essais Siemens à effectuer sur le poste. Voir [TIA_VERSIONS](TIA_VERSIONS.md). |
| Hôte MCP upstream | .NET 10 SDK stable **10.0.400 ou supérieur dans les branches 10.0** | Prérequis upstream ; l'installateur lance `doctor`. |
| Worker Openness upstream | .NET Framework **4.8** + groupe Windows `Siemens TIA Openness` | Prérequis upstream ; DLL chargées depuis Siemens. |
| Client MCP Python | **mcp 2.3.0**, négociation legacy explicite | Transport stdio réel vérifié avec serveur SDK factice. |
| Claude Code / Codex | Serveur stdio standard en lecture seule ; snippets générés | Configuration générée ; clients réels non lancés dans cet environnement. |
| Projets Multiuser `.amc20` / `.als20` / `.amc21` / `.als21` | Non acceptés par le CLI d'écriture | Restriction du parcours sauvegarde/import. |
| Blocs SCL / DB globaux | Export `source` si accepté par TIA | Contrats upstream lus ; chaque type de bloc doit être qualifié. |
| LAD / FBD et autres langages | Export/import XML dans les limites upstream | Diff XML possible ; pas de promesse d'édition graphique universelle. |
| Blocs protégés, sécurité, motion, CPU physique | Aucune validation fonctionnelle spécialisée | Hors périmètre de validation du banc. |

Le catalogue Siemens annonce pour PLCSIM Advanced V8 le support de projets TIA V14–V21 et de CPU supplémentaires, dont S7-1200 G2. Cette annonce ne suffit pas à garantir une combinaison précise de CPU, firmware et fonctions de communication. Référence : [catalogue Siemens](https://sieportal.siemens.com/en-us/products-services/10317038?tree=CatalogTree).

## Fiche à compléter avant la première écriture sur PLCSIM

| Champ | Valeur relevée / preuve |
| --- | --- |
| Windows, build, architecture | À relever sur le poste de FAT |
| TIA Portal version et Update | À relever |
| CPU simulée, référence et firmware | À relever |
| PLCSIM Advanced version et Update | À relever |
| Nom d'instance virtuelle | À relever |
| Mode réseau / adaptateur | TCP/IP ; liaison `<Local>` constatée |
| IP, endpoint OPC UA, namespace/NodeIds | À relever à partir du serveur configuré |
| Authentification, certificats, politiques OPC UA | À documenter, aucune désactivation globale de sécurité |
| Compte/droits de lecture/écriture | Écritures limitées aux entrées simulées du DB convenu |
| Première lecture BOOL, INT, DINT, REAL | Valeurs attendues et observées à joindre |
| Première écriture sur entrée FAT | Valeur affichée dans TIA à joindre |
| Perte de communication | Cessation des écritures et reconnexion volontaire à vérifier |
| Horodatage et responsable de qualification | À consigner |

Ne pas remplir les résultats de cette fiche avec des valeurs issues du serveur factice. Les tests et rapports doivent distinguer explicitement démonstration, test de protocole et qualification sur PLCSIM.

## Qualification de l'ingénierie TIA

Sur une copie de test sans liaison à la production :

1. Exécuter `tia-mcp doctor` ; consigner les versions et droits remontés.
2. Ouvrir et sauvegarder la copie `.ap20` ou `.ap21` dans la version TIA choisie, avec son profil MCP vérifié.
3. Vérifier `status`, `tree` puis l'export d'un bloc SCL ou DB simple.
4. Modifier `after.scl`, examiner le diff, refuser l'application et constater l'absence de changement.
5. Refaire l'essai en acceptant : constater l'archive `.zap20` ou `.zap21` du profil, l'import, les diagnostics et le résultat dans TIA.
6. Tester une source modifiée entre export et import : l'import doit être refusé.
7. Tester une compilation défectueuse : les erreurs doivent être conservées ; le CLI ne doit pas sauvegarder automatiquement.
8. Réouvrir l'archive dans un emplacement distinct et vérifier sa restaurabilité. La vérification de fichier non vide et son SHA-256 ne prouvent pas, à elles seules, une restauration Siemens réussie.
9. Consigner les essais dans un rapport de qualification lié au commit de ce dépôt et au tag MCP épinglé.

Les contrôles applicatifs protègent contre des erreurs d'utilisation. Ils ne constituent pas une frontière de sécurité contre un programme malveillant lancé avec le même compte Windows, capable de modifier le code ou les fichiers de politique.

## Essayer le protocole OPC UA sans Siemens

Le dépôt fournit `scripts/opcua-fixture.py`, un serveur OPC UA générique lié uniquement à `127.0.0.1`. Il reprend les 13 tags du projet de démonstration et exécute le contrôleur fictif toutes les 100 ms. Le moteur de procédé reste exclusivement dans l'application FAT : le serveur n'invente pas de valeurs capteurs et ne simule pas une CPU Siemens.

Dans un premier terminal, depuis le dépôt :

```powershell
.\.venv\Scripts\python.exe scripts\opcua-fixture.py
```

Le script génère `.local\opcua-fixture.project.json` et imprime l'identité exacte du serveur. Il ne modifie aucune autorisation. Dans un deuxième terminal :

```powershell
.\.venv\Scripts\fat-studio.exe authorize-target `
  --endpoint 'opc.tcp://127.0.0.1:48450/fat-fixture/' `
  --application-uri 'urn:fat-studio:generic-opcua-fixture' `
  --name 'Generic OPC UA fixture' --isolated-virtual-adapter --allow-insecure
```

Pour cet essai générique, le drapeau d'isolation correspond au serveur **loopback** du script, pas à une instance PLCSIM. La confirmation demandée est `Generic OPC UA fixture @ opc.tcp://127.0.0.1:48450/fat-fixture/`. Si l'application utilise un `--data-dir` particulier, fournir ce même répertoire à `authorize-target`.

Démarrer FAT Studio, importer le fichier généré, puis lancer le scénario de référence en confirmant cette cible. L'interface échange alors réellement des messages OPC UA avec un processus distinct. Arrêter le premier terminal avec Ctrl+C pendant l'essai : le banc doit passer en erreur, marquer les qualités invalides et arrêter les écritures sans reconnexion automatique.

La suite `tests/test_opcua.py` vérifie aussi sur de vrais sockets loopback les quatre types scalaires BOOL/INT/DINT/REAL, la résolution du namespace par URI, les variables manquantes, types ou droits incompatibles, une écriture partiellement refusée, les mauvaises qualités et le chiffrement Basic256Sha256 avec certificat serveur épinglé. Cette preuve porte sur le protocole OPC UA générique ; elle n'est jamais enregistrée comme un essai Siemens réussi.
