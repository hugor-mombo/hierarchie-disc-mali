"""Monitoring IT : métadonnées techniques uniquement, accès explicitement désigné."""
from pathlib import Path
from uuid import UUID,uuid5
ROOT=Path(__file__).resolve().parent
NS=UUID('0e4e7c29-06aa-4247-86c5-6b60d847661e')
ROLE='DISC_IT_MONITORING'
SLUG='disc-maintenance-it'
def uid(key):return uuid5(NS,key)
TABLES={'events':'mv_disc_it_telemetry_v1','devices':'mv_disc_it_devices_v1'}
METRICS={
 'devices':[
  ('devices','Appareils distincts observés','COUNT(DISTINCT device_id)'),
  ('profiles','Profils compte–appareil','COUNT(*) FILTER(WHERE device_id IS NOT NULL)'),
  ('accounts','Comptes courants','COUNT(DISTINCT CASE WHEN account_status=\'Compte courant\' THEN username END)'),
  ('no_telemetry','Comptes courants sans télémétrie',"COUNT(DISTINCT CASE WHEN account_status='Compte courant' AND device_id IS NULL THEN username END)"),
  ('recent','Appareils avec télémétrie ≤ 7 jours','COUNT(DISTINCT CASE WHEN telemetry_age_days BETWEEN 0 AND 7 THEN device_id END)'),
  ('old','Appareils sans télémétrie récente (> 7 jours)','COUNT(DISTINCT CASE WHEN telemetry_age_days>7 THEN device_id END)'),
  ('critical','Stockage critique · mesure récente',"COUNT(DISTINCT CASE WHEN storage_status='Critique (< 1 Gio)' AND telemetry_age_days BETWEEN 0 AND 7 THEN device_id END)"),
  ('low','Stockage à surveiller · mesure récente',"COUNT(DISTINCT CASE WHEN storage_status='À surveiller (< 2 Gio ou < 10 %)' AND telemetry_age_days BETWEEN 0 AND 7 THEN device_id END)"),
  ('storage_known','Appareils avec mesure disque récente exploitable','COUNT(DISTINCT CASE WHEN storage_valid=1 AND latest_ambiguous=0 AND telemetry_age_days BETWEEN 0 AND 7 THEN device_id END)'),
  ('clock','Profils avec écart horloge signalé · 7 jours','COUNT(*) FILTER(WHERE clock_reports_7d>0)'),
  ('failures','Profils avec échec de réplication · 7 jours','COUNT(*) FILTER(WHERE failure_events_7d>0)'),
  ('denied','Profils avec document refusé · 7 jours','COUNT(*) FILTER(WHERE denied_events_7d>0)'),
  ('future','Profils avec période future dans la source','COUNT(*) FILTER(WHERE future_documents>0)'),
  ('bad_dates','Profils avec date de télémétrie inexploitable','COUNT(*) FILTER(WHERE invalid_date_documents>0)'),
  ('ambiguous','Dernières mesures ambiguës ou conflictuelles','COUNT(*) FILTER(WHERE latest_ambiguous=1)'),
  ('disk_min','Espace libre minimal mesuré (Gio)','MIN(free_gib)'),
  ('calculated','Calcul du relevé (UTC)',"to_char(MAX(calculated_at) AT TIME ZONE 'UTC','DD/MM/YYYY HH24:MI')"),
  ('source_latest','Dernier jour de télémétrie plausible','MAX(telemetry_day)'),
 ],
 'events':[
  ('documents','Documents de télémétrie','COUNT(*)'),
  ('devices','Appareils distincts observés','COUNT(DISTINCT device_id)'),
  ('to_success','Émissions réussies enregistrées','SUM(to_success)'),
  ('from_success','Réceptions réussies enregistrées','SUM(from_success)'),
  ('failures','Échecs de réplication enregistrés','SUM(coalesce(to_failure,0)+coalesce(from_failure,0))'),
  ('offline_client','Émission · échecs appareil hors ligne','SUM(offline_client)'),
  ('offline_server','Émission · serveur injoignable','SUM(offline_server)'),
  ('errors','Émission · autres erreurs','SUM(replication_errors)'),
  ('denied','Documents refusés à l’émission','SUM(denied)'),
  ('clock','Documents avec écart horloge signalé','COUNT(*) FILTER(WHERE clock_count>0)'),
  ('calculated','Calcul du relevé (UTC)',"to_char(MAX(calculated_at) AT TIME ZONE 'UTC','DD/MM/YYYY HH24:MI')"),
 ]}

def number(field):
 return f"CASE WHEN {field} ~ '^-?[0-9]{{1,18}}([.][0-9]{{1,6}})?$' THEN ({field})::numeric END"

def events_sql():
 paths={
  'free_bytes':('device','deviceInfo','storage','free'), 'total_bytes':('device','deviceInfo','storage','total'),
  'ram_bytes':('device','deviceInfo','ram','total'),
  'to_success':('metrics','replication:medic:to:success','count'),
  'from_success':('metrics','replication:medic:from:success','count'),
  'to_failure':('metrics','replication:medic:to:failure','count'),
  'from_failure':('metrics','replication:medic:from:failure','count'),
  'offline_client':('metrics','replication:medic:to:failure:reason:offline:client','sum'),
  'offline_server':('metrics','replication:medic:to:failure:reason:offline:server','sum'),
  'replication_errors':('metrics','replication:medic:to:failure:reason:error','sum'),
  'denied':('metrics','replication:medic:to:denied','sum'),
  'clock_count':('metrics','client-date-offset','count'),
  'clock_min_ms':('metrics','client-date-offset','min'),
  'clock_max_ms':('metrics','client-date-offset','max'),
 }
 measures=',\n'.join(number("doc#>>'{"+','.join(path)+"}'")+' AS '+key for key,path in paths.items())
 # Only whitelisted fields are projected: no feedback logs, reports, phone numbers or auth fields.
 return """WITH raw AS MATERIALIZED (
 SELECT nullif(doc->>'_id','') AS telemetry_id,
 nullif(btrim(doc#>>'{metadata,user}'),'') AS username,
 nullif(btrim(doc#>>'{metadata,deviceId}'),'') AS device_id,
 CASE WHEN doc#>>'{metadata,year}' ~ '^[0-9]{4}$' THEN (doc#>>'{metadata,year}')::int END AS y,
 CASE WHEN doc#>>'{metadata,month}' ~ '^[0-9]{1,2}$' THEN (doc#>>'{metadata,month}')::int END AS m,
 CASE WHEN doc#>>'{metadata,day}' ~ '^[0-9]{1,2}$' THEN (doc#>>'{metadata,day}')::int END AS d,
 doc#>>'{device,deviceInfo,hardware,model}' AS model,
 doc#>>'{device,deviceInfo,hardware,manufacturer}' AS manufacturer,
 doc#>>'{device,deviceInfo,software,androidVersion}' AS android_version,
 doc#>>'{device,deviceInfo,app,version}' AS apk_version,
 doc#>>'{metadata,versions,app}' AS cht_version,
 substring(doc#>>'{device,userAgent}' from 'Chrome/([0-9.]+)') AS chrome_version,
 coalesce(doc#>>'{metadata,conflicted}','false') IN ('true','1') AS source_conflicted,
 """+measures+"""
 FROM public.couchdb_users_meta WHERE doc->>'type'='telemetry'
 AND coalesce(doc->>'_deleted','false')<>'true'
), dates AS (
 SELECT *,CASE WHEN y BETWEEN 2019 AND 2100 AND m BETWEEN 1 AND 12 AND d BETWEEN 1 AND 31
 THEN make_date(y,m,1)+(d-1) END AS candidate_day FROM raw
)
SELECT *,CASE WHEN extract(month FROM candidate_day)=m THEN candidate_day END AS telemetry_day,
 CASE WHEN free_bytes>=0 AND total_bytes>0 AND free_bytes<=total_bytes THEN 1 ELSE 0 END::int AS storage_valid,
 CURRENT_TIMESTAMP AS calculated_at FROM dates"""

DEVICES="""WITH users AS MATERIALIZED (
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
 FROM __EVENTS__ WHERE username IS NOT NULL AND device_id IS NOT NULL
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
 FROM __EVENTS__ GROUP BY 1,2
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
 CURRENT_TIMESTAMP AS calculated_at FROM checked"""

def write_sql():
 target=ROOT/'sql/maintenance';target.mkdir(parents=True,exist_ok=True)
 (target/'events.sql').write_text(events_sql()+'\n')
 (target/'devices.sql').write_text(DEVICES.replace('__EVENTS__','public.'+TABLES['events'])+'\n')
if __name__=='__main__':write_sql()
