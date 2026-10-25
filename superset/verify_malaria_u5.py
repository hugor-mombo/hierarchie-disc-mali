"""Malaria pathway invariants, encounter regression cases and native baseline checks."""
import argparse,json
from pathlib import Path
from sqlalchemy import text
from superset.app import create_app
from theme_sql import CATALOG,ROOT,table_name
p=argparse.ArgumentParser();p.add_argument('--save-baseline');p.add_argument('--baseline');p.add_argument('--fixtures-only',action='store_true');args=p.parse_args();app=create_app()
theme=next(t for t in CATALOG if t['key']=='pec-enfant')
other=[m['key'] for m in theme['metrics'] if not m['key'].startswith('malaria_') and m['key'] not in {'fever_native','consult_native'}]+['malaria_simple']
table=table_name(theme)
with app.app_context():
 from superset import db
 from superset.models.core import Database
 database=db.session.query(Database).filter_by(id=1).one()
 with database.get_sqla_engine() as e:
  with e.connect() as c:
   c.execute(text('SET TRANSACTION READ ONLY'));c.execute(text("SET LOCAL TIME ZONE 'UTC'"));c.execute(text("SET LOCAL statement_timeout='180s'"))
   totals=[dict(r) for r in c.execute(text('SELECT reported_month,'+','.join('coalesce(sum('+k+'),0) AS '+k for k in other)+' FROM '+table+' GROUP BY 1 ORDER BY 1')).mappings()]
   serialized=json.loads(json.dumps(totals,default=str))
   if args.save_baseline:Path(args.save_baseline).write_text(json.dumps(serialized));print(f'Baseline mensuelle de {len(other)} compteurs enregistrée');raise SystemExit(0)
   if args.baseline:assert serialized==json.loads(Path(args.baseline).read_text()),'Compteurs non concernés ou paludisme simple modifiés : examiner les classifications sans TDR positif'
   query=(ROOT/'sql/themes/malaria_u5.sql').read_text();start=query.index('WITH raw AS MATERIALIZED (');end=query.index('), ranked AS (',start)
   prefix="WITH raw(report_uuid,patient_uuid,site_uuid,submitted_at,consultation_day,has_fever,malaria_classification,presumed_classification,rdt_result,age_years) AS MATERIALIZED (VALUES "
   day="(date_trunc('month',CURRENT_DATE)-interval '1 month'+interval '10 days')::date"
   rows=[]
   def add(report,patient,site,hour,flag,age,presumed='no',rdt=None,fever='yes'):
    quote=lambda x:'NULL::text' if x is None else "'"+x+"'::text"
    rows.append('('+','.join([quote(report),quote(patient),quote(site),day+"+interval '"+str(hour)+" hours'",day,quote(fever),quote(flag),quote(presumed),quote(rdt),'NULL::numeric' if age is None else str(age)])+')')
   add('a1','a','s1',8,'yes',2,rdt='positive');add('a2','a','s1',9,'no',2,rdt='negative')
   add('b','b','s1',8,'yes',0.5,rdt='positive') # first episode counts without prior CTA history
   add('c','c','s1',8,'no',3,rdt='negative')
   add('d','d','s1',8,'yes',5,rdt='positive');add('e','e','s1',8,'yes',None,rdt='positive')
   add('f1','f','s1',8,'yes',4,rdt='positive');add('f2','f','s1',8,'no',4,rdt='negative')
   add('g1',None,'s1',8,'yes',1,rdt='positive');add('g2',None,'s1',9,'yes',1,rdt='positive')
   add('h','h','s2',8,None,1,fever='no')
   add('i1','i','s1',8,'yes',2,rdt='positive');add('i2','i','s2',9,'yes',2,rdt='positive')
   add('j','j','s1',8,'no',2,presumed='yes') # truly untested presumed consultation
   add('k','k','s1',8,'yes',3,presumed='yes',rdt='positive') # conflict, counted only once in total
   add('l','l','s3',8,'yes',1) # native diagnosis without positive test must not become confirmed
   add('m','m','s3',8,'no',1,rdt='invalid')
   result={r['entity_uuid']:dict(r) for r in c.execute(text(prefix+','.join(rows)+query[end:])).mappings()}
   assert result['s2']['consult_native']==2 and result['s2']['fever_native']==1
   assert result['s1']['malaria_simple']==4 and result['s2']['malaria_simple']==1
   assert result['s1']['malaria_tested']==6 and result['s1']['malaria_presumed']==1 and result['s1']['malaria_suspected']==7
   assert result['s1']['malaria_conflicts']==1
   assert result['s3']['malaria_simple']==0 and result['s3']['malaria_suspected']==0 and result['s3']['malaria_conflicts']==2
   invariants='malaria_suspected<>malaria_tested+malaria_presumed OR malaria_tested<>malaria_positive+malaria_negative OR malaria_simple>malaria_positive'
   for row in result.values():
    assert row['malaria_suspected']==row['malaria_tested']+row['malaria_presumed']
    assert row['malaria_tested']==row['malaria_positive']+row['malaria_negative']
    assert row['malaria_simple']<=row['malaria_positive']
   if args.fixtures_only:print(json.dumps(dict(status='OK',fixtures='OK')));raise SystemExit(0)
   assert not c.execute(text('SELECT 1 FROM '+table+' WHERE '+invariants+' LIMIT 1')).first(),'Partition du parcours invalide'
   names=[m['key'] for m in theme['metrics'] if m['key'].startswith('malaria_')]
   current=[dict(r) for r in c.execute(text('SELECT reported_month,'+','.join('sum('+x+') AS '+x for x in names)+' FROM '+table+" WHERE attribution='Rattaché au répertoire courant' GROUP BY 1 ORDER BY 1")).mappings()]
   assert any(r['malaria_simple'] and r['malaria_simple']>0 for r in current)
   print(json.dumps(dict(status='OK',fixtures='OK',partitions='OK',baseline_unchanged=bool(args.baseline),monthly=current),default=str,ensure_ascii=False))
