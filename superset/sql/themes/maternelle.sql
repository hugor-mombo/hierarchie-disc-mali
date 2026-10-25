WITH source AS (SELECT entity_uuid,reported_month,count(*)::bigint AS input_rows,sum(pregnant) AS pregnant,sum(followup) AS followup,sum(anc) AS anc,sum(anc_no) AS anc_no,sum(sp1) AS sp1,sum(sp3_month) AS sp3_month,sum(facility) AS facility,sum(home) AS home,sum(death) AS death,sum(anc_referred) AS anc_referred,sum(home_referred) AS home_referred FROM (WITH corrected AS (-- Patient identifiers stay in PostgreSQL; publish only CSCOM/month aggregates.
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
), legacy AS (WITH corrected AS (-- Le parent du contact est un ménage : dédupliquer les patientes à la place.
WITH reports AS (
 SELECT patient_uuid,reported,reported_by_parent FROM public.formview_pregnancy_registration
 WHERE pregnancy_confirmed='yes' AND reported>=date_trunc('month',CURRENT_DATE)-interval '12 months'
  AND reported<date_trunc('month',CURRENT_DATE) AND nullif(patient_uuid,'') IS NOT NULL
 UNION ALL
 SELECT patient_uuid,reported,reported_by_parent FROM public.formview_pregnancy_confirmation
 WHERE pregnancy_confirmed='yes' AND reported>=date_trunc('month',CURRENT_DATE)-interval '12 months'
  AND reported<date_trunc('month',CURRENT_DATE) AND nullif(patient_uuid,'') IS NOT NULL
)
SELECT concat(coalesce(g.region_uuid,'?'),'|',coalesce(g.district_uuid,'?'),'|',coalesce(g.health_area_uuid,'?')) AS entity_uuid,
 date_trunc('month',r.reported)::date AS reported_month,count(DISTINCT r.patient_uuid)::numeric AS pregnant
FROM reports r JOIN public.mv_asc_ops_geography g ON g.site_uuid=r.reported_by_parent
GROUP BY 1,2
), legacy AS (
          SELECT concat(coalesce(s.region_uuid,'?'),'|',coalesce(s.district_uuid,'?'),'|',coalesce(s.health_area_uuid,'?')) AS entity_uuid,s.* FROM public.mv_palu_sm_smi_tpig_indicators s WHERE s.reported_month>=date_trunc('month',CURRENT_DATE)-interval '12 months' AND s.reported_month<date_trunc('month',CURRENT_DATE)), periods AS (
          SELECT entity_uuid,reported_month FROM corrected UNION SELECT entity_uuid,reported_month FROM legacy)
          SELECT p.entity_uuid,p.reported_month,c.pregnant::numeric AS pregnant,s.nbr_pregnant_followup::numeric AS followup,s.nber_patient_been_to_anc::numeric AS anc,s.cpn_refered::numeric AS anc_no,s.hf_delivery::numeric AS facility,s.home_delivery::numeric AS home FROM periods p
          LEFT JOIN legacy s ON s.entity_uuid=p.entity_uuid AND s.reported_month=p.reported_month
          LEFT JOIN corrected c ON c.entity_uuid=p.entity_uuid AND c.reported_month=p.reported_month), periods AS (SELECT entity_uuid,reported_month FROM corrected UNION SELECT entity_uuid,reported_month FROM legacy) SELECT p.entity_uuid,p.reported_month,s.pregnant::numeric AS pregnant,s.followup::numeric AS followup,s.anc::numeric AS anc,s.anc_no::numeric AS anc_no,coalesce(c.sp1,0)::numeric AS sp1,coalesce(c.sp3_month,0)::numeric AS sp3_month,s.facility::numeric AS facility,s.home::numeric AS home,coalesce(c.death,0)::numeric AS death,coalesce(c.anc_referred,0)::numeric AS anc_referred,coalesce(c.home_referred,0)::numeric AS home_referred FROM periods p LEFT JOIN legacy s ON s.entity_uuid IS NOT DISTINCT FROM p.entity_uuid AND s.reported_month=p.reported_month LEFT JOIN corrected c ON c.entity_uuid IS NOT DISTINCT FROM p.entity_uuid AND c.reported_month=p.reported_month) raw GROUP BY entity_uuid,reported_month), geography AS (SELECT DISTINCT region_uuid,region,district_uuid,district,district_name,
        health_area_uuid,cscom,cscom_name,concat(coalesce(region_uuid,'?'),'|',coalesce(district_uuid,'?'),'|',coalesce(health_area_uuid,'?')) AS area_key FROM public.mv_asc_ops_geography)
    SELECT s.entity_uuid,s.reported_month::date,s.input_rows,g.region_uuid,
      coalesce(g.region,'Hors répertoire courant') AS region,g.district_uuid,
      coalesce(g.district,'Hors répertoire courant') AS district,g.district_name,g.health_area_uuid,
      coalesce(g.cscom,'Hors répertoire courant') AS cscom,g.cscom_name,NULL::text AS site_uuid,NULL::text AS site,NULL::text AS site_name,NULL::text AS supervision_area,
      CASE WHEN g.area_key IS NULL THEN 'Hors répertoire courant' ELSE 'Rattaché au répertoire courant' END AS attribution,
      s.pregnant,s.followup,s.anc,s.anc_no,s.sp1,s.sp3_month,s.facility,s.home,s.death,s.anc_referred,s.home_referred,
      CURRENT_TIMESTAMP AS calculated_at,
      (date_trunc('month',CURRENT_DATE)-interval '12 months')::date AS coverage_start,
      date_trunc('month',CURRENT_DATE)::date AS coverage_end
    FROM source s LEFT JOIN geography g ON g.area_key=s.entity_uuid
