"""Relevé commun léger : aucune lecture des documents cliniques bruts."""
from pathlib import Path
from sqlalchemy import text
from superset.app import create_app
ROOT=Path(__file__).resolve().parent
app=create_app()
with app.app_context():
 from superset import db
 from superset.models.core import Database
 database=db.session.query(Database).filter_by(id=1).one()
 with database.get_sqla_engine() as engine:
  with engine.begin() as c:
   c.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
   c.execute(text("SET LOCAL statement_timeout='120s'"))
   c.execute(text("SET LOCAL lock_timeout='10s'"))
   c.execute(text("SET LOCAL TIME ZONE 'UTC'"))
   assert c.execute(text("SELECT pg_try_advisory_xact_lock(hashtext('disc_site_registry_v1'))")).scalar(),'Actualisation en cours'
   name='public.mv_disc_site_registry_v1'
   if c.execute(text('SELECT to_regclass(:n)'),{'n':name}).scalar():
    c.execute(text('REFRESH MATERIALIZED VIEW CONCURRENTLY '+name))
   else:
    c.execute(text('CREATE MATERIALIZED VIEW '+name+' AS '+(ROOT/'sql/site-registry/registry.sql').read_text()))
    c.execute(text('CREATE UNIQUE INDEX disc_site_registry_v1_pk ON '+name+'(site_uuid)'))
   assert c.execute(text('SELECT count(*) FROM '+name)).scalar()==c.execute(text('SELECT count(*) FROM mv_superset_sd_portfolio')).scalar()
   assert not c.execute(text('SELECT chw_site_uuid FROM mv_chw_site_hierarchy_reporting EXCEPT SELECT site_uuid FROM '+name+' LIMIT 1')).first(),'Sources amont désynchronisées : site ASC absent du portefeuille SD'
   c.execute(text('ANALYZE '+name))
   labels='public.mv_disc_site_registry_labels_v1'
   if c.execute(text('SELECT to_regclass(:n)'),{'n':labels}).scalar():
    c.execute(text('REFRESH MATERIALIZED VIEW CONCURRENTLY '+labels))
   else:
    c.execute(text('CREATE MATERIALIZED VIEW '+labels+' AS '+(ROOT/'sql/site-registry/geography.sql').read_text()))
    c.execute(text('CREATE UNIQUE INDEX disc_site_registry_labels_v1_pk ON '+labels+'(site_uuid)'))
   c.execute(text('ANALYZE '+labels))
   assert c.execute(text('SELECT count(*) FROM '+labels)).scalar()==c.execute(text('SELECT count(*) FROM '+name)).scalar(),'Écart de grain géographique'
   c.execute(text('CREATE OR REPLACE VIEW public.v_disc_site_registry_labels_v1 AS SELECT * FROM '+labels))
 print('Référentiel commun ASC / SD actualisé',flush=True)
