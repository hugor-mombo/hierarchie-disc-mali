SELECT reported_month, extract(year FROM reported_month)::integer AS year, region_uuid, region,
 district_uuid, district AS district_name,
 concat_ws(' · ',district,region) AS district,
 health_area_uuid, health_area AS cscom_name,
 concat_ws(' · ',health_area,district,region) AS cscom,
 supervisor_area_uuid, supervisor_area AS zone_name,
 concat_ws(' · ',supervisor_area,health_area,district,region) AS zone,
 chw_site_uuid AS site_uuid, chw_site AS site_name,
 supervisor_uuid, supervisor_name, assignment_status,
 visit_chw_site_reports AS site_visits,
 visit_community_without_chw_reports AS community_visits,
 individual_feedback_reports AS feedbacks,
 has_visit_chw_site AS visited,
 received_sd_three_forms AS three_forms,
 received_sd_complete_quota AS quota,
 CASE WHEN received_sd_complete_quota=1 THEN 'Quota complet'
      WHEN visit_chw_site_reports=0 AND visit_community_without_chw_reports=0 AND individual_feedback_reports=0 THEN 'Aucun des trois formulaires'
      ELSE 'Quota incomplet' END AS quota_status,
 greatest(1-visit_chw_site_reports,0) AS missing_site_visits,
 greatest(5-visit_community_without_chw_reports,0) AS missing_community_visits,
 greatest(1-individual_feedback_reports,0) AS missing_feedbacks,
 last_activity_at
FROM public.mv_superset_sd_chw_monthly_status
WHERE reported_month < date_trunc('month',CURRENT_DATE)
