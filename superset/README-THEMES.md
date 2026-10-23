# Lot 4 — Tableaux thématiques ASC

Point d’entrée : https://dashboard.disc-mali.ml/superset/dashboard/asc-thematiques/.
Dix tableaux spécialisés, construits à côté du tableau ASC historique :

| Tableau | Adresse | Lecture principale |
|---|---|---|
| Vaccination et zéro dose | `/superset/dashboard/asc-theme-vaccination/` | Activité mensuelle et liste actuelle de suivi séparées |
| Nutrition | `/superset/dashboard/asc-theme-nutrition/` | Observations MAM/MAS et rapports de sortie/suivi |
| Santé maternelle | `/superset/dashboard/asc-theme-maternelle/` | Patientes avec grossesse confirmée, suivis, CPN, accouchements |
| Santé néonatale | `/superset/dashboard/asc-theme-neonatale/` | Enregistrements, suivis, état civil, références |
| Planification familiale | `/superset/dashboard/asc-theme-planification/` | Conseil et épisodes d’utilisation de méthodes |
| Paludisme et soins des plus de 5 ans | `/superset/dashboard/asc-theme-paludisme/` | Fièvre, TDR, traitements et grossesse |
| Références et continuité | `/superset/dashboard/asc-theme-references/` | Références et suivis d’arrivée, sans faux taux d’aboutissement |
| Consultations et morbidités des moins de 5 ans | `/superset/dashboard/asc-theme-pec-enfant/` | Consultations, diagnostics et références |
| Promotion de la santé et WASH | `/superset/dashboard/asc-theme-promotion/` | Communications, VAD explicites, causeries et sujets abordés |
| Inscriptions et population enregistrée | `/superset/dashboard/asc-theme-enregistrements/` | Créations et inscriptions par âge/sexe, sans prétendre recenser la population actuelle |

Le catalogue `theme_catalog.json` décrit 96 compteurs avec libellé, unité, expression,
limites de lecture et correspondance avec les graphiques historiques. Il ne s’agit
pas de 96 indicateurs de couverture ou de personnes distinctes. Les diagnostics
peuvent se cumuler ; les observations mensuelles d’un même bénéficiaire peuvent
réapparaître plusieurs mois. Les séries ne sont donc pas une incidence ni une prévalence.

## Navigation et filtres

Chaque tableau comprend Synthèse, Territoires et exports, Méthode et qualité.
Vaccination ajoute Zéro dose · liste actuelle. La synthèse propose quatre repères
(trois pour les thèmes moins fournis), une comparaison régionale et une tendance.

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

1. **Vaccination :** la déclaration « à jour » compte des rapports, pas des enfants
   distincts ; le libellé le précise. Le dénominateur historique des moins de deux
   ans provient des inscriptions : aucun taux de couverture n’est calculé avec lui.
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
   comme patientes distinctes. Les autres compteurs restent ceux de la source
   historique au grain CSCOM.
5. **SP :** le compteur historique « au moins trois SP » porte sur le même mois,
   pas sur toute une grossesse. Il est documenté dans le détail, sans l’appeler TPIg3.
6. **Références :** les références et les rapports d’arrivée ne sont pas appariés
   par épisode : pas de taux d’aboutissement ni de soustraction « non arrivés ».
7. **Nutrition et néonatal :** les sorties/suivis ne sont pas appariés à une cohorte
   d’admissions/naissances : pas de taux de guérison, de mortalité ou de trois visites
   calculé à partir de populations différentes.
8. **Promotion :** les activités explicites sont recalculées avant toute jointure
   géographique, évitant le facteur multiplicatif de plusieurs contacts ASC par
   site. Le total historique qui mélangeait des suivis cliniques sans preuve de
   VAD est remplacé par les communications enregistrées. Le compteur WASH qui
   comptait des lignes déjà agrégées est remplacé par les séances abordant WASH.
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
Le délai SQL limite chaque étape à quinze minutes et le délai de verrouillage à dix secondes. Chaque thème conserve indépendamment son dernier relevé complet ; leurs dates de calcul peuvent différer après un échec. `--only THEME` permet une reprise ciblée sans relire les autres sources.

`validate_themes.py` vérifie l’unicité, les bornes mensuelles, l’absence de valeurs
négatives/non finies, les sommes territoriales, le respect du grain, la partition
âge/sexe et la définition du signalement actuel zéro dose. `--source` vérifie la
conservation des sommes et des lignes amont pendant le rattachement géographique.
`verify_themes_access.py` exerce les exports natifs CSV sur toute la période,
Excel sur le mois par défaut, puis les exports et tentatives hors périmètre d’un
lecteur régional, sans imprimer de contenu individuel. Chaque client vérifie son
identité avant la requête ; le refus par défaut est contrôlé sur les 21 sources.

Installer `systemd/asc-themes-refresh.*` et activer seulement le nouveau minuteur.
Journaux : `journalctl -u asc-themes-refresh.service`. Un retrait du lot consiste
à désactiver ce minuteur et remettre ses onze dashboards en brouillon, sans
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
