-- Liste de suivi : les preuves positives et décès connus ne sont pas exportés.
SELECT *,CASE WHEN observation_age_days<30 THEN 'Moins de 30 jours'
              WHEN observation_age_days<90 THEN '30–89 jours'
              ELSE '90 jours ou plus' END AS observation_recency
FROM public.mv_asc_ops_children_v2
WHERE NOT positive_recorded AND NOT coalesce(deceased_recorded,false)
