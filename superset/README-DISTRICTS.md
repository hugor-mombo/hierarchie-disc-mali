# Comptes district Superset

Les comptes suivent la convention des lecteurs régionaux `reg_<nom>` :
`dist_<nom>`, minuscules sans accents, avec suffixe région puis identifiant court
si nécessaire pour distinguer les homonymes. Les UUID natifs, et jamais les noms,
définissent le périmètre d’accès.

Le répertoire `contactview_metadata` fournit les contacts `c30_district` rattachés
à une région `c20_region`. Le relevé initial comprend 172 districts dans 20 régions,
dont 15 sans site ASC dans le portefeuille courant. Ceux-ci ont un compte valide
mais ne reçoivent pas de faux indicateurs. Un district sans données peut être
alimenté ultérieurement sans élargir son rôle.

## Profil et restrictions

Le profil reprend celui de `reg_bougouni` : Gamma, DISC_DASH_ASC_ACTIVITY,
DISC_DASH_ASC_SUPERVISION et DISC_DASH_SEBAC. Il remplace le rôle régional par un
rôle `DISC_DISTRICT_<nom>`, sans permission globale. Aucun rôle Admin, Alpha,
DISC_NATIONAL ou DISC_REGION n’est affecté aux nouveaux comptes.

Une règle régulière par district impose :

```sql
district_uuid = '<UUID district DISC>' AND region_uuid = '<UUID région DISC>'
```

Elle est appliquée à tous les datasets DISC possédant ces deux clés. Les autres
datasets sont refusés explicitement aux rôles district par la règle
`DISC_RLS_DISTRICT_UNSUPPORTED` (`1 = 0`) : cela inclut les agrégats nationaux ou
régionaux sans clé district et tous les datasets ASA. Les périmètres historiques
ASA ne sont pas attribués en rapprochant simplement les noms des districts.
Certains graphiques historiques peuvent donc rester vides pour ces comptes.

Le refus par défaut des sources dérivées reste en place ; seuls les nouveaux rôles
scopés sont ajoutés à ses exceptions. Leurs restrictions district régulières
continuent de s’appliquer. Les comptes et règles régionaux existants sont
préservés. `regional_security.py` réapplique aussi les règles district et les
refus sur les futurs datasets créés par les scripts de provisionnement.

## Création, vérification et fichier de remise

`provision_district_accounts.py` contrôle les noms, collisions, UUID, droits du
profil de référence et rôles existants avant création. Il ne réinitialise aucun
compte extérieur au manifeste. Chaque nouveau mot de passe est aléatoire, unique
et long de 20 caractères. Une reprise avec le même manifeste conserve ces mots
de passe. Les comptes sont désactivés après création, puis activés seulement
après validation des périmètres et des empreintes par le vérificateur.

Le manifeste de récupération contient des secrets : chemin privé, dossier 700,
fichier 600, jamais dans Git, dans les fichiers cartographiques publics ou dans
les journaux. Ne pas modifier le manifeste entre création et vérification.

```sh
docker exec superset_app python -u /app/superset_config/asc-v2/provision_district_accounts.py --state /tmp/disc-district-accounts-20261023/credentials.json --dry-run
docker exec superset_app python -u /app/superset_config/asc-v2/provision_district_accounts.py --state /tmp/disc-district-accounts-20261023/credentials.json
docker exec superset_app python -u /app/superset_config/asc-v2/verify_district_accounts.py --state /tmp/disc-district-accounts-20261023/credentials.json
```

Le vérificateur contrôle tous les comptes : profil exact, mot de passe haché,
clause RLS effective, couverture des datasets et effectif du territoire. Il teste
ensuite des connexions réelles, les lectures de carte, les CSV, la tentative de
lecture d’un autre district de la même région, les refus ASA/agrégats nationaux
et le refus d’exécuter du SQL. Un échec de cette phase désactive les comptes du
manifeste ; il n’affecte pas les lecteurs régionaux.

Le fichier Excel de remise est créé localement à partir du manifeste validé. Il
contient région, district, compte, URL, état, nombre de sites et identifiant du
périmètre RLS. Les mots de passe n’y sont ajoutés qu’après autorisation explicite
de leur transfert vers le poste et le fichier de remise. Les secrets ne sont pas inclus dans les aperçus de contrôle ou le dépôt.
Le fichier est destiné à l’administrateur pour distribuer les accès concernés.
