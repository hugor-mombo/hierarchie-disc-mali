"""Lot 1 supervision checks. No clinical rows or staff identities are saved or printed."""
import argparse,csv,io,json,zipfile
from decimal import Decimal
import xml.etree.ElementTree as ET
from unittest.mock import patch
from sqlalchemy import text
from superset.app import create_app
from sd_catalog import SOURCES,uid,sql
parser=argparse.ArgumentParser();parser.add_argument('--readers-only',action='store_true');args=parser.parse_args()
app=create_app();base='https://dashboard.disc-mali.ml';region='39af6dc3-4cd1-4eb9-955a-46edb57a9988'
with app.app_context():
 from superset import db,security_manager as sm
 from superset.models.core import Database
 from superset.models.dashboard import Dashboard
 from superset.models.slice import Slice
 from superset.connectors.sqla.models import SqlaTable
 owner_id=sm.find_user(username='hmombo').id
 users=db.session.query(sm.user_model).filter(sm.user_model.roles.any(name='DISC_REGION_bougouni')).all()
 reader_id=next(u.id for u in users if u.is_active and any(r.name=='DISC_DASH_ASC_SUPERVISION' for r in u.roles) and not any(r.name in ['Admin','Alpha','DISC_NATIONAL'] for r in u.roles))
 for key in SOURCES:
  ds=db.session.query(SqlaTable).filter_by(uuid=uid('dataset:'+key)).one()
  assert ds.database_id==SOURCES[key]['db'] and ds.sql.strip()==sql(key).strip()
  dash=db.session.query(Dashboard).filter_by(uuid=uid('dashboard:'+('disc' if key=='disc' else 'asa'))).one()
  config=json.loads(dash.json_metadata)['native_filter_configuration']
  assert next(f for f in config if f['name'] in ['Zone de supervision','Zone ASA'])['targets'][0]['column']['name']=='zone'
  with ds.database.get_sqla_engine() as e:
   with e.connect() as c:
    c.execute(text('SET TRANSACTION READ ONLY'));c.execute(text("SET LOCAL statement_timeout='60s'"))
    grain='site_uuid' if key=='disc' else 'supervisor_area_uuid'
    n,unique,future=c.execute(text('SELECT count(*),count(DISTINCT('+grain+",reported_month)),count(*) FILTER(WHERE reported_month>=date_trunc('month',CURRENT_DATE)) FROM ("+ds.sql+')q')).one()
    assert n==unique and n<=100000 and future==0,(key,'Grain or export cap')
    bad="quota>three_forms OR three_forms>visited OR quota NOT IN(0,1)" if key=='disc' else ('quota_site_months>eligible_site_months OR eligible_site_months<0 OR quota_site_months<0' if key=='asa_history' else 'rdt_correct>rdt_done OR rdt_correct<0 OR rdt_done<0')
    assert not c.execute(text('SELECT 1 FROM ('+ds.sql+')q WHERE '+bad+' LIMIT 1')).first(),key
    if key!='disc':assert c.execute(text('SELECT count(*) FROM ('+ds.sql+')q WHERE region_uuid IS NOT NULL')).scalar()==0,'Revisit ASA RLS if native region IDs become available'
  print(json.dumps(dict(source=key,grain='OK',rows=n,export_cap='OK')),flush=True)

with app.test_request_context('/'):
 from flask import g
 from flask_login import login_user
 user=db.session.query(sm.user_model).filter_by(id=reader_id).one();login_user(user);g.user=user
 for key in SOURCES:
  ds=db.session.query(SqlaTable).filter_by(uuid=uid('dataset:'+key)).one()
  data=ds.query(dict(columns=['region_uuid'],metrics=[],granularity=None,is_timeseries=False,from_dttm=None,to_dttm=None,row_limit=100,filter=[],orderby=[],extras={'where':'','having':''}))
  assert not data.error_message,data.error_message
  seen=set(data.df['region_uuid']) if not data.df.empty else set()
  assert seen.issubset({region}) if key=='disc' else not seen,'Regional boundary'
  with patch.object(sm,'get_user_roles',return_value=[sm.find_role('DISC_DASH_ASC_SUPERVISION')]):assert any(r.clause=='1 = 0' for r in sm.get_rls_filters(ds))
 print(json.dumps(dict(rls='OK',datasets=3,asa_regional='empty_pending_native_scope',default_deny=True)),flush=True)

checks=0

def export(key,fmt,regional=False,forbidden=False,status=False):
 global checks
 with app.app_context():
  user_id=reader_id if regional else owner_id
  chart_key='disc:export' if key=='disc' else ('asa:export' if key=='asa_history' else 'asa:fm')
  chart=db.session.query(Slice).filter_by(uuid=uid('chart:'+chart_key)).one();form=json.loads(chart.params)
  ds=db.session.query(SqlaTable).filter_by(id=chart.datasource_id).one()
  dash=db.session.query(Dashboard).filter_by(uuid=uid('dashboard:'+('disc' if key=='disc' else 'asa'))).one()
  if regional:assert dash.published
  filters=[];where='TRUE'
  if forbidden:
   filters.append(dict(col='region_uuid',op='IN',val=['63aec90d-9aa6-505d-80e4-4f4b2e4a5709']));where+=' AND FALSE'
  if status:
   filters.append(dict(col='quota_status',op='IN',val=['Quota incomplet','Aucun des trois formulaires']));where+=" AND quota_status<>'Quota complet'"
  if regional:where+=" AND region_uuid='"+region+"'"
  body=dict(datasource={'id':ds.id,'type':'table'},force=True,queries=[dict(columns=form['groupby'],metrics=form['metrics'],filters=filters,granularity='reported_month',time_range='No filter',extras={'where':'','having':''},orderby=[],row_limit=100000,row_offset=0)],form_data={**form,'dashboardId':dash.id,'slice_id':chart.id},result_format=fmt,result_type='full')
  with app.test_client() as client:
   with client.session_transaction(base_url=base) as s:s['_user_id']=str(user_id);s['_fresh']=True
   me=client.get('/api/v1/me/',base_url=base);assert me.status_code==200 and me.json['result']['id']==user_id
   csrf=client.get('/api/v1/security/csrf_token/',base_url=base);assert csrf.status_code==200
   result=client.post('/api/v1/chart/data',base_url=base,json=body,headers={'X-CSRFToken':csrf.json['result'],'Referer':base+'/superset/dashboard/'+dash.slug+'/'})
   assert result.status_code==200,(key,fmt,result.status_code,str(result.json)[:300] if result.is_json else 'non-JSON')
   if fmt=='csv':
    rows=list(csv.reader(io.StringIO(result.data.decode('utf-8-sig'))));headers=rows[0] if rows else [];count=max(0,len(rows)-1)
   else:
    with zipfile.ZipFile(io.BytesIO(result.data)) as z:
     root=ET.fromstring(z.read('xl/worksheets/sheet1.xml'));count=max(0,len(root.findall('.//s:sheetData/s:row',{'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}))-1)
   with ds.database.get_sqla_engine() as e:
    with e.connect() as c:
     c.execute(text('SET TRANSACTION READ ONLY'));c.execute(text("SET LOCAL statement_timeout='60s'"))
     expected=c.execute(text('SELECT count(*) FROM (SELECT '+','.join(form['groupby'])+' FROM ('+ds.sql+')q WHERE '+where+' GROUP BY '+','.join(form['groupby'])+')x')).scalar()
     assert count==expected,(key,fmt,count,expected)
     if fmt=='csv' and count:
      for metric in form['metrics']:
       definition=next(m for m in SOURCES[key]['metrics'] if m[0]==metric)
       # A row-level ratio must not be added across rows; check additive metrics only.
       if '/' in definition[2] or 'DISTINCT' in definition[2]:continue
       expected_total=c.execute(text('SELECT '+definition[2]+' FROM ('+ds.sql+')q WHERE '+where)).scalar()
       index=next(headers.index(x) for x in [metric,definition[1]] if x in headers)
       actual=sum((Decimal(r[index]) for r in rows[1:] if r[index]),Decimal(0))
       assert actual==expected_total,(key,metric,'Export sums')
      if regional:
       i=next(headers.index(x) for x in ['region','Région déclarée'] if x in headers)
       assert all(r[i]=='Bougouni' for r in rows[1:])
   checks+=1;print(json.dumps(dict(source=key,format=fmt,regional=regional,forbidden=forbidden,status_filter=status,rows=count)),flush=True)

if not args.readers_only:
 for key in SOURCES:
  for fmt in ['csv','xlsx']:export(key,fmt)
 export('disc','csv',status=True)
else:
 export('disc','csv',regional=True);export('disc','xlsx',regional=True);export('disc','csv',regional=True,forbidden=True);export('disc','csv',regional=True,status=True)
 for key in ['asa_history','asa_recent']:export(key,'csv',regional=True)
print(json.dumps(dict(status='OK',exports=checks)),flush=True)
