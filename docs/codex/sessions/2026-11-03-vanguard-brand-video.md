# Vanguard FAT Studio : DA et vidéo, 3 novembre 2026

Demande de Tai : appliquer la direction artistique de `vanguard_systems`, renommer le produit et le dépôt GitHub, puis créer une présentation LinkedIn rythmée, sous-titrée et sans voix. Travail sur `codex/vanguard-fat-studio-brand`, depuis HEAD `cd4daba16580309a675dfa6b1ec95efe5a669038` et ses modifications précédentes conservées. Aucun reset ; checkpoint privé de 588 fichiers vérifié avant édition.

L'identité reprend les logos originaux et les fontes Geist/OFL du dépôt de marque au commit `b4df8d8ed0942e98ceee643a9be210f00aca9e9f`, son bleu `#0055DD` et ses surfaces claires. Aucune reprise du code métier du site ou d'une autre identité de partenaire. Les couleurs de marche, défaut et qualité restent sémantiques. Les contrats et archives antérieurs restent compatibles.

Fichiers root : `fat_studio/branding.py`, `app.py`, `reporting.py`, `storage.py`, `adapters/opcua.py`, docstring `__init__.py`, régression historique dans `tests/test_archive.py`, cette note et l'état courant. Le frontend possède ses vues/assets/tests ; distribution possède CLI, métadonnées, lanceurs, docs et filtres publics ; vidéo travaille dans `media/vanguard-fat-studio/` sans toucher les services ni CPU réels.

Vérifications acquises : 75 tests ciblés, 38 API et 25 archives ; première globale 579 réussis/cinq ignorés Windows ; deux cas Unicode de confidentialité corrigés puis 69 tests distribution/CLI/smoke réussis/quatre ignorés. Dernière globale complète après ce correctif : **581 réussis, cinq ignorés**, en 234,41 s. Frontend final : 56/56 en 161,480624 s, plus fenêtre réelle et cadrage 1/1 chacun. Les sources et assets n'ont pas changé après cette suite.

Les rapports sont autonomes : logo et trois fontes embarqués, rendus relus à 1440 et 390 pixels, aucune dépendance externe, aucun script ou débordement. Une lecture réelle avec le nouveau nom client OPC UA a validé 75 mappings et lu 19 sorties, en SignAndEncrypt avec le certificat/URI existants, zéro écriture et zéro commande CPU. L'archive native antérieure de 19 essais a été restaurée avec ses rapports/historique exacts. Les prototypes source/portable ont passé deux alias CLI/lanceurs et cinq contrôles de service chacun hors sources, avec intégrité préservée.

Preuves sous `evidence/reprises/2026-11-03-vanguard-brand/`. Les anciens kits scellés et preuves round 5 restent intacts ; les 31 attentes natives antérieures ne sont pas présentées comme une nouvelle campagne complète. La vidéo utilise des captures réelles d'une démo temporaire sur 8774, signalées comme telles, et une preuve native datée distincte.

La présentation réelle 8770 a été explicitement mise en pause avant édition, même essai avant STEP 1, aucune observation, historique conservé. Root seul peut arrêter/redémarrer ce service dédié sur les sources brandées ; l'ancienne instance 8768 et les CPU ne sont pas à modifier. Le framebuffer et les données du film restent temporaires.

À poursuivre : résultat de la globale finale, renommage GitHub et origin, revue du code public sur branche, gel documentaire puis nouvelles livraisons, brouillon/revue/master MP4 et contrôles FFprobe, mise à jour des reçus et état. Aucune publication LinkedIn ni changement de visibilité du dépôt demandé.


## Produit gelé et GitHub renommé

Le dépôt est désormais `https://github.com/vandervan0001/Vanguard-FAT-Studio`, même ID 1443049301 et toujours privé ; origin est mis à jour. Aucun changement de visibilité ou publication LinkedIn. La preuve `github-rename.json` conserve les métadonnées avant/après. Le code public sur branche reste à préparer pour revue.

Les 581 tests Python et 56 tests frontend sont verts. Les rapports ont été relus sur deux tailles, les huit assets officiels sont identiques et le nouveau nom du client a été vérifié sur une session réelle chiffrée sans écriture. Le seul backend 8770 a été redémarré sur les sources actuelles, ancien essai arrêté et conservé. Nouvelle copie locale de démo avec mêmes mappings, cinq échanges réels et 75 good, puis pause avant STEP 1 : `native-presentation.json`. Aucun ancien projet/historique supprimé ni CPU commandée.

Le premier brouillon vidéo de 45 s a passé ses contrôles techniques. Revue de planche MP4 : trois cadrages timed/rapport/archive à corriger, tendances à limiter à trois tags et intersection du trait avec le domaine CTA à enlever. Corrections du montage/captures uniquement ; source produit et assets restent gelés. Master après seconde revue.
