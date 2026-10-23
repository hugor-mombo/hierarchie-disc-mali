WITH source AS (SELECT entity_uuid,reported_month,count(*)::bigint AS input_rows,sum(pregnant_ref) AS pregnant_ref,sum(pregnant_arrived) AS pregnant_arrived,sum(pregnant_not_completed) AS pregnant_not_completed,sum(malaria_ref) AS malaria_ref,sum(malaria_arrived) AS malaria_arrived,sum(danger_over5) AS danger_over5,sum(tb) AS tb FROM (SELECT s.chw_site_uuid AS entity_uuid,s.reported_month,(s.total_pregnant_women_referred)::numeric AS pregnant_ref,
(s.total_pregnant_women_reached_cscom)::numeric AS pregnant_arrived,
(s.total_pregnant_women_referred_not_completed)::numeric AS pregnant_not_completed,
(s.total_malaria_pregnant_women_referred)::numeric AS malaria_ref,
(s.total_malaria_pregnant_reached_cscom)::numeric AS malaria_arrived,
(coalesce(s.sign_danger_referred_male,0)+coalesce(s.sign_danger_referred_female,0))::numeric AS danger_over5,
(coalesce(s.suspicion_tb_referred_male,0)+coalesce(s.suspicion_tb_referred_female,0))::numeric AS tb FROM public.mv_over5_pregnant_malaria_superset s WHERE s.reported_month>=date_trunc('month',CURRENT_DATE)-interval '12 months' AND s.reported_month<date_trunc('month',CURRENT_DATE)) raw GROUP BY entity_uuid,reported_month), geography AS (SELECT * FROM public.mv_asc_ops_geography)
    SELECT s.entity_uuid,s.reported_month::date,s.input_rows,g.region_uuid,
      coalesce(g.region,'Hors répertoire courant') AS region,g.district_uuid,
      coalesce(g.district,'Hors répertoire courant') AS district,g.district_name,g.health_area_uuid,
      coalesce(g.cscom,'Hors répertoire courant') AS cscom,g.cscom_name,g.site_uuid,g.site,g.site_name,g.supervision_area,
      CASE WHEN g.site_uuid IS NULL THEN 'Hors répertoire courant' ELSE 'Rattaché au répertoire courant' END AS attribution,
      s.pregnant_ref,s.pregnant_arrived,s.pregnant_not_completed,s.malaria_ref,s.malaria_arrived,s.danger_over5,s.tb,
      CURRENT_TIMESTAMP AS calculated_at,
      (date_trunc('month',CURRENT_DATE)-interval '12 months')::date AS coverage_start,
      date_trunc('month',CURRENT_DATE)::date AS coverage_end
    FROM source s LEFT JOIN geography g ON g.site_uuid=s.entity_uuid
