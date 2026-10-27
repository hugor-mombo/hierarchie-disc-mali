"""Consultation Superset : capacités explicites, indépendantes des rôles de base."""
VIEWER_ROLE='DISC_VIEWER'
EDITOR_ROLE='DISC_EDITOR'
EDITOR_USERS=frozenset({'hmombo'})
READ_PERMISSIONS={
 'can_read': {'AdvancedDataType','AvailableDomains','Chart','Dashboard','Dataset','DashboardFilterStateRestApi','DashboardPermalinkRestApi','SecurityRestApi'},
 'can_write': {'DashboardFilterStateRestApi','DashboardPermalinkRestApi'},
 'menu_access': {'Dashboards'},
 'can_get': {'Datasource','MenuApi'},
 'can_list': {'AsyncEventsRestApi'},
 'can_csv': {'Superset'},'can_dashboard': {'Superset'},'can_dashboard_permalink': {'Superset'},
 'can_drill': {'Dashboard'},'can_view_chart_as_table': {'Dashboard'},
 'can_explore_json': {'Superset'},'can_fetch_datasource_metadata': {'Superset'},
 'can_query': {'Api'},'can_query_form_data': {'Api'},'can_time_range': {'Api'},
 'can_share_dashboard': {'Superset'},'can_log': {'Superset'},
 'can_this_form_get': {'ResetMyPasswordView'},'can_this_form_post': {'ResetMyPasswordView'},
 'can_userinfo': {'UserDBModelView'},'resetmypassword': {'UserDBModelView'},
}
DATA_PERMISSIONS={'datasource_access','database_access','schema_access'}
def editor(user):
 return bool(user and getattr(user,'is_authenticated',False) and (
  getattr(user,'username',None) in EDITOR_USERS or any(r.name==EDITOR_ROLE for r in user.roles)))
def viewer_permission(permission,view):
 return permission in DATA_PERMISSIONS or view in READ_PERMISSIONS.get(permission,set())
BLOCKED_ENDPOINTS={
 'SliceModelView.list','TableModelView.list','DatabaseView.list','ChartRestApi.get_list',
 'ExploreView.root','Superset.explore','Superset.slice','Superset.add_slices',
 'Superset.sqllab_history','Superset.sqllab','Superset.sql_json',
}
BLOCKED_PREFIXES=('SqlLabRestApi.','SqllabView.','SavedQuery','ExploreRestApi.',
 'ExploreFormDataRestApi.','ExplorePermalink','TableSchemaView.','TabStateView.')
def blocked_endpoint(endpoint):
 return bool(endpoint and (endpoint in BLOCKED_ENDPOINTS or endpoint.startswith(BLOCKED_PREFIXES)))
