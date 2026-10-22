"""Tester l'API d'export native sans sortir de données individuelles du serveur."""
import argparse
import csv
import io
import json
import zipfile
import xml.etree.ElementTree as ET
from uuid import UUID,uuid5
from sqlalchemy import text
from superset.app import create_app

parser=argparse.ArgumentParser()
parser.add_argument('--readers',action='store_true')
parser.add_argument('--all-children',action='store_true')
parser.add_argument('--regional-only',action='store_true')
args=parser.parse_args()
NS=UUID('a88972a5-b85f-4772-92cf-8ff98e473283')
app=create_app()
with app.app_context():
    from superset import db,security_manager
    from superset.models.dashboard import Dashboard
    from superset.models.slice import Slice
    from superset.models.core import Database
    from superset.connectors.sqla.models import SqlaTable
    dash=db.session.query(Dashboard).filter_by(uuid=uuid5(NS,'dashboard')).one()
    owner_id=security_manager.find_user(username='hmombo').id
    dash_id,dash_slug,dash_published=dash.id,dash.slug,dash.published
    checks=[]

    def export(user_id,key,fmt,filters,where):
        with app.app_context():
            datasource=db.session.query(Database).filter_by(id=1).one()
            chart=db.session.query(Slice).filter_by(uuid=uuid5(NS,'chart:'+key)).one()
            form=json.loads(chart.params)
            ds=db.session.query(SqlaTable).filter_by(id=chart.datasource_id).one()
            body=dict(datasource={'id':ds.id,'type':'table'},force=True,
                queries=[dict(columns=form['groupby'],metrics=[],filters=filters,
                    extras={'where':'','having':''},orderby=[],row_limit=100000,row_offset=0,
                    time_range='No filter',order_desc=True)],
                form_data={**form,'slice_id':chart.id,'dashboardId':dash_id},
                result_format=fmt,result_type='full')
            base='https://dashboard.disc-mali.ml'
            # Flask-Login mémorise l'identité dans g. Un contexte distinct par client
            # évite de réutiliser celle de l'export administrateur précédent.
            with app.test_client() as client:
                with client.session_transaction(base_url=base) as session:
                    session['_user_id']=str(user_id)
                    session['_fresh']=True
                identity=client.get('/api/v1/me/',base_url=base)
                assert identity.status_code==200, ('identity',identity.status_code)
                assert identity.json['result']['id']==user_id, 'Identité du client de test incorrecte'
                csrf=client.get('/api/v1/security/csrf_token/',base_url=base)
                assert csrf.status_code==200, ('csrf',csrf.status_code)
                response=client.post('/api/v1/chart/data',base_url=base,json=body,
                    headers={'X-CSRFToken':csrf.json['result'],'Referer':base+'/superset/dashboard/'+dash_slug+'/'})
                if response.status_code!=200:
                    # Les erreurs API décrivent la requête, pas ses lignes.
                    raise AssertionError((key,fmt,response.status_code,response.json))
                payload=response.data
                if fmt=='csv':
                    rows=list(csv.reader(io.StringIO(payload.decode('utf-8-sig'))))
                    headers=rows[0]
                    count=len(rows)-1
                else:
                    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                        ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                        sheet=ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
                        count=len(sheet.findall('.//s:sheetData/s:row',ns))-1
                        headers=[]
                with datasource.get_sqla_engine() as engine:
                    with engine.connect() as c:
                        expected=c.execute(text('SELECT count(*) FROM ('+ds.sql+') q WHERE '+where)).scalar()
                assert count==expected,(key,fmt,count,expected)
                if user_id==owner_id:
                    assert count>20,(key,fmt,'L’export de contrôle doit dépasser une page')
                if fmt=='csv' and count:
                    assert len(headers)==len(form['groupby'])
                    assert any('Région' in x or x=='region' for x in headers)
                    assert any('District' in x or x=='district_name' for x in headers)
                    assert any('CSCOM' in x or x=='cscom_name' for x in headers)
                    assert any('référence' in x or x=='reference_date' for x in headers)
                checks.append({'chart':key,'format':fmt,'rows':count,
                               'columns':len(headers) if fmt=='csv' else len(form['groupby']),
                               'reader':user_id!=owner_id})
                print(json.dumps(checks[-1],ensure_ascii=False),flush=True)

    asc_filters=[{'col':'threshold_days','op':'IN','val':[30]},
                 {'col':'action_status','op':'IN','val':['À relancer']}]
    child_filters=[{'col':'followup_status','op':'IN','val':['Penta 1 non reçu déclaré — à confirmer']}]
    asc_where="threshold_days=30 AND action_status='À relancer'"
    child_where="followup_status='Penta 1 non reçu déclaré — à confirmer'"
    if not args.regional_only:
        for key,filters,where in [('asc_export',asc_filters,asc_where),('child_export',child_filters,child_where)]:
            export(owner_id,key,'csv',filters,where)
            export(owner_id,key,'xlsx',filters,where)
    if args.all_children:
        export(owner_id,'child_export','csv',[],'1=1')
    if args.readers or args.regional_only:
        assert dash_published
        users=db.session.query(security_manager.user_model).filter(
            security_manager.user_model.roles.any(name='DISC_REGION_bougouni')).all()
        reader=next(u for u in users if u.is_active and not any(r.name in ['Admin','Alpha','DISC_NATIONAL'] for r in u.roles))
        reader_id=reader.id
        region='39af6dc3-4cd1-4eb9-955a-46edb57a9988'
        # Aucun filtre de région envoyé : le cloisonnement doit venir de la sécurité.
        for key,filters,where in [('asc_export',asc_filters,asc_where),('child_export',child_filters,child_where)]:
            export(reader_id,key,'csv',filters,where+f" AND region_uuid='{region}'")
        outside='63aec90d-9aa6-505d-80e4-4f4b2e4a5709'
        export(reader_id,'child_export','csv',child_filters+[
            {'col':'region_uuid','op':'IN','val':[outside]}], '1=0')
    print(json.dumps({'status':'OK','exports':checks},ensure_ascii=False))
