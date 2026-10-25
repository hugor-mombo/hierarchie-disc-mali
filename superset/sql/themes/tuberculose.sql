WITH source AS (SELECT entity_uuid,reported_month,count(*)::bigint AS input_rows,sum(followed) AS followed,sum(contacts) AS contacts,sum(contacts_referred) AS contacts_referred,sum(lost_found) AS lost_found FROM (WITH followup AS (
 SELECT reported_by_parent AS site_uuid,coalesce(s_reported_date,reported) AS event_date,
 nullif(btrim(patient_id),'') AS patient,has_patient_returned,why_has_patient_returned
 FROM public.formview_tb_treatment_followup
 WHERE reported<=CURRENT_TIMESTAMP AND coalesce(s_reported_date,reported)>=date_trunc('month',CURRENT_DATE)-interval '12 months'
 AND coalesce(s_reported_date,reported)<date_trunc('month',CURRENT_DATE)
), contacts AS MATERIALIZED (
 SELECT coalesce(f.chw_area,d.doc#>>'{contact,parent,_id}') AS site_uuid,f.reported AS event_date,
 nullif(btrim(d.doc#>>'{fields,patient_uuid}'),'') AS patient,d.doc#>>'{fields,patient_type,case_type}' AS case_type,d.doc#>>'{fields,refer_to_cscom}' AS referred
 FROM public.form_metadata f JOIN LATERAL(SELECT doc FROM public.couchdb c WHERE c.doc->>'_id'=f.uuid OFFSET 0)d ON true
 WHERE f.formname='assessment_case_contact_tb' AND f.reported>=date_trunc('month',CURRENT_DATE)-interval '12 months' AND reported<date_trunc('month',CURRENT_DATE)
), parts AS (
 SELECT site_uuid,date_trunc('month',event_date)::date AS reported_month,
 count(DISTINCT patient) FILTER(WHERE has_patient_returned='yes')::numeric AS followed,
 0::numeric AS contacts,0::numeric AS contacts_referred,
 count(DISTINCT patient) FILTER(WHERE has_patient_returned='yes' AND why_has_patient_returned='patient_lost_found')::numeric AS lost_found
 FROM followup GROUP BY 1,2
 UNION ALL SELECT site_uuid,date_trunc('month',event_date)::date,0,
 count(DISTINCT patient) FILTER(WHERE case_type='contact_case'),
 count(DISTINCT patient) FILTER(WHERE case_type='contact_case' AND referred='yes'),0
 FROM contacts GROUP BY 1,2
)
SELECT site_uuid AS entity_uuid,reported_month,sum(followed) AS followed,sum(contacts) AS contacts,
 sum(contacts_referred) AS contacts_referred,sum(lost_found) AS lost_found FROM parts GROUP BY 1,2
) raw GROUP BY entity_uuid,reported_month), geography AS (SELECT * FROM public.mv_asc_ops_geography)
    SELECT s.entity_uuid,s.reported_month::date,s.input_rows,g.region_uuid,
      coalesce(g.region,'Hors répertoire courant') AS region,g.district_uuid,
      coalesce(g.district,'Hors répertoire courant') AS district,g.district_name,g.health_area_uuid,
      coalesce(g.cscom,'Hors répertoire courant') AS cscom,g.cscom_name,g.site_uuid,g.site,g.site_name,g.supervision_area,
      CASE WHEN g.site_uuid IS NULL THEN 'Hors répertoire courant' ELSE 'Rattaché au répertoire courant' END AS attribution,
      s.followed,s.contacts,s.contacts_referred,s.lost_found,
      CURRENT_TIMESTAMP AS calculated_at,
      (date_trunc('month',CURRENT_DATE)-interval '12 months')::date AS coverage_start,
      date_trunc('month',CURRENT_DATE)::date AS coverage_end
    FROM source s LEFT JOIN geography g ON g.site_uuid=s.entity_uuid
