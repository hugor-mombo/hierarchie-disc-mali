WITH source AS (SELECT entity_uuid,reported_month,count(*)::bigint AS input_rows,sum(new_consult) AS new_consult,sum(old_consult) AS old_consult,sum(malaria_suspected) AS malaria_suspected,sum(malaria_simple) AS malaria_simple,sum(diarrhea) AS diarrhea,sum(pneumonia) AS pneumonia,sum(cough) AS cough,sum(danger_ref) AS danger_ref,sum(other_ref) AS other_ref FROM (SELECT s.chw_site_uuid AS entity_uuid,s.reported_month,(coalesce(s.new_healing_consultations_under_5_male,0)+coalesce(s.new_healing_consultations_under_5_female,0))::numeric AS new_consult,
(coalesce(s.old_healing_consultations_under_5_male,0)+coalesce(s.old_healing_consultations_under_5_female,0))::numeric AS old_consult,
(coalesce(s.suspicion_malaria_male_inf_1y,0)+coalesce(s.suspicion_malaria_male_sup_1y,0)+coalesce(s.suspicion_malaria_female_inf_1y,0)+coalesce(s.suspicion_malaria_female_sup_1y,0))::numeric AS malaria_suspected,
(coalesce(s.simple_malaria_male_inf_1y,0)+coalesce(s.simple_malaria_male_sup_1y,0)+coalesce(s.simple_malaria_female_inf_1y,0)+coalesce(s.simple_malaria_female_sup_1y,0))::numeric AS malaria_simple,
(coalesce(s.diarrhea_male_inf_1y,0)+coalesce(s.diarrhea_male_sup_1y,0)+coalesce(s.diarrhea_female_inf_1y,0)+coalesce(s.diarrhea_female_sup_1y,0))::numeric AS diarrhea,
(coalesce(s.pneumonia_male_inf_1y,0)+coalesce(s.pneumonia_male_sup_1y,0)+coalesce(s.pneumonia_female_inf_1y,0)+coalesce(s.pneumonia_female_sup_1y,0))::numeric AS pneumonia,
(coalesce(s.cough_cold_male_inf_1y,0)+coalesce(s.cough_cold_male_sup_1y,0)+coalesce(s.cough_cold_female_inf_1y,0)+coalesce(s.cough_cold_female_sup_1y,0))::numeric AS cough,
(coalesce(s.sign_danger_referred_male,0)+coalesce(s.sign_danger_referred_female,0))::numeric AS danger_ref,
(coalesce(s.other_male_referred_by_chw,0)+coalesce(s.other_female_referred_by_chw,0))::numeric AS other_ref FROM public.mv_pec_u5_indicators_shared s WHERE s.reported_month>=date_trunc('month',CURRENT_DATE)-interval '12 months' AND s.reported_month<date_trunc('month',CURRENT_DATE)) raw GROUP BY entity_uuid,reported_month), geography AS (SELECT * FROM public.mv_asc_ops_geography)
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
