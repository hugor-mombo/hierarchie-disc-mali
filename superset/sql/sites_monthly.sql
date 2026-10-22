-- Grain : un site UUID par mois. Cohorte et géographie du relevé actuel.
WITH periods AS MATERIALIZED (
  SELECT generate_series(
    date_trunc('month', CURRENT_DATE) - interval '13 months',
    date_trunc('month', CURRENT_DATE), interval '1 month')::date AS reported_month
), areas AS (
  SELECT DISTINCT region_uuid, district_uuid, health_area_uuid,
         region, district, health_area
  FROM public.mv_chw_site_hierarchy_reporting
), districts AS (
  SELECT DISTINCT region_uuid, district_uuid, region, district FROM areas
), district_labels AS (
  SELECT *, coalesce(district, 'District non renseigné') || ' · ' ||
    coalesce(region, 'Région non renseignée') ||
    CASE WHEN count(*) OVER (PARTITION BY region_uuid, district) > 1
         THEN ' [' || coalesce(left(district_uuid, 8), 'sans ID') || ']' ELSE '' END AS district_label
  FROM districts
), labels AS MATERIALIZED (
  SELECT a.*, d.district_label,
    coalesce(a.health_area, 'CSCOM non renseigné') || ' · ' || d.district_label ||
    CASE WHEN count(*) OVER (PARTITION BY a.region_uuid, a.district_uuid, a.health_area) > 1
         THEN ' [' || coalesce(left(a.health_area_uuid, 8), 'sans ID') || ']' ELSE '' END AS cscom
  FROM areas a
  JOIN district_labels d ON coalesce(d.district_uuid, '__missing__') = coalesce(a.district_uuid, '__missing__')
    AND coalesce(d.region_uuid, '__missing__') = coalesce(a.region_uuid, '__missing__')
), reports AS MATERIALIZED (
  SELECT reported_month, site_key, report_count, last_reported
  FROM public.mv_asc_v2_report_monthly
  WHERE quality = 'attribue'
)
SELECT p.reported_month, coalesce(h.region, 'Région non renseignée') AS region,
       l.district_label AS district,
       l.cscom, h.region_uuid, h.district_uuid, h.health_area_uuid,
       h.chw_site_uuid AS site_uuid, h.chw_site AS site,
       h.reported_date AS site_created_date,
       coalesce(r.report_count, 0)::bigint AS report_count,
       r.last_reported,
       (SELECT max(refreshed_at) FROM public.mv_asc_v2_report_monthly) AS refreshed_at
FROM public.mv_chw_site_hierarchy_reporting h
CROSS JOIN periods p
JOIN labels l ON coalesce(l.health_area_uuid, '__missing__') = coalesce(h.health_area_uuid, '__missing__')
  AND coalesce(l.district_uuid, '__missing__') = coalesce(h.district_uuid, '__missing__')
  AND coalesce(l.region_uuid, '__missing__') = coalesce(h.region_uuid, '__missing__')
LEFT JOIN reports r ON r.site_key = h.chw_site_uuid AND r.reported_month = p.reported_month
WHERE h.reported_date < p.reported_month + interval '1 month'
  AND h.reported_date <= CURRENT_DATE
