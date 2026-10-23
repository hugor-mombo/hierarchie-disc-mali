"""Atomic DISC-only snapshots, no upstream writes or stored precise coordinates."""
import argparse,json
from time import perf_counter
from sqlalchemy import text
from superset.app import create_app
from geo_rank_sql import ROOT,TABLES
parser=argparse.ArgumentParser();parser.add_argument('--create',action='store_true');args=parser.parse_args()
app=create_app()
with app.app_context():
 from superset import db
 from superset.models.core import Database
 database=db.session.query(Database).filter_by(id=1).one()
 with database.get_sqla_engine() as engine:
  with engine.begin() as c:
   c.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
   c.execute(text("SET LOCAL statement_timeout='600s'"));c.execute(text("SET LOCAL lock_timeout='10s'"));c.execute(text("SET LOCAL TIME ZONE 'UTC'"));c.execute(text('SET LOCAL jit=off'))
   assert c.execute(text("SELECT pg_try_advisory_xact_lock(hashtext('disc_geo_ranking_v1'))")).scalar(),'Actualisation en cours'
   assert not c.execute(text('SELECT chw_site_uuid FROM mv_superset_sd_portfolio GROUP BY 1 HAVING count(*)>1 OR chw_site_uuid IS NULL LIMIT 1')).first(),'Répertoire ambigu'
   for key,(name,sql) in TABLES.items():
    started=perf_counter();exists=c.execute(text('SELECT to_regclass(:n)'),dict(n='public.'+name)).scalar()
    if exists and args.create:continue
    assert sql.strip()==(ROOT/'sql/supervision/geo-ranking'/(key+'.sql')).read_text().strip()
    target=name+'_next' if exists else name
    c.execute(text('CREATE MATERIALIZED VIEW '+target+' AS '+sql))
    assert not c.execute(text('SELECT site_uuid,reported_month FROM '+target+' GROUP BY 1,2 HAVING count(*)>1 LIMIT 1')).first(),'Grain ambigu'
    if key=='geo':
     assert c.execute(text('SELECT count(*) FROM '+target)).scalar()==c.execute(text('SELECT count(*) FROM mv_superset_sd_portfolio')).scalar()
     assert not c.execute(text('SELECT 1 FROM '+target+" WHERE gps_valid NOT IN (0,1) OR outside_envelope>gps_valid OR older_year>gps_valid LIMIT 1")).first()
    if key=='asc':
     assert not c.execute(text('SELECT 1 FROM '+target+' WHERE assessed+unusable<>visited OR acceptable>assessed OR score_total<0 OR score_total>100*assessed LIMIT 1')).first()
    c.execute(text('CREATE UNIQUE INDEX '+target+'_pk ON '+target+'(site_uuid,reported_month)'))
    c.execute(text('CREATE INDEX '+target+'_geo ON '+target+'(region_uuid,reported_month)'))
    c.execute(text('ANALYZE '+target))
    if exists:
     c.execute(text('ALTER MATERIALIZED VIEW '+name+' RENAME TO '+name+'_previous'))
     c.execute(text('ALTER MATERIALIZED VIEW '+target+' RENAME TO '+name))
     c.execute(text('DROP MATERIALIZED VIEW '+name+'_previous'))
     for suffix in ['_pk','_geo']:c.execute(text('ALTER INDEX '+target+suffix+' RENAME TO '+name+suffix))
    print(json.dumps(dict(source=key,prepared=True,seconds=round(perf_counter()-started,2))),flush=True)
  print('Snapshots DISC committed atomically',flush=True)
