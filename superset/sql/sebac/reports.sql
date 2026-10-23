-- Whitelisted operational fields only; never expose patient names or free text.
WITH raw AS MATERIALIZED (
 SELECT doc->>'_id' AS report_uuid,doc->>'form' AS form,
 CASE WHEN doc->>'reported_date' ~ '^[0-9]{13}$'
 THEN to_timestamp((doc->>'reported_date')::bigint/1000.0) END AS reported_at,
 nullif(btrim(doc#>>'{fields,out,alert_id}'),'') AS out_id,
 nullif(btrim(doc#>>'{fields,inputs,alert_id}'),'') AS input_id,
 nullif(btrim(doc#>>'{fields,out,alert_chw_site_id}'),'') AS out_site,
 nullif(btrim(doc#>>'{fields,inputs,alert_chw_site_id}'),'') AS input_site,
 coalesce(nullif(btrim(doc#>>'{fields,out,alert_notify_by}'),''),
  nullif(btrim(doc#>>'{fields,detection,notified_by}'),''),
  nullif(btrim(doc#>>'{fields,g_alert_information,q_personne_notification}'),'')) AS actor_code,
 doc#>>'{fields,out,alert_diseases_surveillance}' AS mpe,
 doc#>>'{fields,out,alert_events_surveillance}' AS event,
 coalesce(nullif(doc#>>'{fields,out,alert_sort_classification}',''),
  nullif(doc#>>'{fields,info_sur_le_cas,classification_cas}','')) AS classification,
 doc#>>'{fields,out,alert_checked}' AS checked,
 doc#>>'{fields,out,alert_validated}' AS validated,
 doc#>>'{fields,out,alert_nb_people_dead}' AS human_deaths_text,
 doc#>>'{fields,out,alert_nb_animals_dead}' AS animal_deaths_text
 FROM public.couchdb
 WHERE doc->>'form' IN ('sebac_detection','sebac_alert_notification','sebac_alert_sort',
 'sebac_alert_sort_not_done','sebac_alert_verification','sebac_verification_notification',
 'sebac_verification_result','sebac_test_result_reminder','sebac_test_result',
 'sebac_result_notification_supervisor','sebac_result_notification_chw','sebac_alert_notification_dtc')
 AND coalesce(doc->>'deleted','false')<>'true' AND coalesce(doc->>'_deleted','false')<>'true'
), normalized AS (
 SELECT *,coalesce(out_id,input_id) AS alert_id,coalesce(out_site,input_site) AS site_uuid,
 coalesce(out_id<>input_id,false) OR coalesce(out_site<>input_site,false) AS input_conflict,
 CASE WHEN actor_code='chw' THEN 'ASC' WHEN actor_code IS NULL THEN 'Non renseigné' ELSE 'Autre acteur' END AS actor,
 CASE WHEN reported_at IS NULL OR reported_at<'2019-01-01' THEN 'Date absente ou invalide'
 WHEN reported_at>CURRENT_TIMESTAMP THEN 'Date future' ELSE 'Date exploitable' END AS date_status
 FROM raw
)
SELECT n.report_uuid,n.form,n.reported_at,date_trunc('month',n.reported_at)::date AS reported_month,
 n.alert_id,n.site_uuid,n.actor_code,n.actor,n.mpe,n.event,n.classification,n.checked,n.validated,
 CASE WHEN n.human_deaths_text ~ '^[0-9]{1,9}$' THEN n.human_deaths_text::bigint END AS human_deaths,
 CASE WHEN n.animal_deaths_text ~ '^[0-9]{1,9}$' THEN n.animal_deaths_text::bigint END AS animal_deaths,
 n.date_status,n.input_conflict,
 g.region_uuid,coalesce(g.region,'Non rattachée') AS region,g.district_uuid,
 coalesce(g.district,'Non rattaché') AS district_name,
 concat_ws(' · ',g.district,g.region) AS district,g.health_area_uuid,
 g.health_area AS cscom_name,concat_ws(' · ',g.health_area,g.district,g.region) AS cscom,
 g.supervisor_area_uuid,g.supervisor_area AS zone_name,
 concat_ws(' · ',g.supervisor_area,g.health_area,g.district,g.region) AS zone,g.chw_site AS site_name,
 CASE WHEN g.chw_site_uuid IS NOT NULL AND g.region_uuid IS NOT NULL AND g.district_uuid IS NOT NULL
 THEN 'Rattaché au répertoire courant' ELSE 'Hors répertoire courant' END AS mapping_status,
 CURRENT_TIMESTAMP AS calculated_at
FROM normalized n LEFT JOIN public.mv_superset_sd_portfolio g ON g.chw_site_uuid=n.site_uuid
