WITH source AS (SELECT entity_uuid,reported_month,count(*)::bigint AS input_rows,sum(new_consult) AS new_consult,sum(old_consult) AS old_consult,sum(malaria_suspected) AS malaria_suspected,sum(malaria_simple) AS malaria_simple,sum(diarrhea) AS diarrhea,sum(pneumonia) AS pneumonia,sum(cough) AS cough,sum(danger_ref) AS danger_ref,sum(other_ref) AS other_ref FROM (WITH corrected AS (-- Native diagnosis flag, not a reconstruction requiring prior CTA history.
-- Only site/month counts leave this CTE; patient identifiers remain inside PostgreSQL.
WITH raw AS MATERIALIZED (
 SELECT uuid AS report_uuid,nullif(btrim(patient_uuid),'') AS patient_uuid,
 nullif(btrim(reported_by_parent),'') AS site_uuid,reported AS submitted_at,
 coalesce(s_reported_date,reported)::date AS consultation_day,
 lower(nullif(btrim(has_malaria),'')) AS malaria_classification,
 CASE WHEN length(patient_age_in_years)<12 AND patient_age_in_years ~ '^[0-9]+([.][0-9]+)?$'
 THEN patient_age_in_years::numeric END AS age_years
 FROM public.formview_patient_assessment_under_5
 WHERE reported>=date_trunc('month',CURRENT_DATE)-interval '12 months'
 AND reported<=CURRENT_TIMESTAMP
), ranked AS (
 SELECT *,dense_rank() OVER(PARTITION BY coalesce('patient:'||patient_uuid,'report:'||report_uuid),consultation_day
 ORDER BY submitted_at DESC) AS recency,
 count(*) OVER(PARTITION BY coalesce('patient:'||patient_uuid,'report:'||report_uuid),consultation_day,submitted_at) AS latest_ties
 FROM raw
 WHERE consultation_day>=date_trunc('month',CURRENT_DATE)-interval '12 months'
 AND consultation_day<date_trunc('month',CURRENT_DATE)
)
SELECT site_uuid AS entity_uuid,date_trunc('month',consultation_day)::date AS reported_month,
 count(*) FILTER(WHERE malaria_classification='yes' AND age_years>=0 AND age_years<5)::numeric AS malaria_simple
FROM ranked WHERE recency=1 AND latest_ties=1
GROUP BY 1,2
), legacy AS (
          SELECT s.chw_site_uuid AS entity_uuid,s.reported_month,(coalesce(s.new_healing_consultations_under_5_male,0)+coalesce(s.new_healing_consultations_under_5_female,0))::numeric AS new_consult,
(coalesce(s.old_healing_consultations_under_5_male,0)+coalesce(s.old_healing_consultations_under_5_female,0))::numeric AS old_consult,
(coalesce(s.suspicion_malaria_male_inf_1y,0)+coalesce(s.suspicion_malaria_male_sup_1y,0)+coalesce(s.suspicion_malaria_female_inf_1y,0)+coalesce(s.suspicion_malaria_female_sup_1y,0))::numeric AS malaria_suspected,
(coalesce(s.diarrhea_male_inf_1y,0)+coalesce(s.diarrhea_male_sup_1y,0)+coalesce(s.diarrhea_female_inf_1y,0)+coalesce(s.diarrhea_female_sup_1y,0))::numeric AS diarrhea,
(coalesce(s.pneumonia_male_inf_1y,0)+coalesce(s.pneumonia_male_sup_1y,0)+coalesce(s.pneumonia_female_inf_1y,0)+coalesce(s.pneumonia_female_sup_1y,0))::numeric AS pneumonia,
(coalesce(s.cough_cold_male_inf_1y,0)+coalesce(s.cough_cold_male_sup_1y,0)+coalesce(s.cough_cold_female_inf_1y,0)+coalesce(s.cough_cold_female_sup_1y,0))::numeric AS cough,
(coalesce(s.sign_danger_referred_male,0)+coalesce(s.sign_danger_referred_female,0))::numeric AS danger_ref,
(coalesce(s.other_male_referred_by_chw,0)+coalesce(s.other_female_referred_by_chw,0))::numeric AS other_ref
          FROM public.mv_pec_u5_indicators_shared s WHERE s.reported_month>=date_trunc('month',CURRENT_DATE)-interval '12 months' AND s.reported_month<date_trunc('month',CURRENT_DATE)), periods AS (
          SELECT entity_uuid,reported_month FROM corrected UNION SELECT entity_uuid,reported_month FROM legacy)
          SELECT p.entity_uuid,p.reported_month,s.new_consult::numeric AS new_consult,s.old_consult::numeric AS old_consult,s.malaria_suspected::numeric AS malaria_suspected,coalesce(c.malaria_simple,0)::numeric AS malaria_simple,s.diarrhea::numeric AS diarrhea,s.pneumonia::numeric AS pneumonia,s.cough::numeric AS cough,s.danger_ref::numeric AS danger_ref,s.other_ref::numeric AS other_ref FROM periods p
          LEFT JOIN legacy s ON s.entity_uuid IS NOT DISTINCT FROM p.entity_uuid AND s.reported_month=p.reported_month
          LEFT JOIN corrected c ON c.entity_uuid IS NOT DISTINCT FROM p.entity_uuid AND c.reported_month=p.reported_month) raw GROUP BY entity_uuid,reported_month), geography AS (SELECT * FROM public.mv_asc_ops_geography)
    SELECT s.entity_uuid,s.reported_month::date,s.input_rows,g.region_uuid,
      coalesce(g.region,'Hors répertoire courant') AS region,g.district_uuid,
      coalesce(g.district,'Hors répertoire courant') AS district,g.district_name,g.health_area_uuid,
      coalesce(g.cscom,'Hors répertoire courant') AS cscom,g.cscom_name,g.site_uuid,g.site,g.site_name,g.supervision_area,
      CASE WHEN g.site_uuid IS NULL THEN 'Hors répertoire courant' ELSE 'Rattaché au répertoire courant' END AS attribution,
      s.new_consult,s.old_consult,s.malaria_suspected,s.malaria_simple,s.diarrhea,s.pneumonia,s.cough,s.danger_ref,s.other_ref,
      CURRENT_TIMESTAMP AS calculated_at,
      (date_trunc('month',CURRENT_DATE)-interval '12 months')::date AS coverage_start,
      date_trunc('month',CURRENT_DATE)::date AS coverage_end
    FROM source s LEFT JOIN geography g ON g.site_uuid=s.entity_uuid
