WITH raw AS MATERIALIZED (
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
