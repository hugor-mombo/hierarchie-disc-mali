"""Build dedicated thematic snapshots; never refresh or change upstream clinical views."""
import argparse
import json
from time import perf_counter
from sqlalchemy import text
from superset.app import create_app
from theme_sql import ROOT,CATALOG,table_name,snapshot_sql
parser=argparse.ArgumentParser()
parser.add_argument('--create',action='store_true')
parser.add_argument('--preflight',action='store_true')
parser.add_argument('--only',choices=[t['key'] for t in CATALOG])
args=parser.parse_args()
app=create_app()
with app.app_context():
 from superset import db
 from superset.models.core import Database
 database=db.session.query(Database).filter_by(id=1).one()
 with database.get_sqla_engine() as engine:
  with engine.connect() as lock:
   acquired=lock.execute(text("SELECT pg_try_advisory_lock(hashtext('asc_themes_refresh'))")).scalar()
   lock.connection.commit()
   if not acquired:
    raise SystemExit('Actualisation thématique déjà en cours')
   try:
    selected=[t for t in CATALOG if not args.only or t['key']==args.only]
    # The costly communication source runs last. Each theme retains its last complete snapshot independently.
    selected.sort(key=lambda t:t['key']=='promotion')
    for theme in selected:
     with engine.begin() as c:
      c.execute(text("SET LOCAL statement_timeout='900s'"))
      c.execute(text("SET LOCAL lock_timeout='10s'"))
      c.execute(text("SET LOCAL TIME ZONE 'UTC'"))
      c.execute(text("SET LOCAL jit=off"))
      assert not c.execute(text('SELECT site_uuid FROM mv_asc_ops_geography GROUP BY 1 HAVING count(*)>1 LIMIT 1')).first()
      name=table_name(theme)
      sql=snapshot_sql(theme)
      assert sql.strip()==(ROOT/'sql/themes'/(theme['key']+'.sql')).read_text().strip(),'Generated SQL differs'
      if args.preflight:
       c.execute(text('EXPLAIN '+sql)).all()
       print(theme['key']+': SQL plan OK',flush=True)
       continue
      exists=c.execute(text('SELECT to_regclass(:name)'),dict(name='public.'+name)).scalar()
      if args.create and exists:
       print(name+': source existante conservée',flush=True)
       continue
      target=name if not exists else name+'_next'
      started=perf_counter()
      c.execute(text('CREATE MATERIALIZED VIEW public.'+target+' AS '+sql))
      # NULL entity is a quality bucket, retained nationally. Reject duplicates including NULL keys.
      assert not c.execute(text('SELECT 1 FROM public.'+target+' WHERE entity_uuid IS NOT NULL AND input_rows>1 LIMIT 1')).first(),theme['key']+' non-null source grain ambiguous'
      assert not c.execute(text('SELECT entity_uuid,reported_month FROM public.'+target+' GROUP BY 1,2 HAVING count(*)>1 LIMIT 1')).first(),theme['key']+' duplicate grain'
      columns=' OR '.join('('+m['key']+'<0 OR '+m['key']+"::text IN ('NaN','Infinity','-Infinity'))" for m in theme['metrics'])
      assert not c.execute(text('SELECT 1 FROM public.'+target+' WHERE '+columns+' LIMIT 1')).first(),theme['key']+' invalid counters'
      assert c.execute(text('SELECT count(*) FROM public.'+target+" WHERE attribution='Rattaché au répertoire courant'")).scalar()<=100000,theme['key']+' export exceeds 100000 rows'
      c.execute(text('CREATE UNIQUE INDEX '+target+'_pk ON public.'+target+' (entity_uuid,reported_month)'))
      c.execute(text('CREATE INDEX '+target+'_geo ON public.'+target+' (region_uuid,district_uuid,health_area_uuid,reported_month)'))
      c.execute(text('CREATE INDEX '+target+'_month ON public.'+target+' (reported_month)'))
      c.execute(text('ANALYZE public.'+target))
      if exists:
       c.execute(text('ALTER MATERIALIZED VIEW public.'+name+' RENAME TO '+name+'_previous'))
       c.execute(text('ALTER MATERIALIZED VIEW public.'+target+' RENAME TO '+name))
       c.execute(text('DROP MATERIALIZED VIEW public.'+name+'_previous'))
       for suffix in ['_pk','_geo','_month']:
        c.execute(text('ALTER INDEX public.'+target+suffix+' RENAME TO '+name+suffix))
      print(json.dumps(dict(theme=theme['key'],seconds=round(perf_counter()-started,2))),flush=True)
     print(theme['key']+': transaction validée',flush=True)
   finally:
    lock.execute(text("SELECT pg_advisory_unlock(hashtext('asc_themes_refresh'))"))
    lock.connection.commit()
  print('Tableaux thématiques : calcul terminé',flush=True)
