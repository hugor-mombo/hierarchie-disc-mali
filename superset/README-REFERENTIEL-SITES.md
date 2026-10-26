# Référentiel commun des sites DISC pour ASC et SD

Le socle commun est ajouté à `asc-pilotage` et `sd-pilotage-disc` : quatre
compteurs, un onglet « Référentiel et écarts », des tableaux territoriaux et un
export CSV / XLSX par site-mois. ASA et les autres dashboards sont conservés.

## Définitions

- **Inventaire DISC** : UUID uniques du portefeuille SD courant. Un site sans
  contact ASC reste dans ce référentiel. Un site créé après la fin d'un mois
  n'entre pas dans son dénominateur. Une date de création absente reste incluse
  provisoirement et signalée. Il ne s'agit pas d'une reconstitution de sites
  ouverts ou fonctionnels à chaque date.
- **Contact ASC éligible** : appartenance à `mv_chw_site_hierarchy_reporting`,
  avec sa date de création retenue pour le mois. Cela ne certifie pas un compte
  utilisateur actif, une affectation historique ou l'ouverture dans DHIS2.
- **Rapporteur ASC** : au moins un rapport `attribue` dans cette cohorte. Les
  rapports hors cohorte ne sont pas audités par ce compteur. Les sites sans
  rapport ne sont pas automatiquement fermés ou non synchronisés.
- **Visité SD** : au moins un `visit_chw_site`, distinct du quota mensuel.
  Les mois sans relevé SD ne sont pas transformés en activité nulle.
- Les quatre compteurs dédupliquent les sites dans toute la période sélectionnée.
  L'export reste au grain UUID × mois. Les filtres de motifs ne réduisent pas les
  cartes ; période et géographie s'appliquent aux deux.

La géographie UUID et les libellés de branches sont préparés une fois par
rafraîchissement dans un relevé matérialisé commun indexé par UUID. Ils ne sont
pas recalculés sur chaque site-mois lors de chaque requête.
Les noms homonymes sont distingués. Les deux sources de pilotage existantes
reprennent ces libellés ; la source SD prend aussi en compte la création des
sites. La cohorte analytique et l'attribution des rapports ASC restent celles de
la source existante. Les quotas SD restent ceux de l'inventaire (y compris sans
contact ASC) : leur applicabilité individuelle n'est pas démontrée par ce lot.

## Diagnostic du 26 octobre 2026

Comparaison nationale pour septembre 2026 : inventaire courant **5 297**,
cohorte ASC du mois **5 161**. Les 136 écarts se décomposent en :

- 98 sites sans contact `c62_chw` rattaché dans le relevé courant ;
- 6 sites ayant uniquement des contacts dont le username contient `formation` ;
- 30 sites exclus de la cohorte ASC par les règles de nom existantes `zz` / `NE` ;
- 2 sites créés en octobre, donc postérieurs à septembre.

L'inventaire commun de septembre devient **5 295**, dont **5 161** dans la
cohorte ASC, soit **134** sites à expliquer au titre de cette cohorte. La
signification métier de `NE` n'est pas déduite du suffixe. Les exclusions sont
signalées, sans suppression de structure. Ces chiffres sont une photographie,
pas des constantes à imposer aux prochains rafraîchissements.

## Déploiement

Dans le conteneur `superset_app`, dossier `/app/superset_config/asc-v2` :

```sh
python refresh_site_registry.py
python verify_site_registry.py --analytical-only
python provision_site_registry.py
python verify_site_registry.py
```

Sauvegarder les métadonnées Superset avant le provisionnement. Le script ajoute
uniquement ses propres nœuds de mise en page et graphiques à UUID fixes ; il est
idempotent. Les identifiants des dashboards, leurs slugs, leur publication et
leurs rôles restent inchangés. Les restrictions régionales et district existantes
sont appliquées à la nouvelle source, avec refus par défaut sans périmètre.

Exécuter ce complément **après** `provision.py` / `provision_sd.py` si ces
provisionnements de base sont relancés. Le référentiel doit être installé avant
l'utilisation des nouvelles versions de `sites_monthly.sql` et `disc_sites.sql`.

Installer les unités `systemd/disc-site-registry-refresh.*` dans
`/etc/systemd/system`, puis activer le timer. L'actualisation est horaire à :20,
avec verrou, transaction cohérente, timeout et conservation du dernier relevé
validé en cas d'échec. Les sources amont ne sont pas rafraîchies par ce service.

Le registre lit les vues matérialisées existantes et fait des accès indexés UUID
sur les documents de contacts des seuls sites hors cohorte, afin de qualifier les
formations et identifiants absents. Aucun nom, username ou document de personne
n'est conservé dans le nouveau relevé. La date du portefeuille, celle du calcul
commun et celle des rapports sont exposées séparément ; elles ne prouvent pas
la fraîcheur de réplication de DISC. DHIS2 / OpenFn restent à relier explicitement.
