"""Contrôles HTTP réels de connexion, navigation et autorisations sans modifier de données."""
import json,re,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent/'portal'))
from disc_portal_policy import editor,viewer_permission
from superset.app import create_app
app=create_app();BASE='https://dashboard.disc-mali.ml'
with app.app_context():
 from superset import db,security_manager as sm
 from superset.models.dashboard import Dashboard
 from superset.connectors.sqla.models import RowLevelSecurityFilter
 users=db.session.query(sm.user_model).all();owner=sm.find_user(username='hmombo').id
 def select(prefix):return next(u.id for u in users if u.active and any(r.name.startswith(prefix) for r in u.roles) and not editor(u))
 profiles=[('national',select('DISC_NATIONAL')),('region',select('DISC_REGION_')),('district',select('DISC_DISTRICT_'))]
 role=sm.find_role('DISC_VIEWER');assert role and all(viewer_permission(p.permission.name,p.view_menu.name) for p in role.permissions)
 assert {u.username for u in users if u.active and editor(u)}=={'hmombo'}
 rls={r.id:(r.clause,sorted(x.id for x in r.tables),sorted(x.id for x in r.roles)) for r in db.session.query(RowLevelSecurityFilter).all()}
 for user in users:
  if not editor(user):assert not {'Admin','Alpha','Gamma','sql_lab'} & {r.name for r in user.roles}
with app.test_client() as c:
 login=c.get('/login/',base_url=BASE);assert login.status_code==200
 text=login.data.decode();assert 'Armoiries de la République du Mali' in text and 'DISC-Mali' in text
 assert 'name="csrf_token"' in text and 'autocomplete="current-password"' in text
 assert c.get('/disc-assets/portal.css',base_url=BASE).status_code==200
 assert c.get('/api/v1/dashboard/',base_url=BASE).status_code in [401,302,403]
 # The native login form must still reject a missing CSRF token.
 with patch.object(sm,'auth_user_db') as authenticate:
  result=c.post('/login/',base_url=BASE,data={'username':'invalid-disc-test','password':'invalid-disc-test'})
  assert result.status_code in [400,302]
  authenticate.assert_not_called()
print(json.dumps({'anonymous':'OK','login':'branded','csrf':'enforced'}),flush=True)
for name,user_id in profiles+[('editor',owner)]:
 with app.test_client() as c:
  with c.session_transaction(base_url=BASE) as s:s['_user_id']=str(user_id);s['_fresh']=True
  token=c.get('/api/v1/security/csrf_token/',base_url=BASE);assert token.status_code==200
  headers={'X-CSRFToken':token.json['result'],'Referer':BASE+'/'}
  for url in ['/','/superset/welcome/','/login/']:
   response=c.get(url,base_url=BASE);assert response.status_code==302,(name,url,response.status_code)
   # AuthDBView redirects to the index; index and welcome go to the full list.
   if url!='/login/':assert response.location.endswith('/dashboard/list/'),response.location
  response=c.get('/dashboard/list/',base_url=BASE);assert response.status_code==200,(name,'catalog')
  response=c.get('/api/v1/dashboard/?q=(page:0,page_size:100)',base_url=BASE);assert response.status_code==200
  returned=response.json['result'];assert returned
  with app.test_request_context('/'):
   from flask import g
   from flask_login import login_user
   user=db.session.query(sm.user_model).filter_by(id=user_id).one();login_user(user);g.user=user
   for entry in returned:
    dash=db.session.query(Dashboard).filter_by(id=entry['id']).one();assert sm.can_access_dashboard(dash),'Catalogue hors droits'
   if name!='editor':
    pairs={p for values in sm.get_user_roles_permissions(user).values() for p in values}
    assert ('can_write','Dashboard') not in pairs and ('can_write','Chart') not in pairs,'Édition annoncée au navigateur'
   for permission,view in [('can_write','Dashboard'),('can_write','Chart'),('can_execute_sql_query','SQLLab')]:assert sm.can_access(permission,view)==(name=='editor'),(name,permission,view)
  if name!='editor':
   for url in ['/dataset/add/','/tablemodelview/list/','/chart/list/','/explore/','/superset/explore/','/sqllab/','/api/v1/sqllab/','/api/v1/chart/']:
    r=c.get(url,base_url=BASE);assert r.status_code==403,(name,url,r.status_code)
   for url in ['/api/v1/dashboard/','/api/v1/chart/','/api/v1/dataset/','/api/v1/sqllab/execute/']:
    # Empty objects: even if a permission regressed, no valid object can be created.
    r=c.post(url,base_url=BASE,json={},headers=headers);assert r.status_code==403,(name,url,r.status_code)
   # Deep links to dashboard edit mode must not grant write capability in bootstrap.
   detail=c.get('/api/v1/dashboard/'+str(returned[0]['id']),base_url=BASE);assert detail.status_code==200
  else:
   for url in ['/chart/list/','/sqllab/']:
    assert c.get(url,base_url=BASE).status_code==200,(name,url)
  print(json.dumps({'profile':name,'catalog':'OK','visible_dashboards':len(returned),'authoring':'allowed' if name=='editor' else 'denied'}),flush=True)
with app.app_context():
 assert rls=={r.id:(r.clause,sorted(x.id for x in r.tables),sorted(x.id for x in r.roles)) for r in db.session.query(RowLevelSecurityFilter).all()}
print(json.dumps({'status':'OK','rls':'unchanged'}),flush=True)
