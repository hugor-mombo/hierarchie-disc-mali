"""Update only the existing PEC dashboard's method text, preserving its filters and charts."""
import json
from uuid import UUID,uuid5
from superset.app import create_app
from theme_sql import CATALOG,NS
app=create_app()
old='Les observations de morbidité ne sont pas des personnes distinctes et les diagnostics peuvent se cumuler sur une consultation. La source historique retient les suivis dans les sites/mois avec nouvelles consultations : les seuls suivis peuvent être absents. Aucun taux de morbidité ni total de patients issu de l’addition des diagnostics n’est calculé.'
new=next(t for t in CATALOG if t['key']=='pec-enfant')['method']
with app.app_context():
 from superset import db
 from superset.models.dashboard import Dashboard
 d=db.session.query(Dashboard).filter_by(uuid=uuid5(UUID(NS),'dashboard:pec-enfant')).one()
 before=(d.json_metadata,sorted(c.id for c in d.slices),d.css,d.published,sorted(r.id for r in d.roles))
 layout=json.loads(d.position_json);found=0;changed=0
 for n in layout.values():
  if not isinstance(n,dict) or n.get('type')!='MARKDOWN':continue
  code=n['meta']['code']
  if new in code:found+=1
  elif old in code:n['meta']['code']=code.replace(old,new);found+=1;changed+=1
 assert found==2,'Emplacements de méthode inattendus'
 if changed:d.position_json=json.dumps(layout,ensure_ascii=False)
 assert before==(d.json_metadata,sorted(c.id for c in d.slices),d.css,d.published,sorted(r.id for r in d.roles))
 db.session.commit();print(json.dumps(dict(status='OK',dashboard_id=d.id,method_notes_updated=changed)))
