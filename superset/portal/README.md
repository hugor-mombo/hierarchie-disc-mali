# Connexion institutionnelle et consultation Superset

Compatibilité vérifiée avec Superset 5.0.0 / Flask-AppBuilder installé.
Le module est chargé par la configuration existante, sans modification de
l'image ni des sources Superset et sans assouplir le CSP ou le contrôle CSRF.

- Connexion en français, armoiries existantes du Mali, contexte santé communautaire,
  formulaire natif, messages d'erreur génériques et mise en page adaptative.
- `/` et `/superset/welcome/` redirigent les comptes connectés vers
  `/dashboard/list/` : tous les tableaux auxquels ils ont accès, au lieu des
  seuls tableaux récents de l'accueil. Aucun tableau supplémentaire n'est publié
  et aucun droit territorial n'est élargi.
- `DISC_VIEWER` remplace Gamma / Alpha / Admin / sql_lab pour les comptes de
  consultation. Les rôles de tableau et de territoire sont conservés. Filtres,
  affichage des graphiques et exports restent disponibles.
- Les permissions d'édition sont retirées du rôle et du bootstrap transmis au
  navigateur. Le gestionnaire de sécurité bloque aussi ces permissions côté
  serveur, même si Gamma ou un rôle d'auteur est ajouté par erreur à un lecteur.
  Les pages Graphiques, données et SQL / Explore ne sont pas des espaces lecteurs.
- Le compte `hmombo` reste administrateur. Aucun autre utilisateur n'est désigné.
  Le rôle `DISC_EDITOR`, sans membre à l'installation, permet à hmombo de désigner
  ensuite un concepteur de confiance. Il reprend les capacités Alpha + SQL Lab,
  donc l'édition et l'accès SQL sont sensibles. L'accès aux tableaux et les règles
  RLS existantes restent à définir selon le périmètre voulu ; le rôle ne remplace
  pas les rôles territoriaux ou nationaux. Il ne donne pas l'administration des
  utilisateurs et des rôles. Ne l'attribuer qu'à une personne autorisée à concevoir.

Les rôles standard ne sont pas modifiés, afin de résister à leur resynchronisation
par `superset init`. Référence :
https://superset.apache.org/admin-docs/security/ (rôles Gamma et personnalisation).

## Installation

1. Sauvegarder la base des métadonnées Superset et la configuration active,
   en fichiers privés sur le serveur. Ne pas copier les secrets dans Git.
2. Déployer `portal/` et les scripts `provision_portal_access.py`, `verify_portal.py`
   et `verify_portal_data.py` dans le dossier monté `asc-v2/`. Le code doit être
   lisible par l'UID 1000 du conteneur ; les sauvegardes restent privées.
3. Préparer une configuration candidate à partir de la configuration active,
   en ajoutant `config_fragment.py`. S'il existe déjà un gestionnaire de sécurité,
   un mutateur Flask ou une vue d'index, intégrer ces extensions au lieu de les
   écraser. Les chemins du fragment correspondent au montage de production.
4. Avec `SUPERSET_CONFIG_PATH` pointant sur la candidate, exécuter :

```sh
python provision_portal_access.py --backup /tmp/portal_roles_before.json
python verify_portal.py
python verify_portal_data.py
```

Conserver la sauvegarde des affectations de rôles dans les sauvegardes privées
hors du conteneur. La migration est idempotente : un second passage conserve
la sauvegarde initiale. Aucun mot de passe, tableau, filtre, SQL analytique ou
règle RLS n'est modifié. Les comptes district créés ultérieurement reprennent
le profil `DISC_VIEWER` du compte de référence.

5. Vérifier qu’aucun script de rafraîchissement n’est en cours dans le conteneur ;
   attendre sa fin avant le redémarrage. Après succès des contrôles, activer la candidate et redémarrer uniquement
   `superset_app`. Vérifier `/health`, la connexion et la liste des tableaux.

## Retour arrière

Restaurer la configuration sauvegardée, puis les affectations de rôles avec :

```sh
python provision_portal_access.py --backup /tmp/portal_roles_before.json --restore
```

Redémarrer le seul conteneur Superset. Les nouveaux rôles sans membres peuvent
rester présents ; aucune donnée métier n'est à restaurer.

## Contrôles

`verify_portal.py` teste les droits de consultation / conception, les accès
par URL et les tentatives d'écriture par API, pour les profils national,
régional, district et hmombo. Il vérifie aussi la protection CSRF et la visibilité
limitée aux tableaux autorisés. `verify_portal_data.py` vérifie un indicateur réel,
les exports CSV / XLSX et le périmètre RLS des trois profils de consultation.

Tests locaux de la politique (sans serveur ni dépendance Superset) :

```sh
python -m unittest discover -s superset/portal/tests -v
```
