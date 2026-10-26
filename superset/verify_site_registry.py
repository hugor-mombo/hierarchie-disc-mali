"""Contrôles du grain, des totaux comparés et des accès des deux dashboards."""
import argparse,csv,io,json
from pathlib import Path
from unittest.mock import patch
from sqlalchemy import text
from superset.app import create_app
from site_registry_catalog import uid,METRICS
ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--analytical-only',action='store_true');args=parser.parse_args()
app=create_app();base='https://dashboard.disc-mali.ml'
with app.app_context():
 from superset import db,security_manager as sm
 from superset.models.core import Database
 from superset.models.dashboard import Dashboard
 from superset.connectors.sqla.models import SqlaTable
 common=(ROOT/'sql/site-registry/monthly.sql').read_text();asc=(ROOT/'sql/sites_monthly.sql').read_text();sd=(ROOT/'sql/supervision/disc_sites.sql').read_text()
 database=db.session.query(Database).filter_by(id=1).one()
 with database.get_sqla_engine() as e:
  with e.connect() as c:
   c.execute(text('SET TRANSACTION READ ONLY'));c.execute(text("SET LOCAL statement_timeout='60s'"))
   def rows(sql):return [dict(r) for r in c.execute(text(sql)).mappings()]
   assert not rows('SELECT site_uuid FROM mv_disc_site_registry_v1 GROUP BY 1 HAVING count(*)>1 OR site_uuid IS NULL')
   assert not rows('WITH q AS ('+common+') SELECT site_uuid,reported_month FROM q GROUP BY 1,2 HAVING count(*)>1')
   assert not rows('SELECT chw_site_uuid FROM mv_chw_site_hierarchy_reporting EXCEPT SELECT site_uuid FROM mv_disc_site_registry_v1'),'ASC sites missing from common registry'
   native=rows("SELECT count(*) n FROM mv_chw_site_hierarchy_reporting WHERE reported_date<date_trunc('month',CURRENT_DATE)")[0]['n']
   where="reported_month=date_trunc('month',CURRENT_DATE)-interval '1 month'"
   expressions=','.join(expr+' AS '+name for name,_,expr in METRICS)
   totals=rows('WITH q AS ('+common+') SELECT '+expressions+' FROM q WHERE '+where)[0]
   assert totals['eligible']==native
   actual_asc=rows('WITH q AS ('+asc+') SELECT count(DISTINCT site_uuid) eligible,count(DISTINCT CASE WHEN report_count>0 THEN site_uuid END) reporters FROM q WHERE '+where)[0]
   actual_sd=rows('WITH q AS ('+sd+') SELECT count(DISTINCT site_uuid) inventory,count(DISTINCT CASE WHEN visited=1 THEN site_uuid END) visited FROM q WHERE '+where)[0]
   assert all(totals[k]==v for k,v in {**actual_asc,**actual_sd}.items()),(totals,actual_asc,actual_sd)
   for dimension in ['region_uuid','district_uuid','health_area_uuid']:
    scoped=rows('WITH q AS ('+common+') SELECT '+dimension+','+expressions+' FROM q WHERE '+where+' GROUP BY 1')
    for name in ['inventory','eligible','reporters','visited']:assert sum(r[name] or 0 for r in scoped)==totals[name],(dimension,name)
   # Same counts per site-month across every available SD month, not only current default.
   assert not rows('WITH common AS ('+common+'), sd AS ('+sd+''')
    SELECT c.reported_month FROM common c WHERE c.sd_available=1 AND c.in_period=1
    GROUP BY 1 HAVING count(*)<>(SELECT count(*) FROM sd s WHERE s.reported_month=c.reported_month)''')
   for col,identifier in [('district','district_uuid'),('cscom','health_area_uuid')]:
    assert not rows('SELECT '+col+' FROM v_disc_site_registry_labels_v1 GROUP BY 1 HAVING count(DISTINCT '+identifier+')>1')
   reasons=rows('WITH q AS ('+common+') SELECT scope_status,contact_status,count(*) sites FROM q WHERE '+where+' AND asc_in_period=0 GROUP BY 1,2')
   # Quantify what the creation cutoff removes; do not silently reinterpret earlier visits.
   removed=rows('''SELECT count(*) site_months,coalesce(sum(s.visit_chw_site_reports+s.visit_community_without_chw_reports+s.individual_feedback_reports),0) reports
    FROM mv_superset_sd_chw_monthly_status s JOIN mv_disc_site_registry_v1 g ON g.site_uuid=s.chw_site_uuid
    WHERE g.site_created_date>=s.reported_month+interval '1 month' OR g.site_created_date>CURRENT_DATE''')[0]
   scope=rows('WITH q AS ('+common+') SELECT region_uuid,district_uuid,region FROM q WHERE '+where+' AND region_uuid IS NOT NULL AND district_uuid IS NOT NULL GROUP BY 1,2,3 ORDER BY 1,2 LIMIT 1')[0]
   month=rows("SELECT (date_trunc('month',CURRENT_DATE)-interval '1 month')::date start,date_trunc('month',CURRENT_DATE)::date finish")[0]
   expected_export=rows('WITH q AS ('+common+') SELECT count(*) n FROM q WHERE '+where)[0]['n']
 print(json.dumps(dict(analytical='OK',totals=totals,reasons=reasons,excluded_precreation=removed),default=str,ensure_ascii=False),flush=True)
 if args.analytical_only:raise SystemExit(0)
 dataset=db.session.query(SqlaTable).filter_by(uuid=uid('dataset')).one()
 assert dataset.sql.strip()==common.strip()
 owner_id=sm.find_user(username='hmombo').id
 checks=[]
 for role_prefix,scope_col,scope_value in [('DISC_REGION_','region_uuid',scope['region_uuid']),('DISC_DISTRICT_','district_uuid',scope['district_uuid'])]:
  # Find a reader by the actual RLS rule, not by a guessed district name.
  from superset.connectors.sqla.models import RowLevelSecurityFilter
  rules=db.session.query(RowLevelSecurityFilter).filter(RowLevelSecurityFilter.tables.any(id=dataset.id)).all()
  role_names={r.name for rule in rules if scope_value in rule.clause for r in rule.roles if r.name.startswith(role_prefix)}
  users=db.session.query(sm.user_model).filter(sm.user_model.active==True).all()
  user=next(u for u in users if any(r.name in role_names for r in u.roles) and any(r.name=='DISC_DASH_ASC_SUPERVISION' for r in u.roles) and not any(r.name in ['Admin','Alpha','DISC_NATIONAL'] for r in u.roles))
  checks.append((user.id,scope_col,scope_value))
 dashboards=[db.session.query(Dashboard).filter_by(slug=slug).one() for slug in ['asc-pilotage','sd-pilotage-disc']]
 for dash in dashboards:
  assert dash.published
  new=[chart for chart in dash.slices if chart.datasource_id==dataset.id]
  assert len(new)==8,(dash.slug,len(new))
  meta=json.loads(dash.json_metadata)
  for f in meta['native_filter_configuration']:
   col=f.get('targets',[{}])[0].get('column',{}).get('name')
   if col in ['scope_status','contact_status','quota_status']:
    for chart in new:
     if json.loads(chart.params).get('metric') in ['inventory','eligible','reporters','visited']:assert chart.id in f['scope']['excluded']

# Exercise actual Superset chart API and exports, including restricted users.
for user_id,col,value in [(owner_id,None,None)]+checks:
 with app.test_client() as client:
  with client.session_transaction(base_url=base) as session:session['_user_id']=str(user_id);session['_fresh']=True
  token=client.get('/api/v1/security/csrf_token/',base_url=base);assert token.status_code==200
  headers={'X-CSRFToken':token.json['result'],'Referer':base+'/'}
  time_range=f"{month['start']} : {month['finish']}"
  filters=[]
  body=dict(datasource={'id':dataset.id,'type':'table'},force=True,
   queries=[dict(columns=[] if col is None else [col],metrics=['inventory','eligible','reporters','visited'],filters=filters,granularity='reported_month',time_range=time_range,extras={'where':'','having':''},orderby=[],row_limit=100000)],
   form_data={'datasource':f'{dataset.id}__table','viz_type':'table','dashboardId':dashboards[0].id},result_format='json',result_type='full')
  response=client.post('/api/v1/chart/data',base_url=base,json=body,headers=headers)
  assert response.status_code==200,(response.status_code,str(response.json)[:250])
  result=response.json['result'][0];assert not result.get('error'),result.get('error')
  if col:assert {r[col] for r in result['data']}.issubset({value})
  else:assert all(result['data'][0][k]==totals[k] for k in ['inventory','eligible','reporters','visited'])
  body['queries'][0]['columns']=['region_uuid','district_uuid','site_uuid','scope_status','contact_status'];body['queries'][0]['metrics']=[];body['result_format']='csv'
  response=client.post('/api/v1/chart/data',base_url=base,json=body,headers=headers);assert response.status_code==200
  export=list(csv.DictReader(io.StringIO(response.data.decode('utf-8-sig'))))
  if col:
   key=next(k for k in [col,'Identifiant région' if col=='region_uuid' else 'Identifiant district'] if k in export[0]);assert all(r[key]==value for r in export)
  else:assert len(export)==expected_export,(len(export),expected_export)
  if col:
   body['queries'][0]['filters']=[dict(col=col,op='NOT IN',val=[value])];body['result_format']='json'
   denied=client.post('/api/v1/chart/data',base_url=base,json=body,headers=headers);assert denied.status_code==200
   assert denied.json['result'][0]['data']==[],'Territorial leakage'
  print(json.dumps(dict(api='OK',scope=col or 'national',csv_rows=len(export))),flush=True)
with app.test_request_context('/'):
 from flask import g
 from flask_login import login_user
 user=db.session.query(sm.user_model).filter_by(id=checks[0][0]).one();login_user(user);g.user=user
 with patch.object(sm,'get_user_roles',return_value=[sm.find_role('DISC_DASH_ASC_SUPERVISION')]):assert any(r.clause=='1 = 0' for r in sm.get_rls_filters(dataset))
print(json.dumps({'status':'OK','default_deny':True}),flush=True)
