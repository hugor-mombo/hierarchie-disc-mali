SELECT region_uuid,region,district_uuid,district AS district_name,
 concat_ws(' · ',district,region) AS district,health_area_uuid,health_area AS cscom_name,
 concat_ws(' · ',health_area,district,region) AS cscom,supervisor_area_uuid,supervisor_area AS zone_name,
 concat_ws(' · ',supervisor_area,health_area,district,region) AS zone,
 chw_site_uuid AS site_uuid,chw_site AS site_name,reported_month,
 CURRENT_TIMESTAMP AS calculated_at,supervisor_uuid,supervisor_name,assignment_status,
 CASE assignment_status WHEN 'assigned' THEN 'Affectation identifiée' WHEN 'conflict' THEN 'Affectation en conflit' ELSE 'Affectation non identifiée' END AS assignment_label,
 received_sd_complete_quota::bigint AS quota,has_visit_chw_site::bigint AS visited,
 visit_chw_site_reports::bigint AS site_visits,visit_community_without_chw_reports::bigint AS community_visits,
 individual_feedback_reports::bigint AS feedbacks
 FROM public.mv_superset_sd_chw_monthly_status
 WHERE reported_month<date_trunc('month',CURRENT_DATE)
