"""Rendu et exports sous les vrais profils de consultation, avec contrôle RLS."""
import csv,io,json,re,sys,zipfile
from pathlib import Path
from uuid import UUID,uuid5
from sqlalchemy import text
sys.path.insert(0,str(Path(__file__).resolve().parent/'portal'))
from disc_portal_policy import editor
from superset.app import create_app
app=create_app();BASE='https://dashboard.disc-mali.ml'
with app.app_context():
 from superset import db,security_manager as sm
 from superset.models.dashboard import Dashboard
 from superset.connectors.sqla.models import SqlaTable,RowLevelSecurityFilter
 dataset=db.session.query(SqlaTable).filter_by(uuid=uuid5(UUID('07c165d2-f139-45b7-b36e-d001b859f7be'),'dataset')).one()
 dashboard=db.session.query(Dashboard).filter_by(slug='asc-pilotage').one()
 users=db.session.query(sm.user_model).all();rules=db.session.query(RowLevelSecurityFilter).filter(RowLevelSecurityFilter.tables.any(id=dataset.id)).all()
 profiles=[]
 for name,prefix in [('national','DISC_NATIONAL'),('region','DISC_REGION_'),('district','DISC_DISTRICT_')]:
  user=next(u for u in users if u.active and not editor(u) and any(r.name.startswith(prefix) for r in u.roles))
  scopes=[r.clause for r in rules if {x.id for x in r.roles}&{x.id for x in user.roles} and r.clause!='1 = 0']
  profiles.append((name,user.id,scopes))
 chart=next(c for c in dashboard.slices if c.datasource_id==dataset.id and json.loads(c.params).get('metric')=='inventory')
 form_data={**json.loads(chart.params),'slice_id':chart.id,'dashboardId':dashboard.id}
 source=dataset.sql;dataset_id=dataset.id;dashboard_id=dashboard.id
 with dataset.database.get_sqla_engine() as engine:
  with engine.connect() as c:
   c.execute(text('SET TRANSACTION READ ONLY'));c.execute(text("SET LOCAL statement_timeout='60s'"))
   expected={name:c.execute(text('SELECT count(DISTINCT site_uuid) FROM ('+source+")q WHERE in_period=1 AND reported_month=date_trunc('month',CURRENT_DATE)-interval '1 month'"+(' AND ('+' AND '.join(scopes)+')' if scopes else ''))).scalar() for name,_,scopes in profiles}
for name,user_id,scopes in profiles:
 with app.test_client() as c:
  with c.session_transaction(base_url=BASE) as s:s['_user_id']=str(user_id);s['_fresh']=True
  token=c.get('/api/v1/security/csrf_token/',base_url=BASE);assert token.status_code==200
  headers={'X-CSRFToken':token.json['result'],'Referer':BASE+'/'}
  query=dict(columns=[],metrics=['inventory'],filters=[],granularity='reported_month',time_range='previous calendar month',extras={'where':'','having':''},orderby=[],row_limit=100000)
  body=dict(datasource={'id':dataset_id,'type':'table'},force=True,queries=[query],form_data=form_data,result_format='json',result_type='full')
  result=c.post('/api/v1/chart/data',base_url=BASE,json=body,headers=headers)
  assert result.status_code==200,(name,result.status_code,str(result.json)[:200])
  assert result.json['result'][0]['data'][0]['inventory']==expected[name],(name,'RLS count')
  query['metrics']=[];query['columns']=['region_uuid','district_uuid','site_uuid'];query['extras']['where']='in_period=1'
  for fmt in ['csv','xlsx']:
   body['result_format']=fmt
   result=c.post('/api/v1/chart/data',base_url=BASE,json=body,headers=headers);assert result.status_code==200,(name,fmt,result.status_code,str(result.json)[:150] if result.is_json else '')
   if fmt=='csv':
    exported=list(csv.DictReader(io.StringIO(result.data.decode('utf-8-sig'))));assert len(exported)==expected[name]
    if name!='national':
     permitted=set(re.findall(r"[0-9a-f]{8}-[0-9a-f-]{27,}",' '.join(scopes)))
     key='district_uuid' if name=='district' else 'region_uuid'
     label='Identifiant district' if name=='district' else 'Identifiant région'
     assert all(row.get(key,row.get(label)) in permitted for row in exported),'Export hors périmètre'
   else:
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(io.BytesIO(result.data)) as z:
     sheet=ET.fromstring(z.read('xl/worksheets/sheet1.xml'));rows=sheet.findall('.//s:sheetData/s:row',{'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'})
     assert len(rows)-1==expected[name],(name,'XLSX rows')
  print(json.dumps({'profile':name,'dashboard_render':'OK','csv':'OK','xlsx':'OK','sites':expected[name],'rls':'OK'}),flush=True)
