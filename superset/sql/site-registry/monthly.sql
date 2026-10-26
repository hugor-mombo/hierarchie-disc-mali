-- Un UUID site × mois, y compris les sites créés après le mois (signalés, non comptés).
WITH periods AS (
 SELECT generate_series(date_trunc('month',CURRENT_DATE)-interval '13 months',
 date_trunc('month',CURRENT_DATE),interval '1 month')::date AS reported_month
), base AS (
 SELECT r.*,p.reported_month,
 CASE WHEN r.site_created_date IS NULL OR
 (r.site_created_date<p.reported_month+interval '1 month' AND r.site_created_date<=CURRENT_DATE)
 THEN 1 ELSE 0 END AS in_period,
 CASE WHEN r.has_eligible_asc=1 AND r.asc_site_created_date<p.reported_month+interval '1 month'
 AND r.asc_site_created_date<=CURRENT_DATE THEN 1 ELSE 0 END AS asc_in_period,
 coalesce(a.report_count,0) AS asc_report_count,
 s.has_visit_chw_site AS sd_visited,
 CASE WHEN s.chw_site_uuid IS NOT NULL THEN 1 ELSE 0 END AS sd_available,
 (SELECT max(refreshed_at) FROM public.mv_asc_v2_report_monthly) AS reports_calculated_at
 FROM public.v_disc_site_registry_labels_v1 r CROSS JOIN periods p
 LEFT JOIN public.mv_asc_v2_report_monthly a ON a.site_key=r.site_uuid
 AND a.reported_month=p.reported_month AND a.quality='attribue'
 LEFT JOIN public.mv_superset_sd_chw_monthly_status s ON s.chw_site_uuid=r.site_uuid
 AND s.reported_month=p.reported_month
)
SELECT *,CASE WHEN in_period=0 THEN 'Créé après la période ou date future'
 WHEN site_created_date IS NULL THEN 'Création inconnue · inclus provisoirement'
 WHEN asc_in_period=1 THEN 'Présent dans les périmètres ASC et SD'
 ELSE 'Inventaire DISC · hors périmètre ASC du mois' END AS scope_status
FROM base
