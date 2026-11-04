# Vanguard FAT Studio — film de présentation

Film de 45 secondes au format 4:5, avec sous-titres français intégrés, sans voix. La version sonore utilise une composition synthétisée localement, sans échantillons externes. Une version silencieuse et le fichier SRT sont fournis.

Les vues du produit proviennent d’une instance temporaire en **mode démonstration**, avec 75 variables. Elles montrent des commandes et des exports réellement exécutés. Le premier STEP est appliqué, sans observation ni verdict humain. L’instance de capture n’a aucune connexion OPC UA.

La séquence « 31 / 31 » renvoie à la campagne Siemens du **3 novembre 2026**, sur TIA V21 et PLCSIM Advanced 8, exécutée avant le film. Elle ne décrit pas la connexion des captures de démonstration. Sa provenance est conservée dans [historical-proof.json](assets/historical-proof.json).

Le film se termine par « Vanguard FAT Studio / Version en préparation / vanguard-systems.ch ». Il ne présente ni prix, ni date de sortie, ni dépôt public disponible. Aucun média n’a été publié sur LinkedIn ou envoyé à un tiers.

## Refaire le rendu

Les PNG d’entrée sont inclus ; aucune application FAT ou connexion PLC n’est nécessaire pour refaire le film. Le lecteur et l’export utilisent le même Canvas déterministe : `window.ready` attend les ressources, puis `window.seek(seconds)` calcule l’image à un instant donné.

Installer Node, Chromium via Playwright et FFmpeg avec `libx264` et FFprobe, disponibles dans le `PATH`. Versions utilisées : Node 22.23.4, Playwright 1.56.1, Chromium 141.0.7390.37, FFmpeg / FFprobe 9.0.2. Les dépendances JavaScript sont verrouillées ; aucun exécutable FFmpeg ou Chromium n’est redistribué.

Depuis ce dossier :

```powershell
npm ci --legacy-peer-deps --ignore-scripts
npx playwright install chromium
npm run preview
```

Le lecteur local s’ouvre sur `http://127.0.0.1:4173`. Dans un second terminal :

```powershell
npm run subtitles
npm run draft
npm run check -- --draft
npm run master
npm run check
```

Le brouillon est en 720 × 900 à 15 images/s ; le master en 1080 × 1350 à 30 images/s. Les MP4 H.264 utilisent yuv420p, BT.709 et faststart. Le contrôle décode les images, vérifie leur nombre et les métadonnées, compare les pixels après plusieurs parcours temporels, mesure l’audio AAC et extrait la planche depuis les MP4. La revue visuelle reste une inspection échantillonnée. Les mesures audio ne constituent pas une écoute humaine.

## Modifier le film

La copie et les durées sont dans [config.mjs](config.mjs), les ressources de marque dans [brand.mjs](brand.mjs), et la composition dans [src/ads-scene.mjs](src/ads-scene.mjs). Les captures retenues et leurs empreintes sont listées dans [manifest.json](assets/captures/manifest.json). Le montage peut être modifié sans changer le produit FAT Studio.

Les scripts `capture-*.mjs` sont des outils de production de ce film, bornés au port temporaire 8774 et au projet démo. Ils ne sont pas nécessaires pour refaire le rendu depuis les PNG. Leur exécution exige une instance de capture jetable préparée séparément ; ils ne servent pas à commander un automate.

Les sources de ce film et la synthèse musicale suivent la licence MIT du projet, jointe dans [LICENSE](LICENSE). Les logos originaux appartiennent à Vanguard Systems et identifient la marque ; ils ne sont pas une banque de logos à réutiliser. Geist est sous SIL Open Font License 1.1, jointe dans [OFL.txt](assets/OFL.txt). La provenance et les empreintes des ressources sont dans [provenance.json](assets/provenance.json).
