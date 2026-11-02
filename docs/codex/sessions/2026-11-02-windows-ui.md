# Délais du banc navigateur Windows

Le 2 novembre 2026, la CI du commit `791d87749f814ffabb10107e2a0b520d17debc8e` a réussi les 418 tests Python Windows, dont les sept cas d'encodage corrigés. Ubuntu a réussi 418 tests Python et 33 frontend. Windows a réussi 31 tests frontend et échoué deux parcours historiques, déjà présents sans modification en 0.1.1. Les deux nouveaux tests V20/V21 passaient.

Les captures montrent les inspecteurs P101 et LT101 correctement ouverts. Les traces montrent des latences réparties dans la résolution, l'actionability et le scroll, puis un clic dépassant le budget d'action de 6 s. Pour P101, environ 6,18 s du budget sont consommées avant l'envoi ; pour LT101, il reste environ 1,74 s au moment de l'envoi. Le parcours complet workbench avait déjà consommé 26,5 s sur son plafond de 30 s avant de poursuivre les défauts, forçages et exports.

Une comparaison locale sur renderer logiciel Mac avec CPU ralenti n'a pas reproduit cette latence Windows. La cause de performance n'est donc pas attribuée aux animations ou au screencast. Le correctif se limite au banc : `frontend/playwright.config.ts` accorde 12 s par action et 60 s par test uniquement sur Windows CI. Les assertions gardent 6 s ; traces, captures, zéro retry et code produit restent inchangés. Les deux parcours affectés passent localement en 4,8 s. La validation Windows exige le prochain run réel.

Branche : `codex/windows-ui`, base `791d877`, copie avant édition dans `../work/2026-11-02-windows-ui/scratchpad/source-before`. [Rapport](../../../evidence/reprises/2026-11-02-windows-ui/VERIFICATION.md). Aucun serveur FAT persistant laissé actif. La compilation et l'acceptation Siemens du candidat V20 restent ouvertes, même si la CI du runtime Windows réussit.
