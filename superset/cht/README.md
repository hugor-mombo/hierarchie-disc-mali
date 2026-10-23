# Correction de la génération des suivis longitudinaux — 23 octobre 2026

Déployée sur DISC-Mali le **23 octobre 2026 à 09:13:31 UTC**.
La configuration relue après écriture confirme que **seule `tasks.rules` a changé**.
Le déploiement ne remplace pas les paramètres locaux par ceux de la branche vaccination.

## Diagnostic et calendrier confirmé

L'audit de Superset a repéré plusieurs échéances par mois pour un même compte,
bénéficiaire et type longitudinal. La fonction réellement déployée bornait la date
semestrielle par la fin de l'intervalle courant, donc par la date du recalcul.
Le contrôle de vie utilisait aussi `!isAlive` au lieu d'appeler la fonction.
Les dates stockées dans un `this` lexical pouvaient rester renseignées entre évaluations.

Calendrier confirmé par l'utilisateur le 23 octobre :

- ASC : 1, 3, 6, 9, 12, 18 et 24 mois, puis anniversaire semestriel de naissance.
- OCA : suivi mensuel existant ; après deux ans, rapport précédent + un mois,
  ou anniversaire mensuel de naissance en l'absence de rapport.
- Fenêtre : deux jours avant et deux jours après l'échéance.

Les limites d'âge existantes, dont les intervalles sans formulaire entre 5,5 et
6 ans et entre 12,5 et 13 ans, sont conservées. Le filtre OCA au-delà de 60 mois
est conservé. Les suivis sont réservés aux rôles ASC (`chw`) et OCA.
La fermeture explicite du suivi et les restrictions de mariage/grossesse des
adolescents sont conservées. Le rattrapage initial garde sa date d'inscription
pendant les deux jours suivant celle-ci. Une inscription future ne déclenche pas
ce rattrapage. Les décès et dates de naissance invalides/futures sont exclus.

La nouvelle date semestrielle est l'anniversaire encore dans sa fenêtre, sinon
le prochain anniversaire. Elle ne dépend pas de la date du recalcul et reste
ancrée directement à la naissance, y compris aux fins de mois et années bissextiles.
Une date future produit une tâche programmée, qui devient disponible dans sa fenêtre.

## Sources et validation

- Source CHT : `config-moh-mali-chw`, branche `codex/fix-longitudinal-scheduling`,
  commit local `eb6a0d6`, basé sur `67a690e`.
- La branche initiale `feat/vaccination` et ses fichiers de travail sont conservés.
- `config-moh-mali-chw.patch` contient la correction source et ses tests,
  applicable au commit de base avec `git apply --check`, puis `git apply`.
- `longitudinal-factory.js` est la fonction destinée au bundle de production.
  Sa seule adaptation par rapport à la source corrigée est `user.role`, déjà utilisé
  dans le bundle existant, à la place du nouveau helper local `getUserRole()`.
- Tests : 13 cas, dont trois scénarios dans le moteur CHT, sans navigateur ni données
  réelles. Source corrigée, candidat de production et configuration relue après
  déploiement sont testés. Le bundle antérieur échoue à 11 de ces 13 cas.
- Les scénarios couvrent : échéance stable, sept jalons ASC et leurs fenêtres,
  mensualité OCA avec/sans rapport, décès, clôture, mariage/grossesse, isolement
  des dates, inscription, dates invalides/futures, année bissextile, limites d'âge,
  tâche Draft/Ready et visite terminée qui ne se rouvre pas après modification.
- Compilation CHT et ESLint des fichiers modifiés réussis. Le compilateur webpack 4
  installé nécessite `NODE_OPTIONS=--openssl-legacy-provider` avec Node 22,
  uniquement pendant la compilation locale.
- Limite : le harnais installé embarque le moteur CHT **4.0** ; le serveur est en
  **4.21.0**. Les règles exactes déployées ont été chargées dans ce harnais, mais
  cela ne constitue pas une simulation complète d'un téléphone ASC sous 4.21.
  Aucun formulaire clinique ni rapport de test n'a été envoyé en production.

Dans le worktree CHT, après compilation :

```sh
node node_modules/mocha/bin/mocha test/tasks/child_longitudinal_schedule.spec.js --timeout 35000
# Facultatif : même suite contre un app_settings privé relu depuis le serveur.
TASK_SETTINGS=/chemin/prive/settings.json node node_modules/mocha/bin/mocha test/tasks/child_longitudinal_schedule.spec.js --timeout 35000
```

## Déploiement ciblé et retour arrière

`deploy-rules.mjs` vérifie l'empreinte du bundle existant, remplace uniquement la
fonction balisée, sauvegarde les paramètres, puis utilise la fusion récursive
`PUT /api/v1/settings` sans `replace` ni `overwrite`. Il relit ensuite les paramètres
et vérifie que toutes les autres propriétés sont inchangées. Les identifiants
viennent de l'environnement privé existant, jamais des fichiers versionnés.
Une vérification immédiatement avant écriture réduit le risque de concurrence,
sans constituer un verrou contre un autre déploiement simultané.

Empreintes SHA-256 de `tasks.rules` :

- Avant : `1810b36601f799b70fe3d7f872fa3a348527405c87b762f3f2c0a822cbf0fcc1`
- Après : `2e24bb1538c1382771c10f5beaa95f462e5c8507442471b4feace6d701768e82`

Sauvegarde privée distante :
`/opt/moh_superset/backups/cht-longitudinal-20261023/`.
Contenu : paramètres initiaux, règles avant/après, manifeste de vérification.
Ne pas ajouter ces fichiers privés à Git et ne pas les publier dans Superset.
Le dossier `superset/cht` versionné est également livré dans le dossier de
configuration ASC du serveur, sans y inclure les sauvegardes privées.

Vérification à blanc depuis le dépôt de maintenance :

```sh
node superset/cht/deploy-rules.mjs --replacement superset/cht/longitudinal-factory.js --expect-sha256 EMPREINTE_AVANT
```

Une écriture requiert aussi `--apply --backup-dir /nouveau/dossier/prive`.
Pour revenir à la version sauvegardée, utiliser `--rules /chemin/prive/rules-before.js`
à la place de `--replacement`, avec `--expect-sha256 EMPREINTE_APRES` et un **nouveau**
dossier de sauvegarde. Si les règles ont depuis changé, le script refuse d'écrire :
réexaminer les modifications avant tout retour arrière.

## Lecture des prochains résultats Superset

Le correctif s'applique quand les appareils reçoivent la configuration et recalculent
leurs tâches. Il n'efface ni ne fusionne les documents historiques, ne transforme
pas les échecs en réussites et ne change pas le dénominateur du tableau de bord.
La complétude des mois précédents conserve donc ses limites d'interprétation.
La source analytique et le rafraîchissement du tableau ajoutent leur propre délai.

Au prochain contrôle, comparer des périodes comparables après le 23 octobre,
le nombre de dates d'échéance par compte/bénéficiaire/type et le poids longitudinal,
en tenant compte des appareils n'ayant pas encore reçu les règles. Une baisse du
volume seule ne prouve pas une hausse des visites réalisées. Tout retraitement
historique éventuel doit rester une analyse séparée, documentée et validée.

API vérifiée dans le [contrôleur CHT 4.21.0](https://github.com/medic/cht-core/blob/4.21.0/api/src/controllers/settings.js)
et le [service de paramètres](https://github.com/medic/cht-core/blob/4.21.0/api/src/services/settings.js).
