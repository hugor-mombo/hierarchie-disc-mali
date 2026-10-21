> **Déploiement Docker local** : suivre [`README-DOCKER.md`](README-DOCKER.md). Pour un serveur HTTPS, voir [`self-hosted/README.md`](self-hosted/README.md). Le texte ci-dessous décrit la version Sites historique, conservée.

# Comparateur d’unités d’organisation DISC-Mali / DHIS2

Application privée de rapprochement. Elle lit les structures dans les deux plateformes, conserve un relevé et les correspondances validées dans D1, et signale les différences de nom, niveau ou branche. Les patients, ménages, contacts personnels et rapports ne sont pas collectés.

## Utilisation

1. Cliquer sur **Charger les données réelles**. Sans relevé, l’écran présente un jeu explicitement fictif.
2. Vérifier **Configurer les niveaux** : central → 1, région → 2, district → 3, CSCOM/aire DISC → 5, site ASC → 6. Les niveaux DHIS2 4 et 5 distinguent notamment aire/CSRéf et formation sanitaire ; adapter la règle au périmètre. La supervision DISC est initialement exclue, faute d’équivalent présumé.
3. Importer les mappings existants en CSV ou JSON, ou valider les propositions individuellement. Les noms servent à rechercher ; seuls les identifiants assurent une correspondance durable. Un score est une indication de similarité, pas une probabilité.
4. Examiner les écarts de branche après validation des parents. Les niveaux intermédiaires supplémentaires sont traversés. Une unité DHIS2 non rapprochée peut être hors du périmètre DISC.
5. Exporter les mappings, les écarts ou un plan de correction des noms. Une nouvelle actualisation permet de voir les ajouts, déplacements, renommages et absences depuis le relevé précédent.

Le bouton d’actualisation déclenche une lecture complète et paginée des structures. Aucun POST, PUT ou DELETE n’est envoyé aux plateformes sources. Aucun renommage, création d’UO, modification de Google Sheets ou exécution OpenFn n’est automatique. Les plans de correction sont préparatoires. Les automatisations d’écriture devront vérifier les préconditions et les autorisations avant leur mise en place.

## Connexions et sécurité

Les domaines sources sont fixes dans `lib/sources.mjs`. Configurer côté serveur les secrets `DHIS_USER`, `DHIS_PASSWORD`, `DISC_USER`, `DISC_PASSWORD`. Ne jamais les committer. Le navigateur ne reçoit pas ces valeurs. Le site doit rester privé : l’authentification et l’accès sont assurés par Sites à l’entrée des pages et des API. Les mutations du registre refusent les requêtes intersites.

La lecture DISC est limitée aux six types structurels `c10_central` à `c60_chw_site`, avec des clés CouchDB de la forme `["c60_chw_site"]`. Un échec d’une des sources conserve le dernier relevé complet. Il ne s’agit pas d’une capture transactionnelle des deux productions : éviter les modifications simultanées durant un contrôle de référence.

## Développement

```sh
npm install
npm run dev -- --port 5180
node test/reconcile.test.mjs
npm exec tsc -- --noEmit
```

Utiliser le helper de build Sites fourni avec le plugin pour préparer le déploiement. Les migrations D1 se trouvent dans `drizzle/` et sont incluses dans l’archive de publication. Ne pas supprimer l’historique des migrations. Les données métier et les secrets locaux sont exclus du dépôt.

## Échanges de mappings

Le CSV exporté contient `discId`, `chw_site_id`, `dhis2_org_unit`, `active`, `supervisor_area_id`, `disc_contact_type`, `disc_name`. `discId` permet de réimporter tous les niveaux. Pour les workflows OpenFn existants, filtrer le type attendu et utiliser les colonnes du mapping concerné. Une ligne validée dans ce registre ne modifie pas directement les feuilles Google utilisées par les workflows.

L’import accepte aussi un tableau JSON `[{"discId":"…","dhisId":"…"}]`, ou un objet contenant `mappings`. Les lignes inactives sont ignorées ; les doublons, identifiants inconnus et conflits sont refusés. Les écritures sont effectuées par lots : en cas d’interruption, réimporter le fichier identique est possible sans dupliquer les correspondances.

Les journaux du registre conservent les 100 événements récents à l’affichage. Le plan de correction conserve jusqu’à 1 000 propositions. Les arborescences affichent au plus 250 unités par panneau pour rester lisibles ; les filtres permettent de réduire le périmètre.
