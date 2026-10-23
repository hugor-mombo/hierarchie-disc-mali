"""Lot 1 SD: source-specific dashboards; historical SD/ASC remain unchanged."""
import argparse
import json
from superset.app import create_app
from dashboard_branding import brand_primary_dashboards
from sd_catalog import ROOT,SOURCES,FRESHNESS,uid,sql
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
 owner=security_manager.find_user(username='hmombo');assert owner
 login_user(owner);g.user=owner
 history=db.session.query(Dashboard).filter_by(id=2).one()
 originals={d.id:(d.position_json,d.json_metadata,[c.id for c in d.slices],d.published) for d in db.session.query(Dashboard).filter(Dashboard.id.in_([1,2])).all()}
 datasets={};reports=[]
 for key,config in SOURCES.items():
  ds=db.session.query(SqlaTable).filter_by(uuid=uid('dataset:'+key)).one_or_none()
  if ds is None:
   ds=SqlaTable(uuid=uid('dataset:'+key),table_name=config['title'],database_id=config['db'],schema='public');db.session.add(ds)
  assert ds.database_id==config['db']
  ds.sql=sql(key);ds.main_dttm_col='reported_month';ds.owners=[owner];ds.created_by=ds.changed_by=owner
  ds.description='Supervision dédiée — source native '+('DISC' if config['db']==1 else 'ASA')+'. Les définitions ne sont pas fusionnées ; voir Méthode et qualité.'
  for name,kind,label in config['columns']:
   col=next((x for x in ds.columns if x.column_name==name),None)
   if col is None:col=TableColumn(column_name=name);ds.columns.append(col)
   col.type=kind;col.verbose_name=label;col.is_dttm=kind.startswith(('DATE','TIMESTAMP'));col.groupby=col.filterable=True
  for name,label,expression in config['metrics']+FRESHNESS:
   metric=next((x for x in ds.metrics if x.metric_name==name),None)
   if metric is None:metric=SqlMetric(metric_name=name);ds.metrics.append(metric)
   metric.verbose_name=label;metric.expression=expression
  db.session.flush();datasets[key]=ds
 # ASA has no canonical region UUID. Regional access therefore remains empty, never inferred from a matching name.
 apply_regional_security(list(datasets.values()))
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
    adhoc_filters=[],extra_form_data={},row_limit=100000)
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
 def filters_for(board,ds,asa=False):
  prefix='NATIVE_FILTER-sd-'+board.key+'-'
  time='2025-01-01 : 2026-01-01' if asa else 'previous calendar month'
  filters=[dict(id=prefix+'period',type='NATIVE_FILTER',name='Période ASA' if asa else 'Période DISC',filterType='filter_time',targets=[{}],controlValues={},cascadeParentIds=[],
   defaultDataMask={'extraFormData':{'time_range':time},'filterState':{'value':time},'ownState':{}},scope={'rootPath':['ROOT_ID'],'excluded':[c.id for k,c in board.charts.items() if k in ['trend','available','fm_available']]},
   description='Mois civils entiers. Le calcul se fait par site et par mois ; plusieurs mois représentent des sites-mois.')]
  columns=[('region','Région ASA' if asa else 'Région',[]),('district','District déclaré ASA' if asa else 'District',['region'])]
  if not asa:columns+=[('cscom','CSCOM',['region','district'])]
  columns+=[('zone','Zone ASA' if asa else 'Zone de supervision',[x[0] for x in columns])]
  for col,label,parents in columns:
   filters.append(dict(id=prefix+col,type='NATIVE_FILTER',name=label,filterType='filter_select',targets=[{'datasetId':ds.id,'column':{'name':col}}],
    controlValues=dict(enableEmptyFilter=False,defaultToFirstItem=False,multiSelect=True,searchAllOptions=True,inverseSelection=False),defaultDataMask={'extraFormData':{},'filterState':{},'ownState':{}},
    cascadeParentIds=[prefix+p for p in parents],scope={'rootPath':['ROOT_ID'],'excluded':[]},description='Géographie native de cette source. Appliquer après sélection.'))
  if not asa:
   filters.append(dict(id=prefix+'status',type='NATIVE_FILTER',name='État du quota mensuel',filterType='filter_select',targets=[{'datasetId':ds.id,'column':{'name':'quota_status'}}],
    controlValues=dict(enableEmptyFilter=False,defaultToFirstItem=False,multiSelect=True,searchAllOptions=True,inverseSelection=False),defaultDataMask={'extraFormData':{},'filterState':{},'ownState':{}},cascadeParentIds=[],
    scope={'rootPath':['ROOT_ID'],'excluded':[c.id for k,c in board.charts.items() if k not in ['sites','export']]},description='Filtre des listes et exports uniquement ; les cartes et taux conservent leur dénominateur complet.'))
  return filters
 table=dict(query_mode='aggregate',all_columns=[],server_pagination=True,server_page_length=20,page_length=20,include_search=False,allow_render_html=False,show_cell_bars=False,order_desc=True,table_timestamp_format='%d/%m/%Y',column_config={'quota_rate':{'d3NumberFormat':'.1%'},'rdt_rate':{'d3NumberFormat':'.1%'},'average_visits':{'d3NumberFormat':'.1f'}})
 bar=dict(metrics=['quota_rate'],groupby=[],annotation_layers=[],show_legend=False,color_scheme='supersetColors',rich_tooltip=True,y_axis_format='.0%',y_axis_bounds=[0,1],x_axis_sort_series='name',x_axis_sort_series_ascending=True,truncateXAxis=False)
 nav='[← Espace supervision](/superset/dashboard/sd-supervision/) · [DISC](/superset/dashboard/sd-pilotage-disc/) · [Historique ASA](/superset/dashboard/sd-historique-asa/) · [Qualité DISC](/superset/dashboard/sd-qualite-disc/) · [Qualité ASA](/superset/dashboard/sd-qualite-asa/) · [Ancien SD](/superset/dashboard/2/)'
 b=Board('disc','SD — Pilotage DISC','sd-pilotage-disc');ds=datasets['disc']
 p=b.tab('pilot','Synthèse DISC')
 b.note(p,'intro','''## Où renforcer les supervisions sur DISC ?
Choisissez des **mois civils entiers**, puis **Région → District → CSCOM → Zone**, et cliquez sur **Appliquer les filtres**.
Le déploiement 2026 a été progressif. Le dénominateur est le **portefeuille courant relu sur les mois passés**, pas le nombre de sites effectivement déployés à chaque date. Ce taux décrit ce portefeuille ; il ne mesure pas la couverture historique du programme.

'''+nav,26)
 cards=[('unique_sites','Sites distincts du portefeuille','Présents dans le répertoire actuel',',d'),('quota_count','Quotas mensuels complets','Sites-mois avec 1 visite ASC + 5 sans ASC + 1 entretien',',d'),('quota_rate','Part des sites-mois au quota','Quota complet / lignes site-mois du portefeuille','.1%'),('site_visits','Visites avec ASC','Rapports déclarés, pas personnes distinctes',',d'),('community_visits','Visites sans ASC','Rapports déclarés sur les sites du portefeuille',',d'),('feedbacks','Entretiens individuels','Rapports déclarés sur les sites du portefeuille',',d')]
 for key,title,sub,fmt in cards:b.chart(key,title,ds,'big_number_total',metric='sites' if key=='unique_sites' else key,header_font_size=.4,subheader_font_size=.13,y_axis_format=fmt,subheader=sub)
 b.row(p,'cards1',[(k,4) for k,*_ in cards[:3]],24);b.row(p,'cards2',[(k,4) for k,*_ in cards[3:]],24)
 b.chart('regions','Quota mensuel — comparaison régionale du portefeuille',ds,'echarts_timeseries_bar',x_axis='region',orientation='horizontal',**bar)
 b.chart('trend','Évolution DISC — tous les mois disponibles',ds,'echarts_timeseries_line',x_axis='reported_month',time_grain_sqla='P1M',time_range='No filter',seriesType='line',markerEnabled=True,x_axis_time_format='%b %Y',**bar)
 b.row(p,'region',[('regions',6),('trend',6)],55)
 d=b.tab('lists','Territoires et actions')
 b.note(d,'how','''## Passer du constat à la liste des sites
**État du quota mensuel** filtre les listes et l’export, sans modifier les cartes ni les dénominateurs de la synthèse. Sélectionnez « Quota incomplet » et « Aucun des trois formulaires » pour obtenir tous les sites-mois hors quota. Le second statut cible ceux sans activité déclarée parmi ces trois formulaires. Les manques correspondent au minimum mensuel, pas à une tâche clinique calculée.
Les superviseurs et rattachements sont ceux du répertoire courant ; aucune affectation historique n’est inventée.
Pour télécharger : menu **⋮** du tableau **EXPORT** → **Télécharger** → **Exporter en .CSV** ou **.XLSX**.''',30)
 b.chart('territories','Région, district, CSCOM et zone — quota et activité',ds,groupby=['region','district','cscom','zone'],metrics=['sites','site_months','quota_count','quota_rate','site_visits','community_visits','feedbacks'],**table)
 b.chart('sites','Sites à examiner — une ligne par site et mois',ds,groupby=['reported_month','region','district','cscom','zone','site_name','site_uuid','supervisor_name','assignment_label','quota_status'],metrics=['site_visits','community_visits','feedbacks','missing_site_visits','missing_community_visits','missing_feedbacks'],**table)
 export_cols=['reported_month','region','region_uuid','district_name','district_uuid','cscom_name','health_area_uuid','zone_name','supervisor_area_uuid','site_name','site_uuid','supervisor_name','supervisor_uuid','assignment_label','quota_status','last_activity_at']
 b.chart('export','EXPORT DISC — sites, quotas et arborescence',ds,groupby=export_cols,metrics=['site_visits','community_visits','feedbacks','missing_site_visits','missing_community_visits','missing_feedbacks'],**{**table,'server_pagination':False})
 b.row(d,'territories',[('territories',12)],55);b.row(d,'sites',[('sites',12)],60);b.row(d,'export',[('export',12)],60)
 q=b.tab('method','Méthode et qualité DISC')
 b.note(q,'method','''## Définitions DISC — lot 1
- Grain : **site du portefeuille courant × mois**. Un site peut réapparaître plusieurs mois ; les quotas complets sont des **sites-mois**, les sites distincts sont dédupliqués dans la sélection.
- Quota complet : au moins **1** `visit_chw_site`, **5** `visit_community_without_chw` et **1** `individual_feedback` au même site et au même mois. La présence des trois formulaires avec une seule visite communautaire ne suffit pas.
- Les rapports sont rattachés selon leur **date de déclaration**. Le quota ne prouve ni l’ordre des étapes ni l’appariement à une même supervision ; cette vérification relève du lot qualité.
- Une absence de ces formulaires ne prouve ni une absence de soins ni un site fermé. Les sites créés ou déployés après un mois ancien peuvent apparaître dans cette grille actuelle : ne pas utiliser sa courbe comme un taux de déploiement historique.
- Les affectations de superviseurs sont actuelles. Les conflits et absences restent visibles, sans les attribuer à une personne choisie arbitrairement. Le tableau n’établit pas un classement individuel de performance.
- Les dates disponibles sont celles des **relevés matérialisés existants**. Leur date de déclaration ne certifie pas la dernière synchronisation, ni la fraîcheur technique de la réplication.
- Source DISC uniquement : aucune donnée ASA n’est ajoutée au numérateur ou au dénominateur. Les quotas ASA utilisent un autre périmètre.
''',70)
 b.chart('available','Mois DISC disponibles — périmètre et déclarations',ds,time_range='No filter',groupby=['reported_month'],metrics=['sites','site_months','quota_count','site_visits','community_visits','feedbacks'],**table)
 b.chart('assignment','Rattachement superviseur — contrôle du portefeuille',ds,groupby=['assignment_label'],metrics=['sites','site_months','quota_count'],**table)
 b.row(q,'available',[('available',12)],48);b.row(q,'assignment',[('assignment',12)],36)
 b.finish(filters_for(b,ds))
 b=Board('asa','SD — Historique ASA Mali','sd-historique-asa');ds=datasets['asa_history'];recent=datasets['asa_recent']
 p=b.tab('history','Supervisions 2019–2025')
 b.note(p,'intro','''## Retrouver les supervisions dans ASA Mali
**Source ASA uniquement**, avec sa géographie et ses définitions historiques. Année **2025** par défaut ; choisissez des mois entiers entre **2019 et 2025**. **2026 n’est pas encore préparé dans ce relevé de supervision** ; le lot historique suivant devra l’étendre à partir des formulaires.
L’ancienne « aire de santé » est ici la même structure que la zone de supervision ASA : aucun faux CSCOM DISC n’est affiché.

'''+nav,26)
 cards=[('eligible','Sites-mois actifs ASA','État mensuel retenu par le relevé ASA',',d'),('quota_count','Sites-mois actifs au quota','1 visite ASC + 5 sans ASC + 1 entretien',',d'),('quota_rate','Part au quota — ASA','Somme quotas / somme sites-mois actifs','.1%'),('site_visits','Visites avec ASC — ASA','Rapports des sites actifs selon la source historique',',d'),('community_visits','Visites sans ASC — ASA','Rapports des sites actifs selon la source historique',',d'),('feedbacks','Entretiens — ASA','Rapports des sites actifs selon la source historique',',d')]
 for key,title,sub,fmt in cards:b.chart(key,title,ds,'big_number_total',metric=key,time_range='2025-01-01 : 2026-01-01',header_font_size=.4,subheader_font_size=.13,y_axis_format=fmt,subheader=sub)
 b.row(p,'cards1',[(k,4) for k,*_ in cards[:3]],24);b.row(p,'cards2',[(k,4) for k,*_ in cards[3:]],24)
 b.chart('regions','Part au quota — régions déclarées ASA',ds,'echarts_timeseries_bar',x_axis='region',orientation='horizontal',time_range='2025-01-01 : 2026-01-01',**bar)
 b.chart('history_trend','Évolution ASA — période sélectionnée',ds,'echarts_timeseries_line',x_axis='reported_month',time_grain_sqla='P1M',time_range='2025-01-01 : 2026-01-01',seriesType='line',markerEnabled=True,x_axis_time_format='%b %Y',**bar)
 b.row(p,'region',[('regions',6),('history_trend',6)],55)
 d=b.tab('exports','Territoires et exports ASA')
 b.note(d,'how','''## Exporter une extraction reproductible
Les listes suivent uniquement la **période et la géographie ASA**. Les unités natives et identifiants ASA sont conservés. Une ligne représente une **zone ASA et un mois**, sans détail par site reconstruit artificiellement.
Menu **⋮** du tableau **EXPORT** → **Télécharger** → **Exporter en .CSV** ou **.XLSX**. Les taux sont toujours calculés sur les sommes des numérateurs et dénominateurs, jamais sur la moyenne des pourcentages de zones.''',27)
 b.chart('territories','Territoires ASA — activité et quota',ds,time_range='2025-01-01 : 2026-01-01',groupby=['region','district','zone'],metrics=['eligible','quota_count','incomplete','quota_rate','site_visits','community_visits','feedbacks'],**table)
 asa_cols=['reported_month','region','region_uuid','district_name','district_uuid','zone_name','supervisor_area_uuid','supervisor_contact_id','supervisor_name']
 b.chart('export','EXPORT ASA — supervisions 2019–2025',ds,time_range='2025-01-01 : 2026-01-01',groupby=asa_cols,metrics=['eligible','quota_count','incomplete','quota_rate','site_visits','community_visits','feedbacks','inactive_quota','unknown_creation'],**{**table,'server_pagination':False})
 b.row(d,'territories',[('territories',12)],55);b.row(d,'export',[('export',12)],60)
 r=b.tab('fm','FM et GAVI — source ASA')
 b.note(r,'how','''## Retrouver les deux indicateurs historiques déjà disponibles
Cette source ASA couvre une **autre période** que le relevé de supervisions, jusqu’au dernier mois complet préparé. Réglez la **Période ASA** pour consulter notamment 2026.
La moyenne des VAD curatives est `somme des VAD / somme des sites-mois actifs`, pas une somme des moyennes. Les TDR conformes suivent les anciens champs ASA : date de péremption, quantité de sang, solvant et délai de lecture. Ils ne sont pas assimilés au champ de conformité DISC.
L’effondrement de l’activité ASA en 2026 accompagne la migration ; un zéro ou une baisse ne prouve pas une baisse réelle des soins.''',36)
 b.chart('fm','FM/GAVI ASA — mois et zones',recent,time_range='2025-01-01 : 2026-01-01',groupby=asa_cols,metrics=['eligible','curative_visits','average_visits','rdt_done','rdt_correct','rdt_rate'],**{**table,'server_pagination':False})
 b.chart('fm_available','Période FM/GAVI ASA disponible',recent,time_range='No filter',groupby=[],metrics=['first_month','last_month','rows'],**{**table,'server_pagination':False,'page_length':1})
 b.row(r,'fm_available',[('fm_available',12)],22)
 b.row(r,'fm',[('fm',12)],70)
 q=b.tab('method','Méthode et qualité ASA')
 b.note(q,'method','''## ASA et DISC restent deux séries distinctes
- Historique de supervision : **2019–2025**, état du site reconstitué à partir des activations/désactivations et de la création. L’état de l’intervalle ayant la plus longue intersection avec le mois définit son éligibilité dans cette source ; la durée de plusieurs intervalles de même état n’est pas cumulée. Cette règle devra être réauditée au lot historique. Les sites sans date de création sont signalés.
- Quota : au moins 1 visite avec ASC, 5 visites sans ASC et 1 entretien, au même site et au même mois. Les totaux affichés ne concernent que les sites actifs de ce relevé ; les inactifs avec quota restent dans le contrôle.
- Un total annuel de sites-mois n’est pas un nombre d’ASC uniques. Aucun décompte de personnes n’est déduit des nombres de rapports.
- **2019 et 2021 présentent très peu ou pas de rapports dans ce relevé.** Cela nécessite une vérification de l’archive, des formulaires et de leur réplication avant d’interpréter ces périodes comme une absence d’activité.
- Le répertoire des superviseurs est courant dans la source historique : les mutations de personnes et de zones ne sont pas entièrement reconstituées.
- Les UUID de région ASA sont absents dans les relevés existants. **Les lecteurs territoriaux n’accèdent pas à ces nouvelles sources ASA tant que leur ancien périmètre n’est pas validé** ; les comptes disposant déjà du périmètre national peuvent les consulter. Aucun territoire n’est attribué par simple ressemblance de nom avec DISC.
- Les périodes indiquent la disponibilité des relevés existants ; elles ne certifient pas leur date de rafraîchissement technique. Les nouveaux tableaux lisent ces relevés sans les modifier.
''',75)
 b.chart('available','Archive de supervision ASA — contrôle annuel',ds,time_range='No filter',groupby=['year','region'],metrics=['first_month','last_month','rows','eligible','quota_count','inactive_quota','unknown_creation'],**table)
 b.row(q,'available',[('available',12)],60)
 b.finish(filters_for(b,ds,asa=True))
 b=Board('hub','SD — Espace supervision dédiée','sd-supervision');p=b.tab('start','Choisir la source')
 b.note(p,'intro','''## Piloter la supervision, en respectant l’histoire des données
La migration a été **progressive en 2026** : pilote vers février, centre/sud vers mai, nord vers juillet–août (repères indicatifs). Les données **ASA et DISC restent séparées**, car leurs structures et certaines définitions diffèrent.

### [Piloter les supervisions DISC →](/superset/dashboard/sd-pilotage-disc/)
Quota mensuel, visites avec/sans ASC, entretiens, territoires et listes de sites à examiner. Dernier mois complet par défaut.

[Compétences et 31 indicateurs de qualité DISC →](/superset/dashboard/sd-qualite-disc/)

### [Consulter l’historique ASA →](/superset/dashboard/sd-historique-asa/)
Supervisions 2019–2025, exports natifs ASA et indicateurs FM/GAVI disponibles jusqu’en 2026. Les lacunes d’archives et les différences de périmètre restent visibles.

[Compétences et 31 indicateurs de qualité ASA →](/superset/dashboard/sd-qualite-asa/)

[Ancien dashboard SD](/superset/dashboard/2/) · [Tableaux thématiques ASC](/superset/dashboard/asc-thematiques/)
''',49)
 b.note(p,'lots','''## Travaux par lots
1. **Socle livré :** audit, pilotage DISC, historique ASA déjà disponible, filtres corrigés, unités sites/sites-mois, exports et contrôle des accès.
2. **Supervisions et relances :** prolonger le relevé ASA de supervision sur 2026, vérifier les lacunes 2019/2021, consolider les visites/entretiens par épisode et compléter les listes d’action.
3. **Compétences et qualité — premiers indicateurs livrés :** 31 indicateurs issus de la configuration, avec la dernière visite mensuelle, les réponses absentes et les exports français. À approfondir : appariement des épisodes, communauté/TB et versions des formulaires.
4. **Moyens et pilotage des équipes :** intrants, équipements, supports, retours des ASC et affectations ; classement uniquement après vérification des périmètres et de l’historique des affectations.
''',36)
 b.finish([])
 for d in db.session.query(Dashboard).filter(Dashboard.id.in_([1,2])).all():
  assert originals[d.id]==(d.position_json,d.json_metadata,[c.id for c in d.slices],d.published),'Historical dashboard changed'
 brand_primary_dashboards(db.session)
 db.session.commit()
 print(json.dumps(dict(status='OK',published=args.publish,datasets={k:d.id for k,d in datasets.items()},dashboards=reports),ensure_ascii=False),flush=True)
