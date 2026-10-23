"""Clinical indicator edge cases, native totals, French exports and RLS. No row data is logged."""
import argparse,csv,io,json,zipfile
from decimal import Decimal
from unittest.mock import patch
import xml.etree.ElementTree as ET
from sqlalchemy import text
from superset.app import create_app
from sd_quality_sql import CATALOG,CORE,COUNTERS,FIELDS,SOURCES,TABLE,uid,raw,geography,snapshot_sql,literal
parser=argparse.ArgumentParser();parser.add_argument('--readers-only',action='store_true');args=parser.parse_args()
app=create_app();base='https://dashboard.disc-mali.ml';region='39af6dc3-4cd1-4eb9-955a-46edb57a9988'
with app.app_context():
 from superset import db,security_manager as sm
 from superset.models.dashboard import Dashboard
 from superset.models.slice import Slice
 from superset.connectors.sqla.models import SqlaTable
 from superset.models.core import Database
 # Gunicorn imports /app/superset; file-based jobs may import the installed wheel.
 # Inspect the exact mounted catalog used by the web server, not the wheel’s empty catalog.
 from pathlib import Path
 pack=json.loads(Path('/app/superset/translations/fr/LC_MESSAGES/messages.json').read_text())['locale_data']['superset']
 assert pack['']['lang']=='fr' and pack['Apply filters']==['Appliquer les filtres'] and pack['Dashboards']==['Tableaux de bord']
 owner_id=sm.find_user(username='hmombo').id
 readers=db.session.query(sm.user_model).filter(sm.user_model.roles.any(name='DISC_REGION_bougouni')).all()
 reader_id=next(u.id for u in readers if u.is_active and any(r.name=='DISC_DASH_ASC_SUPERVISION' for r in u.roles) and not any(r.name in ['Admin','Alpha','DISC_NATIONAL'] for r in u.roles))
 for source,did in SOURCES.items():
  database=db.session.query(Database).filter_by(id=did).one()
  with database.get_sqla_engine() as e:
   with e.connect() as c:
    c.execute(text('SET TRANSACTION READ ONLY'));c.execute(text("SET LOCAL statement_timeout='120s'"));c.execute(text('SET LOCAL jit=off'));c.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    assert not c.execute(text('SELECT entity_key,reported_month FROM '+TABLE+' GROUP BY 1,2 HAVING count(*)>1 LIMIT 1')).first()
    n=c.execute(text('SELECT count(*) FROM '+TABLE)).scalar();assert n<=100000
    assert not c.execute(text('SELECT 1 FROM '+TABLE+" WHERE reported_month>=date_trunc('month',CURRENT_DATE) OR reported_month<date '2019-01-01' LIMIT 1")).first()
    assert not c.execute(text('SELECT 1 FROM '+TABLE+' WHERE site_months<>score_valid+score_missing+score_invalid+latest_ambiguous OR score_valid<>acceptable+below80 LIMIT 1')).first()
    for m in CATALOG:
     k=m['key'];condition=k+'_num>'+k+'_den OR '+k+'_missing>'+k+'_eligible'
     if m['kind'] in ['enum','rdt'] or (m['kind']=='score' and m['denominator']=='valid'):condition+=' OR '+k+'_eligible<>'+ '+'.join(k+'_'+part for part in ['den','missing','na','invalid'])
     assert not c.execute(text('SELECT 1 FROM '+TABLE+' WHERE '+condition+' LIMIT 1')).first(),k
    print(json.dumps(dict(source=source,status='OK',territorial_rows=n,indicators=len(CATALOG))),flush=True)
    if source=='disc':
     # Real production SQL with synthetic reports: newer low score, ambiguous tie, missing score, exact threshold.
     fixtures=[('r1','s1','2025-01-02 10:00:00','90'),('r2','s1','2025-01-03 10:00:00','70'),('r3','s2','2025-01-04 10:00:00','60'),('r4','s2','2025-01-04 10:00:00','90'),('r5','s3','2025-01-05 10:00:00',None),('r6','s4','2025-01-05 11:00:00','80')]
     rows=[]
     for uuid,site,when,score in fixtures:
      rows.append('SELECT '+literal(uuid)+'::text AS uuid,'+literal(site)+'::text AS site_uuid,TIMESTAMP '+literal(when)+" AS reported_at,DATE '2025-01-01' AS reported_month,"+('NULL::text' if score is None else literal(score)+'::text')+" AS score_text,'0'::text AS assessed_text,'1'::text AS applicable_text,"+','.join('NULL::text AS '+f for f in FIELDS))
     fixture_geo="SELECT unnest(ARRAY['s1','s2','s3','s4']) AS site_uuid,'fixture-region'::text AS region_uuid,'Fixture'::text AS region,'fixture-district'::text AS district_uuid,'Fixture'::text AS district_name,'fixture-area'::text AS health_area_uuid,'Fixture'::text AS cscom_name,'fixture-zone'::text AS supervisor_area_uuid,'Fixture'::text AS zone_name"
     q=snapshot_sql(source).replace(raw(source),' UNION ALL '.join(rows)).replace(geography(source),fixture_geo)
     result=c.execute(text('SELECT sum(site_months),sum(score_valid),sum(acceptable),sum(below80),sum(score_missing),sum(latest_ambiguous),sum(reports) FROM ('+q+')x')).one()
     assert tuple(result)==(4,2,1,1,1,1,6),('Latest visit edge cases',tuple(result))
     print(json.dumps(dict(latest_visit_edge_cases='OK',threshold=80,ambiguous_ties_excluded=True)),flush=True)

with app.test_request_context('/'):
 from flask import g
 from flask_login import login_user
 user=db.session.query(sm.user_model).filter_by(id=reader_id).one();login_user(user);g.user=user
 for source,did in SOURCES.items():
  for suffix in ['',':indicators']:
   ds=db.session.query(SqlaTable).filter_by(uuid=uid('dataset:'+source+suffix)).one();assert ds.database_id==did
   assert all(c.verbose_name and c.verbose_name!=c.column_name for c in ds.columns),'French column labels missing'
   data=ds.query(dict(columns=['region_uuid'],metrics=[],granularity=None,is_timeseries=False,from_dttm=None,to_dttm=None,row_limit=100,filter=[],orderby=[],extras={'where':'','having':''}))
   assert not data.error_message,data.error_message
   seen=set(data.df['region_uuid']) if not data.df.empty else set()
   assert seen.issubset({region}) if source=='disc' else not seen,'RLS boundary'
   with patch.object(sm,'get_user_roles',return_value=[sm.find_role('DISC_DASH_ASC_SUPERVISION')]):assert any(r.clause=='1 = 0' for r in sm.get_rls_filters(ds))
 print(json.dumps(dict(rls='OK',datasets=4,asa_territorial_access='denied_pending_native_scope',french_catalog=True)),flush=True)
checks=0

def export(source,fmt,regional=False,forbidden=False):
 global checks
 with app.app_context():
  user_id=reader_id if regional else owner_id
  chart=db.session.query(Slice).filter_by(uuid=uid('chart:'+source+':export')).one();form=json.loads(chart.params)
  ds=db.session.query(SqlaTable).filter_by(id=chart.datasource_id).one()
  dash=db.session.query(Dashboard).filter_by(uuid=uid('dashboard:'+source)).one()
  if regional:assert dash.published
  filters=[dict(col='region_uuid',op='IN',val=['63aec90d-9aa6-505d-80e4-4f4b2e4a5709'])] if forbidden else []
  time_range='No filter' if fmt=='csv' else form['time_range']
  where="mapping_status='Rattaché au répertoire courant'"
  if fmt=='xlsx':where+=(" AND reported_month>=date_trunc('month',CURRENT_DATE)-interval '1 month' AND reported_month<date_trunc('month',CURRENT_DATE)" if source=='disc' else " AND reported_month>='2025-01-01' AND reported_month<'2026-01-01'")
  if regional:where+=" AND region_uuid='"+region+"'"
  if forbidden:where+=' AND FALSE'
  body=dict(datasource={'id':ds.id,'type':'table'},force=True,queries=[dict(columns=form['groupby'],metrics=form['metrics'],filters=filters,granularity='reported_month',time_range=time_range,extras={'where':"mapping_status='Rattaché au répertoire courant'",'having':''},orderby=[],row_limit=100000,row_offset=0)],form_data={**form,'slice_id':chart.id,'dashboardId':dash.id},result_format=fmt,result_type='full')
  with app.test_client() as client:
   with client.session_transaction(base_url=base) as session:session['_user_id']=str(user_id);session['_fresh']=True
   me=client.get('/api/v1/me/',base_url=base);assert me.status_code==200 and me.json['result']['id']==user_id
   csrf=client.get('/api/v1/security/csrf_token/',base_url=base);assert csrf.status_code==200
   result=client.post('/api/v1/chart/data',base_url=base,json=body,headers={'X-CSRFToken':csrf.json['result'],'Referer':base+'/superset/dashboard/'+dash.slug+'/'})
   assert result.status_code==200,(source,fmt,result.status_code,str(result.json)[:300] if result.is_json else 'non-JSON')
   if fmt=='csv':
    rows=list(csv.reader(io.StringIO(result.data.decode('utf-8-sig'))));headers=rows[0] if rows else [];count=max(0,len(rows)-1)
   else:
    with zipfile.ZipFile(io.BytesIO(result.data)) as z:
     root=ET.fromstring(z.read('xl/worksheets/sheet1.xml'));count=max(0,len(root.findall('.//s:sheetData/s:row',{'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}))-1)
   with ds.database.get_sqla_engine() as engine:
    with engine.connect() as c:
     c.execute(text('SET TRANSACTION READ ONLY'));c.execute(text("SET LOCAL statement_timeout='60s'"))
     expected=c.execute(text('SELECT count(*) FROM (SELECT '+','.join(form['groupby'])+' FROM ('+ds.sql+')q WHERE '+where+' GROUP BY '+','.join(form['groupby'])+')x')).scalar()
     assert count==expected,(source,fmt,count,expected)
     if fmt=='csv' and count:
      expected_headers=[ds.verbose_map.get(k,k) for k in form['groupby']+form['metrics']]
      assert headers==expected_headers,'French export headers differ'
      definitions={m.metric_name:m.expression for m in ds.metrics}
      sums=c.execute(text('SELECT '+','.join(definitions[m]+' AS '+m for m in form['metrics'])+' FROM ('+ds.sql+')q WHERE '+where)).one()._mapping
      for metric in form['metrics']:
       index=headers.index(ds.verbose_map[metric]);total=sum((Decimal(r[index]) for r in rows[1:] if r[index]),Decimal(0))
       assert total==sums[metric],(source,metric,'CSV totals')
      if regional:
       index=headers.index(ds.verbose_map['region']);assert all(r[index]=='Bougouni' for r in rows[1:])
   checks+=1;print(json.dumps(dict(source=source,format=fmt,regional=regional,forbidden=forbidden,rows=count,headers='fr')),flush=True)
if not args.readers_only:
 for source in SOURCES:
  export(source,'csv');export(source,'xlsx')
else:
 for source in SOURCES:
  export(source,'csv',regional=True);export(source,'xlsx',regional=True)
 export('disc','csv',regional=True,forbidden=True)
print(json.dumps(dict(status='OK',exports=checks)),flush=True)
