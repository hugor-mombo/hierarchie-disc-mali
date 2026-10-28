"""Tableau IT privé, sans attribuer le rôle à un utilisateur."""
import argparse,json
from sqlalchemy import text
from superset.app import create_app
from maintenance_catalog import ROOT,ROLE,SLUG,TABLES,METRICS,uid
from reporting_board import board_class
from dashboard_branding import brand_dashboard
parser=argparse.ArgumentParser();parser.add_argument('--publish',action='store_true');args=parser.parse_args()
app=create_app()
LABELS={
 'username':'Compte DISC','roles':'Rôles DISC','device_id':'Identifiant applicatif appareil','account_status':'État du compte',
 'region':'Région','district':'District · Région','cscom':'CSCOM · Territoire','zone':'Zone · Territoire','site_name':'Site ASC',
 'facility_id':'Identifiant structure du compte','mapping_status':'Rattachement géographique',
 'model':'Modèle','manufacturer':'Fabricant','android_version':'Version Android','apk_version':'Version APK','cht_version':'Version CHT','chrome_version':'Version Chrome','device_type':'Type d’appareil',
 'telemetry_day':'Jour de télémétrie déclaré','telemetry_age_days':'Ancienneté télémétrie (jours)',
 'last_upload_day':'Dernier jour avec émission réussie observée','last_download_day':'Dernier jour avec réception réussie observée',
 'storage_status':'État du stockage selon seuils IT','telemetry_status':'Ancienneté de télémétrie',
 'free_gib':'Espace libre (Gio)','total_gib':'Capacité totale (Gio)','free_ratio':'Part libre',
 'storage_valid':'Mesure disque exploitable','latest_ambiguous':'Dernière mesure ambiguë / conflictuelle',
 'future_documents':'Documents datés dans le futur','invalid_date_documents':'Documents à date inexploitable',
 'clock_reports_7d':'Documents avec écart horloge signalé · 7 jours','clock_abs_minutes_7d':'Écart absolu maximal signalé · 7 jours (min)',
 'failure_events_7d':'Échecs de réplication · 7 jours','denied_events_7d':'Documents refusés à l’émission · 7 jours',
 'calculated_at':'Calcul du relevé (UTC)','telemetry_id':'Identifiant télémétrie','source_conflicted':'Télémétrie marquée conflicted',
 'to_success':'Émissions réussies enregistrées','from_success':'Réceptions réussies enregistrées',
 'to_failure':'Émissions échouées enregistrées','from_failure':'Réceptions échouées enregistrées',
 'offline_client':'Émission : appareil hors ligne','offline_server':'Émission : serveur injoignable','replication_errors':'Émission : autres erreurs',
 'denied':'Documents refusés à l’émission','clock_count':'Signaux horloge dans le document','clock_min_minutes':'Écart minimal signalé (min)','clock_max_minutes':'Écart maximal signalé (min)',
 'next_action':'Vérification proposée'
}
DEVICE_COLS=[k for k in LABELS if k not in ['telemetry_id','source_conflicted','to_success','from_success','to_failure','from_failure','offline_client','offline_server','replication_errors','denied','clock_count','clock_min_minutes','clock_max_minutes','next_action']]
DEVICE_SQL='SELECT '+','.join(DEVICE_COLS)+""",CASE
 WHEN device_id IS NULL THEN 'Vérifier le compte et la remontée des métadonnées'
 WHEN telemetry_day IS NULL OR telemetry_day>CURRENT_DATE THEN 'Vérifier la date de la tablette et la télémétrie'
 WHEN telemetry_age_days>7 THEN 'Contacter le terrain et vérifier la remontée de télémétrie'
 WHEN storage_status='Critique (< 1 Gio)' THEN 'Examiner le stockage avec le détenteur ; aucune suppression automatique'
 WHEN clock_reports_7d>0 THEN 'Vérifier date, heure et réglage automatique sur la tablette'
 WHEN failure_events_7d>0 OR denied_events_7d>0 THEN 'Examiner connexion, droits et journal local avec le détenteur'
 WHEN storage_valid<>1 OR latest_ambiguous=1 THEN 'Actualiser ou vérifier les mesures de l’appareil'
 ELSE 'Surveiller selon les seuils IT' END AS next_action FROM public."""+TABLES['devices']
EVENT_COLUMNS=['telemetry_id','username','device_id','telemetry_day','source_conflicted','to_success','from_success','to_failure','from_failure','offline_client','offline_server','replication_errors','denied','clock_count','calculated_at']
EVENT_GEO=['account_status','region','district','cscom','zone','site_name','device_type']
EVENT_SQL='SELECT '+','.join('e.'+x for x in EVENT_COLUMNS)+','+','.join('d.'+x for x in EVENT_GEO)+',e.clock_min_ms/60000.0 AS clock_min_minutes,e.clock_max_ms/60000.0 AS clock_max_minutes FROM public.'+TABLES['events']+' e LEFT JOIN public.'+TABLES['devices']+' d USING(username,device_id)'
with app.test_request_context('/'):
 from flask import g
 from flask_login import login_user
 from superset import db,security_manager as sm
 from superset.connectors.sqla.models import SqlaTable,TableColumn,SqlMetric,RowLevelSecurityFilter
 from superset.models.dashboard import Dashboard
 from superset.models.slice import Slice
 from superset.models.core import Database
 owner=sm.find_user(username='hmombo');assert owner;login_user(owner);g.user=owner
 before={d.id:(d.position_json,d.json_metadata,d.published,sorted(r.id for r in d.roles)) for d in db.session.query(Dashboard) if d.slug!=SLUG}
 user_roles_before={u.id:sorted(r.id for r in u.roles) for u in db.session.query(sm.user_model)}
 role=sm.find_role(ROLE) or sm.add_role(ROLE)
 datasets={}
 for key,sql,columns in [('devices',DEVICE_SQL,DEVICE_COLS+['next_action']),('events',EVENT_SQL,EVENT_COLUMNS+EVENT_GEO+['clock_min_minutes','clock_max_minutes'])]:
  ds=db.session.query(SqlaTable).filter_by(uuid=uid('dataset:'+key)).one_or_none()
  if ds is None:ds=SqlaTable(uuid=uid('dataset:'+key),table_name='IT DISC — '+('Appareils et comptes' if key=='devices' else 'Télémétrie quotidienne'),database_id=1,schema='public');db.session.add(ds)
  ds.sql=sql;ds.main_dttm_col='telemetry_day';ds.description='Monitoring IT privé. Métadonnées techniques, sans données cliniques ni logs libres. Voir Méthode du tableau.';ds.owners=[owner];ds.created_by=ds.changed_by=owner
  for name in columns:
   col=next((c for c in ds.columns if c.column_name==name),None)
   if col is None:col=TableColumn(column_name=name);ds.columns.append(col)
   col.type='TIMESTAMP WITH TIME ZONE' if name=='calculated_at' else 'DATE' if name.endswith('_day') else 'BOOLEAN' if name=='source_conflicted' else 'TEXT' if name in ['telemetry_id','username','device_id','roles','account_status','region','district','cscom','zone','site_name','facility_id','mapping_status','model','manufacturer','android_version','apk_version','cht_version','chrome_version','device_type','storage_status','telemetry_status','next_action'] else 'NUMERIC'
   col.verbose_name=LABELS[name];col.is_dttm=col.type in ['DATE','TIMESTAMP WITH TIME ZONE'];col.groupby=col.filterable=True
  definitions=METRICS[key]+([] if key=='devices' else [
   ('future','Documents à période future','COUNT(*) FILTER(WHERE telemetry_day>CURRENT_DATE)'),
   ('undated','Documents à date inexploitable','COUNT(*) FILTER(WHERE telemetry_day IS NULL)'),
   ('no_identity','Documents sans compte ou identifiant appareil','COUNT(*) FILTER(WHERE username IS NULL OR device_id IS NULL)'),
   ('conflicted','Documents marqués conflicted','COUNT(*) FILTER(WHERE source_conflicted)'),
   ('source_latest','Dernier jour plausible observé','MAX(telemetry_day) FILTER(WHERE telemetry_day<=CURRENT_DATE)')])
  for name,label,expression in definitions:
   m=next((m for m in ds.metrics if m.metric_name==name),None)
   if m is None:m=SqlMetric(metric_name=name);ds.metrics.append(m)
   m.verbose_name=label;m.expression=expression
  db.session.flush();datasets[key]=ds
  permission=sm.add_permission_view_menu('datasource_access',ds.perm)
  if permission not in role.permissions:role.permissions.append(permission)
 deny=db.session.query(RowLevelSecurityFilter).filter_by(name='DISC_IT_DEFAULT_DENY').one_or_none()
 if deny is None:deny=RowLevelSecurityFilter(name='DISC_IT_DEFAULT_DENY',filter_type='Base',clause='1 = 0');db.session.add(deny)
 deny.roles=[role,sm.find_role('Admin')];deny.tables=list(datasets.values())
 # This role receives no authoring, SQL Lab, global database or clinical-data access.
 assert all(p.permission.name=='datasource_access' for p in role.permissions)
 Board=board_class(db,Dashboard,Slice,owner, type('Audience',(),{'roles':[role]})(),args.publish,[],uid)
 b=Board('maintenance','DISC — Monitoring et maintenance IT',SLUG);b.dash.roles=[role]
 standard=dict(query_mode='aggregate',all_columns=[],percent_metrics=[],server_pagination=False,page_length=20,
  show_cell_bars=False,allow_render_html=False,include_search=False,table_timestamp_format='%d/%m/%Y',row_limit=100000)
 def chart(key,title,source='devices',viz='table',where=None,**settings):
  ds=datasets[source]
  p={**(standard if viz=='table' else {}),'time_range':'No filter','granularity_sqla':'telemetry_day','adhoc_filters':[],'row_limit':100000}
  if where:p['adhoc_filters']=[dict(expressionType='SQL',clause='WHERE',sqlExpression=where)]
  p.update(settings);return b.chart(key,title,ds,viz,**p)
 intro=b.tab('summary','Vue d’ensemble')
 b.note(intro,'intro','''## Maintenance des appareils et de la remontée technique
Accès réservé à **hmombo et aux personnes IT désignées**. Les filtres utilisent les **comptes courants** et leur rattachement actuel. Le suivi porte sur les profils compte–appareil observés ; un appareil peut être partagé.

Les alertes disque exigent une mesure non ambiguë âgée de **7 jours au plus**. Réplications et horloges : **7 derniers jours civils, aujourd’hui inclus**. **Vérifiez la couverture récente avant d’interpréter un zéro d’alerte : une mesure ancienne ne décrit pas le parc actuel.**
''',26)
 cards=[('devices','Appareils distincts observés','device_id applicatif, toutes anciennetés'),('no_telemetry','Comptes sans télémétrie','Comptes courants ; ne signifie pas tablette absente'),('recent','Télémétrie ≤ 7 jours','Au moins un profil récent de l’appareil'),('old','Télémétrie > 7 jours','Peut comprendre un ancien profil d’appareil partagé'),('critical','Stockage critique récent','Moins de 1 Gio libre'),('low','Stockage à surveiller','Moins de 2 Gio ou moins de 10 % libre'),('clock','Écart horloge signalé · 7 jours','Profils avec signal client-date-offset'),('failures','Échec de réplication · 7 jours','Profils avec échec enregistré, pas une panne permanente')]
 for key,title,sub in cards:chart('kpi_'+key,title,viz='big_number_total',metric=key,subheader=sub,y_axis_format=',d',header_font_size=.42,subheader_font_size=.13)
 b.row(intro,'cards1',[('kpi_'+x[0],3) for x in cards[:4]],28);b.row(intro,'cards2',[('kpi_'+x[0],3) for x in cards[4:]],28)
 quality_cards=[('storage_known','Mesure disque récente exploitable','Base réellement observable des alertes disque'),('denied','Document refusé · 7 jours','Profils concernés, à distinguer des pannes réseau'),('ambiguous','Dernière mesure ambiguë','Données à vérifier, pas de stockage choisi arbitrairement'),('bad_dates','Date source inexploitable','Profils avec période de télémétrie à examiner')]
 for key,title,sub in quality_cards:chart('kpi_'+key,title,viz='big_number_total',metric=key,subheader=sub,y_axis_format=',d',header_font_size=.42,subheader_font_size=.13)
 b.row(intro,'cards3',[('kpi_'+x[0],3) for x in quality_cards],28)
 chart('source_dates','Fraîcheur du calcul et de la télémétrie disponible',metrics=['calculated','source_latest'],groupby=[]);b.row(intro,'source_dates',[('source_dates',12)],24)
 chart('regions','Repères de maintenance par région',groupby=['region'],metrics=['devices','critical','low','old','no_telemetry']);b.row(intro,'regions',[('regions',12)],62)
 export=b.tab('priorities','Priorités et exports')
 b.note(export,'how','''## Préparer les interventions IT
Filtrez **Région → District → CSCOM**, puis un compte ou un type d’appareil. Les filtres **Stockage à examiner** et **Ancienneté à examiner** isolent les cas souhaités dans les listes ; ils ne réduisent pas les cartes de synthèse ni les séries quotidiennes. Les listes conservent l’arborescence et les identifiants nécessaires à la vérification, sans téléphone ni contenu de rapport clinique.
**⋮ → Télécharger → CSV / Excel** exporte la sélection complète dans la limite contrôlée de 100 000 lignes. Les cas sans télémétrie, les mesures anciennes et les dernières mesures ambiguës restent identifiables. Les motifs peuvent se cumuler ; les cartes ne s’additionnent pas pour donner un total d’incidents uniques.
Aucune correction d’heure, suppression de fichier ou modification de tablette n’est effectuée automatiquement.
''',36)
 columns=['region','district','cscom','zone','site_name','username','roles','device_id','device_type','model','telemetry_day','telemetry_age_days','last_upload_day','last_download_day','free_gib','free_ratio','storage_status','clock_reports_7d','clock_abs_minutes_7d','failure_events_7d','denied_events_7d','future_documents','latest_ambiguous','mapping_status','next_action','calculated_at']
 priority="device_id IS NULL OR telemetry_age_days>7 OR telemetry_day IS NULL OR telemetry_day>CURRENT_DATE OR latest_ambiguous=1 OR storage_valid<>1 OR clock_reports_7d>0 OR failure_events_7d>0 OR denied_events_7d>0 OR future_documents>0 OR (telemetry_age_days<=7 AND free_gib IS NOT NULL AND (free_gib<2 OR free_ratio<0.1))"
 chart('priorities','EXPORT — Profils et comptes à examiner',groupby=columns,metrics=[],where=priority)
 chart('all','EXPORT — Tous les profils compte–appareil sélectionnés',groupby=columns,metrics=[])
 b.row(export,'priorities',[('priorities',12)],80);b.row(export,'all',[('all',12)],70)
 sync=b.tab('sync','Synchronisations enregistrées')
 b.note(sync,'sync','''## Des événements techniques, à la résolution du jour
La source agrège la télémétrie par jour déclaré. Le **dernier jour avec émission/réception réussie observée** est le dernier jour contenant un compteur de succès dans le sens concerné. Ce n’est ni l’heure exacte de dernière synchronisation ni une garantie que tous les documents ont été transférés.
Les essais réussis/échoués proviennent du champ **count** des métriques de réplication, pas de leur somme de durées. Les motifs d’échec d’émission proviennent de leur **sum**. Une même journée peut avoir des réussites et des échecs. Les dates restent dépendantes de l’horloge du client.
Le filtre **Période de télémétrie** s’applique aux graphiques quotidiens de cet onglet et à la liste d’horloge quotidienne, pas aux états actuels des appareils.
''',40)
 period='DATEADD(DATETRUNC(DATETIME("today"), day), -29, day) : DATEADD(DATETRUNC(DATETIME("today"), day), 1, day)'
 chart('sync_trend','Émissions, réceptions et échecs enregistrés',source='events',viz='echarts_timeseries_bar',time_range=period,x_axis='telemetry_day',time_grain_sqla='P1D',metrics=['to_success','from_success','failures'],groupby=[],annotation_layers=[],show_legend=True,color_scheme='supersetColors',rich_tooltip=True,y_axis_format=',d',where='telemetry_day<=CURRENT_DATE')
 chart('sync_reasons','Motifs enregistrés des échecs d’émission',source='events',time_range=period,groupby=['telemetry_day'],metrics=['offline_client','offline_server','errors','denied'],where='telemetry_day<=CURRENT_DATE')
 chart('last_sync','EXPORT — Derniers jours de succès observés',groupby=['region','district','cscom','username','device_id','last_upload_day','last_download_day','telemetry_day','telemetry_status'],metrics=[])
 b.row(sync,'trend',[('sync_trend',12)],65);b.row(sync,'reasons',[('sync_reasons',12)],55);b.row(sync,'last',[('last_sync',12)],65)
 clock=b.tab('clock','Horloges et dates')
 b.note(clock,'clock','''## Identifier les signaux à vérifier sur les tablettes
**client-date-offset** signale un écart entre heure client et serveur, uniquement lorsque CHT décide de l’enregistrer. Son absence **ne certifie pas une horloge correcte**. L’écart absolu maximal est converti des millisecondes en minutes ; les bornes du jour ne sont pas une mesure instantanée.
Une période de télémétrie dans le futur est une anomalie de date distincte. Sans horodatage fiable de réception serveur, les horloges très retardées peuvent aussi rendre les journées anciennes : ne pas conclure à une déconnexion à partir de cette seule donnée.
''',38)
 chart('clock_profiles','EXPORT — Profils avec signal horloge ou anomalie de date',groupby=['region','district','cscom','username','device_id','telemetry_day','clock_reports_7d','clock_abs_minutes_7d','future_documents','invalid_date_documents'],metrics=[],where='clock_reports_7d>0 OR future_documents>0 OR invalid_date_documents>0')
 chart('clock_daily','Signaux horloge par jour déclaré',source='events',time_range=period,groupby=['telemetry_day','username','device_id','clock_min_minutes','clock_max_minutes'],metrics=['clock'],where='clock_count>0 AND telemetry_day<=CURRENT_DATE')
 b.row(clock,'profiles',[('clock_profiles',12)],65);b.row(clock,'daily',[('clock_daily',12)],65)
 inventory=b.tab('versions','Parc et versions')
 b.note(inventory,'versions','''## Préparer les mises à jour et l’assistance
Les versions CHT, APK, Android et Chrome sont celles de la dernière télémétrie du profil, pas une vérification en direct. Les dernières dates ambiguës sont exclues de ces distributions. Une valeur absente reste non renseignée ; aucun numéro de version arbitraire n’est désigné comme obsolète.
Plusieurs profils peuvent correspondre au même appareil partagé. À l’inverse, les comptes sans télémétrie ne permettent pas de déduire un modèle ou un numéro de série.
''',32)
 for key,title,cols in [('models','Fabricants et modèles',['device_type','manufacturer','model','android_version']),('apps','Versions des applications',['cht_version','apk_version','chrome_version']),('age','Ancienneté des métadonnées',['telemetry_status'])]:
  chart(key,title,groupby=cols,metrics=['devices','profiles'],where='latest_ambiguous=0' if key!='age' else None);b.row(inventory,key,[(key,12)],55)
 method=b.tab('method','Méthode et fiabilité')
 b.note(method,'method','''## Périmètre, seuils et limites
- Source : `couchdb_users_meta`, documents **telemetry** non supprimés. Les messages **feedback**, journaux libres, dossiers cliniques et champs d’authentification sont exclus.
- Une ligne de suivi représente un **couple compte–deviceId**, ou un compte courant sans télémétrie. Le deviceId est un identifiant applicatif, pas un IMEI ou un numéro d’inventaire certifié.
- Comptes courants : utilisateurs DISC non supprimés/désactivés, hors noms contenant formation. Les anciens comptes observés restent consultables en changeant le filtre. Les droits Superset ne sont pas des rôles DISC.
- Dernière mesure : jour plausible le plus récent du couple. Deux documents de même jour ou un document marqué conflicted rendent cette dernière mesure ambiguë. Le stockage est alors laissé vide, sans choix arbitraire ni reprise d’une ancienne mesure valide.
- Stockage exploitable : octets numériques, total > 0, libre entre 0 et total. **1 Gio = 1 073 741 824 octets**. Critique : libre < 1 Gio. À surveiller : libre < 2 Gio ou part libre < 10 %. Ce sont des seuils IT de revue, pas des spécifications du fabricant.
- Les cartes disque ne comptent que les dernières mesures âgées de **7 jours au plus**. Les listes conservent les mesures plus anciennes, avec leur date. Un ancien disque faible ne prouve pas un disque faible aujourd’hui.
- Les signaux horloge/échec/refus des profils concernent **aujourd’hui et les 6 jours précédents**. Les jours futurs sont exclus de ces fenêtres et signalés séparément. Aucune heure exacte de synchronisation n’est reconstituée.
- La géographie est celle du compte et du répertoire courant. Les branches ambiguës et les comptes hors répertoire restent visibles sans rattachement inventé.
- Le filtre de période ne concerne que les séries quotidiennes. Les contrôles de source ci-dessous sont **globaux, toutes périodes**, et ignorent les filtres pour permettre de voir les données non attribuables.
- Les relevés IT sont préparés et remplacés dans une transaction propre. Un échec conserve le dernier calcul validé. La date du calcul ne certifie pas l’actualisation de la réplication CouchDB → PostgreSQL.

Documentation de référence : [Télémétrie CHT](https://docs.communityhealthtoolkit.org/apps/guides/performance/telemetry/).
''',115)
 chart('freshness','Dernier calcul IT et dernier jour source plausible',metrics=['calculated','source_latest'],groupby=[])
 chart('quality','Contrôles globaux des documents techniques',source='events',groupby=[],metrics=['documents','no_identity','undated','future','conflicted','source_latest','calculated'])
 b.row(method,'freshness',[('freshness',12)],25);b.row(method,'quality',[('quality',12)],30)
 filters=[];prefix='NATIVE_FILTER-IT-'
 daily=[b.charts[k].id for k in ['sync_trend','sync_reasons','clock_daily']]
 filters.append(dict(id=prefix+'period',type='NATIVE_FILTER',name='Période de télémétrie quotidienne',filterType='filter_time',targets=[{}],controlValues={},cascadeParentIds=[],defaultDataMask={'extraFormData':{'time_range':period},'filterState':{'value':period},'ownState':{}},scope={'rootPath':['ROOT_ID'],'excluded':[c.id for c in b.charts.values() if c.id not in daily]},description='Uniquement séries et signaux quotidiens ; ne filtre pas les derniers états des appareils.'))
 for col,label,parents,default in [('account_status','État du compte',[],['Compte courant']),('region','Région',[],None),('district','District',['region'],None),('cscom','CSCOM',['region','district'],None),('device_type','Type d’appareil',[],None),('username','Compte DISC',[],None)]:
  filters.append(dict(id=prefix+col,type='NATIVE_FILTER',name=label,filterType='filter_select',targets=[{'datasetId':datasets['devices'].id,'column':{'name':col}}],controlValues=dict(enableEmptyFilter=False,defaultToFirstItem=False,multiSelect=True,searchAllOptions=True,inverseSelection=False),cascadeParentIds=[prefix+x for x in parents],defaultDataMask={'extraFormData':{'filters':[{'col':col,'op':'IN','val':default}]} if default else {},'filterState':{'value':default,'label':', '.join(default)} if default else {},'ownState':{}},scope={'rootPath':['ROOT_ID'],'excluded':[b.charts['quality'].id]},description='Rattachement courant. Le contrôle global de source ignore ce filtre.'))
 for col,label,targets in [('storage_status','Stockage à examiner',['priorities','all']),('telemetry_status','Ancienneté à examiner',['priorities','all','last_sync'])]:
  ids={b.charts[k].id for k in targets}
  filters.append(dict(id=prefix+col,type='NATIVE_FILTER',name=label,filterType='filter_select',targets=[{'datasetId':datasets['devices'].id,'column':{'name':col}}],controlValues=dict(enableEmptyFilter=False,defaultToFirstItem=False,multiSelect=True,searchAllOptions=True,inverseSelection=False),cascadeParentIds=[],defaultDataMask={'extraFormData':{},'filterState':{},'ownState':{}},scope={'rootPath':['ROOT_ID'],'excluded':[c.id for c in b.charts.values() if c.id not in ids]},description='Filtre les listes uniquement. Une mesure disque ancienne doit être relue avec sa date. Les cartes et les séries quotidiennes conservent leur périmètre.'))
 b.finish(filters);brand_dashboard(b.dash)
 assert before=={d.id:(d.position_json,d.json_metadata,d.published,sorted(r.id for r in d.roles)) for d in db.session.query(Dashboard) if d.slug!=SLUG},'Autre tableau modifié'
 assert user_roles_before=={u.id:sorted(r.id for r in u.roles) for u in db.session.query(sm.user_model)},'Attribution de rôle non demandée'
 db.session.commit()
 print(json.dumps(dict(status='OK',dashboard_id=b.dash.id,slug=SLUG,published=b.dash.published,charts=len(b.charts),datasets={k:d.id for k,d in datasets.items()},it_role=ROLE,role_assignments_changed=False)),flush=True)
