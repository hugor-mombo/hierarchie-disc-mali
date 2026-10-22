-- La jointure reste virtuelle : ne pas créer de dépendance PostgreSQL sur
-- mv_asc_ops_accounts, remplacée de manière atomique par son propre minuteur.
SELECT t.*,a.region_uuid,a.region,a.district_uuid,a.health_area_uuid,
 a.district,a.cscom,a.site,a.site_uuid,a.site_name,a.district_name,a.cscom_name,
 a.supervision_area,a.asc_name,a.phone,a.contact_uuid,a.contact_status,
 a.refreshed_at AS directory_refreshed_at
FROM public.mv_asc_tasks_rollup t
JOIN public.mv_asc_ops_accounts a USING(username)
WHERE t.record_quality='Valide'
