-- Native diagnosis flag, not a reconstruction requiring prior CTA history.
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
