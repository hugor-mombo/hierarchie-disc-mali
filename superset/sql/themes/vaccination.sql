WITH source AS (SELECT entity_uuid,reported_month,count(*)::bigint AS input_rows,sum(up_to_date) AS up_to_date,sum(at_23m) AS at_23m,sum(found) AS found,sum(referred) AS referred,sum(historic_zero) AS historic_zero FROM (SELECT s.chw_site_uuid AS entity_uuid,s.reported_month,(s.nbr_vaccinated_up_to_date)::numeric AS up_to_date,
(s.fully_vaccinated_23m)::numeric AS at_23m,
(s.nbr_children_found_for_vac)::numeric AS found,
(s.nbr_children_referred_to_vaccine)::numeric AS referred,
(s.nbr_zero_dose)::numeric AS historic_zero FROM public.mv_vaccination_indicators_shared s WHERE s.reported_month>=date_trunc('month',CURRENT_DATE)-interval '12 months' AND s.reported_month<date_trunc('month',CURRENT_DATE)) raw GROUP BY entity_uuid,reported_month), geography AS (SELECT * FROM public.mv_asc_ops_geography)
    SELECT s.entity_uuid,s.reported_month::date,s.input_rows,g.region_uuid,
      coalesce(g.region,'Hors répertoire courant') AS region,g.district_uuid,
      coalesce(g.district,'Hors répertoire courant') AS district,g.district_name,g.health_area_uuid,
      coalesce(g.cscom,'Hors répertoire courant') AS cscom,g.cscom_name,g.site_uuid,g.site,g.site_name,g.supervision_area,
      CASE WHEN g.site_uuid IS NULL THEN 'Hors répertoire courant' ELSE 'Rattaché au répertoire courant' END AS attribution,
      s.up_to_date,s.at_23m,s.found,s.referred,s.historic_zero,
      CURRENT_TIMESTAMP AS calculated_at,
      (date_trunc('month',CURRENT_DATE)-interval '12 months')::date AS coverage_start,
      date_trunc('month',CURRENT_DATE)::date AS coverage_end
    FROM source s LEFT JOIN geography g ON g.site_uuid=s.entity_uuid
