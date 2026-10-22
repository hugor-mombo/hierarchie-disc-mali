-- Source distincte : ne modifie aucune vue des tableaux ASC / SD existants.
WITH attributed AS (
  SELECT f.reported,
         coalesce(p.chw_site_uuid, s.chw_site_uuid) AS site,
         CASE
           WHEN f.reported > CURRENT_TIMESTAMP THEN 'date_future'
           WHEN (p.chw_site_uuid IS NOT NULL AND s.chw_site_uuid IS NOT NULL
                 AND p.chw_site_uuid <> s.chw_site_uuid)
             THEN 'attribution_ambigue'
           WHEN coalesce(p.chw_site_uuid, s.chw_site_uuid) IS NULL
             THEN 'hors_perimetre_ou_non_attribue'
           ELSE 'attribue'
         END AS quality
  FROM public.form_metadata f
  LEFT JOIN public.mv_chw_site_hierarchy_reporting p ON p.chw_site_uuid = f.chw_area
  LEFT JOIN public.mv_chw_site_hierarchy_reporting s ON s.chw_site_uuid = f.chw
  WHERE f.reported >= date_trunc('month', CURRENT_DATE) - interval '13 months'
)
SELECT date_trunc('month', reported)::date AS reported_month,
       coalesce(site, '__sans_site__') AS site_key,
       quality,
       count(*)::bigint AS report_count,
       max(reported) AS last_reported,
       CURRENT_TIMESTAMP AS refreshed_at
FROM attributed
GROUP BY 1, 2, 3
