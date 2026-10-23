"""Native SD assessment summaries; no clinical rows leave either database."""
import json
from pathlib import Path
from uuid import UUID,uuid5
ROOT=Path(__file__).resolve().parent
CATALOG=json.loads((ROOT/'sd_quality_catalog.json').read_text())
NS=UUID('a411e2f8-88dd-414a-b220-89f55ee85a77')
def uid(key):return uuid5(NS,key)
TABLE='mv_sd_quality_v2'
RDT_FIELDS={
 's_tdr_indications':['yes'],'s_tdr_kit_assembled':['yes'],'s_tdr_peremption_date':['yes'],'s_tdr_peremption':['no'],
 's_gloves':['yes'],'s_tdr_information':['yes'],'s_finger_disinfection':['yes'],'s_blood_quantity':['one_pipette'],
 's_solvent_drops':['yes','4'],'s_needles_arranged':['yes'],'s_tdr_required_time_to_read':['yes'],'s_tdr_result_well_interpreted':['yes']}
FIELDS=sorted({m['field'] for m in CATALOG if 'field' in m}|set(RDT_FIELDS)|{'s_patient_assessed','s_tdr_done','s_anje_activity_done'})
CORE=['reports','site_months','score_valid','acceptable','below80','score_missing','score_invalid','latest_ambiguous','multiple_visits','unknown_site_reports','unmapped_site_months','score_basis_unusable','score_formula_disagreements']
GEO=['region_uuid','region','district_uuid','district_name','district','health_area_uuid','cscom_name','cscom','supervisor_area_uuid','zone_name','zone','mapping_status']
MEASURE_SUFFIXES=['num','den','eligible','missing','na','invalid']
COUNTERS=CORE+[m['key']+'_'+suffix for m in CATALOG for suffix in MEASURE_SUFFIXES]
SOURCES={'disc':1,'asa':2}
def literal(value):return "'"+value.replace("'","''")+"'"
def in_values(field,values):return field+' IN ('+','.join(literal(x) for x in values)+')'
def numeric(field):return "CASE WHEN "+field+" ~ '^[+-]?([0-9]+([.,][0-9]*)?|[.,][0-9]+)$' THEN replace("+field+",',','.')::numeric END"
def geography(source):
 if source=='disc':return '''SELECT chw_site_uuid AS site_uuid,region_uuid,region,district_uuid,district AS district_name,
 health_area_uuid,health_area AS cscom_name,supervisor_area_uuid,supervisor_area AS zone_name
 FROM public.mv_superset_sd_portfolio'''
 return '''SELECT s.uuid AS site_uuid,NULL::text AS region_uuid,coalesce(cp.region,'Inconnue') AS region,
 hc.district_hospital AS district_uuid,coalesce(cp.district,dh.name,'Inconnu') AS district_name,
 NULL::text AS health_area_uuid,NULL::text AS cscom_name,hc.uuid AS supervisor_area_uuid,hc.name AS zone_name
 FROM public.contactview_clinic s
 LEFT JOIN public.contactview_health_center hc ON hc.uuid=s.area
 LEFT JOIN public.contactview_person cp ON cp.uuid=hc.primary_contact
 LEFT JOIN public.contactview_hospital dh ON dh.uuid=hc.district_hospital'''
def raw(source):
 site='_id' if source=='disc' else 'area_id'
 fields=',\n'.join("nullif(lower(btrim("+f+"::text)),'') AS "+f for f in FIELDS)
 return '''SELECT uuid,nullif(btrim('''+site+'''::text),'') AS site_uuid,reported AS reported_at,
 date_trunc('month',reported)::date AS reported_month,
 nullif(btrim(final_score::text),'') AS score_text,
 nullif(btrim(assessed_items::text),'') AS assessed_text,
 nullif(btrim(applicable_score::text),'') AS applicable_text,
 '''+fields+'''
 FROM public.formview_visit_chw_site
 WHERE reported>='2019-01-01' AND reported<date_trunc('month',CURRENT_DATE)'''
def count_if(condition):return 'COUNT(*) FILTER (WHERE '+condition+')::bigint'
def metric_expressions(m):
 gate='unambiguous'
 if m['kind'] in ['score','score_available']:
  if m['kind']=='score_available':num='score_usable';den='TRUE';missing='NOT score_usable'
  else:
   num='score_usable AND score>=80';den='score_usable' if m['denominator']=='valid' else 'TRUE';missing='NOT score_usable'
  return dict(num=num,den=den,eligible='TRUE',missing=missing,na='FALSE',invalid='FALSE')
 if m['kind']=='enum':
  gate+=' AND ('+m['gate']+')';f=m['field'];answers=in_values(f,m['answers'])
  return dict(num=gate+' AND '+in_values(f,m['success']),den=gate+' AND '+answers,eligible=gate,
   missing=gate+' AND '+f+' IS NULL',na=gate+" AND "+f+"='not_applicable'",
   invalid=gate+' AND '+f+" IS NOT NULL AND "+f+"<>'not_applicable' AND NOT ("+answers+')')
 gate+=" AND s_tdr_done='yes'"
 complete=' AND '.join(f+" IS NOT NULL AND "+f+"<>'not_applicable'" for f in RDT_FIELDS)
 known=' AND '.join(in_values(f,['less_than_one_pipette','one_pipette','more_than_one'] if f=='s_blood_quantity' else ['yes','no','4'] if f=='s_solvent_drops' else ['yes','no']) for f in RDT_FIELDS)
 success=' AND '.join(in_values(f,expected) for f,expected in RDT_FIELDS.items())
 return dict(num=gate+' AND ('+complete+') AND ('+known+') AND ('+success+')',den=gate+' AND ('+complete+') AND ('+known+')',eligible=gate,
  missing=gate+' AND NOT ('+' AND '.join(f+' IS NOT NULL' for f in RDT_FIELDS)+')',
  na=gate+' AND ('+' OR '.join(f+"='not_applicable'" for f in RDT_FIELDS)+') AND ('+' AND '.join(f+' IS NOT NULL' for f in RDT_FIELDS)+')',invalid=gate+' AND ('+complete+') AND NOT ('+known+')')
def snapshot_sql(source):
 expressions={
 'reports':'SUM(report_count)::bigint','site_months':'COUNT(*)::bigint',
 'score_valid':count_if('score_usable'),'acceptable':count_if('score_usable AND score>=80'),'below80':count_if('score_usable AND score<80'),
 'score_missing':count_if('unambiguous AND score_text IS NULL'),
 'score_invalid':count_if('unambiguous AND score_text IS NOT NULL AND NOT coalesce(score BETWEEN 0 AND 100,FALSE)'),
 'latest_ambiguous':count_if('NOT unambiguous'),'multiple_visits':count_if('report_count>1'),
 'unknown_site_reports':'0::bigint','unmapped_site_months':count_if('NOT mapped'),
 'score_basis_unusable':count_if('score_usable AND NOT coalesce(assessed>0 AND applicable>=0,FALSE)'),
 'score_formula_disagreements':count_if('score_usable AND assessed>0 AND applicable>=0 AND abs(score-round(applicable/NULLIF(assessed*2,0)*100,2))>0.02')}
 for m in CATALOG:
  for suffix,condition in metric_expressions(m).items():expressions[m['key']+'_'+suffix]=count_if(condition)
 select=',\n'.join(expressions[k]+' AS '+k for k in COUNTERS)
 empty=',\n'.join(('COUNT(*)::bigint' if k in ['reports','unknown_site_reports'] else '0::bigint')+' AS '+k for k in COUNTERS)
 geo_select='''g.region_uuid,coalesce(g.region,'Non rattachée') AS region,g.district_uuid,
 coalesce(g.district_name,'Non rattaché') AS district_name,
 concat_ws(' · ',g.district_name,g.region) AS district,g.health_area_uuid,g.cscom_name,
 concat_ws(' · ',g.cscom_name,g.district_name,g.region) AS cscom,
 g.supervisor_area_uuid,g.zone_name,concat_ws(' · ',g.zone_name,g.cscom_name,g.district_name,g.region) AS zone,
 CASE WHEN g.site_uuid IS NOT NULL AND g.supervisor_area_uuid IS NOT NULL AND g.region IS NOT NULL AND g.region<>'Inconnue' THEN 'Rattaché au répertoire courant' ELSE 'Hors répertoire courant' END AS mapping_status'''
 return '''WITH raw AS MATERIALIZED (
'''+raw(source)+'''
), geography AS MATERIALIZED (
'''+geography(source)+'''
), ranked AS (
 SELECT r.*,
 COUNT(*) OVER(PARTITION BY site_uuid,reported_month) AS report_count,
 COUNT(*) OVER(PARTITION BY site_uuid,reported_month,reported_at) AS same_timestamp,
 row_number() OVER(PARTITION BY site_uuid,reported_month ORDER BY reported_at DESC,uuid DESC) AS rank
 FROM raw r WHERE site_uuid IS NOT NULL
), numeric_scores AS (
 SELECT r.*,'''+numeric('score_text')+' AS score,'+numeric('assessed_text')+' AS assessed,'+numeric('applicable_text')+''' AS applicable
 FROM ranked r WHERE rank=1
), latest AS (
 SELECT n.*,same_timestamp=1 AS unambiguous,
 same_timestamp=1 AND coalesce(score BETWEEN 0 AND 100,FALSE) AS score_usable,
 g.site_uuid IS NOT NULL AND g.supervisor_area_uuid IS NOT NULL AND g.region IS NOT NULL AND g.region<>'Inconnue' AS mapped,'''+geo_select+'''
 FROM numeric_scores n LEFT JOIN geography g USING(site_uuid)
), summary AS (
 SELECT reported_month,'''+','.join(GEO)+',\n'+select+'''
 FROM latest GROUP BY reported_month,'''+','.join(GEO)+'''
 UNION ALL
 SELECT reported_month,NULL::text,'Non rattachée',NULL::text,'Non rattaché','',NULL::text,NULL::text,'',NULL::text,NULL::text,'','Identifiant de site absent',
 '''+empty+'''
 FROM raw WHERE site_uuid IS NULL GROUP BY reported_month
)
SELECT md5(jsonb_build_array('''+','.join(GEO)+''')::text) AS entity_key,s.*,CURRENT_TIMESTAMP AS calculated_at
FROM summary s'''
def write_sources():
 target=ROOT/'sql/supervision/quality';target.mkdir(parents=True,exist_ok=True)
 for source in SOURCES:(target/(source+'.sql')).write_text(snapshot_sql(source)+'\n')
if __name__=='__main__':write_sources()
