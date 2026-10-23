"""Regression check: historical SD labels and native French export remain usable."""
import csv,io,json
from superset.app import create_app
app=create_app();base='https://dashboard.disc-mali.ml'
with app.app_context():
 from superset import db,security_manager as sm
 from superset.connectors.sqla.models import SqlaTable
 from superset.models.slice import Slice
 for ds in db.session.query(SqlaTable).filter(SqlaTable.id.in_([21,22,24,27,29,31])).all():
  assert all(c.verbose_name and c.verbose_name!=c.column_name for c in ds.columns),(ds.id,'Raw SD labels remain')
 chart=db.session.query(Slice).filter_by(id=252).one();ds=db.session.query(SqlaTable).filter_by(id=chart.datasource_id).one();form=json.loads(chart.params)
 assert 'assignment_label' in form['groupby'] and 'assignment_status' not in form['groupby']
 body=dict(datasource={'id':ds.id,'type':'table'},force=True,queries=[dict(columns=form['groupby'],metrics=form['metrics'],filters=[],granularity='reported_month',time_range='previous calendar month',extras={'where':'','having':''},orderby=[],row_limit=100000,row_offset=0)],form_data={**form,'slice_id':chart.id,'dashboardId':39},result_format='csv',result_type='full')
 owner=sm.find_user(username='hmombo')
 with app.test_client() as client:
  with client.session_transaction(base_url=base) as s:s['_user_id']=str(owner.id);s['_fresh']=True
  csrf=client.get('/api/v1/security/csrf_token/',base_url=base);assert csrf.status_code==200
  response=client.post('/api/v1/chart/data',base_url=base,json=body,headers={'X-CSRFToken':csrf.json['result'],'Referer':base+'/superset/dashboard/sd-pilotage-disc/'})
  assert response.status_code==200
  rows=list(csv.reader(io.StringIO(response.data.decode('utf-8-sig'))));headers=rows[0]
  expected=[ds.verbose_map.get(k,k) for k in form['groupby']+form['metrics']]
  assert headers==expected,'French SD export headers'
  i=headers.index('Rattachement superviseur')
  assert set(r[i] for r in rows[1:]).issubset({'Affectation identifiée','Affectation en conflit','Affectation non identifiée'})
  from sqlalchemy import text
  with ds.database.get_sqla_engine() as e:
   with e.connect() as c:
    expected_count=c.execute(text('SELECT count(*) FROM ('+ds.sql+")q WHERE reported_month>=date_trunc('month',CURRENT_DATE)-interval '1 month' AND reported_month<date_trunc('month',CURRENT_DATE)")).scalar()
  assert len(rows)-1==expected_count
  print(json.dumps(dict(status='OK',historical_sd_datasets=6,sd_export_rows=len(rows)-1,headers='fr',assignment_labels='fr')),flush=True)
