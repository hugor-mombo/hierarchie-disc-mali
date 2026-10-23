"""Create thematic dashboards alongside the existing ASC dashboards (stable UUIDs)."""
import argparse
import json
from uuid import UUID,uuid5
from superset.app import create_app
from theme_sql import CATALOG,NS,table_name
parser=argparse.ArgumentParser()
parser.add_argument('--publish',action='store_true')
args=parser.parse_args()
uid=lambda key:uuid5(UUID(NS),key)
slug=lambda key:'asc-theme-'+key
literal=lambda value:"'"+value.replace("'","''")+"'"
COMMON=[('input_rows','BIGINT','Lignes amont regroupées'),('reported_month','DATE','Mois déclaré'),('region_uuid','TEXT','Identifiant région'),('region','TEXT','Région'),
 ('district_uuid','TEXT','Identifiant district'),('district','TEXT','District · Région'),('district_name','TEXT','District'),
 ('health_area_uuid','TEXT','Identifiant CSCOM'),('cscom','TEXT','CSCOM · District · Région'),('cscom_name','TEXT','CSCOM'),
 ('site_uuid','TEXT','Identifiant site'),('site','TEXT','Site (identifiant court)'),('site_name','TEXT','Site ASC'),
 ('supervision_area','TEXT','Zone de supervision'),('entity_uuid','TEXT','Clé du grain source'),
 ('attribution','TEXT','Contrôle du rattachement'),('calculated_at','TIMESTAMP WITH TIME ZONE','Calcul du relevé (UTC)'),
 ('coverage_start','DATE','Début de la période préparée'),('coverage_end','DATE','Fin exclusive de la période préparée')]
app=create_app()
with app.test_request_context('/'):
 from flask import g
 from flask_login import login_user
 from superset import db,security_manager
 from superset.models.dashboard import Dashboard
 from superset.models.slice import Slice
 from superset.connectors.sqla.models import SqlaTable,TableColumn,SqlMetric
 from regional_security import apply_regional_security
 owner=security_manager.find_user(username='hmombo');assert owner
 login_user(owner);g.user=owner
 history=db.session.query(Dashboard).filter_by(id=1).one()
 historical_snapshot=(history.position_json,history.json_metadata,[s.id for s in history.slices],history.published)
 geography=db.session.query(SqlaTable).filter_by(uuid=uuid5(UUID('a88972a5-b85f-4772-92cf-8ff98e473283'),'geography')).one()
 new_datasets=[]
 def dataset(key,title,sql,columns,metrics):
  ds=db.session.query(SqlaTable).filter_by(uuid=uid('dataset:'+key)).one_or_none()
  if ds is None:
   ds=SqlaTable(uuid=uid('dataset:'+key),table_name=title,database_id=1,schema='public');db.session.add(ds)
  ds.sql=sql;ds.main_dttm_col='reported_month';ds.owners=[owner];ds.created_by=ds.changed_by=owner
  ds.description='Relevé thématique sur douze mois complets ; observations selon la méthode documentée, sans nouvelle donnée clinique individuelle.'
  for name,kind,label in columns:
   col=next((x for x in ds.columns if x.column_name==name),None)
   if col is None:col=TableColumn(column_name=name);ds.columns.append(col)
   col.type=kind;col.verbose_name=label;col.is_dttm=kind.startswith(('DATE','TIMESTAMP'));col.groupby=col.filterable=True
  for name,label,expression in metrics:
   metric=next((x for x in ds.metrics if x.metric_name==name),None)
   if metric is None:metric=SqlMetric(metric_name=name);ds.metrics.append(metric)
   metric.verbose_name=label;metric.expression=expression
  db.session.flush();new_datasets.append(ds);return ds
 freshness=[('calculation','Calcul du relevé (UTC)','MAX(calculated_at)'),('first_month','Premier mois disponible','MIN(reported_month)'),
  ('last_month','Dernier mois disponible','MAX(reported_month)'),('rows','Lignes de relevé','COUNT(*)'),('input_rows','Lignes amont regroupées','SUM(input_rows)'),
  ('unknown','Lignes hors répertoire courant',"COUNT(*) FILTER(WHERE attribution='Hors répertoire courant')")]
 facts={};longs={}
 for theme in CATALOG:
  key=theme['key'];metrics=theme['metrics']
  facts[key]=dataset(key, 'ASC Thème — '+theme['title'],'SELECT * FROM public.'+table_name(theme),COMMON+
   [(m['key'],'NUMERIC',m['label']) for m in metrics],
   [('m_'+m['key'],m['label'],'SUM('+m['key']+')') for m in metrics]+freshness)
  values=','.join('('+literal(m['key'])+','+literal(m['label'])+','+literal(m['unit'])+',f.'+m['key']+')' for m in metrics)
  longs[key]=dataset(key+':indicators','ASC Indicateurs — '+theme['title'],
   'SELECT f.*,i.indicator_key,i.indicator,i.unit,i.value FROM public.'+table_name(theme)+
   ' f CROSS JOIN LATERAL (VALUES '+values+')i(indicator_key,indicator,unit,value)',COMMON+
   [('indicator_key','TEXT','Code indicateur'),('indicator','TEXT','Indicateur'),('unit','TEXT','Unité'),('value','NUMERIC','Volume enregistré')],
   [('volume','Volume enregistré','SUM(value)')]+freshness)
 quality_parts=[]
 for theme in CATALOG:
  quality_parts.append('SELECT '+literal(theme['title'])+' AS theme,input_rows,reported_month,region_uuid,region,district,cscom,attribution,calculated_at FROM public.'+table_name(theme))
 quality=dataset('availability','ASC Thèmes — Disponibilité des relevés',' UNION ALL '.join(quality_parts),
  [('theme','TEXT','Tableau thématique')]+[c for c in COMMON if c[0] in ['input_rows','reported_month','region_uuid','region','district','cscom','attribution','calculated_at']],freshness)
 apply_regional_security(new_datasets)
 table=dict(query_mode='aggregate',all_columns=[],server_pagination=True,server_page_length=20,page_length=20,
  include_search=False,allow_render_html=False,show_cell_bars=False,order_desc=True,table_timestamp_format='%d/%m/%Y')
 reports=[]
 class Board:
  def __init__(self,key,title,url):
   self.key=key;self.charts={}
   d=db.session.query(Dashboard).filter_by(uuid=uid('dashboard:'+key)).one_or_none()
   if d is None:d=Dashboard(uuid=uid('dashboard:'+key),slug=url);db.session.add(d)
   d.dashboard_title=title;d.owners=[owner];d.created_by=d.changed_by=owner;d.roles=list(history.roles);d.published=args.publish
   self.dash=d
   self.layout={'DASHBOARD_VERSION_KEY':'v2','ROOT_ID':dict(id='ROOT_ID',type='ROOT',children=['GRID_ID']),
    'GRID_ID':dict(id='GRID_ID',type='GRID',children=['TABS-THEME'],parents=['ROOT_ID']),
    'HEADER_ID':dict(id='HEADER_ID',type='HEADER',meta={'text':title}),
    'TABS-THEME':dict(id='TABS-THEME',type='TABS',children=[],parents=['ROOT_ID','GRID_ID'])}
  def chart(self,key,title,ds,viz='table',**settings):
   c=db.session.query(Slice).filter_by(uuid=uid('chart:'+self.key+':'+key)).one_or_none()
   if c is None:c=Slice(uuid=uid('chart:'+self.key+':'+key));db.session.add(c)
   c.slice_name=title;c.viz_type=viz;c.datasource_type='table';c.datasource_id=ds.id;c.owners=[owner];c.created_by=c.changed_by=owner
   p=dict(datasource=f'{ds.id}__table',viz_type=viz,time_range='previous calendar month',granularity_sqla='reported_month',
    adhoc_filters=[] if key in ['quality','freshness','availability'] or key.startswith('zero_') else [dict(expressionType='SQL',clause='WHERE',sqlExpression="attribution='Rattaché au répertoire courant'")],extra_form_data={},row_limit=100000)
   p.update(settings);c.params=json.dumps(p,ensure_ascii=False);c.query_context=None;db.session.flush();self.charts[key]=c;return c
  def tab(self,key,title):
   tid='TAB-'+self.key+'-'+key;self.layout['TABS-THEME']['children'].append(tid)
   self.layout[tid]=dict(id=tid,type='TAB',children=[],parents=['ROOT_ID','GRID_ID','TABS-THEME'],meta={'text':title});return tid
  def row(self,tid,key,items,height):
   rid=tid+'-ROW-'+key;parents=['ROOT_ID','GRID_ID','TABS-THEME',tid]
   self.layout[tid]['children'].append(rid);self.layout[rid]=dict(id=rid,type='ROW',children=[],parents=parents,meta={'background':'BACKGROUND_TRANSPARENT'})
   for name,width in items:
    c=self.charts[name];cid=tid+'-CHART-'+name;self.layout[rid]['children'].append(cid)
    self.layout[cid]=dict(id=cid,type='CHART',children=[],parents=parents+[rid],meta=dict(chartId=c.id,sliceName=c.slice_name,uuid=str(c.uuid),width=width,height=height))
  def note(self,tid,key,code,height):
   rid=tid+'-NOTE-'+key;mid=rid+'-MARKDOWN';parents=['ROOT_ID','GRID_ID','TABS-THEME',tid]
   self.layout[tid]['children'].append(rid);self.layout[rid]=dict(id=rid,type='ROW',children=[mid],parents=parents,meta={'background':'BACKGROUND_TRANSPARENT'})
   self.layout[mid]=dict(id=mid,type='MARKDOWN',children=[],parents=parents+[rid],meta={'code':code,'width':12,'height':height})
  def finish(self,filters):
   seen=set()
   def check(node):
    assert node not in seen,node;seen.add(node)
    for child in self.layout[node].get('children',[]):
     assert self.layout[child]['parents'][-1]==node;check(child)
   check('ROOT_ID')
   self.dash.slices=list(self.charts.values());self.dash.position_json=json.dumps(self.layout,ensure_ascii=False)
   self.dash.json_metadata=json.dumps(dict(native_filter_configuration=filters,cross_filters_enabled=False,refresh_frequency=0,
    expanded_slices={},timed_refresh_immune_slices=[],default_filters='{}',chart_configuration={},color_scheme='supersetColors'),ensure_ascii=False)
   self.dash.css='''.dashboard-content{background:#f3f6fb}.dashboard-component-chart-holder{border:1px solid #dce6ef;border-radius:10px}
.dashboard-markdown h2,.dashboard-markdown h3{color:#153854}.dashboard-markdown{color:#334e68}
.dashboard-markdown a{font-weight:600}.dashboard-markdown table{width:100%}.dashboard-markdown th,.dashboard-markdown td{padding:9px 12px;border-bottom:1px solid #e1e8f0}'''
   db.session.flush();reports.append(dict(key=self.key,id=self.dash.id,slug=self.dash.slug,charts={k:c.id for k,c in self.charts.items()}))
 def filters_for(board,long=None,theme=None,current_ids=[]):
  prefix='NATIVE_FILTER-themes-'+board.key+'-'
  excluded=[board.charts[k].id for k in ['trend','freshness'] if k in board.charts]+current_ids
  filters=[dict(id=prefix+'period',type='NATIVE_FILTER',name='Période des indicateurs mensuels',filterType='filter_time',targets=[{}],controlValues={},cascadeParentIds=[],
   defaultDataMask={'extraFormData':{'time_range':'previous calendar month'},'filterState':{'value':'previous calendar month'},'ownState':{}},
   scope={'rootPath':['ROOT_ID'],'excluded':excluded},description='Mois civils entiers. Dernier mois complet par défaut. La tendance conserve les 12 mois préparés ; le relevé zéro dose est actuel.')]
  for key,name,col,parents in [('region','Région','region',[]),('district','District','district',['region']),('cscom','CSCOM','cscom',['region','district'])]:
   filters.append(dict(id=prefix+key,type='NATIVE_FILTER',name=name,filterType='filter_select',targets=[{'datasetId':geography.id,'column':{'name':col}}],
    controlValues=dict(enableEmptyFilter=False,defaultToFirstItem=False,multiSelect=True,searchAllOptions=True,inverseSelection=False),
    defaultDataMask={'extraFormData':{},'filterState':{},'ownState':{}},cascadeParentIds=[prefix+x for x in parents],scope={'rootPath':['ROOT_ID'],'excluded':[]},description='Appliquer les filtres après sélection. Les droits territoriaux sont appliqués séparément.'))
  if long:
   primary=next(m for m in theme['metrics'] if m['key']==theme['primary'][0])
   targeted=['regions','trend','territories','sites']
   scopes=[c.id for k,c in board.charts.items() if k in targeted]
   filters.append(dict(id=prefix+'indicator',type='NATIVE_FILTER',name='Indicateur à explorer',filterType='filter_select',targets=[{'datasetId':long.id,'column':{'name':'indicator'}}],
    controlValues=dict(enableEmptyFilter=True,defaultToFirstItem=False,multiSelect=False,searchAllOptions=True,inverseSelection=False),
    defaultDataMask={'extraFormData':{'filters':[{'col':'indicator','op':'IN','val':[primary['label']]}]},'filterState':{'value':[primary['label']],'label':primary['label']},'ownState':{}},
    cascadeParentIds=[prefix+'region',prefix+'district',prefix+'cscom'],scope={'rootPath':['ROOT_ID'],'excluded':[c.id for k,c in board.charts.items() if c.id not in scopes]},
    description='Choix pour la comparaison, la tendance et les tableaux détaillés. Les cartes et EXPORT TOUS LES INDICATEURS conservent leur propre indicateur.'))
  return filters
 for theme in CATALOG:
  key=theme['key'];ds=facts[key];long=longs[key];primary=theme['primary'];metrics=theme['metrics']
  b=Board(key,'ASC — '+theme['title'],slug(key))
  for m in metrics:
   if m['key'] in primary:
    b.chart('card_'+m['key'],m.get('card_title',m['label']),ds,'big_number_total',metric='m_'+m['key'],header_font_size=0.45,subheader_font_size=0.14,y_axis_format=',d',subheader=m['unit']+' · période choisie')
  bar=dict(metrics=['volume'],groupby=[],annotation_layers=[],show_legend=False,color_scheme='supersetColors',rich_tooltip=True,
   y_axis_format=',d',x_axis_sort_series='sum',x_axis_sort_series_ascending=False,truncateXAxis=False)
  b.chart('regions','Indicateur choisi — comparaison régionale',long,'echarts_timeseries_bar',x_axis='region',orientation='horizontal',**bar)
  b.chart('trend','Indicateur choisi — 12 derniers mois complets',long,'echarts_timeseries_line',x_axis='reported_month',time_grain_sqla='P1M',
   time_range='No filter',seriesType='line',markerEnabled=True,markerSize=4,x_axis_time_format='%b %Y',**bar)
  b.chart('territories','Indicateur choisi — Région, District et CSCOM',long,groupby=['region','district','cscom','indicator','unit'],metrics=['volume'],**table)
  if theme['grain']=='site':
   b.chart('sites','Indicateur choisi — détail des sites',long,groupby=['cscom','site_name','site_uuid','indicator','unit'],metrics=['volume'],**table)
  export_cols=['reported_month','region','region_uuid','district_name','district_uuid','cscom_name','health_area_uuid']
  if theme['grain']=='site':export_cols+=['supervision_area','site_name','site_uuid']
  export_cols+=['entity_uuid','attribution','input_rows','calculated_at']
  b.chart('export','EXPORT TOUS LES INDICATEURS — période et arborescence',ds,groupby=export_cols,metrics=['m_'+m['key'] for m in metrics],**{**table,'server_pagination':False})
  b.chart('freshness','Période préparée et date du calcul (UTC)',ds,time_range='No filter',groupby=[],metrics=['first_month','last_month','calculation'],**{**table,'server_pagination':False,'page_length':1,'table_timestamp_format':'%d/%m/%Y %H:%M'})
  b.chart('quality','Rattachement des lignes du relevé',ds,groupby=['attribution'],metrics=['rows','input_rows']+['m_'+x for x in primary],**table)
  current_ids=[]
  p=b.tab('pilot','Synthèse')
  b.note(p,'intro','## '+theme['question']+'''
Choisissez des **mois civils entiers**, puis **Région → District → CSCOM** et **Indicateur à explorer**. Cliquez sur **Apply filters**.
Cartes selon la période choisie ; tendance sur **12 mois complets**. Unités du répertoire courant.

[← Tous les tableaux thématiques](/superset/dashboard/asc-thematiques/) · [Suivi opérationnel](/superset/dashboard/asc-suivi-operationnel/) · [Complétude des tâches](/superset/dashboard/asc-completude-taches/)
''',24)
  b.row(p,'cards',[('card_'+x,12//len(primary)) for x in primary],23)
  extra_note={'references':'\n\n[Références des moins de cinq ans](/superset/dashboard/asc-theme-pec-enfant/) · [Références néonatales](/superset/dashboard/asc-theme-neonatale/)', 'paludisme':'\n\n[Paludisme chez les moins de cinq ans](/superset/dashboard/asc-theme-pec-enfant/)'}.get(key,'')
  b.note(p,'interpretation','**À lire avant de comparer :** '+theme['method']+extra_note,28)
  b.row(p,'regions',[('regions',12)],66)
  b.row(p,'trend',[('trend',12)],42)
  d=b.tab('detail','Territoires et exports')
  b.note(d,'intro','''## Comparer, puis télécharger
Les tableaux de détail suivent l’**indicateur choisi**. Comparez les volumes dans leur contexte : l’absence d’activité enregistrée ne prouve pas une absence de soins.

**EXPORT TOUS LES INDICATEURS** conserve les filtres de **période et territoire**, et ignore le sélecteur d’indicateur. Une ligne correspond à un '''+('site/mois' if theme['grain']=='site' else 'CSCOM/mois')+''' ; les noms et identifiants territoriaux sont inclus. Menu **⋮ → Download → Export to .CSV ou Export to Excel**. Les noms de colonnes et unités sont détaillés dans l’onglet Méthode. Aucun nom de patient n’est ajouté à cet export agrégé.''',34)
  b.row(d,'territories',[('territories',12)],52)
  if theme['grain']=='site':b.row(d,'sites',[('sites',12)],52)
  b.row(d,'export',[('export',12)],58)
  if key=='vaccination':
   children=db.session.query(SqlaTable).filter_by(uuid=uuid5(UUID('a88972a5-b85f-4772-92cf-8ff98e473283'),'children')).one()
   fixed=[dict(expressionType='SQL',clause='WHERE',sqlExpression="followup_status='Penta 1 non reçu déclaré — à confirmer'")]
   c=b.chart('zero_count','Enfants actuellement signalés Penta 1 non reçu — à confirmer',children,'big_number_total',metric='children',
    time_range='No filter',granularity_sqla=None,adhoc_filters=fixed,header_font_size=0.45,y_axis_format=',d',subheader='Relevé actuel · 12–59 mois · selon les droits territoriaux')
   c2=b.chart('zero_old','Signalements actuels de 90 jours ou plus',children,'big_number_total',metric='old',time_range='No filter',granularity_sqla=None,
    adhoc_filters=fixed,header_font_size=0.45,y_axis_format=',d',subheader='À actualiser avec l’ASC ; pas une preuve de non-vaccination')
   cols=['region','district_name','cscom_name','supervision_area','site_name','site_uuid','child_name','patient_uuid','sex','age_months',
    'last_observation','observation_age_days','latest_penta1','followup_status','reference_date','refreshed_at']
   ce=b.chart('zero_export','EXPORT ZÉRO DOSE — liste actuelle à confirmer',children,time_range='No filter',granularity_sqla=None,
    groupby=cols,metrics=[],adhoc_filters=fixed,**{**table,'server_pagination':False})
   current_ids=[c.id,c2.id,ce.id]
   z=b.tab('zero','Zéro dose · liste actuelle')
   b.note(z,'intro','''## Retrouver les enfants signalés, puis confirmer leur situation
Cette liste reprend le relevé opérationnel déjà contrôlé : **12–59 mois**, Penta 1 explicitement déclaré non reçu, sans preuve positive retrouvée et avec rattachement actuel non ambigu. Les décès connus sont exclus. Une vaccination non saisie ou non répliquée reste possible : **confirmer sur le terrain**.

Le filtre de période mensuelle et le sélecteur d’indicateur **ne s’appliquent pas à cet onglet**. Région, District et CSCOM s’appliquent. Le CSV/Excel contient des données individuelles et suit les mêmes droits territoriaux que la liste existante. La date du relevé figure dans l’export. [Autres situations à vérifier](/superset/dashboard/asc-suivi-operationnel/) · [Historique des antigènes dans le tableau ASC initial](/superset/dashboard/1/).''',42)
   b.row(z,'cards',[('zero_count',6),('zero_old',6)],32)
   b.row(z,'export',[('zero_export',12)],62)
  method=b.tab('method','Méthode et qualité')
  b.note(method,'rules','## Ce que mesure ce tableau\n'+theme['method']+'''

Les effectifs s’additionnent comme des **volumes d’observations**, pas comme des personnes uniques sur plusieurs mois. Aucune moyenne de pourcentages ni taux clinique sans dénominateur compatible n’est présenté. **Vide ≠ zéro :** une information absente ne doit pas être interprétée comme une mesure nulle. Les zéros déjà présents dans les sources historiques ne permettent pas toujours de distinguer non-saisie et activité nulle.

Le calcul prépare les **12 mois civils complets** précédents. Les sources historiques n’ont pas toutes la même profondeur ni le même rythme d’actualisation ; une période sans ligne reste indisponible. La date ci-dessous est celle du **calcul de ce relevé**, pas celle de la synchronisation des téléphones ou du rafraîchissement des sources amont. Les rattachements géographiques sont ceux du répertoire courant ; les mouvements historiques ne sont pas reconstruits.''',65)
  b.row(method,'freshness',[('freshness',12)],18)
  b.note(method,'quality','''### Contrôle du rattachement
Les lignes absentes du répertoire courant restent dans le contrôle national ; celles ayant perdu leur identifiant de site en amont sont regroupées par mois, avec leurs volumes conservés et le nombre de lignes amont regroupées. Aucun site fictif n’est créé. Ces lignes n’ont pas de rattachement régional utilisable. Les lecteurs régionaux n’obtiennent que leur périmètre autorisé. Un CSCOM trouvé dans plusieurs branches n’est jamais réparti entre ses sites : le chemin complet de la source est vérifié. Le répertoire ne certifie pas l’ouverture DHIS2 du site.''',24)
  b.row(method,'quality',[('quality',12)],28)
  dictionary='### Dictionnaire des indicateurs\n\n| Indicateur | Unité de lecture | Code de colonne export |\n|---|---|---|\n'+'\n'.join('| '+m['label']+' | '+m['unit']+' | `m_'+m['key']+'` |' for m in metrics)
  b.note(method,'dictionary',dictionary,max(40,14+len(metrics)*5))
  b.finish(filters_for(b,long,theme,current_ids))
 hub=Board('hub','ASC — Tableaux thématiques','asc-thematiques')
 start=hub.tab('start','Choisir un tableau')
 hub.note(start,'intro','''## La santé communautaire, du signal à l’action
Ouvrez une thématique, choisissez votre période et votre territoire, puis explorez l’indicateur utile à votre décision. Chaque tableau propose une **synthèse**, des **détails territoriaux**, un **export CSV/Excel** et une **méthode de lecture**.

[Rapportage national](/superset/dashboard/asc-pilotage-v2/) · [Relances ASC et listes de suivi](/superset/dashboard/asc-suivi-operationnel/) · [Complétude des tâches](/superset/dashboard/asc-completude-taches/) · [Tableau ASC historique](/superset/dashboard/1/)''',23)
 for i in range(0,len(CATALOG),2):
  pair=CATALOG[i:i+2]
  content='\n\n'.join('### ['+t['title']+'](/superset/dashboard/'+slug(t['key'])+'/)\n'+t['question'] for t in pair)
  hub.note(start,'themes'+str(i),content,18)
 q=hub.tab('availability','Disponibilité et lecture')
 hub.chart('availability','Relevés disponibles — période et droits appliqués',quality,groupby=['theme','attribution'],metrics=['rows','first_month','last_month','calculation'],**table)
 hub.note(q,'scope','''## Vérifier la période disponible avant d’interpréter les résultats
Les indicateurs mensuels couvrent **au maximum les 12 derniers mois complets**, selon ce qui existe dans chaque source. Une ligne de relevé n’est pas une consultation ou une personne. Certaines sources contiennent des grilles à zéro ; l’absence de valeur ou de ligne reste distincte d’un zéro.

Les sources historiques sont conservées et les corrections de présentation sont documentées dans chaque tableau. Les filtres territoriaux de l’interface complètent les droits d’accès ; ils ne les remplacent pas. Les dates affichées décrivent le calcul des relevés, sans certifier la fraîcheur de la réplication amont. La liste zéro dose est un **relevé actuel** séparé des séries mensuelles.''',40)
 hub.row(q,'availability',[('availability',12)],70)
 hub.finish(filters_for(hub))
 assert historical_snapshot==(history.position_json,history.json_metadata,[s.id for s in history.slices],history.published),'Historical dashboard modified'
 db.session.commit()
 print(json.dumps(dict(status='OK',published=args.publish,datasets=len(new_datasets),dashboards=reports),ensure_ascii=False),flush=True)
