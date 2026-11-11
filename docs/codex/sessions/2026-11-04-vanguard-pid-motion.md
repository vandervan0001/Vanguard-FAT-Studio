# Démo animée Vanguard FAT Studio, 4 novembre 2026

Tai demande des gestes continus et un montage équilibré entre construction, forçage, essai automatique et STEP guidé. Le travail part du bundle déjà livré au commit `f5ad062cfc9babbd2ab61d22ee55528ad0fc7979`. Les changements Git de départ, les anciennes vidéos et les kits scellés sont conservés.

Les sources sont dans `.local/vanguard-pid-motion-2026-11-04/film/`. `scripts/live-footage.mjs` et `scripts/capture-motion.mjs` ont enregistré 635 images navigateur sur neuf prises. La prise a vérifié trois glisser-déposer natifs et deux conduites sauvegardées. Le curseur de tournage affiche le SVG de l’icône issue de la palette pendant le geste. Les conduites, la rotation, le débit et le niveau viennent du rendu de l’application.

Le scénario temporisé a exécuté trois contrôles conformes. Le STEP a été appliqué sans observation saisie. Le pupitre de la démo laboratoire a produit une impulsion TOR et appliqué 12 mA, soit 13 824 points et 50 %. L’instance de prise 8776 était isolée et en mode démo. Elle a été arrêtée proprement.

Les masters locaux sont composés par `scripts/compose-motion.py`, avec la musique de `scripts/audio.mjs`. Le reçu de prise est `footage/takes.json`. La procédure complète et les dépendances sont dans `README-MOTION.md`. Les sorties, planches et vérifications sont dans `exports/`.

La revue du brouillon a conduit à agrandir la zone de dépose et le bouton du STEP. La planche extraite du master montre les positions successives de l’icône, le raccord des ports et la continuité du niveau au défaut. FFprobe a décodé 1 680 images à 30 images/s pour chaque master, soit 56 secondes en 1080 × 1350, H.264 BT.709. Le flux vidéo est identique avec ou sans musique. Les empreintes et les résultats d’essai figurent dans `exports/verification-master.json`.

À la demande de Tai, les deux MP4 et le SRT ont été ajoutés à la [release publique](https://github.com/vandervan0001/Vanguard-FAT-Studio/releases/tag/public-preview-2026-11-04). Le MP4 avec musique figure en tête sous « Vidéo à partager ». Les tailles et SHA-256 des trois fichiers distants correspondent aux exports locaux. Reçu dans `.local/vanguard-pid-motion-2026-11-04/publication-receipt.json`. Pour un post, télécharger le MP4 de la release et le joindre comme vidéo native.
