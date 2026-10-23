-- Le parent du contact est un ménage : dédupliquer les patientes à la place.
WITH reports AS (
 SELECT patient_uuid,reported,reported_by_parent FROM public.formview_pregnancy_registration
 WHERE pregnancy_confirmed='yes' AND reported>=date_trunc('month',CURRENT_DATE)-interval '12 months'
  AND reported<date_trunc('month',CURRENT_DATE) AND nullif(patient_uuid,'') IS NOT NULL
 UNION ALL
 SELECT patient_uuid,reported,reported_by_parent FROM public.formview_pregnancy_confirmation
 WHERE pregnancy_confirmed='yes' AND reported>=date_trunc('month',CURRENT_DATE)-interval '12 months'
  AND reported<date_trunc('month',CURRENT_DATE) AND nullif(patient_uuid,'') IS NOT NULL
)
SELECT concat(coalesce(g.region_uuid,'?'),'|',coalesce(g.district_uuid,'?'),'|',coalesce(g.health_area_uuid,'?')) AS entity_uuid,
 date_trunc('month',r.reported)::date AS reported_month,count(DISTINCT r.patient_uuid)::numeric AS pregnant
FROM reports r JOIN public.mv_asc_ops_geography g ON g.site_uuid=r.reported_by_parent
GROUP BY 1,2
