"""Préparer un agrégat de tâches sans modifier les sources CHT ni les autres lots."""
import argparse
import json
from pathlib import Path
from time import perf_counter
from sqlalchemy import text
from superset.app import create_app

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--create',action='store_true')
args=parser.parse_args()
app=create_app()
with app.app_context():
 from superset import db
 from superset.models.core import Database
 source=db.session.query(Database).filter_by(id=1).one()
 sql=(ROOT/'sql/tasks_rollup.sql').read_text()
 catalog=json.dumps(json.loads((ROOT/'task_catalog.json').read_text()),ensure_ascii=False)
 name='mv_asc_tasks_rollup'
 started=perf_counter()
 with source.get_sqla_engine() as engine:
  with engine.begin() as c:
   if not c.execute(text("SELECT pg_try_advisory_xact_lock(hashtext('asc_tasks_refresh'))")).scalar():
    raise SystemExit('Calcul des tâches déjà en cours')
   c.execute(text("SET LOCAL statement_timeout='900s'"))
   exists=c.execute(text('SELECT to_regclass(:name)'),{'name':'public.'+name}).scalar()
   if args.create and exists:
    raise SystemExit('Source déjà initialisée ; utiliser le rafraîchissement normal')
   target=name+'_next' if exists else name
   c.execute(text('CREATE MATERIALIZED VIEW public.'+target+' AS '+sql),{'catalog':catalog})
   c.execute(text(f"CREATE UNIQUE INDEX {target}_pk ON public.{target} (username,task_code,coalesce(due_month,DATE '1900-01-01'),record_quality)"))
   c.execute(text(f'CREATE INDEX {target}_period ON public.{target} (due_month,username)'))
   c.execute(text(f'ANALYZE public.{target}'))
   if exists:
    c.execute(text("SET LOCAL lock_timeout='10s'"))
    c.execute(text(f'ALTER MATERIALIZED VIEW public.{name} RENAME TO {name}_previous'))
    c.execute(text(f'ALTER MATERIALIZED VIEW public.{target} RENAME TO {name}'))
    c.execute(text(f'DROP MATERIALIZED VIEW public.{name}_previous'))
    for suffix in ['pk','period']:
     c.execute(text(f'ALTER INDEX public.{target}_{suffix} RENAME TO {name}_{suffix}'))
 print(json.dumps({'status':'OK','seconds':round(perf_counter()-started,2)},ensure_ascii=False),flush=True)
