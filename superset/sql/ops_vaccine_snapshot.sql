-- Relevé opérationnel : contacts courants, âge cible et localisation contrôlés
-- AVANT de lire les formulaires cliniques volumineux.
WITH historic_positive AS MATERIALIZED (
  SELECT DISTINCT patient_uuid
  FROM public.mv_children_vaccination_history
  WHERE report_month<date_trunc('month',CURRENT_DATE)
    AND antigens_status_until_month ~ '(^|, )Penta 1(,|$)'
), latest_metadata AS MATERIALIZED (
  SELECT DISTINCT ON (patient_uuid,formname) uuid,patient_uuid,formname,reported,chw,chw_area
  FROM public.form_metadata f
  WHERE formname IN ('child_longitudinal_followup_1_24','vaccine_followup_under_5','patient_assessment_under_5')
    AND reported<=CURRENT_TIMESTAMP AND patient_uuid IS NOT NULL
    AND NOT EXISTS(SELECT 1 FROM historic_positive hp WHERE hp.patient_uuid=f.patient_uuid)
  ORDER BY patient_uuid,formname,reported DESC,uuid DESC
), patient_metadata AS MATERIALIZED (
  SELECT DISTINCT ON (patient_uuid) * FROM latest_metadata
  ORDER BY patient_uuid,reported DESC,uuid DESC
), contacts AS MATERIALIZED (
  SELECT m.patient_uuid,m.chw,m.chw_area,
    p.doc->>'name' AS patient_name,p.doc->>'sex' AS sex,
    p.doc->>'date_of_birth' AS birth_text,
    (coalesce(p.doc->>'deceased',p.doc->>'is_deceased','false') IN ('true','yes')
      OR nullif(p.doc->>'date_of_death','') IS NOT NULL) AS deceased_recorded,
    ARRAY[p.doc#>>'{parent,_id}',p.doc#>>'{parent,parent,_id}',
      p.doc#>>'{parent,parent,parent,_id}',p.doc#>>'{parent,parent,parent,parent,_id}',
      p.doc#>>'{parent,parent,parent,parent,parent,_id}',
      p.doc#>>'{parent,parent,parent,parent,parent,parent,_id}'] AS ancestors
  FROM patient_metadata m
  JOIN LATERAL(SELECT doc FROM public.couchdb WHERE doc->>'_id'=m.patient_uuid LIMIT 1) p ON true
  WHERE coalesce(p.doc->>'_deleted','false')<>'true'
    AND p.doc->>'type' IN ('contact','person')
), current_locations AS MATERIALIZED (
  SELECT c.patient_uuid,min(g.site_uuid) AS site_uuid,count(DISTINCT g.site_uuid) AS n
  FROM contacts c CROSS JOIN LATERAL unnest(c.ancestors) a(id)
  JOIN public.mv_asc_ops_geography g ON g.site_uuid=a.id
  GROUP BY c.patient_uuid
), parsed_contacts AS MATERIALIZED (
  SELECT c.*,loc.site_uuid AS current_site_uuid,coalesce(loc.n,0) AS locations,
    coalesce(loc.site_uuid,pg.site_uuid,sg.site_uuid) AS selected_site_uuid,
    CASE WHEN c.birth_text ~ '^(19|20)[0-9]{2}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'
         THEN make_date(substring(c.birth_text,1,4)::integer,substring(c.birth_text,6,2)::integer,1)
             + (substring(c.birth_text,9,2)::integer-1) END AS birth_parsed
  FROM contacts c LEFT JOIN current_locations loc USING(patient_uuid)
  LEFT JOIN public.mv_asc_ops_geography pg ON pg.site_uuid=c.chw_area
  LEFT JOIN public.mv_asc_ops_geography sg ON sg.site_uuid=c.chw
), contact_ages AS MATERIALIZED (
  SELECT *,CASE WHEN to_char(birth_parsed,'YYYY-MM-DD')=birth_text AND birth_parsed<=CURRENT_DATE
    THEN (extract(year FROM age(CURRENT_DATE,birth_parsed))*12+extract(month FROM age(CURRENT_DATE,birth_parsed)))::integer
    END AS age_months FROM parsed_contacts
), eligible AS MATERIALIZED (
  SELECT * FROM contact_ages
  WHERE NOT deceased_recorded AND selected_site_uuid IS NOT NULL
    AND (age_months BETWEEN 12 AND 59 OR age_months IS NULL)
), selected_reports AS MATERIALIZED (
  SELECT f.* FROM latest_metadata f JOIN eligible e USING(patient_uuid)
  UNION
  SELECT f.uuid,f.patient_uuid,f.formname,f.reported,f.chw,f.chw_area
  FROM public.form_metadata f JOIN eligible e USING(patient_uuid)
  WHERE f.formname IN ('child_longitudinal_followup_1_24','vaccine_followup_under_5','patient_assessment_under_5')
    AND f.reported>=date_trunc('month',CURRENT_DATE) AND f.reported<=CURRENT_TIMESTAMP
), observations AS MATERIALIZED (
  SELECT f.*,lower(trim(coalesce(
      c.doc#>>'{fields,s_general_tracking,vaccine_followup,is_vaccine_penta_1}',
      c.doc#>>'{fields,vaccine_followup,is_vaccine_penta_1}'))) AS penta1,
    lower(trim(c.doc#>>'{fields,already_is_vaccine_penta_1}')) AS already_penta1
  FROM selected_reports f
  JOIN LATERAL(SELECT doc FROM public.couchdb WHERE doc->>'_id'=f.uuid LIMIT 1) c ON true
), evidence AS MATERIALIZED (
  SELECT patient_uuid,bool_or(penta1='yes' OR already_penta1='yes') AS has_positive,
         bool_or(penta1='no' OR already_penta1='no') AS has_negative,
         max(reported) FILTER(WHERE formname='patient_assessment_under_5' AND penta1='no') AS last_negative_assessment
  FROM observations GROUP BY patient_uuid
), latest AS MATERIALIZED (
  SELECT DISTINCT ON (patient_uuid) * FROM observations
  ORDER BY patient_uuid,reported DESC,uuid DESC
), candidates AS (
  SELECT l.*,e.last_negative_assessment,
    -- Un état antérieur « no » recopié dans les inputs ne remplace pas
    -- une observation vaccinale absente du dernier formulaire.
    CASE WHEN l.penta1 IN ('yes','no') THEN l.penta1 END AS latest_penta1
  FROM latest l JOIN evidence e USING(patient_uuid)
  WHERE coalesce(e.has_negative,false) AND NOT coalesce(e.has_positive,false)
)
SELECT a.patient_uuid,coalesce(nullif(ct.patient_name,''),'Nom non renseigné') AS child_name,
       ct.sex,ct.age_months,
       CASE WHEN ct.age_months IS NULL THEN 'Âge à vérifier'
            WHEN ct.age_months<24 THEN '12–23 mois' ELSE '24–59 mois' END AS age_group,
       a.reported AS last_observation,a.formname AS source_form,a.latest_penta1,
       false AS positive_recorded,a.last_negative_assessment,false AS deceased_recorded,true AS contact_exists,
       CURRENT_DATE-a.reported::date AS observation_age_days,
       CASE WHEN ct.locations<>1 THEN 'Localisation courante à vérifier'
            WHEN ct.age_months IS NULL THEN 'Âge à vérifier'
            WHEN a.latest_penta1 IS DISTINCT FROM 'no' THEN 'Information vaccinale à actualiser'
            ELSE 'Penta 1 non reçu déclaré — à confirmer' END AS followup_status,
       g.*,CURRENT_DATE AS reference_date,CURRENT_TIMESTAMP AS refreshed_at
FROM candidates a JOIN eligible ct USING(patient_uuid)
JOIN public.mv_asc_ops_geography g ON g.site_uuid=ct.selected_site_uuid
