# Vérifications effectuées — 21 octobre 2026

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

Aucune écriture n’a été effectuée sur DISC-Mali ou DHIS2 en production. Le serveur distant et le DNS de `hierarchie.disc-mali.ml` n’ont pas été configurés. Les connecteurs d’écriture doivent encore faire l’objet d’une recette sur les versions exactes et les comptes techniques des plateformes cibles avant activation ; le mécanisme complet a été testé ici avec des sources factices.
