"""Provisionnement idempotent de la V2 ; ASC et SD restent inchangés.

Exécuter dans le conteneur Superset : python .../provision.py [--publish].
Une réexécution met à jour uniquement les objets identifiés par nos UUID fixes.
"""
import argparse
import json
from pathlib import Path
from uuid import UUID, uuid5

from superset.app import create_app
from dashboard_branding import brand_primary_dashboards

ROOT = Path(__file__).resolve().parent
NAMESPACE = UUID('57827c7a-4258-4364-bb34-42e237772808')
parser = argparse.ArgumentParser()
parser.add_argument('--publish', action='store_true')
args = parser.parse_args()


def uid(key):
    return uuid5(NAMESPACE, key)


app = create_app()
with app.test_request_context('/'):
    from flask import g
    from flask_login import login_user
    from superset import db
    from superset.connectors.sqla.models import SqlaTable, SqlMetric, TableColumn
    from superset.models.dashboard import Dashboard
    from superset.models.slice import Slice

    owner = app.appbuilder.sm.find_user(username='hmombo')
    if owner is None:
        raise RuntimeError('Administrateur hmombo introuvable')
    g.user = owner
    login_user(owner)

    def dataset(key, title, sql_file, columns, metrics):
        ds = db.session.query(SqlaTable).filter_by(uuid=uid(key)).one_or_none()
        if ds is None:
            ds = SqlaTable(uuid=uid(key), table_name=title, database_id=1, schema='public')
            db.session.add(ds)
        ds.sql = (ROOT / 'sql' / sql_file).read_text()
        ds.main_dttm_col = 'reported_month'
        ds.owners = [owner]
        ds.created_by = owner
        ds.changed_by = owner
        ds.description = 'ASC V2 — agrégats par UUID ; voir la méthode dans le tableau de bord.'
        known_columns = {c.column_name: c for c in ds.columns}
        for name, kind, label in columns:
            col = known_columns.get(name)
            if col is None:
                col = TableColumn(column_name=name)
                ds.columns.append(col)
            col.type = kind
            col.is_dttm = kind.startswith(('DATE', 'TIMESTAMP'))
            col.filterable = True
            col.groupby = True
            col.verbose_name = label
        known_metrics = {m.metric_name: m for m in ds.metrics}
        for name, label, expression in metrics:
            metric = known_metrics.get(name)
            if metric is None:
                metric = SqlMetric(metric_name=name)
                ds.metrics.append(metric)
            metric.verbose_name = label
            metric.expression = expression
            metric.description = expression
        db.session.flush()
        return ds

    sites = 'COUNT(DISTINCT site_uuid)'
    reporters = 'COUNT(DISTINCT CASE WHEN report_count > 0 THEN site_uuid END)'
    metrics = [
        ('sites', 'Sites du périmètre', sites),
        ('reporters', 'Sites avec rapport', reporters),
        ('silent', 'Sites sans rapport', f'{sites} - {reporters}'),
        ('reporting_rate', 'Taux de sites rapporteurs', f'1.0 * {reporters} / NULLIF({sites}, 0)'),
        ('reports', 'Rapports déclarés', 'SUM(report_count)'),
        ('cscom_count', 'CSCOM représentés', 'COUNT(DISTINCT health_area_uuid)'),
        ('refresh_at', 'Calcul V2 actualisé le (UTC)', 'MAX(refreshed_at)'),
    ]
    columns = [
        ('reported_month', 'DATE', 'Mois'),
        ('region', 'TEXT', 'Région'), ('district', 'TEXT', 'District · Région'),
        ('cscom', 'TEXT', 'CSCOM · District · Région'),
        ('region_uuid', 'TEXT', 'Identifiant région'),
        ('district_uuid', 'TEXT', 'Identifiant district'),
        ('health_area_uuid', 'TEXT', 'Identifiant CSCOM'),
        ('site_uuid', 'TEXT', 'Identifiant site DISC'), ('site', 'TEXT', 'Site ASC'),
        ('site_created_date', 'DATE', 'Création déclarée du site'),
        ('report_count', 'BIGINT', 'Nombre de rapports'),
        ('last_reported', 'TIMESTAMP', 'Dernier rapport déclaré'),
        ('refreshed_at', 'TIMESTAMP WITH TIME ZONE', 'Calcul V2 (UTC)'),
    ]
    ds = dataset('sites', 'ASC V2 — Sites et rapports mensuels', 'sites_monthly.sql', columns, metrics)
    quality = dataset('quality', 'ASC V2 — Qualité nationale des rapports', 'quality_monthly.sql', [
        ('region_uuid', 'TEXT', 'Périmètre national uniquement'),
        ('reported_month', 'DATE', 'Mois'), ('quality', 'TEXT', 'Catégorie'),
        ('report_count', 'BIGINT', 'Rapports'), ('last_reported', 'TIMESTAMP', 'Dernière date déclarée'),
        ('refreshed_at', 'TIMESTAMP WITH TIME ZONE', 'Calcul V2 (UTC)'),
    ], [('reports', 'Rapports', 'SUM(report_count)'),
        ('refresh_at', 'Calcul V2 actualisé le (UTC)', 'MAX(refreshed_at)')])
    from regional_security import apply_regional_security
    apply_regional_security([ds, quality])

    charts = {}

    def chart(key, title, viz, source=ds, **settings):
        obj = db.session.query(Slice).filter_by(uuid=uid('chart:' + key)).one_or_none()
        if obj is None:
            obj = Slice(uuid=uid('chart:' + key))
            db.session.add(obj)
        obj.slice_name = title
        obj.viz_type = viz
        obj.datasource_type = 'table'
        obj.datasource_id = source.id
        obj.owners = [owner]
        obj.created_by = owner
        obj.changed_by = owner
        form = dict(datasource=f'{source.id}__table', viz_type=viz,
                    granularity_sqla='reported_month', time_range='previous calendar month',
                    adhoc_filters=[], extra_form_data={}, row_limit=10000)
        form.update(settings)
        obj.params = json.dumps(form, ensure_ascii=False)
        obj.query_context = None
        db.session.flush()
        charts[key] = obj
        return obj

    for key, title, subheader, fmt in [
        ('sites', 'Sites du périmètre', 'Cohorte DISC actuelle, créés avant la fin de période', ',d'),
        ('reporters', 'Sites avec rapport', 'Au moins un rapport déclaré sur la période', ',d'),
        ('silent', 'Sites sans rapport', 'À investiguer ; ne signifie pas site fermé', ',d'),
        ('reporting_rate', 'Sites rapporteurs (%)', 'Sites avec rapport / sites du périmètre', '.1%'),
        ('reports', 'Rapports déclarés', 'Tous formulaires attribués aux sites du périmètre', ',d'),
        ('cscom_count', 'CSCOM représentés', 'Nombre de CSCOM distincts dans la sélection', ',d'),
    ]:
        chart(key, title, 'big_number_total', metric=key, subheader=subheader,
              header_font_size=0.45, subheader_font_size=0.14, y_axis_format=fmt)

    common_bar = dict(metrics=['reporting_rate'], groupby=[], annotation_layers=[],
                      show_legend=False, color_scheme='supersetColors',
                      rich_tooltip=True, y_axis_format='.0%',
                      y_axis_bounds=[0, 1], x_axis_sort_series='name',
                      x_axis_sort_series_ascending=True, truncateXAxis=False)
    chart('region_rate', 'Participation par région — période sélectionnée',
          'echarts_timeseries_bar', x_axis='region', orientation='horizontal',
          xAxisLabelRotation=0, **common_bar)
    chart('trend', 'Tendance — 12 derniers mois complets',
          'echarts_timeseries_line', x_axis='reported_month', time_grain_sqla='P1M',
          time_range='No filter',
          adhoc_filters=[dict(expressionType='SQL', clause='WHERE',
              sqlExpression="reported_month >= date_trunc('month', CURRENT_DATE) - interval '12 months' AND reported_month < date_trunc('month', CURRENT_DATE)")],
          seriesType='line', markerEnabled=True, markerSize=5,
          x_axis_time_format='%b %Y', **common_bar)

    table_base = dict(query_mode='aggregate', metrics=['sites', 'reporters', 'silent',
                      'reporting_rate', 'reports'], all_columns=[], percent_metrics=[],
                      order_desc=True, page_length=20, server_page_length=20,
                      server_pagination=True, show_cell_bars=True,
                      allow_render_html=False, table_timestamp_format='%d/%m/%Y',
                      column_config={'reporting_rate': {'d3NumberFormat': '.1%'},
                                     'sites': {'d3NumberFormat': ',d'},
                                     'reporters': {'d3NumberFormat': ',d'},
                                     'silent': {'d3NumberFormat': ',d'},
                                     'reports': {'d3NumberFormat': ',d'}})
    for key, title, groupby in [
        ('regions', 'Synthèse des régions', ['region']),
        ('districts', 'Comparaison des districts', ['district']),
        ('cscoms', 'Comparaison des CSCOM', ['cscom']),
        ('sites_detail', 'Sites à investiguer — sans rapport sur la période', ['cscom', 'site', 'site_uuid']),
    ]:
        opts = dict(table_base)
        if key == 'sites_detail':
            opts['metrics'] = ['reports']
            opts['adhoc_filters'] = [dict(expressionType='SQL', clause='HAVING',
                sqlExpression='SUM(report_count) = 0')]
        chart(key, title, 'table', groupby=groupby, **opts)

    chart('quality', 'Attribution des rapports — national, période sélectionnée', 'table',
          source=quality, query_mode='aggregate', groupby=['quality'], metrics=['reports'],
          page_length=10, row_limit=20, allow_render_html=False,
          column_config={'reports': {'d3NumberFormat': ',d'}})
    chart('refresh', 'Actualisation du calcul V2 (UTC)', 'table', source=quality,
          query_mode='aggregate', groupby=[], metrics=['refresh_at'], page_length=5,
          table_timestamp_format='%d/%m/%Y %H:%M', row_limit=1)

    dash = db.session.query(Dashboard).filter_by(uuid=uid('dashboard')).one_or_none()
    if dash is None:
        dash = Dashboard(uuid=uid('dashboard'), slug='asc-pilotage-v2')
        db.session.add(dash)
    dash.dashboard_title = 'ASC — Pilotage national · V2'
    dash.owners = [owner]
    # Même audience que le tableau ASC existant ; aucun rôle supplémentaire.
    dash.roles = list(db.session.query(Dashboard).filter_by(id=1).one().roles)
    dash.created_by = owner
    dash.changed_by = owner
    dash.published = args.publish
    dash.slices = list(charts.values())
    layout = {
        'DASHBOARD_VERSION_KEY': 'v2',
        'ROOT_ID': dict(id='ROOT_ID', type='ROOT', children=['GRID_ID']),
        'GRID_ID': dict(id='GRID_ID', type='GRID', children=['TABS-V2'], parents=['ROOT_ID']),
        'HEADER_ID': dict(id='HEADER_ID', type='HEADER', meta={'text': dash.dashboard_title}),
        'TABS-V2': dict(id='TABS-V2', type='TABS', children=[], parents=['ROOT_ID', 'GRID_ID']),
    }

    def tab(key, title):
        tid = 'TAB-' + key
        layout['TABS-V2']['children'].append(tid)
        layout[tid] = dict(id=tid, type='TAB', children=[],
                           parents=['ROOT_ID', 'GRID_ID', 'TABS-V2'], meta={'text': title})
        return tid

    def row(tid, key, items, height=45):
        rid = 'ROW-' + key
        parents = ['ROOT_ID', 'GRID_ID', 'TABS-V2', tid]
        layout[tid]['children'].append(rid)
        layout[rid] = dict(id=rid, type='ROW', children=[], parents=parents,
                           meta={'background': 'BACKGROUND_TRANSPARENT'})
        for ckey, width in items:
            obj = charts[ckey]
            cid = 'CHART-v2-' + ckey
            layout[rid]['children'].append(cid)
            layout[cid] = dict(id=cid, type='CHART', children=[], parents=parents + [rid],
                meta=dict(chartId=obj.id, sliceName=obj.slice_name, uuid=str(obj.uuid),
                          width=width, height=height))

    def note(tid, key, code, height):
        rid, mid = 'ROW-note-' + key, 'MARKDOWN-' + key
        parents = ['ROOT_ID', 'GRID_ID', 'TABS-V2', tid]
        layout[tid]['children'].append(rid)
        layout[rid] = dict(id=rid, type='ROW', children=[mid], parents=parents,
                           meta={'background': 'BACKGROUND_TRANSPARENT'})
        layout[mid] = dict(id=mid, type='MARKDOWN', children=[], parents=parents+[rid],
                           meta={'code': code, 'width': 12, 'height': height})

    overview = tab('overview', 'Vue d’ensemble')
    note(overview, 'intro', '''## Où concentrer l’accompagnement des ASC ?
Choisissez une **période**, puis une **région**, un **district** ou un **CSCOM**, et cliquez sur **Appliquer les filtres**. Par défaut : dernier mois complet, ensemble du périmètre, Bamako inclus.

Un **site rapporteur** a déclaré au moins un rapport sur la période. L’absence de rapport est un signal à investiguer, pas une preuve de fermeture. Les indicateurs comptent des **sites**, pas des personnes. Choisissez des **mois civils entiers** pour la période.

[Listes de relance ASC et enfants signalés zéro dose](/superset/dashboard/asc-suivi-operationnel/) · [Complétude des tâches et exports d’accompagnement](/superset/dashboard/asc-completude-taches/).''', 38)
    row(overview, 'numbers1', [('sites', 4), ('reporters', 4), ('silent', 4)], 22)
    row(overview, 'numbers2', [('reporting_rate', 4), ('reports', 4), ('cscom_count', 4)], 22)
    row(overview, 'region_graph', [('region_rate', 12)], 80)
    row(overview, 'trend_graph', [('trend', 12)], 46)
    note(overview, 'trend_scope', '**Lecture des graphiques :** la comparaison régionale suit la période choisie. La tendance conserve toujours les **12 derniers mois complets** ; les filtres géographiques lui sont appliqués. Un taux élevé décrit la participation au rapportage, pas la qualité des soins.', 12)
    row(overview, 'regions', [('regions', 12)], 56)

    detail = tab('territories', 'Territoires et sites à accompagner')
    note(detail, 'detail', '''## Du national au CSCOM
Les volumes et les taux utilisent le même périmètre. Comparez les taux **avec leur nombre de sites**, puis examinez les sites sans rapport. Les tableaux sont paginés ; recherchez votre territoire avec les filtres à gauche. Les homonymes sont distingués par leur branche.

Les tableaux présentent uniquement des structures et des agrégats : aucun nom de patient, téléphone ou donnée clinique individuelle.''', 20)
    row(detail, 'districts', [('districts', 12)], 60)
    row(detail, 'cscoms', [('cscoms', 12)], 64)
    row(detail, 'sites_detail', [('sites_detail', 12)], 64)

    method = tab('method', 'Qualité et méthode')
    note(method, 'method', '''## Ce que les chiffres permettent de dire
**Périmètre.** Sites du relevé analytique DISC actuel, avec contact ASC hors formation selon les règles existantes ; Bamako est inclus partout. Ce n’est pas l’inventaire de tous les sites DISC ni la liste des sites ouverts de DHIS2.

**Période.** Dates déclarées dans les rapports, et non date de transmission du téléphone. Les dates futures et les attributions contradictoires sont exclues du rapportage. Le mois en cours est incomplet. Historique disponible : 13 mois complets et mois en cours.

**Règles.** Site rapporteur = au moins un rapport attribué. Sites sans rapport = sites du périmètre − sites rapporteurs. Taux = sites rapporteurs / sites du périmètre. Sur plusieurs mois, un site est compté une seule fois et est rapporteur s’il a déclaré au moins un rapport dans la sélection ; les volumes de rapports s’additionnent.

**Attribution.** Le parent enregistré dans le rapport doit être un site du périmètre, ou le contact lui-même dans l’ancien format. Si les deux désignent des sites différents, le rapport est ambigu. Les rapports hors périmètre ou non attribués ne sont pas nécessairement erronés : ils peuvent concerner d’autres profils.

**Limites historiques.** Géographie et cohorte du relevé actuel ; les déplacements passés ne sont pas reconstitués. Un site entre dans le dénominateur à partir de son mois de création déclaré. Le statut ouvert/fermé DHIS2 et l’audit OpenFn ne sont pas encore reliés à cette V2.

**Actualisation.** Le calcul V2 est actualisé chaque heure à partir des sources analytiques disponibles. L’horodatage ci-dessous date le calcul V2, pas la dernière réplication DISC. La fraîcheur du relevé amont reste à instrumenter. Choisissez des mois civils entiers : par exemple, du 1er septembre au 1er octobre pour analyser septembre.

**Portée des contrôles ci-dessous : nationale, réservée aux profils nationaux.** Le filtre de période s’applique ; les filtres Région/District/CSCOM ne s’y appliquent pas, car les rapports non attribués n’ont pas de localisation fiable. Un profil régional ne reçoit pas ces résultats nationaux.''', 76)
    row(method, 'quality', [('quality', 8), ('refresh', 4)], 38)
    note(method, 'categories', '''**Contrôle des volumes :** la somme des catégories retrouve tous les rapports de la source sur la période. Seuls les rapports attribués sans contradiction à un site du périmètre et sans date future entrent dans les indicateurs de participation.

Le tableau [ASC historique](/superset/dashboard/1/) reste disponible pour les autres thématiques. Cette première version refond le pilotage du rapportage ; les indicateurs cliniques doivent être validés séparément avant leur intégration.''', 20)

    geographic_exclusions = [charts[k].id for k in ['quality', 'refresh']]
    filters = []
    for key, label, col, parents in [
        ('region', 'Région', 'region', []),
        ('district', 'District', 'district', ['region']),
        ('cscom', 'CSCOM', 'cscom', ['region', 'district']),
    ]:
        filters.append(dict(id='NATIVE_FILTER-v2-' + key, type='NATIVE_FILTER',
            name=label, filterType='filter_select', targets=[{'datasetId': ds.id, 'column': {'name': col}}],
            controlValues=dict(enableEmptyFilter=False, defaultToFirstItem=False,
                               multiSelect=True, searchAllOptions=True, inverseSelection=False),
            defaultDataMask={'extraFormData': {}, 'filterState': {}, 'ownState': {}},
            cascadeParentIds=['NATIVE_FILTER-v2-' + p for p in parents],
            scope={'rootPath': ['ROOT_ID'], 'excluded': geographic_exclusions},
            description='Filtre géographique ; la qualité nationale conserve sa portée nationale.'))
    filters.insert(0, dict(id='NATIVE_FILTER-v2-period', type='NATIVE_FILTER', name='Période',
        filterType='filter_time', targets=[{}], controlValues={},
        defaultDataMask={'extraFormData': {'time_range': 'previous calendar month'},
                         'filterState': {'value': 'previous calendar month'}, 'ownState': {}},
        cascadeParentIds=[], scope={'rootPath': ['ROOT_ID'], 'excluded': [charts['trend'].id]},
        description='Dernier mois complet par défaut. La tendance garde ses 12 mois complets.'))
    dash.position_json = json.dumps(layout, ensure_ascii=False)
    dash.json_metadata = json.dumps(dict(
        native_filter_configuration=filters, cross_filters_enabled=False,
        color_scheme='supersetColors', refresh_frequency=0,
        expanded_slices={}, timed_refresh_immune_slices=[],
        default_filters='{}', chart_configuration={}, label_colors={}), ensure_ascii=False)
    dash.css = '''.dashboard-content { background: #f3f6fb; }
.dashboard-component-chart-holder { border: 1px solid #e3eaf3; border-radius: 10px; }
.dashboard-markdown h2 { color: #153854; }
.dashboard-markdown { color: #334e68; }
'''
    brand_primary_dashboards(db.session)
    db.session.commit()
    print(json.dumps({'dashboard_id': dash.id, 'slug': dash.slug,
                      'datasets': [ds.id, quality.id],
                      'charts': {key: obj.id for key, obj in charts.items()},
                      'published': dash.published}, ensure_ascii=False))
