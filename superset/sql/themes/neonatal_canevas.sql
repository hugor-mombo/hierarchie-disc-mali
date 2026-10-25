WITH profiles AS (SELECT n.chw_site_id AS entity_uuid,n.reported_date::date AS reported_month,
 count(*)::numeric AS registered_profiles,
 count(*) FILTER(WHERE birth_certificate='yes')::numeric AS certificate_profiles,
 count(*) FILTER(WHERE birth_certificate='yes' OR declaration_within_the_legal_time='yes')::numeric AS civil_profiles
 FROM public.new_born_registration n WHERE n.reported_date>=date_trunc('month',CURRENT_DATE)-interval '12 months'
 AND n.reported_date<date_trunc('month',CURRENT_DATE)
 AND EXISTS(SELECT 1 FROM public.form_metadata f WHERE f.uuid=n.form_uuid AND f.reported<=CURRENT_TIMESTAMP)
 GROUP BY 1,2
), cases AS (WITH raw AS MATERIALIZED(SELECT p.uuid,p.patient_uuid,p.reported_by_parent AS site_uuid,coalesce(p.followup_date,p.reported)::date AS day,p.t_delivery_date,p.task_to_perform,p.orient_child_to_cscom,p.mother_alive,p.why_end_followup,p.g_new_born_repeat FROM public.formview_postnatal_followup p WHERE p.reported>=date_trunc('month',CURRENT_DATE)-interval '12 months' AND p.reported<=CURRENT_TIMESTAMP AND p.role='chw'),located AS(SELECT r.*,CASE WHEN t_delivery_date ~ '^(19|20)[0-9]{2}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$' THEN make_date(substring(t_delivery_date,1,4)::int,substring(t_delivery_date,6,2)::int,1)+(substring(t_delivery_date,9,2)::int-1) END AS birth FROM raw r),cases AS(SELECT site_uuid,patient_uuid,birth,date_trunc('month',birth)::date AS month,count(DISTINCT day) FILTER(WHERE day-birth BETWEEN 0 AND 7 AND task_to_perform='postnatal_followup') AS visit_days,bool_or(orient_child_to_cscom='yes') AS referred,bool_or(mother_alive='no' OR why_end_followup='mother_deceased') AS maternal_death FROM located WHERE nullif(btrim(patient_uuid),'') IS NOT NULL AND to_char(birth,'YYYY-MM-DD')=t_delivery_date AND birth>=date_trunc('month',CURRENT_DATE)-interval '12 months' AND birth<date_trunc('month',CURRENT_DATE) AND day>=birth AND day<=CURRENT_DATE GROUP BY 1,2,3,4) SELECT site_uuid AS entity_uuid,month AS reported_month,count(*)::numeric AS followed_cases,
 count(*) FILTER(WHERE visit_days>=3)::numeric AS three_visit_cases,
 count(*) FILTER(WHERE referred)::numeric AS referred_cases FROM cases GROUP BY 1,2), periods AS (
 SELECT entity_uuid,reported_month FROM profiles UNION SELECT entity_uuid,reported_month FROM cases)
 SELECT p.entity_uuid,p.reported_month,coalesce(n.registered_profiles,0) AS registered_profiles,
 coalesce(n.certificate_profiles,0) AS certificate_profiles,coalesce(n.civil_profiles,0) AS civil_profiles,
 coalesce(c.followed_cases,0) AS followed_cases,coalesce(c.three_visit_cases,0) AS three_visit_cases,
 coalesce(c.referred_cases,0) AS referred_cases FROM periods p
 LEFT JOIN profiles n ON n.entity_uuid IS NOT DISTINCT FROM p.entity_uuid AND n.reported_month=p.reported_month
 LEFT JOIN cases c ON c.entity_uuid IS NOT DISTINCT FROM p.entity_uuid AND c.reported_month=p.reported_month
