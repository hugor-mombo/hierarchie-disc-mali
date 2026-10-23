"""Add native private map tabs to the current GPS dashboard."""
import json
from superset.app import create_app
from site_map import provision_site_map
app=create_app()
with app.app_context():
 from superset import db
 result=provision_site_map(db.session);assert result
 db.session.commit();print(json.dumps(dict(status='OK',**result)),flush=True)
