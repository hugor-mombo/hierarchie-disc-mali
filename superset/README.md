# ASC — Pilotage national · V2

Tableau séparé : `https://dashboard.disc-mali.ml/superset/dashboard/asc-pilotage-v2/`.
Le tableau ASC historique (id 1) et SD ne sont pas modifiés. Cette livraison
concerne le pilotage du **rapportage**, pas encore la refonte des indicateurs cliniques.

## Sources et définitions

- Connexion analytique Superset existante, id 1 ; aucun secret dans ces fichiers.
- Cohorte : `mv_chw_site_hierarchy_reporting`, un site UUID par ligne,
  hors formations selon les règles amont ; Bamako inclus. Création du site
  antérieure à la fin du mois. Les branches incomplètes restent comptées.
- Rapports : `form_metadata`, dates déclarées, sur 13 mois complets et mois en cours.
  Le parent enregistré dans le rapport, ou le contact dans l'ancien format,
  doit désigner un site de la cohorte. Les contradictions et dates futures
  restent dans les contrôles de qualité mais sont exclues des indicateurs.
- Un site rapporteur a au moins un rapport dans la sélection. Sur plusieurs mois,
  les sites restent distincts ; les rapports s'additionnent. Sans rapport =
  périmètre moins rapporteurs. Le taux est un rapport de nombres de sites,
  jamais une moyenne des taux des territoires.
- La période par défaut `previous calendar month` est vérifiée avec le parseur
  de Superset 5. `Last month` représente un mois glissant et ne convient pas.
- Les filtres Région → District → CSCOM s'appliquent à tous les graphiques
  territoriaux. La tendance garde 12 mois complets. La qualité reste nationale,
  avec le filtre de période uniquement. Les libellés de CSCOM distinguent les homonymes.

Le relevé et la géographie sont actuels : les mutations historiques ne sont
pas reconstituées. La cohorte peut inclure des sites fermés. Elle ne fournit
pas un effectif de sites fonctionnels DHIS2. Les dates de rapports ne prouvent
pas une synchronisation technique. Aucun nom de patient, téléphone ou détail
clinique individuel n'est exposé par les nouvelles sources.

## Installation et mises à jour

Exécuter les scripts Python **dans l'environnement du conteneur Superset**,
pas dans l'application de hiérarchie. Les UUID fixes rendent le provisionnement
idempotent. La même audience que le tableau ASC est conservée.

Sur le serveur, après récupération du commit Git validé :

```sh
install -d /opt/moh_superset/superset_config/asc-v2
cp -r superset/. /opt/moh_superset/superset_config/asc-v2/
docker exec superset_app python /app/superset_config/asc-v2/refresh_source.py --create
docker exec superset_app python /app/superset_config/asc-v2/validate.py
docker exec superset_app python /app/superset_config/asc-v2/provision.py
```

Vérifier le brouillon dans le navigateur, puis publier :

```sh
docker exec superset_app python /app/superset_config/asc-v2/provision.py --publish
sudo install -m 644 superset/systemd/asc-v2-refresh.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now asc-v2-refresh.timer
sudo systemctl start asc-v2-refresh.service
systemctl show asc-v2-refresh.service -p Result -p ExecMainStatus
```

Le montage de configuration existant conserve les scripts après recréation du
conteneur. Le timer actualise seulement `mv_asc_v2_report_monthly`, de manière
concurrente, avec verrou transactionnel et délai maximal de 180 secondes.
`--create` initialise la vue si elle n'existe pas ; il ne remplace pas sa définition.
Une évolution du SQL matérialisé nécessite une migration explicite et validée.

Le calcul V2 est horaire, **pas la réplication DISC amont**. L'horodatage visible
date ce calcul. La fraîcheur de `form_metadata` et du relevé de sites reste à
instrumenter avant d'affirmer une fraîcheur de bout en bout.

## Vérifications et exploitation

`validate.py` contrôle en lecture seule : grain site/mois unique, périmètre
complet, absence de dates futures dans les indicateurs, partition rapporteurs /
sans rapport, sommes territoriales, homonymes, volumes bruts et attribution,
décompte distinct sur plusieurs mois et bornes du mois civil.

Après un changement, vérifier aussi dans le navigateur : cartes, tendance,
filtres en cascade, pagination, onglet qualité et accès d'un lecteur autorisé.
La publication d'un dashboard ne le rend pas public : l'authentification et
les rôles existants restent appliqués.

Journaux : `journalctl -u asc-v2-refresh.service`.
État : `systemctl list-timers asc-v2-refresh.timer`.
Un échec laisse disponible le dernier calcul réussi ; son horodatage reste visible.

Sauvegarde initiale privée sur le serveur :
`/opt/moh_superset/backups/avant-asc-v2-20261022.sql.gz` et archive de configuration
associée. Ne pas déposer les sauvegardes, exports contenant des accès, ou `.env`
dans Git.

Pour retirer cette V2 sans toucher à l'existant : désactiver son timer et remettre
son dashboard en brouillon (`provision.py` sans `--publish`). La source dédiée
peut rester en place pour faciliter un retour arrière. Ne pas restaurer toute
la base de métadonnées pour une simple modification de V2.

Documentation : [filtres et tableaux Superset](https://superset.apache.org/docs/using-superset/creating-your-first-dashboard/).
