"""Native SEBAC operational pilotage; historical dashboard remains unchanged."""
import argparse,json
from superset.app import create_app
from sebac_sql import TABLES,FORMS,uid
from reporting_board import board_class
from regional_security import apply_regional_security
from dashboard_branding import brand_primary_dashboards
parser=argparse.ArgumentParser();parser.add_argument('--publish',action='store_true');args=parser.parse_args();app=create_app()
GEO=[('region_uuid','TEXT','Identifiant région'),('region','TEXT','Région'),('district_uuid','TEXT','Identifiant district'),('district_name','TEXT','District'),('district','TEXT','District · Région'),('health_area_uuid','TEXT','Identifiant CSCOM'),('cscom_name','TEXT','CSCOM'),('cscom','TEXT','CSCOM · Territoire'),('supervisor_area_uuid','TEXT','Identifiant zone'),('zone_name','TEXT','Zone'),('zone','TEXT','Zone · Territoire'),('site_uuid','TEXT','Identifiant site'),('site_name','TEXT','Site ASC'),('mapping_status','TEXT','Rattachement'),('reported_month','DATE','Mois de déclaration / notification'),('calculated_at','TIMESTAMP WITH TIME ZONE','Calcul du relevé (UTC)')]
EXTRA={
 'reports':[('report_uuid','TEXT','Identifiant rapport'),('form','TEXT','Code formulaire'),('stage','TEXT','Étape SEBAC'),('reported_at','TIMESTAMP WITH TIME ZONE','Enregistrement du rapport'),('alert_id','TEXT','Identifiant alerte'),('actor','TEXT','Acteur déclarant'),('mpe','TEXT','MPE déclarée'),('event','TEXT','Événement déclaré'),('classification','TEXT','Code classification'),('checked','TEXT','Vérifiée déclarée'),('validated','TEXT','Validée déclarée'),('human_deaths','BIGINT','Personnes décédées déclarées'),('animal_deaths','BIGINT','Animaux décédés déclarés'),('date_status','TEXT','Contrôle de date'),('input_conflict','BOOLEAN','Champs source contradictoires'),('stage_link_status','TEXT','Contrôle de liaison')],
 'alerts':[('alert_key','TEXT','Clé analytique alerte'),('alert_id','TEXT','Identifiant alerte'),('first_report_reference','TEXT','Référence de rapport'),('notified_at','TIMESTAMP WITH TIME ZONE','Premier signalement enregistré'),('last_notification_at','TIMESTAMP WITH TIME ZONE','Dernier signalement enregistré'),('notification_reports','BIGINT','Rapports de signalement'),('identity_status','TEXT','Contrôle identité alerte'),('actor','TEXT','Acteur du signalement'),('is_mpe','BOOLEAN','Au moins un signalement MPE'),('is_event','BOOLEAN','Au moins un signalement événement'),('type_incomplete','BOOLEAN','Type incomplet'),('sorted_at','TIMESTAMP WITH TIME ZONE','Premier tri enregistré'),('verified_at','TIMESTAMP WITH TIME ZONE','Première vérification enregistrée'),('test_result_at','TIMESTAMP WITH TIME ZONE','Premier formulaire résultat de test'),('verification_reports','BIGINT','Rapports de vérification liés'),('sort_reports','BIGINT','Rapports de tri liés'),('checked_reports','BIGINT','Rapports avec vérifiée = oui'),('validated_reports','BIGINT','Rapports avec validée = oui'),('tri_class','TEXT','Dernière classification du tri'),('workflow_status','TEXT','État du suivi enregistré'),('verification_hours','NUMERIC','Délai d’enregistrement vérification (heures)'),('age_days','BIGINT','Jours depuis le premier signalement'),('review_72h','BIGINT','À examiner après 72 heures')],
 'sites':[('last_notification','TIMESTAMP WITH TIME ZONE','Dernier signalement enregistré (tout acteur)'),('last_asc_notification','TIMESTAMP WITH TIME ZONE','Dernière notification ASC MPE / événement'),('notification_reports','BIGINT','Rapports de signalement observés'),('days_since_asc','BIGINT','Jours depuis dernière notification ASC'),('notification_status','TEXT','Ancienneté de notification ASC')]
}
METRICS={
 'alerts':[('alerts','Alertes distinctes','COUNT(*)'),('asc','Alertes source ASC',"COUNT(*) FILTER(WHERE actor='ASC')"),('other','Alertes autres acteurs',"COUNT(*) FILTER(WHERE actor='Autre acteur')"),('actor_unknown','Acteur absent / contradictoire',"COUNT(*) FILTER(WHERE actor NOT IN ('ASC','Autre acteur'))"),('mpe','Alertes avec signalement MPE','COUNT(*) FILTER(WHERE is_mpe)'),('events','Alertes avec signalement événement','COUNT(*) FILTER(WHERE is_event)'),('sorted','Alertes avec tri enregistré','COUNT(sorted_at)'),('verified','Alertes avec vérification enregistrée','COUNT(verified_at)'),('not_verified','Sans vérification enregistrée','COUNT(*)-COUNT(verified_at)'),('verified_rate','Part avec vérification enregistrée','1.0*COUNT(verified_at)/NULLIF(COUNT(*),0)'),('within48','Vérification enregistrée sous 48 h','COUNT(*) FILTER(WHERE verification_hours BETWEEN 0 AND 48)'),('within48_rate','Part des vérifications enregistrées sous 48 h','1.0*COUNT(*) FILTER(WHERE verification_hours BETWEEN 0 AND 48)/NULLIF(COUNT(verified_at),0)'),('backlog','À examiner après 72 h','SUM(review_72h)'),('tests','Avec formulaire de résultat de test','COUNT(test_result_at)'),('notifications','Rapports de signalement','SUM(notification_reports)'),('hours','Délai moyen parmi les vérifications enregistrées (h)','AVG(verification_hours)')],
 'reports':[('reports','Rapports enregistrés','COUNT(*)'),('reporting_sites','Sites déclarants distincts','COUNT(DISTINCT site_uuid)'),('no_id','Rapports sans identifiant alerte','COUNT(*) FILTER(WHERE alert_id IS NULL)'),('bad_date','Dates absentes, invalides ou futures',"COUNT(*) FILTER(WHERE date_status<>'Date exploitable')"),('conflict','Champs source contradictoires','COUNT(*) FILTER(WHERE input_conflict)'),('unmapped','Rapports hors répertoire courant',"COUNT(*) FILTER(WHERE mapping_status='Hors répertoire courant')"),('bad_link','Étapes avec liaison à vérifier',"COUNT(*) FILTER(WHERE stage_link_status NOT IN ('Signalement initial','Rattachable'))"),('human_deaths','Personnes décédées déclarées dans les formulaires ASC',"SUM(human_deaths) FILTER(WHERE actor='ASC' AND form IN ('sebac_detection','sebac_alert_notification'))"),('animal_deaths','Animaux décédés déclarés dans les formulaires ASC',"SUM(animal_deaths) FILTER(WHERE actor='ASC' AND form IN ('sebac_detection','sebac_alert_notification'))")],
 'sites':[('sites','Sites du répertoire','COUNT(*)'),('with_asc','Sites avec notification ASC observée','COUNT(last_asc_notification)'),('never','Sans notification ASC observée','COUNT(*)-COUNT(last_asc_notification)'),('old','Dernière notification ASC ≥ 30 jours',"COUNT(*) FILTER(WHERE days_since_asc>=30)"),('max_days','Ancienneté maximale observée (jours)','MAX(days_since_asc)')]
}
with app.test_request_context('/'):
 from flask import g
 from flask_login import login_user
 from superset import db,security_manager as sm
 from superset.models.dashboard import Dashboard
 from superset.models.slice import Slice
 from superset.connectors.sqla.models import SqlaTable,TableColumn,SqlMetric
 owner=sm.find_user(username='hmombo');assert owner;login_user(owner);g.user=owner
 old=db.session.query(Dashboard).filter_by(id=3).one()
 before=(old.position_json,old.json_metadata,old.published,sorted(s.id for s in old.slices))
 role=sm.find_role('DISC_DASH_SEBAC');assert role
 datasets={};reports=[]
 for key,name in TABLES.items():
  ds=db.session.query(SqlaTable).filter_by(uuid=uid('dataset:'+key)).one_or_none()
  if ds is None:ds=SqlaTable(uuid=uid('dataset:'+key),table_name='SEBAC DISC — '+{'reports':'Activité et qualité','alerts':'Cohortes d’alertes','sites':'Notifications actuelles des sites'}[key],database_id=1,schema='public');db.session.add(ds)
  assert ds.database_id==1
  ds.sql='SELECT * FROM public.'+name
  if key=='reports':
   stages='CASE r.form '+''.join("WHEN '"+form+"' THEN '"+label.replace("'","''")+"' " for form,label in FORMS.items())+'END'
   ds.sql='''SELECT r.*,'''+stages+''' AS stage,CASE WHEN r.form IN ('sebac_detection','sebac_alert_notification') THEN 'Signalement initial'
    WHEN a.alert_key IS NULL THEN 'Sans signalement retrouvé'
    WHEN a.identity_status<>'Identité exploitable' OR r.input_conflict THEN 'Identité en contradiction'
    WHEN r.site_uuid IS NOT NULL AND r.site_uuid<>a.site_uuid THEN 'Site en contradiction'
    WHEN r.date_status<>'Date exploitable' THEN 'Date inexploitable'
    WHEN r.reported_at<a.notified_at THEN 'Étape antérieure au signalement'
    ELSE 'Rattachable' END AS stage_link_status
    FROM public.mv_sebac_reports_v1 r LEFT JOIN public.mv_sebac_alerts_v1 a ON a.alert_key='id:'||r.alert_id'''
  ds.main_dttm_col='reported_month';ds.owners=[owner];ds.created_by=ds.changed_by=owner
  ds.description='SEBAC DISC : voir Méthode et qualité. Aucune identité de patient. Périmètre territorial courant.'
  for name,kind,label in GEO+EXTRA[key]:
   col=next((c for c in ds.columns if c.column_name==name),None)
   if col is None:col=TableColumn(column_name=name);ds.columns.append(col)
   col.type=kind;col.verbose_name=label;col.is_dttm=kind.startswith(('DATE','TIMESTAMP'));col.groupby=col.filterable=True
  for name,label,expression in METRICS[key]+[('fresh','Calcul du relevé (UTC)','MAX(calculated_at)'),('first','Premier mois disponible','MIN(reported_month)'),('last','Dernier mois disponible','MAX(reported_month)')]:
   m=next((m for m in ds.metrics if m.metric_name==name),None)
   if m is None:m=SqlMetric(metric_name=name);ds.metrics.append(m)
   m.verbose_name=label;m.expression=expression
  db.session.flush();datasets[key]=ds
 apply_regional_security(list(datasets.values()))
 Board=board_class(db,Dashboard,Slice,owner,old,args.publish,reports,uid)
 b=Board('pilot','SEBAC — Surveillance et suivi des alertes · DISC','sebac-pilotage-disc');b.dash.roles=[role]
 period='previous calendar month';time_excluded=[]
 table=dict(query_mode='aggregate',all_columns=[],percent_metrics=[],order_by_cols=[],order_desc=True,server_pagination=False,page_length=20,table_timestamp_format='%d/%m/%Y %H:%M',show_cell_bars=False,color_pn=False,allow_render_html=False,search_box=True)
 normal="mapping_status='Rattaché au répertoire courant'"
 def chart(key,title,source='alerts',viz='table',where=None,**settings):
  condition=where if where is not None else normal+(" AND identity_status='Identité exploitable'" if source=='alerts' else " AND date_status='Date exploitable'" if source=='reports' else '')
  c=b.chart(key,title,datasets[source],viz,**{**(table if viz=='table' else {}),'time_range':period,'adhoc_filters':[dict(expressionType='SQL',clause='WHERE',sqlExpression=condition)],**settings});return c
 def current(key,title,source='alerts',**settings):
  c=chart(key,title,source,time_range='No filter',**settings);time_excluded.append(c.id);return c
 nav='[Pilotage ASC](/superset/dashboard/asc-pilotage/) · [Supervision dédiée](/superset/dashboard/sd-supervision/)'
 p=b.tab('summary','Synthèse et évolution')
 b.note(p,'intro','''## Du signalement au suivi enregistré
Choisissez un **mois civil**, puis **Région → District → CSCOM → Zone** et **Appliquer les filtres**.
Les cartes comptent des **alertes distinctes**, selon leur premier signalement. Une vérification enregistrée plus tard reste liée à cette cohorte. La tendance conserve **12 mois complets** ; les onglets **Priorités actuelles** et **Notifications des sites** ignorent la période.
**L’absence de rapport ne prouve pas l’absence d’action terrain.** Consultez **Méthode et qualité** pour retrouver les données à vérifier.
'''+nav,24)
 cards=[('all','Alertes distinctes','alerts','Cohorte des premiers signalements',',d'),('asc','Signalées par les ASC','asc','Acteur cohérent dans les signalements',',d'),('mpe','Signalements MPE','mpe','Peut aussi être classée événement',',d'),('verified','Vérification enregistrée','verified','Même cohorte, à la date du relevé',',d'),('rate','Part avec vérification','verified_rate','Vérifiées enregistrées / alertes distinctes','.1%'),('pending','Sans vérification enregistrée','not_verified','Comprend les tris non conformes',',d')]
 for key,title,metric,sub,fmt in cards:chart(key,title,viz='big_number_total',metric=metric,subheader=sub,y_axis_format=fmt,header_font_size=.4,subheader_font_size=.13)
 b.row(p,'kpi1',[(x[0],4) for x in cards[:3]],24);b.row(p,'kpi2',[(x[0],4) for x in cards[3:]],24)
 bar=dict(groupby=[],annotation_layers=[],rich_tooltip=True,color_scheme='supersetColors',show_legend=True,y_axis_format=',d',x_axis_sort_series='name',x_axis_sort_series_ascending=True,truncateXAxis=False)
 trend=chart('trend','Alertes et vérifications — 12 mois complets',time_range='DATEADD(DATETRUNC(DATETIME("today"), month), -12, month) : DATETRUNC(DATETIME("today"), month)',viz='echarts_timeseries_bar',x_axis='reported_month',time_grain_sqla='P1M',metrics=['alerts','verified'],**bar)
 time_excluded.append(trend.id)
 chart('regions','Alertes et vérifications — régions',viz='echarts_timeseries_bar',x_axis='region',orientation='horizontal',metrics=['alerts','verified'],**bar)
 b.row(p,'trend',[('trend',6),('regions',6)],60)
 d=b.tab('workflow','Circuit et délais')
 b.note(d,'intro','''## Comparer des étapes de la même cohorte
Ces volumes **se chevauchent** : une même alerte peut avoir un tri, une vérification et un formulaire de résultat. Ce n’est pas un entonnoir de cas cliniques confirmés.
Le délai est mesuré entre **l’enregistrement du premier signalement et celui de la première vérification liée**. Il ne mesure pas la date réelle d’investigation. Le seuil de 48 h est un repère de suivi ; une base vide donne un taux vide, jamais un faux 0 %. Un formulaire de test ne garantit ni résultat positif ni complétude des prélèvements.''',30)
 chart('workflow','États du circuit enregistré',groupby=['workflow_status','tri_class'],metrics=['alerts','notifications','verified','tests'])
 chart('delay','Délai d’enregistrement des vérifications',groupby=['region','district'],metrics=['alerts','verified','within48','within48_rate','hours'])
 b.row(d,'workflow',[('workflow',12)],55);b.row(d,'delay',[('delay',12)],65)
 chart('types','Origine et type de signalement',groupby=['actor'],metrics=['alerts','mpe','events','sorted','verified','tests'])
 b.row(d,'types',[('types',12)],50)
 q=b.tab('backlog','Priorités actuelles')
 b.note(q,'intro','''## Préparer une revue des alertes
État **actuel**, toutes périodes de premier signalement, dans votre territoire. **La période ne s’applique pas à cet onglet.** Les alertes de plus de 72 h sans vérification enregistrée sont proposées à la revue ; les tris explicitement non conformes sont présentés séparément, sans leur imposer une vérification.
Une ligne par alerte, avec l’arborescence et les identifiants utiles au rapprochement. Aucune identité de patient. **⋮ → Télécharger → CSV / Excel** pour préparer la relance ; ce tableau ne déclenche aucun message.''',30)
 current('backlog','À examiner après 72 h',viz='big_number_total',metric='backlog',y_axis_format=',d',header_font_size=.4,subheader='Hors tris explicitement non conformes',subheader_font_size=.13)
 current('pending_now','Sans vérification enregistrée — total actuel',viz='big_number_total',metric='not_verified',y_axis_format=',d',header_font_size=.4,subheader='Toutes anciennetés et classifications',subheader_font_size=.13)
 b.row(q,'cards',[('backlog',6),('pending_now',6)],24)
 cols=['region','region_uuid','district','district_uuid','cscom','health_area_uuid','zone','supervisor_area_uuid','site_name','site_uuid','alert_id','notified_at','sorted_at','tri_class','workflow_status','age_days']
 base=normal+" AND identity_status='Identité exploitable'"
 current('review','EXPORT — Alertes à examiner après 72 heures',groupby=cols,metrics=['notifications'],where=base+' AND review_72h=1')
 current('noncompliant','EXPORT — Tris non conformes sans vérification enregistrée',groupby=cols,metrics=['notifications'],where=base+" AND verified_at IS NULL AND tri_class='Non conforme'")
 b.row(q,'review',[('review',12)],70);b.row(q,'noncompliant',[('noncompliant',12)],60)
 s=b.tab('sites','Notifications des sites')
 b.note(s,'intro','''## Repérer les sites sans notification récente
Une ligne par site du **répertoire DISC courant**, au dernier calcul ; la période ne s’applique pas. La dernière notification ASC concerne une MPE ou un événement. **Les jours ne sont jamais additionnés entre sites ou entre semaines.**
« Aucune notification observée » signifie aucune trouvée dans les données SEBAC disponibles depuis 2019. Ce n’est ni un site inactif, ni un site fermé, ni une preuve de défaut de surveillance. L’absence d’événement peut être normale. Le repère **30 jours** sert à organiser une revue, sans quota imposé.''',30)
 for key,title,metric in [('sites','Sites du répertoire','sites'),('never','Sans notification ASC observée','never'),('old','Dernière notification ASC ≥ 30 jours','old')]:current(key,title,'sites',viz='big_number_total',metric=metric,y_axis_format=',d',header_font_size=.4)
 b.row(s,'cards',[('sites',4),('never',4),('old',4)],24)
 current('site_export','EXPORT — Dernières notifications ASC par site','sites',groupby=['region','region_uuid','district','district_uuid','cscom','health_area_uuid','zone','supervisor_area_uuid','site_name','site_uuid','last_asc_notification','last_notification','days_since_asc','notification_status'],metrics=['sites'])
 b.row(s,'sites',[('site_export',12)],80)
 a=b.tab('activity','Activité et exports')
 b.note(a,'intro','''## Suivre les formulaires déclarés
Ici, la période porte sur **le mois d’enregistrement de chaque formulaire**, distinct de la cohorte du premier signalement. Un rapport de vérification peut donc appartenir à une autre période que sa notification initiale. Les décomptes de formulaires ne s’additionnent pas en alertes distinctes.
Les personnes / animaux décédés déclarés correspondent aux nombres saisis dans les formulaires de signalement ASC ; des déclarations répétées ne constituent pas un décompte de décès uniques. Les champs absents restent vides.
**⋮ → Télécharger → CSV / Excel** : les filtres et restrictions territoriales s’appliquent aussi aux exports.''',30)
 chart('activity','Activité enregistrée par étape SEBAC','reports',groupby=['stage'],metrics=['reports','reporting_sites'])
 chart('deaths','Décès déclarés — formulaires source ASC','reports',groupby=['region','district'],metrics=['human_deaths','animal_deaths'])
 b.row(a,'activity',[('activity',12)],65);b.row(a,'deaths',[('deaths',12)],50)
 chart('cohort_export','EXPORT — Cohortes d’alertes et étapes enregistrées',groupby=['reported_month']+cols+['verified_at','test_result_at','verification_hours'],metrics=['notifications'])
 chart('activity_export','EXPORT — Activité territoriale par mois et étape','reports',groupby=['reported_month','region','region_uuid','district','district_uuid','cscom','health_area_uuid','zone','supervisor_area_uuid','site_name','site_uuid','stage'],metrics=['reports','reporting_sites'])
 b.row(a,'cohort',[('cohort_export',12)],65);b.row(a,'export',[('activity_export',12)],65)
 m=b.tab('quality','Méthode et qualité')
 b.note(m,'method','''## Périmètre et contrôles
- Source **DISC uniquement** : aucune vue SEBAC ASA identifiée dans la connexion ASA auditée. Aucune fusion ou correspondance historique implicite.
- Sources cliniques en lecture seule. Trois relevés dédiés sont calculés atomiquement ; un échec conserve le dernier calcul réussi.
- Un document par UUID ; les documents supprimés sont exclus. Les dates absentes, antérieures à 2019 ou futures sont séparées. Les étapes sont liées par `alert_id`, avec contrôle du site et de la chronologie.
- Plusieurs signalements du même identifiant constituent une seule alerte. Un identifiant absent, plusieurs sites ou des champs source contradictoires empêchent l’utilisation comme alerte distincte fiable. Les collisions de sites ne sont pas attribuées arbitrairement à un territoire.
- La classification est celle du dernier tri enregistré ; des tris de même date contradictoires restent ambigus. La présence d’une vérification n’équivaut pas à une validation DTC. Les champs « vérifiée » et « validée » ne sont pas déduits d’une simple présence de formulaire.
- Les taux sont des rapports de sommes / effectifs sur **la même cohorte**, jamais une moyenne de pourcentages territoriaux. Les MPE et événements peuvent se chevaucher. Un acteur absent n’est pas reclassé arbitrairement comme autre acteur.
- Le rattachement est celui du répertoire **courant** ; les mutations historiques ne sont pas reconstituées. Les rapports hors répertoire restent dans les contrôles autorisés, sans faux site. Certains contrôles non rattachables ne sont visibles qu’au niveau national autorisé.
- Le répertoire n’est pas un effectif certifié de sites fonctionnels DHIS2. L’absence de notification n’indique pas un retard de synchronisation technique.
- Le tableau historique est conservé. Ses indicateurs comptent surtout des formulaires / semaines ; ils ne sont pas assimilés à cette cohorte. Les jours d’ancienneté hebdomadaires ne doivent pas être sommés.
- Les dates ci-dessous datent le calcul analytique, pas la réplication amont ni l’action terrain. Les listes n’exposent ni nom de patient, ni téléphone, ni commentaire clinique libre.
''',110)
 current('available','Périodes disponibles et calcul (UTC)','reports',where='TRUE',groupby=[],metrics=['first','last','fresh'],page_length=1)
 current('quality','Contrôles des rapports — toutes périodes','reports',where='TRUE',groupby=['date_status','mapping_status','stage_link_status'],metrics=['reports','no_id','conflict','bad_link'])
 current('identity','Contrôle des identités d’alerte — toutes périodes',where='TRUE',groupby=['identity_status','mapping_status'],metrics=['alerts','notifications'])
 current('quality_export','EXPORT — Rapports SEBAC à vérifier','reports',where="date_status<>'Date exploitable' OR input_conflict OR alert_id IS NULL OR mapping_status='Hors répertoire courant' OR stage_link_status NOT IN ('Signalement initial','Rattachable')",groupby=['region','district','cscom','site_name','site_uuid','report_uuid','alert_id','stage','reported_at','date_status','mapping_status','stage_link_status'],metrics=['reports'])
 b.row(m,'anomalies',[('quality_export',12)],65)
 b.row(m,'available',[('available',12)],24);b.row(m,'reports',[('quality',12)],70);b.row(m,'identity',[('identity',12)],50)
 prefix='NATIVE_FILTER-sebac-'
 filters=[dict(id=prefix+'period',type='NATIVE_FILTER',name='Période des signalements / rapports',filterType='filter_time',targets=[{}],controlValues={},cascadeParentIds=[],defaultDataMask={'extraFormData':{'time_range':period},'filterState':{'value':period},'ownState':{}},scope={'rootPath':['ROOT_ID'],'excluded':time_excluded},description='Cohorte de premier signalement, ou mois du formulaire dans Activité. Sans effet sur la tendance à 12 mois, Priorités, Notifications des sites et Qualité.')]
 for col,label,parents in [('region','Région',[]),('district','District',['region']),('cscom','CSCOM',['region','district']),('zone','Zone',['region','district','cscom'])]:
  filters.append(dict(id=prefix+col,type='NATIVE_FILTER',name=label,filterType='filter_select',targets=[{'datasetId':datasets['sites'].id,'column':{'name':col}}],controlValues=dict(enableEmptyFilter=False,defaultToFirstItem=False,multiSelect=True,searchAllOptions=True,inverseSelection=False),cascadeParentIds=[prefix+x for x in parents],defaultDataMask={'extraFormData':{},'filterState':{},'ownState':{}},scope={'rootPath':['ROOT_ID'],'excluded':[]},description='Périmètre courant, appliqué aux graphiques et exports après les droits RLS.'))
 b.finish(filters);brand_primary_dashboards(db.session)
 assert before==(old.position_json,old.json_metadata,old.published,sorted(s.id for s in old.slices)),'Tableau historique modifié'
 db.session.commit();print(json.dumps(dict(dashboards=reports,datasets={k:v.id for k,v in datasets.items()}),ensure_ascii=False))
