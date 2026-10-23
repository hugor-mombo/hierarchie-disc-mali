"""Translate only human-facing labels; preserve identifiers, SQL, roles and charts."""
import json
from pathlib import Path
from superset.app import create_app
ROOT=Path(__file__).resolve().parent
labels=json.loads((ROOT/'fr-data-labels.json').read_text())
app=create_app()
with app.app_context():
 from superset import db
 from superset.connectors.sqla.models import SqlaTable
 changes=[]
 for ds in db.session.query(SqlaTable).all():
  before=(ds.sql,ds.database_id,[(c.id,c.column_name,c.expression,c.type) for c in ds.columns],[(m.id,m.metric_name,m.expression) for m in ds.metrics])
  for col in ds.columns:
   if col.column_name not in labels:continue
   if col.verbose_name and col.verbose_name!=col.column_name:continue
   label=labels[col.column_name]
   if ds.database_id==2 and col.column_name in ['health_area','health_area_uuid']:
    label='Zone ASA (ancien champ aire de santé)' if col.column_name=='health_area' else 'Identifiant zone ASA (ancien champ aire de santé)'
   col.verbose_name=label;changes.append((ds.id,col.column_name))
  for metric in ds.metrics:
   if metric.verbose_name and metric.verbose_name not in [metric.metric_name,'COUNT(*)']:continue
   label='Lignes de relevé' if metric.metric_name=='count' else labels.get(metric.metric_name)
   if label:metric.verbose_name=label;changes.append((ds.id,metric.metric_name))
  assert before==(ds.sql,ds.database_id,[(c.id,c.column_name,c.expression,c.type) for c in ds.columns],[(m.id,m.metric_name,m.expression) for m in ds.metrics]),'Unexpected technical change'
 db.session.commit()
 print(json.dumps(dict(status='OK',labels_updated=len(changes),datasets=len({x[0] for x in changes}),technical_identifiers_unchanged=True)),flush=True)
