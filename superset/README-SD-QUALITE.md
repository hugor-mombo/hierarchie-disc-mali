# SD — Compétences et qualité, DISC et ASA séparés

- [Qualité DISC](https://dashboard.disc-mali.ml/superset/dashboard/sd-qualite-disc/).
- [Qualité ASA](https://dashboard.disc-mali.ml/superset/dashboard/sd-qualite-asa/).
- [Espace supervision](https://dashboard.disc-mali.ml/superset/dashboard/sd-supervision/).

Le catalogue `sd_quality_catalog.json` décrit 31 indicateurs issus de l’analyse du
repo `config-moh-mali-chw` : compétence acceptable, disponibilité du score,
observation du patient, lavage des mains, pesée, signes de danger, température,
périmètre brachial, fréquence respiratoire, TDR, BERCER/éligibilité PF, ANJE,
suivi néonatal, registres, équipements et disponibilité d’intrants.
Les preuves de configuration, expressions et empreintes des fichiers examinés
sont dans `audit/sd-qualite-20261023/config-evidence.json`.

## Ce qui change dans la lecture de la compétence

Le formulaire calcule `applicable_score / (assessed_items × 2) × 100`, arrondi à
deux décimales. Le seuil acceptable est 80. Les éléments applicables et les versions
de formulaires peuvent changer : le score natif est conservé et les incohérences
avec ses champs de calcul sont signalées, sans réécrire les documents.

Le target CHT compte des contacts de sites visités, pas nécessairement des ASC
individuels. Son `find()` dépend de l’ordre de la liste de rapports. L’ancien SQL
peut compter un site avec au moins un score favorable parmi plusieurs visites.
Les nouveaux tableaux utilisent une règle explicite :

1. UUID de rapport unique, puis dernière visite **par site et par mois de déclaration**.
2. En cas d’égalité de date de la dernière visite, le site-mois est ambigu :
   ses réponses et son score ne sont pas classés arbitrairement.
3. Un score exploitable est numérique dans [0,100]. Les scores absents, invalides
   ou hors plage restent séparés. Un score absent ne devient pas zéro.
4. Compétence principale : derniers scores ≥80 / derniers scores exploitables.
   Disponibilité : scores exploitables / sites-mois visités.
5. Une autre ligne garde le dénominateur « tous les sites-mois visités ». Elle
   permet de lire l’effet des scores non exploitables, sans la confondre avec
   l’ancien choix de rapport du target ou le meilleur score historique.

Sur plusieurs mois, les sites se répètent : les totaux sont des **sites-mois**.
Ils ne sont pas des agents uniques et ne constituent pas un classement individuel
ni une preuve de compétence clinique au-delà des observations déclarées.

## Réponses, applicabilité et TDR

Pour les gestes et supports, les dénominateurs retiennent les réponses connues
et applicables. `not_applicable`, réponse absente et valeur inattendue sont
comptés séparément. Les mesures de gestes sont limitées aux visites déclarant une
évaluation de patient ; les mesures ANJE de procédure aux activités ANJE déclarées.
Les anciens formulaires peuvent ne pas avoir collecté un champ : cela ne signifie
pas échec ni indisponibilité.

La checklist TDR reprend les critères documentés dans la configuration :
indications, matériel assemblé, vérification de péremption, absence de péremption,
gants, information, désinfection, quantité de sang, solvant, élimination des
piquants, délai de lecture et interprétation. La valeur historique ASA « 4 » pour
le solvant est reconnue explicitement. Seules les réponses connues sont évaluées.
L’ancien agrégat ASA à cinq critères reste distinct ; il n’est pas remplacé.
Aucune règle de traitement médical ni document clinique n’est modifié.

Les réponses absentes appartiennent déjà au dénominateur des deux mesures ayant
« tous les sites-mois visités » comme base. Les colonnes ne s’additionnent donc
pas universellement ; les partitions strictes sont contrôlées pour les questions
à réponses connues/applicables et pour le score parmi les scores exploitables.

## Sources et géographie

Chaque base possède sa propre `public.mv_sd_quality_v2`. Il n’y a aucune lecture
croisée ni copie clinique ASA → DISC. Les sources sont `formview_visit_chw_site`
et le répertoire natif : portefeuille SD DISC d’un côté ; clinic/health_center/
person/hospital ASA de l’autre. L’ASA est national seulement tant que ses droits
territoriaux historiques n’ont pas de correspondance validée ; les UUID de région
absents ne sont pas inventés. Les restrictions existantes et le refus par défaut
s’appliquent aux quatre datasets, sans nouveau rôle ni utilisateur.

Les calculs lisent les rapports depuis 2019 jusqu’au début du mois courant. Ils
conservent seulement les mois réellement représentés. Au moment du premier relevé,
DISC contient des visites 2026 et ASA des visites 2019–2026. Les faibles volumes
2019/2021 restent un sujet d’audit des archives/formulaires. Une date minimale et
maximale ne certifie pas la complétude des mois intermédiaires. Les graphiques
mensuels en barres ne relient pas artificiellement les mois manquants.

Les synthèses et exports se limitent aux sites rattachés au répertoire courant
avec zone et région identifiables nativement. Le contrôle conserve aussi les
rapports hors répertoire et sans identifiant de site. Les noms actuels ne sont
pas des affectations historiques reconstituées. L’ancienne aire de santé ASA
n’est pas présentée comme un CSCOM DISC.

Les vues stockent des agrégats zone/mois et des compteurs. Aucun nom de patient,
téléphone, identifiant de bénéficiaire ou score individuel nominatif n’est ajouté
aux datasets. Tous les rapports sont conservés dans les contrôles de volume,
même si une seule visite est retenue pour les indicateurs mensuels.

Les sources de pilotage du lot 1 lisent des relevés matérialisés existants ; ces
nouveaux relevés de qualité relisent les visites natives. Leurs calculs et dates
peuvent différer. Les dates affichées sont celles de l’extraction, pas une mesure
de la dernière synchronisation des téléphones ou de la fraîcheur de bout en bout.

## Filtres et exports

DISC : dernier mois civil complet ; ASA : année 2025 par défaut. Chaque période
est modifiable dans la limite des rapports disponibles. La période et le territoire
s’appliquent aux cartes et aux résultats ; le sélecteur d’indicateur s’applique
aux graphiques et au détail territorial seulement. Le tableau des 31 indicateurs
et l’export les conservent tous. Le contrôle de période disponible ignore le
filtre de période mais suit le territoire.

L’export CSV/Excel est une ligne par grain territorial/mois avec arborescence
native, identifiants, date du calcul et, par indicateur, numérateur, dénominateur
et réponses absentes/inutilisables. Les en-têtes sont français grâce aux
`verbose_name` natifs Superset ; les codes SQL/API restent stables.
L’export complet est contrôlé sous 100 000 lignes. Il ne s’agit pas d’une liste
de bénéficiaires. Les ratios doivent être recalculés sur les sommes de leurs
numérateurs/dénominateurs, jamais moyennés entre zones.

## Calculs et exploitation

`sd_quality_sql.py` produit les SQL versionnés dans `sql/supervision/quality`.
`refresh_sd_quality.py` utilise une transaction à lecture répétable et un verrou
consultatif par base. Chaque vue est préparée, contrôlée et remplacée atomiquement.
Un échec garde le précédent relevé de cette base ; aucun objet amont n’est supprimé,
actualisé ou indexé. Les index créés sont propres aux deux nouveaux relevés.

```sh
docker exec superset_app python -u /app/superset_config/asc-v2/refresh_sd_quality.py --create
docker exec superset_app python -u /app/superset_config/asc-v2/provision_sd_quality.py
docker exec superset_app python -u /app/superset_config/asc-v2/verify_sd_quality.py
# Après inspection du brouillon :
docker exec superset_app python -u /app/superset_config/asc-v2/provision_sd_quality.py --publish
docker exec superset_app python -u /app/superset_config/asc-v2/verify_sd_quality.py --readers-only
```

`--only disc|asa` permet une reprise ciblée. Sans `--create`, un relevé existant
est reconstruit puis remplacé. Chaque requête est limitée à dix minutes et chaque
verrou à dix secondes. Le minuteur dédié `sd-quality-refresh.timer` est prévu
toutes les six heures à 02/08/14/20 h 55 UTC (Bamako), avec léger étalement.
Les deux bases conservent indépendamment leur dernier calcul complet.

`verify_sd_quality.py` teste les cas seuil 80, dernière visite moins bonne qu’une
ancienne, égalité d’horodatage, score absent, partitions et grains. Les contrôles
de construction vérifient la conservation de tous les rapports et sites-mois.
Les vérifications d’exports natifs comparent le CSV de toute la période aux sommes
SQL et l’Excel à la période par défaut, avec les en-têtes français. Les tests de
lecteur régional incluent la région interdite et les deux exports ASA vides.
Aucune ligne individuelle ni nom de personne n’est imprimé ou enregistré.

Les sources historiques restent disponibles. Pour retirer uniquement ces deux
tableaux, exécuter `provision_sd_quality.py` sans `--publish` et désactiver seulement
`sd-quality-refresh.timer`. Les vues dérivées peuvent rester pour faciliter une
reprise ; aucune restauration globale de Superset n’est nécessaire.

## Livraison vérifiée le 23 octobre 2026

Les deux tableaux sont publiés. Les deux remplacements atomiques, la conservation
des rapports et sites-mois, les partitions et les cas limites du score ont passé
les contrôles. Les quatre exports nationaux et cinq exports/tests régionaux natifs
CSV/Excel ont réussi : volume, sommes CSV et en-têtes français. Les demandes hors
région et ASA d’un lecteur territorial renvoient zéro ligne. Le refus par défaut
est vérifié sur les quatre datasets. Le minuteur est activé ; les anciens objets
cliniques et les positions des dashboards historiques ASC/SD restent inchangés.
Un export du pilotage SD antérieur a également été vérifié après traduction.
