WITH source AS (SELECT entity_uuid,reported_month,count(*)::bigint AS input_rows,sum(villages) AS villages,sum(concessions) AS concessions,sum(households) AS households,sum(members) AS members,sum(age_inf1_male) AS age_inf1_male,sum(age_inf1_female) AS age_inf1_female,sum(age_inf1_unknown) AS age_inf1_unknown,sum(age_1_5_male) AS age_1_5_male,sum(age_1_5_female) AS age_1_5_female,sum(age_1_5_unknown) AS age_1_5_unknown,sum(age_6_12_male) AS age_6_12_male,sum(age_6_12_female) AS age_6_12_female,sum(age_6_12_unknown) AS age_6_12_unknown,sum(age_13_19_male) AS age_13_19_male,sum(age_13_19_female) AS age_13_19_female,sum(age_13_19_unknown) AS age_13_19_unknown,sum(age_20plus_male) AS age_20plus_male,sum(age_20plus_female) AS age_20plus_female,sum(age_20plus_unknown) AS age_20plus_unknown,sum(age_unknown_male) AS age_unknown_male,sum(age_unknown_female) AS age_unknown_female,sum(age_unknown_unknown) AS age_unknown_unknown FROM (WITH contacts AS (-- Une ligne par document de contact : l'index unique couchdb_doc_uuid garantit l'unicité.
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
) SELECT chw_site_uuid AS entity_uuid,reported_month,count(*) FILTER(WHERE contact_type='c70_village' AND created_by NOT ILIKE '%formation%')::numeric AS villages,count(*) FILTER(WHERE contact_type='c80_concession' AND created_by LIKE '%asc%')::numeric AS concessions,count(*) FILTER(WHERE contact_type='c90_household' AND created_by LIKE '%asc%')::numeric AS households,count(*) FILTER(WHERE contact_type='c92_household' AND created_by LIKE '%asc%')::numeric AS members,count(*) FILTER(WHERE contact_type='c92_household' AND age_group='inf1' AND sex='male')::numeric AS age_inf1_male,count(*) FILTER(WHERE contact_type='c92_household' AND age_group='inf1' AND sex='female')::numeric AS age_inf1_female,count(*) FILTER(WHERE contact_type='c92_household' AND age_group='inf1' AND sex='unknown')::numeric AS age_inf1_unknown,count(*) FILTER(WHERE contact_type='c92_household' AND age_group='1_5' AND sex='male')::numeric AS age_1_5_male,count(*) FILTER(WHERE contact_type='c92_household' AND age_group='1_5' AND sex='female')::numeric AS age_1_5_female,count(*) FILTER(WHERE contact_type='c92_household' AND age_group='1_5' AND sex='unknown')::numeric AS age_1_5_unknown,count(*) FILTER(WHERE contact_type='c92_household' AND age_group='6_12' AND sex='male')::numeric AS age_6_12_male,count(*) FILTER(WHERE contact_type='c92_household' AND age_group='6_12' AND sex='female')::numeric AS age_6_12_female,count(*) FILTER(WHERE contact_type='c92_household' AND age_group='6_12' AND sex='unknown')::numeric AS age_6_12_unknown,count(*) FILTER(WHERE contact_type='c92_household' AND age_group='13_19' AND sex='male')::numeric AS age_13_19_male,count(*) FILTER(WHERE contact_type='c92_household' AND age_group='13_19' AND sex='female')::numeric AS age_13_19_female,count(*) FILTER(WHERE contact_type='c92_household' AND age_group='13_19' AND sex='unknown')::numeric AS age_13_19_unknown,count(*) FILTER(WHERE contact_type='c92_household' AND age_group='20plus' AND sex='male')::numeric AS age_20plus_male,count(*) FILTER(WHERE contact_type='c92_household' AND age_group='20plus' AND sex='female')::numeric AS age_20plus_female,count(*) FILTER(WHERE contact_type='c92_household' AND age_group='20plus' AND sex='unknown')::numeric AS age_20plus_unknown,count(*) FILTER(WHERE contact_type='c92_household' AND age_group='unknown' AND sex='male')::numeric AS age_unknown_male,count(*) FILTER(WHERE contact_type='c92_household' AND age_group='unknown' AND sex='female')::numeric AS age_unknown_female,count(*) FILTER(WHERE contact_type='c92_household' AND age_group='unknown' AND sex='unknown')::numeric AS age_unknown_unknown FROM contacts GROUP BY 1,2) raw GROUP BY entity_uuid,reported_month), geography AS (SELECT * FROM public.mv_asc_ops_geography)
    SELECT s.entity_uuid,s.reported_month::date,s.input_rows,g.region_uuid,
      coalesce(g.region,'Hors répertoire courant') AS region,g.district_uuid,
      coalesce(g.district,'Hors répertoire courant') AS district,g.district_name,g.health_area_uuid,
      coalesce(g.cscom,'Hors répertoire courant') AS cscom,g.cscom_name,g.site_uuid,g.site,g.site_name,g.supervision_area,
      CASE WHEN g.site_uuid IS NULL THEN 'Hors répertoire courant' ELSE 'Rattaché au répertoire courant' END AS attribution,
      s.villages,s.concessions,s.households,s.members,s.age_inf1_male,s.age_inf1_female,s.age_inf1_unknown,s.age_1_5_male,s.age_1_5_female,s.age_1_5_unknown,s.age_6_12_male,s.age_6_12_female,s.age_6_12_unknown,s.age_13_19_male,s.age_13_19_female,s.age_13_19_unknown,s.age_20plus_male,s.age_20plus_female,s.age_20plus_unknown,s.age_unknown_male,s.age_unknown_female,s.age_unknown_unknown,
      CURRENT_TIMESTAMP AS calculated_at,
      (date_trunc('month',CURRENT_DATE)-interval '12 months')::date AS coverage_start,
      date_trunc('month',CURRENT_DATE)::date AS coverage_end
    FROM source s LEFT JOIN geography g ON g.site_uuid=s.entity_uuid
