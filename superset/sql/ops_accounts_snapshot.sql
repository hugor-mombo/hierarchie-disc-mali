-- Grain : un compte utilisateur ASC (ne pas assimiler comptes et personnes).
WITH users AS MATERIALIZED (
  SELECT doc->>'name' AS username,doc->>'contact_id' AS contact_uuid,
         doc->>'facility_id' AS site_uuid
  FROM public.couchdb_medic_users
  WHERE doc->>'type'='user' AND doc->'roles' @> '"chw"'::jsonb
    AND lower(coalesce(doc->>'name','')) NOT LIKE '%formation%'
    AND coalesce(doc->>'_deleted','false') <> 'true'
    AND coalesce(doc->>'disabled','false') <> 'true'
), personal AS MATERIALIZED (
  SELECT chw,max(reported) FILTER(WHERE reported<=CURRENT_TIMESTAMP) AS last_report,
         count(*) FILTER(WHERE reported>CURRENT_TIMESTAMP) AS future_reports
  FROM public.form_metadata
  WHERE chw IN (SELECT contact_uuid FROM users)
  GROUP BY chw
), site_activity AS MATERIALIZED (
  SELECT chw_area AS site_uuid,max(reported) AS last_site_report
  FROM public.form_metadata WHERE reported<=CURRENT_TIMESTAMP
    AND chw_area IN (SELECT site_uuid FROM public.mv_asc_ops_geography) GROUP BY chw_area
  UNION ALL
  SELECT chw AS site_uuid,max(reported) AS last_site_report
  FROM public.form_metadata WHERE reported<=CURRENT_TIMESTAMP
    AND chw IN (SELECT site_uuid FROM public.mv_asc_ops_geography) GROUP BY chw
), site_reports AS (
  SELECT site_uuid,max(last_site_report) AS last_site_report FROM site_activity GROUP BY site_uuid
)
SELECT u.username,u.contact_uuid,coalesce(nullif(c.doc->>'name',''),'Nom non renseigné') AS asc_name,
       c.doc->>'phone' AS phone,g.*,
       p.last_report AS last_personal_report,s.last_site_report,
       CURRENT_DATE-p.last_report::date AS days_without_report,
       coalesce(p.future_reports,0)::bigint AS future_reports,
       CASE WHEN c.doc IS NULL THEN 'Contact introuvable'
            WHEN c.doc#>>'{parent,_id}' IS DISTINCT FROM u.site_uuid
              THEN 'Rattachement contact / compte différent'
            ELSE 'Rattachement concordant' END AS contact_status,
       CURRENT_DATE AS reference_date,CURRENT_TIMESTAMP AS refreshed_at
FROM users u
JOIN public.mv_asc_ops_geography g ON g.site_uuid=u.site_uuid
LEFT JOIN LATERAL (
  SELECT doc FROM public.couchdb WHERE doc->>'_id'=u.contact_uuid LIMIT 1
) c ON true
LEFT JOIN personal p ON p.chw=u.contact_uuid
LEFT JOIN site_reports s ON s.site_uuid=u.site_uuid
