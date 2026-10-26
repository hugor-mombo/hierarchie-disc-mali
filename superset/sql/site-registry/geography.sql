WITH areas AS (
 SELECT DISTINCT region_uuid,district_uuid,health_area_uuid,region,district_name,cscom_name
 FROM public.mv_disc_site_registry_v1
), districts AS (
 SELECT DISTINCT region_uuid,district_uuid,region,district_name FROM areas
), district_labels AS (
 SELECT *,coalesce(district_name,'District non renseigné') || ' · ' || region ||
 CASE WHEN count(*) OVER(PARTITION BY region_uuid,district_name)>1
 THEN ' ['||coalesce(left(district_uuid,8),'sans ID')||']' ELSE '' END AS district
 FROM districts
), labels AS (
 SELECT a.*,d.district,
 coalesce(a.cscom_name,'CSCOM non renseigné')||' · '||d.district ||
 CASE WHEN count(*) OVER(PARTITION BY a.region_uuid,a.district_uuid,a.cscom_name)>1
 THEN ' ['||coalesce(left(a.health_area_uuid,8),'sans ID')||']' ELSE '' END AS cscom
 FROM areas a JOIN district_labels d
 ON d.region_uuid IS NOT DISTINCT FROM a.region_uuid
 AND d.district_uuid IS NOT DISTINCT FROM a.district_uuid
)
SELECT r.*,l.district,l.cscom,concat_ws(' · ',r.zone_name,l.cscom) AS zone
FROM public.mv_disc_site_registry_v1 r
JOIN labels l ON l.region_uuid IS NOT DISTINCT FROM r.region_uuid
 AND l.district_uuid IS NOT DISTINCT FROM r.district_uuid
 AND l.health_area_uuid IS NOT DISTINCT FROM r.health_area_uuid
