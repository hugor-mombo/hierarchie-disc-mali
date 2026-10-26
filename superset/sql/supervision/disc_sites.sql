-- Même géographie et même date de création que les compteurs communs ASC / SD.
SELECT s.reported_month,extract(year FROM s.reported_month)::integer AS year,
 g.region_uuid,g.region,g.district_uuid,g.district_name,g.district,
 g.health_area_uuid,g.cscom_name,g.cscom,
 g.supervisor_area_uuid,g.zone_name,g.zone,
 g.site_uuid,g.site_name,s.supervisor_uuid,s.supervisor_name,s.assignment_status,
 CASE s.assignment_status WHEN 'assigned' THEN 'Affectation identifiée' WHEN 'conflict' THEN 'Affectation en conflit' ELSE 'Affectation non identifiée' END AS assignment_label,
 s.visit_chw_site_reports AS site_visits,
 s.visit_community_without_chw_reports AS community_visits,
 s.individual_feedback_reports AS feedbacks,
 s.has_visit_chw_site AS visited,s.received_sd_three_forms AS three_forms,
 s.received_sd_complete_quota AS quota,
 CASE WHEN s.received_sd_complete_quota=1 THEN 'Quota complet'
      WHEN s.visit_chw_site_reports=0 AND s.visit_community_without_chw_reports=0 AND s.individual_feedback_reports=0 THEN 'Aucun des trois formulaires'
      ELSE 'Quota incomplet' END AS quota_status,
 greatest(1-s.visit_chw_site_reports,0) AS missing_site_visits,
 greatest(5-s.visit_community_without_chw_reports,0) AS missing_community_visits,
 greatest(1-s.individual_feedback_reports,0) AS missing_feedbacks,s.last_activity_at
FROM public.mv_superset_sd_chw_monthly_status s
JOIN public.v_disc_site_registry_labels_v1 g ON g.site_uuid=s.chw_site_uuid
WHERE s.reported_month<date_trunc('month',CURRENT_DATE)
 AND (g.site_created_date IS NULL OR
 (g.site_created_date<s.reported_month+interval '1 month' AND g.site_created_date<=CURRENT_DATE))
