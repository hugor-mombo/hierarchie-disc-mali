SELECT reported_by_parent AS entity_uuid,date_trunc('month',reported)::date AS reported_month,
 count(DISTINCT nullif(btrim(patient_uuid),'')) FILTER(WHERE has_advice_given='yes')::numeric AS counseling_native,
 count(DISTINCT nullif(btrim(patient_uuid),'')) FILTER(WHERE patient_having_fp='no' AND has_method_offered='yes')::numeric AS new_user_native,
 count(DISTINCT nullif(btrim(patient_uuid),'')) FILTER(WHERE patient_having_fp='yes' OR (patient_having_fp='no' AND has_method_offered='yes'))::numeric AS users_native
 FROM public.formview_fp_registration WHERE reported>=date_trunc('month',CURRENT_DATE)-interval '12 months' AND reported<date_trunc('month',CURRENT_DATE) GROUP BY 1,2
