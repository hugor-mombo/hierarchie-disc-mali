# Déploiement Docker local — Hiérarchies DISC-Mali / DHIS2

Prérequis : Docker Engine (ou Docker Desktop), Docker Compose **2.20 ou supérieur** et OpenSSL pour générer le secret initial.

Depuis la racine du dépôt :

```sh
sh scripts/init-local.sh
# Facultatif : renseigner les accès DISC/DHIS2 dans self-hosted/.env.
docker compose config --quiet
docker compose up -d --build --wait
docker compose exec web node scripts/create-admin.mjs administrateur
```

Ouvrir **http://localhost:5300**, se connecter avec le compte créé, puis changer son mot de passe temporaire. L'initialisation conserve tout fichier `.env` existant. Les accès sources peuvent rester vides pour démarrer ; ils sont nécessaires pour actualiser les relevés réels. Les écritures distantes sont désactivées dans la configuration initiale.

Le port 5300 est accessible uniquement depuis la machine locale. PostgreSQL reste interne au réseau Docker. Le proxy HTTPS est désactivé pour ce lancement. Les migrations sont exécutées automatiquement avant le démarrage du web et du worker.

```sh
docker compose ps
docker compose logs --tail=100 web worker migrate
# Sauvegarde du registre :
sh self-hosted/scripts/backup.sh
# Arrêt, avec conservation des données :
docker compose down
# Redémarrage après une modification du code :
docker compose up -d --build --wait
```

Les données PostgreSQL et les plans de déplacement persistent dans les volumes Docker. `docker compose down -v` les supprime. Les secrets, sauvegardes et dépendances locales sont exclus de Git.

- **`self-hosted/`** : version autonome pour Docker, PostgreSQL, authentification locale, rôles, exports et déplacements approuvés. Voir [le guide de déploiement](self-hosted/README.md).
- Les fichiers à la racine conservent la version historique Sites, son Git et ses migrations D1. Ils ne sont pas nécessaires au déploiement autonome et n’ont pas été remplacés.

Le fichier `compose.yaml` racine inclut la configuration autonome et sa variante locale. Le contexte de construction Docker est uniquement `self-hosted/`. Pour le déploiement HTTPS sur `hierarchie.disc-mali.ml`, suivre le guide distant de ce dossier.
