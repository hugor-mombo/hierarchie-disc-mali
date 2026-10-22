-- Dimension géographique, commune aux deux listes opérationnelles.
WITH areas AS (
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
)
SELECT h.chw_site_uuid AS site_uuid, h.chw_site AS site_name,
       h.chw_site || ' [' || left(h.chw_site_uuid,8) || ']' AS site,
       coalesce(h.region,'Région non renseignée') AS region,
       l.district_label AS district, l.cscom,
       h.region_uuid, h.district_uuid, h.health_area_uuid,
       h.district AS district_name,h.health_area AS cscom_name,
       h.supervisor_area AS supervision_area,
       h.reported_date AS site_created_date
FROM public.mv_chw_site_hierarchy_reporting h
JOIN labels l ON coalesce(l.health_area_uuid,'__missing__')=coalesce(h.health_area_uuid,'__missing__')
 AND coalesce(l.district_uuid,'__missing__')=coalesce(h.district_uuid,'__missing__')
 AND coalesce(l.region_uuid,'__missing__')=coalesce(h.region_uuid,'__missing__')
