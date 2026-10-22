"""Contrôler les exports natifs et les périmètres sans sortie de lignes nominatives."""
import argparse
import csv
import io
import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
from uuid import UUID,uuid5
from sqlalchemy import text
from superset.app import create_app
ROOT=Path(__file__).resolve().parent
NS=UUID('c5e388d0-45bc-47d7-ae63-9eb53b2abbde')
parser=argparse.ArgumentParser()
parser.add_argument('--readers',action='store_true')
parser.add_argument('--regional-only',action='store_true')
args=parser.parse_args()
app=create_app()
base='https://dashboard.disc-mali.ml'
with app.app_context():
 from flask import g
 from flask_login import login_user
 from superset import db,security_manager as sm
 from superset.models.dashboard import Dashboard
 from superset.models.slice import Slice
 from superset.models.core import Database
 from superset.connectors.sqla.models import SqlaTable
 dash=db.session.query(Dashboard).filter_by(uuid=uuid5(NS,'dashboard')).one()
 dash_id,dash_slug,published=dash.id,dash.slug,dash.published
 owner_id=sm.find_user(username='hmombo').id
 users=db.session.query(sm.user_model).filter(sm.user_model.roles.any(name='DISC_REGION_bougouni')).all()
 reader_id=next(u.id for u in users if u.is_active and not any(r.name in ['Admin','Alpha','DISC_NATIONAL'] for r in u.roles))
 region='39af6dc3-4cd1-4eb9-955a-46edb57a9988'
 checks=[]
 def export(user_id,fmt,filters=None,condition='1=1'):
  # Aucun objet ORM ni identité mis en cache entre les contextes de clients.
  with app.app_context():
   chart=db.session.query(Slice).filter_by(uuid=uuid5(NS,'chart:export')).one()
   form=json.loads(chart.params)
   ds=db.session.query(SqlaTable).filter_by(id=chart.datasource_id).one()
   body=dict(datasource={'id':ds.id,'type':'table'},force=True,
    queries=[dict(columns=form['groupby'],metrics=form['metrics'],filters=filters or [],
     granularity='due_month',time_range='previous calendar month',
     extras={'where':'','having':'SUM(due_open)>0'},orderby=[],row_limit=100000,row_offset=0)],
    form_data={**form,'slice_id':chart.id,'dashboardId':dash_id},result_format=fmt,result_type='full')
   with app.test_client() as client:
    with client.session_transaction(base_url=base) as s:s['_user_id']=str(user_id);s['_fresh']=True
    me=client.get('/api/v1/me/',base_url=base)
    assert me.status_code==200 and me.json['result']['id']==user_id,'Identité incorrecte'
    csrf=client.get('/api/v1/security/csrf_token/',base_url=base)
    assert csrf.status_code==200
    r=client.post('/api/v1/chart/data',base_url=base,json=body,
     headers={'X-CSRFToken':csrf.json['result'],'Referer':base+'/superset/dashboard/'+dash_slug+'/'})
    assert r.status_code==200,(r.status_code,r.json)
    if fmt=='csv':
     rows=list(csv.reader(io.StringIO(r.data.decode('utf-8-sig'))))
     headers=rows[0] if rows else [];count=max(len(rows)-1,0)
    else:
     with zipfile.ZipFile(io.BytesIO(r.data)) as archive:
      sheet=ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
      count=len(sheet.findall('.//s:sheetData/s:row',{'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}))-1
    source=db.session.query(Database).filter_by(id=1).one()
    where="due_month>=date_trunc('month',CURRENT_DATE)-interval '1 month' AND due_month<date_trunc('month',CURRENT_DATE) AND ("+condition+")"
    with source.get_sqla_engine() as e:
     with e.connect() as c:
      c.execute(text('SET TRANSACTION READ ONLY'));c.execute(text("SET LOCAL statement_timeout='30s'"))
      expected=c.execute(text('SELECT count(*) FROM (SELECT '+','.join(form['groupby'])+
       ' FROM ('+ds.sql+')q WHERE '+where+' GROUP BY '+','.join(form['groupby'])+' HAVING SUM(due_open)>0)x')).scalar()
      expected_open=c.execute(text('SELECT coalesce(sum(due_open),0) FROM ('+ds.sql+')q WHERE '+where)).scalar()
    assert count==expected,(count,expected)
    if fmt=='csv' and count:
     assert len(headers)==len(form['groupby'])+len(form['metrics'])
     for alternatives in [('region','Région'),('district_name','District'),('cscom_name','CSCOM'),('username','Compte ASC')]:
      assert any(x in headers for x in alternatives),alternatives
     open_column=next(headers.index(x) for x in ['open','Échues encore ouvertes'] if x in headers)
     from decimal import Decimal
     assert sum(Decimal(row[open_column]) for row in rows[1:])==expected_open,'Effectifs exportés divergents'
    result={'format':fmt,'regional':user_id==reader_id,'rows':count,'open_tasks':str(expected_open)}
    checks.append(result);print(json.dumps(result),flush=True)
 # Requêtes effectives sous un profil régional, sur les deux nouveaux datasets.
 with app.test_request_context('/'):
  user=db.session.query(sm.user_model).filter_by(id=reader_id).one();login_user(user);g.user=user
  for key in ['facts','quality']:
   ds=db.session.query(SqlaTable).filter_by(uuid=uuid5(NS,key)).one()
   result=ds.query(dict(columns=['region_uuid'],metrics=[],granularity=None,is_timeseries=False,
    from_dttm=None,to_dttm=None,row_limit=100,filter=[],orderby=[],extras={'where':'','having':''}))
   assert not result.error_message,result.error_message
   seen=set(result.df['region_uuid']) if not result.df.empty else set()
   assert seen=={region},(key,'Périmètre régional incorrect')
   with patch.object(sm,'get_user_roles',return_value=[sm.find_role('DISC_DASH_ASC_ACTIVITY')]):
    assert any(r.clause=='1 = 0' for r in sm.get_rls_filters(ds)),key
  print(json.dumps({'regional_queries':'OK','default_deny':True}),flush=True)
 if not args.regional_only:
  export(owner_id,'csv');export(owner_id,'xlsx')
  export(owner_id,'csv',[{'col':'theme','op':'IN','val':['Nutrition']}],"theme='Nutrition'")
 if args.readers or args.regional_only:
  assert published,'Publier après contrôle du brouillon'
  export(reader_id,'csv',condition=f"region_uuid='{region}'")
  export(reader_id,'xlsx',condition=f"region_uuid='{region}'")
  export(reader_id,'csv',[{'col':'region_uuid','op':'IN','val':['63aec90d-9aa6-505d-80e4-4f4b2e4a5709']}],'1=0')
 print(json.dumps({'status':'OK','exports':checks}),flush=True)
