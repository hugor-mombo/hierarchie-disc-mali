# Hiérarchies DISC-Mali / DHIS2 — version Docker et PostgreSQL

Application autonome Next.js/Node.js 22, PostgreSQL 17, worker de déplacements et proxy HTTPS Caddy. Le domaine prévu est **maintenance.disc-mali.ml**. Aucun service ChatGPT/Sites n’est nécessaire pour cette version. La version Sites précédente est conservée dans le dossier parent.

## Déploiement distant

Prévoir Docker Engine et le plugin Compose v2, un serveur Linux avec 4 Go de RAM au minimum (8 Go recommandés pour de grosses branches CHT), du disque pour les sauvegardes et les documents préparés, ainsi que les ports 80/443 disponibles. PostgreSQL n’expose pas de port sur l’hôte.

1. Faire pointer les enregistrements DNS A de `maintenance.disc-mali.ml` vers le serveur. Ne publier un AAAA que si IPv6 fonctionne aussi. Autoriser TCP 80/443 et éventuellement UDP 443. Si un proxy existe déjà, adapter le routage vers `web:3000` et ne pas lancer le proxy Caddy fourni.
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

La migration est un service ponctuel ; `web` et `worker` attendent sa réussite. Caddy obtient le certificat lorsque le DNS et les ports sont prêts. Ouvrir ensuite `https://maintenance.disc-mali.ml`. Le mot de passe temporaire doit être changé à la première connexion.

Créer un second compte de validation depuis **Comptes et rôles** : une personne ne peut pas approuver sa propre demande, même administratrice. Aucun compte utilisateur n’est créé automatiquement dans DISC ou DHIS2 ; ce sont les comptes du registre.

Le domaine personnalisé n’est pas configuré par le code seul : DNS, pare-feu et lancement sur le serveur doivent être effectués sur l’infrastructure de destination.

## Serveur avec Nginx existant

Pour `maintenance.disc-mali.ml`, l'application est installée dans `/opt/maintenance-disc-mali`. Le web n'écoute que sur `127.0.0.1:5300` ; Nginx termine HTTPS. PostgreSQL reste interne à Docker.

Dans `.env`, définir `SITE_DOMAIN=maintenance.disc-mali.ml`, `APP_URL=https://maintenance.disc-mali.ml` et `COMPOSE_FILE=compose.yaml:compose.nginx.yaml`. Conserver ce fichier privé avec les permissions 600. Puis :

```sh
docker compose up -d --build --wait
sudo sh deploy/install-nginx.sh maintenance.disc-mali.ml
```

Le script ajoute uniquement le vhost de ce domaine, valide Nginx puis utilise le plugin Nginx de Certbot pour obtenir et installer le certificat Let's Encrypt. Il conserve les vhosts existants et refuse d'écraser une configuration de ce domaine qu'il ne gère pas. Le renouvellement est assuré par le service Certbot du serveur. Le proxy Caddy du Compose reste désactivé dans cette variante.

Les comptes, relevés et mappings peuvent être repris par restauration d'un dump PostgreSQL sur une base vide. Exclure `app_sessions` et `login_attempts` lors de ce transfert. Le registre du serveur devient une base indépendante : ses mises à jour ne sont pas répliquées dans le registre local de développement.

## Rôles

| Rôle technique | Autorisations |
|---|---|
| `viewer` | Consulter les relevés, demandes, historique et exports |
| `editor` | Actualiser les relevés, gérer les mappings, proposer des déplacements et corrections de noms |
| `reviewer` | Édition et approbation/rejet des demandes et des plans d’une autre personne |
| `admin` | Administration des comptes, confirmation et exécution de la liste de synchronisation, déplacements avec approbation indépendante |

Les droits sont contrôlés dans les API, indépendamment de l’interface. Les mots de passe utilisent scrypt avec sel ; les sessions opaques sont stockées hachées dans PostgreSQL et expirent après huit heures. Les cookies sont HttpOnly, SameSite et Secure en HTTPS. Modifier un rôle, désactiver un utilisateur ou réinitialiser son mot de passe révoque ses sessions. Le dernier administrateur actif ne peut pas être désactivé ou rétrogradé. Les tentatives de connexion sont limitées à dix par identifiant sur quinze minutes.

## Relevés et cartographies

Cliquer sur **Actualiser les relevés**, puis vérifier **Niveaux de correspondance**. Les noms sont normalisés pour reconnaître automatiquement les correspondances certaines et rechercher des candidats pour les autres ; les identifiants enregistrés restent la référence. Les niveaux DISC et DHIS2 ne sont pas supposés identiques. Les types de structure DISC sont `c10_central` à `c60_chw_site` ; les personnes et rapports ne sont pas collectés dans les relevés de comparaison.

L’écran **Exports** fournit les mappings CSV avec les branches, les écarts/non-rapprochés CSV, les arborescences JSON et un graphe GraphML avec les relations parents/enfants et les liens entre plateformes. GraphML peut être ouvert dans Gephi ou yEd. C’est une cartographie organisationnelle, sans coordonnées géographiques. Le CSV neutralise les formules provenant de libellés externes. Les exports du comparateur permettent aussi de télécharger le périmètre filtré.

Les corrections de noms peuvent rester des plans exportables ou être appliquées par la liste de synchronisation. Cette liste permet aussi les créations de structures et les déplacements, avec une cible explicite et une confirmation.

## Rapprochement automatique

Les correspondances certaines sont enregistrées automatiquement dans le registre, dès la lecture des relevés existants et après chaque actualisation. Le moteur avance de haut en bas : nom équivalent après normalisation, niveau configuré, parent comparable déjà rapproché et correspondance **unique dans les deux sens**. Les niveaux intermédiaires DHIS2 et les zones de supervision DISC non comparés sont traversés. Un identifiant DHIS2 déjà présent sur un document DISC peut aussi établir une correspondance si le niveau et la branche concordent.

Les variantes de casse, accents, apostrophes et préfixes usuels n'imposent pas de validation manuelle. Les homonymes dans une même branche, parents non reconnus, différences de niveau, similitudes approximatives et unités absentes restent à examiner. La vue par défaut conserve les filtres des groupes CSCOM et Sites ASC.

Les correspondances automatiques sont utilisées par les exports et la synchronisation comme les correspondances manuelles. Leur origine est affichée dans le détail et le nombre de correspondances automatiques est visible dans le comparateur. Les identifiants enregistrés restent stables : une évolution ultérieure du nom ou du parent apparaît comme un écart, sans réaffectation silencieuse.

Une correspondance peut être refusée dans son détail. Ce refus empêche son rétablissement automatique ; une validation manuelle explicite peut ensuite lever l'exclusion. Les décisions manuelles sont prioritaires. Le rapprochement automatique n'écrit aucune donnée dans DISC ou DHIS2 : les modifications des plateformes restent soumises à la file et à la confirmation d'exécution.

## Référence et synchronisation bidirectionnelle

**DHIS2 est le référentiel par défaut.** Le choix dans le comparateur est enregistré pour le registre. Chaque action conserve sa propre référence : DHIS2 → DISC-Mali, ou DISC-Mali → DHIS2 lorsque DISC dispose de données plus récentes. Changer la référence ne lance aucune écriture.

La vue DISC n'affiche par défaut que les niveaux DHIS2 1 à 3, les CSCOM de niveau 5 du groupe `a8PnG1kmKY9` et les Sites ASC de niveau 6 du groupe `JBThfLOBPmn`. Les maternités rurales et les autres formations sanitaires restent dans le relevé complet. **Afficher toute l’arborescence DHIS2** permet de les explorer ; les listes de parents utilisent le relevé complet. Les membres des deux groupes sont lus via `/api/29/organisationUnitGroups/{id}`. Un groupe inaccessible ou une réponse incomplète fait échouer l'actualisation sans remplacer le relevé précédent.

Le statut DHIS2 d'un site est calculé depuis `closedDate` : ouvert si aucune date n'est définie, fermé à partir de cette date, ou fermeture prévue. Un ancien relevé sans ce champ affiche « Statut non relevé » et doit être actualisé. Le statut est informatif ; aucune fermeture ou réouverture DISC n'est déduite automatiquement.

Depuis le détail d'une unité ou **Synchronisation → Ajouter une opération** :

1. Choisir la référence et l'opération : création, mise à jour du nom ou déplacement.
2. Pour modifier une unité existante, valider préalablement son mapping. Pour créer une unité, vérifier qu'aucune correspondance ou structure similaire n'existe déjà.
Si la création est bloquée par une unité existante, le détail affiche son nom, son chemin et son identifiant. **Ouvrir dans DISC-Mali** permet de vérifier le contact ; **Rapprocher cette unité existante** valide le mapping sans créer de doublon. « DHIS2 non rapproché » indique une absence de mapping, pas une absence du contact sur DISC.

3. Choisir un parent compatible dans la branche d'un ancêtre rapproché. Les niveaux intermédiaires restent pris en compte : un Site ASC DISC doit être placé sous une **zone de supervision de l'aire correspondante**, pas directement sous le CSCOM DHIS2. S'il manque un parent ou un mapping, préparer d'abord celui-ci, attendre sa réalisation, puis actualiser les relevés.
4. Ajouter l'action à la liste avec une justification. Les éditeurs et validateurs peuvent préparer des actions ; seul un administrateur peut confirmer leur exécution avec le droit `execute`.
5. Vérifier la cible, les chemins avant/après et confirmer l'opération, la sauvegarde et la disponibilité de la plateforme. **Appliquer maintenant** confirme et met directement l'action en file. On peut aussi sélectionner jusqu'à 100 actions préparées et confirmer leur exécution ensemble.

Le worker traite chaque action en arrière-plan, sous le même verrou que les déplacements et actualisations existants. Il revérifie les droits de l'exécutant, les URL, la référence, les mappings et les parents avant écriture. Un changement de relevé exige une nouvelle préparation. Le succès d'une création ajoute le mapping uniquement après relecture de l'unité créée. Le résultat apparaît dans la liste et l'historique ; les relevés sont ensuite actualisés. Une création DISC réussie affiche **Voir le contact dans DISC-Mali** avec son identifiant vérifié.

Les créations DISC utilisent l'API CHT `/api/v1/places` avec `type=contact`, le `contact_type` structurel et le parent choisi ; CHT construit le lignage. Aucune personne ASC ni aucun compte utilisateur n'est inventé : compléter le contact primaire selon le processus DISC. Les créations DHIS2 ajoutent le CSCOM ou Site ASC au groupe correspondant. Les renommages DHIS2 mettent à jour le nom et le nom court. Les déplacements DISC réutilisent la préparation officielle `cht-conf` et les sauvegardes des descendants et rapports.

Cette voie de confirmation directe par un administrateur complète le circuit à approbation indépendante présenté ci-dessous. Elle ne nécessite pas un second compte. `ENABLE_REMOTE_WRITES=true` reste requis dans le web **et** le worker pour toute écriture réelle. Les comptes techniques doivent disposer des droits de création, modification et gestion des groupes nécessaires ; tester la compatibilité des API CHT et DHIS2 sur les versions cibles avant leur utilisation réelle.

Une réponse ambiguë après le début des écritures ou un redémarrage du worker pendant une action donne le statut **Contrôle manuel requis**. Aucun nouvel essai n'est automatique et une autre action sur la même unité est bloquée. Examiner la plateforme, l'historique et les fichiers privés du volume `move_work` avant de résoudre cet état en maintenance. Les données métier et preuves restent soumises aux mêmes règles de sauvegarde que les déplacements.

## Déplacements avec approbation indépendante

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

La recette de synchronisation utilise une base PostgreSQL distincte et des connecteurs simulés. Depuis la racine du dépôt, après construction des images :

```sh
docker compose -f self-hosted/compose.qa.yaml up -d --wait
docker compose -f self-hosted/compose.qa.yaml run --rm runner
# Supprimer uniquement cette stack de recette et ses volumes fictifs :
docker compose -f self-hosted/compose.qa.yaml down -v
```

Aucun worker autonome n'est lancé dans cette stack : le script de recette appelle le traitement des actions avec des plateformes fictives. Elle n'utilise pas `self-hosted/.env` et ne doit recevoir aucun identifiant de production.

Pour tester les images Docker localement sans certificat : configurer `.env`, puis lancer `docker compose -f compose.yaml -f compose.local.yaml up -d --build db migrate web worker`. Ouvrir `http://localhost:5300`. Cette variante n’expose le port web que sur la boucle locale et désactive le proxy TLS. Les accès en HTTP aux sources factices ne sont permis qu’avec `ALLOW_HTTP_SOURCES=true` ; garder `false` pour les plateformes réelles.

## Lecture de la présence et mise à jour depuis Git

Le filtre **Présence par rapport à la référence** est commun à la comparaison et aux arborescences. Choisir la référence, puis le niveau et la région :

- **Présentes dans les deux plateformes** : fiches liées ; consulter ensuite les écarts de nom, niveau ou branche.
- **Référence sans lien dans la cible** : liste de travail complète des unités non rapprochées de la référence.
- **Correspondance à vérifier** : candidats existants ; examiner leurs parents avant de créer.
- **Absence probable** : aucun candidat au niveau configuré, parent rapproché. Le relevé peut être ancien ou incomplet : vérifier avant création.
- **Parent ou périmètre à vérifier** : les informations ne permettent pas de conclure.

Aucune absence n'est certifiée automatiquement. Le détail d'une unité DHIS2 propose d'examiner les contacts DISC candidats, y compris ceux déjà liés à une autre unité. Rapprocher ne modifie aucune plateforme ; synchroniser demande une confirmation.

Sur le serveur, les mises à jour utilisent le dépôt Git public, sans clé GitHub privée. Le dépôt de déploiement est conservé dans `.deploy-repository.git` ; une archive du sous-dossier `self-hosted` est extraite dans l'installation existante. `.env`, PostgreSQL et les sauvegardes sont conservés. Après commit et push sur `main` :

```sh
sh /opt/maintenance-disc-mali/deploy/update-from-git.sh /opt/maintenance-disc-mali main
```

Il est possible de remplacer `main` par le SHA attendu : le script refuse alors de déployer si la tête distante ne correspond pas. Les images sont construites avant le remplacement des services. La version est enregistrée dans `DEPLOYED_REVISION` uniquement après réussite des contrôles.
