-- Patient identifiers stay in PostgreSQL; publish only CSCOM/month aggregates.
WITH raw AS MATERIALIZED (
 SELECT f.uuid,f.formname,f.reported,coalesce(f.chw_area,d.doc#>>'{contact,parent,_id}') AS site_uuid,
 coalesce(nullif(btrim(d.doc#>>'{fields,patient_uuid}'),''),nullif(btrim(d.doc#>>'{fields,patient_id}'),''),nullif(btrim(d.doc#>>'{fields,inputs,contact,_id}'),'')) AS patient,
 d.doc->'fields' AS fields
 FROM public.form_metadata f JOIN LATERAL (
  SELECT doc FROM public.couchdb c WHERE c.doc->>'_id'=f.uuid OFFSET 0
 ) d ON true
 WHERE f.formname IN ('pregnancy_followup','pregnancy_registration','pregnancy_confirmation','pregnancy_referral_followup','mother_referral_followup','postnatal_followup','delivery_registration')
 AND f.reported>=date_trunc('month',CURRENT_DATE)-interval '12 months' AND reported<date_trunc('month',CURRENT_DATE)
), flags AS (
 SELECT *,formname='pregnancy_followup' AND fields#>>'{g_followup_realization,g_sp_administration,has_given_ps1}'='yes' AS sp1,
 ((formname='pregnancy_followup' AND fields#>>'{g_followup_realization,g_sp_administration,has_given_ps2}'='yes'
 AND replace(fields#>>'{g_followup_realization,g_sp_administration,sp_administered}','_','') IN ('sp3','sp4','sp5','sp6'))
 OR (formname='pregnancy_registration' AND fields#>>'{g_sp_administration,has_given_sp}'='yes'
 AND replace(fields#>>'{g_sp_administration,sp_administered}','_','') IN ('sp3','sp4','sp5','sp6'))) AS sp3_month,
 (formname IN ('pregnancy_followup','pregnancy_referral_followup','mother_referral_followup','postnatal_followup') AND (
 fields#>>'{g_end_followup,why_end_followup}' IN ('death_of_the woman','mother_deceased')
 OR (formname='postnatal_followup' AND fields#>>'{g_postnatal_consultation,mother_alive}'='no'))) AS death
 FROM raw
), events AS (
 SELECT site_uuid,reported,patient,sp1,sp3_month,death,false AS anc_referred,false AS home_referred FROM flags
 UNION ALL
 SELECT reported_by_parent,reported,nullif(btrim(patient_uuid),''),false,false,false,
 pregnancy_confirmed='yes' AND had_prenatal_visit='no' AND refer_to_cscom_chw='yes',false
 FROM public.formview_pregnancy_registration WHERE reported>=date_trunc('month',CURRENT_DATE)-interval '12 months' AND reported<date_trunc('month',CURRENT_DATE)
 UNION ALL
 SELECT reported_by_parent,reported,nullif(btrim(patient_uuid),''),false,false,false,
 pregnancy_confirmed='yes' AND had_prenatal_visit='no' AND refer_to_cscom_chw='yes',false
 FROM public.formview_pregnancy_confirmation WHERE reported>=date_trunc('month',CURRENT_DATE)-interval '12 months' AND reported<date_trunc('month',CURRENT_DATE)
 UNION ALL
 SELECT reported_by_parent,reported,nullif(btrim(patient_uuid),''),false,false,false,false,
 delivery_location='home' AND refer_patient_to_cscom_chw='yes'
 FROM public.formview_delivery_registration WHERE reported>=date_trunc('month',CURRENT_DATE)-interval '12 months' AND reported<date_trunc('month',CURRENT_DATE)
)
SELECT concat(coalesce(g.region_uuid,'?'),'|',coalesce(g.district_uuid,'?'),'|',coalesce(g.health_area_uuid,'?')) AS entity_uuid,
 date_trunc('month',r.reported)::date AS reported_month,
count(DISTINCT patient) FILTER(WHERE sp1)::numeric AS sp1,
count(DISTINCT patient) FILTER(WHERE sp3_month)::numeric AS sp3_month,
count(DISTINCT patient) FILTER(WHERE death)::numeric AS death,
count(DISTINCT patient) FILTER(WHERE anc_referred)::numeric AS anc_referred,
count(DISTINCT patient) FILTER(WHERE home_referred)::numeric AS home_referred
 FROM events r LEFT JOIN public.mv_asc_ops_geography g ON g.site_uuid=r.site_uuid GROUP BY 1,2
