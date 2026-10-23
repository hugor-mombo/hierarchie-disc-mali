WITH raw AS MATERIALIZED (
 SELECT uuid,_id AS site_uuid,reported AS reported_at,date_trunc('month',reported)::date AS reported_month,
 nullif(replace(btrim(final_score),',','.'),'') AS score_text
 FROM public.formview_visit_chw_site WHERE reported>='2019-01-01' AND reported<date_trunc('month',CURRENT_DATE)
), ranked AS (
 SELECT *,row_number() OVER(PARTITION BY site_uuid,reported_month ORDER BY reported_at DESC,uuid DESC) AS rank,
 count(*) OVER(PARTITION BY site_uuid,reported_month,reported_at) AS ties
 FROM raw WHERE site_uuid IS NOT NULL
), parsed AS (
 SELECT *,CASE WHEN score_text ~ '^[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)$' THEN score_text::numeric END AS score FROM ranked WHERE rank=1
)
 SELECT p.region_uuid,p.region,p.district_uuid,p.district AS district_name,
 concat_ws(' · ',p.district,p.region) AS district,p.health_area_uuid,p.health_area AS cscom_name,
 concat_ws(' · ',p.health_area,p.district,p.region) AS cscom,
 p.supervisor_area_uuid,p.supervisor_area AS zone_name,
 concat_ws(' · ',p.supervisor_area,p.health_area,p.district,p.region) AS zone,
 p.chw_site_uuid AS site_uuid,p.chw_site AS site_name,r.reported_month,CURRENT_TIMESTAMP AS calculated_at,
 CASE WHEN ties=1 AND score BETWEEN 0 AND 100 THEN score ELSE 0 END AS score_total,
 CASE WHEN ties=1 AND score BETWEEN 0 AND 100 THEN 1 ELSE 0 END::bigint AS assessed,
 CASE WHEN ties=1 AND score>=80 AND score<=100 THEN 1 ELSE 0 END::bigint AS acceptable,
 1::bigint AS visited,
 CASE WHEN ties=1 AND score BETWEEN 0 AND 100 THEN 0 ELSE 1 END::bigint AS unusable
 FROM parsed r JOIN public.mv_superset_sd_portfolio p ON p.chw_site_uuid=r.site_uuid
