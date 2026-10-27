"""Points d'extension Superset 5 / FAB : connexion, accueil et consultation."""
from pathlib import Path
from flask import abort,g,redirect,request,send_from_directory
from flask_appbuilder import IndexView,expose
from flask_appbuilder.security.views import AuthDBView
from jinja2 import ChoiceLoader,FileSystemLoader
from superset.security import SupersetSecurityManager
from disc_portal_policy import editor,viewer_permission,blocked_endpoint
ROOT=Path(__file__).resolve().parent
CATALOG='/dashboard/list/'
class DiscAuthDBView(AuthDBView):
 login_template='disc/login.html'
 title='Connexion à DISC-Mali'
 invalid_login_message='Identifiant ou mot de passe incorrect.'
class DiscSecurityManager(SupersetSecurityManager):
 authdbview=DiscAuthDBView
 def _has_view_access(self,user,permission_name,view_name):
  if getattr(user,'is_authenticated',False) and not editor(user) and not viewer_permission(permission_name,view_name):
   return False
  return super()._has_view_access(user,permission_name,view_name)
 def get_user_roles_permissions(self,user):
  permissions=super().get_user_roles_permissions(user)
  if editor(user):return permissions
  return {name:[p for p in pairs if viewer_permission(*p)] for name,pairs in permissions.items()}
class DiscIndexView(IndexView):
 @expose('/')
 def index(self):
  return redirect(CATALOG if getattr(g,'user',None) and g.user.is_authenticated else '/login/')
def configure_portal(app):
 app.jinja_loader=ChoiceLoader([FileSystemLoader(str(ROOT/'templates')),app.jinja_loader])
 @app.get('/disc-assets/portal.css')
 def disc_portal_css():
  return send_from_directory(ROOT/'static','portal.css',max_age=3600)
 @app.before_request
 def disc_navigation_policy():
  user=getattr(g,'user',None)
  if not user or not user.is_authenticated:return None
  if request.path.rstrip('/') in ('','/superset/welcome'):
   return redirect(CATALOG)
  if not editor(user) and blocked_endpoint(request.endpoint):abort(403)
  return None
