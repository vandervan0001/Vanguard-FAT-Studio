# Provenance des représentations P&ID

Les 41 familles historiques sont des dessins schématiques originaux de Vanguard FAT Studio. Le vocabulaire reprend les catégories attribuées à Scott Duncan lorsque celles-ci s'appliquent. Elles restent disponibles avec leurs identifiants et leurs piquages antérieurs.

## Géométries libres adaptées

Quatre représentations générales supplémentaires sont adaptées du code de dessin de [pyflowsheet](https://github.com/nukleon84/pyflowsheet), de Jochen Steimel, sous licence MIT. Le logiciel amont décrit son objectif comme le dessin de PFD simples ; cette réutilisation ne certifie aucun symbole ISO ou ISA. Aucun module pyflowsheet, routeur ou modèle de procédé n'est exécuté par Vanguard.

Révision figée : `8a68f2569a9a977079ece242aa7771b9d53448a8`, consultée le 11 novembre 2026. Les fichiers source à cette révision sont identifiés ci-dessous par leur SHA-256.

| Identifiant ajouté | Fichier source pyflowsheet | SHA-256 |
| --- | --- | --- |
| `pump_general` | `pyflowsheet/unitoperations/pump.py` | `f52463af9deb811763862e124679ac9471660d2e6bbb15d57f512e37123ff61b` |
| `valve_general` | `pyflowsheet/unitoperations/valve.py` | `fe72d12a9262fb51ce6607ff3f0b30d0a876b181e528dfa5c35564d8c27ba174` |
| `heat_exchanger_general` | `pyflowsheet/unitoperations/heatexchanger.py` | `f30d45e228116a499b0bdae4fd97aa38a8d646994ba7e39ab0967df9f2dd884f` |
| `compressor_general` | `pyflowsheet/unitoperations/compressor.py` | `9ad71daca0590aeca48f93f29423fcdbda51a358c5e3ae5d04b39323a6cec245` |

Adaptations : corps normalisé dans le carré `(25,25)..(75,75)` du canevas 100 × 100, raccords ajoutés jusqu'au bord, couleurs locales et noms français. Les formules du cercle, des diagonales de pompe, du polygone de vanne, du serpentin d'échangeur et des segments angulaires du compresseur proviennent de ces fichiers. Les raccords de l'échangeur général restent radiaux, comme dans la source : primaire gauche/droite, secondaire haut/bas. L'échangeur historique à quatre raccords latéraux n'est pas remplacé.

La [licence MIT complète](pid_symbols_pyflowsheet_LICENSE.txt) conserve le copyright `(c) 2020 Jochen Steimel`. Empreinte du fichier LICENSE amont : `7531c6bcc185c118554ead3d46f8a487387b2ef9c5e80a98edee554515651d59`. Le champ `source` de chaque représentation expose le lien immuable, la licence, la révision, l'empreinte et les adaptations.

## Instrumentation et références

Seize fonctions documentaires ajoutent les codes usuels FT/PT/LT/TT, FI/PI/LI/TI, FIC/PIC/LIC/TIC, LAH/LAL et PSH/PSL. La lettre de fonction est affichée dans une bulle simple avec une prise documentaire. Le préfixe décrit la fonction ; il ne détermine ni implantation réelle, ni numérotation de boucle, ni variable PLC. Les identifiants et repères importés sont conservés.

L'[aperçu pédagogique publié par ISA](https://www.isa.org/getmedia/e122051e-8c8c-48be-97ef-5d344c585771/Chapter7_Control) explique les lettres fonctionnelles et l'exemple FIC. La référence actuelle des fonctions et de leur identification est [ANSI/ISA-5.1-2024](https://www.isa.org/standards-and-publications/isa-standards/find-isa-standards-by-topic). Aucune table de la norme ni planche payante n'est incorporée.

Les références pertinentes pour choisir les conventions d'un projet sont :

- [ISO 10628-1:2014](https://www.iso.org/standard/51840.html), classification, contenu et représentation des schémas de procédé chimique et pétrochimique, édition confirmée en 2026.
- [ISO 10628-2:2012](https://www.iso.org/standard/51841.html), symboles des schémas de procédé chimique et pétrochimique, édition confirmée en 2024.
- [ISO 14617-1:2025](https://www.iso.org/standard/85641.html), règles générales de présentation des symboles, et [ISO 14617-2:2025](https://www.iso.org/standard/83364.html), bibliothèque de symboles industriels. Les anciennes parties 3 à 15 sont retirées au profit de la partie 2 de 2025.
- [EN 1861:1998](https://www.dinmedia.de/en/standard/din-en-1861/4533906), présentation et symboles des schémas frigorifiques et de pompes à chaleur, indiquée actuelle par DIN Media au contrôle.
- [ISO 20560-1:2024](https://www.iso.org/standard/86049.html), information de sécurité pour les tuyauteries physiques hors-sol. Son domaine ne constitue pas une palette universelle chaud/froid pour tous les P&ID.

Les liens et domaines ont été contrôlés le 11 novembre 2026 dans les catalogues des organismes émetteurs. Les notices publiques ont été consultées, sans achat ni incorporation des textes normatifs complets. Le catalogue fourni est une aide au dessin et au choix des conventions ; il ne constitue pas une certification de conformité, un dossier de sécurité ou une validation FAT humaine.
