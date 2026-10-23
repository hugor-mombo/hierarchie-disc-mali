# Géolocalisation et comparaisons opérationnelles DISC

- [Géolocalisation des sites](https://dashboard.disc-mali.ml/superset/dashboard/sites-geolocalisation/)
- [Top 10 et appui SD](https://dashboard.disc-mali.ml/superset/dashboard/sd-classement-disc/)
- [Top 10 et appui des sites ASC](https://dashboard.disc-mali.ml/superset/dashboard/asc-classement-disc/)

Ce lot porte sur DISC. Les tableaux historiques ASC/SD sont préservés. Des liens
sont ajoutés aux introductions des nouveaux espaces de pilotage existants. Les
règles d’accès existantes et le refus par défaut sont réutilisés ; aucun rôle,
utilisateur ou privilège nouveau n’est créé.

## Géolocalisation des sites

`formview_location_gps` contient le formulaire propre au site, avec le point dans
`location.geopoint` (ancien champ direct `geopoint` accepté). Ce n’est pas le GPS
collecté lors d’une visite du superviseur. Le dénominateur est le portefeuille
courant `mv_superset_sd_portfolio`, une ligne par UUID de site. Ce portefeuille
ne donne pas le statut fonctionnel DHIS2.

Le dernier rapport daté au plus tard à l’instant du calcul est retenu. Des rapports
à la même dernière date sont ambigus, sans choix arbitraire. Les deux premières
composantes du geopoint sont latitude et longitude. Elles doivent être numériques,
dans [-90,90] et [-180,180], et différentes ensemble de (0,0). Les coordonnées
précises ne sont pas stockées dans la nouvelle vue ni exposées par les datasets.
Un ancien point valide ne masque pas un dernier point invalide.

Quatre états exclusifs : sans relevé, coordonnées absentes/invalides, dernier
relevé ambigu, coordonnées exploitables. La couverture est exploitables / tous
les sites du périmètre courant. Les deux contrôles supplémentaires concernent :

- Dernier relevé exploitable de plus de 12 mois : ancienneté, sans inférer une fermeture.
- Point hors rectangle latitude [10,26], longitude [-13,5] : simple contrôle de
  plausibilité, sans test polygonal des frontières du Mali ni validation GPS terrain.

Les listes CSV/Excel contiennent les identifiants, l’arborescence, le statut,
les dates et les contrôles. La date historique du dernier point exploitable est
conservée même si le dernier relevé doit être vérifié. Il n’y a pas de filtre de
période : c’est l’état du répertoire actuel. Tous les filtres territoriaux affectent
les cartes, graphique et exports.

ASA reste séparé. Sa vue `mv_supervisor_geoloc` rassemble les coordonnées de
formulaires de visite SD, et n’est pas assimilée à un registre de géolocalisation
des sites. Aucun indicateur de couverture des sites ASA n’est inventé à partir
de ces positions.

## SD : un classement de portefeuilles courants

Critère unique : somme des sites-mois au quota complet / nombre de sites-mois
considérés. Le quota existant est 1 visite ASC, 5 visites sans ASC, 1 entretien
dans le même site et mois. La source est le relevé natif
`mv_superset_sd_chw_monthly_status` ; la réalisation peut combiner des déclarations
de plusieurs auteurs. Les affectations du répertoire sont actuelles, non historiques.
Ce tableau ne certifie donc pas la performance individuelle passée du SD nommé.

Seules les affectations identifiées sans conflit et munies d’un UUID SD sont
éligibles. Le minimum est 5 sites distincts **dans la période et le périmètre
sélectionnés**, y compris ceux sans activité. Les affectations ambiguës et
manquantes sont comptées séparément. Aucun auteur arbitraire n’est choisi.

Le dernier mois civil complet est sélectionné par défaut. La sélection de plusieurs
mois répète les sites comme sites-mois. Le déploiement progressif et les mutations
ne sont pas reconstitués par ce portefeuille courant. Il faut comparer des périodes
et contextes appropriés, pas transformer ce résultat en couverture historique du
programme.

Top 10 : quotas les plus élevés. Appui prioritaire : quotas les plus faibles,
strictement inférieurs à 100 %, parmi les portefeuilles éligibles. La liste des
bases insuffisantes est séparée. Il n’y a pas de score composite à poids arbitraires.

## ASC : compétence observée des sites

Le formulaire d’observation évalue un site, pas nécessairement un agent unique.
Le classement s’intitule donc **sites ASC**, avec l’arborescence et l’UUID du site.
Il ne rattache pas artificiellement des scores historiques à un agent actuel.

Une seule observation par site et mois : la plus récente. Les égalités de date
sont exclues du score. Les valeurs absentes, non numériques et hors [0,100]
sont conservées dans les contrôles, jamais assimilées à une compétence nulle.
La règle reprend celle du lot SD qualité, y compris la virgule décimale.

Critère : moyenne des scores mensuels exploitables /100. Minimum : 3 mois
évalués dans la période filtrée. La période par défaut est les **six mois civils
complets précédents**, calculés par les expressions temporelles Superset 5.
Le nombre de mois évalués, les mois avec visite, les scores inutilisables et la
couverture des scores accompagnent toujours la moyenne. Un mois sans visite ne
peut pas être classé comme un échec clinique. Les sites sans aucune observation
ne font pas partie du relevé d’évaluation ; les listes de rapportage et de
supervision restent les sources pour rechercher leur absence d’activité.

Top 10 : meilleures moyennes. Appui : moyennes inférieures à 80, en ordre croissant.
Le taux des mois évalués atteignant 80 est affiché séparément. Les seuils de volume
sont des garde-fous opérationnels, pas des seuils statistiques validés. Aucun
classement ne résume à lui seul la qualité du travail ou le contexte d’exercice.

## Filtres, ex æquo et exports

L’agrégation, le minimum de volume et la limite de 10 sont appliqués **après** les
restrictions de lignes et les filtres de période et géographie. Il n’y a pas de rang
national stocké en amont. Sélectionner une région recalcule donc les résultats dans
cette région. Pour un SD multiterritorial, le résultat décrit sa fraction de
portefeuille visible dans la sélection, et non un total national caché.

Les tableaux limités contiennent au plus 10 lignes. Les ex æquo gardent le même
score ; le choix à la limite ne constitue pas un départage de qualité. L’export
éligible complet permet de consulter tous les ex æquo. Les listes « données
insuffisantes » isolent ceux qui ne remplissent pas le minimum. Un tableau vide
ne signifie pas une absence d’activité. Les exports complets sont limités à
100 000 lignes et portent des libellés français. Aucun téléphone, e-mail,
identifiant de patient ou coordonnée précise n’est ajouté.

## Exploitation et vérification

`geo_rank_sql.py` génère les trois SQL versionnés. `refresh_geo_rank.py` construit
ses seules nouvelles vues matérialisées dans la connexion DISC (id 1). Transaction
à lecture répétable, verrou consultatif, contrôle du grain et du répertoire,
préparation à côté puis remplacement atomique des trois relevés. Un échec laisse
le précédent ensemble intact. Aucun objet clinique amont n’est modifié.

`disc-geo-ranking-refresh.timer` : 03/09/15/21 h 35 UTC, décalage aléatoire maximal
de deux minutes. Les dates de calcul ne certifient pas la fraîcheur de la
réplication amont ou la synchronisation technique des téléphones.

```sh
python geo_rank_sql.py
docker exec superset_app python -u /app/superset_config/asc-v2/refresh_geo_rank.py --create
docker exec superset_app python -u /app/superset_config/asc-v2/provision_geo_rank.py
docker exec superset_app python -u /app/superset_config/asc-v2/verify_geo_rank.py
# Publication après contrôles des brouillons :
docker exec superset_app python -u /app/superset_config/asc-v2/provision_geo_rank.py --publish
docker exec superset_app python -u /app/superset_config/asc-v2/verify_geo_rank.py
```

Les tests utilisent les SQL réels avec des fixtures : dernier point invalide après
ancien point valide, égalité de date, (0,0), site sans relevé ; score récent faible
après ancien score élevé, seuil 80 et score absent. Ils vérifient aussi le grain,
les bornes, les restrictions d’un vrai rôle régional et le refus par défaut,
les minimums et l’ordre des top 10, les listes d’appui, les résultats contre le SQL
natif filtré et les exports JSON/CSV/Excel via l’API native. Aucun enregistrement
nominatif n’est écrit dans les journaux de test ou le dépôt.

Le déploiement serveur utilise une archive Git des fichiers `superset/`, dans le
montage existant `/opt/moh_superset/superset_config/asc-v2/`. Il ne s’agit pas d’un
`git pull` dans le projet Superset amont. La sauvegarde de métadonnées préalable
reste sur le serveur avec permissions privées.

Référence d’implémentation : [tri de la table native Superset 5.0.0](https://github.com/apache/superset/blob/5.0.0/superset-frontend/plugins/plugin-chart-table/src/buildQuery.ts).
