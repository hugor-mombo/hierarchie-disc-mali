"""Regression cases and unchanged non-malaria monthly totals; never export patient rows."""
import argparse,json
from pathlib import Path
from sqlalchemy import text
from superset.app import create_app
from theme_sql import CATALOG,ROOT,table_name
p=argparse.ArgumentParser();p.add_argument('--save-baseline');p.add_argument('--baseline');args=p.parse_args();app=create_app()
theme=next(t for t in CATALOG if t['key']=='pec-enfant');other=[m['key'] for m in theme['metrics'] if m['key']!='malaria_simple'];table=table_name(theme)
with app.app_context():
 from superset import db
 from superset.models.core import Database
 database=db.session.query(Database).filter_by(id=1).one()
 with database.get_sqla_engine() as e:
  with e.connect() as c:
   c.execute(text('SET TRANSACTION READ ONLY'));c.execute(text("SET LOCAL TIME ZONE 'UTC'"));c.execute(text("SET LOCAL statement_timeout='180s'"))
   totals=[dict(r) for r in c.execute(text('SELECT reported_month,'+','.join('coalesce(sum('+k+'),0) AS '+k for k in other)+' FROM '+table+' GROUP BY 1 ORDER BY 1')).mappings()]
   serialized=json.loads(json.dumps(totals,default=str))
   if args.save_baseline:Path(args.save_baseline).write_text(json.dumps(serialized));print(f'Baseline mensuelle des {len(other)} autres compteurs enregistrée');raise SystemExit(0)
   if args.baseline:assert serialized==json.loads(Path(args.baseline).read_text()),'Autres compteurs mensuels modifiés'
   # The production SQL's raw projection is replaced by independent encounter fixtures.
   query=(ROOT/'sql/themes/malaria_u5.sql').read_text();start=query.index('WITH raw AS MATERIALIZED (');end=query.index('), ranked AS (',start)
   prefix="WITH raw(report_uuid,patient_uuid,site_uuid,submitted_at,consultation_day,malaria_classification,age_years) AS MATERIALIZED (VALUES "
   # Prior CTA-history fields are deliberately absent, just as for a first consultation.
   day="(date_trunc('month',CURRENT_DATE)-interval '1 month'+interval '10 days')::date"
   rows=[]
   def add(report,patient,site,hour,flag,age):
    quote=lambda x:'NULL' if x is None else "'"+x+"'"
    rows.append('('+','.join([quote(report),quote(patient),quote(site),day+"+interval '"+str(hour)+" hours'",day,quote(flag),'NULL::numeric' if age is None else str(age)])+')')
   add('a1','a','s1',8,'yes',2);add('a2','a','s1',9,'no',2) # latest negative must suppress an old positive
   add('b','b','s1',8,'yes',0.5) # first episode, no prior CTA history, counts
   add('c','c','s1',8,'no',3)
   add('d','d','s1',8,'yes',5) # wrong age, excluded
   add('e','e','s1',8,'yes',None)
   add('f1','f','s1',8,'yes',4);add('f2','f','s1',8,'no',4) # latest tie, excluded
   add('g1',None,'s1',8,'yes',1);add('g2',None,'s1',9,'yes',1) # missing IDs must not collapse
   add('h','h','s2',8,None,1)
   add('i1','i','s1',8,'yes',2);add('i2','i','s2',9,'yes',2) # latest site wins without double count
   result={r.entity_uuid:r.malaria_simple for r in c.execute(text(prefix+','.join(rows)+query[end:]))}
   assert result=={'s1':3,'s2':1},'Régression des règles de comptage'
   current=[dict(r) for r in c.execute(text('SELECT reported_month,sum(malaria_simple) all_sites,sum(malaria_simple) FILTER(WHERE attribution=\'Rattaché au répertoire courant\') mapped FROM '+table+' GROUP BY 1 ORDER BY 1')).mappings()]
   assert any(r['mapped'] and r['mapped']>0 for r in current),'Compteur toujours nul'
   print(json.dumps(dict(status='OK',fixtures='OK',other_counters_unchanged=bool(args.baseline),monthly=current),default=str,ensure_ascii=False))
