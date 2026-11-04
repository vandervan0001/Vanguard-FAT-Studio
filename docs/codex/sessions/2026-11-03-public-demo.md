# Reprise publique du 3 novembre 2026

Cette reprise prépare une livraison locale de FAT Studio limitée au banc FAT/test et à une démo PLC passive. Les standards et sources d'ingénierie privés restent hors de Git et des distributions. Les sauvegardes privées et les anciennes livraisons vérifiées ont été conservées. Aucun commit, push ou publication n'a été exécuté.

## État Git et modifications

Branche `codex/windows-local-setup`, HEAD `cd4daba16580309a675dfa6b1ec95efe5a669038`, modifications locales conservées. Les principaux changements portent sur :

- Le contrat de démonstration `fat_studio/demo_contract.py`, son projet `demo_lab.py` et le générateur passif `integrations/demo_plc.py`.
- Le modèle de transfert entre cuves, le contrôleur de référence explicitement réservé à la démo et les animations associées aux tags.
- Les formats versionnés `exchange.py`, les archives `archive.py`, les espaces locaux `workspaces.py`, l'API et les commandes CLI/client IA correspondantes.
- Le frontend, les pupitres, les scénarios temporisés et guidés, le builder en pause et les tests navigateur sur données temporaires.
- La sélection explicite des fichiers publics, les hooks de build et les scripts de construction/vérification du portable Windows.
- Les guides utilisateur, d'installation, de formats, d'archives et de commande par un assistant externe.

Le laboratoire comporte trois cuves, quatre pompes, huit vannes, 75 tags et 36 objets, dont 24 physiques. Les huit scénarios temporisés ont 31 attentes ; la FAT guidée comporte cinq STEP. Le programme PLC public contient uniquement une DB et OB1 : demandes manuelles, commandes, retours et conversion linéaire native. Aucun standard métier n'est distribué.

## Vérifications déjà acquises

La campagne TIA V21 / PLCSIM Advanced 8 a compilé et chargé le nouveau programme dans une CPU virtuelle dédiée. Les huit scénarios ont réussi leurs 31 attentes par le client public, avec OPC UA Basic256Sha256/SignAndEncrypt, 75 tags réels, 460 échantillons et 9 660 valeurs REAL vérifiées Float32. Le premier STEP technique a appliqué 12 mA / 13 824 bruts / 50 %, sans observation ni verdict humain. Les preuves sont sous [native](../../../evidence/reprises/2026-11-03-public-demo/native/VERIFICATION.md).

La première suite Python globale a réussi 568 tests avec cinq contrôles de liens symboliques ignorés sous ce compte Windows. Les tests de frontières ont ensuite reproduit et corrigé plusieurs défauts : archives d'essais terminés, conservation des preuves après erreur d'édition, contexte d'export entre espaces identiques, contexte du client après réouverture de l'espace actif et export d'archive bloquant les commandes. La suite finale sur ces dernières sources et le bundle copié a réussi **572 tests, cinq ignorés**, en 257,13 s. Les 45 tests d'archives/client/échanges passent ; les quatre défauts backend ont une contre-vérification indépendante. Les originaux JUnit et leurs copies de travail restent conservés à part, hors Git et distribution. Les identifiants automatiques des tests de confidentialité peuvent contenir leurs sentinelles ; le reçu `python-verification.json` conserve les compteurs et empreintes sans publier ces rapports.

Les exemples versionnés correspondent exactement à la factory courante et les trois schémas JSON aux modèles. Ruff passe sur le périmètre produit/intégrations/tests/scripts et les modules de distribution ; le contrôle public compte 310 fichiers autorisés à cette étape. Les anciens helpers de preuves ne sont pas réécrits pour satisfaire le lint courant.

Un prototype du portable embarquant Python 3.12.10 a passé cinq contrôles de service et 39 appels du client public hors sources, avec un PATH limité et sans Python/Node installés globalement. Ce prototype ne remplace pas la vérification du portable final.

La suite navigateur finale a réussi **54 tests**, sans échec, test ignoré ou flaky, en 145,771 s sur le bundle `index-Bi1N3rC1.js`. Le premier passage 51/54 a identifié trois attentes de tests devenues anciennes : input JSON ambigu, ancien libellé du laboratoire et comptage figé des tags après ajout d'un port facultatif. Elles ont été corrigées, vérifiées en ciblé puis toute la suite a été rejouée. Aucun changement produit pour ces adaptations ; les résultats initiaux restent conservés. Les empreintes des assets figurent dans `ui/final/assets.json`.

La nouvelle campagne sur le backend final a également réussi les huit scénarios et **31/31 attentes**, avec 140 appels du client public tous réussis. Elle conserve 460 échantillons, 25 760 écritures d'entrées et 9 660 REAL Float32. L'archive réelle de 19 essais a été restaurée dans un Store temporaire : les huit nouveaux essais conservent leur statut terminé et leurs données ; aucune politique/clé n'est restaurée, le workspace live n'a pas changé. Reçus [final-live](../../../evidence/reprises/2026-11-03-public-demo/final-live/VERIFICATION.md).

Après clôture de campagne, root a créé un nouvel essai guidé avant STEP 1 sur 8770, 75 tags good, CPU virtuelle dédiée RUN. Aucun STEP ni observe exécuté, aucun verdict humain. La fenêtre Edge réelle suit le poste à 125 % : contenu 1528 × 828, largeur document 1513, panneau analogique à 1512,8 ; aucun débordement à droite. Les captures et le reçu sont sous `presentation/`. Le premier préflight du harness cherchait un champ `security_mode` inexistant ; il a échoué avant toute mutation, puis a été corrigé pour lire le contrat `security_policy`. Le produit n'a pas changé.

## Reprise précise

Les suites, sources produit et livraisons sont figées. La wheel vérifiée contient 45 entrées et 39 payloads identiques aux sources/assets, SHA256 `df7af8daedcf0ebff512b4c749320bc63e8c6c0b82ea74ef9002f374a8e9aaf5`. Les destinations sont `C:/FAT_Studio_Public_2026-11-03` et `C:/FAT_Studio_Public_Source_2026-11-03`. Le bilan après scellement ci-dessous complète les reçus seulement dans les sources ; ne pas modifier une livraison après scellement. Une prochaine évolution nécessite une nouvelle copie source et une nouvelle destination de livraison.

```powershell
. .\.local\dev-env.ps1
python -m pytest -q --tb=short
python -m ruff check fat_studio integrations tests scripts public_distribution.py build_public.py
python public_distribution.py check
```

Le frontend possède le serveur temporaire 8766 jusqu'à son dernier contrôle de rendu. Les données natives sont séparées sur 8770, worker 6688. La campagne finale s'est terminée essai arrêté et CPU virtuelle STOP ; la présentation ultérieure de root est en RUN avant STEP 1, essai `run-84fc4a8c7b974bd2a842381d398e1763`. Relire son état avant action. L'ancienne instance et ses essais restent conservés. Aucun contrôle de CPU physique ni qualification V20 ne découle de ces tests.

## Après scellement

Les deux livraisons finales sont conservées intactes : portable `C:/FAT_Studio_Public_2026-11-03`, 3 090 fichiers manifestés ; source `C:/FAT_Studio_Public_Source_2026-11-03`, 483 fichiers dont 29 wheels. Le contrôle root `launch.py --check` du portable et `check-kit.py` du source passent. Les manifestes respectifs sont `9d0298725633d78766bb7e185a18d6d2ddacff01aa0c2e7562954d5160873b93` et `e9d3fb6f8705ee35929c9315826cf3f2a644ce9456b31115ceb2773ca94ecee8`.

Le portable exact a passé cinq contrôles de service/redémarrage hors sources avec le runtime isolé et PATH minimal. Une **copie** du kit source s'est installée avec `PIP_NO_INDEX=1`, puis a passé les cinq mêmes contrôles. Les originaux n'ont pas changé. Les reçus sont [portable-final-service.json](../../../evidence/reprises/2026-11-03-public-demo/distribution/portable-final-service.json) et [source-final-service.json](../../../evidence/reprises/2026-11-03-public-demo/distribution/source-final-service.json).

Les ZIP sont construits uniquement à partir des entrées manifestées et du manifeste. CRC de toutes les entrées et SHA-256 de chaque contenu décompressé vérifiés, manifestes inchangés :

- `.local/FAT_Studio_Public_2026-11-03.zip` : 40 345 988 octets, 3 091 entrées, SHA256 `eb9bc1a41988be6346f55a615e06421ca2393fea018e78abaa288db5aa9b8a15`.
- `.local/FAT_Studio_Public_Source_2026-11-03.zip` : 16 593 236 octets, 484 entrées, SHA256 `64c749439ef599c511cf280faf470f9cc0f0d07de2cf5a6eadf9b5a32b42cba2`.

Le [client IA sur le portable final](../../../evidence/reprises/2026-11-03-public-demo/distribution/portable-final-client.json) a exécuté 37 commandes publiques réussies : quatre attentes temporisées, export/import JSON et scénarios, restauration de l'archive d'un essai terminé, nouvelle révision d'espace, contexte conservé pendant les polls, STEP technique 13 824 et trois exports. Aucun observe ni verdict humain. Les [contrôles de livraison](../../../evidence/reprises/2026-11-03-public-demo/distribution/final-delivery-checks.json) confirment 333 liens locaux, les manifestes intacts après tous les essais et aucun serveur de test laissé actif.

Reçu [delivery-zips.json](../../../evidence/reprises/2026-11-03-public-demo/distribution/delivery-zips.json). Ces bilans sont ajoutés seulement dans les sources après scellement, sans réécrire les dossiers livrés ni les anciennes livraisons. Travail autorisé terminé pour ce périmètre local, aucun commit/push/publication. La réception humaine reste à effectuer ; la dernière lecture native conserve le nouvel essai connecté, 75 qualités good et zéro STEP/observation.
