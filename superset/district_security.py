"""District read scopes complement existing regional RLS without changing regional users."""
from superset import db
PREFIX='DISC_RLS_DISTRICT_'
DENY_NAME=PREFIX+'UNSUPPORTED'
def supported(dataset):
 return dataset.database_id==1 and {'region_uuid','district_uuid'}.issubset({c.column_name for c in dataset.columns})
def apply_district_security(datasets):
 from superset.connectors.sqla.models import RowLevelSecurityFilter
 rules=[r for r in db.session.query(RowLevelSecurityFilter).all() if r.name.startswith(PREFIX) and r.name!=DENY_NAME]
 if not rules:return 0
 roles={role.id:role for rule in rules for role in rule.roles}
 assert roles and all(role.name.startswith('DISC_DISTRICT_') for role in roles.values()),'Unexpected district role'
 deny=db.session.query(RowLevelSecurityFilter).filter_by(name=DENY_NAME).one_or_none()
 if deny is None:
  deny=RowLevelSecurityFilter(name=DENY_NAME,filter_type=rules[0].filter_type,clause='1 = 0',group_key=None);db.session.add(deny)
 assert deny.clause=='1 = 0'
 deny.roles=list(roles.values())
 for dataset in datasets:
  safe=supported(dataset)
  for rule in rules:
   attached=any(t.id==dataset.id for t in rule.tables)
   if safe and not attached:rule.tables.append(dataset)
   elif not safe and attached:rule.tables=[t for t in rule.tables if t.id!=dataset.id]
  attached=any(t.id==dataset.id for t in deny.tables)
  if not safe and not attached:deny.tables.append(dataset)
  elif safe and attached:deny.tables=[t for t in deny.tables if t.id!=dataset.id]
 # The existing derived-data base rule denies unscoped readers. Exempt only the
 # newly scoped roles; their regular district rule still applies to every query.
 base=db.session.query(RowLevelSecurityFilter).filter_by(name='DISC_RLS_DERIVED_DEFAULT_DENY').one()
 known={r.id:r for r in base.roles};known.update(roles);base.roles=list(known.values())
 db.session.flush();return len(rules)
