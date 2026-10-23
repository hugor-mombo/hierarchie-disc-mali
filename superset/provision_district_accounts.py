"""Create district counterparts to reg_* readers. Secrets stay in a private recovery file."""
import argparse,json,os,re,secrets,string,unicodedata
from collections import Counter
from pathlib import Path
from uuid import UUID
from sqlalchemy import text
from superset.app import create_app
from district_security import apply_district_security,supported
parser=argparse.ArgumentParser();parser.add_argument('--state',required=True);parser.add_argument('--dry-run',action='store_true');args=parser.parse_args()
state_path=Path(args.state);app=create_app()
def slug(name):
 value=unicodedata.normalize('NFKD',name).encode('ascii','ignore').decode().lower()
 value=re.sub(r'^district\s+(sanitaire\s+)?','',value)
 return re.sub(r'[^a-z0-9]+','_',value).strip('_')
def password():
 alphabet='ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#%'
 while True:
  value=''.join(secrets.choice(alphabet) for _ in range(20))
  if all(any(c in category for c in value) for category in [string.ascii_uppercase,string.ascii_lowercase,string.digits,'!@#%']):return value

def save(state):
 state_path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 temporary=state_path.with_name(state_path.name+'.next')
 with os.fdopen(os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600),'w') as f:json.dump(state,f,ensure_ascii=False)
 os.replace(temporary,state_path);state_path.chmod(0o600)

with app.app_context():
 from superset import db,security_manager as sm
 from superset.models.core import Database
 from superset.connectors.sqla.models import SqlaTable,RowLevelSecurityFilter
 reference=sm.find_user(username='reg_bougouni');assert reference and reference.active
 common=[r for r in reference.roles if not r.name.startswith('DISC_REGION_')]
 assert {r.name for r in common}=={'Gamma','DISC_DASH_ASC_ACTIVITY','DISC_DASH_ASC_SUPERVISION','DISC_DASH_SEBAC'}
 dangerous={'all_database_access','all_datasource_access','can_sql_json','can_sqllab','can_execute_sql_query'}
 assert not [(p.permission.name,p.view_menu.name) for r in common for p in r.permissions if p.permission.name in dangerous],'Reference reader has SQL or global-data privileges'
 database=db.session.query(Database).filter_by(id=1).one()
 with database.get_sqla_engine() as engine:
  with engine.connect() as c:
   c.execute(text('SET TRANSACTION READ ONLY'));c.execute(text("SET LOCAL statement_timeout='120s'"))
   sql="""SELECT d.uuid AS district_uuid,d.name AS district_name,d.parent_uuid AS region_uuid,r.name AS region,
   (SELECT count(*) FROM mv_superset_sd_portfolio p WHERE p.district_uuid=d.uuid AND p.region_uuid=r.uuid) AS sites
   FROM contactview_metadata d JOIN contactview_metadata r ON r.uuid=d.parent_uuid AND r.contact_type='c20_region'
   WHERE d.contact_type='c30_district' ORDER BY r.name,d.name,d.uuid"""
   registry=[dict(r._mapping) for r in c.execute(text(sql))]
 assert registry and len(registry)==len({r['district_uuid'] for r in registry})
 for r in registry:UUID(r['district_uuid']);UUID(r['region_uuid']);assert r['district_name'] and r['region']
 counts=Counter(slug(r['district_name']) for r in registry)
 for r in registry:
  base=slug(r['district_name']);assert base
  if counts[base]>1:base+='_'+slug(r['region'])
  r['username']='dist_'+base
 collisions=Counter(r['username'] for r in registry)
 for r in registry:
  if collisions[r['username']]>1:r['username']+='_'+r['district_uuid'][:8]
  r['role']='DISC_DISTRICT_'+r['username'][5:]
 assert len({r['username'] for r in registry})==len(registry)
 assert all(len(r['username'])<=64 and len(r['role'])<=64 for r in registry)
 prior=json.loads(state_path.read_text()) if state_path.exists() else {'accounts':[]}
 saved={r['district_uuid']:r for r in prior['accounts']}
 for r in registry:
  user=sm.find_user(username=r['username']);old=saved.get(r['district_uuid'])
  if old:assert old['username']==r['username'] and old['region_uuid']==r['region_uuid'],'Registry changed; inspect before renaming accounts'
  email_user=sm.find_user(email=r['username']+'@dashboard.disc-mali.ml')
  assert email_user is None or email_user.username==r['username'],'Email collision'
  if user:
   assert old and old['username']==r['username'] and old['region_uuid']==r['region_uuid'],'Existing account outside this recovery file; no password reset performed'
   assert {x.name for x in user.roles}=={x.name for x in common}|{r['role']},'Existing role mismatch'
 if args.dry_run:
  print(json.dumps(dict(status='OK',dry_run=True,districts=len(registry),regions=len({r['region_uuid'] for r in registry}),without_sites=sum(r['sites']==0 for r in registry),reader_profile=sorted(r.name for r in common)),ensure_ascii=False));raise SystemExit(0)
 regular=db.session.query(RowLevelSecurityFilter).filter_by(name='DISC_RLS_REGION_bougouni').one().filter_type
 for r in registry:
  role=sm.find_role(r['role'])
  if role is None:role=sm.add_role(r['role'])
  assert not role.permissions,'Scope role must grant no global permissions'
  name='DISC_RLS_DISTRICT_'+r['username'][5:]
  rule=db.session.query(RowLevelSecurityFilter).filter_by(name=name).one_or_none()
  clause="district_uuid='"+r['district_uuid']+"' AND region_uuid='"+r['region_uuid']+"'"
  if rule is None:rule=RowLevelSecurityFilter(name=name,filter_type=regular,clause=clause,group_key=None);db.session.add(rule)
  assert rule.clause==clause and rule.group_key is None,'District rule collision'
  rule.roles=[role]
  # Attach first to the reference dataset so future derived-source provisioning
  # discovers the scoped role and keeps the base default-deny exception correct.
  reference_ds=db.session.query(SqlaTable).filter_by(id=7).one();assert supported(reference_ds)
  if not any(t.id==7 for t in rule.tables):rule.tables.append(reference_ds)
 db.session.flush();apply_district_security(db.session.query(SqlaTable).all());db.session.commit()
 state={'base_url':'https://dashboard.disc-mali.ml/','generated_on':'2026-10-23','status':'pending_verification','accounts':[]}
 for r in registry:
  record={**r,'password':saved.get(r['district_uuid'],{}).get('password') or password(),'active':False,'verification':'À vérifier'}
  state['accounts'].append(record)
 assert len({r['password'] for r in state['accounts']})==len(registry),'Passwords must be unique'
 save(state)
 created=0
 for record in state['accounts']:
  user=sm.find_user(username=record['username'])
  if user is None:
   user=sm.add_user(username=record['username'],first_name=record['district_name'],last_name='DISTRICT',email=record['username']+'@dashboard.disc-mali.ml',role=common+[sm.find_role(record['role'])],password=record['password'])
   assert user,'Account creation failed'
   user.active=False;db.session.commit();created+=1
  record['user_id']=user.id;record['active']=user.active;save(state)
 print(json.dumps(dict(status='created_pending_verification',districts=len(registry),new_accounts=created,private_state=str(state_path)),ensure_ascii=False),flush=True)
