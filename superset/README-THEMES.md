# Lot 4 — Tableaux thématiques ASC

Point d’entrée : https://dashboard.disc-mali.ml/superset/dashboard/asc-thematiques/.
Onze tableaux spécialisés, construits à côté du tableau ASC historique :

| Tableau | Adresse | Lecture principale |
|---|---|---|
| Vaccination et zéro dose | `/superset/dashboard/asc-theme-vaccination/` | Activité mensuelle et liste actuelle de suivi séparées |
| Nutrition | `/superset/dashboard/asc-theme-nutrition/` | Observations MAM/MAS et rapports de sortie/suivi |
| Santé maternelle | `/superset/dashboard/asc-theme-maternelle/` | Patientes avec grossesse confirmée, suivis, CPN, accouchements |
| Santé néonatale | `/superset/dashboard/asc-theme-neonatale/` | Enregistrements, suivis, état civil, références |
| Planification familiale | `/superset/dashboard/asc-theme-planification/` | Conseil et épisodes d’utilisation de méthodes |
| Paludisme et soins des plus de 5 ans | `/superset/dashboard/asc-theme-paludisme/` | Fièvre, TDR, traitements et grossesse |
| Références et continuité | `/superset/dashboard/asc-theme-references/` | Références et suivis d’arrivée, sans faux taux d’aboutissement |
| Tuberculose | `/superset/dashboard/asc-theme-tuberculose/` | Malades suivis, contacts évalués/référés et perdus de vue retrouvés |
| Consultations et morbidités des moins de 5 ans | `/superset/dashboard/asc-theme-pec-enfant/` | Consultations, diagnostics et références |
| Promotion de la santé et WASH | `/superset/dashboard/asc-theme-promotion/` | Communications, VAD explicites, causeries et sujets abordés |
| Inscriptions et population enregistrée | `/superset/dashboard/asc-theme-enregistrements/` | Créations et inscriptions par âge/sexe, sans prétendre recenser la population actuelle |

Le catalogue `theme_catalog.json` décrit 137 compteurs avec libellé, unité, expression,
limites de lecture et correspondance avec les graphiques historiques. Il ne s’agit
pas de 137 indicateurs de couverture ou de personnes distinctes. Les diagnostics
peuvent se cumuler ; les observations mensuelles d’un même bénéficiaire peuvent
réapparaître plusieurs mois. Les séries ne sont donc pas une incidence ni une prévalence.

## Navigation et filtres

Chaque tableau comprend Synthèse, Territoires et exports, Méthode et qualité.
Vaccination ajoute Zéro dose · liste actuelle. La synthèse propose les repères clés du thème, une comparaison régionale et une tendance.

- Période : dernier mois civil complet par défaut ; choisir des mois entiers.
- Préparation : douze mois complets au maximum, selon les mois effectivement présents
  dans chaque source. Le mois courant incomplet est exclu des séries.
- Région → District → CSCOM : filtres en cascade, mêmes libellés que les listes
  opérationnelles. Les règles RLS s’appliquent même sans filtre d’interface.
- Indicateur à explorer : sélection unique pour comparaison, tendance et tableaux
  territoriaux ; les cartes conservent leur propre indicateur.
- La tendance conserve les douze mois préparés et suit le territoire et l’indicateur.
- Les cartes et exports mensuels sont limités aux unités rattachées au répertoire
  courant. Les lignes non rattachées restent dans le contrôle national.
- La santé maternelle a un grain CSCOM/mois : aucun détail par site n’est inventé.
  Le chemin région/district/CSCOM est utilisé pour éviter de multiplier des totaux
  lorsqu’un identifiant de CSCOM apparaît dans plusieurs branches du répertoire.

Le répertoire est actuel ; les mutations historiques ne sont pas reconstituées.
L’ouverture DHIS2 n’est pas reliée ici. Un zéro fourni par une grille amont peut
représenter une activité nulle ou une absence de saisie ; un NULL n’est pas forcé
à zéro. Les dates affichées datent ce calcul, pas la réplication des téléphones
ni l’actualisation des vues amont.

## Corrections par rapport à l’ancien tableau

1. **Vaccination :** les nouvelles cartes retiennent le dernier suivi non ambigu
   par enfant et mois à 0–23 mois. Les calculs historiques restent identifiés dans
   le sélecteur. Leur dénominateur d’inscriptions ne sert pas à calculer de couverture.
2. **Zéro dose :** les signalements mensuels historiques sont séparés de la liste
   actuelle du lot 2, déjà contrôlée. Cette liste retient les 12–59 mois avec
   Penta 1 explicitement non reçu, sans preuve positive retrouvée ni décès connu,
   et avec rattachement courant non ambigu. Le mois et l’indicateur mensuels ne
   filtrent pas cet onglet ; Région/District/CSCOM s’appliquent. L’historique des
   antigènes du tableau initial reste accessible par un lien dédié ; il n’est pas
   reconstruit en nouvel export individuel dans ce lot.
3. **Rattachement vaccinal :** certaines lignes historiques ont perdu leur site
   dans une jointure amont. Leurs volumes sont conservés, regroupés par mois dans
   un contrôle national sans créer de faux site. Le nombre de lignes amont
   regroupées reste visible. Les doublons sur un identifiant renseigné bloquent
   l’actualisation au lieu d’être additionnés arbitrairement.
4. **Grossesses :** l’ancien `nber_pregnant` dédupliquait `parent__id`, c’est-à-dire
   le ménage du contact. `maternal_confirmed.sql` déduplique maintenant les patientes
   (`patient_uuid`) avec confirmation positive dans les deux formulaires de
   confirmation/enregistrement, par CSCOM et mois, dans le répertoire courant.
   Les confirmations sans identifiant patient utilisable ne sont pas comptées
   comme patientes distinctes. SP, décès et références explicites utilisent aussi
   les formulaires natifs ; les autres compteurs conservent la source historique.
5. **SP :** SP1 est une prise déclarée ; SP ≥3 exige une administration déclarée
   de rang 3 à 6. Le rang de dose n’est pas le nombre de prises dans le mois ni
   une couverture TPIg3. La patiente est dédupliquée par CSCOM et mois.
6. **Références :** les références et les rapports d’arrivée ne sont pas appariés
   par épisode : pas de taux d’aboutissement ni de soustraction « non arrivés ».
7. **Nutrition et néonatal :** aucun taux de guérison ou mortalité depuis des
   populations différentes. Le nouveau suivi J0–J7 compte des dossiers mère/naissance
   et des dates réelles distinctes ; il ne prétend pas compter chaque nouveau-né.
8. **Promotion :** les activités explicites sont recalculées avant toute jointure
   géographique, évitant le facteur multiplicatif de plusieurs contacts ASC par
   site. Le total historique qui mélangeait des suivis cliniques sans preuve de
   VAD est remplacé par les communications enregistrées. Le compteur WASH qui
   comptait des lignes déjà agrégées est remplacé par deux mesures distinctes :
   séances abordant WASH et formulaires d’activité WASH uniques.
   Les séances multithématiques et les participations ne sont pas des personnes uniques.
9. **Population :** le détail âge/sexe est calculé sur les UUID de contacts uniques,
   par mois d’inscription et âge renseigné au dossier, avec tranches exclusives
   <1, 1–5, 6–12, 13–19, 20+ et catégorie inconnue. Le chevauchement à 19 ans de
   l’ancienne source disparaît. Les tranches <2, imbriquées dans d’autres tranches,
   ne sont pas additionnées dans un total. Ce n’est pas une population actuelle.
10. **PEC enfant/PF :** les limites de jointure des sources historiques sont
    explicites : les suivis seuls sans nouvelles consultations et certains
    renouvellements peuvent manquer. L’absence d’activité n’est pas une preuve
    d’absence de soins. Le lot ne réécrit pas les données cliniques amont.

## Sources, architecture et cadence

Les sources historiques sont conservées. Les vues `mv_asc_theme_*` sont propres
à ce lot, au grain site/mois ou CSCOM/mois. Elles lisent les agrégats historiques,
le répertoire du lot 2 et, pour les corrections ciblées, les formulaires de
communication/grossesse et les contacts. Les nouveaux relevés ne stockent aucun
nom ou identifiant de patient ; les identifiants patients utilisés pendant les
calculs sont agrégés et ne figurent pas dans les résultats.

`theme_sql.py` produit les définitions lisibles versionnées dans `sql/themes`.
`refresh_themes.py` vérifie leur concordance, le grain source, les dates et les
valeurs ; il prépare des vues `_next` et les remplace dans une transaction par thème.
Une erreur laisse le précédent calcul disponible. Seuls les anciens relevés de
ce lot sont supprimés après remplacement ; aucune source amont n’est supprimée
ou actualisée. Les index mois et géographie évitent de relire les formulaires
lors de l’ouverture des tableaux. Les corrections de communication et de population
utilisent les index existants de métadonnées, d’UUID et de date ; aucun index amont
n’est créé ou modifié. La période promotionnelle est celle de l’activité déclarée
(sinon du rapport), parmi les rapports déclarés depuis le début de la période
préparée ; les saisies tardives du mois courant peuvent donc alimenter un mois antérieur.

Minuteur dédié : toutes les six heures, à 02/08/14/20 h 35 UTC, avec léger
étalement. Cette cadence concerne les relevés thématiques, pas la réplication
amont. Le calcul des listes zéro dose garde le minuteur existant du lot 2.

## Exports et accès

**EXPORT TOUS LES INDICATEURS** contient une ligne par grain source/mois avec
Région, District, CSCOM, site/zone si disponibles, identifiants territoriaux,
compteurs, contrôle du rattachement et date du calcul. Il suit période et
territoire, et ignore le sélecteur d’indicateur, comme indiqué dans le tableau.
Les exports agrégés ne contiennent pas de nom de patient.

Les exports CSV/Excel du relevé zéro dose restent individuels, sur le périmètre
courant et les droits existants. Ne jamais les sauvegarder dans Git ou dans les
journaux. Leur date de relevé figure dans les colonnes exportées.

Les tableaux de détail ont une pagination serveur de vingt lignes. Les tableaux
EXPORT ont une pagination d’affichage et une limite de 100 000 lignes. Le contrôle
compare les exports aux volumes SQL et bloque la publication en cas de dépassement.
Chaque actualisation refuse également un relevé dépassant cette limite sur le périmètre exportable.
Les UUID fixes rendent le provisionnement idempotent. L’audience est celle du
ASC historique ; aucun utilisateur, rôle ou accès public n’est créé. Les règles
RLS du lot 2 et le refus par défaut sont appliqués aux 21 nouveaux datasets
(dix sources, dix déclinaisons par indicateur, un contrôle de disponibilité).

## Déploiement et vérification

Sauvegarde privée initiale des métadonnées :
`/opt/moh_superset/backups/avant-asc-thematiques-20261023.sql.gz`.
La livraison des fichiers se fait par archive du commit dans
`/opt/moh_superset/superset_config/asc-v2/`, qui n’est pas un dépôt Git.

```sh
docker exec superset_app python -u /app/superset_config/asc-v2/refresh_themes.py --preflight
docker exec superset_app python -u /app/superset_config/asc-v2/refresh_themes.py --create
docker exec superset_app python -u /app/superset_config/asc-v2/validate_themes.py
# Contrôle de conservation des sources, ciblé ou complet si nécessaire :
docker exec superset_app python -u /app/superset_config/asc-v2/validate_themes.py --source --only vaccination
docker exec superset_app python -u /app/superset_config/asc-v2/provision_themes.py
docker exec superset_app python -u /app/superset_config/asc-v2/verify_themes_access.py
# Après inspection du brouillon dans le navigateur :
docker exec superset_app python -u /app/superset_config/asc-v2/provision_themes.py --publish
docker exec superset_app python -u /app/superset_config/asc-v2/verify_themes_access.py --regional-only
```

`--create` conserve les vues déjà présentes. Pour appliquer un nouveau SQL à des
relevés existants, lancer le calcul sans `--create` : les vues sont reconstruites
et remplacées atomiquement par thème. Un verrou de session PostgreSQL évite deux calculs thématiques simultanés, y compris entre les transactions des différents thèmes.
Le délai SQL limite chaque étape à quinze minutes (trente pour promotion/VAD) et le délai de verrouillage à dix secondes. Chaque thème conserve indépendamment son dernier relevé complet ; leurs dates de calcul peuvent différer après un échec. `--only THEME` permet une reprise ciblée sans relire les autres sources.

`validate_themes.py` vérifie l’unicité, les bornes mensuelles, l’absence de valeurs
négatives/non finies, les sommes territoriales, le respect du grain, la partition
âge/sexe et la définition du signalement actuel zéro dose. `--source` vérifie la
conservation des sommes et des lignes amont pendant le rattachement géographique.
`verify_themes_access.py` exerce les exports natifs CSV sur toute la période,
Excel sur le mois par défaut, puis les exports et tentatives hors périmètre d’un
lecteur régional, sans imprimer de contenu individuel. Chaque client vérifie son
identité avant la requête ; le refus par défaut est contrôlé sur les sources du catalogue.

Installer `systemd/asc-themes-refresh.*` et activer seulement le nouveau minuteur.
Journaux : `journalctl -u asc-themes-refresh.service`. Un retrait du lot consiste
à désactiver ce minuteur et remettre ses douze dashboards en brouillon, sans
restaurer globalement les métadonnées ni modifier le tableau ASC historique.

## Livraison du 23 octobre 2026

Les dix tableaux et leur portail sont publiés. Les validations des dix relevés,
le remplacement atomique ciblé vaccination et la conservation de sa source ont
été contrôlés. Les 22 exports nationaux et 33 exports/tests régionaux natifs
CSV/Excel ont passé les contrôles de volume ; les sommes CSV ont été comparées
au SQL. Les accès régionaux et le refus par défaut ont été vérifiés sur les
21 datasets. Les exports hors région sont vides, y compris la liste zéro dose.
Les dix synthèses, les filtres en cascade et le dictionnaire ont été inspectés
dans le navigateur. Le minuteur dédié est activé, sans changer les autres minuteurs.

## Correction du paludisme simple des moins de cinq ans — 23 octobre 2026

Le compteur `malaria_simple` utilise la classification native explicitement
positive `has_malaria = 'yes'` du formulaire, avec âge renseigné entre 0 et moins
de 5 ans. Il décrit des consultations classées paludisme, sans attester un
traitement CTA. Le champ de traitement antérieur `nb_days_cta_treatment`,
conditionnel dans le formulaire, ne sert plus à exclure ces premières consultations.
L’audit retrouve notamment 6647 TDR positifs et 6451 classifications paludisme
brutes en septembre 2026, avant déduplication et rattachement, alors que l’ancien
compteur préparé était à zéro. Tous ces TDR positifs ont un nombre de jours de
traitement CTA antérieur absent. Ces effectifs bruts ne sont pas le total final
affiché et ne constituent pas des enfants uniques.

`sql/themes/malaria_u5.sql` retient la dernière évaluation par enfant et date de
consultation déclarée (sinon date du rapport). Les derniers horodatages ex æquo
restent exclus comme ambigus ; un enfant sans identifiant ne fusionne pas avec
les autres dossiers anonymes : chaque rapport conserve sa clé. Les âges absents,
invalides ou hors [0,5[ ne sont pas comptés comme moins de cinq ans. Une réponse
absente ne devient pas un diagnostic positif ; aucune classification clinique
n’est recalculée à partir d’une simple suspicion ou d’un TDR isolé.

La projection finale ne contient que les volumes par site et mois, jamais les
identifiants patients. Les mois/sites manquants dans la source historique sont
conservés ; leurs autres compteurs restent NULL. Les autres compteurs existants
sont inchangés, ce que vérifie une référence mensuelle avant/après.

Le tableau, ses filtres, son audience, ses RLS et ses identifiants de graphiques
restent les mêmes. `update_malaria_method.py` met seulement ses deux notes de
méthode à jour, sans reprovisionner les autres tableaux. Les prochaines exécutions
de `provision_themes.py` utilisent aussi la méthode corrigée du catalogue.

```sh
docker exec superset_app python /app/superset_config/asc-v2/verify_malaria_u5.py --save-baseline /tmp/malaria-baseline.json
docker exec superset_app python /app/superset_config/asc-v2/refresh_themes.py --only pec-enfant
docker exec superset_app python /app/superset_config/asc-v2/update_malaria_method.py
docker exec superset_app python /app/superset_config/asc-v2/verify_malaria_u5.py --baseline /tmp/malaria-baseline.json
docker exec superset_app python /app/superset_config/asc-v2/validate_themes.py --only pec-enfant --source
docker exec superset_app python /app/superset_config/asc-v2/verify_themes_access.py --only pec-enfant --readers
```

Le timer thématique existant réutilise cette correction aux actualisations suivantes.
Les vues cliniques d’origine et les flux OpenFn ne sont pas modifiés par cette correction.

## Harmonisation du parcours paludisme — 24 octobre 2026

Cette définition remplace celle du compteur général `malaria_suspected` : l’ancien
227 de septembre ne représentait que la suspicion sans TDR pour rupture de stock,
et non l’ensemble des consultations suspectes/testées. L’ancienne vue comptait
aussi un alias de parent utilisateur comme UUID distinct ; le parcours corrigé
compte les consultations après déduplication enfant/jour, avec le vrai UUID rapport.

Tous les compteurs ci-dessous utilisent **le même âge < 5 ans renseigné, la même
date de consultation, la même dernière évaluation non ambiguë par enfant/jour et
le même rattachement territorial** :

- `malaria_suspected` : consultations avec TDR positif/négatif **ou** classification
  native `has_malaria_suspicion = yes` sans résultat TDR, union sans doublon.
- `malaria_tested` : consultations avec résultat TDR positif/négatif renseigné.
- `malaria_positive`, `malaria_negative` : sous-ensembles selon le résultat TDR.
- `malaria_presumed` : classification native de suspicion sans résultat TDR. Dans
  le formulaire, ce champ signifie fièvre, rupture de TDR et absence d’éruption.
- `malaria_simple` : classification native `has_malaria = yes` **et** TDR positif.
- `malaria_conflicts` : classification sans preuve TDR positive, présumé avec
  résultat TDR renseigné, ou résultat TDR non reconnu. Ces cas ne sont pas forcés
  dans les confirmés pour respecter artificiellement une inégalité.

Identités contrôlées pour chaque site/mois : suspects évalués = TDR interprétables
+ présumés sans TDR ; TDR interprétables = positifs + négatifs ; paludisme simple
avec TDR positif ≤ TDR positifs ≤ TDR interprétables ≤ suspects évalués. Aucun
traitement administré, nombre de kits, incidence ou effectif d’enfants uniques
n’est inféré. Les résultats TDR positifs incluent les autres classifications
possibles : ils ne sont pas assimilés automatiquement à du paludisme simple.

Cette reconstruction opérationnelle par consultation s’appuie sur les champs
réellement collectés. Elle est cohérente avec la distinction OMS entre suspects,
testés, présumés non testés et confirmés ; elle ne prétend pas recenser tous les
épisodes suspects de la population ni remplacer une définition PNLP validée.
Source primaire : [métadonnées OMS des cas suspects](https://www.who.int/data/gho/indicator-metadata-registry/imr-details/4633).

Les huit cartes sont réparties en deux lignes, et les compteurs supplémentaires
figurent dans le sélecteur, le détail et les exports. Le dictionnaire présente
leurs critères. `provision_themes.py --only pec-enfant --publish` actualise les
deux datasets et ce seul tableau ; les autres dashboards sont contrôlés inchangés.
Le timer thématique existant conserve la correction aux calculs suivants.

Contrôle national de septembre 2026, sites rattachés au répertoire courant :
8 134 suspicions évaluées = 7 896 consultations avec TDR + 238 présumées sans
TDR ; 7 896 = 6 551 positifs + 1 345 négatifs ; 6 358 paludismes simples avec
TDR positif. Aucune incohérence de classification n'est observée dans ce relevé.
Les sept autres compteurs et le paludisme simple sont inchangés sur les douze
mois par rapport à la référence précédant cette harmonisation.

Pour cette version, après `refresh_themes.py --only pec-enfant`, utiliser
`provision_themes.py --only pec-enfant --publish` afin de mettre aussi à jour
les huit cartes, le sélecteur, le dictionnaire et les colonnes d'export.


## Enrichissement depuis le canevas d’analyse — 24 octobre 2026

44 nouvelles séries (dont 20 ventilations de participations par thème et sexe),
avec correction de SP1, SP de rang ≥3 et décès maternels signalés. Huit compteurs
néonatals hérités sont retirés du nouveau tableau : le calcul amont tronquait les
dates au mois et multipliait certaines inscriptions. Le dashboard ASC historique
reste intact. Le catalogue contient désormais 137 séries, réparties sur 11 thèmes.

- **Santé maternelle** : références CPN explicites et accouchements à domicile
  avec référence déclarée. La SP1 est une prise déclarée ; SP ≥3 accepte les codes
  `sp_3`…`sp_6`, avec administration explicitement déclarée. Il ne s’agit pas de
  trois administrations dans le mois. Les décès sont dédupliqués entre formulaires
  par patiente/CSCOM/mois, datés du signalement et sans validation de cause.
- **Tuberculose** : nouveau tableau et entrée dans le portail, contacts évalués et
  référés, malades suivis et motif explicite `patient_lost_found`. Un vrai zéro
  reste possible, sans déduire un retour d’une absence.
- **Vaccination** : dernier suivi non ambigu par enfant/mois, âge 0–23 mois,
  enfants observés, à jour, à jour à 23 mois et sans Penta 1 déclaré à 12–23 mois.
  Même cohorte pour les compteurs comparables. Ce n’est pas une couverture de
  population ; la liste individuelle actuelle de relance reste séparée.
- **Moins de cinq ans** : consultations évaluées et fièvre dans la cohorte native
  déjà utilisée par le parcours paludisme ; la fièvre ne constitue pas un diagnostic.
- **Néonatal** : profils enregistrés, acte/déclaration civile, dossiers mère/naissance
  suivis, trois jours distincts entre J0 et J7 et référence explicite. Un dossier
  mère/naissance peut contenir plusieurs nouveau-nés : ne pas le présenter comme
  un enfant unique. Les visites sont classées par mois de naissance, avec les suivis
  disponibles jusqu’au calcul ; les autres thèmes utilisent leur date documentée.
- **Planification familiale** : conseil, nouvelles utilisatrices et utilisatrices
  observées, dédupliquées par patiente/site/mois. Aucune assimilation à un stock.
- **Promotion/WASH** : formulaires WASH uniques, VAD cliniques explicitement
  déclarées, total de rapports VAD promotionnels/cliniques et participations par
  thème et sexe. Plusieurs formulaires peuvent décrire une visite physique ;
  plusieurs thèmes peuvent compter les mêmes participations.

### Lecture trimestrielle

Les séries mensuelles agrégées s’additionnent en **observations mensuelles**.
Un total trimestriel de patients-mois peut donc dépasser les personnes distinctes
sur le trimestre calculées séparément dans le fichier Excel. Aucun identifiant
patient n’est exporté par ces nouveaux jeux agrégés. Les personnes distinctes par
période arbitraire ne sont pas reconstituées depuis des totaux mensuels.

### Déploiement ciblé et vérification

`refresh_themes.py --only <thème>` reconstruit atomiquement son relevé ;
`provision_themes.py --only <thème> --publish` met à jour son tableau et ses jeux.
`--hub-only --publish` actualise uniquement la navigation et la disponibilité du
portail, avec vérification que les autres dashboards restent inchangés. Les règles
régionales et district sont appliquées aux nouveaux jeux. La disponibilité inclut
`district_uuid` pour permettre les contrôles district.

`verify_canevas.py` exécute le SQL natif sur des cas anonymes (âges, derniers suivis,
ex æquo, administration SP, décès répétés, dates J0/J7/J8, contacts et retours TB),
puis les bornes entre compteurs des relevés. `verify_canevas_scopes.py` contrôle les
nouveaux jeux TB et le portail avec un vrai compte district ; les exports natifs
CSV/Excel et les refus interrégionaux sont testés par `verify_themes_access.py`.
La promotion dispose d’un délai SQL de 1800 s pour ses lectures bornées ; les
sources cliniques amont ne sont ni modifiées ni rafraîchies par ce lot.

### Validation de cette livraison

Les sept relevés concernés sont reconstruits et leurs tableaux publiés, ainsi
que le portail à onze thèmes. Les fixtures natives, les bornes entre compteurs,
la conservation des huit compteurs de référence du parcours paludisme et les
contrôles de structure/grain/volumes sont réussis. Les **40 exports et tentatives
hors région** CSV/Excel ont réussi, avec comparaison des sommes CSV au SQL et
refus par défaut sur les jeux thématiques. Les nouveaux jeux TB et le portail ont
également passé les requêtes d’un compte district réel, sans fuite hors périmètre.
Les assertions de publication ciblée conservent les autres dashboards, dont le
tableau ASC historique, SD, ASA et SEBAC. Sauvegarde de métadonnées prise avant
publication et intégrité gzip vérifiée ; Superset répond OK et le minuteur reste actif.
