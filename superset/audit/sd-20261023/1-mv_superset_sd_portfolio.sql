-- Définition en lecture seule relevée le 23 octobre 2026. Référence d’audit, ne pas exécuter comme migration.
 WITH places AS MATERIALIZED (
         SELECT contactview_metadata.uuid,
            contactview_metadata.name,
            contactview_metadata.contact_type,
            contactview_metadata.parent_uuid
           FROM contactview_metadata
          WHERE contactview_metadata.contact_type = ANY (ARRAY['c10_central'::text, 'c20_region'::text, 'c30_district'::text, 'c40_health_area'::text, 'c50_supervision_area'::text, 'c60_chw_site'::text])
        )
 SELECT c.uuid AS central_uuid,
    c.name AS central,
    r.uuid AS region_uuid,
    r.name AS region,
    d.uuid AS district_uuid,
    d.name AS district,
    h.uuid AS health_area_uuid,
    h.name AS health_area,
    z.uuid AS supervisor_area_uuid,
    z.name AS supervisor_area,
    s.uuid AS chw_site_uuid,
    s.name AS chw_site,
    COALESCE(a.supervisor_key, 'unassigned:'::text || s.uuid) AS supervisor_key,
    a.supervisor_uuid,
    a.supervisor_username,
    a.supervisor_name,
    a.supervisor_first_name,
    a.supervisor_last_name,
    a.supervisor_phone,
    a.supervisor_email,
    a.supervisor_sex,
    COALESCE(a.assignment_status, 'unassigned'::text) AS assignment_status,
    a.assignment_source,
    a.assignment_candidates,
    g.first_geolocation_date,
    g.last_geolocation_date,
    COALESCE(g.geolocation_report_count, 0::bigint) AS geolocation_report_count,
        CASE
            WHEN g.first_geolocation_date IS NOT NULL THEN 1
            ELSE 0
        END AS is_geolocated,
    CURRENT_DATE AS snapshot_date
   FROM places s
     LEFT JOIN places z ON z.uuid = s.parent_uuid AND z.contact_type = 'c50_supervision_area'::text
     LEFT JOIN places h ON h.uuid = z.parent_uuid AND h.contact_type = 'c40_health_area'::text
     LEFT JOIN places d ON d.uuid = h.parent_uuid AND d.contact_type = 'c30_district'::text
     LEFT JOIN places r ON r.uuid = d.parent_uuid AND r.contact_type = 'c20_region'::text
     LEFT JOIN places c ON c.uuid = r.parent_uuid AND c.contact_type = 'c10_central'::text
     LEFT JOIN mv_superset_sd_zone_assignments a ON a.supervisor_area_uuid = z.uuid
     LEFT JOIN mv_superset_sd_site_geolocation g ON g.chw_site_uuid = s.uuid
  WHERE s.contact_type = 'c60_chw_site'::text;