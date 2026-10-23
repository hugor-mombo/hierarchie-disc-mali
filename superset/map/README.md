# Carte privée des sites DISC

La carte est ajoutée au [tableau de géolocalisation](https://dashboard.disc-mali.ml/superset/dashboard/sites-geolocalisation/),
avec les onglets **Carte des sites** et **Points à vérifier**. Elle utilise le
composant natif Superset `deck_scatter` : zoom, déplacement, recentrage sur les
points filtrés et fiche du site au survol, sans JavaScript personnalisé.

## Sources et contrôles

Le relevé distinct `public.mv_disc_sites_map_v1` contient seulement les derniers
points GPS exploitables de sites du répertoire courant. La règle est identique à
la synthèse : date non future, dernière visite non ambiguë, latitude/longitude
numériques dans les bornes mondiales et différentes ensemble de (0,0). Les sites
sans relevé ou avec dernier relevé invalide ne deviennent pas de faux points.

Le rafraîchissement de `refresh_geo_rank.py` prépare désormais quatre vues dans
une seule transaction. Le nombre de points doit correspondre au nombre de sites
avec coordonnées exploitables de la synthèse. Les snapshots sont remplacés
atomiquement et conservés en cas d’échec ; aucun document amont n’est modifié.
Le minuteur existant d’actualisation de six heures couvre aussi la carte.

La vue Mali retient le rectangle de contrôle latitude [10,26], longitude [-13,5].
Les autres points ont une carte mondiale et une liste exportable distinctes. Le
rectangle n’est pas un test des frontières du Mali et aucune coordonnée n’est
corrigée automatiquement. La couleur distingue les sites, pas leur performance.
Les points superposés peuvent nécessiter de zoomer.

Le dataset et les requêtes de carte utilisent l’authentification Superset et les
règles régionales/district, avant extraction des points. Les filtres du tableau
s’appliquent également. ASA n’est pas mélangé à DISC. Les coordonnées sont dans
ce relevé privé, pas dans le relevé de synthèse sans coordonnées ni dans Git.

## Fond cartographique local

Le fond est une représentation indicative des pays Natural Earth à l’échelle
1:110 millions, hébergée sur le même domaine. La provenance, l’empreinte de la
source et la transformation des propriétés sont dans `provenance.json`. Les
contours ne servent pas à décider des droits d’accès, fondés sur les UUID DISC.
Ce fond ne présente pas les routes ou les limites des districts sanitaires.

Nginx sert uniquement deux fichiers publics par routes exactes : `style-v1.json`
et `countries-v1.geojson`. Le fichier GeoJSON contient uniquement les polygones
publics des pays et leurs noms, aucun site, contact ou point clinique. Aucun jeton
Mapbox ou service tiers recevant les positions des sites n’est nécessaire.
`install_nginx.py` vérifie cette structure et préserve le proxy/TLS, avec sauvegarde
privée et restauration en cas d’échec du test ou du rechargement Nginx.

```sh
python geo_rank_sql.py
# Migration initiale : recalcul complet pour aligner carte et synthèse.
docker exec superset_app python -u /app/superset_config/asc-v2/refresh_geo_rank.py
docker exec superset_app python -u /app/superset_config/asc-v2/provision_site_map.py
```

`provision_geo_rank.py` réapplique aussi les onglets de carte après reconstruction
du tableau. Les graphiques, onglets et filtres existants sont conservés.

Références d’implémentation : [Superset 5, couche Scatter](https://github.com/apache/superset/blob/5.0.0/superset-frontend/plugins/legacy-preset-chart-deckgl/src/layers/Scatter/Scatter.tsx),
[contrôles cartographiques](https://github.com/apache/superset/blob/5.0.0/superset-frontend/plugins/legacy-preset-chart-deckgl/src/utilities/Shared_DeckGL.jsx).
