WITH raw AS MATERIALIZED (
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
 CASE WHEN doc#>>'{device,deviceInfo,storage,free}' ~ '^-?[0-9]{1,18}([.][0-9]{1,6})?$' THEN (doc#>>'{device,deviceInfo,storage,free}')::numeric END AS free_bytes,
CASE WHEN doc#>>'{device,deviceInfo,storage,total}' ~ '^-?[0-9]{1,18}([.][0-9]{1,6})?$' THEN (doc#>>'{device,deviceInfo,storage,total}')::numeric END AS total_bytes,
CASE WHEN doc#>>'{device,deviceInfo,ram,total}' ~ '^-?[0-9]{1,18}([.][0-9]{1,6})?$' THEN (doc#>>'{device,deviceInfo,ram,total}')::numeric END AS ram_bytes,
CASE WHEN doc#>>'{metrics,replication:medic:to:success,count}' ~ '^-?[0-9]{1,18}([.][0-9]{1,6})?$' THEN (doc#>>'{metrics,replication:medic:to:success,count}')::numeric END AS to_success,
CASE WHEN doc#>>'{metrics,replication:medic:from:success,count}' ~ '^-?[0-9]{1,18}([.][0-9]{1,6})?$' THEN (doc#>>'{metrics,replication:medic:from:success,count}')::numeric END AS from_success,
CASE WHEN doc#>>'{metrics,replication:medic:to:failure,count}' ~ '^-?[0-9]{1,18}([.][0-9]{1,6})?$' THEN (doc#>>'{metrics,replication:medic:to:failure,count}')::numeric END AS to_failure,
CASE WHEN doc#>>'{metrics,replication:medic:from:failure,count}' ~ '^-?[0-9]{1,18}([.][0-9]{1,6})?$' THEN (doc#>>'{metrics,replication:medic:from:failure,count}')::numeric END AS from_failure,
CASE WHEN doc#>>'{metrics,replication:medic:to:failure:reason:offline:client,sum}' ~ '^-?[0-9]{1,18}([.][0-9]{1,6})?$' THEN (doc#>>'{metrics,replication:medic:to:failure:reason:offline:client,sum}')::numeric END AS offline_client,
CASE WHEN doc#>>'{metrics,replication:medic:to:failure:reason:offline:server,sum}' ~ '^-?[0-9]{1,18}([.][0-9]{1,6})?$' THEN (doc#>>'{metrics,replication:medic:to:failure:reason:offline:server,sum}')::numeric END AS offline_server,
CASE WHEN doc#>>'{metrics,replication:medic:to:failure:reason:error,sum}' ~ '^-?[0-9]{1,18}([.][0-9]{1,6})?$' THEN (doc#>>'{metrics,replication:medic:to:failure:reason:error,sum}')::numeric END AS replication_errors,
CASE WHEN doc#>>'{metrics,replication:medic:to:denied,sum}' ~ '^-?[0-9]{1,18}([.][0-9]{1,6})?$' THEN (doc#>>'{metrics,replication:medic:to:denied,sum}')::numeric END AS denied,
CASE WHEN doc#>>'{metrics,client-date-offset,count}' ~ '^-?[0-9]{1,18}([.][0-9]{1,6})?$' THEN (doc#>>'{metrics,client-date-offset,count}')::numeric END AS clock_count,
CASE WHEN doc#>>'{metrics,client-date-offset,min}' ~ '^-?[0-9]{1,18}([.][0-9]{1,6})?$' THEN (doc#>>'{metrics,client-date-offset,min}')::numeric END AS clock_min_ms,
CASE WHEN doc#>>'{metrics,client-date-offset,max}' ~ '^-?[0-9]{1,18}([.][0-9]{1,6})?$' THEN (doc#>>'{metrics,client-date-offset,max}')::numeric END AS clock_max_ms
 FROM public.couchdb_users_meta WHERE doc->>'type'='telemetry'
 AND coalesce(doc->>'_deleted','false')<>'true'
), dates AS (
 SELECT *,CASE WHEN y BETWEEN 2019 AND 2100 AND m BETWEEN 1 AND 12 AND d BETWEEN 1 AND 31
 THEN make_date(y,m,1)+(d-1) END AS candidate_day FROM raw
)
SELECT *,CASE WHEN extract(month FROM candidate_day)=m THEN candidate_day END AS telemetry_day,
 CASE WHEN free_bytes>=0 AND total_bytes>0 AND free_bytes<=total_bytes THEN 1 ELSE 0 END::int AS storage_valid,
 CURRENT_TIMESTAMP AS calculated_at FROM dates
