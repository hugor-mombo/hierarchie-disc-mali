SELECT reported_month, extract(year FROM reported_month)::integer AS year, region_uuid, region,
 district_uuid, district AS district_name,
 concat_ws(' · ',district,region) AS district,
 supervisor_area_uuid, supervisor_area AS zone_name,
 concat_ws(' · ',supervisor_area,district,region) AS zone,
 supervisor_contact_id, supervisor_name,
 numerator AS quota_site_months, denominator AS eligible_site_months,
 total_chw_sites_all AS known_site_months,
 active_sites_with_chw_visit AS visited_site_months,
 inactive_sites_with_all_steps AS inactive_quota,
 sites_without_creation_date AS unknown_creation,
 supervisions_with_chw AS site_visits,
 supervisions_without_chw AS community_visits,
 individual_meetings AS feedbacks
FROM public.mv_superset_sd_monthly_supervision_2019_2025
WHERE reported_month < date_trunc('month',CURRENT_DATE)
