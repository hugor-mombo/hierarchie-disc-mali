"""Vérifier les dénominateurs et les cas limites sans sortie de données individuelles."""
import argparse
import json
from pathlib import Path
from time import perf_counter
from sqlalchemy import text
from superset.app import create_app
ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--source',action='store_true')
args=parser.parse_args()
app=create_app()
with app.app_context():
 from superset import db
 from superset.models.core import Database
 source=db.session.query(Database).filter_by(id=1).one()
 catalog=json.dumps(json.loads((ROOT/'task_catalog.json').read_text()),ensure_ascii=False)
 with source.get_sqla_engine() as e:
  with e.connect() as c:
   c.execute(text('SET TRANSACTION READ ONLY'));c.execute(text("SET LOCAL statement_timeout='120s'"))
   started=perf_counter()
   def query(sql,params=None):return [dict(r._mapping) for r in c.execute(text(sql),params or {})]
   assert not query('''SELECT 1 FROM mv_asc_tasks_rollup WHERE due_total<>due_completed+due_failed+due_open
    OR due_open<>open_window+open_draft+open_stale
    OR observed<>completed_all+failed_all+ready_all+draft_all+cancelled_all+other_all
    OR due_completed>due_total OR due_open<0 OR due_total<0 LIMIT 1''')
   assert not query('''SELECT 1 FROM mv_asc_tasks_rollup WHERE record_quality<>'Valide' AND
    (due_total<>0 OR upcoming<>0 OR due_open<>0) LIMIT 1''')
   assert not query('''SELECT 1 FROM mv_asc_tasks_rollup WHERE due_month>=date_trunc('month',reference_date)+interval '1 month'
    AND due_total>0 LIMIT 1''')
   assert not query('''SELECT 1 FROM mv_asc_tasks_rollup GROUP BY username,task_code,due_month,record_quality
    HAVING count(*)>1 LIMIT 1''')
   facts=(ROOT/'sql/tasks_monthly.sql').read_text()
   quality=(ROOT/'sql/tasks_quality.sql').read_text()
   # Toute tâche retenue se retrouve soit dans le périmètre et sa qualité,
   # soit parmi les tâches hors périmètre ; aucune multiplication des comptes.
   raw=query('SELECT sum(observed) n FROM mv_asc_tasks_rollup')[0]['n']
   quality_total=query('SELECT sum(observed) n FROM ('+quality+')q')[0]['n']
   assert raw==quality_total,(raw,quality_total)
   exports=query('SELECT count(*) n FROM (SELECT username,task_code FROM ('+facts+
    ')q GROUP BY 1,2 HAVING sum(due_open)>0)x')[0]['n']
   assert exports<=100000, 'Volume supérieur à la limite des exports complets'
   # Le taux national est reconstruit par les volumes régionaux, sans moyenne de taux.
   totals=query("WITH f AS ("+facts+") SELECT sum(due_total) due,sum(due_completed) done,sum(due_failed) failed,sum(due_open) open FROM f WHERE due_month=date_trunc('month',CURRENT_DATE)-interval '1 month'")[0]
   regions=query("WITH f AS ("+facts+") SELECT region,sum(due_total) due,sum(due_completed) done FROM f WHERE due_month=date_trunc('month',CURRENT_DATE)-interval '1 month' GROUP BY 1")
   assert totals['due'] and sum(r['due'] for r in regions)==totals['due']
   assert sum(r['done'] for r in regions)==totals['done']
   if args.source:
    snapshot=query('SELECT max(refreshed_at) cutoff,max(reference_date) ref FROM mv_asc_tasks_rollup')[0]
    # Une borne issue d'une sous-requête provoquait un parcours d'index massif.
    # Ici la comparaison indépendante parcourt la source une seule fois.
    c.execute(text("SET LOCAL statement_timeout='180s'"))
    c.execute(text('SET LOCAL enable_indexscan=off'))
    c.execute(text('SET LOCAL enable_bitmapscan=off'))
    direct=query('''SELECT count(*) AS due,
     count(*) FILTER(WHERE t.task_state='Completed') AS done,
     count(*) FILTER(WHERE t.task_state='Failed') AS failed,
     count(*) FILTER(WHERE t.task_state IN ('Ready','Draft')) AS open
     FROM useview_task t JOIN mv_asc_ops_accounts a ON a.username=t."user"
     WHERE t.duedate>=date_trunc('month',CURRENT_DATE)-interval '1 month'
      AND t.duedate<date_trunc('month',CURRENT_DATE) AND t.duedate<:ref
      AND t.task_uuid IS NOT NULL AND t.startdate IS NOT NULL AND t.enddate IS NOT NULL
      AND t.startdate<=t.duedate AND t.duedate<=t.enddate
      AND t.date_task_authored IS NOT NULL AND t.date_task_authored<=:cutoff
      AND t.task_state IN ('Completed','Failed','Ready','Draft')''',snapshot)[0]
    assert direct==totals,('Écart avec la source',direct,totals)
   # Cas synthétiques : aujourd'hui n'est pas échu ; les annulations et dates invalides
   # restent hors du taux ; les trois types d'ouverture partitionnent les retards.
   cases=[('completed','Completed',-2,2,0),('failed','Failed',-2,-1,0),
    ('ready','Ready',-2,2,0),('stale','Ready',-2,-1,0),('draft','Draft',-2,2,0),
    ('future','Draft',2,3,0),('today','Ready',0,2,0),('cancelled','Cancelled',-2,2,0),
    ('unknown','NewState',-2,2,0),('future_authored','Completed',-2,2,1)]
   values=[]
   for name,state,due,end,future in cases:
    values.append(f"('{name}','test','{name}','{state}',CURRENT_DATE-3,CURRENT_DATE+({due}),CURRENT_DATE+({end}),CURRENT_TIMESTAMP+interval '{future} days')")
   values.append("('bad_window','test','bad_window','Ready',CURRENT_DATE+2,CURRENT_DATE-1,CURRENT_DATE+3,CURRENT_TIMESTAMP)")
   values.append("('no_due','test','no_due','Ready',CURRENT_DATE-3,NULL::date,CURRENT_DATE+3,CURRENT_TIMESTAMP)")
   fixture='(VALUES '+','.join(values)+') AS t(task_uuid,"user",title,task_state,startdate,duedate,enddate,date_task_authored)'
   sql=(ROOT/'sql/tasks_rollup.sql').read_text().replace('public.useview_task t',fixture)
   result={r['task_code']:r for r in query(sql,{'catalog':catalog})}
   assert len(result)==len(values)
   for name in ['completed','failed','ready','stale','draft']:assert result[name]['due_total']==1,name
   assert result['completed']['due_completed']==1
   assert result['failed']['due_failed']==1
   assert result['ready']['open_window']==1
   assert result['stale']['open_stale']==1
   assert result['draft']['open_draft']==1
   for name in ['future','today','cancelled','unknown','future_authored','bad_window','no_due']:
    assert result[name]['due_total']==0,name
   assert result['today']['upcoming']==1 and result['cancelled']['cancelled_all']==1
   assert result['no_due']['record_quality']=='Échéance manquante'
   assert c.execute(text('SELECT 1.0/NULLIF(0,0)')).scalar() is None
   print(json.dumps({'status':'OK','tasks_retained':raw,'export_groups_max':exports,
    'previous_month':totals,'direct_source_checked':args.source,
    'synthetic_cases':len(result),'seconds':round(perf_counter()-started,2)},default=str),flush=True)
