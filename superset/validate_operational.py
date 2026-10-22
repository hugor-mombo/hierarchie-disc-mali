"""Contrôles des listes, sans sortie de donnée individuelle."""
import json
from pathlib import Path
from time import perf_counter
from sqlalchemy import text
from superset.app import create_app

ROOT=Path(__file__).resolve().parent
app=create_app()
with app.app_context():
    from superset import db
    from superset.models.core import Database
    database=db.session.query(Database).filter_by(id=1).one()
    with database.get_sqla_engine() as engine:
        with engine.connect() as c:
            c.execute(text('SET TRANSACTION READ ONLY'))
            c.execute(text("SET LOCAL statement_timeout='30s'"))
            durations=[]

            def query(sql):
                started=perf_counter()
                rows=[dict(r._mapping) for r in c.execute(text(sql))]
                durations.append(perf_counter()-started)
                return rows

            for table,key in [('mv_asc_ops_geography','site_uuid'),
                              ('mv_asc_ops_accounts','username'),
                              ('mv_asc_ops_children_v2','patient_uuid')]:
                assert not query(f'SELECT {key} FROM {table} GROUP BY {key} HAVING count(*)>1 OR {key} IS NULL'),table
            geo=query('SELECT count(*) n FROM mv_asc_ops_geography')[0]['n']
            assert geo==query('SELECT count(*) n FROM mv_chw_site_hierarchy_reporting')[0]['n']
            assert not query('''SELECT 1 FROM mv_asc_ops_accounts
                WHERE last_personal_report>refreshed_at OR last_site_report>refreshed_at
                OR days_without_report<0 LIMIT 1''')
            # Dernier rapport personnel : contrôle direct de plusieurs comptes,
            # sans lire leurs noms ni imprimer leurs identifiants.
            assert not query('''WITH sample AS MATERIALIZED (
                SELECT contact_uuid,last_personal_report,refreshed_at FROM mv_asc_ops_accounts
                ORDER BY username LIMIT 50), expected AS MATERIALIZED (
                SELECT f.chw,max(f.reported) AS last_report FROM form_metadata f
                JOIN sample s ON s.contact_uuid=f.chw AND f.reported<=s.refreshed_at GROUP BY f.chw)
                SELECT 1 FROM sample a LEFT JOIN expected e ON e.chw=a.contact_uuid
                WHERE a.last_personal_report IS DISTINCT FROM e.last_report LIMIT 1''')
            accounts=(ROOT/'sql/ops_accounts.sql').read_text()
            asc_counts=query(f'''WITH a AS ({accounts}) SELECT threshold_days,action_status,
                count(DISTINCT username) n FROM a GROUP BY 1,2 ORDER BY 1,2''')
            assert not query(f'''WITH a AS ({accounts}) SELECT 1 FROM a
                WHERE last_personal_report IS NOT NULL AND days_without_report<threshold_days LIMIT 1''')
            assert not query(f'''WITH a AS ({accounts}) SELECT username,threshold_days FROM a
                GROUP BY 1,2 HAVING count(*)>1''')
            children=(ROOT/'sql/ops_children.sql').read_text()
            status='Penta 1 non reçu déclaré — à confirmer'
            assert not query(f'''SELECT 1 FROM mv_asc_ops_children_v2 WHERE followup_status='{status}'
                AND (positive_recorded OR deceased_recorded OR NOT contact_exists
                     OR age_months NOT BETWEEN 12 AND 59 OR age_months IS NULL
                     OR latest_penta1 IS DISTINCT FROM 'no' OR site_uuid IS NULL) LIMIT 1''')
            assert not query('SELECT 1 FROM mv_asc_ops_children_v2 WHERE last_observation>refreshed_at LIMIT 1')
            assert not query(f'''WITH children AS ({children})
                SELECT 1 FROM children WHERE positive_recorded OR deceased_recorded LIMIT 1''')
            # Vérification indépendante de la recherche du libellé Penta 1 dans le cumul.
            assert not query(f'''WITH children AS ({children})
                SELECT 1 FROM children c JOIN mv_children_vaccination_history h USING(patient_uuid)
                WHERE c.followup_status='{status}' AND h.report_month<date_trunc('month',c.reference_date)
                AND 'Penta 1'=ANY(string_to_array(h.antigens_status_until_month,', ')) LIMIT 1''')
            child_counts=query(f'''WITH children AS ({children}) SELECT followup_status,count(*) n,
                count(DISTINCT patient_uuid) ids FROM children GROUP BY 1 ORDER BY 1''')
            assert all(x['n']==x['ids'] for x in child_counts)
            assert sum(x['n'] for x in child_counts)<=100000, 'Prévoir des exports par lots avant publication'
            assert max((x['n'] for x in asc_counts),default=0)<=100000
            # La somme des régions retrouve les enfants de la sélection, y compris les localisations inconnues.
            national=query(f"SELECT count(*) n FROM mv_asc_ops_children_v2 WHERE followup_status='{status}'")[0]['n']
            regional=query(f"SELECT region,count(*) n FROM mv_asc_ops_children_v2 WHERE followup_status='{status}' GROUP BY region")
            assert national>0 and sum(x['n'] for x in regional)==national
            print(json.dumps(dict(status='OK',geographic_sites=geo,accounts=asc_counts,
                children=child_counts,default_children=national,
                query_seconds_max=round(max(durations),3)),ensure_ascii=False,default=str))
