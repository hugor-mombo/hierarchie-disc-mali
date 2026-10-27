"""Validate every district scope, real sign-ins, denied cross-district reads and map access."""
import argparse,csv,io,json,os,re
from pathlib import Path
from uuid import UUID
from sqlalchemy import text
from werkzeug.security import check_password_hash
from superset.app import create_app
from geo_rank_sql import uid
from district_security import supported,DENY_NAME
parser=argparse.ArgumentParser();parser.add_argument('--state',required=True);args=parser.parse_args()
path=Path(args.state);state=json.loads(path.read_text());records=state['accounts'];app=create_app();base=state['base_url'].rstrip('/')
assert records and len({r['password'] for r in records})==len(records)
with app.app_context():
 from superset import db,security_manager as sm
 from superset.models.core import Database
 from superset.models.slice import Slice
 from superset.models.dashboard import Dashboard
 from superset.connectors.sqla.models import SqlaTable,RowLevelSecurityFilter
 from flask import g
 from flask_login import login_user
 datasets=db.session.query(SqlaTable).all();rules=db.session.query(RowLevelSecurityFilter).all()
 primary={r.name:r for r in rules};deny=primary[DENY_NAME]
 scope_ds=db.session.query(SqlaTable).filter_by(uuid=uid('dataset:geo')).one()
 map_ds=db.session.query(SqlaTable).filter_by(uuid=uid('dataset:map')).one()
 map_chart=db.session.query(Slice).filter_by(uuid=uid('chart:geo:map')).one()
 dash=db.session.query(Dashboard).filter_by(uuid=uid('dashboard:geo')).one();assert dash.published
 database=db.session.query(Database).filter_by(id=1).one()
 common={'DISC_VIEWER','DISC_DASH_ASC_ACTIVITY','DISC_DASH_ASC_SUPERVISION','DISC_DASH_SEBAC'}
 with database.get_sqla_engine() as engine:
  with engine.connect() as c:
   c.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'));c.execute(text('SET TRANSACTION READ ONLY'));c.execute(text("SET LOCAL statement_timeout='120s'"))
   actual=c.execute(text('SELECT count(*),count(DISTINCT site_uuid) FROM mv_disc_gps_quality_v1')).one();assert actual[0]==actual[1]
   portfolio_counts={(r.district_uuid,r.region_uuid):r.n for r in c.execute(text('SELECT district_uuid,region_uuid,count(*) n FROM mv_superset_sd_portfolio GROUP BY 1,2'))}
   map_counts={(r.district_uuid,r.region_uuid):r.n for r in c.execute(text('SELECT district_uuid,region_uuid,count(*) n FROM mv_disc_sites_map_v1 GROUP BY 1,2'))}
   safe_ids={d.id for d in datasets if supported(d)};all_ids={d.id for d in datasets}
   denied={d.id for d in deny.tables};assert denied==all_ids-safe_ids
   total=0
   for index,record in enumerate(records):
    UUID(record['district_uuid']);UUID(record['region_uuid'])
    user=sm.find_user(username=record['username']);assert user and user.id==record['user_id']
    assert {r.name for r in user.roles}==common|{record['role']}
    assert check_password_hash(user.password,record['password']),'Credential mismatch'
    role=sm.find_role(record['role']);assert role and not role.permissions
    name='DISC_RLS_DISTRICT_'+record['username'][5:];rule=primary[name]
    expected="district_uuid='"+record['district_uuid']+"' AND region_uuid='"+record['region_uuid']+"'"
    assert rule.clause==expected and rule.group_key is None and {r.id for r in rule.roles}=={role.id}
    attached={d.id for d in rule.tables};assert role.id in {r.id for r in deny.roles}
    assert attached==safe_ids,'Dataset coverage gap'
    with app.test_request_context('/'):
     login_user(user,force=True);g.user=user
     effective=sm.get_rls_filters(scope_ds)
     assert [r.clause for r in effective]==[expected],('Unexpected effective scope',record['username'])
     n=c.execute(text('SELECT count(*) FROM ('+scope_ds.sql+')q WHERE '+effective[0].clause)).scalar()
     expected_n=portfolio_counts.get((record['district_uuid'],record['region_uuid']),0)
     assert n==expected_n==record['sites'],('Territory mismatch',record['username'])
     assert [r.clause for r in sm.get_rls_filters(map_ds)]==[expected]
     for denied_id in [34,66]:
      ds=next(d for d in datasets if d.id==denied_id)
      assert any(r.clause=='1 = 0' for r in sm.get_rls_filters(ds)),'Unsupported scope is not denied'
    record['map_points']=map_counts.get((record['district_uuid'],record['region_uuid']),0)
    total+=n
    if (index+1)%20==0 or index+1==len(records):print(json.dumps(dict(scopes_checked=index+1,total_scopes=len(records))),flush=True)
   assert total==actual[0],'Districts do not partition the current site registry'
 print(json.dumps(dict(structural_rls='OK',districts=len(records),datasets=len(datasets),sites_checked=total,credentials_verified=len(records))),flush=True)
 # Activate only after all scopes and hashes pass. A failed end-to-end check below
 # deactivates the accounts created by this manifest; regional users are untouched.
 for record in records:sm.find_user(username=record['username']).active=True
 db.session.commit()

checks=0
try:
 with app.app_context():
  candidates=sorted([r for r in records if r['map_points']>0],key=lambda r:r['map_points'],reverse=True)
  examples=[];regions=set()
  for r in candidates:
   if r['region_uuid'] not in regions:examples.append(r);regions.add(r['region_uuid'])
   if len(examples)==3:break
  examples.append(next(r for r in records if r['sites']==0))
 for record in examples:
  with app.app_context():
   map_ds=db.session.query(SqlaTable).filter_by(uuid=uid('dataset:map')).one()
   chart=db.session.query(Slice).filter_by(uuid=uid('chart:geo:map')).one();form=json.loads(chart.params)
   dash=db.session.query(Dashboard).filter_by(uuid=uid('dashboard:geo')).one()
   other=next(r for r in records if r['region_uuid']==record['region_uuid'] and r['district_uuid']!=record['district_uuid'])
   with app.test_client() as client:
    # Exercise the real login form, not an administrator session impersonation.
    login=client.get('/login/',base_url=base)
    token=re.search(r'name="csrf_token"[^>]*value="([^"]+)"',login.data.decode())
    assert token,'Login CSRF token missing'
    result=client.post('/login/',base_url=base,data={'username':record['username'],'password':record['password'],'csrf_token':token.group(1)},headers={'Referer':base+'/login/'},follow_redirects=False)
    assert result.status_code==302,'Native login failed'
    me=client.get('/api/v1/me/',base_url=base);assert me.status_code==200 and me.json['result']['id']==record['user_id']
    csrf=client.get('/api/v1/security/csrf_token/',base_url=base);assert csrf.status_code==200
    headers={'X-CSRFToken':csrf.json['result'],'Referer':base+'/superset/dashboard/'+dash.slug+'/'}
    def query(ds,fmt='json',filters=None,columns=None,metrics=None):
     columns=columns if columns is not None else ['site_uuid','region_uuid','district_uuid','latitude','longitude']
     query=dict(columns=columns,metrics=metrics or [],filters=filters or [],granularity=None,time_range='No filter',extras={'where':'','having':''},orderby=[],row_limit=100000,row_offset=0)
     context_chart=chart;context_dash=dash
     if ds.id!=map_ds.id:
      pairs=[(d,c) for d in db.session.query(Dashboard).all() for c in d.slices if c.datasource_id==ds.id and c.datasource_type=='table']
      assert pairs,'No dashboard context for dataset'
      context_dash,context_chart=pairs[0]
     body=dict(datasource={'id':ds.id,'type':'table'},force=True,queries=[query],form_data={**form,'datasource':f'{ds.id}__table','slice_id':context_chart.id,'dashboardId':context_dash.id},result_format=fmt,result_type='full')
     response=client.post('/api/v1/chart/data',base_url=base,json=body,headers=headers)
     assert response.status_code==200,('Native data API',response.status_code)
     return response
    data=query(map_ds).json['result'][0]['data'];assert len(data)==record['map_points']
    assert all(r['district_uuid']==record['district_uuid'] and r['region_uuid']==record['region_uuid'] for r in data)
    assert all(-90<=float(r['latitude'])<=90 and -180<=float(r['longitude'])<=180 and (float(r['latitude'])!=0 or float(r['longitude'])!=0) for r in data)
    csv_result=query(map_ds,fmt='csv');rows=list(csv.reader(io.StringIO(csv_result.data.decode('utf-8-sig'))))
    assert max(0,len(rows)-1)==record['map_points']
    if data:
     labels=[map_ds.verbose_map.get(k,k) for k in ['site_uuid','region_uuid','district_uuid','latitude','longitude']]
     assert rows[0]==labels
     assert all(row[2]==record['district_uuid'] for row in rows[1:])
    forbidden=query(map_ds,filters=[{'col':'district_uuid','op':'IN','val':[other['district_uuid']]}]).json['result'][0]['data'];assert not forbidden,'Cross-district access'
    for dataset_id,metric in [(34,'count'),(66,'c_reports')]:
     denied_ds=db.session.query(SqlaTable).filter_by(id=dataset_id).one()
     if metric not in {m.metric_name for m in denied_ds.metrics}:
      # Explicit aggregate, without assuming a named metric on legacy datasets.
      metric={'expressionType':'SQL','sqlExpression':'COUNT(*)','label':'rows'}
     result=query(denied_ds,columns=[],metrics=[metric]).json['result'][0]['data']
     key=metric if isinstance(metric,str) else metric['label']
     assert not result or result[0][key] in [0,None],'Unsupported aggregate leaked'
    sql=client.post('/api/v1/sqllab/execute/',base_url=base,json={'database_id':1,'sql':'SELECT 1','runAsync':False},headers=headers)
    assert sql.status_code in [401,403],'SQL execution must be denied'
    checks+=1;print(json.dumps(dict(native_login='OK',map='scoped',csv='scoped',other_district='denied',asa_and_national='denied',sql_lab='denied',zero_data=record['sites']==0)),flush=True)
 with app.app_context():
  for record in records:
   user=sm.find_user(username=record['username']);assert user.active
   record['active']=True;record['verification']='RLS validée'
  state['status']='verified';state['district_count']=len(records);state['native_logins_checked']=checks
  temp=path.with_name(path.name+'.verified-next')
  with os.fdopen(os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600),'w') as f:json.dump(state,f,ensure_ascii=False)
  os.replace(temp,path);path.chmod(0o600)
 print(json.dumps(dict(status='OK',districts=len(records),native_login_profiles=checks)),flush=True)
except BaseException:
 with app.app_context():
  for record in records:
   user=sm.find_user(username=record['username'])
   if user:user.active=False
  db.session.commit()
 raise
