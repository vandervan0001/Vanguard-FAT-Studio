<picture>
  <source media="(prefers-color-scheme: dark)" srcset="frontend/public/brand/logo_vanguard_wordmark_horizontal_white.png">
  <img alt="Vanguard" src="frontend/public/brand/logo_vanguard_wordmark_horizontal.png" width="320">
</picture>

# Vanguard FAT Studio

[Dépôt du projet](https://github.com/vandervan0001/Vanguard-FAT-Studio)

Banc FAT local : P&ID interactif, procédé simulé, scénarios automatiques, essais pas à pas et preuves exportables. Le programme PLC fournit les commandes ; le banc calcule les capteurs et les retours simulés. Une démonstration Python permet de commencer sans Siemens.

## Démarrer sous Windows

Avec la distribution **portable Windows x64**, extraire toute l’archive dans un dossier accessible, puis double-cliquer **Start-FAT.cmd**. Python et les dépendances sont fournis. Aucun droit administrateur, Python ou Node.js global n’est nécessaire. Utiliser [http://127.0.0.1:8765](http://127.0.0.1:8765). Garder la fenêtre ouverte ; `Ctrl+C` arrête le serveur. Les données restent dans votre profil, hors du runtime.

Le lanceur **Vanguard-FAT-Studio.cmd** ouvre le même service. Le module Python reste `fat_studio` ; les commandes `vanguard-fat-studio` et `fat-studio` sont compatibles. Les dossiers de données existants et les formats d’échange gardent leurs identifiants.

Depuis les **sources**, installer Python 3.12 x64 puis lancer le même `Start-FAT.cmd`. Ce lanceur crée `.venv` avec les versions verrouillées ; il utilise les wheels du kit hors ligne si elles sont présentes. Node.js sert uniquement à reconstruire l’interface. Les deux distributions sont décrites dans [INSTALLATION.md](docs/INSTALLATION.md).

## Essayer le banc

1. Dans **Ouvrir**, charger la **démo laboratoire** : trois cuves, quatre pompes et huit vannes.
2. Choisir un scénario, puis **Préparer la vue** et **Démarrer**.
3. Observer les mesures, les qualités et les tendances. Le pupitre agit sur les entrées simulées autorisées.
4. Pour une FAT pas à pas, déclencher chaque STEP puis saisir l’observation du testeur. La conclusion FAT humaine reste à renseigner séparément.
5. Exporter les données CSV, le rapport HTML ou les preuves JSON.

La démo PLC est volontairement passive : elle recopie les demandes manuelles vers ses commandes et calcule des conversions simples. Elle ne contient ni séquence de production ni standard de programmation utilisateur. Lire [DEMO_PLC.md](docs/DEMO_PLC.md) pour son contrat et sa génération. Le [guide utilisateur](docs/USER_GUIDE.md) détaille les gestes.

| Besoin | Document |
| --- | --- |
| Installer ou choisir le dossier de données | [INSTALLATION](docs/INSTALLATION.md) |
| Dessiner, mapper, forcer, créer une FAT, exporter | [USER_GUIDE](docs/USER_GUIDE.md) |
| Piloter avec votre propre assistant | [AI_QUICKSTART](docs/AI_QUICKSTART.md) et [AI_CONTROL](docs/AI_CONTROL.md) |
| Échanger projets et scénarios JSON versionnés | [FORMAT](docs/FORMAT.md) |
| Sauvegarder et restaurer un projet complet | [PROJECT_ARCHIVES](docs/PROJECT_ARCHIVES.md) |
| Comprendre les bilans et les limites physiques | [MODEL](docs/MODEL.md) |
| Préparer une cible virtuelle autorisée | [PLCSIM_SETUP](docs/PLCSIM_SETUP.md) |
| Développer ou reprendre les sources | [README-CODEX](README-CODEX.md) et [AGENTS](AGENTS.md) |

Vanguard FAT Studio n’embarque aucun modèle IA et ne demande aucune clé API de modèle. Votre client Codex, Claude ou autre assistant lit les fichiers et utilise le CLI/API local avec un contexte projet/révision/essai explicite.

## Périmètre

Les sorties PLC sont lues ; les écritures du banc visent uniquement les entrées simulées déclarées et autorisées. Importer un projet n’autorise jamais une cible sur le poste. Les adresses PLC sont documentaires et les NodeIds OPC UA doivent être réellement découverts. Une erreur de communication ou de stockage arrête les échanges sans reconnexion automatique. La pause du banc ne commande pas le STOP d’une CPU externe.

Le P&ID utilise des paramètres de volume, débit et groupes de transfert ; il ne constitue pas un solveur hydraulique général. Les contrôles automatiques et simulations de test ne valent ni réception FAT humaine, ni qualification V20, CPU physique ou sécurité fonctionnelle.

La livraison publique contient le banc, ses formats et sa démo. Les programmes utilisateurs, bibliothèques de programmation, secrets, politiques de cible, données personnelles et notes de travail restent hors de cette livraison. [PUBLIC_CHANGELOG.md](PUBLIC_CHANGELOG.md) présente les changements publics. Les licences sont dans [LICENSE](LICENSE) et [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
