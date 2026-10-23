-- One notification cohort per business alert ID; collisions are quarantined.
WITH origins AS MATERIALIZED (
 SELECT * FROM public.mv_sebac_reports_v1
 WHERE form IN ('sebac_detection','sebac_alert_notification') AND date_status='Date exploitable'
), grouped AS (
 SELECT coalesce('id:'||alert_id,'report:'||report_uuid) AS alert_key,alert_id,
 (array_agg(report_uuid ORDER BY reported_at,report_uuid))[1] AS first_report_reference,min(reported_at) AS notified_at,max(reported_at) AS last_notification_at,
 count(*)::bigint AS notification_reports,count(DISTINCT site_uuid) AS site_count,
 count(*) FILTER(WHERE site_uuid IS NULL)::bigint AS missing_sites,
 bool_or(input_conflict) AS input_conflict,min(site_uuid) AS site_uuid,
 CASE WHEN count(DISTINCT actor)=1 THEN min(actor) ELSE 'Indéterminé / contradictoire' END AS actor,
 bool_or(mpe='yes') AS is_mpe,bool_or(event='yes') AS is_event,
 bool_or(mpe IS NULL OR event IS NULL) AS type_incomplete
 FROM origins GROUP BY 1,alert_id
), cohort AS (
 SELECT *,CASE WHEN alert_id IS NULL THEN 'Identifiant d’alerte absent'
 WHEN site_count<>1 OR missing_sites>0 OR input_conflict THEN 'Identité ou site en contradiction'
 ELSE 'Identité exploitable' END AS identity_status FROM grouped
), stages AS MATERIALIZED (
 SELECT a.alert_key,r.* FROM cohort a JOIN public.mv_sebac_reports_v1 r
 ON r.alert_id=a.alert_id AND a.identity_status='Identité exploitable'
 AND r.date_status='Date exploitable' AND NOT r.input_conflict
 AND (r.site_uuid IS NULL OR r.site_uuid=a.site_uuid)
 AND r.reported_at>=a.notified_at
 WHERE r.form NOT IN ('sebac_detection','sebac_alert_notification')
), last_sort AS (
 SELECT s.*,dense_rank() OVER(PARTITION BY alert_key ORDER BY reported_at DESC) AS latest
 FROM stages s WHERE form='sebac_alert_sort'
), sort_class AS (
 SELECT alert_key,CASE WHEN count(DISTINCT coalesce(classification,'?'))<>1 THEN 'Tri ambigu'
 WHEN min(classification)='compliant' THEN 'Conforme'
 WHEN min(classification)='non_compliant' THEN 'Non conforme' ELSE 'Non renseignée' END AS tri_class
 FROM last_sort WHERE latest=1 GROUP BY 1
), progress AS (
 SELECT alert_key,
 min(reported_at) FILTER(WHERE form='sebac_alert_sort') AS sorted_at,
 min(reported_at) FILTER(WHERE form='sebac_alert_verification') AS verified_at,
 min(reported_at) FILTER(WHERE form='sebac_test_result') AS test_result_at,
 count(*) FILTER(WHERE form='sebac_alert_verification')::bigint AS verification_reports,
 count(*) FILTER(WHERE form='sebac_alert_sort')::bigint AS sort_reports,
 count(*) FILTER(WHERE form='sebac_alert_verification' AND checked='yes')::bigint AS checked_reports,
 count(*) FILTER(WHERE form='sebac_alert_verification' AND validated='yes')::bigint AS validated_reports
 FROM stages GROUP BY 1
)
SELECT a.alert_key,a.alert_id,a.first_report_reference,a.notified_at,a.last_notification_at,
 date_trunc('month',a.notified_at)::date AS reported_month,
 a.notification_reports,a.identity_status,a.actor,coalesce(a.is_mpe,false) AS is_mpe,coalesce(a.is_event,false) AS is_event,
 a.type_incomplete,a.site_uuid,r.site_name,r.region_uuid,r.region,r.district_uuid,r.district_name,r.district,
 r.health_area_uuid,r.cscom_name,r.cscom,r.supervisor_area_uuid,r.zone_name,r.zone,r.mapping_status,
 p.sorted_at,p.verified_at,p.test_result_at,coalesce(p.verification_reports,0) AS verification_reports,
 coalesce(p.sort_reports,0) AS sort_reports,coalesce(p.checked_reports,0) AS checked_reports,
 coalesce(p.validated_reports,0) AS validated_reports,
 coalesce(s.tri_class,'Sans tri enregistré') AS tri_class,
 CASE WHEN a.identity_status<>'Identité exploitable' THEN 'Identité à vérifier'
 WHEN p.verified_at IS NOT NULL THEN 'Vérification enregistrée'
 WHEN s.tri_class='Non conforme' THEN 'Tri non conforme · à examiner'
 WHEN p.sorted_at IS NOT NULL THEN 'Tri enregistré · sans vérification'
 ELSE 'Sans tri ni vérification enregistrés' END AS workflow_status,
 extract(epoch FROM (p.verified_at-a.notified_at))/3600 AS verification_hours,
 floor(extract(epoch FROM CURRENT_TIMESTAMP-a.notified_at)/86400)::bigint AS age_days,
 CASE WHEN a.identity_status='Identité exploitable' AND p.verified_at IS NULL
 AND coalesce(s.tri_class,'')<>'Non conforme' AND CURRENT_TIMESTAMP-a.notified_at>=interval '72 hours'
 THEN 1 ELSE 0 END::bigint AS review_72h,
 CURRENT_TIMESTAMP AS calculated_at
FROM cohort a
-- Choosing a geographic row cannot hide an identity conflict: those stay quarantined.
LEFT JOIN LATERAL (SELECT o.* FROM origins o WHERE coalesce('id:'||o.alert_id,'report:'||o.report_uuid)=a.alert_key
 ORDER BY o.reported_at,o.report_uuid LIMIT 1)r ON (a.identity_status='Identité exploitable' OR a.alert_id IS NULL)
LEFT JOIN progress p ON p.alert_key=a.alert_key LEFT JOIN sort_class s ON s.alert_key=a.alert_key
