-- Grain : un site UUID par mois. Cohorte et géographie du relevé actuel.
WITH periods AS MATERIALIZED (
  SELECT generate_series(
    date_trunc('month', CURRENT_DATE) - interval '13 months',
    date_trunc('month', CURRENT_DATE), interval '1 month')::date AS reported_month
), reports AS MATERIALIZED (
  SELECT reported_month, site_key, report_count, last_reported
  FROM public.mv_asc_v2_report_monthly
  WHERE quality = 'attribue'
)
SELECT p.reported_month, g.region AS region,
       g.district AS district,
       g.cscom, g.region_uuid, g.district_uuid, g.health_area_uuid,
       h.chw_site_uuid AS site_uuid, h.chw_site AS site,
       h.reported_date AS site_created_date,
       coalesce(r.report_count, 0)::bigint AS report_count,
       r.last_reported,
       (SELECT max(refreshed_at) FROM public.mv_asc_v2_report_monthly) AS refreshed_at
FROM public.mv_chw_site_hierarchy_reporting h
CROSS JOIN periods p
JOIN public.v_disc_site_registry_labels_v1 g ON g.site_uuid=h.chw_site_uuid
LEFT JOIN reports r ON r.site_key = h.chw_site_uuid AND r.reported_month = p.reported_month
WHERE h.reported_date < p.reported_month + interval '1 month'
  AND h.reported_date <= CURRENT_DATE
