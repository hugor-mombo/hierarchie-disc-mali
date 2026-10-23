-- Une ligne par document de contact : l'index unique couchdb_doc_uuid garantit l'unicité.
-- Filtre textuel sur les dates en millisecondes (13 chiffres), compatible avec l'index amont existant.
WITH contacts AS MATERIALIZED (
 SELECT doc->>'_id' AS uuid,doc->>'contact_type' AS contact_type,
  CASE doc->>'contact_type'
   WHEN 'c70_village' THEN doc #>> '{parent,_id}'
   WHEN 'c80_concession' THEN doc #>> '{parent,parent,_id}'
   WHEN 'c90_household' THEN doc #>> '{parent,parent,parent,_id}'
   WHEN 'c92_household' THEN doc #>> '{parent,parent,parent,parent,_id}' END AS chw_site_uuid,
  date_trunc('month',to_timestamp((doc->>'reported_date')::bigint/1000))::date AS reported_month,
  doc #>> '{meta,created_by}' AS created_by,
  CASE WHEN doc->>'person_age_in_years' ~ '^[0-9]+([.][0-9]+)?$'
       AND length(doc->>'person_age_in_years')<12 THEN (doc->>'person_age_in_years')::numeric END AS age,
  CASE WHEN doc->>'sex' IN ('male','female') THEN doc->>'sex' ELSE 'unknown' END AS sex
 FROM public.couchdb
 WHERE doc->>'type' IN ('contact','clinic','district_hospital','health_center','person')
  AND doc->>'contact_type' IN ('c70_village','c80_concession','c90_household','c92_household')
  AND doc->>'_id' IS NOT NULL AND doc->>'reported_date' ~ '^[0-9]{13}$'
  AND doc->>'reported_date'>=(extract(epoch FROM date_trunc('month',CURRENT_DATE)-interval '12 months')*1000)::bigint::text
  AND doc->>'reported_date'<(extract(epoch FROM date_trunc('month',CURRENT_DATE))*1000)::bigint::text
)
SELECT *,CASE WHEN age IS NULL OR age<0 OR age>120 THEN 'unknown'
 WHEN age<1 THEN 'inf1' WHEN age<6 THEN '1_5' WHEN age<13 THEN '6_12'
 WHEN age<20 THEN '13_19' ELSE '20plus' END AS age_group
FROM contacts
