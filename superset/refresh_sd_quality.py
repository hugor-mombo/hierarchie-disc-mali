"""Refresh only our native summaries. Never mutate raw clinical/ASA/DISC views."""
import argparse,json
from time import perf_counter
from sqlalchemy import text
from superset.app import create_app
from sd_quality_sql import ROOT,CATALOG,CORE,COUNTERS,SOURCES,TABLE,raw,geography,snapshot_sql
parser=argparse.ArgumentParser();parser.add_argument('--only',choices=list(SOURCES));parser.add_argument('--create',action='store_true');args=parser.parse_args()
app=create_app()
with app.app_context():
 from superset import db
 from superset.models.core import Database
 for source,did in SOURCES.items():
  if args.only and args.only!=source:continue
  database=db.session.query(Database).filter_by(id=did).one()
  with database.get_sqla_engine() as engine:
   started=perf_counter()
   with engine.begin() as c:
    c.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
    c.execute(text("SET LOCAL statement_timeout='600s'"));c.execute(text("SET LOCAL lock_timeout='10s'"));c.execute(text("SET LOCAL TIME ZONE 'UTC'"));c.execute(text('SET LOCAL jit=off'))
    assert c.execute(text("SELECT pg_try_advisory_xact_lock(hashtext('sd_quality_v2_refresh'))")).scalar(),'Actualisation déjà en cours dans cette base'
    exists=c.execute(text('SELECT to_regclass(:n)'),dict(n='public.'+TABLE)).scalar()
    if exists and args.create:print(source+': source existante conservée',flush=True);continue
    sql=snapshot_sql(source)
    assert sql.strip()==(ROOT/'sql/supervision/quality'/(source+'.sql')).read_text().strip()
    assert not c.execute(text('SELECT site_uuid FROM ('+geography(source)+')g GROUP BY 1 HAVING count(*)>1 LIMIT 1')).first(),'Répertoire natif ambigu'
    assert not c.execute(text('SELECT uuid FROM ('+raw(source)+')r GROUP BY 1 HAVING count(*)>1 OR uuid IS NULL LIMIT 1')).first(),'Rapport UUID ambigu'
    target=TABLE+'_next' if exists else TABLE
    c.execute(text('CREATE MATERIALIZED VIEW public.'+target+' AS '+sql))
    assert not c.execute(text('SELECT entity_key,reported_month FROM '+target+' GROUP BY 1,2 HAVING count(*)>1 LIMIT 1')).first(),'Grain ambigu'
    assert not c.execute(text('SELECT 1 FROM '+target+' WHERE '+' OR '.join(k+'<0' for k in COUNTERS)+' LIMIT 1')).first(),'Valeur négative'
    for m in CATALOG:
     k=m['key'];parts=['den','missing','na','invalid']
     invalid=k+'_num>'+k+'_den OR '+k+'_missing>'+k+'_eligible'
     if m['kind'] in ['enum','rdt'] or (m['kind']=='score' and m['denominator']=='valid'):
      invalid+=' OR '+k+'_eligible<>'+ '+'.join(k+'_'+p for p in parts)
     assert not c.execute(text('SELECT 1 FROM '+target+' WHERE '+invalid+' LIMIT 1')).first(),k+' partition invalide'
    actual=c.execute(text('SELECT sum(reports),sum(site_months),count(*) FROM '+target)).one()
    expected=c.execute(text('SELECT count(*),count(DISTINCT(site_uuid,reported_month)) FILTER(WHERE site_uuid IS NOT NULL) FROM ('+raw(source)+')r')).one()
    assert tuple(actual[:2])==tuple(expected),'Rapports perdus ou multipliés'
    assert actual[2]<=100000,'Export territorial complet trop volumineux'
    assert not c.execute(text('SELECT 1 FROM '+target+' WHERE site_months<>score_valid+score_missing+score_invalid+latest_ambiguous OR score_valid<>acceptable+below80 LIMIT 1')).first(),'Partition du score invalide'
    c.execute(text('CREATE UNIQUE INDEX '+target+'_pk ON '+target+'(entity_key,reported_month)'))
    c.execute(text('CREATE INDEX '+target+'_geo ON '+target+'(region_uuid,reported_month)'))
    c.execute(text('ANALYZE '+target))
    if exists:
     c.execute(text('ALTER MATERIALIZED VIEW '+TABLE+' RENAME TO '+TABLE+'_previous'))
     c.execute(text('ALTER MATERIALIZED VIEW '+target+' RENAME TO '+TABLE))
     c.execute(text('DROP MATERIALIZED VIEW '+TABLE+'_previous'))
     for suffix in ['_pk','_geo']:c.execute(text('ALTER INDEX '+target+suffix+' RENAME TO '+TABLE+suffix))
   print(json.dumps(dict(source=source,status='committed',rows=actual[2],seconds=round(perf_counter()-started,2))),flush=True)
