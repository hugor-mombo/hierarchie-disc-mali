"""Exercise native exports and RLS for every theme. Never print or save individual rows."""
import argparse
import csv
import io
import json
import zipfile
from decimal import Decimal
from unittest.mock import patch
from uuid import UUID,uuid5
import xml.etree.ElementTree as ET
from sqlalchemy import text
from superset.app import create_app
from theme_sql import CATALOG,NS,table_name
parser=argparse.ArgumentParser()
parser.add_argument('--readers',action='store_true')
parser.add_argument('--regional-only',action='store_true')
parser.add_argument('--only',choices=[t['key'] for t in CATALOG])
parser.add_argument('--exclude',choices=[t['key'] for t in CATALOG])
args=parser.parse_args()
uid=lambda key:uuid5(UUID(NS),key)
app=create_app()
base='https://dashboard.disc-mali.ml'
with app.app_context():
 from superset import db,security_manager as sm
 from superset.models.dashboard import Dashboard
 from superset.models.slice import Slice
 from superset.models.core import Database
 from superset.connectors.sqla.models import SqlaTable
 owner_id=sm.find_user(username='hmombo').id
 candidates=db.session.query(sm.user_model).filter(sm.user_model.roles.any(name='DISC_REGION_bougouni')).all()
 reader_id=next(u.id for u in candidates if u.is_active and not any(r.name in ['Admin','Alpha','DISC_NATIONAL'] for r in u.roles))
region='39af6dc3-4cd1-4eb9-955a-46edb57a9988'
checks=[]
selected=[t for t in CATALOG if (not args.only or t['key']==args.only) and t['key']!=args.exclude]

def export(key,user_id,fmt,time_range='previous calendar month',forbidden=False,zero=False):
 with app.app_context():
  # Each client owns a fresh app context so Flask-Login cannot retain the previous identity.
  chart=db.session.query(Slice).filter_by(uuid=uid('chart:'+key+':'+('zero_export' if zero else 'export'))).one()
  dash=db.session.query(Dashboard).filter_by(uuid=uid('dashboard:'+key)).one()
  if user_id==reader_id:assert dash.published,'Publish only after administrator/visual checks'
  form=json.loads(chart.params);ds=db.session.query(SqlaTable).filter_by(id=chart.datasource_id).one()
  filters=[dict(col='region_uuid',op='IN',val=['63aec90d-9aa6-505d-80e4-4f4b2e4a5709'])] if forbidden else []
  condition="followup_status='Penta 1 non reçu déclaré — à confirmer'" if zero else "attribution='Rattaché au répertoire courant'"
  body=dict(datasource={'id':ds.id,'type':'table'},force=True,
   queries=[dict(columns=form['groupby'],metrics=form['metrics'],filters=filters,
    granularity=None if zero else 'reported_month',time_range='No filter' if zero else time_range,
    extras={'where':condition,'having':''},orderby=[],row_limit=100000,row_offset=0)],
   form_data={**form,'slice_id':chart.id,'dashboardId':dash.id},result_format=fmt,result_type='full')
  with app.test_client() as client:
   with client.session_transaction(base_url=base) as session:
    session['_user_id']=str(user_id);session['_fresh']=True
   me=client.get('/api/v1/me/',base_url=base)
   assert me.status_code==200 and me.json['result']['id']==user_id,'Wrong export identity'
   csrf=client.get('/api/v1/security/csrf_token/',base_url=base)
   assert csrf.status_code==200
   result=client.post('/api/v1/chart/data',base_url=base,json=body,
    headers={'X-CSRFToken':csrf.json['result'],'Referer':base+'/superset/dashboard/'+dash.slug+'/'})
   assert result.status_code==200,(key,fmt,result.status_code,str(result.json)[:500] if result.is_json else 'non-JSON error')
   if fmt=='csv':
    rows=list(csv.reader(io.StringIO(result.data.decode('utf-8-sig'))))
    headers=rows[0] if rows else [];row_count=max(0,len(rows)-1)
   else:
    with zipfile.ZipFile(io.BytesIO(result.data)) as archive:
     sheet=ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
     row_count=max(0,len(sheet.findall('.//s:sheetData/s:row',{'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}))-1)
   source=db.session.query(Database).filter_by(id=1).one()
   where=condition
   if not zero and time_range!='No filter':
    where+=" AND reported_month>=date_trunc('month',CURRENT_DATE)-interval '1 month' AND reported_month<date_trunc('month',CURRENT_DATE)"
   if user_id==reader_id:where+=" AND region_uuid='"+region+"'"
   if forbidden:where+=' AND 1=0'
   with source.get_sqla_engine() as e:
    with e.connect() as c:
     c.execute(text('SET TRANSACTION READ ONLY'));c.execute(text("SET LOCAL statement_timeout='45s'"))
     expected=c.execute(text('SELECT count(*) FROM (SELECT '+','.join(form['groupby'])+' FROM ('+ds.sql+')q WHERE '+where+' GROUP BY '+','.join(form['groupby'])+')x')).scalar()
     if not zero:
      theme=next(t for t in CATALOG if t['key']==key)
      sums=dict(c.execute(text('SELECT '+','.join('coalesce(sum('+m['key']+'),0) AS '+m['key'] for m in theme['metrics'])+' FROM ('+ds.sql+')q WHERE '+where)).one()._mapping)
   assert row_count==expected,(key,fmt,row_count,expected)
   if fmt=='csv' and row_count:
    assert len(headers)==len(form['groupby'])+len(form['metrics'])
    for alternatives in [('region','Région'),('district_name','District'),('cscom_name','CSCOM')]:
     assert any(x in headers for x in alternatives),alternatives
    if not zero:
     for m in theme['metrics']:
      index=next(headers.index(x) for x in ['m_'+m['key'],m['label']] if x in headers)
      total=sum((Decimal(row[index]) for row in rows[1:] if row[index]),Decimal(0))
      assert total==sums[m['key']],(key,m['key'],'Export totals differ')
    if user_id==reader_id:
     index=next(headers.index(x) for x in ['region','Région'] if x in headers)
     assert all(row[index]=='Bougouni' for row in rows[1:]),'Out-of-region row exported'
   check=dict(theme=key,format=fmt,regional=user_id==reader_id,full_period=time_range=='No filter',zero_dose=zero,forbidden=forbidden,rows=row_count)
   checks.append(check);print(json.dumps(check),flush=True)

with app.test_request_context('/'):
 from flask import g
 from flask_login import login_user
 user=db.session.query(sm.user_model).filter_by(id=reader_id).one();login_user(user);g.user=user
 datasets=db.session.query(SqlaTable).filter(SqlaTable.uuid.in_([uid('dataset:'+t['key']+suffix) for t in selected for suffix in ['',':indicators']]+([] if args.only or args.exclude else [uid('dataset:availability')]))).all()
 assert len(datasets)==len(selected)*2+(0 if args.only or args.exclude else 1)
 for ds in datasets:
  result=ds.query(dict(columns=['region_uuid'],metrics=[],granularity=None,is_timeseries=False,
   from_dttm=None,to_dttm=None,row_limit=100,filter=[],orderby=[],extras={'where':'','having':''}))
  assert not result.error_message,(ds.id,result.error_message)
  seen=set(result.df['region_uuid']) if not result.df.empty else set()
  assert seen.issubset({region}),(ds.id,'Regional boundary failed')
  with patch.object(sm,'get_user_roles',return_value=[sm.find_role('DISC_DASH_ASC_ACTIVITY')]):
   assert any(r.clause=='1 = 0' for r in sm.get_rls_filters(ds)),ds.id
 print(json.dumps(dict(regional_queries='OK',datasets=len(datasets),default_deny=True)),flush=True)

for theme in selected:
 if not args.regional_only:
  export(theme['key'],owner_id,'csv',time_range='No filter')
  export(theme['key'],owner_id,'xlsx')
 if args.readers or args.regional_only:
  export(theme['key'],reader_id,'csv')
  export(theme['key'],reader_id,'xlsx')
  export(theme['key'],reader_id,'csv',forbidden=True)
if not args.regional_only and (not args.only or args.only=='vaccination') and args.exclude!='vaccination':
 export('vaccination',owner_id,'csv',zero=True)
 export('vaccination',owner_id,'xlsx',zero=True)
if (args.readers or args.regional_only) and (not args.only or args.only=='vaccination') and args.exclude!='vaccination':
 export('vaccination',reader_id,'csv',zero=True)
 export('vaccination',reader_id,'xlsx',zero=True)
 export('vaccination',reader_id,'csv',zero=True,forbidden=True)
print(json.dumps(dict(status='OK',exports=len(checks))),flush=True)
