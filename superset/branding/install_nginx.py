"""Install one exact public PNG route, preserving the existing proxy and TLS setup."""
import hashlib,os,stat,subprocess
from datetime import datetime,timezone
from pathlib import Path
asset=Path('/opt/moh_superset/superset_config/asc-v2/branding/armoiries-mali-87405e53.png')
assert hashlib.sha256(asset.read_bytes()).hexdigest()=='87405e53f11a45e811db7ff0b2038b748acf50f9cef9799a85a6cf61b6668bc0','Unexpected emblem asset'
config=Path('/etc/nginx/sites-enabled/reporting.disc-mali.ml').resolve()
original=config.read_text();marker='# DISC institutional emblem — exact public asset only'
block='''    # DISC institutional emblem — exact public asset only
    location = /assets/disc-mali/armoiries-mali-87405e53.png {
        alias /opt/moh_superset/superset_config/asc-v2/branding/armoiries-mali-87405e53.png;
        default_type image/png;
        add_header Cache-Control "public, max-age=31536000, immutable";
        add_header X-Content-Type-Options nosniff always;
    }

'''
if marker in original:
 assert block in original,'Existing branding route differs; inspect before changing'
 print('Emblem asset route already installed');raise SystemExit(0)
needle='    location / {\n        proxy_pass http://127.0.0.1:8070;'
assert original.count(needle)==1 and 'dashboard.disc-mali.ml' in original,'Unexpected Superset virtual host'
updated=original.replace(needle,block+needle)
backup=Path('/opt/moh_superset/backups')/('nginx-before-branding-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.conf')
with backup.open('x') as f:f.write(original)
backup.chmod(0o600)
mode=stat.S_IMODE(config.stat().st_mode)
def write(value):
 temporary=config.with_name(config.name+'.disc-branding-next')
 with temporary.open('x') as f:f.write(value)
 temporary.chmod(mode);os.replace(temporary,config)
write(updated)
try:
 subprocess.run(['nginx','-t'],check=True)
 subprocess.run(['systemctl','reload','nginx'],check=True)
except BaseException:
 write(original)
 subprocess.run(['nginx','-t'],check=False)
 subprocess.run(['systemctl','reload','nginx'],check=False)
 raise
print('Emblem asset route installed; proxy and TLS preserved; private backup: '+str(backup))
