"""Publish only static public basemap files. Site coordinates are never served here."""
import json,os,stat,subprocess
from datetime import datetime,timezone
from pathlib import Path
root=Path('/opt/moh_superset/superset_config/asc-v2/map')
countries=json.loads((root/'countries-v1.geojson').read_text())
assert countries['type']=='FeatureCollection' and 100<len(countries['features'])<300
assert all(f['geometry']['type'] in ['Polygon','MultiPolygon'] and set(f['properties'])=={'code','name'} for f in countries['features'])
style=json.loads((root/'style-v1.json').read_text());assert style['sources']['countries']['data']=='/assets/disc-mali/map/countries-v1.geojson'
assert set(style['sources'])=={'countries'} and 'glyphs' not in style and 'sprite' not in style
config=Path('/etc/nginx/sites-enabled/reporting.disc-mali.ml').resolve();original=config.read_text()
marker='# DISC local public basemap — no site coordinates'
block='''    # DISC local public basemap — no site coordinates
    location = /assets/disc-mali/map/style-v1.json {
        alias /opt/moh_superset/superset_config/asc-v2/map/style-v1.json;
        default_type application/json;
        add_header Cache-Control "public, max-age=300";
        add_header X-Content-Type-Options nosniff always;
    }
    location = /assets/disc-mali/map/countries-v1.geojson {
        alias /opt/moh_superset/superset_config/asc-v2/map/countries-v1.geojson;
        default_type application/json;
        add_header Cache-Control "public, max-age=86400";
        add_header X-Content-Type-Options nosniff always;
    }

'''
if marker in original:
 assert block in original,'Unexpected existing map routes'
 print('Local basemap routes already installed');raise SystemExit(0)
needle='    location / {\n        proxy_pass http://127.0.0.1:8070;'
assert original.count(needle)==1 and 'dashboard.disc-mali.ml' in original
backup=Path('/opt/moh_superset/backups')/('nginx-before-map-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.conf')
with backup.open('x') as f:f.write(original)
backup.chmod(0o600);mode=stat.S_IMODE(config.stat().st_mode)
def write(value):
 p=config.with_name(config.name+'.disc-map-next')
 with p.open('x') as f:f.write(value)
 p.chmod(mode);os.replace(p,config)
write(original.replace(needle,block+needle))
try:
 subprocess.run(['nginx','-t'],check=True);subprocess.run(['systemctl','reload','nginx'],check=True)
except BaseException:
 write(original);subprocess.run(['nginx','-t'],check=False);subprocess.run(['systemctl','reload','nginx'],check=False);raise
print('Public basemap routes installed; all site points remain in authenticated Superset data queries')
