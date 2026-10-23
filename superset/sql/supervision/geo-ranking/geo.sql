WITH raw AS MATERIALIZED (
 SELECT uuid,_id AS site_uuid,reported,
 nullif(btrim(coalesce(nullif(geopoint,''),CASE WHEN location LIKE '{%' THEN location::jsonb->>'geopoint' END)),'') AS point
 FROM public.formview_location_gps WHERE reported<=CURRENT_TIMESTAMP
), parts AS (
 SELECT *,regexp_split_to_array(point,'[[:space:]]+') AS parts FROM raw
), parsed AS (
 SELECT *,CASE WHEN parts[1] ~ '^[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)$' THEN parts[1]::numeric END AS lat,CASE WHEN parts[2] ~ '^[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)$' THEN parts[2]::numeric END AS lon FROM parts
), checked AS (
 SELECT *,coalesce(lat BETWEEN -90 AND 90 AND lon BETWEEN -180 AND 180 AND NOT(lat=0 AND lon=0),FALSE) AS valid
 FROM parsed
), ranked AS (
 SELECT *,count(*) OVER(PARTITION BY site_uuid,reported) AS ties,
 row_number() OVER(PARTITION BY site_uuid ORDER BY reported DESC,uuid DESC) AS rank,
 count(*) OVER(PARTITION BY site_uuid) AS reports,
 min(reported) OVER(PARTITION BY site_uuid) AS first_report,
 max(reported) FILTER(WHERE valid) OVER(PARTITION BY site_uuid) AS last_valid_report
 FROM checked
)
SELECT p.region_uuid,p.region,p.district_uuid,p.district AS district_name,
 concat_ws(' · ',p.district,p.region) AS district,p.health_area_uuid,p.health_area AS cscom_name,
 concat_ws(' · ',p.health_area,p.district,p.region) AS cscom,
 p.supervisor_area_uuid,p.supervisor_area AS zone_name,
 concat_ws(' · ',p.supervisor_area,p.health_area,p.district,p.region) AS zone,
 p.chw_site_uuid AS site_uuid,p.chw_site AS site_name,CURRENT_DATE AS reported_month,CURRENT_TIMESTAMP AS calculated_at,
 coalesce(r.reports,0)::bigint AS gps_reports,r.first_report,r.reported AS last_report,r.last_valid_report,
 CASE WHEN r.uuid IS NULL THEN 'Sans relevé GPS'
 WHEN r.ties>1 THEN 'Dernier relevé ambigu'
 WHEN NOT r.valid THEN 'Coordonnées absentes ou invalides'
 ELSE 'Coordonnées exploitables' END AS gps_status,
 CASE WHEN r.ties=1 AND r.valid THEN 1 ELSE 0 END::bigint AS gps_valid,
 CASE WHEN r.ties=1 AND r.valid AND NOT(r.lat BETWEEN 10 AND 26 AND r.lon BETWEEN -13 AND 5) THEN 1 ELSE 0 END::bigint AS outside_envelope,
 CASE WHEN r.ties=1 AND r.valid AND r.reported<CURRENT_DATE-interval '12 months' THEN 1 ELSE 0 END::bigint AS older_year
 FROM public.mv_superset_sd_portfolio p LEFT JOIN ranked r ON r.site_uuid=p.chw_site_uuid AND r.rank=1
