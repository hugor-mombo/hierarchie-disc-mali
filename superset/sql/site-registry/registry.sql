-- Inventaire DISC courant, sans supprimer les sites sans contact ASC éligible.
-- Les noms suspects sont des signaux à examiner, pas des statuts de fermeture.
SELECT p.chw_site_uuid AS site_uuid,p.chw_site AS site_name,
 p.region_uuid,coalesce(p.region,'Région non renseignée') AS region,
 p.district_uuid,p.district AS district_name,
 p.health_area_uuid,p.health_area AS cscom_name,
 p.supervisor_area_uuid,p.supervisor_area AS zone_name,
 m.reported::date AS site_created_date,
 h.reported_date AS asc_site_created_date,
 CASE WHEN h.chw_site_uuid IS NOT NULL THEN 1 ELSE 0 END AS has_eligible_asc,
 CASE WHEN h.chw_site_uuid IS NULL THEN a.contact_count END AS contact_count,
 CASE WHEN h.chw_site_uuid IS NULL THEN a.training_contacts END AS training_contacts,
 CASE WHEN h.chw_site_uuid IS NULL THEN a.missing_username_contacts END AS missing_username_contacts,
 CASE WHEN p.chw_site LIKE '%zz%' OR p.chw_site ~* '\sNE$' THEN 1 ELSE 0 END AS name_flag,
 CASE WHEN h.chw_site_uuid IS NOT NULL THEN 'Dans la cohorte ASC'
      WHEN a.contact_count=0 THEN 'Sans contact ASC dans le relevé courant'
      WHEN p.chw_site LIKE '%zz%' OR p.chw_site ~* '\sNE$' THEN 'Nom exclu par la règle ASC (zz / NE)'
      WHEN a.training_contacts=a.contact_count THEN 'Contacts de formation uniquement'
      WHEN a.missing_username_contacts=a.contact_count THEN 'Identifiant ASC non renseigné'
      ELSE 'Contact présent · autre exclusion ASC à examiner' END AS contact_status,
 p.snapshot_date AS portfolio_snapshot_date,CURRENT_TIMESTAMP AS calculated_at
FROM public.mv_superset_sd_portfolio p
LEFT JOIN public.contactview_metadata m ON m.uuid=p.chw_site_uuid
LEFT JOIN public.mv_chw_site_hierarchy_reporting h ON h.chw_site_uuid=p.chw_site_uuid
LEFT JOIN LATERAL (
 SELECT count(*) AS contact_count,
 count(*) FILTER(WHERE b.doc->>'username' LIKE '%formation%') AS training_contacts,
 count(*) FILTER(WHERE b.doc->>'username' IS NULL) AS missing_username_contacts
 FROM public.contactview_metadata c
 LEFT JOIN LATERAL (
  SELECT doc FROM public.couchdb WHERE doc->>'_id'=c.uuid
   AND h.chw_site_uuid IS NULL LIMIT 1
 ) b ON TRUE
 WHERE h.chw_site_uuid IS NULL
 AND c.parent_uuid=p.chw_site_uuid AND c.contact_type='c62_chw'
) a ON TRUE
