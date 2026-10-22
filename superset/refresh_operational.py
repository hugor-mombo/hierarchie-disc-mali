"""Actualiser uniquement les sources du lot opérationnel, sans modifier les vues amont."""
import argparse
from pathlib import Path
from time import perf_counter
from sqlalchemy import text
from superset.app import create_app

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--create', action='store_true')
args = parser.parse_args()
app = create_app()
with app.app_context():
    from superset import db
    from superset.models.core import Database
    database = db.session.query(Database).filter_by(id=1).one()
    tables = [
        ('mv_asc_ops_geography', 'ops_geography.sql', 'site_uuid'),
        ('mv_asc_ops_accounts', 'ops_accounts_snapshot.sql', 'username'),
        ('mv_asc_ops_children_v2', 'ops_vaccine_snapshot.sql', 'patient_uuid'),
    ]

    def prepare(c):
        if not c.execute(text("SELECT pg_try_advisory_xact_lock(hashtext('asc_ops_refresh'))")).scalar():
            raise SystemExit('Actualisation opérationnelle déjà en cours')
        c.execute(text("SET LOCAL statement_timeout='600s'"))

    def run(c, name, filename, key):
        started = perf_counter()
        if args.create:
            c.execute(text(f'CREATE MATERIALIZED VIEW IF NOT EXISTS public.{name} AS ' +
                           (ROOT / 'sql' / filename).read_text()))
            c.execute(text(f'CREATE UNIQUE INDEX IF NOT EXISTS {name}_pk ON public.{name} ({key})'))
        else:
            c.execute(text(f'REFRESH MATERIALIZED VIEW CONCURRENTLY public.{name}'))
        c.execute(text(f'ANALYZE public.{name}'))
        print(f'{name} : {perf_counter()-started:.2f} s', flush=True)

    with database.get_sqla_engine() as engine:
        if args.create:
            # Sources nouvelles, encore sans tableau publié : reprendre après un échec
            # sans recalculer les vues déjà initialisées. Aucun remplacement implicite.
            for table in tables:
                with engine.begin() as c:
                    prepare(c)
                    run(c, *table)
        else:
            # Préparer les gros relevés à côté des tables lues par Superset.
            # REFRESH CONCURRENTLY réécrivait chaque ligne à cause de l'horodatage,
            # avec un coût excessif de comparaison/suppression/insertion.
            # La dimension géographique garde son OID, référencé dans les SQL des vues.
            with engine.begin() as c:
                prepare(c)
                run(c, *tables[0])
                for name, filename, key in tables[1:]:
                    started=perf_counter()
                    c.execute(text(f'CREATE MATERIALIZED VIEW public.{name}_next AS '+
                                   (ROOT/'sql'/filename).read_text()))
                    c.execute(text(f'CREATE UNIQUE INDEX {name}_next_pk ON public.{name}_next ({key})'))
                    c.execute(text(f'ANALYZE public.{name}_next'))
                    print(f'{name} : relevé préparé en {perf_counter()-started:.2f} s',flush=True)
                c.execute(text("SET LOCAL lock_timeout='10s'"))
                for name, _, _ in tables[1:]:
                    c.execute(text(f'ALTER MATERIALIZED VIEW public.{name} RENAME TO {name}_previous'))
                    c.execute(text(f'ALTER MATERIALIZED VIEW public.{name}_next RENAME TO {name}'))
                    # Seulement l'ancien agrégat de ce lot ; aucune donnée source.
                    c.execute(text(f'DROP MATERIALIZED VIEW public.{name}_previous'))
                    c.execute(text(f'ALTER INDEX public.{name}_next_pk RENAME TO {name}_pk'))
        print('Lot opérationnel : calculs validés', flush=True)
