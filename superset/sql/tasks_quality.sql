SELECT t.due_month,a.region_uuid,a.region,a.district,a.cscom,a.site,
 t.theme,t.task_label,t.task_code,
 CASE WHEN a.username IS NULL THEN 'Hors périmètre des comptes ASC courants'
      ELSE t.record_quality END AS quality,
 sum(t.observed)::bigint AS observed,max(t.refreshed_at) AS refreshed_at
FROM public.mv_asc_tasks_rollup t
LEFT JOIN public.mv_asc_ops_accounts a USING(username)
GROUP BY t.due_month,a.region_uuid,a.region,a.district,a.cscom,a.site,
 t.theme,t.task_label,t.task_code,
 CASE WHEN a.username IS NULL THEN 'Hors périmètre des comptes ASC courants' ELSE t.record_quality END
