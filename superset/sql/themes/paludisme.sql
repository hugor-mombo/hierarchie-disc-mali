WITH source AS (SELECT entity_uuid,reported_month,count(*)::bigint AS input_rows,sum(fever) AS fever,sum(tested) AS tested,sum(positive) AS positive,sum(negative) AS negative,sum(pregnant) AS pregnant,sum(pregnant_cta) AS pregnant_cta,sum(other_cta) AS other_cta,sum(over5) AS over5,sum(over5_ref) AS over5_ref FROM (SELECT s.chw_site_uuid AS entity_uuid,s.reported_month,(s.total_fever_cases)::numeric AS fever,
(s.total_rdt_realized)::numeric AS tested,
(s.total_rdt_positive)::numeric AS positive,
(s.total_rdt_negative)::numeric AS negative,
(s.total_malaria_cases_pregnant_women)::numeric AS pregnant,
(s.malaria_cases_pregnant_treated_by_cta)::numeric AS pregnant_cta,
(s.malaria_cases_other_treated_by_cta)::numeric AS other_cta,
(s.total_malaria_cases_over5)::numeric AS over5,
(s.total_malaria_cases_over5_referred)::numeric AS over5_ref FROM public.mv_over5_pregnant_malaria_superset s WHERE s.reported_month>=date_trunc('month',CURRENT_DATE)-interval '12 months' AND s.reported_month<date_trunc('month',CURRENT_DATE)) raw GROUP BY entity_uuid,reported_month), geography AS (SELECT * FROM public.mv_asc_ops_geography)
    SELECT s.entity_uuid,s.reported_month::date,s.input_rows,g.region_uuid,
      coalesce(g.region,'Hors répertoire courant') AS region,g.district_uuid,
      coalesce(g.district,'Hors répertoire courant') AS district,g.district_name,g.health_area_uuid,
      coalesce(g.cscom,'Hors répertoire courant') AS cscom,g.cscom_name,g.site_uuid,g.site,g.site_name,g.supervision_area,
      CASE WHEN g.site_uuid IS NULL THEN 'Hors répertoire courant' ELSE 'Rattaché au répertoire courant' END AS attribution,
      s.fever,s.tested,s.positive,s.negative,s.pregnant,s.pregnant_cta,s.other_cta,s.over5,s.over5_ref,
      CURRENT_TIMESTAMP AS calculated_at,
      (date_trunc('month',CURRENT_DATE)-interval '12 months')::date AS coverage_start,
      date_trunc('month',CURRENT_DATE)::date AS coverage_end
    FROM source s LEFT JOIN geography g ON g.site_uuid=s.entity_uuid
