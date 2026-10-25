-- Native diagnosis flag, not a reconstruction requiring prior CTA history.
-- Only site/month counts leave this CTE; patient identifiers remain inside PostgreSQL.
WITH raw AS MATERIALIZED (
 SELECT uuid AS report_uuid,nullif(btrim(patient_uuid),'') AS patient_uuid,
 nullif(btrim(reported_by_parent),'') AS site_uuid,reported AS submitted_at,
 coalesce(s_reported_date,reported)::date AS consultation_day,
 has_fever,lower(nullif(btrim(has_malaria),'')) AS malaria_classification,
 lower(nullif(btrim(has_malaria_suspicion),'')) AS presumed_classification,
 lower(nullif(btrim(tdr_result),'')) AS rdt_result,
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
 count(*)::numeric AS consult_native,
 count(*) FILTER(WHERE has_fever='yes')::numeric AS fever_native,
 count(*) FILTER(WHERE malaria_classification='yes' AND rdt_result='positive')::numeric AS malaria_simple,
 count(*) FILTER(WHERE rdt_result IN ('positive','negative') OR (presumed_classification='yes' AND rdt_result IS NULL))::numeric AS malaria_suspected,
 count(*) FILTER(WHERE rdt_result IN ('positive','negative'))::numeric AS malaria_tested,
 count(*) FILTER(WHERE rdt_result='positive')::numeric AS malaria_positive,
 count(*) FILTER(WHERE rdt_result='negative')::numeric AS malaria_negative,
 count(*) FILTER(WHERE presumed_classification='yes' AND rdt_result IS NULL)::numeric AS malaria_presumed,
 count(*) FILTER(WHERE (malaria_classification='yes' AND rdt_result IS DISTINCT FROM 'positive')
 OR (presumed_classification='yes' AND rdt_result IS NOT NULL)
 OR (rdt_result IS NOT NULL AND rdt_result NOT IN ('positive','negative')))::numeric AS malaria_conflicts
FROM ranked WHERE recency=1 AND latest_ties=1 AND age_years>=0 AND age_years<5
GROUP BY 1,2
