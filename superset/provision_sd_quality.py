"""Publish SD quality indicators from each native database; clinical sources stay separate."""
import argparse,json
from superset.app import create_app
from sd_quality_sql import ROOT,CATALOG,CORE,COUNTERS,GEO,SOURCES,TABLE,uid,literal
parser=argparse.ArgumentParser();parser.add_argument('--publish',action='store_true');args=parser.parse_args()
app=create_app()
LABELS={'reports':'Rapports de visite source','site_months':'Sites-mois visités déclarés','score_valid':'Derniers scores exploitables (0–100)',
 'acceptable':'Sites-mois au score ≥ 80','below80':'Sites-mois au score < 80','score_missing':'Derniers scores absents','score_invalid':'Derniers scores invalides',
 'latest_ambiguous':'Dernières visites ambiguës (horodatage identique)','multiple_visits':'Sites-mois avec plusieurs visites','unknown_site_reports':'Rapports sans identifiant de site',
 'unmapped_site_months':'Sites-mois hors répertoire courant','score_basis_unusable':'Scores avec base de calcul inexploitable',
 'score_formula_disagreements':'Scores en écart avec les champs de calcul'}
META=[('entity_key','TEXT','Clé du grain territorial'),('reported_month','DATE','Mois de déclaration'),
 ('region_uuid','TEXT','Identifiant région natif'),('region','TEXT','Région déclarée'),('district_uuid','TEXT','Identifiant district natif'),('district_name','TEXT','District déclaré'),
 ('district','TEXT','District · Région'),('health_area_uuid','TEXT','Identifiant CSCOM DISC'),('cscom_name','TEXT','CSCOM DISC'),('cscom','TEXT','CSCOM · Territoire'),
 ('supervisor_area_uuid','TEXT','Identifiant zone natif'),('zone_name','TEXT','Zone de supervision'),('zone','TEXT','Zone · Territoire'),
 ('mapping_status','TEXT','Rattachement géographique'),('calculated_at','TIMESTAMP WITH TIME ZONE','Calcul du relevé (UTC)')]
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
 original={d.id:(d.position_json,d.json_metadata,[s.id for s in d.slices],d.published) for d in db.session.query(Dashboard).filter(Dashboard.id.in_([1,2])).all()}
 reports=[];datasets=[]
 def dataset(key,title,did,sql,columns,metrics):
  ds=db.session.query(SqlaTable).filter_by(uuid=uid('dataset:'+key)).one_or_none()
  if ds is None:ds=SqlaTable(uuid=uid('dataset:'+key),table_name=title,database_id=did,schema='public');db.session.add(ds)
  assert ds.database_id==did
  ds.sql=sql;ds.main_dttm_col='reported_month';ds.owners=[owner];ds.created_by=ds.changed_by=owner
  ds.description='SD — dernière visite mensuelle native, score et réponses non exploitables visibles ; aucune fusion ASA/DISC. Voir Méthode.'
  for name,kind,label in columns:
   col=next((c for c in ds.columns if c.column_name==name),None)
   if col is None:col=TableColumn(column_name=name);ds.columns.append(col)
   col.type=kind;col.verbose_name=label;col.is_dttm=kind.startswith(('DATE','TIMESTAMP'));col.groupby=col.filterable=True
  for name,label,expression in metrics:
   metric=next((m for m in ds.metrics if m.metric_name==name),None)
   if metric is None:metric=SqlMetric(metric_name=name);ds.metrics.append(metric)
   metric.verbose_name=label;metric.expression=expression
  db.session.flush();datasets.append(ds);return ds
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
    adhoc_filters=[] if key in ['quality','available'] else [dict(expressionType='SQL',clause='WHERE',sqlExpression="mapping_status='Rattaché au répertoire courant'")],extra_form_data={},row_limit=100000)
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
 table=dict(query_mode='aggregate',all_columns=[],server_pagination=True,server_page_length=20,page_length=20,include_search=False,allow_render_html=False,show_cell_bars=False,order_desc=True,table_timestamp_format='%d/%m/%Y',column_config={'rate':{'d3NumberFormat':'.1%'}})
 fresh=[('first_month','Premier mois préparé','MIN(reported_month)'),('last_month','Dernier mois préparé','MAX(reported_month)'),('calculation','Calcul du relevé (UTC)','MAX(calculated_at)')]
 for source,did in SOURCES.items():
  native='DISC' if source=='disc' else 'ASA';period='previous calendar month' if source=='disc' else '2025-01-01 : 2026-01-01'
  metrics=[('c_'+k,LABELS[k],'SUM('+k+')') for k in CORE]
  metrics += [('competence_rate','Compétence ≥ 80 parmi les scores exploitables','1.0*SUM(acceptable)/NULLIF(SUM(score_valid),0)'),
   ('score_coverage','Scores exploitables parmi les sites-mois visités','1.0*SUM(score_valid)/NULLIF(SUM(site_months),0)'),
   ('to_review','Sites-mois avec dernière visite ou score à vérifier','SUM(score_missing+score_invalid+latest_ambiguous)')]+fresh
  for m in CATALOG:
   k=m['key']
   metrics += [('n_'+k,m['label']+' · Numérateur','SUM('+k+'_num)'),('d_'+k,m['label']+' · Dénominateur','SUM('+k+'_den)'),
    ('u_'+k,m['label']+' · Réponses absentes/inutilisables','SUM('+k+'_missing+'+k+'_invalid)')]
  counter_labels={m['key']+'_'+suffix:m['label']+' · '+label for m in CATALOG for suffix,label in [('num','Numérateur'),('den','Dénominateur'),('eligible','Sites-mois concernés'),('missing','Réponses absentes'),('na','Non applicables'),('invalid','Réponses invalides')]}
  facts=dataset(source,'SD Qualité '+native+' — Relevé territorial',did,'SELECT * FROM public.'+TABLE,
   META+[(k,'BIGINT',LABELS.get(k,counter_labels.get(k,k))) for k in COUNTERS],metrics)
  values=','.join('('+','.join([literal(m['key']),literal(m['label']),literal(m['category']),literal(m['note'])]+['f.'+m['key']+'_'+s for s in ['num','den','eligible','missing','na','invalid']])+')' for m in CATALOG)
  long_sql='SELECT '+','.join('f.'+c[0] for c in META)+',i.* FROM public.'+TABLE+' f CROSS JOIN LATERAL (VALUES '+values+')i(indicator_key,indicator,category,definition,numerator,denominator,eligible,missing,not_applicable,invalid)'
  detail=dataset(source+':indicators','SD Qualité '+native+' — Indicateurs',did,long_sql,META+[
   ('indicator_key','TEXT','Code de l’indicateur'),('indicator','TEXT','Indicateur'),('category','TEXT','Thématique'),('definition','TEXT','Définition'),
   ('numerator','BIGINT','Numérateur'),('denominator','BIGINT','Dénominateur renseigné'),('eligible','BIGINT','Sites-mois concernés'),('missing','BIGINT','Réponses absentes'),('not_applicable','BIGINT','Non applicables'),('invalid','BIGINT','Réponses invalides')],
   [('num','Numérateur','SUM(numerator)'),('den','Dénominateur','SUM(denominator)'),('eligible','Sites-mois concernés','SUM(eligible)'),('missing','Réponses absentes','SUM(missing)'),
    ('na','Non applicables','SUM(not_applicable)'),('invalid','Réponses invalides','SUM(invalid)'),('rate','Proportion calculée','1.0*SUM(numerator)/NULLIF(SUM(denominator),0)')]+fresh)
  b=Board(source,'SD — Compétences et qualité · '+native,'sd-qualite-'+source)
  p=b.tab('pilot','Compétence et synthèse')
  b.note(p,'intro','## Compétence des sites visités — '+native+'''
Les résultats portent sur la **dernière visite de chaque site dans le mois**, puis sont regroupés par territoire. Ils ne comptent pas des ASC individuels uniques. Le seuil acceptable est **80 sur 100**, avec le score natif du formulaire.
Choisissez des **mois civils entiers**, le territoire et **Indicateur à explorer**, puis **Appliquer les filtres**. Les séries ASA et DISC restent séparées.

[Espace supervision](/superset/dashboard/sd-supervision/) · [Pilotage DISC](/superset/dashboard/sd-pilotage-disc/) · [Historique ASA](/superset/dashboard/sd-historique-asa/)''',28)
  cards=[('visited','Sites-mois visités','c_site_months','Dernière visite mensuelle identifiable',',d'),
   ('scored','Scores exploitables','c_score_valid','Dernier score numérique entre 0 et 100',',d'),
   ('acceptable','Score ≥ 80','c_acceptable','Sites-mois avec un dernier score acceptable',',d'),
   ('rate_card','Compétence acceptable','competence_rate','Dernier score ≥ 80 / scores exploitables','.1%'),
   ('coverage','Disponibilité du score','score_coverage','Scores exploitables / sites-mois visités','.1%'),
   ('review','À vérifier','to_review','Score absent, invalide ou dernière visite ambiguë',',d')]
  for key,title,metric,sub,fmt in cards:b.chart(key,title,facts,'big_number_total',metric=metric,time_range=period,header_font_size=.4,subheader_font_size=.13,y_axis_format=fmt,subheader=sub)
  b.row(p,'cards1',[(x[0],4) for x in cards[:3]],24);b.row(p,'cards2',[(x[0],4) for x in cards[3:]],24)
  bar=dict(metrics=['rate'],groupby=[],annotation_layers=[],show_legend=False,color_scheme='supersetColors',rich_tooltip=True,y_axis_format='.0%',y_axis_bounds=[0,1],x_axis_sort_series='name',x_axis_sort_series_ascending=True,truncateXAxis=False)
  b.chart('regions','Indicateur choisi — comparaison des régions natives',detail,'echarts_timeseries_bar',x_axis='region',orientation='horizontal',time_range=period,**bar)
  b.chart('trend','Indicateur choisi — mois disponibles',detail,'echarts_timeseries_bar',x_axis='reported_month',time_grain_sqla='P1M',time_range=period,x_axis_time_format='%b %Y',**bar)
  b.row(p,'charts',[('regions',6),('trend',6)],55)
  d=b.tab('indicators','Les 31 indicateurs SD')
  b.note(d,'reading','''## Lire les résultats avec leurs dénominateurs
Ce tableau montre **tous les indicateurs**, selon la période et le territoire. Le choix **Indicateur à explorer** ne le masque pas.
Pour les gestes, les réponses non applicables, absentes ou invalides sont séparées des réponses renseignées. Un dénominateur nul donne une proportion vide, jamais un faux 0 %. Pour les deux indicateurs rapportés à tous les sites-mois visités, les réponses absentes peuvent déjà appartenir au dénominateur : les colonnes ne s’additionnent pas dans tous les cas.
Ces constats décrivent les visites déclarées. Une indisponibilité d’intrant signalée lors d’une visite n’est pas un état de stock en temps réel.''',35)
  b.chart('indicators','31 indicateurs — résultat, base et qualité des réponses',detail,time_range=period,groupby=['category','indicator'],metrics=['num','den','rate','eligible','missing','na','invalid'],**table)
  b.row(d,'indicators',[('indicators',12)],90)
  e=b.tab('export','Territoires et export')
  b.note(e,'how','''## Retrouver le territoire concerné et télécharger
Le premier tableau suit l’**indicateur choisi**. Le tableau **EXPORT** conserve **les 31 indicateurs**, avec leurs numérateurs, dénominateurs et réponses absentes/inutilisables : le sélecteur d’indicateur ne s’y applique pas. Une ligne représente une zone native et un mois, avec le contrôle de rattachement ; aucun nom de patient ou d’ASC n’est exporté.
Menu **⋮ → Télécharger → Exporter en .CSV** ou **Exporter vers Excel**. Les en-têtes portent les libellés français. Les identifiants techniques restent des identifiants.
Les ratios territoriaux sont calculés sur les sommes des numérateurs et dénominateurs ; les pourcentages des zones ne sont pas additionnés ni moyennés.''',34)
  groups=['region','district']+(['cscom'] if source=='disc' else [])+['zone','indicator']
  b.chart('territories','Indicateur choisi — détail territorial',detail,time_range=period,groupby=groups,metrics=['num','den','rate','missing','na','invalid'],**table)
  cols=['reported_month','region','region_uuid','district_name','district_uuid']+(['cscom_name','health_area_uuid'] if source=='disc' else [])+['zone_name','supervisor_area_uuid','mapping_status','calculated_at']
  export_metrics=['c_'+k for k in ['reports','site_months','score_valid','acceptable','below80','score_missing','score_invalid','latest_ambiguous','multiple_visits']]+[prefix+m['key'] for m in CATALOG for prefix in ['n_','d_','u_']]
  b.chart('export','EXPORT '+native+' — tous les indicateurs et l’arborescence',facts,time_range=period,groupby=cols,metrics=export_metrics,**{**table,'server_pagination':False})
  b.row(e,'territories',[('territories',12)],65);b.row(e,'export',[('export',12)],65)
  q=b.tab('method','Méthode et qualité')
  b.note(q,'method','''## Une règle explicite pour les visites multiples
- Les rapports `visit_chw_site` sont dédupliqués par UUID, puis une seule visite est retenue par **site et mois de déclaration** : la plus récente. Les versions de score natives ne sont pas recalculées arbitrairement.
- Deux rapports à la même date la plus récente ne permettent pas d’établir un ordre fiable : le site-mois est **ambigu**, séparé des scores exploitables et des réponses évaluées.
- Un score vide, non numérique, négatif ou supérieur à 100 ne devient pas un zéro. Les écarts avec `applicable_score / (assessed_items × 2) × 100` restent dans le contrôle, sans réécrire le score source.
- La compétence principale utilise **les scores exploitables** comme dénominateur. Un second indicateur utilise **tous les sites-mois visités**, pour retrouver ce dénominateur du target CHT. L’ancien target utilise `find()` et l’ancienne vue peut compter un score favorable parmi plusieurs : leurs résultats ne sont pas assimilés à la dernière visite.
- Les procédures sont évaluées parmi les réponses connues et applicables de la dernière visite. Les anciennes versions peuvent ne pas collecter certains champs ; leurs absences sont visibles.
- La checklist TDR reprend les critères documentés dans le formulaire DISC, avec l’ancienne valeur ASA « 4 » pour le solvant. Elle exige des réponses connues. L’ancienne statistique ASA à cinq critères reste distincte.
- Les noms et rattachements territoriaux sont ceux du répertoire courant de **chaque base**. Aucun déplacement historique n’est reconstitué et aucun CSCOM DISC n’est inventé pour ASA.
- Les synthèses et exports concernent les sites rattachés au répertoire courant. Les autres rapports restent dans le contrôle de rattachement. Les lecteurs régionaux restent limités à leurs droits ; l’historique ASA n’est pas attribué par simple ressemblance des noms de régions.
- Un mois absent des rapports de ce formulaire n’est pas remplacé par un mois à zéro. Les résultats mensuels sont présentés en barres, sans relier artificiellement deux périodes séparées par une lacune.
- Les dates de calcul ne certifient ni la synchronisation des téléphones ni la fraîcheur technique de la réplication amont. Les données cliniques sources ne sont pas modifiées.
''',88)
  b.chart('available','Périodes réellement présentes et calcul du relevé (UTC)',facts,time_range='No filter',groupby=[],metrics=['first_month','last_month','calculation'],**{**table,'server_pagination':False,'page_length':1,'table_timestamp_format':'%d/%m/%Y %H:%M'})
  b.chart('quality','Contrôle des rattachements et scores — période sélectionnée',facts,time_range=period,groupby=['mapping_status'],metrics=['c_'+k for k in CORE],**table)
  b.row(q,'available',[('available',12)],23);b.row(q,'quality',[('quality',12)],55)
  dictionary='### Dictionnaire des 31 indicateurs\n\n| Indicateur | Définition |\n|---|---|\n'+'\n'.join('| '+m['label']+' | '+m['note']+' |' for m in CATALOG)
  b.note(q,'dictionary',dictionary,240)
  prefix='NATIVE_FILTER-sd-quality-'+source+'-'
  filters=[dict(id=prefix+'period',type='NATIVE_FILTER',name='Période '+native,filterType='filter_time',targets=[{}],controlValues={},cascadeParentIds=[],defaultDataMask={'extraFormData':{'time_range':period},'filterState':{'value':period},'ownState':{}},scope={'rootPath':['ROOT_ID'],'excluded':[b.charts['available'].id]},description='Mois civils entiers ; le mois courant incomplet est exclu.')]
  geographic=[('region','Région',[]),('district','District déclaré' if source=='asa' else 'District',['region'])]
  if source=='disc':geographic.append(('cscom','CSCOM',['region','district']))
  geographic.append(('zone','Zone de supervision',[x[0] for x in geographic]))
  for col,label,parents in geographic:
   filters.append(dict(id=prefix+col,type='NATIVE_FILTER',name=label+' '+native,filterType='filter_select',targets=[{'datasetId':facts.id,'column':{'name':col}}],controlValues=dict(enableEmptyFilter=False,defaultToFirstItem=False,multiSelect=True,searchAllOptions=True,inverseSelection=False),defaultDataMask={'extraFormData':{},'filterState':{},'ownState':{}},cascadeParentIds=[prefix+x for x in parents],scope={'rootPath':['ROOT_ID'],'excluded':[]},description='Géographie native '+native+'. Appliquer après sélection.'))
  primary=CATALOG[0]
  filters.append(dict(id=prefix+'indicator',type='NATIVE_FILTER',name='Indicateur à explorer',filterType='filter_select',targets=[{'datasetId':detail.id,'column':{'name':'indicator'}}],controlValues=dict(enableEmptyFilter=True,defaultToFirstItem=False,multiSelect=False,searchAllOptions=True,inverseSelection=False),
   defaultDataMask={'extraFormData':{'filters':[{'col':'indicator','op':'IN','val':[primary['label']]}]},'filterState':{'value':[primary['label']],'label':primary['label']},'ownState':{}},cascadeParentIds=[],scope={'rootPath':['ROOT_ID'],'excluded':[c.id for key,c in b.charts.items() if key not in ['regions','trend','territories']]},description='Le choix s’applique aux graphiques de comparaison, à la tendance et au détail territorial ; les cartes, les 31 indicateurs et l’export conservent leurs mesures.'))
  b.finish(filters)
 apply_regional_security(datasets)
 for d in db.session.query(Dashboard).filter(Dashboard.id.in_([1,2])).all():assert original[d.id]==(d.position_json,d.json_metadata,[s.id for s in d.slices],d.published)
 db.session.commit()
 print(json.dumps(dict(status='OK',published=args.publish,datasets=[d.id for d in datasets],dashboards=reports),ensure_ascii=False),flush=True)
