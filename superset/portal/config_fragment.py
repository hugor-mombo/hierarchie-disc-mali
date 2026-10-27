# DISC portal: import from the mounted, versioned project (no secrets here).
import sys
_disc_portal_path='/app/superset_config/asc-v2/portal'
if _disc_portal_path not in sys.path:
    sys.path.insert(0,_disc_portal_path)
from disc_portal import DiscSecurityManager,configure_portal
CUSTOM_SECURITY_MANAGER=DiscSecurityManager
FAB_INDEX_VIEW='disc_portal.DiscIndexView'
FLASK_APP_MUTATOR=configure_portal
APP_NAME='DISC-Mali · Santé communautaire'
APP_ICON='/assets/disc-mali/armoiries-mali-87405e53.png'
LOGO_TARGET_PATH='/dashboard/list/'
