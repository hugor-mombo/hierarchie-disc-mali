"""Add only the French catalog bind mount to the existing Compose service.

Preserves all image, environment, network, volume and command settings. Backs up
only the Compose file privately; never prints its values or reads credentials.
"""
import argparse,copy,datetime,os,shutil,stat,tempfile
from pathlib import Path
import yaml
parser=argparse.ArgumentParser();parser.add_argument('--compose',type=Path,required=True);parser.add_argument('--backup-dir',type=Path,required=True);args=parser.parse_args()
source='./superset_config/asc-v2/i18n/build/fr';target='/app/superset/translations/fr'
original=yaml.safe_load(args.compose.read_text());updated=copy.deepcopy(original)
service=updated['services']['superset'];volumes=service.setdefault('volumes',[])
current=[v for v in volumes if (v.get('target') if isinstance(v,dict) else v.split(':')[1])==target]
assert len(current)<=1,'Ambiguous French mount'
mount=dict(type='bind',source=source,target=target,read_only=True)
if current:
 assert current[0]==mount,'Existing French mount differs; inspect before changing'
 print('French mount already configured');raise SystemExit(0)
assert (args.compose.parent/source).is_dir(),'Compile the French catalog first'
volumes.append(mount)
check=copy.deepcopy(updated);check['services']['superset']['volumes'].pop()
assert check==original,'Unexpected configuration change'
args.backup_dir.mkdir(parents=True,exist_ok=True)
backup=args.backup_dir/('compose-before-fr-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.yml')
with backup.open('xb') as f:f.write(args.compose.read_bytes())
backup.chmod(0o600)
fd,tmp=tempfile.mkstemp(dir=args.compose.parent,prefix='.compose-fr-')
try:
 with os.fdopen(fd,'w') as f:yaml.safe_dump(updated,f,allow_unicode=True,sort_keys=False)
 os.chmod(tmp,stat.S_IMODE(args.compose.stat().st_mode));os.replace(tmp,args.compose)
finally:
 if os.path.exists(tmp):os.unlink(tmp)
print('French catalog mount installed; private backup: '+str(backup))
