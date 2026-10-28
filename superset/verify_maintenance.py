"""Fixtures SQL et vrais endpoints Superset, sans compte IT créé ni rôle attribué."""
import argparse,csv,io,json,logging
from datetime import date,timedelta
from pathlib import Path
from sqlalchemy import text
from flask_login import UserMixin,login_user
from maintenance_catalog import ROOT,TABLES,METRICS,ROLE,SLUG,uid,events_sql,DEVICES
from superset.app import create_app
parser=argparse.ArgumentParser();parser.add_argument('--analytical-only',action='store_true');parser.add_argument('--metadata-only',action='store_true');args=parser.parse_args()
app=create_app();base='https://dashboard.disc-mali.ml'
logging.getLogger('superset.views.error_handling').setLevel(logging.ERROR)
def fixtures(c):
 today=date.today();docs=[]
 def add(user,device,day=None,free=3*1073741824,total=20*1073741824,metrics=None):
  d=day or today
  doc=dict(_id='fixture-'+str(len(docs)),type='telemetry',metadata=dict(user=user,deviceId=device,year=d.year,month=d.month,day=d.day,versions={'app':'fixture'}),device={'deviceInfo':{'storage':{'free':free,'total':total}}},metrics=metrics or {})
  docs.append(doc);return doc
 add('u1','d1',free=0,metrics={'replication:medic:to:success':dict(count=3,sum=9999),'replication:medic:from:success':dict(count=4,sum=4444),'client-date-offset':dict(count=1,min=-600000,max=-300000)})
 add('u2','d2');add('u2','d2',free=0)
 add('u3','d3',free=-1)
 add('u4','d4');add('u4','d4',day=date(2099,1,1),metrics={'client-date-offset':dict(count=1,min=999999,max=999999)})
 add('u5','d5',day=today-timedelta(days=10),free=1073741824/2)
 invalid=add('u6','d6');invalid['metadata'].update(year=2025,month=2,day=30)
 add('u7','d7',free=2*1073741824,total=20*1073741824)
 add('u8','d8',free=2*1073741824,total=30*1073741824)
 add('u9','d9',free=None)
 params={f'd{i}':json.dumps(d) for i,d in enumerate(docs)}
 telemetry='(VALUES '+','.join('(CAST(:d'+str(i)+' AS jsonb))' for i in range(len(docs)))+') AS test_docs(doc)'
 evsql=events_sql().replace('public.couchdb_users_meta',telemetry)
 users=[dict(type='user',name='u'+str(i),facility_id='site',roles=['chw']) for i in range(10)]
 params.update({f'u{i}':json.dumps(d) for i,d in enumerate(users)})
 user_sql='(VALUES '+','.join('(CAST(:u'+str(i)+' AS jsonb))' for i in range(len(users)))+') AS test_users(doc)'
 geography="(SELECT 'site'::text site_uuid,'zone'::text supervisor_area_uuid,'cscom'::text health_area_uuid,'district'::text district_uuid,'region'::text region_uuid,'R'::text region,'D'::text district,'C'::text cscom,'Z'::text zone,'S'::text site_name) AS test_geography"
 sql=DEVICES.replace('WITH users AS','WITH test_events AS ('+evsql+'), users AS').replace('__EVENTS__','test_events').replace('public.couchdb_medic_users',user_sql).replace('public.v_disc_site_registry_labels_v1',geography)
 rows={r['username']:dict(r) for r in c.execute(text(sql),params).mappings()}
 assert rows['u0']['device_id'] is None and rows['u0']['storage_status']=='Aucune télémétrie'
 assert rows['u1']['free_gib']==0 and rows['u1']['storage_status']=='Critique (< 1 Gio)'
 assert rows['u1']['last_upload_day']==today and rows['u1']['last_download_day']==today
 assert rows['u1']['clock_abs_minutes_7d']==10
 assert rows['u2']['latest_ambiguous']==1 and rows['u2']['free_gib'] is None
 assert rows['u3']['storage_valid']==0 and rows['u3']['free_gib'] is None
 assert rows['u4']['telemetry_day']==today and rows['u4']['future_documents']==1 and rows['u4']['clock_reports_7d']==0
 assert rows['u5']['telemetry_age_days']==10 and rows['u5']['storage_status']=='Critique (< 1 Gio)'
 assert rows['u6']['telemetry_day'] is None and rows['u6']['invalid_date_documents']==1
 assert rows['u7']['storage_status']=='Espace suffisant selon seuils IT'
 assert rows['u8']['storage_status']=='À surveiller (< 2 Gio ou < 10 %)'
 assert rows['u9']['storage_valid']==0
 evrows=c.execute(text('WITH fixture AS ('+evsql+') SELECT sum(to_success) n FROM fixture'),params).scalar()
 assert evrows==3,'Ne pas compter les durées comme des réussites'
 # Recent-disk cards must exclude old and ambiguous measurements.
 critical=next(expr for key,label,expr in METRICS['devices'] if key=='critical')
 assert c.execute(text('WITH fixture AS ('+sql+') SELECT '+critical+' FROM fixture'),params).scalar()==1
 return len(rows)

with app.app_context():
 from superset import db,security_manager as sm
 from superset.models.core import Database
 from superset.connectors.sqla.models import SqlaTable,RowLevelSecurityFilter
 from superset.models.dashboard import Dashboard
 with db.session.query(Database).filter_by(id=1).one().get_sqla_engine() as engine:
  with engine.connect() as c:
   c.execute(text('SET TRANSACTION READ ONLY'));c.execute(text("SET LOCAL statement_timeout='90s'"))
   n=fixtures(c)
   assert not c.execute(text('SELECT username,device_id FROM '+TABLES['devices']+' GROUP BY 1,2 HAVING count(*)>1 LIMIT 1')).first()
   assert c.execute(text('SELECT count(*) FROM '+TABLES['events'])).scalar()==c.execute(text("SELECT count(*) FROM couchdb_users_meta WHERE doc->>'type'='telemetry' AND coalesce(doc->>'_deleted','false')<>'true'")).scalar()
   assert c.execute(text('SELECT count(*) FROM '+TABLES['devices'])).scalar()<100000
   totals=dict(c.execute(text('SELECT '+','.join(sql+' AS '+key for key,label,sql in METRICS['devices'])+' FROM '+TABLES['devices']+" WHERE account_status='Compte courant'")).mappings().one())
   print(json.dumps(dict(fixtures=n,totals=totals),default=str),flush=True)
 if args.analytical_only:raise SystemExit(0)
 dash=db.session.query(Dashboard).filter_by(slug=SLUG).one();datasets={key:db.session.query(SqlaTable).filter_by(uuid=uid('dataset:'+key)).one() for key in TABLES}
 assert {r.name for r in dash.roles}=={ROLE}
 deny=db.session.query(RowLevelSecurityFilter).filter_by(name='DISC_IT_DEFAULT_DENY').one()
 assert deny.clause=='1 = 0' and {r.name for r in deny.roles}=={ROLE,'Admin'}
 assert {t.id for t in deny.tables}=={d.id for d in datasets.values()}
 viewer=sm.find_role('DISC_VIEWER');itrole=sm.find_role(ROLE);assert viewer and itrole
 assignments_before={u.id:sorted(r.id for r in u.roles) for u in db.session.query(sm.user_model)}
 owner_id=sm.find_user(username='hmombo').id
 users=db.session.query(sm.user_model).filter(sm.user_model.active==True).all()
 examples={}
 for title,prefix in [('national','DISC_NATIONAL'),('region','DISC_REGION_'),('district','DISC_DISTRICT_')]:
  example=next(u for u in users if any(r.name.startswith(prefix) for r in u.roles) and not {'Admin','Alpha',ROLE}&{r.name for r in u.roles})
  examples[title]=example.id
 dset=datasets['devices'];slice_id=next(s.id for s in dash.slices if json.loads(s.params).get('metric')=='devices')
 raw_expected=totals['devices']
 dsids={k:d.id for k,d in datasets.items()};dashid=dash.id
 chart_by_title={s.slice_name:s.id for s in dash.slices};all_ids={s.id for s in dash.slices}
 list_titles=['EXPORT — Profils et comptes à examiner','EXPORT — Tous les profils compte–appareil sélectionnés']
 expected={'storage_status':{chart_by_title[t] for t in list_titles},'telemetry_status':{chart_by_title[t] for t in list_titles+['EXPORT — Derniers jours de succès observés']}}
 for f in json.loads(dash.json_metadata)['native_filter_configuration']:
  col=f.get('targets',[{}])[0].get('column',{}).get('name')
  if col in expected:assert all_ids-set(f['scope']['excluded'])==expected[col],('filter scope',col)
 if args.metadata_only:
  assert expected.keys()<={f.get('targets',[{}])[0].get('column',{}).get('name') for f in json.loads(dash.json_metadata)['native_filter_configuration']}
  print(json.dumps(dict(metadata='OK',list_filters='OK',roles='unchanged')),flush=True);raise SystemExit(0)

class Identity(UserMixin):
 def __init__(self,roles):self.id=examples['region'];self.username='it_test_non_persiste';self.first_name='Test';self.last_name='IT';self.roles=roles;self.email=''

# This authentication hook exists only in this local verification process.
# No account, role assignment or web-server configuration is written.
def identity_hook():
 from flask import request,g
 label=request.headers.get('X-DISC-Monitoring-Test')
 if not label:return
 if label=='IT':user=Identity([sm.find_role('DISC_VIEWER'),sm.find_role(ROLE)])
 elif label=='viewer_only':user=Identity([sm.find_role('DISC_VIEWER')])
 else:user=sm.get_user_by_id(owner_id if label=='hmombo' else examples[label])
 login_user(user,force=True);g.user=user
app.before_request_funcs.setdefault(None,[]).insert(0,identity_hook)

for label in ['hmombo','IT','national','region','district','viewer_only','anonymous']:
 with app.test_client() as client:
  h={} if label=='anonymous' else {'X-DISC-Monitoring-Test':label}
  response=client.get('/api/v1/dashboard/'+str(dashid),base_url=base,headers=h)
  authorized=label in ['hmombo','IT']
  assert (response.status_code==200)==authorized,(label,'dashboard',response.status_code)
  if label=='anonymous':continue
  token=client.get('/api/v1/security/csrf_token/',base_url=base,headers=h);assert token.status_code==200,(label,token.status_code)
  headers={**h,'X-CSRFToken':token.json['result'],'Referer':base+'/'}
  if label=='IT':
   for path in ['/api/v1/dashboard/','/api/v1/chart/','/api/v1/sqllab/execute/']:
    assert client.post(path,base_url=base,json={},headers=headers).status_code==403,('IT authoring',path)
  for key,dsid in dsids.items():
   query=dict(columns=[],metrics=['devices'],filters=[dict(col='account_status',op='IN',val=['Compte courant'])],time_range='No filter',extras={'where':'','having':''},orderby=[],row_limit=100000)
   body=dict(datasource={'id':dsid,'type':'table'},force=True,queries=[query],form_data={'datasource':f'{dsid}__table','viz_type':'table','dashboardId':dashid,'slice_id':slice_id if key=='devices' else next(s.id for s in dash.slices if s.datasource_id==dsid)},result_format='json',result_type='full')
   data=client.post('/api/v1/chart/data',base_url=base,json=body,headers=headers)
   if not authorized:
    assert data.status_code in [403,404] or (data.status_code==200 and not data.json['result'][0]['data']),(label,key,'data access')
   else:
    assert data.status_code==200 and not data.json['result'][0].get('error'),(label,key,data.status_code,str(data.json)[:200])
    if key=='devices':assert data.json['result'][0]['data'][0]['devices']==raw_expected
    # Native aggregate and list export must retain the authorized scope.
    if key=='devices':
     query['columns']=['region','district','cscom','username','device_id','storage_status','telemetry_day'];query['metrics']=[]
     for fmt in ['csv','xlsx']:
      body['result_format']=fmt;export=client.post('/api/v1/chart/data',base_url=base,json=body,headers=headers)
      assert export.status_code==200,(label,fmt,export.status_code)
      if fmt=='xlsx':assert export.data[:2]==b'PK'
      else:assert list(csv.reader(io.StringIO(export.data.decode('utf-8-sig'))))
  if authorized:
   for chart in dash.slices:
    p=json.loads(chart.params);dsid=chart.datasource_id
    where=' AND '.join(f['sqlExpression'] for f in p.get('adhoc_filters',[]) if f.get('clause')=='WHERE' and f.get('expressionType')=='SQL')
    filters=[] if chart.id==next(s.id for s in dash.slices if s.slice_name=='Contrôles globaux des documents techniques') else [dict(col='account_status',op='IN',val=['Compte courant'])]
    metrics=p.get('metrics',[p['metric']] if 'metric' in p else [])
    columns=p.get('groupby',[])
    if p.get('x_axis'):columns=[p['x_axis']]+columns
    query=dict(columns=columns,metrics=metrics,filters=filters,time_range=p.get('time_range','No filter'),granularity='telemetry_day',extras={'where':where,'having':''},orderby=[],row_limit=100000)
    body=dict(datasource={'id':dsid,'type':'table'},force=True,queries=[query],form_data={'datasource':f'{dsid}__table','viz_type':chart.viz_type,'dashboardId':dashid,'slice_id':chart.id},result_format='json',result_type='full')
    response=client.post('/api/v1/chart/data',base_url=base,json=body,headers=headers)
    assert response.status_code==200 and not response.json['result'][0].get('error'),(label,chart.id,chart.slice_name,response.status_code,str(response.json)[:300])
  print(json.dumps(dict(profile=label,dashboard_access=authorized,data_access='OK',exports='OK' if authorized else 'refusés')),flush=True)
with app.app_context():
 assert assignments_before=={u.id:sorted(r.id for r in u.roles) for u in db.session.query(sm.user_model)},'Attributions de rôles modifiées pendant la vérification'
