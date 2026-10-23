# Français Superset 5.0.0

Le serveur avait `BABEL_DEFAULT_LOCALE='fr'` et le choix Français, mais aucun
catalogue français compilé dans l’image exécutée. Le catalogue officiel Apache
Superset 5.0.0 est conservé dans `vendor/`, avec sa licence et son empreinte.
`build_fr.py` le compile avec Babel en MO et JSON Jed 1.x, format vérifié contre
`po2json --domain superset --format jed1.x`, utilisé par cette version Superset.

105 compléments relus couvrent menus, publication, filtres, téléchargement,
export, recherche et commandes d’édition. Ils préservent les paramètres `%s`,
`%d` et nommés. Les entrées floues/invalides ne sont pas activées arbitrairement.
Les codes SQL, paramètres d’API et valeurs techniques des périodes ne sont pas
traduits dans les calculs. L’activation compile plus de 2 600 entrées françaises ;
elle ne prétend pas traduire chaque plugin ou composant externe.

Sources officielles :
- [Catalogue français 5.0.0](https://github.com/apache/superset/blob/5.0.0/superset/translations/fr/LC_MESSAGES/messages.po).
- [Compilation frontend de cette version](https://github.com/apache/superset/blob/5.0.0/superset-frontend/scripts/po2json.sh).
- [Documentation des traductions](https://superset.apache.org/docs/contributing/howtos/).

Les fichiers compilés sont générés dans `build/fr/LC_MESSAGES`, exclus de Git.
Sur le serveur, le montage persistant en lecture seule cible exactement
`/app/superset/translations/fr`. L’image, les identifiants, ports, réseaux, rôles
et volumes existants sont conservés. `install_mount.py` ajoute uniquement ce
montage et sauvegarde le Compose original avec permissions 600. Le serveur
Gunicorn charge le code sous `/app/superset` ; les scripts exécutés par chemin
peuvent charger le wheel installé dans le venv. Le contrôle de traduction lit
le catalogue exact monté pour le serveur web et l’interface est vérifiée séparément.

```sh
# Compiler avec l’UID/GID propriétaire du dossier de configuration monté :
docker exec --user "$(id -u):$(id -g)" superset_app python /app/superset_config/asc-v2/i18n/build_fr.py
python3 /opt/moh_superset/superset_config/asc-v2/i18n/install_mount.py \
  --compose /opt/moh_superset/docker-compose.yml \
  --backup-dir /opt/moh_superset/backups
cd /opt/moh_superset
docker compose config --quiet
docker compose up -d --no-deps superset
curl --fail http://127.0.0.1:8070/health
```

Une mise à jour du catalogue déjà monté nécessite ensuite un redémarrage du
seul service Superset pour vider les caches de traduction. Attendre que les
calculs de relevés soient terminés avant une recréation du conteneur. En cas
d’échec de démarrage, remettre le Compose privé sauvegardé puis recréer le seul
service ; aucun changement de base ni migration n’est nécessaire.
Le fichier `docker-compose.locale-fr.yml` représente le même montage pour un
déploiement préférant un fichier override, avec le Compose de `/opt/moh_superset`
en premier. Ne pas additionner des montages concurrents de la même cible.

`fr-data-labels.json` complète 203 libellés métier à partir du dictionnaire du
repo de configuration et de noms explicites pour les unités territoriales,
scores, numérateurs et dénominateurs. `localize_metadata.py` met à jour uniquement
les libellés encore bruts, sans écraser les libellés personnalisés existants.
Il vérifie que SQL, identifiants, types, expressions et connexions ne changent pas.
La zone ASA n’est pas renommée CSCOM DISC. Les nouvelles sources qualité disposent
d’emblée de leurs propres libellés français complets.

```sh
docker exec superset_app python -u /app/superset_config/asc-v2/i18n/localize_metadata.py
```

Les aides des tableaux créés par le projet utilisent les mêmes commandes
françaises que l’interface. Les identifiants machine sont conservés pour
l’interopérabilité ; les utilisateurs lisent les libellés métier à l’écran et
dans les exports CSV/Excel des mesures nommées.

## Vérification de livraison

Le catalogue web français contient 2 611 entrées traduites, dont 105 compléments
relus. La première passe des libellés a changé 611 occurrences et le complément
SD 103 occurrences, soit 714, sans changement de SQL ou d’identifiant. Les six
anciennes sources SD n’ont plus de libellés de colonne bruts. `verify_labels.py`
vérifie également les en-têtes CSV français et les affectations affichées en
français dans l’export du pilotage SD existant. Les menus et commandes publiés
sont inspectés dans le navigateur ; la santé du service est contrôlée après
recréation du seul conteneur Superset.
