-- Lecture bornée des rapports uniques, via les index existants de métadonnées et d’identifiant CouchDB.
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
 count(*) FILTER(WHERE themes ~* 'diarrhea|diarrhée|diarrhee') AS theme_diarrhea,
 sum(men) FILTER(WHERE themes ~* 'malaria|palu') AS theme_malaria_men,
 sum(women) FILTER(WHERE themes ~* 'malaria|palu') AS theme_malaria_women,
 sum(men) FILTER(WHERE themes ~* 'vaccination') AS theme_vaccination_men,
 sum(women) FILTER(WHERE themes ~* 'vaccination') AS theme_vaccination_women,
 sum(men) FILTER(WHERE themes ~* 'hiv|vih') AS theme_hiv_men,
 sum(women) FILTER(WHERE themes ~* 'hiv|vih') AS theme_hiv_women,
 sum(men) FILTER(WHERE themes ~* 'tuberculosis|tuberculose|tb') AS theme_tuberculosis_men,
 sum(women) FILTER(WHERE themes ~* 'tuberculosis|tuberculose|tb') AS theme_tuberculosis_women,
 sum(men) FILTER(WHERE themes ~* 'nutrition') AS theme_nutrition_men,
 sum(women) FILTER(WHERE themes ~* 'nutrition') AS theme_nutrition_women,
 sum(men) FILTER(WHERE themes ~* 'water|wash|eau|hygiene|hygiène') AS theme_wash_men,
 sum(women) FILTER(WHERE themes ~* 'water|wash|eau|hygiene|hygiène') AS theme_wash_women,
 sum(men) FILTER(WHERE themes ~* 'family_planning|planification') AS theme_family_planning_men,
 sum(women) FILTER(WHERE themes ~* 'family_planning|planification') AS theme_family_planning_women,
 sum(men) FILTER(WHERE themes ~* 'anc|cpn') AS theme_anc_men,
 sum(women) FILTER(WHERE themes ~* 'anc|cpn') AS theme_anc_women,
 sum(men) FILTER(WHERE themes ~* 'ira') AS theme_ira_men,
 sum(women) FILTER(WHERE themes ~* 'ira') AS theme_ira_women,
 sum(men) FILTER(WHERE themes ~* 'diarrhea|diarrhée|diarrhee') AS theme_diarrhea_men,
 sum(women) FILTER(WHERE themes ~* 'diarrhea|diarrhée|diarrhee') AS theme_diarrhea_women
FROM valid GROUP BY 1,2
