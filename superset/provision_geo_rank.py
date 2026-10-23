"""Publish DISC geolocation and qualified SD / ASC site comparisons."""
import argparse,json
from superset.app import create_app
from dashboard_branding import brand_primary_dashboards
from geo_rank_sql import uid,TABLES
from reporting_board import board_class
parser=argparse.ArgumentParser();parser.add_argument('--publish',action='store_true');args=parser.parse_args()
app=create_app()
COMMON=[('reported_month','DATE','Mois de déclaration'),('calculated_at','TIMESTAMP WITH TIME ZONE','Calcul du relevé (UTC)'),
 ('region_uuid','TEXT','Identifiant région'),('region','TEXT','Région'),('district_uuid','TEXT','Identifiant district'),('district_name','TEXT','District'),('district','TEXT','District · Région'),
 ('health_area_uuid','TEXT','Identifiant CSCOM'),('cscom_name','TEXT','CSCOM'),('cscom','TEXT','CSCOM · Territoire'),('supervisor_area_uuid','TEXT','Identifiant zone'),('zone_name','TEXT','Zone'),('zone','TEXT','Zone · Territoire'),
 ('site_uuid','TEXT','Identifiant site'),('site_name','TEXT','Site ASC')]
EXTRA={
 'geo':[('gps_reports','BIGINT','Relevés GPS du site'),('first_report','TIMESTAMP WITH TIME ZONE','Premier relevé GPS'),('last_report','TIMESTAMP WITH TIME ZONE','Dernier relevé GPS'),('last_valid_report','TIMESTAMP WITH TIME ZONE','Dernières coordonnées exploitables déclarées'),('gps_status','TEXT','État des coordonnées'),('gps_valid','BIGINT','Coordonnées exploitables'),('outside_envelope','BIGINT','Hors rectangle de contrôle Mali'),('older_year','BIGINT','Dernier relevé exploitable de plus de 12 mois')],
 'asc':[('score_total','NUMERIC','Somme des scores exploitables'),('assessed','BIGINT','Mois avec score exploitable'),('acceptable','BIGINT','Mois au score ≥ 80'),('visited','BIGINT','Mois avec visite'),('unusable','BIGINT','Mois avec score absent, invalide ou ambigu')],
 'sd':[('supervisor_uuid','TEXT','Identifiant SD courant'),('supervisor_name','TEXT','SD courant'),('assignment_status','TEXT','Code affectation'),('assignment_label','TEXT','État de l’affectation'),('quota','BIGINT','Quota complet'),('visited','BIGINT','Visite ASC déclarée'),('site_visits','BIGINT','Rapports de visite ASC'),('community_visits','BIGINT','Rapports de visite sans ASC'),('feedbacks','BIGINT','Rapports d’entretien')]
}
METRICS={
 'geo':[('sites','Sites du répertoire courant','COUNT(*)'),('valid','Sites avec coordonnées exploitables','SUM(gps_valid)'),('coverage','Couverture GPS exploitable','1.0*SUM(gps_valid)/NULLIF(COUNT(*),0)'),('absent','Sites sans relevé GPS',"COUNT(*) FILTER(WHERE gps_status='Sans relevé GPS')"),('review','Sites avec relevé à vérifier',"COUNT(*) FILTER(WHERE gps_status NOT IN ('Sans relevé GPS','Coordonnées exploitables'))"),('outside','Sites hors rectangle de contrôle','SUM(outside_envelope)'),('old','Relevés exploitables de plus de 12 mois','SUM(older_year)')],
 'asc':[('average','Moyenne / 100','SUM(score_total)/NULLIF(SUM(assessed),0)'),('evaluations','Mois évalués','SUM(assessed)'),('acceptable','Mois au score ≥ 80','SUM(acceptable)'),('rate','Mois au seuil ≥ 80','1.0*SUM(acceptable)/NULLIF(SUM(assessed),0)'),('visited','Mois avec visite','SUM(visited)'),('unknown','Mois sans score exploitable','SUM(unusable)'),('coverage','Scores disponibles','1.0*SUM(assessed)/NULLIF(SUM(visited),0)')],
 'sd':[('rate','Quota complet (%)','1.0*SUM(quota)/NULLIF(COUNT(*),0)'),('sites','Sites distincts','COUNT(DISTINCT site_uuid)'),('site_months','Sites-mois','COUNT(*)'),('quota','Quotas complets','SUM(quota)'),('missing','Quotas manquants','COUNT(*)-SUM(quota)'),('visited','Sites-mois avec visite ASC','SUM(visited)'),('site_visits','Rapports de visite ASC','SUM(site_visits)'),('community_visits','Rapports sans ASC','SUM(community_visits)'),('feedbacks','Rapports d’entretien','SUM(feedbacks)')]
}
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
 history=db.session.query(Dashboard).filter_by(id=2).one();reports=[];datasets={}
 originals={d.id:(d.position_json,d.json_metadata,[s.id for s in d.slices],d.published) for d in db.session.query(Dashboard).filter(Dashboard.id.in_([1,2])).all()}
 Board=board_class(db,Dashboard,Slice,owner,history,args.publish,reports,uid)
 for key,(name,_) in TABLES.items():
  ds=db.session.query(SqlaTable).filter_by(uuid=uid('dataset:'+key)).one_or_none()
  if ds is None:ds=SqlaTable(uuid=uid('dataset:'+key),database_id=1,schema='public',table_name={'geo':'DISC — Géolocalisation des sites','sd':'DISC — Comparaison SD du portefeuille courant','asc':'DISC — Compétence observée par site ASC'}[key]);db.session.add(ds)
  assert ds.database_id==1
  ds.sql='SELECT * FROM public.'+name;ds.main_dttm_col='reported_month';ds.owners=[owner];ds.created_by=ds.changed_by=owner
  ds.description='DISC uniquement. Voir la méthode du dashboard ; classement recalculé après filtres et restrictions territoriales. Aucun rang global précalculé.'
  for column,kind,label in COMMON+EXTRA[key]:
   col=next((c for c in ds.columns if c.column_name==column),None)
   if col is None:col=TableColumn(column_name=column);ds.columns.append(col)
   col.type=kind;col.verbose_name=label;col.is_dttm=kind.startswith(('DATE','TIMESTAMP'));col.groupby=col.filterable=True
  for metric,label,expression in METRICS[key]+[('fresh','Calcul du relevé (UTC)','MAX(calculated_at)')]:
   m=next((m for m in ds.metrics if m.metric_name==metric),None)
   if m is None:m=SqlMetric(metric_name=metric);ds.metrics.append(m)
   m.verbose_name=label;m.expression=expression
  db.session.flush();datasets[key]=ds
 apply_regional_security(list(datasets.values()))
 table=dict(query_mode='aggregate',all_columns=[],server_pagination=False,page_length=10,include_search=False,allow_render_html=False,show_cell_bars=False,order_desc=True,
  table_timestamp_format='%d/%m/%Y',column_config={k:{'d3NumberFormat':'.1%'} for k in ['rate','coverage']})
 table['column_config']['average']={'d3NumberFormat':'.1f'}
 for name in ['site_uuid','supervisor_uuid']:table['column_config'][name]={'columnWidth':100,'truncateLongCells':True}
 nav='[← Espace SD](/superset/dashboard/sd-supervision/) · [Géolocalisation](/superset/dashboard/sites-geolocalisation/) · [Top 10 SD](/superset/dashboard/sd-classement-disc/) · [Top 10 sites ASC](/superset/dashboard/asc-classement-disc/)'
 def filters(b,ds,period=None):
  prefix='NATIVE_FILTER-geo-rank-'+b.key+'-';items=[]
  if period:items.append(dict(id=prefix+'period',type='NATIVE_FILTER',name='Période DISC',filterType='filter_time',targets=[{}],controlValues={},cascadeParentIds=[],defaultDataMask={'extraFormData':{'time_range':period},'filterState':{'value':period},'ownState':{}},scope={'rootPath':['ROOT_ID'],'excluded':[]},description='Mois civils complets. Une période trop courte peut rendre le classement vide.'))
  for col,label,parents in [('region','Région',[]),('district','District',['region']),('cscom','CSCOM',['region','district']),('zone','Zone',['region','district','cscom'])]:
   items.append(dict(id=prefix+col,type='NATIVE_FILTER',name=label,filterType='filter_select',targets=[{'datasetId':ds.id,'column':{'name':col}}],controlValues=dict(enableEmptyFilter=False,defaultToFirstItem=False,multiSelect=True,searchAllOptions=True,inverseSelection=False),defaultDataMask={'extraFormData':{},'filterState':{},'ownState':{}},cascadeParentIds=[prefix+p for p in parents],scope={'rootPath':['ROOT_ID'],'excluded':[]},description='Les classements sont recalculés dans ce périmètre, après application des droits.'))
  return items
 def chart(b,key,title,ds,**settings):
  # Board's quality default applies a mapping filter which these datasets do not use.
  b.chart(key,title,ds,**{**table,'adhoc_filters':[],**settings})
 b=Board('geo','Sites ASC — Géolocalisation · DISC','sites-geolocalisation');ds=datasets['geo'];p=b.tab('summary','Couverture et priorités')
 b.note(p,'intro','''## Où compléter ou vérifier la géolocalisation ?
État actuel du **répertoire DISC**, une ligne par site. Le dernier formulaire `location_gps` détermine le statut : coordonnées numériques dans les bornes mondiales, différentes de (0,0), sans ambiguïté de date. Un ancien relevé valide ne masque pas un dernier relevé invalide. Ces contrôles ne certifient ni la précision GPS ni la position réelle du site.
'''+nav,24)
 for key,title,metric,sub,fmt in [('sites','Sites du répertoire','sites','Périmètre courant DISC',',d'),('valid','Coordonnées exploitables','valid','Dernier relevé contrôlé',',d'),('coverage','Couverture GPS','coverage','Sites exploitables / répertoire','.1%'),('absent','Sans relevé GPS','absent','Priorité de collecte',',d'),('review','Relevés à vérifier','review','Coordonnées ou date ambiguës',',d'),('old','Relevés de plus de 12 mois','old','Ancienneté, sans présumer une erreur',',d')]:
  b.chart(key,title,ds,'big_number_total',metric=metric,time_range='No filter',adhoc_filters=[],header_font_size=.4,subheader_font_size=.13,subheader=sub,y_axis_format=fmt)
 b.row(p,'cards1',[('sites',4),('valid',4),('coverage',4)],24);b.row(p,'cards2',[('absent',4),('review',4),('old',4)],24)
 b.chart('regions','Couverture GPS par région',ds,'echarts_timeseries_bar',time_range='No filter',adhoc_filters=[],x_axis='region',orientation='horizontal',groupby=[],metrics=['coverage'],annotation_layers=[],show_legend=False,color_scheme='supersetColors',rich_tooltip=True,y_axis_format='.0%',y_axis_bounds=[0,1],x_axis_sort_series='name',x_axis_sort_series_ascending=True,truncateXAxis=False)
 b.row(p,'regions',[('regions',12)],80)
 e=b.tab('export','Listes et exports')
 chart(b,'territories','Contrôles GPS par région',ds,time_range='No filter',groupby=['region'],metrics=['sites','valid','coverage','absent','review','outside','old'],page_length=20)
 b.row(e,'territories',[('territories',12)],65)
 b.note(e,'how','''## Préparer les corrections
Les deux listes contiennent l’arborescence et les dates des relevés. **⋮ → Télécharger → CSV / Excel**. Aucune coordonnée précise ni information de patient n’est ajoutée à ces jeux de données.
Le contrôle « hors rectangle » utilise seulement latitude 10–26 et longitude −13–5 : c’est un signal de vérification, pas une frontière administrative ni une preuve de site hors du Mali. Une date ancienne ne signifie pas que le site est fermé.
'''+nav,34)
 cols=['region','district','cscom','zone','site_name','site_uuid','gps_status','last_report','last_valid_report']
 for key,title,where in [('todo','EXPORT — Sites sans GPS ou avec relevé à vérifier',"gps_valid=0"),('all','EXPORT — Tous les sites et contrôles GPS','TRUE')]:
  chart(b,key,title,ds,time_range='No filter',groupby=cols,metrics=['outside','old'],adhoc_filters=[dict(expressionType='SQL',clause='WHERE',sqlExpression=where)],row_limit=100000,page_length=20)
  b.row(e,key,[(key,12)],60)
 q=b.tab('method','Méthode et fraîcheur');b.note(q,'method','''## Des formulaires de site, pas la position du superviseur
Le formulaire de géolocalisation du site est distingué du GPS éventuellement saisi pendant une visite SD. Deux derniers rapports de même date rendent le dernier relevé ambigu. Les coordonnées absentes, non numériques, hors bornes ou (0,0) ne comptent pas dans la couverture.
Le dénominateur est le répertoire courant, sans déduire un statut « fonctionnel DHIS2 ». Ce dashboard n’a pas de filtre historique : le relevé décrit l’état actuel. Les filtres territoriaux et droits existants s’appliquent à tous les tableaux et exports.
ASA reste séparé : sa vue GPS existante décrit surtout des positions de visites des superviseurs ; elle n’est pas assimilée à un registre des coordonnées de sites. Aucun regroupement des deux bases.
''',60)
 chart(b,'fresh','Calcul du relevé GPS (UTC)',ds,time_range='No filter',groupby=[],metrics=['fresh']);b.row(q,'fresh',[('fresh',12)],22);b.finish(filters(b,ds))
 for key in ['sd','asc']:
  ds=datasets[key];is_sd=key=='sd';b=Board(key,('SD — Réalisation des supervisions' if is_sd else 'Sites ASC — Compétence observée')+' · DISC',key+'-classement-disc')
  period='previous calendar month'
  # ASC defaults to six complete rolling months; literal date kept out of saved configuration.
  if not is_sd:period='DATEADD(DATETRUNC(DATETIME("today"), month), -6, month) : DATETRUNC(DATETIME("today"), month)'
  score='rate' if is_sd else 'average'
  groups=['supervisor_name','supervisor_uuid'] if is_sd else ['site_name','site_uuid','region','district','cscom','zone']
  metrics=['rate','sites','site_months','quota','missing','visited'] if is_sd else ['average','evaluations','rate','visited','unknown','coverage']
  where="assignment_status='assigned' AND supervisor_uuid IS NOT NULL" if is_sd else 'TRUE'
  minimum='COUNT(DISTINCT site_uuid)>=5' if is_sd else 'SUM(assessed)>=3'
  low='SUM(quota)<COUNT(*)' if is_sd else 'SUM(score_total)/NULLIF(SUM(assessed),0)<80'
  def ranked_filters(having):return [dict(expressionType='SQL',clause='WHERE',sqlExpression=where),dict(expressionType='SQL',clause='HAVING',sqlExpression=having)]
  p=b.tab('top','Top 10 et appui')
  intro=('''Critère : **part des sites-mois au quota complet** (1 visite ASC + 5 visites sans ASC + 1 entretien). Minimum : **5 sites distincts** dans le périmètre sélectionné. Les rapports d’un site-mois peuvent avoir été soumis par plusieurs personnes ; ce résultat est celui du portefeuille associé au SD courant, pas une preuve de son activité individuelle historique.
Les affectations ambiguës ou manquantes sont exclues du classement et visibles dans le contrôle. La sélection Région / District / CSCOM réduit le portefeuille évalué. Les SD sans activité restent présents si leur portefeuille est identifiable.''' if is_sd else '''Critère : **moyenne des derniers scores mensuels exploitables / 100**, minimum **3 mois évalués**. Une seule visite est retenue par site et mois : la dernière, avec exclusion des égalités d’horodatage. Seuil acceptable : **80**.
Ce sont des **sites ASC observés**, pas des personnes ASC uniques : plusieurs agents ou changements peuvent concerner un site. Un score absent, invalide ou ambigu est séparé, jamais transformé en zéro. La couverture des scores est affichée à côté de la moyenne. Les sites non visités ne sont pas évaluables ici.''')
  b.note(p,'intro','## Comparer sur un critère explicite\n'+intro+'\n\n**10 lignes maximum**, recalculées après filtres et droits. Les ex æquo ont la même valeur ; la limite de 10 peut en masquer certains : utiliser l’export complet. Une liste vide signifie « aucun résultat éligible », pas une absence d’activité.\n\n'+nav,43 if is_sd else 43)
  for name,title,desc,having in [('top','Top 10 — '+('portefeuilles au quota le plus élevé' if is_sd else 'scores observés les plus élevés'),True,minimum),('support','Appui prioritaire — 10 '+('portefeuilles hors quota' if is_sd else 'sites au score moyen < 80'),False,minimum+' AND '+low)]:
   chart(b,name,title,ds,time_range=period,groupby=groups if is_sd else ['site_name','site_uuid','district_name','cscom_name'],metrics=metrics if is_sd else ['average','evaluations','rate','coverage'],adhoc_filters=ranked_filters(having),timeseries_limit_metric=score,order_desc=desc,row_limit=10,page_length=10)
   b.row(p,name,[(name,12)],65)
  e=b.tab('export','Export et données insuffisantes')
  b.note(e,'how','''## Examiner l’ensemble des résultats
**EXPORT — Résultats éligibles** contient toutes les lignes du classement, au-delà du top 10. **Données insuffisantes** isole les bases trop petites ; ces lignes ne sont pas assimilées aux performances faibles. Les valeurs nulles restent vides.
Les filtres territoriaux et la période s’appliquent avant les calculs. Export CSV / Excel par le menu ⋮. Choisissez des mois civils entiers ; les données du mois courant sont exclues de la source.
'''+nav,32)
  for name,title,having in [('export','EXPORT — Résultats éligibles',minimum),('small','Données insuffisantes — hors classement','NOT ('+minimum+')')]:
   chart(b,name,title,ds,time_range=period,groupby=groups,metrics=metrics,adhoc_filters=ranked_filters(having),timeseries_limit_metric=score,row_limit=100000,page_length=20);b.row(e,name,[(name,12)],65)
  if is_sd:
   chart(b,'assignment','Contrôle — sites-mois par état d’affectation',ds,time_range=period,groupby=['assignment_label'],metrics=['sites','site_months']);b.row(e,'assignment',[('assignment',12)],35)
  q=b.tab('method','Méthode et limites')
  b.note(q,'method','''## Lire les résultats pour orienter l’appui
'''+intro+'''
Un classement ne résume pas la qualité globale du travail : contexte, taille du portefeuille et conditions de collecte peuvent différer. Les seuils de volume sont des garde-fous de lecture, pas des seuils statistiques validés. Aucun score composite à pondérations arbitraires n’est ajouté.
Les affectations et noms géographiques sont ceux du répertoire courant DISC. Ils ne reconstituent pas les déploiements passés ni les mutations. Pour une comparaison de SD, commencer par le dernier mois complet dans un territoire comparable. Pour les sites ASC, choisir une période assez longue pour atteindre 3 mois de scores.
Les restrictions territoriales sont appliquées avant agrégation et limite de 10. Un lecteur régional ne reçoit pas un classement national filtré après coup. ASA et DISC ne sont pas fusionnés ; le présent lot porte sur DISC.
La date du relevé est celle du calcul, sans certifier la synchronisation du téléphone ni la fraîcheur de toute la chaîne amont.
''',85)
  chart(b,'fresh','Calcul du relevé (UTC)',ds,time_range=period,groupby=[],metrics=['fresh']);b.row(q,'fresh',[('fresh',12)],22);b.finish(filters(b,ds,period))
 # Add discoverable navigation without rebuilding or changing existing chart queries/layouts.
 for slug in ['sd-supervision','sd-pilotage-disc','sd-qualite-disc','asc-pilotage-v2','asc-suivi-operationnel','asc-thematiques']:
  d=db.session.query(Dashboard).filter_by(slug=slug).one_or_none()
  if not d:continue
  layout=json.loads(d.position_json);notes=[v for v in layout.values() if isinstance(v,dict) and v.get('type')=='MARKDOWN']
  if notes:
   code=notes[0]['meta'].get('code','');marker='<!-- geo-ranking-nav -->'
   if marker in code:code=code.split(marker)[0].rstrip()
   notes[0]['meta']['code']=code+'\n\n'+marker+'\n'+nav
   # Leave sufficient vertical room for the new navigation line.
   notes[0]['meta']['height']=max(notes[0]['meta'].get('height',0),40)
   d.position_json=json.dumps(layout,ensure_ascii=False)
 for d in db.session.query(Dashboard).filter(Dashboard.id.in_([1,2])).all():assert originals[d.id]==(d.position_json,d.json_metadata,[s.id for s in d.slices],d.published)
 brand_primary_dashboards(db.session)
 db.session.commit();print(json.dumps(dict(status='OK',published=args.publish,datasets={k:d.id for k,d in datasets.items()},dashboards=reports),ensure_ascii=False),flush=True)
