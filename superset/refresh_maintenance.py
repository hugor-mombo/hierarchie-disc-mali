"""Préparer et remplacer uniquement les deux relevés IT, sans toucher aux sources."""
import json
from sqlalchemy import text
from superset.app import create_app
from maintenance_catalog import ROOT,TABLES
app=create_app()
with app.app_context():
 from superset import db
 from superset.models.core import Database
 with db.session.query(Database).filter_by(id=1).one().get_sqla_engine() as engine:
  with engine.begin() as c:
   c.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
   c.execute(text("SET LOCAL statement_timeout='180s'"));c.execute(text("SET LOCAL lock_timeout='10s'"));c.execute(text("SET LOCAL TIME ZONE 'UTC'"))
   assert c.execute(text("SELECT pg_try_advisory_xact_lock(hashtext('disc_it_maintenance_v1'))")).scalar(),'Calcul IT déjà en cours'
   for key,name in TABLES.items():
    sql=(ROOT/'sql/maintenance'/('events.sql' if key=='events' else 'devices.sql')).read_text()
    if key=='devices':sql=sql.replace('public.'+TABLES['events'],'public.'+TABLES['events']+'_next')
    c.execute(text('DROP MATERIALIZED VIEW IF EXISTS public.'+name+'_next'))
    c.execute(text('CREATE MATERIALIZED VIEW public.'+name+'_next AS '+sql))
    if key=='events':
     assert not c.execute(text('SELECT telemetry_id FROM public.'+name+'_next GROUP BY 1 HAVING count(*)>1 OR telemetry_id IS NULL LIMIT 1')).first(),'UUID télémétrie absent ou dupliqué'
     c.execute(text('CREATE UNIQUE INDEX '+name+'_next_pk ON public.'+name+'_next(telemetry_id)'))
     c.execute(text('CREATE INDEX '+name+'_next_pair ON public.'+name+'_next(username,device_id,telemetry_day)'))
    else:
     assert not c.execute(text('SELECT username,device_id FROM public.'+name+'_next GROUP BY 1,2 HAVING count(*)>1 OR username IS NULL LIMIT 1')).first(),'Grain IT dupliqué'
     assert not c.execute(text('SELECT 1 FROM public.'+name+'_next WHERE free_ratio<0 OR free_ratio>1 OR free_gib<0 LIMIT 1')).first(),'Mesure disque invalide'
     c.execute(text('CREATE UNIQUE INDEX '+name+'_next_pair ON public.'+name+'_next(username,coalesce(device_id,\'__none__\'))'))
   # Retirer l'ancien enfant avant l'ancien parent. Le nouvel enfant suit le nouvel OID parent.
   for key,name in reversed(list(TABLES.items())):
    c.execute(text('DROP MATERIALIZED VIEW IF EXISTS public.'+name))
    c.execute(text('ALTER MATERIALIZED VIEW public.'+name+'_next RENAME TO '+name))
    indexes=c.execute(text("SELECT indexname FROM pg_indexes WHERE schemaname='public' AND tablename=:name"),{'name':name}).scalars().all()
    for index in indexes:
     if '_next_' in index:c.execute(text('ALTER INDEX public.'+index+' RENAME TO '+index.replace('_next_','_')))
    c.execute(text('ANALYZE public.'+name))
   counts={key:c.execute(text('SELECT count(*) FROM public.'+name)).scalar() for key,name in TABLES.items()}
 print(json.dumps(dict(status='OK',counts=counts)),flush=True)
