# Monitoring et maintenance IT DISC

Tableau : https://dashboard.disc-mali.ml/superset/dashboard/disc-maintenance-it/

Ce lot lit les documents techniques `telemetry` de `couchdb_users_meta`. Il
n’extrait aucun message feedback, journal libre, dossier clinique, téléphone,
champ d’authentification ou URI de connexion. Les tables sources ne sont pas
modifiées et les tableaux de bord métier conservent leurs définitions et accès.

## Accès

Le tableau publié et ses deux datasets sont réservés à `hmombo` (administrateur)
et au rôle `DISC_IT_MONITORING`. Le provisionnement crée le rôle, sans l’attribuer
à un utilisateur. Pour désigner un collègue IT, `hmombo` ajoute ce rôle à son
compte Superset, en conservant `DISC_VIEWER` pour la navigation en consultation.
Ce rôle IT n’accorde ni SQL Lab, ni création/modification de contenu, ni accès
global à une base, ni nouveaux tableaux cliniques.

Une RLS Base `1 = 0` refuse les données IT aux profils sans rôle IT, avec
l’exception habituelle des administrateurs Superset. Les administrateurs sont
des comptes privilégiés à maîtriser séparément. Le rôle national et les rôles
région/district n’accordent pas l’accès IT. Aucun rôle territorial n’est copié
sur ces relevés nationaux de maintenance.

## Mesures et limites

- Grain du suivi : couple **compte–deviceId**, complété par une ligne pour les
  comptes courants sans télémétrie. Un deviceId n’est pas un IMEI certifié. Un
  appareil partagé peut figurer dans plusieurs profils, une réinstallation
  peut produire un nouvel identifiant. Les cartes distinguent appareils uniques,
  profils et comptes.
- Comptes courants : documents utilisateur non supprimés/désactivés, hors
  noms contenant formation. Ce périmètre ne prouve pas une affectation ou une
  activité actuelle sur le terrain. Les autres comptes observés restent
  consultables en changeant le filtre.
- Les dates sont les **jours déclarés par le client**. L’absence de jour, un
  calendrier impossible et une période future sont distincts. La dernière
  période plausible est privilégiée ; deux dernières observations du même jour
  ou un document marqué conflicted rendent le dernier stockage inexploitable.
- Stockage : libre et total numériques en octets, total positif, libre entre
  zéro et total. Conversion : 1 Gio = 1 073 741 824 octets. Seuil critique < 1 Gio,
  surveillance < 2 Gio ou < 10 % libre. Ces seuils IT de revue sont explicites.
  Les cartes ne comptent que les mesures âgées de 7 jours au plus. Une mesure
  ancienne reste dans la liste, sans être présentée comme un état actuel.
- Réplication : `count` des métriques `replication:medic:to/from:success/failure`
  compte les événements enregistrés ; leur `sum` est une somme de durées et
  n’est pas utilisée comme nombre de succès. Les compteurs de motifs et de
  documents refusés utilisent `sum`. Réussites et échecs peuvent coexister.
- Dernière synchronisation : **dernier jour avec un succès observé**, dans
  chaque sens. L’heure exacte et l’exhaustivité d’un transfert ne sont pas
  reconstituées. Une absence de succès observé reste vide.
- Horloge : présence du signal `client-date-offset`, bornes agrégées en
  millisecondes converties en minutes. Son absence ne certifie pas l’heure.
  Les signaux des profils couvrent aujourd’hui et les 6 jours précédents.
  Une horloge fortement retardée peut aussi faire paraître les données anciennes.
- Géographie : rattachement courant du compte. Une branche ambiguë ou inconnue
  reste signalée, sans rattachement inventé.
- Versions : dernier relevé CHT/APK/Android/Chrome, sans désigner arbitrairement
  une version comme obsolète. Les distributions excluent les dernières dates
  ambiguës. La RAM, la batterie et l’état de santé physique des tablettes ne
  sont pas inférés depuis le stockage.

Référence primaire : [télémétrie CHT](https://docs.communityhealthtoolkit.org/apps/guides/performance/telemetry/).

## Filtres, listes et qualité

État du compte par défaut : **Compte courant**. Région, district, CSCOM, type
d’appareil et compte suivent le répertoire courant. Le filtre de période ne
concerne que les graphiques quotidiens de réplication/horloge. Les derniers états
des profils et les succès les plus récents ignorent ce filtre.

Le contrôle global de source ignore tous les filtres, pour conserver les
documents non attribuables et les dates invalides/futures. Les motifs d’incident
peuvent se cumuler : ne pas additionner les cartes comme des incidents uniques.
Les listes proposent une vérification, jamais une suppression ou une correction
à distance automatique. Exports CSV/XLSX natifs, plafond vérifié de 100 000 lignes.

Les filtres de stockage et d’ancienneté propres aux listes n’affectent ni les
cartes globales ni les séries quotidiennes. Ils permettent notamment d’isoler
les anciens relevés critiques sans les présenter comme des mesures actuelles.

La couverture doit toujours être lue avant les alertes : un zéro d’incident ne
certifie pas le parc lorsque peu d’appareils remontent des mesures. Le dernier
calcul analytique et le dernier jour plausible de télémétrie sont affichés
séparément. Le premier ne certifie pas la réplication amont ou les téléphones.

## Déploiement et retour arrière

Sources versionnées sous `superset/`, livrées au montage existant
`/opt/moh_superset/superset_config/asc-v2/`. Aucun redémarrage de Superset requis.

```sh
python maintenance_catalog.py
python refresh_maintenance.py
python provision_maintenance.py
python verify_maintenance.py --analytical-only
python provision_maintenance.py --publish
python verify_maintenance.py
```

`refresh_maintenance.py` prépare deux vues `_next`, contrôle leur grain et les
mesures, puis les remplace dans une seule transaction repeatable-read, avec
verrou consultatif, délai de requête de 180 s et délai de verrou de 10 s.
L’ancien relevé est conservé si une étape échoue. Seuls les objets de ce lot
sont remplacés. Le timer `disc-it-monitoring.timer` est horaire à :10 avec
étalement maximal de 90 s. Il ne rafraîchit pas les vues sources couch2pg.

La vérification couvre des fixtures sans données réelles : disque zéro/absent/
négatif, bornes 2 Gio/10 %, date impossible/future, mesure ambiguë, mesure ancienne,
compte sans télémétrie, directions de réplication et conversion d’horloge. Les
endpoints réels sont testés pour hmombo, un profil IT simulé dans le seul processus
de test, et les refus national/région/district/lecteur/visiteur. Aucun compte IT
ou attribution de rôle n’est créé pour les tests. Les exports et chaque requête
de graphique sont vérifiés, sans enregistrer de ligne nominative.

Pour retirer uniquement ce lot : désactiver son timer et relancer
`provision_maintenance.py` sans `--publish`. Les relevés peuvent rester privés
pour la reprise. Ne pas restaurer globalement Superset. Sauvegarde préalable :
`/opt/moh_superset/backups/avant-maintenance-20261028.dump`.
