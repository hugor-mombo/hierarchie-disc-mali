WITH source AS (SELECT entity_uuid,reported_month,count(*)::bigint AS input_rows,sum(up_to_date) AS up_to_date,sum(at_23m) AS at_23m,sum(found) AS found,sum(referred) AS referred,sum(historic_zero) AS historic_zero,sum(observed_under2) AS observed_under2,sum(observed_up_to_date) AS observed_up_to_date,sum(observed_at23) AS observed_at23,sum(observed_zero12_23) AS observed_zero12_23 FROM (WITH corrected AS (WITH raw AS MATERIALIZED (
 SELECT uuid,nullif(btrim(patient_uuid),'') AS patient_uuid,reported_by_parent AS site_uuid,reported,
 CASE WHEN patient_age_in_months ~ '^[0-9]+([.][0-9]+)?$' AND length(patient_age_in_months)<12 THEN patient_age_in_months::numeric END AS age_months,
 vaccination_up_to_date,vaccination_already_up_to_date,is_vaccine_penta_1,already_is_vaccine_penta_1
 FROM public.formview_child_longitudinal_followup_1_24 WHERE reported>=date_trunc('month',CURRENT_DATE)-interval '12 months' AND reported<date_trunc('month',CURRENT_DATE)
), ranked AS (
 SELECT *,dense_rank() OVER(PARTITION BY patient_uuid,date_trunc('month',reported) ORDER BY reported DESC) AS recency,
 count(*) OVER(PARTITION BY patient_uuid,reported) AS ties FROM raw WHERE patient_uuid IS NOT NULL
)
SELECT site_uuid AS entity_uuid,date_trunc('month',reported)::date AS reported_month,
 count(*)::numeric AS observed_under2,
 count(*) FILTER(WHERE vaccination_up_to_date='yes' OR vaccination_already_up_to_date='yes')::numeric AS observed_up_to_date,
 count(*) FILTER(WHERE age_months=23 AND (vaccination_up_to_date='yes' OR vaccination_already_up_to_date='yes'))::numeric AS observed_at23,
 count(*) FILTER(WHERE age_months>=12 AND is_vaccine_penta_1='no' AND coalesce(already_is_vaccine_penta_1,'')<>'yes')::numeric AS observed_zero12_23
 FROM ranked WHERE recency=1 AND ties=1 AND age_months>=0 AND age_months<24 GROUP BY 1,2
), legacy AS (SELECT s.chw_site_uuid AS entity_uuid,s.reported_month,(s.nbr_vaccinated_up_to_date)::numeric AS up_to_date,
(s.fully_vaccinated_23m)::numeric AS at_23m,
(s.nbr_children_found_for_vac)::numeric AS found,
(s.nbr_children_referred_to_vaccine)::numeric AS referred,
(s.nbr_zero_dose)::numeric AS historic_zero FROM public.mv_vaccination_indicators_shared s WHERE s.reported_month>=date_trunc('month',CURRENT_DATE)-interval '12 months' AND s.reported_month<date_trunc('month',CURRENT_DATE)), periods AS (SELECT entity_uuid,reported_month FROM corrected UNION SELECT entity_uuid,reported_month FROM legacy) SELECT p.entity_uuid,p.reported_month,s.up_to_date::numeric AS up_to_date,s.at_23m::numeric AS at_23m,s.found::numeric AS found,s.referred::numeric AS referred,s.historic_zero::numeric AS historic_zero,coalesce(c.observed_under2,0)::numeric AS observed_under2,coalesce(c.observed_up_to_date,0)::numeric AS observed_up_to_date,coalesce(c.observed_at23,0)::numeric AS observed_at23,coalesce(c.observed_zero12_23,0)::numeric AS observed_zero12_23 FROM periods p LEFT JOIN legacy s ON s.entity_uuid IS NOT DISTINCT FROM p.entity_uuid AND s.reported_month=p.reported_month LEFT JOIN corrected c ON c.entity_uuid IS NOT DISTINCT FROM p.entity_uuid AND c.reported_month=p.reported_month) raw GROUP BY entity_uuid,reported_month), geography AS (SELECT * FROM public.mv_asc_ops_geography)
    SELECT s.entity_uuid,s.reported_month::date,s.input_rows,g.region_uuid,
      coalesce(g.region,'Hors répertoire courant') AS region,g.district_uuid,
      coalesce(g.district,'Hors répertoire courant') AS district,g.district_name,g.health_area_uuid,
      coalesce(g.cscom,'Hors répertoire courant') AS cscom,g.cscom_name,g.site_uuid,g.site,g.site_name,g.supervision_area,
      CASE WHEN g.site_uuid IS NULL THEN 'Hors répertoire courant' ELSE 'Rattaché au répertoire courant' END AS attribution,
      s.up_to_date,s.at_23m,s.found,s.referred,s.historic_zero,s.observed_under2,s.observed_up_to_date,s.observed_at23,s.observed_zero12_23,
      CURRENT_TIMESTAMP AS calculated_at,
      (date_trunc('month',CURRENT_DATE)-interval '12 months')::date AS coverage_start,
      date_trunc('month',CURRENT_DATE)::date AS coverage_end
    FROM source s LEFT JOIN geography g ON g.site_uuid=s.entity_uuid
