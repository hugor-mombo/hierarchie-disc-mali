SELECT reported_month, extract(year FROM reported_month)::integer AS year, region_uuid, region,
 district_uuid, district AS district_name,
 concat_ws(' · ',district,region) AS district,
 supervisor_area_uuid, supervisor_area AS zone_name,
 concat_ws(' · ',supervisor_area,district,region) AS zone,
 supervisor_contact_id, supervisor_name,
 total_chw_sites AS eligible_site_months,
 total_curative_home_visits AS curative_visits,
 number_rdt_done AS rdt_done,
 number_rdt_correctly_done AS rdt_correct
FROM public.mv_superset_sd_monthly_indicators
WHERE reported_month < date_trunc('month',CURRENT_DATE)
