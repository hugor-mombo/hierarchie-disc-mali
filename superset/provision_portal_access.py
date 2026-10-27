"""Migration réversible des lecteurs ; aucun mot de passe, RLS ou tableau modifié."""
import argparse,json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'portal'))
from disc_portal_policy import VIEWER_ROLE,EDITOR_ROLE,editor,viewer_permission
from superset.app import create_app
parser=argparse.ArgumentParser();parser.add_argument('--backup',required=True);parser.add_argument('--restore',action='store_true');args=parser.parse_args()
app=create_app()
with app.app_context():
 from superset import db,security_manager as sm
 from superset.connectors.sqla.models import RowLevelSecurityFilter
 from superset.models.dashboard import Dashboard
 users=db.session.query(sm.user_model).all();roles={r.id:r for r in sm.get_all_roles()}
 scope_before={r.id:(r.clause,sorted(t.id for t in r.tables),sorted(x.id for x in r.roles)) for r in db.session.query(RowLevelSecurityFilter).all()}
 dashboards_before={d.id:(sorted(r.id for r in d.roles),d.position_json,d.json_metadata,d.published) for d in db.session.query(Dashboard).all()}
 path=Path(args.backup)
 if args.restore:
  state=json.loads(path.read_text())
  for user in users:
   if str(user.id) in state['users']:user.roles=[roles[i] for i in state['users'][str(user.id)]]
  db.session.commit();print(json.dumps({'status':'restored'}));raise SystemExit(0)
 assert sm.find_user(username='hmombo') and any(r.name=='Admin' for r in sm.find_user(username='hmombo').roles),'Compte administrateur manquant'
 if not path.exists():
  descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(descriptor,'w') as f:json.dump({'users':{str(u.id):[r.id for r in u.roles] for u in users}},f)
 viewer=sm.find_role(VIEWER_ROLE) or sm.add_role(VIEWER_ROLE)
 gamma=sm.find_role('Gamma');assert gamma
 viewer.permissions=[p for p in gamma.permissions if viewer_permission(p.permission.name,p.view_menu.name)]
 designer=sm.find_role(EDITOR_ROLE) or sm.add_role(EDITOR_ROLE)
 # Aucun compte n'est désigné ici : la désignation relève de hmombo.
 candidates={p.id:p for name in ['Alpha','sql_lab'] for p in sm.find_role(name).permissions}
 designer.permissions=list(candidates.values())
 count=0
 for user in users:
  if editor(user):continue
  safe=[r for r in user.roles if r.name not in ['Gamma','Alpha','Admin','sql_lab',VIEWER_ROLE]]
  user.roles=safe+[viewer];count+=1
 db.session.flush()
 for user in users:
  if editor(user):continue
  assert not {'Admin','Alpha','Gamma','sql_lab'} & {r.name for r in user.roles}
  assert VIEWER_ROLE in {r.name for r in user.roles}
 assert scope_before=={r.id:(r.clause,sorted(t.id for t in r.tables),sorted(x.id for x in r.roles)) for r in db.session.query(RowLevelSecurityFilter).all()},'Restrictions territoriales modifiées'
 assert dashboards_before=={d.id:(sorted(r.id for r in d.roles),d.position_json,d.json_metadata,d.published) for d in db.session.query(Dashboard).all()},'Tableaux modifiés'
 db.session.commit()
 print(json.dumps({'status':'OK','viewer_accounts':count,'designated_editors':[u.username for u in users if editor(u)],'viewer_permissions':len(viewer.permissions),'rls':'unchanged','dashboards':'unchanged'}),flush=True)
