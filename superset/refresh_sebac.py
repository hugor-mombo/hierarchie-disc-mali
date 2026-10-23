"""Atomically refresh our three SEBAC snapshots; upstream views remain untouched."""
import argparse,json
from time import perf_counter
from sqlalchemy import text
from superset.app import create_app
from sebac_sql import TABLES,sql
p=argparse.ArgumentParser();p.add_argument('--create',action='store_true');args=p.parse_args();app=create_app()
with app.app_context():
 from superset import db
 from superset.models.core import Database
 database=db.session.query(Database).filter_by(id=1).one()
 with database.get_sqla_engine() as e:
  started=perf_counter()
  with e.begin() as c:
   c.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
   for setting in ["statement_timeout='600s'","lock_timeout='10s'","TIME ZONE 'UTC'","jit=off"]:c.execute(text('SET LOCAL '+setting))
   assert c.execute(text("SELECT pg_try_advisory_xact_lock(hashtext('sebac_v1_refresh'))")).scalar(),'Calcul déjà en cours'
   assert not c.execute(text('SELECT chw_site_uuid FROM mv_superset_sd_portfolio GROUP BY 1 HAVING count(*)>1 OR chw_site_uuid IS NULL LIMIT 1')).first(),'Répertoire ambigu'
   existing={k:bool(c.execute(text('SELECT to_regclass(:n)'),{'n':'public.'+name}).scalar()) for k,name in TABLES.items()}
   assert len(set(existing.values()))==1,'Installation SEBAC partielle : intervention requise'
   if args.create and all(existing.values()):print('Sources existantes conservées');raise SystemExit(0)
   targets={k:name+('_next' if existing[k] else '') for k,name in TABLES.items()}
   keys={'reports':'report_uuid','alerts':'alert_key','sites':'site_uuid'}
   for key,name in TABLES.items():
    query=sql(key)
    for previous in TABLES:
     if previous!=key:query=query.replace('public.'+TABLES[previous],'public.'+targets[previous])
    target=targets[key];c.execute(text('CREATE MATERIALIZED VIEW public.'+target+' AS '+query))
    assert not c.execute(text('SELECT '+keys[key]+' FROM '+target+' GROUP BY 1 HAVING count(*)>1 OR '+keys[key]+' IS NULL LIMIT 1')).first(),key+' : grain ambigu'
    c.execute(text('CREATE UNIQUE INDEX '+target+'_pk ON '+target+'('+keys[key]+')'))
    c.execute(text('CREATE INDEX '+target+'_geo ON '+target+'(region_uuid,district_uuid,reported_month)'))
    if key=='reports':c.execute(text('CREATE INDEX '+target+'_alert ON '+target+'(alert_id)'))
    c.execute(text('ANALYZE '+target))
   reports,alerts,sites=(targets[k] for k in ['reports','alerts','sites'])
   origin=c.execute(text("SELECT count(*) FROM "+reports+" WHERE form IN ('sebac_detection','sebac_alert_notification') AND date_status='Date exploitable'")).scalar()
   assert c.execute(text('SELECT coalesce(sum(notification_reports),0) FROM '+alerts)).scalar()==origin,'Notifications perdues ou multipliées'
   assert c.execute(text('SELECT count(*) FROM '+sites)).scalar()==c.execute(text('SELECT count(*) FROM mv_superset_sd_portfolio')).scalar(),'Sites perdus'
   assert not c.execute(text('SELECT 1 FROM '+alerts+' WHERE verification_hours<0 OR age_days<0 OR (review_72h=1 AND verified_at IS NOT NULL) LIMIT 1')).first(),'Chronologie invalide'
   for key,name in TABLES.items():
    if existing[key]:
     c.execute(text('ALTER MATERIALIZED VIEW '+name+' RENAME TO '+name+'_previous'))
     c.execute(text('ALTER MATERIALIZED VIEW '+targets[key]+' RENAME TO '+name))
   for key,name in reversed(list(TABLES.items())):
    if existing[key]:
     c.execute(text('DROP MATERIALIZED VIEW '+name+'_previous'))
     for suffix in ['_pk','_geo']+(['_alert'] if key=='reports' else []):c.execute(text('ALTER INDEX '+targets[key]+suffix+' RENAME TO '+name+suffix))
   result={k:c.execute(text('SELECT count(*) FROM '+name)).scalar() for k,name in TABLES.items()}
  print(json.dumps(dict(status='committed',rows=result,origin_reports=origin,seconds=round(perf_counter()-started,2))),flush=True)
