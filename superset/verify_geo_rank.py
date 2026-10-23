"""Exercise native query/API exports, eligible rankings, GPS edges and territorial RLS."""
import csv,io,json,zipfile
from unittest.mock import patch
from sqlalchemy import text
from superset.app import create_app
from geo_rank_sql import uid,TABLES,GPS,ASC,GEO
app=create_app();base='https://dashboard.disc-mali.ml';bougouni='39af6dc3-4cd1-4eb9-955a-46edb57a9988'
with app.app_context():
 from superset import db,security_manager as sm
 from superset.models.dashboard import Dashboard
 from superset.models.slice import Slice
 from superset.connectors.sqla.models import SqlaTable
 from superset.models.core import Database
 from superset.utils.date_parser import get_since_until
 owner=sm.find_user(username='hmombo').id
 readers=db.session.query(sm.user_model).filter(sm.user_model.roles.any(name='DISC_REGION_bougouni')).all()
 reader=next(u.id for u in readers if u.is_active and any(r.name=='DISC_DASH_ASC_SUPERVISION' for r in u.roles) and not any(r.name in ['Admin','Alpha','DISC_NATIONAL'] for r in u.roles))
 database=db.session.query(Database).filter_by(id=1).one()
 with database.get_sqla_engine() as e:
  with e.connect() as c:
   c.execute(text('SET TRANSACTION READ ONLY'));c.execute(text("SET LOCAL statement_timeout='120s'"));c.execute(text("SET LOCAL TIME ZONE 'UTC'"))
   # Replace only raw forms and the native geography with explicit test fixtures.
   raw_start=GPS.index(' SELECT uuid,');raw_end=GPS.index('\n), parts AS')
   rows=[("'r1'","'s1'","CURRENT_TIMESTAMP-interval '2 days'","'12 -7 0 5'"),("'r2'","'s1'","CURRENT_TIMESTAMP-interval '1 day'","'999 -7 0 5'"),("'r3'","'s2'","CURRENT_TIMESTAMP-interval '1 day'","'12 -7 0 5'"),("'r4'","'s2'","CURRENT_TIMESTAMP-interval '1 day'","'12 -7 0 5'"),("'r5'","'s3'","CURRENT_TIMESTAMP-interval '1 day'","'0 0 0 5'"),("'r6'","'s4'","CURRENT_TIMESTAMP-interval '1 day'","'12 -7 0 5'")]
   fixture=' UNION ALL '.join('SELECT '+uuid+'::text AS uuid,'+site+'::text AS site_uuid,'+when+' AS reported,'+point+'::text AS point' for uuid,site,when,point in rows)
   geo="(SELECT unnest(ARRAY['s1','s2','s3','s4','s5']) AS chw_site_uuid)"
   q=GPS[:raw_start]+fixture+GPS[raw_end:];q=q.replace(GEO,'p.chw_site_uuid AS site_uuid').replace('public.mv_superset_sd_portfolio p',geo+' p')
   actual={r.site_uuid:r.gps_status for r in c.execute(text(q))}
   assert actual=={'s1':'Coordonnées absentes ou invalides','s2':'Dernier relevé ambigu','s3':'Coordonnées absentes ou invalides','s4':'Coordonnées exploitables','s5':'Sans relevé GPS'},actual
   print(json.dumps(dict(gps_edge_cases='OK',latest_invalid_not_masked=True,zero_and_ties_excluded=True)),flush=True)
   a_start=ASC.index(' SELECT uuid,');a_end=ASC.index('\n), ranked AS')
   fixture="SELECT 'r1'::text uuid,'s1'::text site_uuid,TIMESTAMP '2025-01-01 12:00' reported_at,DATE '2025-01-01' reported_month,'90'::text score_text UNION ALL SELECT 'r2','s1',TIMESTAMP '2025-01-02 12:00',DATE '2025-01-01','70' UNION ALL SELECT 'r3','s2',TIMESTAMP '2025-01-01 12:00',DATE '2025-01-01','80' UNION ALL SELECT 'r4','s3',TIMESTAMP '2025-01-01 12:00',DATE '2025-01-01',NULL"
   q=(ASC[:a_start]+fixture+ASC[a_end:]).replace(GEO,'p.chw_site_uuid AS site_uuid').replace('public.mv_superset_sd_portfolio p',geo+' p')
   actual=c.execute(text('SELECT sum(score_total),sum(assessed),sum(acceptable),sum(visited),sum(unusable) FROM ('+q+')x')).one()
   assert tuple(actual)==(150,2,1,3,1),tuple(actual)
   print(json.dumps(dict(asc_latest_score='OK',missing_not_zero=True)),flush=True)
   for key,(name,_) in TABLES.items():
    assert not c.execute(text('SELECT site_uuid,reported_month FROM '+name+' GROUP BY 1,2 HAVING count(*)>1 LIMIT 1')).first()
   assert not c.execute(text("SELECT supervisor_uuid FROM mv_disc_sd_ranking_v1 WHERE assignment_status='assigned' GROUP BY 1 HAVING count(DISTINCT supervisor_name)>1 LIMIT 1")).first(),'Inconsistent supervisor names'
with app.test_request_context('/'):
 from flask import g
 from flask_login import login_user
 user=db.session.query(sm.user_model).filter_by(id=reader).one();login_user(user);g.user=user
 for key in TABLES:
  ds=db.session.query(SqlaTable).filter_by(uuid=uid('dataset:'+key)).one()
  result=ds.query(dict(columns=['region_uuid'],metrics=[],granularity=None,is_timeseries=False,from_dttm=None,to_dttm=None,row_limit=100,filter=[],orderby=[],extras={'where':'','having':''}))
  assert not result.error_message,result.error_message
  assert set(result.df.region_uuid).issubset({bougouni})
  with patch.object(sm,'get_user_roles',return_value=[sm.find_role('DISC_DASH_ASC_SUPERVISION')]):assert any(r.clause=='1 = 0' for r in sm.get_rls_filters(ds))
 print(json.dumps(dict(rls='OK',datasets=3,default_deny=True)),flush=True)
checks=0
for key in TABLES:
 for chart_key in (['todo','all'] if key=='geo' else ['top','support','export','small']):
  for regional,fmt in [(False,'json'),(True,'csv')]+([(False,'xlsx')] if chart_key in ['all','export'] else [])+([(True,'json')] if chart_key in ['all','top','support'] else []):
   with app.app_context():
    chart=db.session.query(Slice).filter_by(uuid=uid('chart:'+key+':'+chart_key)).one();form=json.loads(chart.params);ds=db.session.query(SqlaTable).filter_by(id=chart.datasource_id).one()
    dash=db.session.query(Dashboard).filter_by(uuid=uid('dashboard:'+key)).one()
    if regional and not dash.published:continue
    where=' AND '.join(f['sqlExpression'] for f in form['adhoc_filters'] if f['clause']=='WHERE');having=' AND '.join(f['sqlExpression'] for f in form['adhoc_filters'] if f['clause']=='HAVING')
    metric=form.get('timeseries_limit_metric',form['metrics'][0]);orderby=[[metric,not form.get('order_desc',True)]]
    query=dict(columns=form['groupby'],metrics=form['metrics'],filters=[],granularity='reported_month',time_range=form['time_range'],extras={'where':where,'having':having},orderby=orderby,row_limit=form['row_limit'],row_offset=0)
    body=dict(datasource={'id':ds.id,'type':'table'},force=True,queries=[query],form_data={**form,'slice_id':chart.id,'dashboardId':dash.id},result_format=fmt,result_type='full')
    with app.test_client() as client:
     with client.session_transaction(base_url=base) as session:session['_user_id']=str(reader if regional else owner);session['_fresh']=True
     csrf=client.get('/api/v1/security/csrf_token/',base_url=base);assert csrf.status_code==200
     response=client.post('/api/v1/chart/data',base_url=base,json=body,headers={'X-CSRFToken':csrf.json['result'],'Referer':base+'/superset/dashboard/'+dash.slug+'/'})
     assert response.status_code==200,(key,chart_key,fmt,response.status_code,str(response.json)[:300] if response.is_json else '')
     if fmt=='json':
      result=response.json['result'][0];assert not result.get('error'),result.get('error');rows=result['data']
      values=[r[metric] for r in rows if r[metric] is not None];assert values==sorted(values,reverse=form.get('order_desc',True))
      if chart_key in ['top','support']:
       assert len(rows)<=10
       assert all((r['sites']>=5 if key=='sd' else r['evaluations']>=3) for r in rows)
       if chart_key=='support':assert all((r['rate']<1 if key=='sd' else r['average']<80) for r in rows)
     elif fmt=='csv':
      rows=list(csv.reader(io.StringIO(response.data.decode('utf-8-sig'))));expected=[ds.verbose_map.get(n,n) for n in form['groupby']+form['metrics']]
      if rows:assert rows[0]==expected,'French headers'
      # SD group is nominal; verify RLS by server query below, not by assuming names imply region.
     else:
      with zipfile.ZipFile(io.BytesIO(response.data)) as z:assert 'xl/worksheets/sheet1.xml' in z.namelist()
     if fmt=='json':
      # Compare full native SQL aggregation AFTER time and territorial filters.
      start,end=get_since_until(form['time_range']);clauses=[where or 'TRUE']
      params={}
      if start:clauses.append('reported_month>=:start');params['start']=start
      if end:clauses.append('reported_month<:end');params['end']=end
      if regional:clauses.append('region_uuid=:region');params['region']=bougouni
      definitions={m.metric_name:m.expression for m in ds.metrics}
      sql='SELECT '+','.join(form['groupby']+[definitions[m]+' AS '+m for m in form['metrics']])+' FROM ('+ds.sql+')q WHERE '+' AND '.join(clauses)+' GROUP BY '+','.join(form['groupby'])+(' HAVING '+having if having else '')+' ORDER BY '+metric+(' DESC' if form.get('order_desc',True) else ' ASC')+' LIMIT '+str(form['row_limit'])
      with ds.database.get_sqla_engine() as e:
       with e.connect() as c:
        c.execute(text('SET TRANSACTION READ ONLY'));expected=list(c.execute(text(sql),params).mappings())
      assert len(rows)==len(expected),(key,chart_key,'row count')
      # Compare ranked metric values; ties at the 10-row boundary need not choose identical UUIDs.
      assert [round(float(r[metric]),8) if r[metric] is not None else None for r in rows]==[round(float(r[metric]),8) if r[metric] is not None else None for r in expected],(key,chart_key,'ranking values')
     checks+=1;print(json.dumps(dict(dataset=key,chart=chart_key,regional=regional,format=fmt,status='OK')),flush=True)
print(json.dumps(dict(status='OK',native_api_checks=checks)),flush=True)
