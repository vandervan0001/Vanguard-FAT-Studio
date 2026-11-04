# Programme PLC public de laboratoire

Le générateur produit une DB standard `DB_FAT_Demo` et OB1 `Main` pour trois cuves, quatre pompes et huit vannes. Les 75 tags suivent [demo_contract.py](../fat_studio/demo_contract.py). Il ne contient ni bibliothèque client, ni FB, ni UDT, ni séquence de procédé. Ce programme passif sert à vérifier le trajet réel entre le simulateur de procédé, OPC UA et une CPU virtuelle ; il ne constitue pas un programme de production ou de sécurité.

Depuis la copie source et son environnement Python installé :

```powershell
python -m integrations.demo_plc build C:\FAT_Demo_Public
python -m integrations.demo_plc verify C:\FAT_Demo_Public
```

La destination doit être nouvelle. Le bundle contient sept fichiers : les sources DB et OB1 séparées, leur concaténation `plc/Program_All.scl`, une table des symboles, le projet FAT en mode démo Python, un guide et le manifeste SHA-256. La vérification refuse les fichiers manquants, modifiés ou supplémentaires et les chemins par lien symbolique ou jonction. Le manifeste détecte les altérations du contenu ; il ne remplace pas une signature de provenance.

`EnableDemo` vaut **FALSE** dans la source canonique. Les commandes des pompes et vannes tout ou rien valent `EnableDemo AND StopHealthy AND Request`. Les vitesses demandées sont limitées à 0…100 lorsque cette commande est active, sinon elles valent zéro. FCV302 reçoit une demande de position analogique : sa sortie est limitée à 0…100 lorsque `EnableDemo AND StopHealthy`, sinon zéro. Les niveaux utilisent les instructions Siemens natives `NORM_X` et `SCALE_X`, de 0…27648 points à 0…100 %. Il n'y a ni mémorisation de défaut, ni acquittement, ni diagnostic d'équipement. L'entrée `Fault` d'une pompe est un retour simulé visible ; elle n'ajoute aucune logique métier au PLC.

Vanguard FAT Studio écrit les demandes opérateur, les retours d'équipements et les valeurs des capteurs simulés. Le programme PLC écrit les commandes ; ces sorties ne sont pas des tags de forçage FAT. Les REAL échangés sont des Float32. L'entrée `EnableDemo`, masquée aux clients OPC UA, est réservée à la préparation explicite de la copie virtuelle.

Pour une passe Siemens, créer **un projet TIA V21 neuf** et une CPU PLCSIM Advanced dédiée. Conserver les projets et essais existants. Choisir une adresse sur un adaptateur Siemens isolé, sans passerelle ni liaison PLCSIM vers une carte physique. Activer le support simulation du projet, le serveur OPC UA et son certificat SHA-256 ; conserver ses secrets dans un stockage local protégé. Importer uniquement `plc/Program_All.scl` comme source externe, générer les deux blocs, puis compiler le matériel et le logiciel. La copie privée destinée à cette seule CPU virtuelle peut passer `EnableDemo` à TRUE ; conserver la source publique inchangée et une preuve du seul écart.

Le téléchargement et le RUN/STOP suivent le workflow d'ingénierie humain autorisé. Le client IA public ne propose pas de commande CPU. Après chargement, relever le numéro réel de DB et ses offsets depuis l'export Openness `WithReadOnly`, puis parcourir le vrai serveur OPC UA. `tags.csv` laisse volontairement adresses et NodeIds vides : compléter les 75 lignes avec les valeurs observées, le type et l'accès de chaque nœud. Ne pas déduire un numéro de DB, un namespace ou une adresse physique à partir de cet exemple.

Sur une nouvelle instance FAT locale, importer une copie du projet dont les 75 tags sont reliés à ces NodeIds observés. Choisir `Basic256Sha256 / SignAndEncrypt`, épingler le certificat serveur et son ApplicationUri, fournir le certificat client et sa clé dans un dossier protégé, et approuver séparément la cible dans la politique du poste. L'identité est vérifiée avant l'authentification et les écritures. La validation du projet et des mappings doit réussir avant de démarrer.

Le [client public](AI_CONTROL.md) permet ensuite de capturer le contexte, importer ce projet, valider, démarrer un scénario avec sa confirmation exacte de cible, lire l'état et exporter l'essai. Exemple pour une instance FAT locale dont l'URL et la cible ont été préparées :

```powershell
$fatUrl = 'http://127.0.0.1:8765'
$fatContext = 'C:\FAT_Demo_User\contexte.json'
python -m fat_studio.assistant --url $fatUrl --context $fatContext context
python -m fat_studio.assistant --url $fatUrl --context $fatContext load-project C:\FAT_Demo_User\projet-opcua-observe.json
python -m fat_studio.assistant --url $fatUrl --context $fatContext validate
python -m fat_studio.assistant --url $fatUrl --context $fatContext start --scenario demo-fill-source --target-confirmation '<nom instance> @ <endpoint observé>'
python -m fat_studio.assistant --url $fatUrl --context $fatContext state
python -m fat_studio.assistant --url $fatUrl --context $fatContext export --run '<run_id renvoyé>' --kind json --output C:\FAT_Demo_User\essai.json
python -m fat_studio.assistant --url $fatUrl --context $fatContext stop
```

Adapter l'URL au serveur démarré. Remplacer les éléments entre chevrons par les valeurs observées et la confirmation exacte déjà enregistrée dans la politique du poste. Le contexte est capturé explicitement ; une commande refusée sur un contexte périmé demande une inspection, pas une répétition automatique. Le fichier d'export doit être nouveau. Pour le premier STEP guidé, choisir `demo-guided-io` au démarrage puis `step-execute guided-initial` ; cette commande prépare les entrées et ne remplit aucune observation. Utiliser `python -m fat_studio.assistant --help` pour la syntaxe installée.

Les scénarios techniques testent ce programme public ; ils ne qualifient aucune bibliothèque privée. Un scénario guidé conserve ses observations et son verdict humains à remplir par l'opérateur. Une perte de communication arrête explicitement l'essai, rend la qualité visible et ne déclenche aucune reconnexion automatique. La [passe native du 3 novembre 2026](../evidence/reprises/2026-11-03-public-demo/native/VERIFICATION.md) conserve les correspondances réellement observées et les essais de cette version.

Les résultats d'une compilation ou d'un essai Siemens sont des preuves distinctes des tests du générateur. Les preuves datées indiquent leur matériel virtuel, leur certificat, les sources chargées, les mappings observés, les commandes exécutées et leurs limites.
