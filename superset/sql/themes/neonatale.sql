WITH source AS (SELECT entity_uuid,reported_month,count(*)::bigint AS input_rows,sum(newborn) AS newborn,sum(three_visits) AS three_visits,sum(on_time) AS on_time,sum(civil) AS civil,sum(certificate) AS certificate,sum(referred) AS referred,sum(death24) AS death24,sum(home) AS home FROM (SELECT s.chw_site_uuid AS entity_uuid,s.reported_month,(s.nber_newborn)::numeric AS newborn,
(s.newborn_with_3_visit)::numeric AS three_visits,
(s.newborn_with_visits_on_time)::numeric AS on_time,
(s.newborn_declared_civil_status)::numeric AS civil,
(s.newborn_with_birth_certificate)::numeric AS certificate,
(s.newborn_referred)::numeric AS referred,
(s.newborn_died_in_24h)::numeric AS death24,
(s.newborn_mother_given_birth_at_home)::numeric AS home FROM public.mv_neonat_indicators_superset s WHERE s.reported_month>=date_trunc('month',CURRENT_DATE)-interval '12 months' AND s.reported_month<date_trunc('month',CURRENT_DATE)) raw GROUP BY entity_uuid,reported_month), geography AS (SELECT * FROM public.mv_asc_ops_geography)
    SELECT s.entity_uuid,s.reported_month::date,s.input_rows,g.region_uuid,
      coalesce(g.region,'Hors répertoire courant') AS region,g.district_uuid,
      coalesce(g.district,'Hors répertoire courant') AS district,g.district_name,g.health_area_uuid,
      coalesce(g.cscom,'Hors répertoire courant') AS cscom,g.cscom_name,g.site_uuid,g.site,g.site_name,g.supervision_area,
      CASE WHEN g.site_uuid IS NULL THEN 'Hors répertoire courant' ELSE 'Rattaché au répertoire courant' END AS attribution,
      s.newborn,s.three_visits,s.on_time,s.civil,s.certificate,s.referred,s.death24,s.home,
      CURRENT_TIMESTAMP AS calculated_at,
      (date_trunc('month',CURRENT_DATE)-interval '12 months')::date AS coverage_start,
      date_trunc('month',CURRENT_DATE)::date AS coverage_end
    FROM source s LEFT JOIN geography g ON g.site_uuid=s.entity_uuid
