# Livraison Vanguard FAT Studio, 4 novembre 2026

Reprise de la [session DA et vidéo](2026-11-03-vanguard-brand-video.md), branche `codex/vanguard-fat-studio-brand`. Les modifications du produit sont celles testées dans la session précédente. Cette reprise termine la vérification des livrables et prépare la branche pour revue.

Les deux dossiers scellés sont `C:/Vanguard_FAT_Studio_2026-11-03` et `C:/Vanguard_FAT_Studio_Source_2026-11-03`. Les cinq contrôles de service par kit, deux CLI, deux lanceurs et 19 appels du client public sont consignés dans `distribution/final-delivery-checks.json`. L'installation source a utilisé une copie. Les deux ZIP de livraison ont été construits à partir des manifestes puis relus avec contrôle CRC, ensemble exact d'entrées et SHA-256. Les empreintes sont dans `distribution/delivery-zips.json`.

Le film est livré avec deux MP4 de 45 s, SRT français et ZIP éditable de 113 entrées. Les deux masters ont été sondés avec FFprobe et la planche extraite a été relue. Les 36 contrôles vidéo et 19 contrôles de reproduction sont documentés dans `video/VERIFICATION.md`. Le serveur temporaire de capture est fermé. Le nettoyage de son seul dossier temporaire a été refusé par le contrôle automatique (« blocked by policy »). Il reste hors des livrables.

La suite locale compte 581 tests Python réussis, cinq ignorés sur ce compte Windows et 56 tests UI réussis. La campagne TIA V21 / PLCSIM Advanced 8 du 3 novembre compte 31 attentes réussies. La passe de marque a vérifié la lecture native et la présentation a été placée en pause avant STEP 1. La validation humaine et l'essai natif V20 restent à réaliser.

Pour reprendre, lire [l'état courant](../ETAT_REPRISE.md). Lancer le portable avec `Vanguard-FAT-Studio.cmd` ou vérifier le kit source avec `python scripts/check-kit.py --root <dossier>`. Sur ce poste, contrôler le contexte de l'instance dédiée sur le port 8770 avant de reprendre un essai. Garder les anciens kits, projets et preuves en place.
