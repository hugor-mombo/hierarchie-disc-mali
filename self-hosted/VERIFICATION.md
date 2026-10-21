# Vérifications effectuées — 21 octobre 2026

## Déploiement sur maintenance.disc-mali.ml

- Application installée dans `/opt/maintenance-disc-mali` ; images construites sur le serveur, compilation Next.js et TypeScript réussie.
- PostgreSQL et web sains, migration terminée avec le code 0, worker démarré ; seul le web est publié sur `127.0.0.1:5300`.
- Nginx existant conservé ; certificat Let's Encrypt installé pour `maintenance.disc-mali.ml`, valable jusqu'au 19 janvier 2027 ; timer de renouvellement Certbot actif.
- Vérification depuis l'extérieur avec validation TLS : `/api/health` et `/login` répondent 200, `/api/state` sans session répond 401, HTTP redirige vers HTTPS.
- Reprise autorisée de la configuration technique et du registre : 2 comptes, 5 298 mappings et 3 enregistrements ; aucune session ni opération en attente transférée. Sauvegarde initiale conservée avec permissions 600 sur le serveur.
- Lectures authentifiées DISC et DHIS2 réussies depuis le serveur pour District Massigui. Configuration d'écriture existante reprise après vérification de l'absence d'opérations en attente ; aucune écriture de recette envoyée aux plateformes.

## Rapprochement automatique des correspondances certaines

- Tests : progression de haut en bas, noms équivalents, niveaux intermédiaires, homonymes dans des branches différentes, doublons dans une même branche, parents absents ou cycliques, identifiant embarqué, priorités manuelles et exclusions.
- Recette PostgreSQL/API/worker : correspondance automatique persistante, refus non recréé, validation manuelle explicite prioritaire ; file de synchronisation et détection des écritures ambiguës toujours vérifiées.
- Construction Docker, TypeScript, migration `003_automatic_mappings.sql` et démarrage local réussis.
- Application aux relevés existants du registre : 5 297 correspondances automatiques enregistrées ; seconde lecture sans ajout ni doublon. Aucune écriture sur les plateformes sources.

## Parcours des unités déjà présentes et boutons de création

- Détection de doublon limitée au même type structurel et même parent, ou à un identifiant DHIS2 embarqué ; message avec nom et identifiant.
- Recette navigateur isolée avec un compte éditeur : district existant affiché, mapping validé sans création, résultat concordant et lien DISC disponible.
- Unité absente : justification minimale explicitée, bouton activé après saisie, besoin de confirmation par un administrateur affiché.
- Liens vers le contact DISC pour les unités rapprochées et les opérations réussies ; URLs sans identifiants et protocoles sûrs vérifiés.

## Synchronisation bidirectionnelle et périmètre DISC

- Tests unitaires et connecteurs : groupes CSCOM/Sites ASC, conservation des autres UO, fermeture passée/future, référence DHIS2 par défaut, parents sous l'ancêtre rapproché, deux sens de synchronisation, doublons et relevés obsolètes.
- Création et renommage DISC/DHIS2 simulés avec relecture du résultat ; type CHT `contact` et `contact_type`, parent, appartenance au groupe DHIS2 et préconditions vérifiés.
- Recette PostgreSQL/API/worker isolée : authentification, droits, confirmation et plan présenté exigés ; création DISC, mapping après succès ; révocation des droits ; réponse perdue après création et interruption du worker classées `uncertain`, sans relance.
- Préparation et déplacement CHT officiels avec contact descendant et rapport fictifs revérifiés.
- Construction Docker, migration `002_sync_requests.sql` et démarrage local réussis.
- Recette navigateur sur données fictives : DHIS2 sélectionné par défaut, site fermé affiché, maternité et niveau 4 masqués puis accessibles dans la vue complète ; parent DISC de supervision proposé ; action ajoutée à la liste ; confirmation requise pour exécuter.

Les nouvelles créations et mises à jour sont testées contre des connecteurs simulés. Aucune écriture de recette n'est envoyée aux plateformes DISC-Mali et DHIS2 réelles. Les permissions et la compatibilité des versions cibles restent à vérifier avant utilisation réelle.

## Déploiement local depuis la racine du dépôt

- `npm test` et `npm run typecheck` réussis.
- `docker compose config --quiet` et `docker compose up -d --build --wait --wait-timeout 120` réussis.
- PostgreSQL et web sains ; migration `001_initial.sql` terminée avec le code 0 ; worker démarré et volume de travail accessible en écriture.
- HTTP : `/api/health` et `/login` répondent 200 ; `/api/state` sans session répond 401.
- Port web limité à `127.0.0.1:5300`, aucun proxy HTTPS actif et aucun port PostgreSQL publié.
- Initialisation de `.env` avec permissions 600 ; second lancement sans écrasement ; secrets et fichiers générés exclus de Git.
- Corrections vérifiées : images distinctes pour le web et la migration afin d'éviter un conflit de construction parallèle ; inclusion de `dotenv` dans l'image finale pour les scripts Node.

## Recettes de la version autonome déjà consignées

- 23 tests unitaires : normalisation, rapprochement, exports, mots de passe, rôles, transitions et préconditions.
- TypeScript sans erreur ; images Docker `web` et `worker` construites.
- Migrations exécutées dans PostgreSQL 17 jetable ; dump `pg_dump -Fc` relu avec `pg_restore --list`.
- Docker Compose validé avec la configuration d’exemple ; configuration Caddy validée sans publication.
- Recette API dans Docker : connexion, refus des accès anonymes, droits côté serveur, origine des requêtes, atomicité de l’import de mappings, exports protégés, révocation des sessions et changement de mot de passe obligatoire.
- Déplacement DHIS2 complet sur un serveur fictif : approbation indépendante, préparation, validation d’empreinte, exécution, relecture du parent.
- Panne simulée après une écriture DHIS2 : statut `uncertain`, exécution ultérieure refusée et nouvelle demande bloquée sur la même unité.
- Recette CHT avec le véritable préparateur `cht-conf@6.6.1` contre un CouchDB fictif : aucune écriture pendant la préparation ; déplacement du site, d’un contact descendant et d’un rapport ; vérification du nouveau lignage.
- Interface navigateur : connexion, navigation des déplacements et gestion des comptes vérifiées dans l’image Docker avec des données fictives.

Aucune écriture de recette n’a été effectuée sur DISC-Mali ou DHIS2 en production. Le mécanisme complet d'écriture a été testé avec des sources factices ; les lectures des plateformes réelles sont vérifiées sur le serveur, mais les écritures réelles n'ont pas été exécutées pendant le déploiement.

## Filtres de présence et compréhension des résultats

- Tests de régression : site identique bloqué par un parent non rapproché, absence probable dans les deux sens, parent non rapproché sans conclusion d'absence, candidat déjà lié, différence de nom entre deux fiches rapprochées.
- Suite de tests et vérification TypeScript réussies.
- Filtre de présence commun à la comparaison et aux arborescences ; candidats DISC accessibles depuis le détail DHIS2. Les créations restent soumises aux contrôles existants.
- Mise à jour distante par récupération Git de `main`, archive du sous-dossier autonome et conservation de la configuration privée et des volumes.
