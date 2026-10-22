-- Grain : compte × type × mois d'échéance × qualité. Aucun nom de patient.
-- Le catalogue JSON est inséré par refresh_tasks.py, à partir du fichier versionné.
WITH catalog AS (
 SELECT key AS task_code,value->>'label' AS task_label,value->>'theme' AS theme
 FROM jsonb_each(CAST(:catalog AS jsonb))
), classified AS (
 SELECT coalesce(t."user",'') AS username,coalesce(t.title,'') AS task_code,
        date_trunc('month',t.duedate)::date AS due_month,t.task_state,
        t.duedate,t.startdate,t.enddate,t.date_task_authored,
        CASE WHEN t.task_uuid IS NULL THEN 'Identifiant de tâche manquant'
             WHEN t.duedate IS NULL THEN 'Échéance manquante'
             WHEN t.startdate IS NULL OR t.enddate IS NULL OR t.startdate>t.duedate
                  OR t.duedate>t.enddate THEN 'Fenêtre invalide ou incomplète'
             WHEN t.date_task_authored IS NULL THEN 'Date de création manquante'
             WHEN t.date_task_authored>CURRENT_TIMESTAMP THEN 'Création datée dans le futur'
             WHEN t.task_state IS NULL OR t.task_state NOT IN ('Completed','Failed','Ready','Draft','Cancelled')
               THEN 'État inconnu'
             ELSE 'Valide' END AS record_quality
 FROM public.useview_task t
 WHERE t.duedate>=date_trunc('month',CURRENT_DATE)-interval '12 months' OR t.duedate IS NULL
), grouped AS (
 SELECT username,task_code,due_month,record_quality,
 count(*)::bigint AS observed,
 count(*) FILTER(WHERE task_state='Completed')::bigint AS completed_all,
 count(*) FILTER(WHERE task_state='Failed')::bigint AS failed_all,
 count(*) FILTER(WHERE task_state='Ready')::bigint AS ready_all,
 count(*) FILTER(WHERE task_state='Draft')::bigint AS draft_all,
 count(*) FILTER(WHERE task_state='Cancelled')::bigint AS cancelled_all,
 count(*) FILTER(WHERE task_state IS NULL OR task_state NOT IN ('Completed','Failed','Ready','Draft','Cancelled'))::bigint AS other_all,
 count(*) FILTER(WHERE record_quality='Valide' AND duedate<CURRENT_DATE AND task_state IN ('Completed','Failed','Ready','Draft'))::bigint AS due_total,
 count(*) FILTER(WHERE record_quality='Valide' AND duedate<CURRENT_DATE AND task_state='Completed')::bigint AS due_completed,
 count(*) FILTER(WHERE record_quality='Valide' AND duedate<CURRENT_DATE AND task_state='Failed')::bigint AS due_failed,
 count(*) FILTER(WHERE record_quality='Valide' AND duedate<CURRENT_DATE AND task_state IN ('Ready','Draft'))::bigint AS due_open,
 count(*) FILTER(WHERE record_quality='Valide' AND duedate<CURRENT_DATE AND task_state='Ready' AND enddate>=CURRENT_DATE)::bigint AS open_window,
 count(*) FILTER(WHERE record_quality='Valide' AND duedate<CURRENT_DATE AND task_state='Draft' AND enddate>=CURRENT_DATE)::bigint AS open_draft,
 count(*) FILTER(WHERE record_quality='Valide' AND duedate<CURRENT_DATE AND task_state IN ('Ready','Draft') AND enddate<CURRENT_DATE)::bigint AS open_stale,
 count(*) FILTER(WHERE record_quality='Valide' AND duedate>=CURRENT_DATE AND task_state IN ('Ready','Draft'))::bigint AS upcoming,
 min(duedate) FILTER(WHERE record_quality='Valide' AND duedate<CURRENT_DATE AND task_state IN ('Ready','Draft')) AS oldest_open_due,
 min(duedate) AS first_due,max(duedate) AS last_due,
 max(date_task_authored) AS last_authored
 FROM classified GROUP BY username,task_code,due_month,record_quality
)
SELECT g.*,coalesce(c.task_label,'Type de tâche non reconnu') AS task_label,
 coalesce(c.theme,'Type non classé') AS theme,(c.task_code IS NOT NULL) AS catalogued,
 CURRENT_DATE AS reference_date,CURRENT_TIMESTAMP AS refreshed_at
FROM grouped g LEFT JOIN catalog c USING(task_code)
