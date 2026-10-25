WITH source AS (SELECT entity_uuid,reported_month,count(*)::bigint AS input_rows,sum(counseling) AS counseling,sum(new_user) AS new_user,sum(users) AS users,sum(counseling_native) AS counseling_native,sum(new_user_native) AS new_user_native,sum(users_native) AS users_native FROM (WITH corrected AS (SELECT reported_by_parent AS entity_uuid,date_trunc('month',reported)::date AS reported_month,
 count(DISTINCT nullif(btrim(patient_uuid),'')) FILTER(WHERE has_advice_given='yes')::numeric AS counseling_native,
 count(DISTINCT nullif(btrim(patient_uuid),'')) FILTER(WHERE patient_having_fp='no' AND has_method_offered='yes')::numeric AS new_user_native,
 count(DISTINCT nullif(btrim(patient_uuid),'')) FILTER(WHERE patient_having_fp='yes' OR (patient_having_fp='no' AND has_method_offered='yes'))::numeric AS users_native
 FROM public.formview_fp_registration WHERE reported>=date_trunc('month',CURRENT_DATE)-interval '12 months' AND reported<date_trunc('month',CURRENT_DATE) GROUP BY 1,2
), legacy AS (SELECT s.chw_site_uuid AS entity_uuid,s.reported_month,(s.fp_counseling)::numeric AS counseling,
(s.fp_new_user)::numeric AS new_user,
(s.fp_total_user)::numeric AS users FROM public.mv_family_planning_summary_superset s WHERE s.reported_month>=date_trunc('month',CURRENT_DATE)-interval '12 months' AND s.reported_month<date_trunc('month',CURRENT_DATE)), periods AS (SELECT entity_uuid,reported_month FROM corrected UNION SELECT entity_uuid,reported_month FROM legacy) SELECT p.entity_uuid,p.reported_month,s.counseling::numeric AS counseling,s.new_user::numeric AS new_user,s.users::numeric AS users,coalesce(c.counseling_native,0)::numeric AS counseling_native,coalesce(c.new_user_native,0)::numeric AS new_user_native,coalesce(c.users_native,0)::numeric AS users_native FROM periods p LEFT JOIN legacy s ON s.entity_uuid IS NOT DISTINCT FROM p.entity_uuid AND s.reported_month=p.reported_month LEFT JOIN corrected c ON c.entity_uuid IS NOT DISTINCT FROM p.entity_uuid AND c.reported_month=p.reported_month) raw GROUP BY entity_uuid,reported_month), geography AS (SELECT * FROM public.mv_asc_ops_geography)
    SELECT s.entity_uuid,s.reported_month::date,s.input_rows,g.region_uuid,
      coalesce(g.region,'Hors répertoire courant') AS region,g.district_uuid,
      coalesce(g.district,'Hors répertoire courant') AS district,g.district_name,g.health_area_uuid,
      coalesce(g.cscom,'Hors répertoire courant') AS cscom,g.cscom_name,g.site_uuid,g.site,g.site_name,g.supervision_area,
      CASE WHEN g.site_uuid IS NULL THEN 'Hors répertoire courant' ELSE 'Rattaché au répertoire courant' END AS attribution,
      s.counseling,s.new_user,s.users,s.counseling_native,s.new_user_native,s.users_native,
      CURRENT_TIMESTAMP AS calculated_at,
      (date_trunc('month',CURRENT_DATE)-interval '12 months')::date AS coverage_start,
      date_trunc('month',CURRENT_DATE)::date AS coverage_end
    FROM source s LEFT JOIN geography g ON g.site_uuid=s.entity_uuid
