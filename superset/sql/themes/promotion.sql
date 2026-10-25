WITH source AS (SELECT entity_uuid,reported_month,count(*)::bigint AS input_rows,sum(communications) AS communications,sum(promotion_visits) AS promotion_visits,sum(talks) AS talks,sum(men) AS men,sum(women) AS women,sum(theme_malaria) AS theme_malaria,sum(theme_vaccination) AS theme_vaccination,sum(theme_hiv) AS theme_hiv,sum(theme_tuberculosis) AS theme_tuberculosis,sum(theme_nutrition) AS theme_nutrition,sum(theme_wash) AS theme_wash,sum(theme_family_planning) AS theme_family_planning,sum(theme_anc) AS theme_anc,sum(theme_ira) AS theme_ira,sum(theme_diarrhea) AS theme_diarrhea,sum(wash_reports) AS wash_reports,sum(clinical_visits) AS clinical_visits,sum(all_visits) AS all_visits,sum(theme_malaria_men) AS theme_malaria_men,sum(theme_malaria_women) AS theme_malaria_women,sum(theme_vaccination_men) AS theme_vaccination_men,sum(theme_vaccination_women) AS theme_vaccination_women,sum(theme_hiv_men) AS theme_hiv_men,sum(theme_hiv_women) AS theme_hiv_women,sum(theme_tuberculosis_men) AS theme_tuberculosis_men,sum(theme_tuberculosis_women) AS theme_tuberculosis_women,sum(theme_nutrition_men) AS theme_nutrition_men,sum(theme_nutrition_women) AS theme_nutrition_women,sum(theme_wash_men) AS theme_wash_men,sum(theme_wash_women) AS theme_wash_women,sum(theme_family_planning_men) AS theme_family_planning_men,sum(theme_family_planning_women) AS theme_family_planning_women,sum(theme_anc_men) AS theme_anc_men,sum(theme_anc_women) AS theme_anc_women,sum(theme_ira_men) AS theme_ira_men,sum(theme_ira_women) AS theme_ira_women,sum(theme_diarrhea_men) AS theme_diarrhea_men,sum(theme_diarrhea_women) AS theme_diarrhea_women FROM (WITH base AS (WITH activity AS (-- Lecture bornée des rapports uniques, via les index existants de métadonnées et d’identifiant CouchDB.
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
) SELECT s.chw_site_uuid AS entity_uuid,s.reported_month,s.communications::numeric AS communications,s.promotion_visits::numeric AS promotion_visits,s.talks::numeric AS talks,s.men::numeric AS men,s.women::numeric AS women,s.theme_malaria::numeric AS theme_malaria,s.theme_vaccination::numeric AS theme_vaccination,s.theme_hiv::numeric AS theme_hiv,s.theme_tuberculosis::numeric AS theme_tuberculosis,s.theme_nutrition::numeric AS theme_nutrition,s.theme_wash::numeric AS theme_wash,s.theme_family_planning::numeric AS theme_family_planning,s.theme_anc::numeric AS theme_anc,s.theme_ira::numeric AS theme_ira,s.theme_diarrhea::numeric AS theme_diarrhea,s.theme_malaria_men::numeric AS theme_malaria_men,s.theme_malaria_women::numeric AS theme_malaria_women,s.theme_vaccination_men::numeric AS theme_vaccination_men,s.theme_vaccination_women::numeric AS theme_vaccination_women,s.theme_hiv_men::numeric AS theme_hiv_men,s.theme_hiv_women::numeric AS theme_hiv_women,s.theme_tuberculosis_men::numeric AS theme_tuberculosis_men,s.theme_tuberculosis_women::numeric AS theme_tuberculosis_women,s.theme_nutrition_men::numeric AS theme_nutrition_men,s.theme_nutrition_women::numeric AS theme_nutrition_women,s.theme_wash_men::numeric AS theme_wash_men,s.theme_wash_women::numeric AS theme_wash_women,s.theme_family_planning_men::numeric AS theme_family_planning_men,s.theme_family_planning_women::numeric AS theme_family_planning_women,s.theme_anc_men::numeric AS theme_anc_men,s.theme_anc_women::numeric AS theme_anc_women,s.theme_ira_men::numeric AS theme_ira_men,s.theme_ira_women::numeric AS theme_ira_women,s.theme_diarrhea_men::numeric AS theme_diarrhea_men,s.theme_diarrhea_women::numeric AS theme_diarrhea_women FROM activity s), clinical AS (WITH r AS MATERIALIZED(SELECT f.uuid,f.formname,f.reported,coalesce(f.chw_area,c.doc#>>'{contact,parent,_id}') AS site_uuid,c.doc->'fields' AS fields FROM public.form_metadata f JOIN LATERAL(SELECT doc FROM public.couchdb c WHERE c.doc->>'_id'=f.uuid LIMIT 1) c ON true WHERE f.reported>=date_trunc('month',CURRENT_DATE)-interval '12 months' AND reported<date_trunc('month',CURRENT_DATE) AND f.formname IN ('patient_assessment_under_5','care_of_pregnant_women_and_others','referral_followup_over_5','pregnancy_registration','pregnancy_confirmation','pregnancy_followup','pregnancy_referral_followup','mother_referral_followup','postnatal_followup','delivery_registration','fp_registration','fp_reference_followup','fp_renewal_followup')) SELECT site_uuid AS entity_uuid,date_trunc('month',reported)::date AS reported_month,count(DISTINCT uuid)::numeric AS clinical_visits FROM r WHERE (formname='patient_assessment_under_5' AND (fields#>>'{s_reported,s_reported_how_patient_found}' IN ('home_visit','during_home_visit','vad'))) OR (formname='care_of_pregnant_women_and_others' AND (fields#>>'{s_reported,s_reported_how_patient_found}' IN ('home_visit','during_home_visit','vad'))) OR (formname='referral_followup_over_5' AND (fields#>>'{g_realisation,how_patient_found}' IN ('home_visit','during_home_visit','vad'))) OR (formname='pregnancy_registration' AND (fields#>>'{g_reported,how_patient_found}' IN ('home_visit','during_home_visit','vad'))) OR (formname='pregnancy_confirmation' AND (fields#>>'{g_reported,how_patient_found}' IN ('home_visit','during_home_visit','vad'))) OR (formname='pregnancy_followup' AND (fields#>>'{g_followup_realization,g_patient_availability,how_patient_found}' IN ('home_visit','during_home_visit','vad'))) OR (formname='pregnancy_referral_followup' AND (fields#>>'{g_search_for_woman,how_patient_found}' IN ('home_visit','during_home_visit','vad'))) OR (formname='mother_referral_followup' AND (fields#>>'{g_followup,g_patient_present,how_patient_found}' IN ('home_visit','during_home_visit','vad'))) OR (formname='postnatal_followup' AND (fields#>>'{g_realisation,how_patient_found}' IN ('home_visit','during_home_visit','vad'))) OR (formname='delivery_registration' AND (fields#>>'{g_registration_recording,how_patient_found}' IN ('home_visit','during_home_visit','vad'))) OR (formname='fp_registration' AND (fields#>>'{g_evaluation,g_patient_found,how_patient_found}' IN ('home_visit','during_home_visit','vad'))) OR (formname='fp_reference_followup' AND (fields#>>'{g_followup,g_patient_found,how_patient_found}' IN ('home_visit','during_home_visit','vad'))) OR (formname='fp_renewal_followup' AND (fields#>>'{g_followup,g_patient_found,how_patient_found}' IN ('home_visit','during_home_visit','vad'))) GROUP BY 1,2
), wash AS (SELECT coalesce(f.chw_area,d.doc#>>'{contact,parent,_id}') AS entity_uuid,date_trunc('month',f.reported)::date AS reported_month,
 count(DISTINCT f.uuid)::numeric AS wash_reports
 FROM public.form_metadata f JOIN LATERAL(SELECT doc FROM public.couchdb c WHERE c.doc->>'_id'=f.uuid OFFSET 0)d ON true
 WHERE f.formname='wash' AND f.reported>=date_trunc('month',CURRENT_DATE)-interval '12 months' AND reported<date_trunc('month',CURRENT_DATE) GROUP BY 1,2
), periods AS (SELECT entity_uuid,reported_month FROM base UNION SELECT entity_uuid,reported_month FROM clinical UNION SELECT entity_uuid,reported_month FROM wash) SELECT p.entity_uuid,p.reported_month,s.communications AS communications,s.promotion_visits AS promotion_visits,s.talks AS talks,s.men AS men,s.women AS women,s.theme_malaria AS theme_malaria,s.theme_vaccination AS theme_vaccination,s.theme_hiv AS theme_hiv,s.theme_tuberculosis AS theme_tuberculosis,s.theme_nutrition AS theme_nutrition,s.theme_wash AS theme_wash,s.theme_family_planning AS theme_family_planning,s.theme_anc AS theme_anc,s.theme_ira AS theme_ira,s.theme_diarrhea AS theme_diarrhea,coalesce(w.wash_reports,0) AS wash_reports,coalesce(c.clinical_visits,0) AS clinical_visits,coalesce(s.promotion_visits,0)+coalesce(c.clinical_visits,0) AS all_visits,s.theme_malaria_men AS theme_malaria_men,s.theme_malaria_women AS theme_malaria_women,s.theme_vaccination_men AS theme_vaccination_men,s.theme_vaccination_women AS theme_vaccination_women,s.theme_hiv_men AS theme_hiv_men,s.theme_hiv_women AS theme_hiv_women,s.theme_tuberculosis_men AS theme_tuberculosis_men,s.theme_tuberculosis_women AS theme_tuberculosis_women,s.theme_nutrition_men AS theme_nutrition_men,s.theme_nutrition_women AS theme_nutrition_women,s.theme_wash_men AS theme_wash_men,s.theme_wash_women AS theme_wash_women,s.theme_family_planning_men AS theme_family_planning_men,s.theme_family_planning_women AS theme_family_planning_women,s.theme_anc_men AS theme_anc_men,s.theme_anc_women AS theme_anc_women,s.theme_ira_men AS theme_ira_men,s.theme_ira_women AS theme_ira_women,s.theme_diarrhea_men AS theme_diarrhea_men,s.theme_diarrhea_women AS theme_diarrhea_women FROM periods p LEFT JOIN base s ON s.entity_uuid IS NOT DISTINCT FROM p.entity_uuid AND s.reported_month=p.reported_month LEFT JOIN clinical c ON c.entity_uuid IS NOT DISTINCT FROM p.entity_uuid AND c.reported_month=p.reported_month LEFT JOIN wash w ON w.entity_uuid IS NOT DISTINCT FROM p.entity_uuid AND w.reported_month=p.reported_month) raw GROUP BY entity_uuid,reported_month), geography AS (SELECT * FROM public.mv_asc_ops_geography)
    SELECT s.entity_uuid,s.reported_month::date,s.input_rows,g.region_uuid,
      coalesce(g.region,'Hors répertoire courant') AS region,g.district_uuid,
      coalesce(g.district,'Hors répertoire courant') AS district,g.district_name,g.health_area_uuid,
      coalesce(g.cscom,'Hors répertoire courant') AS cscom,g.cscom_name,g.site_uuid,g.site,g.site_name,g.supervision_area,
      CASE WHEN g.site_uuid IS NULL THEN 'Hors répertoire courant' ELSE 'Rattaché au répertoire courant' END AS attribution,
      s.communications,s.promotion_visits,s.talks,s.men,s.women,s.theme_malaria,s.theme_vaccination,s.theme_hiv,s.theme_tuberculosis,s.theme_nutrition,s.theme_wash,s.theme_family_planning,s.theme_anc,s.theme_ira,s.theme_diarrhea,s.wash_reports,s.clinical_visits,s.all_visits,s.theme_malaria_men,s.theme_malaria_women,s.theme_vaccination_men,s.theme_vaccination_women,s.theme_hiv_men,s.theme_hiv_women,s.theme_tuberculosis_men,s.theme_tuberculosis_women,s.theme_nutrition_men,s.theme_nutrition_women,s.theme_wash_men,s.theme_wash_women,s.theme_family_planning_men,s.theme_family_planning_women,s.theme_anc_men,s.theme_anc_women,s.theme_ira_men,s.theme_ira_women,s.theme_diarrhea_men,s.theme_diarrhea_women,
      CURRENT_TIMESTAMP AS calculated_at,
      (date_trunc('month',CURRENT_DATE)-interval '12 months')::date AS coverage_start,
      date_trunc('month',CURRENT_DATE)::date AS coverage_end
    FROM source s LEFT JOIN geography g ON g.site_uuid=s.entity_uuid
