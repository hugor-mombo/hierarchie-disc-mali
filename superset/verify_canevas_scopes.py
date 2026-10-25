"""Verify district restrictions on the new TB datasets and the thematic hub."""
from uuid import UUID,uuid5
from sqlalchemy import text
from superset.app import create_app
from theme_sql import NS
app=create_app()
with app.app_context():
 from superset import db,security_manager as sm
 from superset.models.core import Database
 from superset.connectors.sqla.models import SqlaTable,RowLevelSecurityFilter
 from flask import g
 from flask_login import login_user
 datasets=[db.session.query(SqlaTable).filter_by(uuid=uuid5(UUID(NS),'dataset:'+key)).one() for key in ['tuberculose','tuberculose:indicators','availability']]
 rule=next(r for r in db.session.query(RowLevelSecurityFilter).all() if r.name.startswith('DISC_RLS_DISTRICT_') and r.clause!='1 = 0' and r.roles)
 reader=next(u for u in db.session.query(sm.user_model).filter(sm.user_model.roles.any(id=rule.roles[0].id)).all() if u.is_active and not any(role.name in ['Admin','Alpha','DISC_NATIONAL'] for role in u.roles))
 import re
 district=re.search("district_uuid='([^']+)'",rule.clause).group(1)
 with app.test_request_context('/'):
  login_user(reader);g.user=reader
  for ds in datasets:
   assert ds in rule.tables,(ds.id,'District rule absent')
   result=ds.query(dict(columns=['district_uuid'],metrics=[],granularity=None,is_timeseries=False,from_dttm=None,to_dttm=None,row_limit=1000,filter=[],orderby=[],extras={'where':'','having':''}))
   assert not result.error_message,(ds.id,result.error_message)
   seen=set(result.df['district_uuid']) if not result.df.empty else set()
   assert seen.issubset({district}),(ds.id,'Out-of-district values')
   with db.session.query(Database).filter_by(id=1).one().get_sqla_engine() as e:
    with e.connect() as c:expected=c.execute(text('SELECT count(*) FROM ('+ds.sql+')q WHERE '+rule.clause)).scalar()
   assert bool(seen)==bool(expected),(ds.id,'Allowed district data lost')
 print('District : jeux TB et portail thématique, périmètre autorisé et absence de fuite OK',flush=True)
