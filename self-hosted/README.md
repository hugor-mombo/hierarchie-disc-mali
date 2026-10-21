# Hiérarchies DISC-Mali / DHIS2 — version Docker et PostgreSQL

Application autonome Next.js/Node.js 22, PostgreSQL 17, worker de déplacements et proxy HTTPS Caddy. Le domaine prévu est **hierarchie.disc-mali.ml**. Aucun service ChatGPT/Sites n’est nécessaire pour cette version. La version Sites précédente est conservée dans le dossier parent.

## Déploiement distant

Prévoir Docker Engine et le plugin Compose v2, un serveur Linux avec 4 Go de RAM au minimum (8 Go recommandés pour de grosses branches CHT), du disque pour les sauvegardes et les documents préparés, ainsi que les ports 80/443 disponibles. PostgreSQL n’expose pas de port sur l’hôte.

1. Faire pointer les enregistrements DNS A de `hierarchie.disc-mali.ml` vers le serveur. Ne publier un AAAA que si IPv6 fonctionne aussi. Autoriser TCP 80/443 et éventuellement UDP 443. Si un proxy existe déjà, adapter le routage vers `web:3000` et ne pas lancer le proxy Caddy fourni.
2. Copier **le contenu de ce dossier `self-hosted`** sur le serveur, par exemple dans `/opt/hierarchie-disc-mali`, en excluant `node_modules`, `.next`, `.env`, `work`, `backups` et `.git`.
3. Sur le serveur :

```sh
cd /opt/hierarchie-disc-mali
cp .env.example .env
chmod 600 .env
openssl rand -hex 32
```

Renseigner `.env` dans un éditeur : le secret hexadécimal généré pour `POSTGRES_PASSWORD`, une vraie adresse `ACME_EMAIL`, et les comptes techniques DISC/DHIS2. Ne pas intégrer les identifiants dans les URL et ne pas copier les secrets de production dans un dépôt Git. Les mots de passe contenant `$`, `#`, espaces ou caractères spéciaux doivent être entourés de **guillemets simples** dans `.env` afin d’éviter l’interpolation Compose. Le mot de passe PostgreSQL doit rester hexadécimal pour être utilisable dans `DATABASE_URL`.

```sh
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 migrate web worker proxy
# Le premier compte est créé interactivement, sans mot de passe dans les arguments :
docker compose exec web node scripts/create-admin.mjs administrateur
```

La migration est un service ponctuel ; `web` et `worker` attendent sa réussite. Caddy obtient le certificat lorsque le DNS et les ports sont prêts. Ouvrir ensuite `https://hierarchie.disc-mali.ml`. Le mot de passe temporaire doit être changé à la première connexion.

Créer un second compte de validation depuis **Comptes et rôles** : une personne ne peut pas approuver sa propre demande, même administratrice. Aucun compte utilisateur n’est créé automatiquement dans DISC ou DHIS2 ; ce sont les comptes du registre.

Le domaine personnalisé n’est pas configuré par le code seul : DNS, pare-feu et lancement sur le serveur doivent être effectués sur l’infrastructure de destination.

## Rôles

| Rôle technique | Autorisations |
|---|---|
| `viewer` | Consulter les relevés, demandes, historique et exports |
| `editor` | Actualiser les relevés, gérer les mappings, proposer des déplacements et corrections de noms |
| `reviewer` | Édition et approbation/rejet des demandes et des plans d’une autre personne |
| `admin` | Administration des comptes, préparation et exécution après les approbations requises |

Les droits sont contrôlés dans les API, indépendamment de l’interface. Les mots de passe utilisent scrypt avec sel ; les sessions opaques sont stockées hachées dans PostgreSQL et expirent après huit heures. Les cookies sont HttpOnly, SameSite et Secure en HTTPS. Modifier un rôle, désactiver un utilisateur ou réinitialiser son mot de passe révoque ses sessions. Le dernier administrateur actif ne peut pas être désactivé ou rétrogradé. Les tentatives de connexion sont limitées à dix par identifiant sur quinze minutes.

## Relevés et cartographies

Cliquer sur **Actualiser les relevés**, puis vérifier **Niveaux de correspondance**. Les noms sont normalisés pour rechercher des candidats ; les identifiants validés restent la référence. Les niveaux DISC et DHIS2 ne sont pas supposés identiques. Les types de structure DISC sont `c10_central` à `c60_chw_site` ; les personnes et rapports ne sont pas collectés dans les relevés de comparaison.

L’écran **Exports** fournit les mappings CSV avec les branches, les écarts/non-rapprochés CSV, les arborescences JSON et un graphe GraphML avec les relations parents/enfants et les liens entre plateformes. GraphML peut être ouvert dans Gephi ou yEd. C’est une cartographie organisationnelle, sans coordonnées géographiques. Le CSV neutralise les formules provenant de libellés externes. Les exports du comparateur permettent aussi de télécharger le périmètre filtré.

Les corrections de noms restent des plans exportables. La fonction d’écriture intégrée concerne les **déplacements**, pas les renommages ni les créations d’UO.

## Déplacements avec application directe

Les écritures sont désactivées par défaut. Faire d’abord une recette sur des instances de test et vérifier les droits des comptes techniques. Pour autoriser les opérations réelles, configurer `ENABLE_REMOTE_WRITES=true`, puis recréer `web` et `worker` :

```sh
docker compose up -d --force-recreate web worker
```

Un déplacement concerne **une plateforme**. Pour corriger les deux côtés, créer deux demandes distinctes. Le circuit est :

1. Un éditeur ou validateur choisit unité, nouveau parent et justification. Les cycles, racines, parents identiques et types incompatibles sont refusés.
2. Un **autre** validateur ou administrateur approuve la demande.
3. Un administrateur demande la préparation. Le worker lit les données à jour, vérifie les branches puis construit un plan sans écriture distante.
4. Un autre validateur que le demandeur examine le nombre de documents/contacts/rapports et valide le plan signé par son empreinte SHA-256.
5. Un administrateur confirme une sauvegarde restaurable et une fenêtre de maintenance, puis exécute explicitement le déplacement.

Pour DISC, seuls district, aire de santé et site ASC sont proposés. Les parents correspondent à la configuration du projet Mali : district → région ; aire → district ; site ASC → zone de supervision. Un déplacement de site vers une autre aire se fait donc en choisissant une zone de supervision de cette aire. `cht-conf@6.6.1` prépare officiellement les changements de lignage des descendants et des rapports. Les règles CHT, notamment les contacts primaires et parents autorisés, sont encore contrôlées par le préparateur officiel.

Le worker prépare une seconde fois avant exécution, compare le plan approuvé, vérifie les révisions CouchDB, sauvegarde les documents originaux puis écrit par lots. Il ne modifie pas seulement le champ `parent`. Les utilisateurs hors ligne affectés doivent ensuite vider leur cache et resynchroniser selon la procédure CHT. Prévoir un volume de synchronisation important pour les grandes branches.

Pour DHIS2, les déplacements sont limités aux niveaux 3 à 6, avec un parent immédiatement supérieur : le niveau de l’UO ne change pas. Le worker revérifie le parent et `lastUpdated`, puis utilise JSON Patch avec une précondition sur le parent et relit le résultat. La compatibilité du PATCH et les droits doivent être validés sur la version DHIS2 cible avant activation en production.

Un plan expire après `PLAN_MAX_AGE_MINUTES` (60 par défaut). Une hiérarchie, un document ou un rapport changé depuis la préparation exige une nouvelle demande. Les comptes d’approbation et d’exécution doivent encore être actifs au moment du traitement. Un verrou PostgreSQL empêche deux workers ou une actualisation concurrente du registre pendant une opération.

Les écritures entre CouchDB, DHIS2 et PostgreSQL ne forment pas une transaction distribuée. Une erreur après le premier envoi ou un worker interrompu pendant l’écriture produit un état **Contrôle manuel requis** (`uncertain`). Le worker ne rejoue jamais automatiquement ce travail. Une demande sur la même unité reste bloquée jusqu’à investigation. Examiner la plateforme, les sauvegardes et l’historique ; résoudre explicitement le statut en maintenance avec un administrateur de base, en documentant le résultat. Ne pas modifier directement le statut pour forcer une nouvelle exécution.

Le volume `move_work` contient les plans complets et les copies avant écriture, qui peuvent inclure des **données de santé**. Il n’est monté que dans le worker, ses fichiers sont privés, et les API n’en exportent que les métadonnées. Réserver les accès système, chiffrer le disque et les sauvegardes selon votre politique, puis purger les dossiers après la période de contrôle retenue. Aucun effacement automatique des preuves n’est prévu.

Sources techniques : [déplacements officiels CHT](https://docs.communityhealthtoolkit.org/building/contact-management/moving-contacts/), [métadonnées DHIS2 et JSON Patch](https://docs.dhis2.org/fr/develop/using-the-api/dhis-core-version-241/metadata.html), [déploiement autonome Next.js](https://nextjs.org/docs/app/api-reference/config/next-config-js/output).

## Sauvegarde et mise à jour

```sh
./scripts/backup.sh
# Inclure les plans CHT et copies avant déplacement :
./scripts/backup.sh --with-work
```

Copier les sauvegardes hors du serveur, avec chiffrement et contrôle d’accès, et tester leur restauration. Le dump PostgreSQL sauvegarde le registre, les comptes et les sessions ; **il ne sauvegarde pas DISC/DHIS2**. Une sauvegarde de ces plateformes reste nécessaire avant déplacement.

```sh
# Mise à jour : attendre la fin des opérations actives avant d’arrêter le worker.
./scripts/backup.sh --with-work
docker compose stop web worker
docker compose build
docker compose run --rm migrate
docker compose up -d web worker proxy
```

`./scripts/restore.sh --confirm-restore backups/postgres-DATE.dump` remplace la base du registre. Ne l’utiliser qu’en maintenance ; elle ne remet pas les contacts à leur ancien emplacement sur DISC/DHIS2. Les volumes persistent lors de `docker compose down` ; ne pas employer `down -v` pour une maintenance normale. Les migrations SQL sont versionnées et doivent être conservées.

## Import du relevé de la version précédente

Les comptes et sessions Sites ne sont pas réutilisés. Depuis un export JSON de forme `{snapshot, mappings, levels}` (par exemple la réponse authentifiée `/api/state` de la version Sites), importer sur une base de registre encore vide :

```sh
docker compose cp /chemin/export.json web:/tmp/export.json
docker compose exec web node scripts/import-state.mjs /tmp/export.json
```

Le script refuse d’écraser un relevé existant et valide les identifiants, niveaux, types et doublons. Il importe uniquement les structures, les niveaux et les mappings ; aucun secret, mot de passe ou compte n’est importé. On peut aussi simplement relire les plateformes puis réimporter les mappings CSV depuis l’interface.

## Développement et recette locale

Pour lancer Docker depuis la racine du dépôt, suivre [le guide local](../README-DOCKER.md). La commande `sh scripts/init-local.sh` depuis la racine génère le secret PostgreSQL sans écraser une configuration existante.

```sh
npm ci
npm run typecheck
npm test
# Recette officielle CHT sur une source fictive locale :
node test/cht-integration.mjs
# PostgreSQL doit être disponible ; DATABASE_URL est nécessaire hors Compose.
npm run db:migrate
npm run dev -- --port 5300
```

Pour tester les images Docker localement sans certificat : configurer `.env`, puis lancer `docker compose -f compose.yaml -f compose.local.yaml up -d --build db migrate web worker`. Ouvrir `http://localhost:5300`. Cette variante n’expose le port web que sur la boucle locale et désactive le proxy TLS. Les accès en HTTP aux sources factices ne sont permis qu’avec `ALLOW_HTTP_SOURCES=true` ; garder `false` pour les plateformes réelles.
