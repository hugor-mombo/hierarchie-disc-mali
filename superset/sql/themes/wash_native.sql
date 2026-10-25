SELECT coalesce(f.chw_area,d.doc#>>'{contact,parent,_id}') AS entity_uuid,date_trunc('month',f.reported)::date AS reported_month,
 count(DISTINCT f.uuid)::numeric AS wash_reports
 FROM public.form_metadata f JOIN LATERAL(SELECT doc FROM public.couchdb c WHERE c.doc->>'_id'=f.uuid OFFSET 0)d ON true
 WHERE f.formname='wash' AND f.reported>=date_trunc('month',CURRENT_DATE)-interval '12 months' AND reported<date_trunc('month',CURRENT_DATE) GROUP BY 1,2
