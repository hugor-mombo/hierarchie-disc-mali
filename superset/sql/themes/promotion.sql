WITH source AS (SELECT entity_uuid,reported_month,count(*)::bigint AS input_rows,sum(communications) AS communications,sum(promotion_visits) AS promotion_visits,sum(talks) AS talks,sum(men) AS men,sum(women) AS women,sum(theme_malaria) AS theme_malaria,sum(theme_vaccination) AS theme_vaccination,sum(theme_hiv) AS theme_hiv,sum(theme_tuberculosis) AS theme_tuberculosis,sum(theme_nutrition) AS theme_nutrition,sum(theme_wash) AS theme_wash,sum(theme_family_planning) AS theme_family_planning,sum(theme_anc) AS theme_anc,sum(theme_ira) AS theme_ira,sum(theme_diarrhea) AS theme_diarrhea FROM (WITH activity AS (-- Lecture bornée des rapports uniques, via les index existants de métadonnées et d’identifiant CouchDB.
-- Aucun tri/dédoublonnage sur l'identifiant du contact : plusieurs activités du même jour sont distinctes.
WITH eligible AS MATERIALIZED (
 SELECT uuid,reported FROM public.form_metadata
 WHERE formname='communication'
  AND reported>=date_trunc('month',CURRENT_DATE)-interval '12 months'
  AND reported<=CURRENT_TIMESTAMP
), fields AS MATERIALIZED (
 SELECT e.uuid,e.reported,
  d.doc #>> '{contact,parent,_id}' AS chw_site_uuid,
  coalesce(to_timestamp(nullif(d.doc #>> '{fields,g_evaluation,done_date}',''),'YYYY-MM-DD HH24:MI:SS')::date,e.reported::date) AS activity_date,
  d.doc #>> '{fields,g_activity,activity_type}' AS activity_type,
  d.doc #>> '{fields,inputs,user,role}' AS role,
  concat_ws(' ',d.doc #>> '{fields,g_theme,g_discuss_theme,discussed_themes}',
   d.doc #>> '{fields,g_theme,g_discuss_theme,discussed_themes_vad}',
   d.doc #>> '{fields,g_theme,g_discuss_theme,discussed_themes_other_type}',
   d.doc #>> '{fields,g_theme_oca,g_actor_discuss,discussed_themes_oca}') AS themes,
  d.doc #> '{fields,g_affected_people}' AS affected
 FROM eligible e JOIN LATERAL (
  SELECT c.doc FROM public.couchdb c WHERE c.doc->>'_id'=e.uuid OFFSET 0
 ) d ON d.doc->>'form'='communication'
), valid AS MATERIALIZED (
 SELECT *,date_trunc('month',activity_date)::date AS reported_month,
  CASE WHEN role='oca' THEN
   CASE WHEN affected->>'affected_old_man' ~ '^[0-9]+([.][0-9]+)?$' THEN (affected->>'affected_old_man')::numeric ELSE 0 END+
   CASE WHEN affected->>'affected_little_boy' ~ '^[0-9]+([.][0-9]+)?$' THEN (affected->>'affected_little_boy')::numeric ELSE 0 END
  ELSE CASE WHEN affected->>'affected_man' ~ '^[0-9]+([.][0-9]+)?$' THEN (affected->>'affected_man')::numeric ELSE 0 END END AS men,
  CASE WHEN role='oca' THEN
   CASE WHEN affected->>'affected_old_woman' ~ '^[0-9]+([.][0-9]+)?$' THEN (affected->>'affected_old_woman')::numeric ELSE 0 END+
   CASE WHEN affected->>'affected_little_girl' ~ '^[0-9]+([.][0-9]+)?$' THEN (affected->>'affected_little_girl')::numeric ELSE 0 END
  ELSE CASE WHEN affected->>'affected_woman' ~ '^[0-9]+([.][0-9]+)?$' THEN (affected->>'affected_woman')::numeric ELSE 0 END END AS women
 FROM fields
 WHERE activity_date>=date_trunc('month',CURRENT_DATE)-interval '12 months'
  AND activity_date<date_trunc('month',CURRENT_DATE)
)
SELECT chw_site_uuid,reported_month,count(*) AS communications,
 count(*) FILTER(WHERE activity_type='vad') AS promotion_visits,
 count(*) FILTER(WHERE activity_type='chat') AS talks,
 sum(men) FILTER(WHERE activity_type='vad') AS men,
 sum(women) FILTER(WHERE activity_type='vad') AS women,
 count(*) FILTER(WHERE themes ~* 'malaria|palu') AS theme_malaria,
 count(*) FILTER(WHERE themes ~* 'vaccination') AS theme_vaccination,
 count(*) FILTER(WHERE themes ~* 'hiv|vih') AS theme_hiv,
 count(*) FILTER(WHERE themes ~* 'tuberculosis|tuberculose|tb') AS theme_tuberculosis,
 count(*) FILTER(WHERE themes ~* 'nutrition') AS theme_nutrition,
 count(*) FILTER(WHERE themes ~* 'water|wash|eau|hygiene|hygiène') AS theme_wash,
 count(*) FILTER(WHERE themes ~* 'family_planning|planification') AS theme_family_planning,
 count(*) FILTER(WHERE themes ~* 'anc|cpn') AS theme_anc,
 count(*) FILTER(WHERE themes ~* 'ira') AS theme_ira,
 count(*) FILTER(WHERE themes ~* 'diarrhea|diarrhée|diarrhee') AS theme_diarrhea
FROM valid GROUP BY 1,2
) SELECT s.chw_site_uuid AS entity_uuid,s.reported_month,s.communications::numeric AS communications,s.promotion_visits::numeric AS promotion_visits,s.talks::numeric AS talks,s.men::numeric AS men,s.women::numeric AS women,s.theme_malaria::numeric AS theme_malaria,s.theme_vaccination::numeric AS theme_vaccination,s.theme_hiv::numeric AS theme_hiv,s.theme_tuberculosis::numeric AS theme_tuberculosis,s.theme_nutrition::numeric AS theme_nutrition,s.theme_wash::numeric AS theme_wash,s.theme_family_planning::numeric AS theme_family_planning,s.theme_anc::numeric AS theme_anc,s.theme_ira::numeric AS theme_ira,s.theme_diarrhea::numeric AS theme_diarrhea FROM activity s) raw GROUP BY entity_uuid,reported_month), geography AS (SELECT * FROM public.mv_asc_ops_geography)
    SELECT s.entity_uuid,s.reported_month::date,s.input_rows,g.region_uuid,
      coalesce(g.region,'Hors répertoire courant') AS region,g.district_uuid,
      coalesce(g.district,'Hors répertoire courant') AS district,g.district_name,g.health_area_uuid,
      coalesce(g.cscom,'Hors répertoire courant') AS cscom,g.cscom_name,g.site_uuid,g.site,g.site_name,g.supervision_area,
      CASE WHEN g.site_uuid IS NULL THEN 'Hors répertoire courant' ELSE 'Rattaché au répertoire courant' END AS attribution,
      s.communications,s.promotion_visits,s.talks,s.men,s.women,s.theme_malaria,s.theme_vaccination,s.theme_hiv,s.theme_tuberculosis,s.theme_nutrition,s.theme_wash,s.theme_family_planning,s.theme_anc,s.theme_ira,s.theme_diarrhea,
      CURRENT_TIMESTAMP AS calculated_at,
      (date_trunc('month',CURRENT_DATE)-interval '12 months')::date AS coverage_start,
      date_trunc('month',CURRENT_DATE)::date AS coverage_end
    FROM source s LEFT JOIN geography g ON g.site_uuid=s.entity_uuid
