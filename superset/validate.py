"""Contrôles d'intégration, en lecture seule sur les données analytiques."""
import json
from time import perf_counter
from pathlib import Path
from sqlalchemy import text
from superset.app import create_app

ROOT = Path(__file__).resolve().parent
app = create_app()
with app.app_context():
    from superset import db
    from superset.models.core import Database
    from superset.utils.date_parser import get_since_until
    from datetime import date
    start, end = get_since_until(time_range='previous calendar month')
    assert start.day == end.day == 1 and start < end
    assert end.date() == date.today().replace(day=1), (start, end)
    database = db.session.query(Database).filter_by(id=1).one()
    with database.get_sqla_engine() as engine:
        with engine.connect() as c:
            c.execute(text('SET TRANSACTION READ ONLY'))
            c.execute(text("SET LOCAL statement_timeout='60s'"))
            sql = (ROOT / 'sql/sites_monthly.sql').read_text()
            durations = []

            def query(q):
                started = perf_counter()
                rows = [dict(r._mapping) for r in c.execute(text(q))]
                durations.append(perf_counter() - started)
                return rows

            assert not query(f'''WITH sites AS ({sql})
                SELECT site_uuid,reported_month FROM sites GROUP BY 1,2 HAVING count(*)<>1'''), 'Doublons site/mois'
            assert not query(f'''WITH sites AS ({sql})
                SELECT 1 FROM sites WHERE report_count < 0 OR last_reported > CURRENT_TIMESTAMP LIMIT 1'''), 'Rapports négatifs ou futurs'
            expected = query('''SELECT count(*) n FROM mv_chw_site_hierarchy_reporting
                WHERE reported_date < date_trunc('month',CURRENT_DATE)''')[0]['n']
            counts = query(f'''WITH sites AS ({sql})
                SELECT count(DISTINCT site_uuid) sites,
                    count(DISTINCT site_uuid) FILTER(WHERE report_count>0) reporters,
                    count(DISTINCT site_uuid) FILTER(WHERE report_count=0) silent,
                    sum(report_count) reports
                FROM sites WHERE reported_month=date_trunc('month',CURRENT_DATE)-interval '1 month' ''')[0]
            assert counts['sites'] == expected, (counts, expected)
            assert counts['reporters'] + counts['silent'] == counts['sites'], counts
            assert 0 <= counts['reporters'] <= counts['sites'], counts
            # La somme par région doit retrouver le national ; les taux ne s'additionnent pas.
            region_counts = query(f'''WITH sites AS ({sql})
                SELECT region,count(DISTINCT site_uuid) sites,
                    count(DISTINCT site_uuid) FILTER(WHERE report_count>0) reporters
                FROM sites WHERE reported_month=date_trunc('month',CURRENT_DATE)-interval '1 month'
                GROUP BY region''')
            assert sum(r['sites'] for r in region_counts) == counts['sites']
            assert sum(r['reporters'] for r in region_counts) == counts['reporters']
            for dimension, identifier in [('district', 'district_uuid'), ('cscom', 'health_area_uuid')]:
                assert not query(f'''WITH sites AS ({sql})
                    SELECT {dimension} FROM sites GROUP BY {dimension}
                    HAVING count(DISTINCT {identifier}) > 1'''), f'Homonymes fusionnés : {dimension}'
                rollup = query(f'''WITH sites AS ({sql}), territories AS (
                    SELECT {dimension}, count(DISTINCT site_uuid) n FROM sites
                    WHERE reported_month=date_trunc('month',CURRENT_DATE)-interval '1 month'
                    GROUP BY {dimension}) SELECT sum(n) n FROM territories''')[0]['n']
                assert rollup == expected, (dimension, rollup, expected)
            # Test indépendant des volumes de la source : ne réutilise pas la logique de jointure.
            raw = query('''SELECT count(*) n FROM form_metadata
                WHERE reported >= date_trunc('month',CURRENT_DATE)-interval '1 month'
                AND reported < date_trunc('month',CURRENT_DATE)''')[0]['n']
            classified = query('''SELECT sum(report_count) n FROM mv_asc_v2_report_monthly
                WHERE reported_month=date_trunc('month',CURRENT_DATE)-interval '1 month' ''')[0]['n']
            assert raw == classified, (raw, classified)
            quality = query('''SELECT quality,sum(report_count) reports
                FROM mv_asc_v2_report_monthly
                WHERE reported_month=date_trunc('month',CURRENT_DATE)-interval '1 month' GROUP BY quality''')
            # Contrôles des formes historiques de contact : parent-site et contact-site.
            expected_reports = query('''SELECT count(*) n FROM form_metadata f
                LEFT JOIN mv_chw_site_hierarchy_reporting p ON p.chw_site_uuid=f.chw_area
                LEFT JOIN mv_chw_site_hierarchy_reporting s ON s.chw_site_uuid=f.chw
                WHERE f.reported >= date_trunc('month',CURRENT_DATE)-interval '1 month'
                AND f.reported < date_trunc('month',CURRENT_DATE)
                AND coalesce(p.chw_site_uuid,s.chw_site_uuid) IS NOT NULL
                AND (p.chw_site_uuid IS NULL OR s.chw_site_uuid IS NULL OR p.chw_site_uuid=s.chw_site_uuid)''')[0]['n']
            attributed = sum(q['reports'] for q in quality if q['quality']=='attribue')
            assert expected_reports == attributed, (expected_reports, attributed)
            # Le décompte sur plusieurs mois reste distinct et sa partition ne double-compte pas.
            multi = query(f'''WITH sites AS ({sql})
                SELECT count(DISTINCT site_uuid) sites,
                  count(DISTINCT CASE WHEN report_count>0 THEN site_uuid END) reporters
                FROM sites WHERE reported_month >= date_trunc('month',CURRENT_DATE)-interval '3 months'
                AND reported_month < date_trunc('month',CURRENT_DATE)''')[0]
            assert 0 <= multi['reporters'] <= multi['sites']
            print(json.dumps(dict(status='OK', last_complete_month=counts,
                classified_reports=raw, quality=quality, three_months=multi,
                regions=region_counts, query_seconds_max=round(max(durations), 3)),
                default=str, ensure_ascii=False))
