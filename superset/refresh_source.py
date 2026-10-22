"""À exécuter dans superset_app ; aucun identifiant dans ce dépôt."""
import argparse
from pathlib import Path
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
    with database.get_sqla_engine() as engine:
        with engine.begin() as connection:
            if not connection.execute(text(
                "SELECT pg_try_advisory_xact_lock(hashtext('asc_v2_refresh'))"
            )).scalar():
                raise SystemExit('Actualisation déjà en cours')
            connection.execute(text("SET statement_timeout='180s'"))
            if args.create:
                sql = (ROOT / 'sql/report_monthly.sql').read_text()
                connection.execute(text(
                    'CREATE MATERIALIZED VIEW IF NOT EXISTS public.mv_asc_v2_report_monthly AS ' + sql
                ))
                connection.execute(text(
                    'CREATE UNIQUE INDEX IF NOT EXISTS asc_v2_report_monthly_pk '
                    'ON public.mv_asc_v2_report_monthly (reported_month,site_key,quality)'
                ))
            else:
                connection.execute(text(
                    'REFRESH MATERIALIZED VIEW CONCURRENTLY public.mv_asc_v2_report_monthly'
                ))
            connection.execute(text('ANALYZE public.mv_asc_v2_report_monthly'))
        print('ASC V2 : source actualisée et transaction validée')
