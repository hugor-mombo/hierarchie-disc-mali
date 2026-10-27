import sys,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from disc_portal_policy import editor,viewer_permission,blocked_endpoint
class ConsultationPolicyTest(unittest.TestCase):
 def test_privilege_grants_cannot_turn_a_reader_into_a_designer(self):
  for role in ['Admin','Alpha','Gamma','sql_lab','DISC_NATIONAL']:
   user=SimpleNamespace(username='reader',is_authenticated=True,roles=[SimpleNamespace(name=role)])
   self.assertFalse(editor(user))
  self.assertTrue(editor(SimpleNamespace(username='hmombo',is_authenticated=True,roles=[])))
  self.assertTrue(editor(SimpleNamespace(username='designated',is_authenticated=True,roles=[SimpleNamespace(name='DISC_EDITOR')])))
  self.assertFalse(editor(SimpleNamespace(username='hmombo',is_authenticated=False,roles=[])))
 def test_visualisation_and_filter_state_are_distinct_from_authoring(self):
  for view in ['Chart','Dashboard','Dataset','Database','SavedQuery','ReportSchedule','Row Level Security','Tag']:
   self.assertFalse(viewer_permission('can_write',view),view)
  self.assertFalse(viewer_permission('can_execute_sql_query','SQLLab'))
  self.assertFalse(viewer_permission('all_datasource_access','all_datasource_access'))
  self.assertTrue(viewer_permission('can_read','Chart'))
  self.assertTrue(viewer_permission('can_write','DashboardFilterStateRestApi'))
  self.assertTrue(viewer_permission('can_write','DashboardPermalinkRestApi'))
  self.assertTrue(viewer_permission('can_csv','Superset'))
  self.assertTrue(viewer_permission('can_this_form_post','ResetMyPasswordView'))
 def test_direct_authoring_routes_are_blocked_but_rendering_is_kept(self):
  for endpoint in ['DatasetEditor.root','DatasetEditor.show','TableModelView.list','SliceModelView.list','ExploreView.root','Superset.explore','SqlLabRestApi.execute_sql_query','SqllabView.root','ExploreFormDataRestApi.post']:
   self.assertTrue(blocked_endpoint(endpoint),endpoint)
  for endpoint in [None,'ChartRestApi.data','DashboardRestApi.get_charts','DashboardFilterStateRestApi.post']:
   self.assertFalse(blocked_endpoint(endpoint),endpoint)
if __name__=='__main__':unittest.main()
