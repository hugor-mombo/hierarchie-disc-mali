"""Contrôles des périmètres, sans modifier les rôles et sans sortir de lignes nominatives."""
import json
from unittest.mock import patch
from flask import g
from flask_login import login_user
from superset.app import create_app

app=create_app()
with app.app_context():
    from superset import db,security_manager
    from superset.connectors.sqla.models import SqlaTable
    from superset.models.dashboard import Dashboard
    from uuid import UUID,uuid5
    ns=UUID('a88972a5-b85f-4772-92cf-8ff98e473283')
    datasets=[db.session.query(SqlaTable).filter_by(uuid=uuid5(ns,k)).one()
              for k in ['accounts','children','geography']]
    datasets.extend(db.session.query(SqlaTable).filter(SqlaTable.id.in_([33,34])).all())
    owner=security_manager.find_user(username='hmombo')
    users=db.session.query(security_manager.user_model).filter(
        security_manager.user_model.roles.any(name='DISC_REGION_bougouni')).all()
    reader=next(u for u in users if u.is_active and not any(r.name in ['Admin','Alpha','DISC_NATIONAL'] for r in u.roles))
    region='39af6dc3-4cd1-4eb9-955a-46edb57a9988'
    checks=[]
    with app.test_request_context('/'):
        login_user(reader);g.user=reader
        for ds in datasets:
            result=ds.query(dict(columns=['region_uuid'],metrics=[],granularity=None,
                is_timeseries=False,from_dttm=None,to_dttm=None,row_limit=100,
                filter=[],orderby=[],extras={'where':'','having':''}))
            assert not result.error_message,(ds.id,result.error_message)
            seen=set(result.df['region_uuid']) if not result.df.empty else set()
            assert seen.issubset({region}),(ds.id,'Résultat hors région')
            if ds.id==34:
                assert not seen,'Les contrôles nationaux doivent rester nationaux'
            elif ds.id in [33,datasets[2].id]:
                assert seen=={region},(ds.id,'Périmètre régional vide inattendu')
            checks.append({'dataset':ds.id,'regional_scope':'OK'})
        dashboard_role=security_manager.find_role('DISC_DASH_ASC_ACTIVITY')
        with patch.object(security_manager,'get_user_roles',return_value=[dashboard_role]):
            for ds in datasets:
                rules=security_manager.get_rls_filters(ds)
                assert any(r.clause=='1 = 0' for r in rules),(ds.id,'Absence de refus par défaut')
        login_user(owner);g.user=owner
        for ds in datasets:
            assert not any(r.clause=='1 = 0' for r in security_manager.get_rls_filters(ds)), 'Administrateur bloqué'
    print(json.dumps({'status':'OK','checks':checks,'default_deny':True,'admin_preserved':True}))
