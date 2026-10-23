"""Native Superset site maps; clinical coordinates only come from authenticated RLS queries."""
import json
from geo_rank_sql import uid
from regional_security import apply_regional_security
from dashboard_branding import brand_dashboard
TABLE='mv_disc_sites_map_v1'
STYLE='/assets/disc-mali/map/style-v1.json'

def provision_site_map(session):
 from superset import security_manager as sm
 from superset.models.dashboard import Dashboard
 from superset.models.slice import Slice
 from superset.connectors.sqla.models import SqlaTable,TableColumn,SqlMetric
 owner=sm.find_user(username='hmombo');assert owner
 dashboard=session.query(Dashboard).filter_by(uuid=uid('dashboard:geo')).one_or_none()
 if dashboard is None:return None
 before=(dashboard.json_metadata,sorted(s.id for s in dashboard.slices),dashboard.published,sorted(r.id for r in dashboard.roles))
 ds=session.query(SqlaTable).filter_by(uuid=uid('dataset:map')).one_or_none()
 if ds is None:ds=SqlaTable(uuid=uid('dataset:map'),database_id=1,schema='public',table_name='DISC — Carte privée des sites géolocalisés');session.add(ds)
 assert ds.database_id==1
 ds.sql="SELECT *,concat_ws(' · ',site_name,cscom_name,district_name,region) AS site_label FROM public."+TABLE
 ds.main_dttm_col='reported_month';ds.owners=[owner];ds.created_by=ds.changed_by=owner
 ds.description='Coordonnées de la dernière géolocalisation exploitable par site DISC. Accès authentifié et restrictions régionales/district. Aucun point de site dans les fichiers publics du fond de carte.'
 reference=session.query(SqlaTable).filter_by(uuid=uid('dataset:geo')).one()
 columns=[(c.column_name,c.type,c.verbose_name) for c in reference.columns]+[('latitude','NUMERIC','Latitude'),('longitude','NUMERIC','Longitude'),('site_label','TEXT','Site et rattachement')]
 for name,kind,label in columns:
  col=next((c for c in ds.columns if c.column_name==name),None)
  if col is None:col=TableColumn(column_name=name);ds.columns.append(col)
  col.type=kind;col.verbose_name=label;col.is_dttm=kind.startswith(('DATE','TIMESTAMP'));col.groupby=col.filterable=True
 metrics=[('sites','Sites géolocalisés','COUNT(*)'),('in_area','Points dans le rectangle de contrôle Mali','COUNT(*) FILTER(WHERE outside_envelope=0)'),('outside','Points hors rectangle de contrôle Mali','SUM(outside_envelope)'),('fresh','Calcul du relevé (UTC)','MAX(calculated_at)')]
 for name,label,expression in metrics:
  metric=next((m for m in ds.metrics if m.metric_name==name),None)
  if metric is None:metric=SqlMetric(metric_name=name);ds.metrics.append(metric)
  metric.verbose_name=label;metric.expression=expression
 session.flush();apply_regional_security([ds])
 charts={}
 def chart(key,title,viz,**settings):
  c=session.query(Slice).filter_by(uuid=uid('chart:geo:'+key)).one_or_none()
  if c is None:c=Slice(uuid=uid('chart:geo:'+key));session.add(c)
  c.slice_name=title;c.viz_type=viz;c.datasource_type='table';c.datasource_id=ds.id;c.owners=[owner];c.created_by=c.changed_by=owner
  params=dict(datasource=f'{ds.id}__table',viz_type=viz,time_range='No filter',granularity_sqla=None,adhoc_filters=[],extra_form_data={},row_limit=100000)
  params.update(settings);c.params=json.dumps(params,ensure_ascii=False);c.query_context=None;session.flush();charts[key]=c;return c
 map_config=dict(spatial=dict(type='latlong',latCol='latitude',lonCol='longitude',reverseCheckbox=False),dimension='site_label',
  mapbox_style=STYLE,autozoom=True,viewport=dict(longitude=-4.0,latitude=17.0,zoom=4.7,pitch=0,bearing=0),
  point_radius_fixed=dict(type='fix',value=200),point_unit='radius_m',min_radius=3,max_radius=7,multiplier=1,
  color_picker=dict(r=24,g=121,b=125,a=.85),color_scheme='supersetColors',legend_position=None,legend_format=None,
  filter_nulls=True,js_columns=['site_uuid','site_name','region','district_name','cscom_name','last_report'],
  js_tooltip='',js_data_mutator='',js_onclick_href='',time_grain_sqla=None)
 for key,title,where in [('map','Carte — Sites géolocalisés, vue Mali','outside_envelope=0'),('map_external','Carte — Points hors rectangle de contrôle, à vérifier','outside_envelope=1')]:
  chart(key,title,'deck_scatter',**map_config,adhoc_filters=[dict(expressionType='SQL',clause='WHERE',sqlExpression=where)])
 for key,title,metric in [('map_count','Sites affichés sur la vue Mali','in_area'),('map_outside_count','Points hors rectangle à vérifier','outside')]:
  chart(key,title,'big_number_total',metric=metric,header_font_size=.4,subheader_font_size=.13,y_axis_format=',d')
 chart('map_outside_list','EXPORT — Points hors rectangle de contrôle', 'table',query_mode='aggregate',all_columns=[],
  groupby=['site_name','site_uuid','region','district','cscom','zone','latitude','longitude','last_report'],metrics=[],
  adhoc_filters=[dict(expressionType='SQL',clause='WHERE',sqlExpression='outside_envelope=1')],
  server_pagination=False,page_length=20,include_search=True,allow_render_html=False,table_timestamp_format='%d/%m/%Y',
  column_config={k:{'d3NumberFormat':'.6f'} for k in ['latitude','longitude']})
 layout=json.loads(dashboard.position_json);tabs=layout['TABS-THEME'];parents=['ROOT_ID','GRID_ID','TABS-THEME']
 newtabs=['TAB-geo-map','TAB-geo-map-check']
 tabs['children']=[t for t in tabs['children'] if t not in newtabs]
 tabs['children'][1:1]=newtabs
 for tid,title in zip(newtabs,['Carte des sites','Points à vérifier']):
  layout[tid]=dict(id=tid,type='TAB',parents=parents,children=[],meta={'text':title})
 def row(tid,key,items,height):
  rid=tid+'-ROW-'+key;ps=parents+[tid];layout[tid]['children'].append(rid)
  layout[rid]=dict(id=rid,type='ROW',children=[],parents=ps,meta={'background':'BACKGROUND_TRANSPARENT'})
  for chart_key,width in items:
   c=charts[chart_key];cid=tid+'-CHART-'+chart_key;layout[rid]['children'].append(cid)
   layout[cid]=dict(id=cid,type='CHART',children=[],parents=ps+[rid],meta=dict(chartId=c.id,sliceName=c.slice_name,uuid=str(c.uuid),width=width,height=height))
 def note(tid,key,code,height):
  rid=tid+'-NOTE-'+key;mid=rid+'-MARKDOWN';ps=parents+[tid];layout[tid]['children'].append(rid)
  layout[rid]=dict(id=rid,type='ROW',children=[mid],parents=ps,meta={'background':'BACKGROUND_TRANSPARENT'})
  layout[mid]=dict(id=mid,type='MARKDOWN',children=[],parents=ps+[rid],meta={'code':code,'width':12,'height':height})
 tid=newtabs[0]
 note(tid,'how','''## Localiser les sites géolocalisés
Zoomez avec la molette et déplacez la carte. **Survolez un point** pour retrouver le site et son rattachement. Les filtres territoriaux et vos droits s’appliquent à la carte, qui se recentre sur les sites visibles.
Cette vue retient les relevés exploitables du rectangle de contrôle Mali ; les autres figurent dans **Points à vérifier**. Le fond est indicatif, sans validation de la position réelle. Les couleurs distinguent les points, sans score de performance.''',24)
 row(tid,'counts',[('map_count',6),('map_outside_count',6)],20)
 row(tid,'map',[('map',12)],95)
 tid=newtabs[1]
 note(tid,'how','''## Vérifier les coordonnées atypiques
Ces relevés sont numériques et dans les bornes mondiales, mais hors du rectangle de contrôle Mali. Ils ne sont pas corrigés automatiquement. Survolez les points pour retrouver les sites et utilisez la liste exportable avec l’arborescence et la date du dernier relevé.
L’absence de relevé GPS, une coordonnée invalide et une dernière date ambiguë restent dans les listes de la synthèse ; ils ne deviennent pas de faux points sur la carte. Le contrôle ne certifie pas qu’un site est hors du Mali.''',28)
 row(tid,'map',[('map_external',12)],80);row(tid,'list',[('map_outside_list',12)],65)
 dashboard.position_json=json.dumps(layout,ensure_ascii=False)
 chart_ids={c.id for c in charts.values()};dashboard.slices=[c for c in dashboard.slices if c.id not in chart_ids]+list(charts.values())
 assert dashboard.json_metadata==before[0] and dashboard.published==before[2] and sorted(r.id for r in dashboard.roles)==before[3]
 assert set(before[1]).issubset({c.id for c in dashboard.slices})
 css='/* DISC site map tooltip */\n.deckgl-tooltip{max-width:420px;white-space:normal;overflow-wrap:anywhere}\n'
 if '/* DISC site map tooltip */' not in (dashboard.css or ''):dashboard.css=(dashboard.css or '')+'\n'+css
 brand_dashboard(dashboard)
 session.flush();return dict(dashboard=dashboard.id,dataset=ds.id,charts={k:c.id for k,c in charts.items()})
