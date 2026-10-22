# OpenFn de recette DISC-Mali

Instance dédiée : https://openfn.disc-mali.ml ; dossier `/opt/openfn-disc-mali`.
Docker Compose sépare Lightning, son PostgreSQL et son worker des autres applications.
Le port 5400 est exposé uniquement sur loopback ; nginx termine TLS et les WebSockets.
Certificat Let's Encrypt avec renouvellement automatique par le certbot du serveur.

Installation reproductible : copier ce dossier sur le serveur, générer `.env` avec
`python3 generate-env.py`, télécharger les images officielles, remplacer les références
d'image de `.env` par leurs RepoDigests, démarrer la base, exécuter
`docker compose run --rm --no-deps web /app/bin/lightning eval 'Lightning.Release.migrate()'`,
puis `docker compose up -d --wait web worker`. Exécuter `sudo sh install-nginx.sh`
uniquement lors de la première création du vhost.
Les clés sont générées sur le serveur et `.env` n'est jamais versionné.
Le worker démarre directement avec Node : le lanceur pnpm de l'image téléchargée
échoue sur des permissions de liens binaires. La commande Node utilise le même programme compilé.

Les inscriptions publiques et la télémétrie sont désactivées. Le compte administrateur
est créé explicitement. Aucun accès PostgreSQL analytique ou DHIS2 n'est configuré
dans cette instance au moment de l'installation. Aucun cron de synchronisation réel
n'est importé. L'envoi de mails nécessite encore un SMTP ; ne pas compter sur les
invitations ou la récupération par e-mail avant sa configuration.

## Connexion au registre

L'application de maintenance fournit :

- `GET /api/interop/mappings` : jeton Bearer `OPENFN_MAPPING_TOKEN`, au moins 32 caractères.
  Réponse JSON : `version`, `snapshotAt`, `effectiveDate`, `mappings`.
  Chaque ligne conserve `chw_site_id`, `dhis2_org_unit`, `active` et les chemins.
  Seuls les ASC ouverts rapprochés sont inclus. Un relevé de plus de 48 h est refusé.
  Le manifeste complet est figé dans la base lors de sa première lecture.
- `POST /api/interop/events` : autre jeton Bearer `OPENFN_AUDIT_TOKEN`.
  Accepte un événement par site/période/dataset, lié à une version connue du mapping.
  Les événements sont append-only dans l'application, dédupliqués par `eventId` ;
  une réutilisation avec un contenu différent est refusée. Une tentative ultérieure
  emploie un nouvel identifiant. La réception ne remplace jamais un événement antérieur.
- `GET /api/interop` : session utilisateur normale, lecture des 200 derniers événements,
  filtres `site` (identifiant exact DISC ou DHIS2) et `period`.

La page **Données OpenFn** expose ce suivi. `reported_success` reste un succès déclaré
par le moteur, pas une vérification indépendante des valeurs DHIS2. `test` et `live`
sont séparés. Aucun bouton de lancement réel n'est activé.

`connection-test.js` utilise l'adaptateur HTTP OpenFn et un credential privé contenant
`registryURL`, `mappingToken`, `auditToken`. Il lit les correspondances et journalise
une simulation de connexion pour un site. Il ne transmet aucun indicateur à DHIS2.
Le credential est chiffré par Lightning ; les jetons ne figurent pas dans l'expression.

## Suite de l'intégration métier

Les workflows existants restent sur leur instance actuelle tant que leur migration
n'est pas validée. Remplacer d'abord la lecture Google Sheets des **sites** par l'API,
en conservant les étapes de calcul PostgreSQL, prévalidation et upload.
Le mapping **des indicateurs/datasets/combinaisons de catégories** doit ensuite être
importé, validé et versionné dans le registre avant de supprimer cette autre dépendance
Google Sheets. Ne pas faire tourner deux moteurs en écriture sur le même périmètre.

Avant un traitement réel : accès analytique PostgreSQL de lecture, fraîcheur des vues,
mapping indicateurs, dry-run DHIS2, audit par site et reprise ciblée. Le garde-fou actuel
par mois global doit évoluer vers site/période/dataset/version. Une relecture DHIS2
sera nécessaire pour certifier les résultats des lots mixtes. L'absence de valeurs
non nulles ne signifie pas absence de rapport : la vue SQL actuelle supprime les zéros.

## Exploitation

`sh backup.sh` sauvegarde la base et la configuration privée (ne pas partager ces archives).
La clé de chiffrement de `.env` est indispensable à la restauration des credentials.
Prévoir une copie hors serveur et un test de restauration avant usage en production.
Une planification quotidienne peut appeler ce script.
`provision-test.exs` provisionne le projet, le credential et le workflow de recette
via les contextes officiels de Lightning, puis conserve leurs identifiants.
Les réexécutions retrouvent le projet par son identifiant, même après renommage. Conserver le même dossier `.env`
et les volumes lors des mises à jour ; ne jamais lancer `down -v` sur cette instance.
Les limites de mémoire et une capacité worker de 1 conviennent à la recette initiale.

## Recette du 22 octobre 2026

Lightning v2.18.0 et son worker sont épinglés par empreinte dans le générateur.
HTTPS, migration et connexion du worker vérifiés. Le workflow de connexion a terminé
avec `success` et a produit un événement `dry_run` dans le registre distant.
Aucun indicateur ni envoi DHIS2. Le déclencheur public a ensuite été désactivé.
Le projet est retrouvé par identifiant lors des mises à jour ; son nom peut être changé
dans l'interface sans casser la connexion.
La page de suivi a également été vérifiée au navigateur sur des données fictives,
avec une simulation explicitement identifiée et le filtre par site/période.

## Langue de l'interface

Vérification sur l'instance déployée : Lightning `2.18.0`,
`Gettext.known_locales(LightningWeb.Gettext)` retourne uniquement `["en"]`.
Le profil ne fournit pas de sélecteur de langue ; aucun catalogue français
n'est livré dans cette version. Modifier une variable de locale ne traduit
pas l'interface. L'application de maintenance reste en français.
