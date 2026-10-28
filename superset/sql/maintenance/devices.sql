WITH users AS MATERIALIZED (
 SELECT doc->>'name' AS username,doc->>'facility_id' AS facility_id,
 coalesce(doc->'roles','[]'::jsonb)::text AS roles
 FROM public.couchdb_medic_users WHERE doc->>'type'='user'
 AND nullif(doc->>'name','') IS NOT NULL
 AND lower(doc->>'name') NOT LIKE '%formation%'
 AND coalesce(doc->>'_deleted','false')<>'true' AND coalesce(doc->>'disabled','false')<>'true'
), candidates AS (
 SELECT site_uuid AS facility_id,region,district,cscom,zone,site_name FROM public.v_disc_site_registry_labels_v1
 UNION SELECT supervisor_area_uuid,region,district,cscom,zone,NULL FROM public.v_disc_site_registry_labels_v1
 UNION SELECT health_area_uuid,region,district,cscom,NULL,NULL FROM public.v_disc_site_registry_labels_v1
 UNION SELECT district_uuid,region,district,NULL,NULL,NULL FROM public.v_disc_site_registry_labels_v1
 UNION SELECT region_uuid,region,NULL,NULL,NULL,NULL FROM public.v_disc_site_registry_labels_v1
), geography AS (
 SELECT facility_id,CASE WHEN count(*)=1 THEN max(region) END AS region,
 CASE WHEN count(*)=1 THEN max(district) END AS district,
 CASE WHEN count(*)=1 THEN max(cscom) END AS cscom,
 CASE WHEN count(*)=1 THEN max(zone) END AS zone,
 CASE WHEN count(*)=1 THEN max(site_name) END AS site_name,count(*) AS branches
 FROM candidates WHERE facility_id IS NOT NULL GROUP BY facility_id
), ranked AS (
 SELECT *,row_number() OVER(PARTITION BY username,device_id ORDER BY
 (telemetry_day<=CURRENT_DATE) DESC NULLS LAST,telemetry_day DESC NULLS LAST,telemetry_id DESC) AS rank,
 count(*) OVER(PARTITION BY username,device_id,telemetry_day) AS ties
 FROM public.mv_disc_it_telemetry_v1 WHERE username IS NOT NULL AND device_id IS NOT NULL
), signals AS (
 SELECT username,device_id,
 max(telemetry_day) FILTER(WHERE telemetry_day<=CURRENT_DATE AND to_success>0) AS last_upload_day,
 max(telemetry_day) FILTER(WHERE telemetry_day<=CURRENT_DATE AND from_success>0) AS last_download_day,
 count(*) FILTER(WHERE telemetry_day>CURRENT_DATE) AS future_documents,
 count(*) FILTER(WHERE telemetry_day IS NULL OR telemetry_id IS NULL) AS invalid_date_documents,
 count(*) FILTER(WHERE telemetry_day BETWEEN CURRENT_DATE-6 AND CURRENT_DATE AND clock_count>0) AS clock_reports_7d,
 max(greatest(abs(clock_min_ms),abs(clock_max_ms))) FILTER(WHERE telemetry_day BETWEEN CURRENT_DATE-6 AND CURRENT_DATE) / 60000.0 AS clock_abs_minutes_7d,
 sum(coalesce(to_failure,0)+coalesce(from_failure,0)) FILTER(WHERE telemetry_day BETWEEN CURRENT_DATE-6 AND CURRENT_DATE) AS failure_events_7d,
 sum(denied) FILTER(WHERE telemetry_day BETWEEN CURRENT_DATE-6 AND CURRENT_DATE) AS denied_events_7d
 FROM public.mv_disc_it_telemetry_v1 GROUP BY 1,2
), pairs AS (
 SELECT r.username,r.device_id,r.telemetry_day,r.model,r.manufacturer,r.android_version,r.apk_version,r.cht_version,r.chrome_version,
 r.free_bytes,r.total_bytes,r.ram_bytes,r.storage_valid,
 CASE WHEN r.ties>1 OR r.source_conflicted THEN 1 ELSE 0 END AS latest_ambiguous,
 s.last_upload_day,s.last_download_day,s.future_documents,s.invalid_date_documents,
 s.clock_reports_7d,s.clock_abs_minutes_7d,coalesce(s.failure_events_7d,0) AS failure_events_7d,
 coalesce(s.denied_events_7d,0) AS denied_events_7d
 FROM ranked r JOIN signals s USING(username,device_id) WHERE r.rank=1
), accounts_devices AS (
 SELECT coalesce(u.username,p.username) AS username,u.facility_id,u.roles,p.device_id,
 CASE WHEN u.username IS NOT NULL THEN 'Compte courant' ELSE 'Compte absent / inactif / formation' END AS account_status,
 p.telemetry_day,p.model,p.manufacturer,p.android_version,p.apk_version,p.cht_version,p.chrome_version,
 p.free_bytes,p.total_bytes,p.ram_bytes,p.storage_valid,p.latest_ambiguous,p.last_upload_day,p.last_download_day,
 p.future_documents,p.invalid_date_documents,p.clock_reports_7d,p.clock_abs_minutes_7d,p.failure_events_7d,p.denied_events_7d
 FROM users u FULL JOIN pairs p USING(username)
), checked AS (
 SELECT a.*,g.region,g.district,g.cscom,g.zone,g.site_name,
 CASE WHEN g.facility_id IS NULL THEN 'Hors répertoire des sites' WHEN g.branches>1 THEN 'Branche ambiguë' ELSE 'Rattaché' END AS mapping_status,
 CASE WHEN telemetry_day<=CURRENT_DATE THEN CURRENT_DATE-telemetry_day END AS telemetry_age_days,
 CASE WHEN latest_ambiguous=0 AND storage_valid=1 THEN free_bytes/1073741824.0 END AS free_gib,
 CASE WHEN latest_ambiguous=0 AND storage_valid=1 THEN total_bytes/1073741824.0 END AS total_gib,
 CASE WHEN latest_ambiguous=0 AND storage_valid=1 THEN free_bytes/total_bytes END AS free_ratio,
 CASE WHEN android_version IS NOT NULL THEN 'Android' ELSE 'Navigateur / non renseigné' END AS device_type
 FROM accounts_devices a LEFT JOIN geography g USING(facility_id)
)
SELECT *,CASE WHEN device_id IS NULL THEN 'Aucune télémétrie'
 WHEN telemetry_day IS NULL OR telemetry_day>CURRENT_DATE THEN 'Date inexploitable ou future'
 WHEN latest_ambiguous=1 THEN 'Dernière mesure ambiguë'
 WHEN storage_valid IS DISTINCT FROM 1 THEN 'Stockage absent / invalide'
 WHEN free_gib<1 THEN 'Critique (< 1 Gio)'
 WHEN free_gib<2 OR free_ratio<0.1 THEN 'À surveiller (< 2 Gio ou < 10 %)'
 ELSE 'Espace suffisant selon seuils IT' END AS storage_status,
 CASE WHEN device_id IS NULL THEN 'Sans télémétrie'
 WHEN telemetry_day IS NULL OR telemetry_day>CURRENT_DATE THEN 'Date à vérifier'
 WHEN telemetry_age_days<=7 THEN '7 jours ou moins' WHEN telemetry_age_days<=30 THEN '8–30 jours'
 ELSE 'Plus de 30 jours' END AS telemetry_status,
 CURRENT_TIMESTAMP AS calculated_at FROM checked
