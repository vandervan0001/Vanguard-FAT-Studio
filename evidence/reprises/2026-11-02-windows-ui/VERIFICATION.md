# Délais de l'automatisation Windows — 0.2.1

La [CI 41468421321](https://github.com/vandervan0001/FAT-Studio/actions/runs/41468421321), commit `791d87749f814ffabb10107e2a0b520d17debc8e`, a obtenu : Ubuntu 418 Python / 33 frontend réussis ; Windows 418 Python réussis, 31 frontend réussis et deux échecs de délai. Aucun test ignoré. Les sept échecs d'encodage précédents ont été vérifiés nominativement comme réussis.

Les deux échecs sont des clics sur P101 (`workbench.spec.ts`) et LT101 (`adversarial.spec.ts`). Les fichiers de ces tests sont identiques à la référence 0.1.1. Les nouveaux tests de sélection V20/V21 réussissent sous Windows.

## Mesure et observation

Les captures après échec montrent le nœud attendu sélectionné et son inspecteur ouvert. Les traces ne signalent ni interception du clic ni nœud absent. P101 prend environ 6,86 s au total, dont environ 6,18 s avant l'envoi du clic en retranchant la capture initiale ; LT101 prend environ 6,39 s et ne dispose plus que d'environ 1,74 s au moment de l'envoi. Le budget d'action était de 6 s. Le parcours workbench avait déjà consommé 26,5 s de son plafond de test de 30 s.

Il n'y a pas de profil CPU dans les artefacts Windows. Une comparaison Mac avec renderer logiciel et CPU ralenti n'a pas reproduit le retard ; aucune causalité animation ou traçage n'est donc affirmée.

## Correctif et contrôle

Seule la configuration du banc change : sur Windows CI, délai d'action 12 s et délai de test 60 s. Assertions 6 s, zéro retry, traces et captures conservés ; aucun changement produit. Les deux parcours affectés ont été rejoués localement : deux réussis, 4,8 s. La [CI 41471993176](https://github.com/vandervan0001/FAT-Studio/actions/runs/41471993176), commit `b55bfded63dc5572da8d3409409210381cc50c34`, a ensuite réussi les 33 tests navigateur Windows et le contrôle installé hors ligne. Voir les [preuves finales](../2026-11-02-windows-ci/VERIFICATION.md).

Les logs, traces et captures sources sont conservés dans les artefacts privés de la CI citée. Ils ne constituent pas une qualification TIA/PLCSIM. Le serveur local reste arrêté, données conservées.
