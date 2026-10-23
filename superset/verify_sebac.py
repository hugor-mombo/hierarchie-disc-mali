"""SEBAC cohort edge cases, native chart exports and territorial access checks."""
import csv,io,json,zipfile
from types import SimpleNamespace
from sqlalchemy import text
from superset.app import create_app
from sebac_sql import TABLES,sql,uid
app=create_app();base='https://dashboard.disc-mali.ml'
with app.app_context():
 from superset import db,security_manager as sm
 from superset.models.core import Database
 from superset.models.dashboard import Dashboard
 from superset.models.slice import Slice
 from superset.connectors.sqla.models import SqlaTable,RowLevelSecurityFilter
 from flask import g
 from flask_login import login_user
 database=db.session.query(Database).filter_by(id=1).one()
 owner=sm.find_user(username='hmombo').id
 dash=db.session.query(Dashboard).filter_by(uuid=uid('dashboard:pilot')).one()
 datasets={k:db.session.query(SqlaTable).filter_by(uuid=uid('dataset:'+k)).one() for k in TABLES}
 assert {r.name for r in dash.roles}=={'DISC_DASH_SEBAC'}
 assert all(d.database_id==1 and {'region_uuid','district_uuid'}.issubset({c.column_name for c in d.columns}) for d in datasets.values())
 scoped=[r for r in db.session.query(RowLevelSecurityFilter).all() if r.name.startswith('DISC_RLS_DISTRICT_') and r.name!='DISC_RLS_DISTRICT_UNSUPPORTED']
 assert len(scoped)==172 and all(all(any(t.id==d.id for t in r.tables) for d in datasets.values()) for r in scoped)
 gamma=sm.find_role('Gamma');sebac=sm.find_role('DISC_DASH_SEBAC')
 transient=SimpleNamespace(roles=[gamma,sebac],is_active=True,is_authenticated=True,is_anonymous=False,get_id=lambda:'-1')
 with app.test_request_context('/'):
  login_user(transient,force=True);g.user=transient
  assert all(any(r.clause=='1 = 0' for r in sm.get_rls_filters(d)) for d in datasets.values()),'Lecteur sans périmètre non refusé'
 with database.get_sqla_engine() as e:
  with e.connect() as c:
   c.execute(text('SET TRANSACTION READ ONLY'));c.execute(text("SET LOCAL statement_timeout='120s'"));c.execute(text("SET LOCAL TIME ZONE 'UTC'"))
   for key,name in TABLES.items():
    identity={'reports':'report_uuid','alerts':'alert_key','sites':'site_uuid'}[key]
    assert not c.execute(text('SELECT '+identity+' FROM '+name+' GROUP BY 1 HAVING count(*)>1 LIMIT 1')).first()
    assert c.execute(text('SELECT count(*) FROM '+name)).scalar()<100000,'Exporter par période / territoire : plafond atteint'
   cols=['report_uuid','form','reported_at','alert_id','site_uuid','actor','mpe','event','input_conflict','classification','checked','validated','date_status','site_name','region_uuid','region','district_uuid','district_name','district','health_area_uuid','cscom_name','cscom','supervisor_area_uuid','zone_name','zone','mapping_status']
   values=[]
   def row(r,form,a,site,days,classification=None):
    v=[r,form,'$DATE$',a,site,'ASC','yes','no',False,classification,'yes','yes','Date exploitable','Site','reg','Région','dist','District','District · Région','cscom','CSCOM','CSCOM · District','zone','Zone','Zone · CSCOM','Rattaché au répertoire courant']
    expressions=[]
    for name,x in zip(cols,v):
     if name=='reported_at':expressions.append("CURRENT_TIMESTAMP-interval '"+str(days)+" days'")
     elif isinstance(x,bool):expressions.append('TRUE' if x else 'FALSE')
     elif x is None:expressions.append('NULL::text')
     else:expressions.append("'"+x.replace("'","''")+"'::text")
    values.append('('+','.join(expressions)+')')
   origin='sebac_detection'
   row('a1',origin,'a','s1',5);row('a2',origin,'a','s1',4);row('av','sebac_alert_verification','a','s1',1)
   row('b',origin,'b','s1',10);row('bt','sebac_alert_sort','b','s1',9,'non_compliant')
   row('c',origin,'c','s1',7)
   row('d1',origin,'d','s1',7);row('d2',origin,'d','s2',6)
   row('e',origin,None,'s1',7)
   row('f',origin,'f','s1',2);row('fv','sebac_alert_verification','f','s1',3)
   row('g',origin,'g','s1',7);row('gt1','sebac_alert_sort','g','s1',6,'compliant');row('gt2','sebac_alert_sort','g','s1',6,'non_compliant')
   row('h',origin,'h','s1',7);row('hv','sebac_alert_verification','h','s2',6)
   row('i',origin,'i','s1',7);row('iv','sebac_alert_verification','i',None,6)
   fixture='WITH fixture('+','.join(cols)+') AS (VALUES '+','.join(values)+'), '
   query=fixture+sql('alerts').lstrip().split('WITH ',1)[1].replace('public.mv_sebac_reports_v1','fixture')
   result={r['alert_key']:r for r in c.execute(text(query)).mappings()}
   assert len(result)==9
   assert result['id:a']['notification_reports']==2 and result['id:a']['verification_hours']==96 and result['id:a']['review_72h']==0
   assert result['id:b']['tri_class']=='Non conforme' and result['id:b']['review_72h']==0
   assert result['id:c']['review_72h']==1
   assert result['id:d']['identity_status']!='Identité exploitable' and result['id:d']['region_uuid'] is None
   assert result['report:e']['identity_status']=='Identifiant d’alerte absent'
   assert result['id:f']['verified_at'] is None and result['id:f']['review_72h']==0
   assert result['id:g']['tri_class']=='Tri ambigu' and result['id:g']['review_72h']==1
   assert result['id:h']['verified_at'] is None and result['id:h']['review_72h']==1
   assert result['id:i']['verified_at'] is not None
   totals=dict(c.execute(text("SELECT count(*) alerts,count(verified_at) verified,sum(review_72h) review FROM mv_sebac_alerts_v1 WHERE identity_status='Identité exploitable' AND mapping_status='Rattaché au répertoire courant'")).mappings().one())
   print(json.dumps(dict(edge_cases='OK',duplicates=True,collision_quarantined=True,missing_identity=True,negative_delay_excluded=True,foreign_site_excluded=True,tri_ties=True,totals=totals),default=str),flush=True)
 # Select actual scoped users; choose a district with SEBAC signalements, not merely a large GPS portfolio.
 with database.get_sqla_engine() as e:
  with e.connect() as c:
   example=c.execute(text("SELECT region_uuid,district_uuid,count(*) n FROM mv_sebac_alerts_v1 WHERE identity_status='Identité exploitable' AND mapping_status='Rattaché au répertoire courant' GROUP BY 1,2 ORDER BY n DESC LIMIT 1")).one()
 region_rule=next(r for r in db.session.query(RowLevelSecurityFilter).all() if r.name.startswith('DISC_RLS_REGION_') and example.region_uuid in r.clause) if any(r.name.startswith('DISC_RLS_REGION_') and example.region_uuid in r.clause for r in db.session.query(RowLevelSecurityFilter).all()) else next(r for r in db.session.query(RowLevelSecurityFilter).all() if example.region_uuid in r.clause and any(x.name.startswith('DISC_REGION_') for x in r.roles))
 district_rule=next(r for r in scoped if example.district_uuid in r.clause)
 def reader(rule,prefix):
  names={r.name for r in rule.roles if r.name.startswith(prefix)}
  return next(u.id for u in db.session.query(sm.user_model).all() if u.is_active and names & {r.name for r in u.roles} and 'DISC_DASH_SEBAC' in {r.name for r in u.roles} and not {'Admin','Alpha','DISC_NATIONAL'} & {r.name for r in u.roles})
 profiles=[('national',owner,None,None),('region',reader(region_rule,'DISC_REGION_'),example.region_uuid,None),('district',reader(district_rule,'DISC_DISTRICT_'),example.region_uuid,example.district_uuid)]
checks=0
for profile,user_id,region,district in profiles:
 for key,chart_key,fmt in [('alerts','cohort_export','json'),('alerts','review','csv'),('reports','activity_export','csv'),('reports','quality_export','csv'),('sites','site_export','json')]+([('alerts','cohort_export','xlsx')] if profile=='national' else []):
  with app.app_context():
   ds=db.session.query(SqlaTable).filter_by(uuid=uid('dataset:'+key)).one();chart=db.session.query(Slice).filter_by(uuid=uid('chart:pilot:'+chart_key)).one();form=json.loads(chart.params)
   # No time range for this export validation: exercise every record within the profile's RLS.
   where=' AND '.join(f['sqlExpression'] for f in form['adhoc_filters']);columns=list(dict.fromkeys(form['groupby']+['region_uuid','district_uuid']))
   query=dict(columns=columns,metrics=form['metrics'],filters=[],granularity='reported_month',time_range='No filter',extras={'where':where,'having':''},row_limit=100000,row_offset=0)
   body=dict(datasource={'id':ds.id,'type':'table'},force=True,queries=[query],form_data={**form,'slice_id':chart.id,'dashboardId':dash.id},result_format=fmt,result_type='full')
   with app.test_client() as client:
    with client.session_transaction(base_url=base) as session:session['_user_id']=str(user_id);session['_fresh']=True
    csrf=client.get('/api/v1/security/csrf_token/',base_url=base);assert csrf.status_code==200
    response=client.post('/api/v1/chart/data',base_url=base,json=body,headers={'X-CSRFToken':csrf.json['result'],'Referer':base+'/superset/dashboard/sebac-pilotage-disc/'})
    assert response.status_code==200,(profile,key,fmt,response.status_code,str(response.json)[:300] if response.is_json else '')
    if fmt=='json':
     result=response.json['result'][0];assert not result.get('error'),result.get('error');rows=result['data']
     if region:assert all(r['region_uuid']==region for r in rows)
     if district:assert all(r['district_uuid']==district for r in rows)
     clauses=[where];params={}
     if region:clauses.append('region_uuid=:region');params['region']=region
     if district:clauses.append('district_uuid=:district');params['district']=district
     with ds.database.get_sqla_engine() as engine:
      with engine.connect() as conn:
       conn.execute(text('SET TRANSACTION READ ONLY'))
       expected=conn.execute(text('SELECT count(*) FROM (SELECT '+','.join(columns)+' FROM ('+ds.sql+') native WHERE '+' AND '.join('('+x+')' for x in clauses)+' GROUP BY '+','.join(columns)+') grouped'),params).scalar()
     assert len(rows)==expected,(profile,key,'export incomplet')
     if chart_key=='cohort_export':assert rows,'Profil de test sans alertes alors que le périmètre en contient'
    elif fmt=='csv':
     rows=list(csv.reader(io.StringIO(response.data.decode('utf-8-sig'))));header=rows[0] if rows else []
     if header:assert header==[ds.verbose_map.get(n,n) for n in columns+form['metrics']]
     clauses=[where];params={}
     if region:clauses.append('region_uuid=:region');params['region']=region
     if district:clauses.append('district_uuid=:district');params['district']=district
     with ds.database.get_sqla_engine() as engine:
      with engine.connect() as conn:
       conn.execute(text('SET TRANSACTION READ ONLY'))
       expected=conn.execute(text('SELECT count(*) FROM (SELECT '+','.join(columns)+' FROM ('+ds.sql+') native WHERE '+' AND '.join('('+x+')' for x in clauses)+' GROUP BY '+','.join(columns)+') grouped'),params).scalar()
     assert max(len(rows)-1,0)==expected,(profile,key,'CSV incomplet')
     for r in rows[1:]:
      if region:assert r[header.index(ds.verbose_map['region_uuid'])]==region
      if district:assert r[header.index(ds.verbose_map['district_uuid'])]==district
    else:
     with zipfile.ZipFile(io.BytesIO(response.data)) as z:assert 'xl/worksheets/sheet1.xml' in z.namelist()
    # Prove that an explicit request for another district cannot override the reader scope.
    if profile=='district' and fmt=='json':
     body['queries'][0]['filters']=[{'col':'district_uuid','op':'!=','val':district}]
     blocked=client.post('/api/v1/chart/data',base_url=base,json=body,headers={'X-CSRFToken':csrf.json['result'],'Referer':base+'/superset/dashboard/sebac-pilotage-disc/'})
     assert blocked.status_code==200 and not blocked.json['result'][0]['data'],'Lecture hors district'
   checks+=1
 print(json.dumps(dict(profile=profile,native_exports='OK')),flush=True)
print(json.dumps(dict(status='OK',native_query_checks=checks,district_scopes=172,default_deny=True)))
