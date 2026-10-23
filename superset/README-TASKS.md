# Lot 3 — Complétude des tâches ASC

Tableau : https://dashboard.disc-mali.ml/superset/dashboard/asc-completude-taches/.
Audience du tableau ASC historique, avec restrictions territoriales et refus par défaut.
Le tableau historique, les lots 1/2 et OpenFn sont conservés.

## Ce que mesure le tableau

Une tâche est un document CHT, pas un patient distinct ni une visite nécessairement
réalisée. Le périmètre est celui des comptes ASC courants du lot 2 : rôle `chw`,
hors formation, suppression/désactivation explicite, rattachés à un site du relevé.
Les tâches d'anciens comptes ou d'autres rôles restent dans le contrôle de périmètre.
Les affectations sont actuelles ; les mouvements historiques ne sont pas reconstruits.

Le mois est celui de **l'échéance**, pas celui de la saisie ou de la réalisation.
La période par défaut est le dernier mois civil complet. Utiliser des mois entiers :
la granularité physique est mensuelle. Historique : douze mois complets, mois courant
et échéances suivantes disponibles. Aucun objectif clinique théorique n'est reconstruit.
L'absence de tâche ne signifie donc pas qu'aucun soin n'était attendu.

Au calcul, une tâche échue a une échéance **strictement antérieure** à la date de
référence et un état Completed, Failed, Ready ou Draft. Une échéance du jour peut
encore être réalisée aujourd'hui et reste hors des échues. Le taux est :

`SUM(échues Completed) / NULLIF(SUM(échues Completed + Failed + Ready + Draft), 0)`.

Les annulations sont visibles mais exclues. Les dates de création futures,
identifiants manquants, états inconnus et fenêtres absentes/incohérentes sont exclus
et restent dans la qualité. Un taux sans dénominateur est NULL, pas zéro.
Les consolidations territoriales utilisent les sommes, jamais une moyenne de taux.
Le taux comparatif des clôturées `Completed/(Completed+Failed)` ne mesure pas la
même chose puisqu'il ignore les tâches encore ouvertes.

Pour les échues non terminées, trois catégories se complètent :

- Ready avec fin de fenêtre non passée : ouverte dans sa fenêtre.
- Ready ou Draft avec fin de fenêtre passée : état à actualiser/vérifier.
- Draft avec fin de fenêtre non passée : programmée échue à vérifier.

Les états ne sont jamais réécrits. Un état Failed ne devient pas une action à refaire.
La vue analytique utilisée ne contient pas la date de réalisation. Le tableau ne
revendique aucun taux « réalisé dans les délais ». Le fonctionnement des états est
documenté par le [schéma CHT](https://docs.communityhealthtoolkit.org/technical-overview/data/db-schema/#tasks)
et le [guide d'analyse des tâches](https://docs.communityhealthtoolkit.org/building/tasks/managing-tasks/query-task-data/).

## Sources et calcul

- `useview_task` existante : environ 31,6 millions de documents à l'audit.
- `mv_asc_tasks_rollup` dédiée : agrégats compte × type × mois × qualité.
  Aucun nom ou identifiant de patient n'est copié dans cet agrégat.
- Les jeux Superset joignent **virtuellement** le répertoire `mv_asc_ops_accounts`.
  Ne pas matérialiser de dépendance sur cette dernière : son remplacement atomique
  par le lot 2 doit pouvoir continuer à supprimer son ancien agrégat.
- `task_catalog.json` : libellés français extraits des traductions du dépôt
  `config-moh-mali-chw`, et regroupements thématiques explicites. Types inconnus
  conservés, jamais supprimés silencieusement.

`refresh_tasks.py` construit une vue `_next`, valide ses index, puis remplace
l'ancien agrégat par renommage transactionnel. Seul l'ancien agrégat de ce lot
est supprimé ; aucune tâche ou vue amont n'est supprimée ou actualisée.
Le SQL et le catalogue versionnés sont relus à chaque calcul.
Le verrou transactionnel évite deux calculs simultanés ; le remplacement attend
au maximum dix secondes. Un échec laisse le dernier relevé disponible.

Le minuteur est prévu toutes les six heures, à 00/06/12/18 h 45 UTC, avec léger
étalement. Cette cadence évite une lecture de 23 Go toutes les heures. Les dates
visibles sont celles du calcul et du répertoire, **pas celles de la dernière
réplication DISC ou de la dernière actualisation de `useview_task`**.
Le statut ouvert/fermé DHIS2 n'est pas relié à ce périmètre.

## Exports et droits

Les tableaux de consultation utilisent une pagination serveur de vingt lignes.
Le tableau **EXPORT TÂCHES** utilise une pagination d'affichage et une limite de
100 000 groupes, contrôlée avant publication. Il conserve toute la sélection.
Une ligne regroupe un compte, un site et un type, avec les compteurs additionnés
sur les mois choisis. Les mois min/max décrivent les données représentées,
pas nécessairement toutes les bornes demandées par le filtre.

CSV et Excel contiennent Région, District, CSCOM, zone, site, compte, nom/téléphone
ASC, type, compteurs, première échéance ouverte, retard maximal et dates du relevé.
Les lignes visent les comptes avec au moins une tâche échue encore ouverte.
Aucun nom de patient n'est exposé. Ne jamais committer ces exports individuels.

`regional_security.py` reprend les règles existantes du jeu historique 7.
Les lignes de qualité hors périmètre ont une région NULL : un lecteur régional
ne peut pas les obtenir. Les profils sans périmètre sont refusés par défaut.
Les filtres d'interface ne remplacent pas les règles de sécurité.

## Audit longitudinal du 22 octobre 2026

Sur septembre, périmètre des comptes courants : 1 356 325 tâches échues,
105 000 Completed, 1 085 267 Failed et 166 058 encore ouvertes ; 23 093 annulations.
La complétude enregistrée est 7,74 %, celle des clôturées 8,82 %.
Les tâches longitudinales pèsent environ 95,4 % des échues : ces taux ne doivent
pas être assimilés sans contrôle à une performance clinique individuelle.

Dans la source de septembre, les types longitudinaux 2–5 ans et 6–12 ans ont
respectivement 495 188 et 809 664 documents, pour 189 348 et 313 945 couples
compte/bénéficiaire. La médiane est de trois dates d'échéance distinctes par couple
sur le mois ; certains couples en ont jusqu'à neuf. Aucun identifiant individuel
n'est conservé dans ces résultats d'audit.

Le code local `config-moh-mali-chw/tasks.extras.js`, dans
`childLongitudinalTemplate`, borne une date semestrielle par la fin d'un intervalle
qui correspond au moment du calcul. Cette logique constitue une piste à vérifier
avec la version réellement déployée et la fréquence métier attendue.
Le présent lot ne change pas les règles CHT et ne déduplique pas arbitrairement
les documents. Un avertissement et le poids longitudinal restent visibles.

## Correction longitudinale du 23 octobre 2026

Le diagnostic a été confirmé dans les règles réellement déployées. Le calendrier
ASC/OCA a été confirmé par l'utilisateur et la correction ciblée a été déployée
à 09:13 UTC, avec sauvegarde. Les échéances restent désormais ancrées aux jalons
prévus ; le contrôle des décès et l'isolement des dates ont aussi été corrigés.
Les 13 tests ciblés passent sur la source corrigée et le bundle de production.
L'historique et les calculs de ce tableau sont conservés. L'effet dépend de la
réception des règles sur les appareils et de leurs prochains recalculs.
Voir [le diagnostic, les limites des tests et le retour arrière](cht/README.md).

## Déploiement et vérification

Livrer le dossier `superset` de l'archive du commit validé dans
`/opt/moh_superset/superset_config/asc-v2/`, puis noter le SHA dans `RELEASE`.
Le dossier distant n'est pas un dépôt Git : le déploiement se fait par archive,
pas par `git pull`. Aucun identifiant n'est versionné.

```sh
docker exec superset_app python /app/superset_config/asc-v2/refresh_tasks.py --create
docker exec superset_app python /app/superset_config/asc-v2/validate_tasks.py --source
docker exec superset_app python /app/superset_config/asc-v2/provision_tasks.py
docker exec superset_app python /app/superset_config/asc-v2/verify_tasks_access.py
# Après vérification visuelle du brouillon :
docker exec superset_app python /app/superset_config/asc-v2/provision_tasks.py --publish
docker exec superset_app python /app/superset_config/asc-v2/verify_tasks_access.py --regional-only
sudo install -m 644 superset/systemd/asc-tasks-refresh.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now asc-tasks-refresh.timer
sudo systemctl start asc-tasks-refresh.service
```

`--create` refuse d'écraser une source existante ; sans cet argument, le calcul
remplace l'agrégat de façon atomique. `validate_tasks.py` vérifie partitions,
consolidations et douze cas limites ; `--source` compare les volumes directement
à `useview_task`. `verify_tasks_access.py` teste les requêtes régionales,
le refus par défaut, CSV/XLSX, la somme des compteurs exportés, le filtre Nutrition
et une tentative de requête sur une région non autorisée. Chaque client de test
isole son contexte et vérifie son identité par l'API avant tout export.

Sauvegarde privée des métadonnées :
`/opt/moh_superset/backups/avant-asc-tasks-20261022.sql.gz`.
Journaux : `journalctl -u asc-tasks-refresh.service`.
Pour retirer seulement ce lot, désactiver son minuteur et remettre son tableau
en brouillon ; ne pas restaurer globalement la base des métadonnées.
