# Supervision dédiée — lot 1

Portail : https://dashboard.disc-mali.ml/superset/dashboard/sd-supervision/.

- DISC : `/superset/dashboard/sd-pilotage-disc/`.
- ASA : `/superset/dashboard/sd-historique-asa/`.
- L’ancien dashboard SD (id 2) et ASC (id 1) sont conservés.

## Décision de périmètre

Le déploiement DISC a été progressif en 2026 : pilote vers février, centre/sud
vers mai, nord vers juillet/août, selon les repères approximatifs donnés par le
responsable métier. Ces dates ne sont pas transformées en dates de coupure.
À sa demande, **les bases, les structures et les séries ASA/DISC restent séparées**.
Aucun UNION interbase, rapprochement de noms ou total commun n’est utilisé.

La connexion analytique id 1 est DISC-MALI, la connexion id 2 est ASA-MALI.
Les URI et les secrets restent dans la configuration existante de Superset.
Les nouveaux datasets lisent seulement les relevés matérialisés déjà présents ;
aucune table clinique, définition amont ou cadence de rafraîchissement n’est modifiée.
Une indisponibilité ASA ne remplace jamais ses résultats par ceux de DISC.

Les définitions SQL amont et les paramètres des 28 graphiques audités sont
conservés dans `audit/sd-20261023/`, sans données de résultats. Ces fichiers
sont des références en lecture seule, pas des migrations à exécuter.

## Constats de l’audit du 23 octobre 2026

L’ancien SD comprend 28 graphiques sur six datasets, dont deux ASA. Le filtre
« Zone de supervision » cible `health_area`, la même colonne que le CSCOM.
Les cartes n’ont pas de mois par défaut et additionnent donc les sites sur tous
les mois de la grille, sous un titre suggérant un effectif unique. La nouvelle
version utilise une période civile par défaut, la vraie colonne de zone et des
unités distinctes « sites » et « sites-mois ». Les taux sont calculés sur les
sommes des numérateurs et dénominateurs, jamais sur la moyenne des taux locaux.

### DISC

Source : `mv_superset_sd_chw_monthly_status`. Au moment de l’audit, janvier à
septembre 2026, avec un grain site/mois unique. Le quota est 1 visite avec ASC,
5 sans ASC, 1 entretien, au même site et au même mois. La présence d’un exemplaire
de chaque formulaire ne suffit pas. Les rapports UUID de la vue d’événements
ont été contrôlés sans doublon ; l’appariement chronologique par épisode reste
un travail du lot qualité.

**Limite majeure :** tous les sites du portefeuille courant sont recroisés avec
les mois passés, y compris avant leur déploiement. On ne présente donc pas ce
ratio comme une couverture historique du programme. Les rattachements de
superviseurs sont actuels, avec des cas `conflict` et `unassigned`. Ils restent
visibles sans attribution individuelle arbitraire. Aucun classement de performance
individuelle ne peut être justifié par cette seule grille.

La synthèse distingue sites uniques, quotas en sites-mois et volumes de rapports.
Les listes exportent une ligne site/mois avec arborescence native, rattachement,
état du quota et manques pour le minimum mensuel. Le filtre d’état du quota ne
s’applique qu’aux listes et à l’export, pour conserver les dénominateurs des cartes.
Choisir « Quota incomplet » et « Aucun des trois formulaires » pour tous les
sites-mois hors quota ; le dernier statut ne prouve pas une absence de soins.
La période et les filtres géographiques s’appliquent aux résultats, sauf la
tendance et le tableau de disponibilité qui gardent les mois préparés.

### ASA

Deux sources natives, présentées dans le même espace ASA mais sans les joindre :

1. `mv_superset_sd_monthly_supervision_2019_2025` : janvier 2019 à décembre 2025,
   grain zone/mois unique, quotas inférieurs ou égaux aux dénominateurs. L’état
   de l’intervalle ayant la plus longue intersection avec le mois détermine les
   sites actifs ; plusieurs intervalles de même état ne sont pas cumulés. Cette
   règle amont devra être réauditée au lot historique.
   Ce dénominateur diffère de celui du portefeuille actuel DISC. Les totaux
   annuels sont des sites-mois, pas des personnes distinctes. L’année 2025 est
   affichée par défaut. Le détail par site n’existe pas dans ce relevé : il n’est
   pas inventé dans le nouvel export.
2. `mv_superset_sd_monthly_indicators` : relevé FM/GAVI actuellement de novembre
   2024 à octobre 2026. Le nouvel accès exclut le mois courant incomplet. Les VAD
   curatives par site-mois utilisent `SUM(visites)/SUM(sites-mois actifs)`. Les
   TDR conformes sont définis par les anciens champs ASA, différents du champ
   `rdt_correctly_carried_out` DISC. La baisse d’activité ASA en 2026 accompagne
   la migration et ne constitue pas une mesure de la baisse des soins.

L’historique 2019/2021 contient très peu ou pas de rapports dans les relevés
existants : vérifier les archives et formulaires avant toute interprétation.
Le relevé de supervision s’arrête explicitement en 2025 : l’historique 2026 de
supervision doit être préparé au lot suivant. Les rapports bruts et les indicateurs
FM/GAVI encore présents en 2026 ne sont pas assimilés à ce relevé de supervision.

La colonne historique `health_area` correspond ici à la zone ASA : on n’affiche
pas un faux CSCOM DISC. « District déclaré ASA » conserve le nom natif, sans
certifier sa correspondance avec les districts sanitaires actuels.

## Droits et exports

L’audience des nouveaux dashboards est celle du SD existant
(`DISC_DASH_ASC_SUPERVISION`), sans nouveau rôle ni compte. Les restrictions
territoriales et le refus par défaut sont appliqués aux trois nouveaux datasets.
Les UUID de région ASA sont absents dans ces relevés. Les lecteurs régionaux
reçoivent donc **zéro ligne ASA** tant qu’un périmètre historique propre à ASA
n’a pas été validé. Les rôles ayant déjà un périmètre national et les
administrateurs conservent leur périmètre. On n’infère pas un droit sur une
ancienne région par ressemblance avec une région DISC actuelle.

Les exports CSV/Excel sont natifs Superset : menu ⋮ du tableau EXPORT, Download.
Les identifiants territoriaux natifs sont inclus. Le grain et la limite de
100 000 lignes sont contrôlés sur toute la période disponible. Les noms de
superviseurs, utiles aux listes d’action, ne sont ni imprimés dans les tests ni
sauvegardés dans Git. Aucun nom de bénéficiaire, téléphone, score individuel de
patient ou document clinique n’est ajouté aux sources du lot.

## Déploiement et contrôles

Depuis l’archive du commit validé, copier les fichiers dans le montage existant
`/opt/moh_superset/superset_config/asc-v2/`. Ce dossier serveur n’est pas un dépôt
Git. Les UUID fixes assurent un provisionnement idempotent.

```sh
docker exec superset_app python -u /app/superset_config/asc-v2/provision_sd.py
docker exec superset_app python -u /app/superset_config/asc-v2/verify_sd.py
# Après vérification du brouillon :
docker exec superset_app python -u /app/superset_config/asc-v2/provision_sd.py --publish
docker exec superset_app python -u /app/superset_config/asc-v2/verify_sd.py --readers-only
```

`verify_sd.py` contrôle source, grain, dates, quotas, plafond d’export, cible du
filtre de zone, RLS, refus par défaut, CSV/Excel natifs et conservation des sommes
additives. Les exports nationaux couvrent tous les mois, et un filtre de quota
hors quota est aussi testé. Les tests régionaux incluent un refus hors région et
les deux sources ASA vides. Les scripts n’émettent que des contrôles agrégés.
Le provisionnement vérifie que les positions, filtres, graphiques et publication
des anciens SD/ASC sont inchangés.

Sauvegarde privée des métadonnées :
`/opt/moh_superset/backups/avant-sd-lot1-20261023.sql.gz`.
Pour retirer uniquement ce lot : exécuter `provision_sd.py` sans `--publish`.
Aucune restauration globale de Superset n’est nécessaire.

## Lots suivants

| Lot | Livrable | Vérification avant publication |
|---|---|---|
| 2 — historique et opérations | ASA supervision 2026, audit des lacunes anciennes, listes de visites/entretiens et relances | Cohortes natives, déduplication, appariement des épisodes, périodes et droits ASA explicites |
| 3 — qualité et thématiques | Protocoles et observation clinique, TDR, PF, mère-enfant, communauté/TB | Dictionnaire par version de formulaire, dénominateurs et populations comparables dans chaque source |
| 4 — moyens et équipes | Intrants, matériel, supports, retours ASC, affectations | Historique des affectations et périmètres avant tout classement individuel |

Les deux séries restent séparées pour tous les lots. Toute comparaison entre
sources devra être explicitement qualifiée, avec son unité, son dénominateur et
ses limites ; aucun total ne sera produit par simple addition des bases.

## Livraison vérifiée du 23 octobre 2026

Trois dashboards publiés, trois datasets. Les contrôles de grain, quotas,
plafond d’export et source native ont réussi. Sept exports/tests nationaux et
six régionaux CSV/Excel ont passé les contrôles de volume ; les sommes additives
CSV ont été comparées aux agrégats SQL. Les demandes hors région et les deux
exports ASA d’un lecteur régional renvoient zéro ligne. Le refus par défaut est
vérifié sur les trois datasets. La période civile, les cartes DISC/ASA et la
cascade régionale DISC ont été inspectées dans le navigateur. Les mises à jour
ultérieures de mise en page sont idempotentes ; les dashboards historiques n’ont
pas été modifiés. Les tests ne certifient pas l’exhaustivité des archives amont.

## Complément : compétences et qualité

Les [31 indicateurs de compétences et qualité](README-SD-QUALITE.md), analysés à partir de `config-moh-mali-chw`, enrichissent les deux espaces natifs. Ils utilisent la dernière visite mensuelle, rendent visibles les scores non exploitables et proposent des exports français. Les anciens calculs de quota de ce premier lot restent distincts de ces nouvelles observations de qualité.
