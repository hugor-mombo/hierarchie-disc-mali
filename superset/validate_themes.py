"""Read-only conservation, grain and export bounds checks for the thematic snapshots."""
import argparse
import json
from time import perf_counter
from sqlalchemy import text
from superset.app import create_app
from theme_sql import CATALOG,table_name,source_sql,raw_source_sql
parser=argparse.ArgumentParser()
parser.add_argument('--source',action='store_true')
parser.add_argument('--only',choices=[t['key'] for t in CATALOG])
args=parser.parse_args()
app=create_app()
with app.app_context():
 from superset import db
 from superset.models.core import Database
 d=db.session.query(Database).filter_by(id=1).one()
 checks=[]
 with d.get_sqla_engine() as e:
  with e.connect() as c:
   c.execute(text('SET TRANSACTION READ ONLY'));c.execute(text("SET LOCAL statement_timeout='900s'"));c.execute(text("SET LOCAL TIME ZONE 'UTC'"));c.execute(text("SET LOCAL jit=off"))
   for theme in [t for t in CATALOG if not args.only or t['key']==args.only]:
    start=perf_counter();name=table_name(theme);fields=[m['key'] for m in theme['metrics']]
    count=c.execute(text('SELECT count(*) FROM public.'+name)).scalar()
    exportable=c.execute(text('SELECT count(*) FROM public.'+name+" WHERE attribution='Rattaché au répertoire courant'")).scalar()
    assert exportable<=100000,(theme['key'],'Full period export exceeds row limit')
    assert not c.execute(text('SELECT entity_uuid,reported_month FROM '+name+' GROUP BY 1,2 HAVING count(*)>1 LIMIT 1')).first(),theme['key']
    assert not c.execute(text('SELECT 1 FROM '+name+''' WHERE reported_month<coverage_start OR reported_month>=coverage_end
      OR reported_month<>date_trunc('month',reported_month)::date OR calculated_at>CURRENT_TIMESTAMP LIMIT 1''')).first()
    if theme['grain']=='cscom':
     assert not c.execute(text('SELECT 1 FROM '+name+' WHERE site_uuid IS NOT NULL LIMIT 1')).first()
    else:
     assert not c.execute(text('SELECT 1 FROM '+name+" WHERE attribution='Rattaché au répertoire courant' AND site_uuid IS DISTINCT FROM entity_uuid LIMIT 1")).first()
    assert not c.execute(text('SELECT 1 FROM '+name+" WHERE attribution='Hors répertoire courant' AND region_uuid IS NOT NULL LIMIT 1")).first()
    cols=','.join('coalesce(sum('+f+'),0) AS '+f for f in fields)
    totals=dict(c.execute(text('SELECT '+cols+' FROM '+name)).one()._mapping)
    assert all(v>=0 and v.is_finite() for v in totals.values()),theme['key']
    grouped=c.execute(text('SELECT '+cols+' FROM (SELECT region_uuid,'+','.join('sum('+f+') AS '+f for f in fields)+' FROM '+name+' GROUP BY 1)x')).one()._mapping
    assert totals==dict(grouped),'Regional totals diverge'
    if args.source:
     expected=c.execute(text('WITH src AS ('+raw_source_sql(theme)+') SELECT count(*) AS n,'+cols+' FROM src')).one()._mapping
     input_count=c.execute(text('SELECT coalesce(sum(input_rows),0) FROM '+name)).scalar()
     assert expected['n']==input_count,(theme['key'],'Source rows multiplied or lost')
     assert totals=={f:expected[f] for f in fields},(theme['key'],'Counts changed during geographic attribution')
    quality=[dict(r._mapping) for r in c.execute(text('SELECT attribution,count(*) AS rows,min(reported_month) AS first_month,max(reported_month) AS last_month FROM '+name+' GROUP BY 1'))]
    checks.append(dict(theme=theme['key'],rows=count,indicators=len(fields),quality=quality,seconds=round(perf_counter()-start,2)))
    print(json.dumps(checks[-1],default=str,ensure_ascii=False),flush=True)
   if not args.only or args.only=='enregistrements':
    # Population age/sex buckets must partition distinct contact registrations.
    pop=next(t for t in CATALOG if t['key']=='enregistrements')
    buckets=[m['key'] for m in pop['metrics'] if m['key'].startswith('age_')]
    total=c.execute(text('SELECT '+ '+'.join('coalesce(sum('+f+'),0)' for f in buckets)+' FROM '+table_name(pop))).scalar()
    raw=c.execute(text("SELECT count(DISTINCT doc->>'_id') FROM raw_contacts WHERE doc->>'contact_type'='c92_household' AND doc->>'reported_date' ~ '^[0-9]{13}$' AND doc->>'reported_date'>=(extract(epoch FROM date_trunc('month',CURRENT_DATE)-interval '12 months')*1000)::bigint::text AND doc->>'reported_date'<(extract(epoch FROM date_trunc('month',CURRENT_DATE))*1000)::bigint::text AND to_timestamp((doc->>'reported_date')::bigint/1000)>=date_trunc('month',CURRENT_DATE)-interval '12 months' AND to_timestamp((doc->>'reported_date')::bigint/1000)<date_trunc('month',CURRENT_DATE)")).scalar()
    assert total==raw,('Non-exclusive population buckets',total,raw)
   # ZD exports use the existing controlled current snapshot, not monthly historical counts.
   assert not c.execute(text("SELECT 1 FROM mv_asc_ops_children_v2 WHERE followup_status='Penta 1 non reçu déclaré — à confirmer' AND (positive_recorded OR coalesce(deceased_recorded,false) OR NOT contact_exists OR age_months NOT BETWEEN 12 AND 59 OR latest_penta1 IS DISTINCT FROM 'no' OR site_uuid IS NULL) LIMIT 1")).first()
   print(json.dumps(dict(status='OK',themes=len(checks),source_checks=args.source),default=str),flush=True)
