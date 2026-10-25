"""Build site/month or CSCOM/month sources without joining a CSCOM total to its sites."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
CATALOG=json.loads((ROOT/'theme_catalog.json').read_text())
NS='21ae1ecf-7a1d-4b78-a449-61ce8a2eed64'

def table_name(theme):
    return 'mv_asc_theme_'+theme['key'].replace('-','_')

NATIVE = {
    'maternelle': ('maternal_canevas.sql', {'sp1','sp3_month','death','anc_referred','home_referred'}),
    'vaccination': ('vaccination_canevas.sql', {'observed_under2','observed_up_to_date','observed_at23','observed_zero12_23'}),
    'planification': ('fp_native.sql', {'counseling_native','new_user_native','users_native'}),
}

def raw_source_sql(theme):
    key=theme['key']
    if key=='tuberculose':
        return (ROOT/'sql/themes/tuberculose_native.sql').read_text()
    if key=='neonatale':
        return (ROOT/'sql/themes/neonatal_canevas.sql').read_text()
    if key=='promotion':
        extra={'wash_reports','clinical_visits','all_visits'}
        base=_base_source_sql({**theme,'metrics':[m for m in theme['metrics'] if m['key'] not in extra]})
        clinical=(ROOT/'sql/themes/clinical_home_visits.sql').read_text()
        wash=(ROOT/'sql/themes/wash_native.sql').read_text()
        items=','.join(('coalesce(w.wash_reports,0)' if m['key']=='wash_reports' else
                       'coalesce(c.clinical_visits,0)' if m['key']=='clinical_visits' else
                       'coalesce(s.promotion_visits,0)+coalesce(c.clinical_visits,0)' if m['key']=='all_visits' else 's.'+m['key'])+' AS '+m['key'] for m in theme['metrics'])
        return ('WITH base AS ('+base+'), clinical AS ('+clinical+'), wash AS ('+wash+'), periods AS ('
                'SELECT entity_uuid,reported_month FROM base UNION SELECT entity_uuid,reported_month FROM clinical UNION SELECT entity_uuid,reported_month FROM wash) '
                'SELECT p.entity_uuid,p.reported_month,'+items+' FROM periods p '
                'LEFT JOIN base s ON s.entity_uuid IS NOT DISTINCT FROM p.entity_uuid AND s.reported_month=p.reported_month '
                'LEFT JOIN clinical c ON c.entity_uuid IS NOT DISTINCT FROM p.entity_uuid AND c.reported_month=p.reported_month '
                'LEFT JOIN wash w ON w.entity_uuid IS NOT DISTINCT FROM p.entity_uuid AND w.reported_month=p.reported_month')
    if key not in NATIVE:
        return _base_source_sql(theme)
    filename,keys=NATIVE[key]
    corrected=(ROOT/'sql/themes'/filename).read_text()
    base=_base_source_sql({**theme,'metrics':[m for m in theme['metrics'] if m['key'] not in keys]})
    items=','.join(('coalesce(c.'+m['key']+',0)' if m['key'] in keys else 's.'+m['key'])+'::numeric AS '+m['key'] for m in theme['metrics'])
    return ('WITH corrected AS ('+corrected+'), legacy AS ('+base+'), periods AS ('
            'SELECT entity_uuid,reported_month FROM corrected UNION SELECT entity_uuid,reported_month FROM legacy) '
            'SELECT p.entity_uuid,p.reported_month,'+items+' FROM periods p '
            'LEFT JOIN legacy s ON s.entity_uuid IS NOT DISTINCT FROM p.entity_uuid AND s.reported_month=p.reported_month '
            'LEFT JOIN corrected c ON c.entity_uuid IS NOT DISTINCT FROM p.entity_uuid AND c.reported_month=p.reported_month')

def _base_source_sql(theme):
    key=theme['key']
    metrics=theme['metrics']
    period="s.reported_month>=date_trunc('month',CURRENT_DATE)-interval '12 months' AND s.reported_month<date_trunc('month',CURRENT_DATE)"
    entity="concat(coalesce(s.region_uuid,'?'),'|',coalesce(s.district_uuid,'?'),'|',coalesce(s.health_area_uuid,'?'))" if theme['grain']=='cscom' else 's.chw_site_uuid'
    def projection(items):
        return ',\n'.join('('+expression+')::numeric AS '+name for name,expression in items)
    if key=='pec-enfant':
        corrected=(ROOT/'sql/themes/malaria_u5.sql').read_text()
        corrected_keys={m['key'] for m in metrics if m['key'].startswith('malaria_') or m['key'] in {'fever_native','consult_native'}}
        legacy_projection=projection([(m['key'],m['expression']) for m in metrics if m['key'] not in corrected_keys])
        items=','.join(('coalesce(c.'+m['key']+',0)' if m['key'] in corrected_keys else 's.'+m['key'])+'::numeric AS '+m['key'] for m in metrics)
        return ('WITH corrected AS ('+corrected+"""), legacy AS (
          SELECT """+entity+""" AS entity_uuid,s.reported_month,"""+legacy_projection+"""
          FROM public."""+theme['source']+""" s WHERE """+period+"""), periods AS (
          SELECT entity_uuid,reported_month FROM corrected UNION SELECT entity_uuid,reported_month FROM legacy)
          SELECT p.entity_uuid,p.reported_month,"""+items+""" FROM periods p
          LEFT JOIN legacy s ON s.entity_uuid IS NOT DISTINCT FROM p.entity_uuid AND s.reported_month=p.reported_month
          LEFT JOIN corrected c ON c.entity_uuid IS NOT DISTINCT FROM p.entity_uuid AND c.reported_month=p.reported_month""")
    if key=='maternelle':
        corrected=(ROOT/'sql/themes/maternal_confirmed.sql').read_text()
        items=','.join(('c.pregnant' if m['key']=='pregnant' else 's.'+m['expression'].split('.')[-1])+ '::numeric AS '+m['key'] for m in metrics)
        return ('WITH corrected AS ('+corrected+"""), legacy AS (
          SELECT """+entity+""" AS entity_uuid,s.* FROM public."""+theme['source']+""" s WHERE """+period+"""), periods AS (
          SELECT entity_uuid,reported_month FROM corrected UNION SELECT entity_uuid,reported_month FROM legacy)
          SELECT p.entity_uuid,p.reported_month,"""+items+""" FROM periods p
          LEFT JOIN legacy s ON s.entity_uuid=p.entity_uuid AND s.reported_month=p.reported_month
          LEFT JOIN corrected c ON c.entity_uuid=p.entity_uuid AND c.reported_month=p.reported_month""")
    if key=='nutrition':
        parts=[]
        for outcome in [False,True]:
            items=[(m['key'],m['expression'] if (m['key'].startswith(('mam_','mas_'))==outcome) else 'NULL::numeric') for m in metrics]
            table='malnutrition_indicators' if outcome else theme['source']
            entity='s.chw_site_id' if outcome else 's.chw_site_uuid'
            parts.append('SELECT '+entity+' AS entity_uuid,s.reported_month,'+projection(items)+' FROM public.'+table+' s WHERE '+period)
        return 'SELECT entity_uuid,reported_month,'+','.join('sum('+m['key']+') AS '+m['key'] for m in metrics)+' FROM ('+' UNION ALL '.join(parts)+') x GROUP BY 1,2'
    if key=='promotion':
        activity=(ROOT/'sql/themes/promotion_base.sql').read_text()
        return 'WITH activity AS ('+activity+') SELECT s.chw_site_uuid AS entity_uuid,s.reported_month,'+','.join('s.'+m['key']+'::numeric AS '+m['key'] for m in metrics)+' FROM activity s'
    if key=='enregistrements':
        raw=(ROOT/'sql/themes/registration_base.sql').read_text()
        aggs=[]
        conditions={'villages':"contact_type='c70_village' AND created_by NOT ILIKE '%formation%'",
                    'concessions':"contact_type='c80_concession' AND created_by LIKE '%asc%'",
                    'households':"contact_type='c90_household' AND created_by LIKE '%asc%'",
                    'members':"contact_type='c92_household' AND created_by LIKE '%asc%'"}
        for m in metrics:
            if m['key'].startswith('age_'):
                group,sex=m['key'][4:].rsplit('_',1)
                condition="contact_type='c92_household' AND age_group='"+group+"' AND sex='"+sex+"'"
            else:
                condition=conditions[m['key']]
            aggs.append('count(*) FILTER(WHERE '+condition+')::numeric AS '+m['key'])
        return 'WITH contacts AS ('+raw+') SELECT chw_site_uuid AS entity_uuid,reported_month,'+','.join(aggs)+' FROM contacts GROUP BY 1,2'
    return 'SELECT '+entity+' AS entity_uuid,s.reported_month,'+projection([(m['key'],m['expression']) for m in metrics])+' FROM public.'+theme['source']+' s WHERE '+period

def source_sql(theme):
    # Legacy vaccination rows can lose their site ID in an upstream LEFT JOIN.
    # Preserve their volumes in one NULL quality bucket per month, never as a fictitious site.
    raw=raw_source_sql(theme)
    return ('SELECT entity_uuid,reported_month,count(*)::bigint AS input_rows,'+
            ','.join('sum('+m['key']+') AS '+m['key'] for m in theme['metrics'])+
            ' FROM ('+raw+') raw GROUP BY entity_uuid,reported_month')

def snapshot_sql(theme):
    raw=source_sql(theme)
    if theme['grain']=='cscom':
        geography='''SELECT DISTINCT region_uuid,region,district_uuid,district,district_name,
        health_area_uuid,cscom,cscom_name,concat(coalesce(region_uuid,'?'),'|',coalesce(district_uuid,'?'),'|',coalesce(health_area_uuid,'?')) AS area_key FROM public.mv_asc_ops_geography'''
        entity='area_key'
        site="NULL::text AS site_uuid,NULL::text AS site,NULL::text AS site_name,NULL::text AS supervision_area"
    else:
        geography='SELECT * FROM public.mv_asc_ops_geography'
        entity='site_uuid'
        site='g.site_uuid,g.site,g.site_name,g.supervision_area'
    return '''WITH source AS ('''+raw+'''), geography AS ('''+geography+''')
    SELECT s.entity_uuid,s.reported_month::date,s.input_rows,g.region_uuid,
      coalesce(g.region,'Hors répertoire courant') AS region,g.district_uuid,
      coalesce(g.district,'Hors répertoire courant') AS district,g.district_name,g.health_area_uuid,
      coalesce(g.cscom,'Hors répertoire courant') AS cscom,g.cscom_name,'''+site+''',
      CASE WHEN g.'''+entity+''' IS NULL THEN 'Hors répertoire courant' ELSE 'Rattaché au répertoire courant' END AS attribution,
      '''+','.join('s.'+m['key'] for m in theme['metrics'])+''',
      CURRENT_TIMESTAMP AS calculated_at,
      (date_trunc('month',CURRENT_DATE)-interval '12 months')::date AS coverage_start,
      date_trunc('month',CURRENT_DATE)::date AS coverage_end
    FROM source s LEFT JOIN geography g ON g.'''+entity+'''=s.entity_uuid'''
