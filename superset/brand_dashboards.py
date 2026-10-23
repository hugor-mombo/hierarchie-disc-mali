"""Apply the institutional banner without rerunning chart/dataset provisioning."""
import argparse,json
from superset.app import create_app
from dashboard_branding import brand_primary_dashboards
parser=argparse.ArgumentParser();parser.add_argument('--ids',nargs='+',type=int);parser.add_argument('--dry-run',action='store_true');args=parser.parse_args()
app=create_app()
with app.app_context():
 from superset import db
 result=brand_primary_dashboards(db.session,args.ids)
 assert result,'No selected dashboard'
 if args.dry_run:db.session.rollback()
 else:db.session.commit()
 print(json.dumps(dict(status='OK',dry_run=args.dry_run,dashboards=result,count=len(result)),ensure_ascii=False),flush=True)
