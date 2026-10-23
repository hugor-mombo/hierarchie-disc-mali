-- Current snapshot: no sum of elapsed days over weeks, and no fabricated zero.
WITH activity AS (
 SELECT site_uuid,max(reported_at) AS last_notification,
 max(reported_at) FILTER(WHERE actor='ASC' AND (mpe='yes' OR event='yes')) AS last_asc_notification,
 count(*)::bigint AS notification_reports
 FROM public.mv_sebac_reports_v1
 WHERE form IN ('sebac_detection','sebac_alert_notification') AND date_status='Date exploitable' AND NOT input_conflict
 GROUP BY 1
)
SELECT g.chw_site_uuid AS site_uuid,g.chw_site AS site_name,g.region_uuid,g.region,g.district_uuid,
 g.district AS district_name,concat_ws(' · ',g.district,g.region) AS district,
 g.health_area_uuid,g.health_area AS cscom_name,concat_ws(' · ',g.health_area,g.district,g.region) AS cscom,
 g.supervisor_area_uuid,g.supervisor_area AS zone_name,concat_ws(' · ',g.supervisor_area,g.health_area,g.district,g.region) AS zone,
 a.last_notification,a.last_asc_notification,coalesce(a.notification_reports,0) AS notification_reports,
 floor(extract(epoch FROM CURRENT_TIMESTAMP-a.last_asc_notification)/86400)::bigint AS days_since_asc,
 CASE WHEN a.last_asc_notification IS NULL THEN 'Aucune notification ASC observée'
 WHEN CURRENT_TIMESTAMP-a.last_asc_notification>=interval '30 days' THEN 'Dernière notification ASC ≥ 30 jours'
 ELSE 'Notification ASC < 30 jours' END AS notification_status,
 'Rattaché au répertoire courant'::text AS mapping_status,CURRENT_TIMESTAMP AS calculated_at,
 date_trunc('month',CURRENT_TIMESTAMP)::date AS reported_month
FROM public.mv_superset_sd_portfolio g LEFT JOIN activity a ON a.site_uuid=g.chw_site_uuid
