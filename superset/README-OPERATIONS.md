# Lot 2 — Suivi opérationnel et exports

Dashboard : `https://dashboard.disc-mali.ml/superset/dashboard/asc-suivi-operationnel/`.
Le tableau ASC historique reste inchangé. OpenFn n'est pas modifié.

## Règles de suivi

### Comptes ASC

Source des comptes : `couchdb_medic_users`, rôle `chw`, établissement présent
dans le périmètre courant ; comptes de formation et comptes explicitement
supprimés/désactivés exclus. Une ligne par nom de connexion ; plusieurs comptes
peuvent partager un contact. Le nombre de comptes n'est donc pas un effectif de personnes.

La dernière déclaration personnelle est `MAX(form_metadata.reported)` pour le
contact du compte, en excluant les dates futures. Le dernier rapport du site
est calculé séparément selon les deux formats d'attribution historiques.
Ni l'un ni l'autre ne prouve une synchronisation technique du téléphone.

Les seuils 7, 14 et 30 jours sont inclusifs. Le filtre Seuil est obligatoire,
avec 30 jours par défaut. Les incohérences de rattachement et les rapports
uniquement attribués au site sont distingués des relances proposées.

### Enfants signalés zéro dose

Le relevé préparé contient une seule ligne par identifiant enfant. Il combine :

- Les derniers rapports par enfant et par formulaire parmi suivi longitudinal,
  suivi vaccinal et évaluation des moins de cinq ans.
- Tous les rapports de ces formulaires du mois courant, pour ne pas perdre une
  preuve positive suivie d'une déclaration contradictoire ou incomplète.
- Les preuves Penta 1 positives de `mv_children_vaccination_history`, dont
  l'historique commence en 2024, jusqu'au dernier mois complet. Ne pas utiliser
  le cumul du mois courant : sa construction par mois peut inclure une date future.

Les contacts courants, leur âge et leur localisation sont contrôlés avant
la lecture des formulaires volumineux. Les enfants ciblés ont 12 à 59 mois
au calcul ; les dates de naissance manquantes ou invalides restent à vérifier.
Les contacts absents, décès renseignés et âges connus hors cible ne sont pas
présentés comme enfants à retrouver. Une localisation de dernier rapport
peut identifier un dossier à vérifier, sans être présentée comme localisation actuelle.

La liste par défaut nécessite une déclaration explicite Penta 1 `no` dans le
dernier rapport, aucune preuve positive retrouvée dans les sources contrôlées,
un âge cible connu et un rattachement courant non ambigu. Un état `no` ancien
recopié dans les inputs d'un rapport ne remplace pas une observation manquante :
le dossier passe dans « Information vaccinale à actualiser ».

Il s'agit de signalements à confirmer, pas d'une estimation nationale de
prévalence ni d'un constat médical. La vaccination peut avoir eu lieu sans
être saisie ou répliquée dans les sources disponibles. Référence de définition :
[OMS — indicateur zéro dose](https://www.who.int/data/gho/indicator-metadata-registry/imr-details/7792).

## Droits territoriaux

`regional_security.py` réutilise les règles RLS du jeu historique de relances
(dataset 7), avec leurs rôles, clauses et clés de groupe, sur les nouveaux jeux.
Leurs colonnes `region_uuid` gardent les UUID DISC existants. Une règle Base
refuse par défaut les résultats aux profils sans rôle territorial/national.
Les administrateurs et Alpha conservent leurs exemptions à cette règle Base.
Aucun compte ni rôle utilisateur n'est créé ou modifié.

Ces restrictions sont aussi appliquées aux datasets V2 33 et 34. Le dataset
34 reste national : `region_uuid` y est NULL, donc un profil régional ne reçoit
pas ses agrégats nationaux. L'accès au dashboard et le filtrage effectif des
données sont deux contrôles distincts.

## Installation

Copier le dossier versionné dans le montage de configuration Superset existant,
comme pour le lot 1. Aucun identifiant n'est stocké dans ce dépôt.

```sh
docker exec superset_app python /app/superset_config/asc-v2/refresh_operational.py --create
docker exec superset_app python /app/superset_config/asc-v2/provision.py --publish
docker exec superset_app python /app/superset_config/asc-v2/provision_operational.py
docker exec superset_app python /app/superset_config/asc-v2/validate_operational.py
docker exec superset_app python /app/superset_config/asc-v2/verify_regional_access.py
docker exec superset_app python /app/superset_config/asc-v2/verify_operational_exports.py
```

Vérifier le brouillon, puis publier et contrôler les exports d'un lecteur régional :

```sh
docker exec superset_app python /app/superset_config/asc-v2/provision_operational.py --publish
docker exec superset_app python /app/superset_config/asc-v2/verify_operational_exports.py --readers
sudo install -m 644 superset/systemd/asc-ops-refresh.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now asc-ops-refresh.timer
sudo systemctl start asc-ops-refresh.service
systemctl show asc-ops-refresh.service -p Result -p ExecMainStatus
```

L'initialisation valide chaque vue séparément pour permettre une reprise.
Les actualisations régulières sont atomiques, avec verrou transactionnel et
délais maximaux. La dimension géographique est actualisée de manière concurrente ;
les relevés de comptes et d'enfants sont préparés dans des vues `_next`, puis
remplacés ensemble par renommage transactionnel. Les anciens agrégats de ce lot
sont supprimés après remplacement ; aucune donnée source n'est supprimée.
Un délai de verrouillage de 10 secondes empêche une attente prolongée du remplacement.
Le calcul est horaire, à partir
des relevés analytiques disponibles : il n'actualise pas les vues amont et
ne prouve pas la fraîcheur de la réplication DISC.

`--create` ne remplace pas une définition existante. Le relevé enfants final
utilise `mv_asc_ops_children_v2`. Le premier relevé technique, non publié,
`mv_asc_ops_children`, est conservé pour retour arrière et n'est pas interrogé
par les nouveaux datasets. Toute évolution du SQL matérialisé nécessite une migration explicite.

## Exports et vérifications

Les tableaux de consultation utilisent la pagination serveur. Les tableaux
**EXPORT** utilisent une pagination d'affichage et une limite de 100 000 lignes,
pour que CSV et Excel couvrent la sélection complète. Ils n'ont pas de recherche
locale susceptible de diverger des filtres de l'export. Les contrôles bloquent
la livraison si le volume complet ne tient pas dans cette limite.

`verify_operational_exports.py` appelle l'API native Superset dans un client de
test local au serveur : CSV et XLSX sont analysés en mémoire, puis comparés aux
effectifs SQL indépendants. Aucun contenu individuel n'est imprimé ou sauvegardé.
Le test régional envoie volontairement une requête sans filtre géographique :
la limitation doit venir de la sécurité, pas de la bonne utilisation de l'interface.

`verify_regional_access.py` contrôle aussi le refus par défaut et la V2.
`validate_operational.py` vérifie l'unicité, les seuils, les dates, les dénominateurs,
les preuves positives, l'âge cible et la cohérence des totaux territoriaux.

Une sauvegarde privée des métadonnées précède ce lot :
`/opt/moh_superset/backups/avant-asc-operations-20261022.sql.gz`.
Les fichiers exportés contenant des noms ou téléphones ne doivent pas entrer dans Git.
