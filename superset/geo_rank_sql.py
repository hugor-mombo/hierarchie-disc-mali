"""DISC site GPS quality and explicitly qualified operational rankings."""
from pathlib import Path
from uuid import UUID,uuid5
ROOT=Path(__file__).resolve().parent
NS=UUID('31544323-3708-4849-959c-20ff1f502b90')
def uid(key):return uuid5(NS,key)
def number(field):return "CASE WHEN "+field+" ~ '^[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)$' THEN "+field+"::numeric END"
GEO="""p.region_uuid,p.region,p.district_uuid,p.district AS district_name,
 concat_ws(' · ',p.district,p.region) AS district,p.health_area_uuid,p.health_area AS cscom_name,
 concat_ws(' · ',p.health_area,p.district,p.region) AS cscom,
 p.supervisor_area_uuid,p.supervisor_area AS zone_name,
 concat_ws(' · ',p.supervisor_area,p.health_area,p.district,p.region) AS zone,
 p.chw_site_uuid AS site_uuid,p.chw_site AS site_name"""
GPS="""WITH raw AS MATERIALIZED (
 SELECT uuid,_id AS site_uuid,reported,
 nullif(btrim(coalesce(nullif(geopoint,''),CASE WHEN location LIKE '{%' THEN location::jsonb->>'geopoint' END)),'') AS point
 FROM public.formview_location_gps WHERE reported<=CURRENT_TIMESTAMP
), parts AS (
 SELECT *,regexp_split_to_array(point,'[[:space:]]+') AS parts FROM raw
), parsed AS (
 SELECT *,__LAT__ AS lat,__LON__ AS lon FROM parts
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
SELECT __GEO__,CURRENT_DATE AS reported_month,CURRENT_TIMESTAMP AS calculated_at,
 coalesce(r.reports,0)::bigint AS gps_reports,r.first_report,r.reported AS last_report,r.last_valid_report,
 CASE WHEN r.uuid IS NULL THEN 'Sans relevé GPS'
 WHEN r.ties>1 THEN 'Dernier relevé ambigu'
 WHEN NOT r.valid THEN 'Coordonnées absentes ou invalides'
 ELSE 'Coordonnées exploitables' END AS gps_status,
 CASE WHEN r.ties=1 AND r.valid THEN 1 ELSE 0 END::bigint AS gps_valid,
 CASE WHEN r.ties=1 AND r.valid AND NOT(r.lat BETWEEN 10 AND 26 AND r.lon BETWEEN -13 AND 5) THEN 1 ELSE 0 END::bigint AS outside_envelope,
 CASE WHEN r.ties=1 AND r.valid AND r.reported<CURRENT_DATE-interval '12 months' THEN 1 ELSE 0 END::bigint AS older_year
 FROM public.mv_superset_sd_portfolio p LEFT JOIN ranked r ON r.site_uuid=p.chw_site_uuid AND r.rank=1""".replace('__LAT__',number('parts[1]')).replace('__LON__',number('parts[2]')).replace('__GEO__',GEO)
ASC="""WITH raw AS MATERIALIZED (
 SELECT uuid,_id AS site_uuid,reported AS reported_at,date_trunc('month',reported)::date AS reported_month,
 nullif(replace(btrim(final_score),',','.'),'') AS score_text
 FROM public.formview_visit_chw_site WHERE reported>='2019-01-01' AND reported<date_trunc('month',CURRENT_DATE)
), ranked AS (
 SELECT *,row_number() OVER(PARTITION BY site_uuid,reported_month ORDER BY reported_at DESC,uuid DESC) AS rank,
 count(*) OVER(PARTITION BY site_uuid,reported_month,reported_at) AS ties
 FROM raw WHERE site_uuid IS NOT NULL
), parsed AS (
 SELECT *,__SCORE__ AS score FROM ranked WHERE rank=1
)
 SELECT __GEO__,r.reported_month,CURRENT_TIMESTAMP AS calculated_at,
 CASE WHEN ties=1 AND score BETWEEN 0 AND 100 THEN score ELSE 0 END AS score_total,
 CASE WHEN ties=1 AND score BETWEEN 0 AND 100 THEN 1 ELSE 0 END::bigint AS assessed,
 CASE WHEN ties=1 AND score>=80 AND score<=100 THEN 1 ELSE 0 END::bigint AS acceptable,
 1::bigint AS visited,
 CASE WHEN ties=1 AND score BETWEEN 0 AND 100 THEN 0 ELSE 1 END::bigint AS unusable
 FROM parsed r JOIN public.mv_superset_sd_portfolio p ON p.chw_site_uuid=r.site_uuid""".replace('__SCORE__',number('score_text')).replace('__GEO__',GEO)
SD="""SELECT region_uuid,region,district_uuid,district AS district_name,
 concat_ws(' · ',district,region) AS district,health_area_uuid,health_area AS cscom_name,
 concat_ws(' · ',health_area,district,region) AS cscom,supervisor_area_uuid,supervisor_area AS zone_name,
 concat_ws(' · ',supervisor_area,health_area,district,region) AS zone,
 chw_site_uuid AS site_uuid,chw_site AS site_name,reported_month,
 CURRENT_TIMESTAMP AS calculated_at,supervisor_uuid,supervisor_name,assignment_status,
 CASE assignment_status WHEN 'assigned' THEN 'Affectation identifiée' WHEN 'conflict' THEN 'Affectation en conflit' ELSE 'Affectation non identifiée' END AS assignment_label,
 received_sd_complete_quota::bigint AS quota,has_visit_chw_site::bigint AS visited,
 visit_chw_site_reports::bigint AS site_visits,visit_community_without_chw_reports::bigint AS community_visits,
 individual_feedback_reports::bigint AS feedbacks
 FROM public.mv_superset_sd_chw_monthly_status
 WHERE reported_month<date_trunc('month',CURRENT_DATE)"""
TABLES={'geo':('mv_disc_gps_quality_v1',GPS),'asc':('mv_disc_asc_ranking_v1',ASC),'sd':('mv_disc_sd_ranking_v1',SD)}
MAP_SQL=GPS.replace('SELECT '+GEO+',CURRENT_DATE AS reported_month',
 'SELECT '+GEO+',r.lat AS latitude,r.lon AS longitude,CURRENT_DATE AS reported_month')+" WHERE r.ties=1 AND r.valid"
REFRESH_TABLES={**TABLES,'map':('mv_disc_sites_map_v1',MAP_SQL)}
def write_sources():
 p=ROOT/'sql/supervision/geo-ranking';p.mkdir(parents=True,exist_ok=True)
 for key,(_,sql) in REFRESH_TABLES.items():(p/(key+'.sql')).write_text(sql+'\n')
if __name__=='__main__':write_sources()
