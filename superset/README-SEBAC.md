# SEBAC — Surveillance et suivi des alertes DISC

Tableau : https://dashboard.disc-mali.ml/superset/dashboard/sebac-pilotage-disc/

Premier lot : synthèse par cohorte, circuit enregistré, délais d’enregistrement,
priorités actuelles, ancienneté des notifications par site, activité et exports,
contrôles de qualité. Le tableau historique 3 et son graphique 75 restent inchangés.
Son inventaire de 36 indicateurs / variantes est conservé dans
[audit/sebac-20261023/legacy-audit.json](audit/sebac-20261023/legacy-audit.json).

## Corrections et définitions

L’ancien graphique additionne tous les `numerator` : cela ne fournit pas les taux
recommandés par son propre dictionnaire et additionne les anciennetés hebdomadaires.
La nouvelle vue utilise trois sources dédiées, sans modifier les vues métier,
les flux OpenFn ni les documents cliniques :

- `mv_sebac_reports_v1` : un document SEBAC non supprimé par UUID, champs opérationnels
  explicitement sélectionnés. Les dates absentes, invalides, antérieures à 2019 et
  futures sont séparées. La géographie est celle du répertoire DISC courant.
- `mv_sebac_alerts_v1` : une cohorte par `alert_id`, datée du premier signalement
  exploitable. Les signalements répétés ne multiplient pas les alertes. Un ID absent,
  plusieurs sites pour le même ID, un site absent ou des champs source contradictoires
  empêchent le traitement comme alerte distincte fiable. Les collisions entre sites
  ne reçoivent aucun rattachement territorial arbitraire.
- `mv_sebac_sites_v1` : une ligne par site courant, dernière notification ASC MPE /
  événement et ancienneté actuelle. Aucun cumul de jours entre semaines ou sites.
  Sans notification observée, la date et le nombre de jours restent vides.

Les étapes sont reliées par l’ID alerte, avec contrôle de site et d’ordre des
horodatages. Une étape sans site peut être liée lorsque l’origine détermine un
site unique. Une étape sur un autre site ou antérieure au premier signalement
reste dans le contrôle, sans faire avancer le suivi. Les tris de même dernière
date avec classifications différentes restent ambigus.

Le délai « sous 48 h » est le délai **entre enregistrements des rapports**, pas
une mesure certifiée du délai d’investigation sur le terrain. Le taux utilise les
vérifications enregistrées comme base ; le taux de vérification utilise la même
cohorte de signalements. Une base vide donne NULL. La présence d’un formulaire
n’est ni une validation DTC ni un diagnostic confirmé.

Les priorités à 72 h sont les alertes fiables sans vérification enregistrée, sauf
tri explicitement non conforme ; ces derniers sont listés séparément. Ce sont des
listes de revue, pas une décision clinique ni un envoi de message. L’ancienneté à
30 jours est aussi un repère de revue, sans quota de notification : une absence
d’événement peut être normale.

Les MPE et événements peuvent se chevaucher. Un acteur absent / contradictoire
est distinct des autres acteurs. Les nombres de personnes et animaux décédés sont
les valeurs déclarées dans les formulaires ASC, pas des décès individuels uniques ;
une valeur absente reste NULL. Ne pas additionner les étapes du circuit.

## Filtres et exports

Période par défaut : mois civil précédent. Dans les synthèses, elle sélectionne
les premiers signalements ; dans Activité, elle sélectionne les rapports de
chaque étape. La tendance conserve douze mois civils complets et ignore ce filtre. Les étapes d’une cohorte peuvent être enregistrées après la période.
Les priorités, notifications des sites et contrôles de qualité sont des états
actuels toutes périodes et **exclus du filtre de période**. Les filtres Région,
District, CSCOM, Zone et les RLS s’appliquent à toutes les vues et aux exports.

CSV / Excel : menu ⋮ de chaque tableau, Télécharger. Les listes comportent
l’arborescence, les UUID natifs et les dates, sans nom de patient, téléphone,
commentaire clinique libre ni géolocalisation individuelle. Le plafond de 100000
lignes est contrôlé à la vérification ; le détail par site et mois peut approcher
ce plafond en grandissant et doit alors être découpé par période / territoire.

Le rôle dashboard `DISC_DASH_SEBAC` et les restrictions régionales / district sont
réutilisés. Un lecteur sans périmètre est refusé par défaut. Les 172 règles district
couvrent les trois nouvelles sources. Les contrôles hors répertoire ne sont pas
attribués artificiellement à un district. Aucune source SEBAC native identifiée
dans la connexion ASA auditée : ce lot reste **DISC uniquement**.

## Installation et actualisation

Dans le conteneur Superset, après déploiement des sources :

```sh
docker exec superset_app python -u /app/superset_config/asc-v2/refresh_sebac.py --create
docker exec superset_app python -u /app/superset_config/asc-v2/provision_sebac.py --publish
docker exec superset_app python -u /app/superset_config/asc-v2/verify_sebac.py
```

Le rafraîchissement prend un verrou transactionnel et un snapshot repeatable-read,
construit les trois vues suivantes, vérifie grains, conservation des volumes et
chronologie, puis les remplace dans une transaction. Un échec garde l’ancien relevé.
Les sources d’origine ne sont jamais rafraîchies ou remplacées par ce script.

Installer `systemd/sebac-refresh.service` et `.timer`, activer le timer horaire.
L’horodatage visible date le calcul analytique, pas la réplication amont ni la
synchronisation des téléphones. Le bandeau Mali est appliqué à ce nouveau tableau.

`verify_sebac.py` couvre les doublons, identités absentes, collisions entre sites,
chronologies inversées, étapes sur un site différent, tri non conforme, tris de
même date contradictoires, exports JSON/CSV/Excel natifs, RLS région/district,
refus par défaut et tentative explicite de lecture hors district.

Lots suivants : approfondir les classifications et la complétude des prélèvements /
résultats selon les versions de formulaires, puis rapprocher les tâches SEBAC et
les étapes enregistrées avec leur calendrier réel. Les faibles volumes d’étapes
DTC doivent être investigués avant d’interpréter les taux comme performance terrain.
