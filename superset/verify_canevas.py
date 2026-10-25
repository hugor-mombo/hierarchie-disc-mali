"""Native SQL fixtures and cross-indicator bounds; no clinical rows leave PostgreSQL."""
import json
from sqlalchemy import text
from superset.app import create_app
from theme_sql import ROOT


def fixture_checks(c):
    # Execute the production vaccination SQL against anonymous evaluations:
    # updated status, age boundaries, ties, missing identity and a prior positive.
    fixture="""(VALUES
      ('r1','p1','s',date_trunc('month',CURRENT_DATE)-interval '1 month'+interval '1 day','12','no','no','no','no'),
      ('r2','p1','s',date_trunc('month',CURRENT_DATE)-interval '1 month'+interval '5 days','12','yes','no','yes','no'),
      ('r3','p2','s',date_trunc('month',CURRENT_DATE)-interval '1 month'+interval '5 days','23','no','yes','no','yes'),
      ('r4','p3','s',date_trunc('month',CURRENT_DATE)-interval '1 month'+interval '5 days','24','yes','no','yes','no'),
      ('r5','p4','s',date_trunc('month',CURRENT_DATE)-interval '1 month'+interval '5 days','12','no','no','no','no'),
      ('r6','p4','s',date_trunc('month',CURRENT_DATE)-interval '1 month'+interval '5 days','12','no','no','no','no'),
      ('r7','','s',date_trunc('month',CURRENT_DATE)-interval '1 month'+interval '5 days','12','yes','no','yes','no'),
      ('r8','p5','s',date_trunc('month',CURRENT_DATE)-interval '1 month'+interval '5 days','15','no','no','no','no')
    ) AS fixture(uuid,patient_uuid,reported_by_parent,reported,patient_age_in_months,
       vaccination_up_to_date,vaccination_already_up_to_date,is_vaccine_penta_1,already_is_vaccine_penta_1)"""
    sql=(ROOT/'sql/themes/vaccination_canevas.sql').read_text().replace('public.formview_child_longitudinal_followup_1_24',fixture)
    rows=c.execute(text(sql)).mappings().all()
    assert len(rows)==1 and tuple(rows[0][k] for k in ['observed_under2','observed_up_to_date','observed_at23','observed_zero12_23'])==(3,2,1,1),rows
    # Full production maternal SQL with synthetic Couch documents and empty native
    # registration/delivery sources. Explicit administration and actual patient ID
    # are required; repeat death notifications must collapse within the CSCOM/month.
    documents=[
      ('s1','pregnancy_followup',{'patient_id':'p1','g_followup_realization':{'g_sp_administration':{'has_given_ps1':'yes','has_given_ps2':'yes','sp_administered':'sp_3'}}}),
      ('s2','pregnancy_registration',{'patient_uuid':'p2','g_sp_administration':{'has_given_sp':'yes','sp_administered':'sp3'}}),
      ('s3','pregnancy_followup',{'patient_id':'p3','g_followup_realization':{'g_sp_administration':{'has_given_ps2':'no','sp_administered':'sp_6'}}}),
      ('d1','pregnancy_followup',{'patient_id':'p4','g_end_followup':{'why_end_followup':'death_of_the woman'}}),
      ('d2','postnatal_followup',{'patient_id':'p4','g_postnatal_consultation':{'mother_alive':'no'}}),
      ('d3','postnatal_followup',{'patient_id':'','g_postnatal_consultation':{'mother_alive':'no'}}),
    ]
    literal=lambda v:"'"+v.replace("'","''")+"'"
    docs=','.join('('+literal(json.dumps({'_id':uid,'fields':fields}))+ '::jsonb)' for uid,form,fields in documents)
    meta=','.join('('+literal(uid)+','+literal(form)+",date_trunc('month',CURRENT_DATE)-interval '1 month'+interval '5 days','s')" for uid,form,fields in documents)
    replacements={
      'public.form_metadata':"(VALUES "+meta+") AS fm(uuid,formname,reported,chw_area)",
      'public.couchdb':"(VALUES "+docs+") AS cd(doc)",
      'public.mv_asc_ops_geography':"(VALUES ('s','r','d','h')) AS geo(site_uuid,region_uuid,district_uuid,health_area_uuid)",
      'public.formview_pregnancy_registration':"(SELECT 's'::text reported_by_parent,CURRENT_DATE::timestamp reported,''::text patient_uuid,'no'::text pregnancy_confirmed,'no'::text had_prenatal_visit,'no'::text refer_to_cscom_chw WHERE false) AS empty_registration",
      'public.formview_pregnancy_confirmation':"(SELECT 's'::text reported_by_parent,CURRENT_DATE::timestamp reported,''::text patient_uuid,'no'::text pregnancy_confirmed,'no'::text had_prenatal_visit,'no'::text refer_to_cscom_chw WHERE false) AS empty_confirmation",
      'public.formview_delivery_registration':"(SELECT 's'::text reported_by_parent,CURRENT_DATE::timestamp reported,''::text patient_uuid,'home'::text delivery_location,'no'::text refer_patient_to_cscom_chw WHERE false) AS empty_delivery",
    }
    # The production SQL supplies aliases f/c/g; inline relation replacements must
    # leave those aliases available instead of adding a second alias.
    import re
    sql=(ROOT/'sql/themes/maternal_canevas.sql').read_text()
    for table,replacement in replacements.items():
        match=re.search(r'\) AS \w+\(([^)]+)\)$',replacement)
        if match:
            alias={'public.form_metadata':'f','public.couchdb':'c','public.mv_asc_ops_geography':'g'}[table]
            replacement=replacement[:match.start()]+') '+alias+'('+match.group(1)+')'
            sql=sql.replace(table+' '+alias,replacement)
        else:sql=sql.replace(table,replacement)
    row=c.execute(text(sql)).mappings().one()
    assert tuple(row[k] for k in ['sp1','sp3_month','death'])==(1,2,1),dict(row)
    # The production neonatal cohort uses real days, includes J0 and J7,
    # excludes negative dates/J8 from the three-visit count and collapses same-day forms.
    birth="(date_trunc('month',CURRENT_DATE)-interval '1 month'+interval '3 days')::date"
    visits=[]
    for patient,days,referred in [('mother1',[0,3,3,7],'no'),('mother2',[-1,0,8],'yes'),('',[0,3,7],'yes')]:
        for i,day in enumerate(days):
            visits.append("('r"+patient+str(i)+"','"+patient+"','s',"+birth+"+"+str(day)+","+birth+",to_char("+birth+",'YYYY-MM-DD'),'postnatal_followup','"+referred+"','yes','',NULL::jsonb,'chw')")
    table="(VALUES "+','.join(visits)+") AS p(uuid,patient_uuid,reported_by_parent,followup_date,reported,t_delivery_date,task_to_perform,orient_child_to_cscom,mother_alive,why_end_followup,g_new_born_repeat,role)"
    sql=(ROOT/'sql/themes/neonatal_canevas.sql').read_text().split('), cases AS (',1)[1].split('), periods AS (',1)[0]
    sql=sql.replace('public.formview_postnatal_followup p',table)
    row=c.execute(text(sql)).mappings().one()
    assert tuple(row[k] for k in ['followed_cases','three_visit_cases','referred_cases'])==(2,1,1),dict(row)
    # Explicit TB return reason, not inferred from a report of absence.
    meta="(VALUES ('contact1','assessment_case_contact_tb',date_trunc('month',CURRENT_DATE)-interval '1 month'+interval '5 days','s')) AS f(uuid,formname,reported,chw_area)"
    doc={'_id':'contact1','fields':{'patient_uuid':'contact','patient_type':{'case_type':'contact_case'},'refer_to_cscom':'yes'}}
    couch="(VALUES ("+literal(json.dumps(doc))+"::jsonb)) AS c(doc)"
    followup="(VALUES ('s',CURRENT_DATE-interval '1 month',CURRENT_DATE-interval '1 month','p1','yes','patient_lost_found'),('s',CURRENT_DATE-interval '1 month',CURRENT_DATE-interval '1 month','p1','yes','patient_lost_found'),('s',CURRENT_DATE-interval '1 month',CURRENT_DATE-interval '1 month','p2','yes','routine'),('s',CURRENT_DATE-interval '1 month',CURRENT_DATE-interval '1 month','p3','no','patient_lost_found')) AS ff(reported_by_parent,s_reported_date,reported,patient_id,has_patient_returned,why_has_patient_returned)"
    sql=(ROOT/'sql/themes/tuberculose_native.sql').read_text().replace('public.formview_tb_treatment_followup',followup).replace('public.form_metadata f',meta).replace('public.couchdb c',couch)
    row=c.execute(text(sql)).mappings().one()
    assert tuple(row[k] for k in ['followed','lost_found','contacts','contacts_referred'])==(2,1,1,1),dict(row)
    # Communication UUIDs, both ASC/OCA sex fields and multiple themes. Theme
    # participation totals intentionally overlap; they are not unique people.
    date="date_trunc('month',CURRENT_DATE)-interval '1 month'+interval '5 days'"
    records=[]
    for uid,role,kind,themes,affected in [
      ('a','chw','vad','malaria vaccination',{'affected_man':'2','affected_woman':'3'}),
      ('b','chw','chat','malaria',{'affected_man':'4','affected_woman':'5'}),
      ('c','oca','chat','wash',{'affected_old_man':'1','affected_little_boy':'2','affected_old_woman':'3','affected_little_girl':'4'}),
    ]:
        records.append({'_id':uid,'form':'communication','contact':{'parent':{'_id':'s'}},'fields':{
          'inputs':{'user':{'role':role}},'g_activity':{'activity_type':kind},
          'g_theme':{'g_discuss_theme':{'discussed_themes':themes}},'g_affected_people':affected}})
    meta="(VALUES "+','.join("('"+d['_id']+"',"+date+",'communication')" for d in records)+") AS fm(uuid,reported,formname)"
    couch="(VALUES "+','.join('('+literal(json.dumps(d))+'::jsonb)' for d in records)+") AS c(doc)"
    sql=(ROOT/'sql/themes/promotion_base.sql').read_text().replace('public.form_metadata',meta).replace('public.couchdb c',couch)
    row=c.execute(text(sql)).mappings().one()
    assert tuple(row[k] for k in ['communications','promotion_visits','talks','men','women','theme_malaria_men','theme_malaria_women','theme_wash_men','theme_wash_women'])==(3,1,2,2,3,6,8,3,7),dict(row)
    # A root-level home-visit answer must not substitute for the real question
    # path of a pregnancy follow-up; duplicate report IDs count once.
    records=[
      {'_id':'v1','form':'patient_assessment_under_5','fields':{'s_reported':{'s_reported_how_patient_found':'home_visit'}}},
      {'_id':'v2','form':'pregnancy_followup','fields':{'how_patient_found':'home_visit'}},
      {'_id':'v3','form':'pregnancy_followup','fields':{'g_followup_realization':{'g_patient_availability':{'how_patient_found':'during_home_visit'}}}},
    ]
    meta="(VALUES "+','.join("('"+d['_id']+"','"+d['form']+"',"+date+",'s')" for d in records+[records[0]])+") AS f(uuid,formname,reported,chw_area)"
    couch="(VALUES "+','.join('('+literal(json.dumps(d))+'::jsonb)' for d in records)+") AS c(doc)"
    sql=(ROOT/'sql/themes/clinical_home_visits.sql').read_text().replace('public.form_metadata f',meta).replace('public.couchdb c',couch)
    row=c.execute(text(sql)).mappings().one()
    assert row['clinical_visits']==2,dict(row)
    print('Fixtures SQL natives : vaccination, SP1/SP3, décès, J0–J7, TB, VAD et participations ASC/OCA OK',flush=True)


def snapshot_checks(c):
    bounds={
      'vaccination': 'observed_up_to_date>observed_under2 OR observed_at23>observed_up_to_date OR observed_zero12_23>observed_under2',
      'tuberculose':'contacts_referred>contacts OR lost_found>followed',
      'pec_enfant':'fever_native>consult_native OR malaria_suspected>consult_native OR malaria_simple>malaria_positive OR malaria_tested<>malaria_positive+malaria_negative OR malaria_suspected<>malaria_tested+malaria_presumed',
      'neonatale':'certificate_profiles>civil_profiles OR civil_profiles>registered_profiles OR three_visit_cases>followed_cases OR referred_cases>followed_cases',
      'planification':'new_user_native>users_native',
      'promotion':'all_visits<>coalesce(promotion_visits,0)+coalesce(clinical_visits,0)',
    }
    for key,condition in bounds.items():
        assert not c.execute(text('SELECT 1 FROM public.mv_asc_theme_'+key+' WHERE '+condition+' LIMIT 1')).first(),key
    print('Bornes entre indicateurs : six thématiques OK',flush=True)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--fixtures-only',action='store_true');args=parser.parse_args()
    app=create_app()
    with app.app_context():
        from superset import db
        from superset.models.core import Database
        with db.session.query(Database).filter_by(id=1).one().get_sqla_engine() as e:
            with e.connect() as c:
                c.execute(text('SET TRANSACTION READ ONLY'));c.execute(text("SET LOCAL statement_timeout='60s'"));c.execute(text("SET LOCAL TIME ZONE 'UTC'"));c.execute(text('SET LOCAL jit=off'))
                fixture_checks(c)
                if not args.fixtures_only:snapshot_checks(c)
