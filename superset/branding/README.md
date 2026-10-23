# Identité visuelle des tableaux ASC et SD

Bandeau partagé sur les 24 tableaux ASC et SD : historiques (1 et 2), pilotage
ASC (25), suivi opérationnel, complétude, thèmes, espaces de supervision,
qualité, géolocalisation et classements. Le bandeau reste au-dessus des onglets.

Le visuel est repris **à l’identique** du fichier `branding/mali.png` de
`config-moh-mali-chw`. La provenance et l’empreinte sont dans `provenance.json`.
Il est affiché à 64 pixels, sans recoloration ni déformation, accompagné de :

- République du Mali — Santé communautaire ;
- titre du tableau ;
- repère DISC-Mali ou ASA-Mali, avec mention de l’historique pour ASA.

Le tableau historique SD et l’espace de supervision indiquent les deux sources,
car leurs graphiques utilisent les deux connexions. Les séries restent distinctes.
Le bandeau n’affirme aucune certification ni validation des résultats.

## Application et persistance

`dashboard_branding.py` ajoute une seule ligne Markdown et son CSS strictement
limité au bandeau. Il préserve les nœuds existants et vérifie l’idempotence, les
filtres, les graphiques, les rôles, propriétaires et états de publication.
Les sept scripts de provisionnement réappliquent ce bandeau avant leur commit :
il est donc conservé lorsque les tableaux sont reconstruits.

```sh
# Contrôle de structure, sans conserver les changements :
docker exec superset_app python -u /app/superset_config/asc-v2/brand_dashboards.py --dry-run
# Application ciblée pour inspecter le rendu :
docker exec superset_app python -u /app/superset_config/asc-v2/brand_dashboards.py --ids 44
# Application aux espaces ASC et SD :
docker exec superset_app python -u /app/superset_config/asc-v2/brand_dashboards.py
```

Le CSS utilise les éléments Markdown ordinaires et l’attribut `alt` de l’image.
Aucune extension des règles de rendu HTML de Superset n’est nécessaire.
Les filtres et onglets restent accessibles ; la hauteur du bandeau est de 128 px.
Le texte de contexte se réduit sur petits écrans, avec maintien de l’armoirie et
du repère de source. Les indicateurs et leurs requêtes ne sont pas modifiés.

## Image servie sur le même domaine

`install_nginx.py`, exécuté avec sudo sur le serveur existant, ajoute une seule
route exacte publique vers le PNG :
`/assets/disc-mali/armoiries-mali-87405e53.png`.
Il ne publie pas le dossier de configuration. Le fichier doit avoir l’empreinte
attendue avant installation. L’image est mise en cache un an grâce à son nom
versionné ; aucune dépendance envers un serveur d’images tiers.

L’installateur préserve le proxy et les paramètres TLS, sauvegarde le vhost avec
permissions privées, vérifie `nginx -t` et recharge Nginx. En cas d’échec, il
restaure le vhost précédent. Superset n’est pas redémarré. L’ancienne base de
métadonnées est sauvegardée séparément avant application du bandeau.

Vérifications : rendu réel dans Superset, chargement du PNG depuis le domaine
HTTPS avec contrôle SHA-256, mise en page ASC / SD / ASA, conservation des filtres
et contrôles de structure/idempotence pour tous les tableaux ciblés.
