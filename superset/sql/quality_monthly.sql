-- Qualité nationale : ne peut pas être attribuée à une géographie de manière sûre.
SELECT reported_month,
       CASE quality
         WHEN 'attribue' THEN 'Rapports attribués au périmètre'
         WHEN 'date_future' THEN 'Date déclarée dans le futur — exclus'
         WHEN 'attribution_ambigue' THEN 'Attribution contradictoire — exclus'
         ELSE 'Hors périmètre ou sans attribution sûre'
       END AS quality,
       sum(report_count)::bigint AS report_count,
       max(last_reported) AS last_reported, max(refreshed_at) AS refreshed_at
FROM public.mv_asc_v2_report_monthly
GROUP BY 1, 2
