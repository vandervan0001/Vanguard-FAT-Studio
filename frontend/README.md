# Interface de FAT Studio

Application locale en français, construite avec React, TypeScript et Vite. Le navigateur utilise exclusivement l’API HTTP du service FAT Studio ; il n’ouvre aucune communication directe avec le PLC. Tous les scripts, styles, symboles SVG et polices système fonctionnent hors ligne après installation.

## Construire

Depuis ce répertoire, avec Node.js 22 ou supérieur :

```sh
npm ci
npm run build
```

`dist/` contient les fichiers statiques servis par le backend. Le script d’installation du dépôt réalise ces étapes. Le fichier `package-lock.json` fige l’intégralité de l’arbre npm. Aucun service cloud ni clé API n’est requis.

Pour développer, démarrer le backend sur `127.0.0.1:8765` avec `FAT_STUDIO_DEV_ORIGIN=http://127.0.0.1:5173`, puis `npm run dev`. Le proxy Vite `/api` utilise cette autorisation d’origine de développement explicite. La distribution utilise toujours la même origine que le backend.

## Fonctions disponibles

- **P&ID** : bibliothèque de sept symboles, glisser-déposer ou clic pour ajouter, déplacements, connexions, libellés, zoom, panoramique, grille, suppression et propriétés des équipements.
- **Associations PLC** : sélection de variables compatibles par port, création des tags manquants, édition des types, bornes, valeurs initiales, directions, autorisations d’écriture et NodeId OPC UA ; import/export CSV.
- **Scénarios** : création, choix, description, durée, séquence JSON éditable et contrôlée, aperçu de la chronologie et résultats d’assertions. Un brouillon JSON non appliqué bloque sauvegarde et démarrage ; ses étapes restent téléchargeables, y compris pendant un conflit de projet.
- **Exécution** : lancement, pause, reprise, arrêt et réinitialisation ; commandes bloquées si le service est indisponible. L’édition du modèle est verrouillée pendant l’essai et sa pause.
- **Essais** : forçage de mesures simulées, libération, injection/levée des défauts proposés pour chaque équipement ; distinction visuelle des valeurs forcées et défauts.
- **Traces** : tendances en unités natives, journal, marqueurs, conclusion de l’ingénieur, rapports HTML, exports CSV/JSON et récupération des essais archivés. Les conclusions enregistrées sont relues depuis le service. Les brouillons de conclusion et de marqueur restent dans l’onglet lors des changements de section ; un changement d’essai bloque leur envoi et permet de les télécharger. Une fermeture ou un rechargement avertit si une saisie reste non enregistrée.
- **Connexion** : mode démonstration ou OPC UA, identité de cible, certificats, noms de variables d’environnement pour les secrets, confirmation saisie avant connexion réelle. La politique d’autorisation du poste reste gérée hors du projet.
- **Plusieurs onglets** : si un autre onglet change de projet actif ou en enregistre une nouvelle révision, les commandes sont bloquées. Le brouillon local reste téléchargeable avant rechargement. Le serveur vérifie aussi l’identifiant et la révision attendue sur les commandes d’essai et les sauvegardes, et l’identifiant de l’essai pour les interventions. Les exports de preuves ciblent l’essai affiché ; l’export du mapping vérifie le contexte du projet.

Enregistrer ou valider un projet inchangé conserve l’essai courant. Les réponses de polling antérieures à une intervention confirmée sont ignorées. Une requête d’acquisition sans réponse est interrompue après cinq secondes et le service est signalé indisponible ; la reprise du polling conserve le brouillon.

Les lignes du P&ID sont graphiques. Les groupes de débit définissent les circuits physiques simplifiés : cuve cible, sens, circuit en série et capacité. Cette distinction est rappelée dans l’interface.

## Réutilisation

Le canevas utilise **React Flow** : déplacement, sélection, connexions, grille, mini-carte et navigation sont fournis par la bibliothèque. Les symboles de procédé et le panneau FAT sont spécifiques à ce projet. Les courbes utilisent **Recharts** et les icônes **Lucide**.

Versions résolues lors de la construction initiale : React/React DOM 19.3.1 ; React Flow 12.12.1 ; Recharts 3.10.1 ; Lucide React 0.468.0 ; Vite 6.4.5 ; TypeScript 5.9.3. La référence d’installation est le verrou npm, pas cette liste documentaire.

Sources primaires consultées pour l’implémentation :

- [React Flow : TypeScript et types de nœuds](https://reactflow.dev/learn/advanced-use/typescript)
- [React Flow : nœuds personnalisés](https://reactflow.dev/learn/customization/custom-nodes)
- [React Flow : propriétés des nœuds](https://reactflow.dev/api-reference/types/node-props)
- [Recharts : dimensionnement responsive](https://recharts.github.io/en-US/guide/sizes/)
- [Recharts : LineChart](https://recharts.github.io/en-US/api/LineChart/)
- [React : documentation officielle](https://react.dev/reference/react)

## Vérification

`npm run build` effectue la vérification TypeScript stricte et produit la distribution.

La suite Playwright utilise un navigateur neuf, le backend réel et le vrai moteur de procédé, avec un répertoire de données temporaire sur le port local `8766`. Elle ne touche pas aux projets du technicien. Elle couvre édition/sauvegarde/rechargement, création complète depuis un canevas vide, boucle fermée, défaut moteur, forçage, pause/reprise, exports CSV/HTML, import/export du mapping, scénario JSON malformé, import invalide et conflit entre onglets. Les parcours adverses retardent volontairement des réponses pour vérifier les courses de polling, la conservation des saisies et le rattachement des rapports au bon essai. Ils contrôlent aussi les requêtes bloquées, le forçage vide, les associations incompatibles, les états des symboles et l’accès aux actions à 768 px. Des tests ciblés vérifient le format des étapes et les erreurs de session/API, notamment le contexte conservé après renouvellement du jeton.

Depuis la racine du dépôt, après installation Python :

```sh
cd frontend
npm ci
npx playwright install chromium
npm run build
cd ..
python scripts/build-web.py
cd frontend
npm test
```

En CI Linux, utiliser `npx playwright install --with-deps chromium`. Le runner est figé à `@playwright/test` 1.56.1. `npm run test:e2e` exécute uniquement les parcours navigateur. Le rapport machine est écrit dans `frontend/test-results/results.json` ; traces et captures d’échec restent dans ce répertoire ignoré par Git.

`FAT_E2E_PYTHON` peut désigner un interpréteur Python explicite. `FAT_E2E_BASE_URL` permet de viser un serveur de test existant **uniquement sur loopback** ; ce serveur doit être dédié aux tests, car la suite y remplace le projet actif. Sans cette variable, l’isolation temporaire est automatique.

Les essais sur Siemens nécessitent le poste Windows et les versions de TIA/PLCSIM ciblées ; les tests du mode démonstration ne prouvent pas cette compatibilité.
