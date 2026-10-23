WITH source AS (SELECT entity_uuid,reported_month,count(*)::bigint AS input_rows,sum(pregnant) AS pregnant,sum(followup) AS followup,sum(anc) AS anc,sum(anc_no) AS anc_no,sum(sp1) AS sp1,sum(sp3_month) AS sp3_month,sum(facility) AS facility,sum(home) AS home,sum(death) AS death FROM (WITH corrected AS (-- Le parent du contact est un ménage : dédupliquer les patientes à la place.
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
          SELECT p.entity_uuid,p.reported_month,c.pregnant::numeric AS pregnant,s.nbr_pregnant_followup::numeric AS followup,s.nber_patient_been_to_anc::numeric AS anc,s.cpn_refered::numeric AS anc_no,s.nber_sp1_given::numeric AS sp1,s.women_received_at_least_3_sp::numeric AS sp3_month,s.hf_delivery::numeric AS facility,s.home_delivery::numeric AS home,s.number_maternal_deaths::numeric AS death FROM periods p
          LEFT JOIN legacy s ON s.entity_uuid=p.entity_uuid AND s.reported_month=p.reported_month
          LEFT JOIN corrected c ON c.entity_uuid=p.entity_uuid AND c.reported_month=p.reported_month) raw GROUP BY entity_uuid,reported_month), geography AS (SELECT DISTINCT region_uuid,region,district_uuid,district,district_name,
        health_area_uuid,cscom,cscom_name,concat(coalesce(region_uuid,'?'),'|',coalesce(district_uuid,'?'),'|',coalesce(health_area_uuid,'?')) AS area_key FROM public.mv_asc_ops_geography)
    SELECT s.entity_uuid,s.reported_month::date,s.input_rows,g.region_uuid,
      coalesce(g.region,'Hors répertoire courant') AS region,g.district_uuid,
      coalesce(g.district,'Hors répertoire courant') AS district,g.district_name,g.health_area_uuid,
      coalesce(g.cscom,'Hors répertoire courant') AS cscom,g.cscom_name,NULL::text AS site_uuid,NULL::text AS site,NULL::text AS site_name,NULL::text AS supervision_area,
      CASE WHEN g.area_key IS NULL THEN 'Hors répertoire courant' ELSE 'Rattaché au répertoire courant' END AS attribution,
      s.pregnant,s.followup,s.anc,s.anc_no,s.sp1,s.sp3_month,s.facility,s.home,s.death,
      CURRENT_TIMESTAMP AS calculated_at,
      (date_trunc('month',CURRENT_DATE)-interval '12 months')::date AS coverage_start,
      date_trunc('month',CURRENT_DATE)::date AS coverage_end
    FROM source s LEFT JOIN geography g ON g.area_key=s.entity_uuid
