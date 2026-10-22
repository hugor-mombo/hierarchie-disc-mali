"""Lot 3 : complétude des tâches, périmètres territoriaux et exports ASC."""
import argparse
import json
from pathlib import Path
from uuid import UUID, uuid5
from superset.app import create_app

ROOT=Path(__file__).resolve().parent
NS=UUID('c5e388d0-45bc-47d7-ae63-9eb53b2abbde')
uid=lambda key:uuid5(NS,key)
parser=argparse.ArgumentParser()
parser.add_argument('--publish',action='store_true')
args=parser.parse_args()
app=create_app()
with app.test_request_context('/'):
 from flask import g
 from flask_login import login_user
 from superset import db,security_manager
 from superset.models.dashboard import Dashboard
 from superset.models.slice import Slice
 from superset.connectors.sqla.models import SqlaTable,TableColumn,SqlMetric
 from regional_security import apply_regional_security
 owner=security_manager.find_user(username='hmombo')
 assert owner
 login_user(owner);g.user=owner
 geo=[('region_uuid','TEXT','Identifiant région'),('region','TEXT','Région'),
  ('district_uuid','TEXT','Identifiant district'),('health_area_uuid','TEXT','Identifiant CSCOM'),
  ('district','TEXT','District · Région'),('cscom','TEXT','CSCOM · District · Région'),
  ('site','TEXT','Site (identifiant court)'),('site_uuid','TEXT','Identifiant site'),
  ('site_name','TEXT','Site ASC'),('district_name','TEXT','District'),('cscom_name','TEXT','CSCOM'),
  ('supervision_area','TEXT','Zone de supervision')]
 common=[('due_month','DATE','Mois d’échéance'),('theme','TEXT','Thématique'),
  ('task_label','TEXT','Type de tâche'),('task_code','TEXT','Code du type de tâche'),
  ('refreshed_at','TIMESTAMP WITH TIME ZONE','Calcul des tâches (UTC)')]
 counts=[('observed','Tâches enregistrées'),('due_total','Tâches échues'),
  ('due_completed','Échues réalisées'),('due_failed','Expirées enregistrées'),
  ('due_open','Échues encore ouvertes'),('open_window','Ouvertes dans leur fenêtre'),
  ('open_stale','Ouvertes après fin de fenêtre'),('open_draft','Programmées échues à vérifier'),
  ('cancelled_all','Annulées'),('upcoming','Ouvertes à venir ou dues aujourd’hui')]
 metrics=[('due_tasks','Tâches échues','SUM(due_total)'),
  ('done_tasks','Échues réalisées','SUM(due_completed)'),
  ('completion','Complétude des échues (%)','SUM(due_completed)::numeric / NULLIF(SUM(due_total),0)'),
  ('expired','Expirées enregistrées','SUM(due_failed)'),
  ('open','Échues encore ouvertes','SUM(due_open)'),
  ('actionable','Ouvertes dans leur fenêtre','SUM(open_window)'),
  ('stale','Ouvertes après fin de fenêtre','SUM(open_stale)'),
  ('draft_overdue','Programmées échues à vérifier','SUM(open_draft)'),
  ('cancelled','Annulées — hors taux','SUM(cancelled_all)'),
  ('upcoming','Ouvertes à venir ou dues aujourd’hui','SUM(upcoming)'),
  ('observed_tasks','Tâches enregistrées','SUM(observed)'),
  ('closed_completion','Réalisation des clôturées (%)','SUM(due_completed)::numeric / NULLIF(SUM(due_completed+due_failed),0)'),
  ('longitudinal_share','Part des échues longitudinales (%)',"SUM(CASE WHEN task_code LIKE 'task.child_longitudinal_%' THEN due_total ELSE 0 END)::numeric / NULLIF(SUM(due_total),0)"),
  ('sites_due','Sites avec tâches échues','COUNT(DISTINCT CASE WHEN due_total>0 THEN site_uuid END)'),
  ('sites_open','Sites avec tâches échues ouvertes','COUNT(DISTINCT CASE WHEN due_open>0 THEN site_uuid END)'),
  ('accounts_open','Comptes avec tâches échues ouvertes','COUNT(DISTINCT CASE WHEN due_open>0 THEN username END)'),
  ('oldest','Plus ancienne échéance encore ouverte','MIN(oldest_open_due)'),
  ('delay','Retard maximal observé (jours)','MAX(reference_date-oldest_open_due)'),
  ('first_month','Premier mois représenté','MIN(due_month)'),
  ('last_month','Dernier mois représenté','MAX(due_month)'),
  ('reference','Date de référence','MAX(reference_date)'),
  ('refresh','Calcul des tâches (UTC)','MAX(refreshed_at)'),
  ('directory_refresh','Répertoire des comptes (UTC)','MIN(directory_refreshed_at)')]
 def dataset(key,title,filename,columns,definitions):
  obj=db.session.query(SqlaTable).filter_by(uuid=uid(key)).one_or_none()
  if obj is None:
   obj=SqlaTable(uuid=uid(key),table_name=title,database_id=1,schema='public');db.session.add(obj)
  obj.sql=(ROOT/'sql'/filename).read_text();obj.main_dttm_col='due_month'
  obj.owners=[owner];obj.created_by=obj.changed_by=owner
  obj.description='Tâches enregistrées, affectation courante des comptes ASC ; période selon le mois d’échéance.'
  known={c.column_name:c for c in obj.columns}
  for name,kind,label in columns:
   c=known.get(name)
   if c is None:c=TableColumn(column_name=name);obj.columns.append(c)
   c.type=kind;c.verbose_name=label;c.is_dttm=kind.startswith(('DATE','TIMESTAMP'));c.groupby=c.filterable=True
  known={m.metric_name:m for m in obj.metrics}
  for name,label,sql in definitions:
   m=known.get(name)
   if m is None:m=SqlMetric(metric_name=name);obj.metrics.append(m)
   m.verbose_name=label;m.expression=sql
  db.session.flush();return obj
 facts=dataset('facts','ASC — Complétude des tâches', 'tasks_monthly.sql',geo+common+
  [(name,'BIGINT',label) for name,label in counts]+
  [('username','TEXT','Compte ASC'),('asc_name','TEXT','Nom ASC'),('phone','TEXT','Téléphone ASC'),
   ('contact_uuid','TEXT','Identifiant contact ASC'),('contact_status','TEXT','Contrôle du rattachement'),
   ('record_quality','TEXT','Qualité du relevé'),('catalogued','BOOLEAN','Type reconnu'),
   ('oldest_open_due','DATE','Plus ancienne échéance ouverte'),('reference_date','DATE','Date de référence'),
   ('directory_refreshed_at','TIMESTAMP WITH TIME ZONE','Répertoire des comptes (UTC)')],metrics)
 quality=dataset('quality','ASC — Qualité des tâches','tasks_quality.sql',common+
  [(n,t,l) for n,t,l in geo if n in ['region_uuid','region','district','cscom','site']]+
  [('quality','TEXT','Situation'),('observed','BIGINT','Tâches enregistrées')],
  [('records','Tâches enregistrées','SUM(observed)'),('refresh','Calcul des tâches (UTC)','MAX(refreshed_at)')])
 geography=db.session.query(SqlaTable).filter_by(uuid=uuid5(UUID('a88972a5-b85f-4772-92cf-8ff98e473283'),'geography')).one()
 apply_regional_security([facts,quality])
 charts={}
 def chart(key,title,source=facts,viz='table',**settings):
  c=db.session.query(Slice).filter_by(uuid=uid('chart:'+key)).one_or_none()
  if c is None:c=Slice(uuid=uid('chart:'+key));db.session.add(c)
  c.slice_name=title;c.viz_type=viz;c.datasource_type='table';c.datasource_id=source.id
  c.owners=[owner];c.created_by=c.changed_by=owner
  params=dict(datasource=f'{source.id}__table',viz_type=viz,granularity_sqla='due_month',
   time_range='previous calendar month',adhoc_filters=[],extra_form_data={},row_limit=100000)
  params.update(settings);c.params=json.dumps(params,ensure_ascii=False);c.query_context=None
  db.session.flush();charts[key]=c;return c
 for key,title,metric,sub in [
  ('due','Tâches échues','due_tasks','Échéance avant la date de référence ; hors annulations'),
  ('done','Échues réalisées','done_tasks','État Completed ; ne prouve pas une réalisation à temps'),
  ('rate','Complétude des échues','completion','Réalisées / échues enregistrées, tous états non annulés'),
  ('expired','Expirées enregistrées','expired','État Failed dans le relevé'),
  ('open','Échues encore ouvertes','open','Ready ou Draft ; état à vérifier avec l’ASC'),
  ('cancelled','Annulées — hors taux','cancelled','État Cancelled ; exclues du dénominateur'),
  ('sites_due','Sites avec tâches échues','sites_due','Au moins une tâche échue enregistrée'),
  ('longitudinal','Part des échues longitudinales','longitudinal_share','À examiner avant toute interprétation de performance'),
  ('closed_rate','Réalisation des clôturées','closed_completion','Comparatif : exclut les tâches encore ouvertes'),
  ('sites_open','Sites à examiner','sites_open','Avec au moins une tâche échue encore ouverte'),
  ('stale','Ouvertes après fin de fenêtre','stale','État à actualiser ; ne pas reclasser automatiquement en échec'),
  ('window','Ouvertes dans leur fenêtre','actionable','État Ready, échéance passée, fenêtre non terminée')]:
  chart(key,title,viz='big_number_total',metric=metric,subheader=sub,
   header_font_size=0.45,subheader_font_size=0.14,y_axis_format='.1%' if key in ['rate','closed_rate','longitudinal'] else ',d')
 bar=dict(metrics=['completion'],groupby=[],annotation_layers=[],show_legend=False,
  color_scheme='supersetColors',rich_tooltip=True,y_axis_format='.0%',y_axis_bounds=[0,1],
  x_axis_sort_series='name',x_axis_sort_series_ascending=True,truncateXAxis=False)
 chart('regions_graph','Complétude par région — période sélectionnée',viz='echarts_timeseries_bar',
  x_axis='region',orientation='horizontal',xAxisLabelRotation=0,**bar)
 chart('trend','Évolution selon les mois d’échéance sélectionnés',viz='echarts_timeseries_line',
  x_axis='due_month',time_grain_sqla='P1M',seriesType='line',markerEnabled=True,
  markerSize=5,x_axis_time_format='%b %Y',**bar)
 formats={m:{'d3NumberFormat':'.1%' if m in ['completion','closed_completion'] else ',d'}
  for m in ['due_tasks','done_tasks','expired','open','stale','actionable','draft_overdue','cancelled',
            'upcoming','completion','closed_completion','observed_tasks','sites_due','delay']}
 table=dict(query_mode='aggregate',all_columns=[],server_pagination=True,server_page_length=20,
  page_length=20,include_search=False,allow_render_html=False,show_cell_bars=False,
  table_timestamp_format='%d/%m/%Y',column_config=formats,order_desc=True)
 summary_metrics=['due_tasks','done_tasks','expired','open','completion']
 for key,title,cols in [('regions','Comparer les régions',['region']),
  ('territories','Comparer les CSCOM',['cscom']),
  ('themes','Complétude par thématique et type',['theme','task_label','task_code']),
  ('months','Volumes et taux par mois',['due_month'])]:
  chart(key,title,groupby=cols,metrics=summary_metrics+(['cancelled','upcoming'] if key=='months' else []),**table)
 followup_filter=[dict(expressionType='SQL',clause='HAVING',sqlExpression='SUM(due_open)>0')]
 chart('followup','ASC à accompagner — tâches échues encore ouvertes',
  groupby=['cscom','site_name','username','task_label','task_code'],
  metrics=['open','actionable','stale','draft_overdue','oldest','delay'],
  adhoc_filters=followup_filter,**table)
 export_columns=['region','district_name','cscom_name','supervision_area','site_name','site_uuid',
  'asc_name','username','phone','contact_status','theme','task_label','task_code']
 export_metrics=['due_tasks','done_tasks','expired','open','actionable','stale','draft_overdue',
  'completion','oldest','delay','first_month','last_month','reference','refresh']
 chart('export','EXPORT TÂCHES — ASC à accompagner avec arborescence',groupby=export_columns,
  metrics=export_metrics,adhoc_filters=followup_filter,**{**table,'server_pagination':False})
 chart('quality','Qualité et périmètre des tâches — période sélectionnée',source=quality,
  groupby=['quality'],metrics=['records'],**table)
 chart('missing_due','Tâches sans échéance — toutes périodes disponibles',source=quality,
  viz='big_number_total',time_range='No filter',metric='records',
  adhoc_filters=[dict(expressionType='SQL',clause='WHERE',sqlExpression="due_month IS NULL")],
  subheader='Contrôle non filtrable par date ; périmètre limité par les droits',y_axis_format=',d')
 chart('freshness','Dates des calculs (UTC)',groupby=[],metrics=['reference','refresh','directory_refresh'],
  **{**table,'server_pagination':False,'page_length':1,'table_timestamp_format':'%d/%m/%Y %H:%M'})
 chart('geography','Sites du relevé géographique courant',source=geography,viz='big_number_total',
  granularity_sqla=None,time_range='No filter',metric='sites',subheader='Ne signifie pas sites fonctionnels DHIS2',y_axis_format=',d')
 dash=db.session.query(Dashboard).filter_by(uuid=uid('dashboard')).one_or_none()
 if dash is None:dash=Dashboard(uuid=uid('dashboard'),slug='asc-completude-taches');db.session.add(dash)
 dash.dashboard_title='ASC — Complétude des tâches';dash.owners=[owner]
 dash.created_by=dash.changed_by=owner;dash.published=args.publish
 dash.roles=list(db.session.query(Dashboard).filter_by(id=1).one().roles)
 dash.slices=list(charts.values())
 layout={'DASHBOARD_VERSION_KEY':'v2',
  'ROOT_ID':dict(id='ROOT_ID',type='ROOT',children=['GRID_ID']),
  'GRID_ID':dict(id='GRID_ID',type='GRID',children=['TABS-TASKS'],parents=['ROOT_ID']),
  'HEADER_ID':dict(id='HEADER_ID',type='HEADER',meta={'text':dash.dashboard_title}),
  'TABS-TASKS':dict(id='TABS-TASKS',type='TABS',children=[],parents=['ROOT_ID','GRID_ID'])}
 def tab(key,title):
  tid='TAB-TASKS-'+key;layout['TABS-TASKS']['children'].append(tid)
  layout[tid]=dict(id=tid,type='TAB',children=[],parents=['ROOT_ID','GRID_ID','TABS-TASKS'],meta={'text':title})
  return tid
 def row(tid,key,items,height):
  rid='ROW-TASKS-'+tid+'-'+key;parents=['ROOT_ID','GRID_ID','TABS-TASKS',tid]
  layout[tid]['children'].append(rid)
  layout[rid]=dict(id=rid,type='ROW',children=[],parents=parents,meta={'background':'BACKGROUND_TRANSPARENT'})
  for ckey,width in items:
   c=charts[ckey];cid='CHART-TASKS-'+ckey;layout[rid]['children'].append(cid)
   layout[cid]=dict(id=cid,type='CHART',children=[],parents=parents+[rid],
    meta=dict(chartId=c.id,sliceName=c.slice_name,uuid=str(c.uuid),width=width,height=height))
 def note(tid,key,code,height):
  rid='ROW-TASKS-note-'+tid+'-'+key;mid='MARKDOWN-TASKS-'+tid+'-'+key;parents=['ROOT_ID','GRID_ID','TABS-TASKS',tid]
  layout[tid]['children'].append(rid)
  layout[rid]=dict(id=rid,type='ROW',children=[mid],parents=parents,meta={'background':'BACKGROUND_TRANSPARENT'})
  layout[mid]=dict(id=mid,type='MARKDOWN',children=[],parents=parents+[rid],meta={'code':code,'width':12,'height':height})
 pilot=tab('pilot','Pilotage de la complétude')
 note(pilot,'intro','''## Où concentrer l’accompagnement sur les tâches ?
Choisissez la **période d’échéance**, puis Région → District → CSCOM → Site et, si nécessaire, une thématique ou un type. Cliquez sur **Apply filters**. Par défaut : dernier mois civil complet. Utilisez des **mois entiers**. L’historique conserve **12 mois complets et les échéances suivantes** ; une période plus ancienne n’est couverte que partiellement.

La **complétude des échues** = tâches réalisées / tâches enregistrées dont l’échéance est **antérieure à la date de référence**, hors annulations et données invalides. Les tâches encore ouvertes restent dans le dénominateur. Une tâche complétée n’est pas nécessairement réalisée à temps. [Pilotage national](/superset/dashboard/asc-pilotage-v2/) · [Listes de suivi](/superset/dashboard/asc-suivi-operationnel/).''',38)
 row(pilot,'cards1',[('due',4),('done',4),('rate',4)],25)
 row(pilot,'cards2',[('expired',4),('open',4),('cancelled',4)],25)
 note(pilot,'vigilance','''**Vigilance sur le suivi longitudinal.** L’audit a constaté plusieurs échéances pour un même bénéficiaire et un même compte au cours d’un mois. Vérifiez la fréquence attendue de génération avant d’interpréter le taux comme une performance individuelle. Les volumes sont conservés ; le filtre **Thématique** permet de les examiner séparément.''',20)
 row(pilot,'context',[('sites_due',4),('longitudinal',4),('closed_rate',4)],25)
 row(pilot,'region_graph',[('regions_graph',12)],72)
 row(pilot,'region_table',[('regions',12)],46)
 row(pilot,'trend',[('trend',12)],42)
 row(pilot,'months',[('months',12)],40)
 action=tab('action','Thématiques et ASC à accompagner')
 note(action,'intro','''## Transformer les résultats en suivi
Les types de tâches sont regroupés par thématique. Comparez les **volumes avec les taux**. La liste ASC cible les comptes ayant des tâches **Ready ou Draft à échéance passée** dans la période choisie.

**Dans leur fenêtre** : l’état Ready est enregistré et la date de fin n’est pas passée. **Après fin de fenêtre** ou **Draft échu** : vérifier l’actualisation et le contexte avec l’ASC. Une tâche expirée n’est pas automatiquement une visite à refaire. Les états reflètent les données disponibles, pas une observation directe du terrain.''',32)
 row(action,'cards',[('sites_open',4),('window',4),('stale',4)],25)
 row(action,'themes',[('themes',12)],52)
 row(action,'territories',[('territories',12)],48)
 row(action,'followup',[('followup',12)],62)
 note(action,'export','''### Télécharger la liste complète d’accompagnement
Appliquez d’abord les filtres, puis utilisez le menu du tableau **EXPORT TÂCHES : ⋮ → Download → Export to .CSV ou Export to Excel**. Une ligne réunit un compte ASC, un site et un type de tâche sur la période sélectionnée, avec Région, District, CSCOM, téléphone, effectifs, échéance la plus ancienne et dates du calcul. Les mois min/max indiquent les mois effectivement représentés dans cette ligne. Aucun nom de patient n’est inclus.''',22)
 row(action,'export',[('export',12)],52)
 method=tab('method','Méthode et qualité')
 note(method,'rules','''## Lire les taux et les états
**Échues** : échéance avant la date de référence du calcul, état Completed, Failed, Ready ou Draft, dates valides. **Réalisées** : Completed parmi ces tâches. **Expirées** : Failed. **Encore ouvertes** : Ready ou Draft. Ces trois effectifs retrouvent le dénominateur. Cancelled reste visible et est exclu du taux. Sans tâche échue, le taux est **non calculable**, jamais forcé à zéro.

Le taux est un **rapport de sommes**, pas la moyenne des taux des comptes ou territoires. Les dates futures de création, états inconnus et fenêtres invalides sont exclus des indicateurs. Une tâche correspond à un **document enregistré pour un compte** ; plusieurs comptes peuvent concerner la même personne. Ce n’est ni un nombre de bénéficiaires distincts, ni la totalité théorique des soins attendus.

La source actuelle ne fournit pas la date de réalisation dans le relevé analytique utilisé : **aucun taux de réalisation dans les délais n’est affirmé**. Le taux historique Completed / (Completed + Failed) ignore les tâches encore ouvertes et répond à une autre question.''',50)
 note(method,'scope','''### Périmètre et fraîcheur
Le périmètre reprend les **comptes ASC courants des listes de suivi**, hors formations et comptes explicitement désactivés/supprimés, rattachés à un site du relevé. Les tâches hors de ce périmètre sont comptées dans le contrôle national, sans noms. L’affectation est celle du répertoire courant ; les mutations historiques ne sont pas reconstituées. Les sites fermés DHIS2 ne sont pas encore identifiés ici.

L’historique couvre **12 mois complets et les échéances suivantes** disponibles. Le calcul est prévu **toutes les six heures**, à partir de la vue analytique de tâches existante. Ses dates ne prouvent pas la fraîcheur de la réplication du téléphone ou de la vue amont. Un état ouvert ancien peut nécessiter une actualisation plutôt qu’une action clinique.''',38)
 row(method,'freshness',[('freshness',12)],16)
 row(method,'quality',[('quality',12)],38)
 note(method,'quality_help','''**Lecture du contrôle :** les tâches hors périmètre, sans rattachement régional, sont visibles uniquement aux profils nationaux. Les profils régionaux voient leur propre périmètre. Les filtres géographiques masquent les tâches non attribuées. Le contrôle sans échéance ci-dessous ignore le filtre de date, car aucun mois ne peut lui être attribué.

Références techniques : [analyse des tâches CHT](https://docs.communityhealthtoolkit.org/building/tasks/managing-tasks/query-task-data/) · [états et schéma CHT](https://docs.communityhealthtoolkit.org/technical-overview/data/db-schema/#tasks).''',24)
 row(method,'coverage',[('missing_due',6),('geography',6)],25)
 all_ids=[c.id for c in charts.values()]
 filters=[dict(id='NATIVE_FILTER-tasks-period',type='NATIVE_FILTER',name='Période d’échéance',
  filterType='filter_time',targets=[{}],controlValues={},cascadeParentIds=[],
  defaultDataMask={'extraFormData':{'time_range':'previous calendar month'},
   'filterState':{'value':'previous calendar month'},'ownState':{}},
  scope={'rootPath':['ROOT_ID'],'excluded':[charts[k].id for k in ['geography','missing_due']]},
  description='Mois civils entiers ; dernier mois complet par défaut. La source est mensuelle.')]
 for key,name,source,column,parents in [('region','Région',geography,'region',[]),
  ('district','District',geography,'district',['region']),('cscom','CSCOM',geography,'cscom',['region','district']),
  ('site','Site ASC',geography,'site',['region','district','cscom']),
  ('theme','Thématique',facts,'theme',['period','region','district','cscom','site']),
  ('type','Type de tâche',facts,'task_label',['period','region','district','cscom','site','theme'])]:
  filters.append(dict(id='NATIVE_FILTER-tasks-'+key,type='NATIVE_FILTER',name=name,filterType='filter_select',
   targets=[{'datasetId':source.id,'column':{'name':column}}],
   controlValues=dict(enableEmptyFilter=False,defaultToFirstItem=False,multiSelect=True,searchAllOptions=True,inverseSelection=False),
   defaultDataMask={'extraFormData':{},'filterState':{},'ownState':{}},
   cascadeParentIds=['NATIVE_FILTER-tasks-'+p for p in parents],
   scope={'rootPath':['ROOT_ID'],'excluded':[charts['geography'].id] if key in ['theme','type'] else []},
   description='Appliquer les filtres après la sélection.'))
 dash.position_json=json.dumps(layout,ensure_ascii=False)
 # Chaque composant a un seul parent ; une note d'un onglet ne doit pas
 # remplacer une note portant le même nom dans un autre onglet.
 seen=set()
 def validate_layout(node):
  assert node not in seen, 'Composant de mise en page partagé : '+node
  seen.add(node)
  for child in layout[node].get('children',[]):
   assert layout[child]['parents'][-1]==node,(node,child)
   validate_layout(child)
 validate_layout('ROOT_ID')
 dash.json_metadata=json.dumps(dict(native_filter_configuration=filters,cross_filters_enabled=False,
  refresh_frequency=0,expanded_slices={},timed_refresh_immune_slices=[],default_filters='{}',chart_configuration={},color_scheme='supersetColors'),ensure_ascii=False)
 dash.css='''.dashboard-content {background:#f3f6fb;}
.dashboard-component-chart-holder {border:1px solid #e3eaf3;border-radius:10px;}
.dashboard-markdown h2 {color:#153854;}
.dashboard-markdown {color:#334e68;}
'''
 db.session.commit()
 print(json.dumps({'dashboard':dash.id,'slug':dash.slug,'published':dash.published,
  'datasets':{'facts':facts.id,'quality':quality.id},'charts':{k:c.id for k,c in charts.items()}},ensure_ascii=False),flush=True)
